import contextlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from own.gpu_worker import run_provider, load_task, provider_environment, recover_stop, stop_by_id
from own.training_data import digest
from own.store import Problem


class Pending(Exception): pass


class FakeApp:
    app_id = 'ap-fictional'
    def __init__(self): self.stopped = False
    @contextlib.contextmanager
    def run(self): yield self
    def stop(self): self.stopped = True


class GpuWorkerTests(unittest.TestCase):
    def bridge(self, output=b'real-result', cancel=False, broken_stop=False):
        app = FakeApp()
        if broken_stop:
            app.stop = lambda: (_ for _ in ()).throw(ConnectionError('as-private-token'))
        spawned = []
        class Call:
            object_id = 'fc-fictional'
            def get(self, timeout=0):
                if cancel: raise Pending()
                return output
            def cancel(self, terminate_containers=False): pass
        class Function:
            def spawn(self, payload, queue): spawned.append(payload); return Call()
        class Queue:
            def get_many(self, count, block=False): return []
            @staticmethod
            @contextlib.contextmanager
            def ephemeral(): yield Queue()
        sdk = SimpleNamespace(Queue=Queue, exception=SimpleNamespace(TimeoutError=Pending))
        launcher = SimpleNamespace(build_app=lambda timeout: (app, Function()))
        payload = {'quote': {'timeout_seconds': 300}}
        events = []
        result = run_provider(payload, launcher, sdk, lambda: cancel and bool(spawned), lambda **data: events.append(data), poll_seconds=.001)
        return result, events, app, spawned

    def test_success_requires_real_output_and_provider_stop_ack(self):
        result, events, app, spawned = self.bridge()
        self.assertEqual(result['data'], b'real-result')
        self.assertTrue(result['provider_stop_confirmed'])
        self.assertTrue(app.stopped)
        self.assertEqual(len(spawned), 1)
        self.assertNotIn('as-private', str(events))

    def test_cancellation_never_succeeds_without_provider_ack(self):
        result, events, app, spawned = self.bridge(cancel=True)
        self.assertEqual(result['status'], 'cancelled')
        self.assertTrue(result['provider_stop_confirmed'])
        result, events, app, spawned = self.bridge(cancel=True, broken_stop=True)
        self.assertEqual(result['status'], 'interrupted')
        self.assertFalse(result['provider_stop_confirmed'])
        self.assertNotIn('as-private-token', str(result) + str(events))

    def test_missing_or_nonbytes_output_cannot_be_success(self):
        for value in (None, {'fake': True}, b''):
            result, events, app, spawned = self.bridge(output=value)
            self.assertEqual(result['status'], 'failed')
            self.assertNotIn('data', result)

    def test_credentials_only_enter_environment_and_inherited_profiles_are_removed(self):
        with patch.dict('os.environ', {'MODAL_TOKEN_ID': 'wrong', 'MODAL_PROFILE': 'other', 'MODAL_SERVER_URL': 'http://elsewhere'}):
            env = provider_environment(Path('private'), {'token_id': 'ak-test', 'token_secret': 'as-test'})
        self.assertEqual(env['MODAL_TOKEN_SECRET'], 'as-test')
        self.assertNotIn('MODAL_PROFILE', env)
        self.assertNotIn('MODAL_SERVER_URL', env)

    def test_worker_checks_consent_and_code_hashes_before_loading_trainer(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            payload = {'private': 'business data'}
            task = {'payload': payload, 'request_hash': digest(payload), 'source_hashes': {},
                    'approval': {'upload': True, 'free_only': True, 'out_of_pocket_usd': 0, 'available_credits': False}}
            (folder/'task.json').write_text(json.dumps(task))
            with self.assertRaises(Problem): load_task(folder)
            task['approval']['available_credits'] = True
            task['source_hashes'] = {'../escape.py': 'changed'}
            (folder/'task.json').write_text(json.dumps(task))
            with self.assertRaises(Problem): load_task(folder)

    def test_recovery_finds_only_its_unique_app_when_id_was_not_saved(self):
        rows=[{'App ID':'ap-otherapp','Description':'someone-elses-app'},
              {'App ID':'ap-matching','Description':'own-training-'+'a'*32}]
        with patch('own.gpu_worker.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(rows).encode())):
            with patch('own.gpu_worker.stop_by_id',return_value=True) as stop:
                acknowledged,app_id=recover_stop(None,'own-training-'+'a'*32)
        self.assertTrue(acknowledged)
        self.assertEqual(app_id,'ap-matching')
        stop.assert_called_once_with('ap-matching')
        with patch('own.gpu_worker.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=b'[]')):
            self.assertEqual(recover_stop(None,'own-training-'+'a'*32),(False,None))

    def test_recovery_requires_stop_rpc_or_confirmed_stopped_state(self):
        with patch('own.gpu_worker.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=b'')) as command:
            self.assertTrue(stop_by_id('ap-matching'))
            self.assertIn('--yes',command.call_args.args[0])
        with patch('own.gpu_worker.subprocess.run',side_effect=[SimpleNamespace(returncode=1),SimpleNamespace(returncode=0,stdout=b'{"lifecycle":{"state":"stopped"}}')]):
            self.assertTrue(stop_by_id('ap-matching'))
        with patch('own.gpu_worker.subprocess.run',side_effect=ConnectionError('unavailable')):
            self.assertFalse(stop_by_id('ap-matching'))

    def test_queue_failure_before_app_creation_is_terminal_and_cancel_before_start_uses_no_sdk(self):
        app=FakeApp()
        app.app_id=None
        app.run=lambda: self.fail('App creation must not be attempted')
        @contextlib.contextmanager
        def broken_queue():
            raise ConnectionError('Provider unavailable before app creation')
            yield
        sdk=SimpleNamespace(Queue=SimpleNamespace(ephemeral=broken_queue))
        launcher=SimpleNamespace(build_app=lambda timeout:(app,None))
        result=run_provider({'quote':{'timeout_seconds':300}},launcher,sdk,lambda:False,lambda **event:None,poll_seconds=.001)
        self.assertEqual(result['status'],'failed')
        self.assertTrue(result['provider_stop_confirmed'])
        launcher.build_app=lambda timeout:self.fail('Cancellation before launch must not construct or invoke anything')
        result=run_provider({'quote':{'timeout_seconds':300}},launcher,sdk,lambda:True,lambda **event:None)
        self.assertEqual(result['status'],'cancelled')
        self.assertTrue(result['provider_stop_confirmed'])

    def test_identity_helper_uses_public_workspace_name_not_an_unavailable_object_id(self):
        import io
        from own.gpu_identity import main
        workspace=SimpleNamespace(name='fictional-workspace')
        sdk=SimpleNamespace(Workspace=SimpleNamespace(from_context=lambda:SimpleNamespace(hydrate=lambda:workspace)))
        output=io.StringIO()
        with patch.dict('sys.modules',{'modal':sdk}), contextlib.redirect_stdout(output):
            self.assertEqual(main(),0)
        self.assertEqual(json.loads(output.getvalue()),{'workspace_name':'fictional-workspace'})

    def test_local_launcher_failure_before_sdk_invocation_does_not_leave_an_orphan(self):
        from own import gpu_worker
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/'train_on_gpu.py').write_text('def validate_request(*args):\n    raise ValueError("local invalid request")\n')
            with patch.object(gpu_worker,'load_task',return_value={'payload':{}}), patch('sys.argv',['worker','train',tmp]):
                gpu_worker.main()
            result=json.loads((folder/'progress.json').read_text())
            self.assertEqual(result['status'],'failed')
            self.assertTrue(result['provider_stop_confirmed'])


if __name__ == '__main__': unittest.main()
