"""Execute selector failure/dispatch and exercise ownership boundaries without a VM."""
import importlib.util
import json
import os
import pathlib
import shutil
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
            if argv[:3] == ['systemctl', 'show', 'xray']: out = 'not-found\n'
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

    def test_executed_dispatch_isolates_native_and_docker_roles(self):
        # Execute the real orchestration/defaults with harmless role sentinels.
        # This checks Ansible's conditions, rather than only YAML syntax/text.
        for mode in ['native', 'docker']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                directory = pathlib.Path(tmp) / 'ansible'
                shutil.copytree(ROOT / 'ansible', directory)
                scripts = pathlib.Path(tmp) / 'scripts'; scripts.mkdir()
                (scripts / 'runtime-ownership.py').write_text('import json\nprint(json.dumps(dict(native_exists=False,native_running=False,native_enabled=False,docker_exists=False,docker_running=False,docker_id="")))\n')
                for role in ['proxy_host_policy','xray_common','docker_prereqs','xray_native','xray_deploy']:
                    (directory / f'roles/{role}/tasks/main.yml').write_text('- name: '+role+' sentinel\n  ansible.builtin.debug:\n    msg: EXECUTED_'+role+' {{ xray_config_path }}\n')
                result = self.run_play(directory, mode)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('/usr/local/etc/xray' if mode=='native' else '/opt/xray/config', result.stdout)
                self.assertIn('EXECUTED_xray_'+('native' if mode=='native' else 'deploy'), result.stdout)
                if mode=='native':
                    self.assertNotIn('EXECUTED_docker_prereqs', result.stdout)
                    self.assertNotIn('EXECUTED_xray_deploy', result.stdout)
                else:
                    self.assertIn('EXECUTED_docker_prereqs', result.stdout)
                    self.assertNotIn('EXECUTED_xray_native', result.stdout)

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
                for role in ['proxy_host_policy','xray_common','docker_prereqs','xray_native','xray_deploy']:
                    (directory / f'roles/{role}/tasks/main.yml').write_text('- name: harmless sentinel\n  ansible.builtin.debug:\n    msg: ROLE_EXECUTED\n')
                rejected = self.run_play(directory, mode)
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn('Opposite runtime exists', rejected.stdout)
                self.assertNotIn('ROLE_EXECUTED', rejected.stdout)
                accepted = self.run_play(directory, mode, {'xray_allow_runtime_switch': True})
                self.assertEqual(accepted.returncode, 0, accepted.stdout+accepted.stderr)
                self.assertIn('ROLE_EXECUTED', accepted.stdout)

    def test_lifecycle_tags_select_only_existing_runtime_without_installation(self):
        for mode in ['native', 'docker']:
            for tag in ['xray_down', 'xray_reload', 'xray_recreate']:
                with self.subTest(mode=mode, tag=tag), tempfile.TemporaryDirectory() as tmp:
                    directory = pathlib.Path(tmp) / 'ansible'
                    shutil.copytree(ROOT / 'ansible', directory)
                    scripts = pathlib.Path(tmp) / 'scripts'; scripts.mkdir()
                    state = dict(native_exists=mode=='native', native_running=mode=='native',
                                 native_enabled=mode=='native', docker_exists=mode=='docker',
                                 docker_running=mode=='docker', docker_id='owned')
                    (scripts / 'runtime-ownership.py').write_text('print('+repr(json.dumps(state))+')\n')
                    for role in ['proxy_host_policy','xray_common','docker_prereqs','xray_native','xray_deploy']:
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
                    self.assertIn('LIFECYCLE_xray_'+('native' if mode=='native' else 'deploy'),result.stdout)
                    self.assertNotIn('Unexpected normal deployment task',result.stdout)
                    self.assertNotIn('LIFECYCLE_xray_'+('deploy' if mode=='native' else 'native'),result.stdout)

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
