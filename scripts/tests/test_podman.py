"""Exercise Podman ownership and all affected switch/recovery boundaries."""
import copy
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
spec = importlib.util.spec_from_file_location('ownership', ROOT/'scripts/runtime-ownership.py')
ownership = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ownership)
ROLES = ['proxy_host_policy', 'xray_common', 'docker_prereqs', 'xray_native',
         'xray_deploy', 'podman_prereqs', 'xray_podman']


def state(mode):
    return dict(native_exists=mode=='native', native_running=mode=='native',
                native_enabled=mode=='native', docker_exists=mode=='docker',
                docker_running=mode=='docker', docker_id='owned-docker',
                podman_unit_exists=mode=='podman', podman_exists=mode=='podman',
                podman_running=mode=='podman', podman_enabled=mode=='podman',
                podman_id='owned-podman')


class PodmanOwnership(unittest.TestCase):
    def probe(self, mutate=None, rootless=False, fail=False, active=True, override=False):
        data = dict(Id='owned-podman', Image='reviewed-digest',
                    Config=dict(Image='ghcr.io/xtls/xray-core:26.3.27', User='65532:65532',
                                Labels=copy.deepcopy(ownership.PODMAN_LABELS)),
                    State=dict(Running=True), AppArmorProfile='containers-default-test',
                    Mounts=[dict(Source='/opt/xray-podman/config',
                                 Destination='/usr/local/etc/xray', RW=False)],
                    HostConfig=dict(Privileged=False, NetworkMode='bridge', PortBindings={'443/tcp':[{'HostPort':'443'}]},
                                    LogConfig={'Type':'journald'}, RestartPolicy={'Name':'no'}))
        if mutate: mutate(data)
        def call(argv, **kwargs):
            if argv[:3] == ownership.PODMAN+['info']:
                if fail: raise subprocess.CalledProcessError(1, argv)
                out=json.dumps({'host':{'security':{'rootless':rootless}}})
            elif argv[:3] == ownership.PODMAN+['container']:out='owned-podman'
            elif argv[:3] == ownership.PODMAN+['inspect']:out=json.dumps([data])
            elif argv[:2] == ['systemctl','is-active']:out='active' if active else 'inactive'
            elif argv[:2] == ['systemctl','is-enabled']:out='enabled'
            else:out='not-found'
            return subprocess.CompletedProcess(argv,0,out,'')
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); unit=root/'etc/systemd/system/xray-podman.service'
            unit.parent.mkdir(parents=True)
            unit.write_text((ROOT/'ansible/templates/xray-podman.service.j2').read_text())
            deployment=root/'opt/xray-podman';deployment.mkdir(parents=True)
            (deployment/'.managed-by-less-vision-reality').write_text(ownership.PODMAN_MARKER)
            if override:
                folder=unit.with_name('xray-podman.service.d');folder.mkdir()
                (folder/'override.conf').write_text('[Service]\nExecStart=/other\n')
            return ownership.inspect_podman(root,call,podman=True)

    def test_owned_container_is_identified(self):
        self.assertEqual(self.probe()['podman_id'],'owned-podman')

    def test_unrelated_labels_mounts_ports_user_and_logging_are_rejected(self):
        mutations=[lambda d:d['Config']['Labels'].clear(),
                   lambda d:d['Mounts'][0].update(Source='/other'),
                   lambda d:d['Mounts'][0].update(RW=True),
                   lambda d:d['HostConfig']['PortBindings'].update({'80/tcp':[{'HostPort':'80'}]}),
                   lambda d:d['Config'].update(User='0'),
                   lambda d:d['HostConfig']['LogConfig'].update(Type='k8s-file'),
                   lambda d:d['HostConfig']['RestartPolicy'].update(Name='always')]
        for mutation in mutations:
            with self.subTest(mutation=mutation),self.assertRaises(RuntimeError):self.probe(mutate=mutation)

    def test_rootless_failure_unsupervised_and_overrides_fail_closed(self):
        for kwargs in [{'rootless':True},{'fail':True},{'active':False},{'override':True}]:
            with self.subTest(kwargs=kwargs),self.assertRaises((RuntimeError,subprocess.CalledProcessError)):
                self.probe(**kwargs)


class ThreeRuntimeSwitches(unittest.TestCase):
    def run_play(self, directory, play, extra=None):
        path=directory/'play.yml';path.write_text(yaml.safe_dump(play))
        return subprocess.run(['ansible-playbook','-i','localhost,','-c','local',str(path),
                               '-e',json.dumps(extra or {})],capture_output=True,text=True,
                              env={**os.environ,'ANSIBLE_LOCAL_TEMP':'/tmp/ansible-local',
                                   'ANSIBLE_REMOTE_TEMP':'/tmp/ansible-remote'})

    def test_lifecycle_activation_cannot_bypass_validated_switch(self):
        for previous in ['native','docker','podman']:
            for selected in ['native','docker','podman']:
                with self.subTest(previous=previous,selected=selected),tempfile.TemporaryDirectory() as tmp:
                    directory=pathlib.Path(tmp);ansible=directory/'ansible'
                    shutil.copytree(ROOT/'ansible',ansible)
                    scripts=directory/'scripts';scripts.mkdir()
                    (scripts/'runtime-ownership.py').write_text('print('+repr(json.dumps(state(previous)))+')\n')
                    for role in ROLES:
                        (ansible/f'roles/{role}/tasks/main.yml').write_text(
                            '- ansible.builtin.debug:\n    msg: LIFECYCLE_EXECUTED\n  tags: [xray_reload, xray_recreate]\n')
                    inventory=directory/'inventory.yml'
                    inventory.write_text('all:\n  children:\n    xray_servers:\n      hosts:\n        localhost:\n          ansible_connection: local\n')
                    for tag in ['xray_reload','xray_recreate']:
                        result=subprocess.run(['ansible-playbook','-i',str(inventory),str(ansible/'site.yml'),
                            '-e','xray_deployment_mode='+selected,'-e','ansible_become=false',
                            '-e','xray_allow_runtime_switch=true','--tags',tag],capture_output=True,text=True,
                            env={**os.environ,'ANSIBLE_LOCAL_TEMP':'/tmp/ansible-local',
                                 'ANSIBLE_REMOTE_TEMP':'/tmp/ansible-remote'})
                        if selected==previous:
                            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                            self.assertIn('LIFECYCLE_EXECUTED',result.stdout)
                        else:
                            self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
                            self.assertIn('Lifecycle tags cannot switch runtimes',result.stdout)
                            self.assertNotIn('LIFECYCLE_EXECUTED',result.stdout)

    def test_all_six_transitions_require_opt_in_before_roles(self):
        for previous in ['native','docker','podman']:
            for selected in ['native','docker','podman']:
                if selected==previous:continue
                with self.subTest(previous=previous,selected=selected),tempfile.TemporaryDirectory() as tmp:
                    directory=pathlib.Path(tmp);ansible=directory/'ansible'
                    shutil.copytree(ROOT/'ansible',ansible)
                    scripts=directory/'scripts';scripts.mkdir()
                    (scripts/'runtime-ownership.py').write_text('print('+repr(json.dumps(state(previous)))+')\n')
                    for role in ROLES:
                        (ansible/f'roles/{role}/tasks/main.yml').write_text('- ansible.builtin.debug:\n    msg: ROLE_EXECUTED\n')
                    inventory=directory/'inventory.yml'
                    inventory.write_text('all:\n  children:\n    xray_servers:\n      hosts:\n        localhost:\n          ansible_connection: local\n')
                    env={**os.environ,'ANSIBLE_LOCAL_TEMP':'/tmp/ansible-local','ANSIBLE_REMOTE_TEMP':'/tmp/ansible-remote'}
                    cmd=['ansible-playbook','-i',str(inventory),str(ansible/'site.yml'),'-e','xray_deployment_mode='+selected,'-e','ansible_become=false']
                    result=subprocess.run(cmd,capture_output=True,text=True,env=env)
                    self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
                    self.assertIn('Opposite runtime exists',result.stdout)
                    self.assertNotIn('ROLE_EXECUTED',result.stdout)
                    result=subprocess.run(cmd+['-e','xray_allow_runtime_switch=true'],capture_output=True,text=True,env=env)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_all_six_activation_failures_restore_only_previous_runtime(self):
        for previous in ['native','docker','podman']:
            for selected in ['native','docker','podman']:
                if selected==previous:continue
                with self.subTest(previous=previous,selected=selected),tempfile.TemporaryDirectory() as tmp:
                    directory=pathlib.Path(tmp)
                    tasks=yaml.safe_load((ROOT/'ansible/tasks/restore-opposite.yml').read_text())
                    for task in tasks:
                        for action in ['ansible.builtin.command','ansible.builtin.systemd_service']:
                            if action in task:
                                del task[action];task['ansible.builtin.debug']={'msg':'EXECUTED '+task['name']}
                    play=[{'hosts':'all','gather_facts':False,'vars':{
                        'xray_deployment_mode':selected,'xray_existing':state(previous),
                        'xray_compose_up':{},'xray_podman_unit':{}},'tasks':tasks}]
                    result=self.run_play(directory,play)
                    self.assertNotEqual(result.returncode,0)
                    expected={'native':'native service','docker':'Docker container','podman':'Podman supervisor'}
                    for mode,description in expected.items():
                        text='EXECUTED Restore previous verified '+description
                        (self.assertIn if mode==previous else self.assertNotIn)(text,result.stdout)
                    self.assertIn('activation failed',result.stdout)


if __name__=='__main__':unittest.main()
