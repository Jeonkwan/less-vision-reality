"""Execute selector failure/dispatch and exercise ownership boundaries without a VM."""
import importlib.util
import json
import os
import pathlib
import shutil
import socket
import subprocess
import tempfile
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ownership', ROOT / 'scripts/runtime-ownership.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Ownership(unittest.TestCase):
    def inspect(self, labels=None, source='/opt/xray/config', daemon_fails=False):
        labels = labels if labels is not None else {
            'com.docker.compose.project': 'xray', 'com.docker.compose.service': 'xray',
            'com.docker.compose.project.working_dir': '/opt/xray',
            'com.docker.compose.project.config_files': '/opt/xray/docker-compose.yml'}
        data = [{'Config': {'Labels': labels}, 'State': {'Running': True}, 'Id': 'owned-id',
                 'Mounts': [{'Source': source, 'Destination': '/usr/local/etc/xray'}]}]
        def call(argv, **kwargs):
            if argv == ['docker', 'info'] and daemon_fails:
                raise subprocess.CalledProcessError(1, argv)
            if argv[:2] == ['systemctl', 'show']: out = 'not-found\n'
            elif argv[:3] == ['docker', 'container', 'ls']: out = 'owned-id\n'
            elif argv[:2] == ['docker', 'inspect']: out = json.dumps(data)
            else: out = ''
            return subprocess.CompletedProcess(argv, 0, out, '')
        with tempfile.TemporaryDirectory() as tmp:
            return module.inspect(pathlib.Path(tmp), call, docker=True)

    def test_legacy_compose_ownership_is_recognized(self):
        self.assertEqual(self.inspect()['docker_id'], 'owned-id')

    def test_unrelated_container_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'unmanaged container'):
            self.inspect(labels={'com.docker.compose.project': 'other'})

    def test_unrelated_configuration_mount_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'unrelated configuration'):
            self.inspect(source='/opt/other')

    def test_daemon_failure_is_not_absence(self):
        with self.assertRaises(subprocess.CalledProcessError): self.inspect(daemon_fails=True)

    def test_absent_unit_exit_one_is_recognized(self):
        def call(argv, **kwargs):
            rc,out=(1,'not-found') if argv[1]=='show' else (3,'inactive')
            if kwargs.get('check') and rc:
                raise subprocess.CalledProcessError(rc,argv)
            return subprocess.CompletedProcess(argv,rc,out,'')
        with tempfile.TemporaryDirectory() as tmp:
            data=module.inspect(pathlib.Path(tmp),call,docker=False)
            self.assertFalse(data['native_exists'])
            self.assertFalse(data['native_running'])

    def test_unrelated_native_unit_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp); unit = root / 'etc/systemd/system/xray.service'
            unit.parent.mkdir(parents=True); unit.write_text('[Service]\nUser=root\n')
            with self.assertRaisesRegex(RuntimeError, 'unmanaged xray.service'):
                module.inspect(root, docker=False)

    def test_unmarked_docker_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp); (root / 'opt/xray').mkdir(parents=True)
            def call(argv, **kwargs):
                return subprocess.CompletedProcess(argv, 0, 'not-found' if argv[1]=='show' else '', '')
            with self.assertRaisesRegex(RuntimeError, 'unmarked'):
                module.inspect(root, call, docker=False)


class Selector(unittest.TestCase):
    def test_port_probe_rejects_and_preserves_unrelated_listener(self):
        task=yaml.safe_load((ROOT/'ansible/tasks/switch-runtime.yml').read_text())[-1]
        probe=task['ansible.builtin.command']['argv'][:3]
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen()
            port=listener.getsockname()[1]
            result=subprocess.run(probe+[str(port)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Address already in use',result.stderr)
            with socket.create_connection(('127.0.0.1',port),timeout=1):pass

    def run_play(self, directory, mode, extra=None, tags=None):
        inventory = directory / 'inventory.yml'
        inventory.write_text('all:\n  children:\n    xray_servers:\n      hosts:\n        test:\n          ansible_connection: local\n')
        env = {**os.environ, 'ANSIBLE_LOCAL_TEMP': '/tmp/ansible-local',
               'ANSIBLE_REMOTE_TEMP': '/tmp/ansible-remote',
               'XRAY_PRIVATE_KEY': 'FAKE_PRIVATE_KEY', 'XRAY_PUBLIC_KEY': 'FAKE_PUBLIC_KEY'}
        return subprocess.run(['ansible-playbook', '-i', str(inventory), str(directory / 'site.yml'),
                               '-e', json.dumps({'xray_deployment_mode': mode, 'ansible_become': False, **(extra or {})})] + (['--tags', tags] if tags else []),
                              env=env, text=True, capture_output=True)

    def test_real_invalid_selector_fails_before_host_operations(self):
        # Inventory lives outside the repo; real site/defaults are used.
        with tempfile.TemporaryDirectory() as tmp:
            inventory = pathlib.Path(tmp) / 'inventory.yml'
            inventory.write_text('all:\n  children:\n    xray_servers:\n      hosts:\n        unreachable:\n          ansible_host: invalid.example\n')
            result = subprocess.run(['ansible-playbook', '-i', str(inventory), str(ROOT / 'ansible/site.yml'),
                                     '-e', 'xray_deployment_mode=invalid'],
                                    env={**os.environ, 'ANSIBLE_LOCAL_TEMP': '/tmp/ansible-local'},
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Unsupported runtime', result.stdout)
            self.assertNotIn('Inspect managed runtimes', result.stdout)
            self.assertNotIn('UNREACHABLE!', result.stdout)

    def test_unreviewed_or_mismatched_image_fails_before_host_operations(self):
        for overrides in [{'xray_container_image_version':'latest'},
                          {'xray_container_image_version':'26.3.27',
                           'xray_container_image':'ghcr.io/xtls/xray-core:25.10.15'}]:
            with self.subTest(overrides=overrides), tempfile.TemporaryDirectory() as tmp:
                directory=pathlib.Path(tmp)/'ansible'
                shutil.copytree(ROOT/'ansible',directory)
                result=self.run_play(directory,'docker',overrides)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('Unsupported runtime',result.stdout)
                self.assertNotIn('Inspect managed runtimes',result.stdout)

    def test_executed_dispatch_isolates_native_and_docker_roles(self):
        # Execute the real orchestration/defaults with harmless role sentinels.
        # This checks Ansible's conditions, rather than only YAML syntax/text.
        for mode in ['native', 'docker', 'podman']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                directory = pathlib.Path(tmp) / 'ansible'
                shutil.copytree(ROOT / 'ansible', directory)
                scripts = pathlib.Path(tmp) / 'scripts'; scripts.mkdir()
                (scripts / 'runtime-ownership.py').write_text('import json\nprint(json.dumps(dict(native_exists=False,native_running=False,native_enabled=False,docker_exists=False,docker_running=False,docker_id="")))\n')
                for role in ['proxy_host_policy','xray_common','docker_prereqs','xray_native','xray_deploy','podman_prereqs','xray_podman']:
                    (directory / f'roles/{role}/tasks/main.yml').write_text('- name: '+role+' sentinel\n  ansible.builtin.debug:\n    msg: EXECUTED_'+role+' {{ xray_config_path }}\n')
                result = self.run_play(directory, mode)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn({'native':'/usr/local/etc/xray','docker':'/opt/xray/config','podman':'/opt/xray-podman/config'}[mode], result.stdout)
                self.assertIn('EXECUTED_xray_'+{'native':'native','docker':'deploy','podman':'podman'}[mode], result.stdout)
                if mode=='native':
                    self.assertNotIn('EXECUTED_docker_prereqs', result.stdout)
                    self.assertNotIn('EXECUTED_xray_deploy', result.stdout)
                elif mode=='docker':
                    self.assertIn('EXECUTED_docker_prereqs', result.stdout)
                    self.assertNotIn('EXECUTED_xray_native', result.stdout)
                else:
                    self.assertIn('EXECUTED_podman_prereqs', result.stdout)
                    self.assertNotIn('EXECUTED_docker_prereqs', result.stdout)
                    self.assertNotIn('EXECUTED_xray_native', result.stdout)
                    self.assertNotIn('EXECUTED_xray_deploy', result.stdout)

    def test_active_opposite_requires_opt_in_before_any_role(self):
        for mode in ['native', 'docker']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                directory = pathlib.Path(tmp) / 'ansible'
                shutil.copytree(ROOT / 'ansible', directory)
                scripts = pathlib.Path(tmp) / 'scripts'; scripts.mkdir()
                state = dict(native_exists=mode=='docker', native_running=mode=='docker',
                             native_enabled=mode=='docker', docker_exists=mode=='native',
                             docker_running=mode=='native', docker_id='owned')
                (scripts / 'runtime-ownership.py').write_text('print('+repr(json.dumps(state))+')\n')
                for role in ['proxy_host_policy','xray_common','docker_prereqs','xray_native','xray_deploy','podman_prereqs','xray_podman']:
                    (directory / f'roles/{role}/tasks/main.yml').write_text('- name: harmless sentinel\n  ansible.builtin.debug:\n    msg: ROLE_EXECUTED\n')
                rejected = self.run_play(directory, mode)
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn('Opposite runtime exists', rejected.stdout)
                self.assertNotIn('ROLE_EXECUTED', rejected.stdout)
                accepted = self.run_play(directory, mode, {'xray_allow_runtime_switch': True})
                self.assertEqual(accepted.returncode, 0, accepted.stdout+accepted.stderr)
                self.assertIn('ROLE_EXECUTED', accepted.stdout)

    def test_lifecycle_tags_select_only_existing_runtime_without_installation(self):
        for mode in ['native', 'docker', 'podman']:
            for tag in ['xray_down', 'xray_reload', 'xray_recreate']:
                with self.subTest(mode=mode, tag=tag), tempfile.TemporaryDirectory() as tmp:
                    directory = pathlib.Path(tmp) / 'ansible'
                    shutil.copytree(ROOT / 'ansible', directory)
                    scripts = pathlib.Path(tmp) / 'scripts'; scripts.mkdir()
                    state = dict(native_exists=mode=='native', native_running=mode=='native',
                                 native_enabled=mode=='native', docker_exists=mode=='docker',
                                 docker_running=mode=='docker', docker_id='owned',
                                 podman_unit_exists=mode=='podman', podman_running=mode=='podman',podman_enabled=mode=='podman')
                    (scripts / 'runtime-ownership.py').write_text('print('+repr(json.dumps(state))+')\n')
                    for role in ['proxy_host_policy','xray_common','docker_prereqs','xray_native','xray_deploy','podman_prereqs','xray_podman']:
                        taskfile = directory / f'roles/{role}/tasks/main.yml'
                        original = yaml.safe_load(taskfile.read_text())
                        tasks = [{'name': role+' install sentinel', 'ansible.builtin.fail': {'msg':'Unexpected normal deployment task'}}]
                        for task in original:
                            if tag in task.get('tags', []):
                                tasks.append({'name':task['name'], 'tags':task['tags'],
                                              'ansible.builtin.debug':{'msg':'LIFECYCLE_'+role}})
                        taskfile.write_text(yaml.safe_dump(tasks))
                    result = self.run_play(directory, mode, tags=tag)
                    self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                    self.assertIn('LIFECYCLE_xray_'+{'native':'native','docker':'deploy','podman':'podman'}[mode],result.stdout)
                    self.assertNotIn('Unexpected normal deployment task',result.stdout)
                    self.assertNotIn('LIFECYCLE_xray_'+('deploy' if mode=='native' else 'native'),result.stdout)

    def test_controller_cleanup_handles_skipped_registered_result(self):
        cleanup=yaml.safe_load((ROOT/'ansible/roles/xray_native/tasks/main.yml').read_text())[-1]
        for prepared in [False,True]:
            with self.subTest(prepared=prepared),tempfile.TemporaryDirectory() as tmp:
                directory=pathlib.Path(tmp);artifact=directory/'artifact';artifact.mkdir()
                registered={'path':str(artifact)} if prepared else {'skipped':True,'changed':False}
                play=[{'hosts':'all','gather_facts':False,'vars':{'xray_controller_directory':registered},'tasks':[cleanup]}]
                playfile=directory/'play.yml';playfile.write_text(yaml.safe_dump(play))
                result=subprocess.run(['ansible-playbook','-i','localhost,','-c','local',str(playfile)],
                    env={**os.environ,'ANSIBLE_LOCAL_TEMP':'/tmp/ansible-local','ANSIBLE_REMOTE_TEMP':'/tmp/ansible-remote'},capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual(artifact.exists(),not prepared)

    def test_pre_compose_activation_failure_restores_native(self):
        # Execute the actual rescue task conditions with harmless action sentinels.
        with tempfile.TemporaryDirectory() as tmp:
            directory=pathlib.Path(tmp)
            tasks=yaml.safe_load((ROOT/'ansible/tasks/restore-opposite.yml').read_text())
            for task in tasks:
                for action in ['ansible.builtin.command','ansible.builtin.systemd_service']:
                    if action in task:
                        del task[action]
                        task['ansible.builtin.debug']={'msg':'EXECUTED '+task['name']}
            (directory/'restore.yml').write_text(yaml.safe_dump(tasks))
            play=[{'hosts':'all','gather_facts':False,'vars':{
                'xray_deployment_mode':'docker','xray_existing':{
                    'native_exists':True,'native_running':True,'native_enabled':True,
                    'docker_exists':False,'docker_running':False}},
                'tasks':[{'ansible.builtin.include_tasks':str(directory/'restore.yml')}]}]
            (directory/'play.yml').write_text(yaml.safe_dump(play))
            result=subprocess.run(['ansible-playbook','-i','localhost,',str(directory/'play.yml')],
                                  env={**os.environ,'ANSIBLE_LOCAL_TEMP':'/tmp/ansible-local'},
                                  capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('EXECUTED Restore previous verified native service',result.stdout)
            self.assertNotIn('EXECUTED Stop selected Docker service',result.stdout)
            self.assertIn('activation failed',result.stdout)


if __name__ == '__main__': unittest.main()
