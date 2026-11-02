import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from own.store import Store, Problem
from own.gpu_setup import GpuSetup
from own.gpu_runtime import GpuJobManager
from own.training_setup import write_json
from tests.test_gpu_result import fixture


class GpuRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.store=Store(self.root/'db.sqlite3')
        self.setup=GpuSetup(self.store,self.root)
        self.manager=GpuJobManager(self.store,self.setup)
        self.ws=self.store.create_workspace('Fictional business')['id']
        self.job=self.store.create_job(self.ws,'Reply','Brief replies')['id']
        for n in range(3):self.store.add_example(self.ws,self.job,'teach',f'Teach {n}',f'Answer {n}')
        self.store.add_example(self.ws,self.job,'check','A different question','KEEP_TARGET_LOCAL')
        self.args=dict(dataset_hash=self.setup.plan(self.ws,self.job)['dataset_hash'],upload=True,free_only=True,zero_limit=True,credits=True)

    def tearDown(self):
        self.manager.close();self.setup.close();self.store.close();self.tmp.cleanup()

    def run_record(self):
        run=self.manager.repo.begin(self.ws,self.job,**self.args)
        self.manager.folder(run).mkdir(parents=True)
        return run

    def test_setup_and_connection_are_required_before_record_or_process(self):
        with patch.object(self.manager,'_launch') as launch:
            with self.assertRaises(Problem):self.manager.start(self.ws,self.job,**self.args)
            launch.assert_not_called()
        self.assertEqual(self.manager.repo.list(self.ws,self.job),[])

    def test_only_verified_result_gets_imported_and_expected_answers_are_joined_locally(self):
        run=self.run_record()
        folder=self.manager.folder(run)
        data,_=fixture(payload=run['payload'])
        (folder/'result.zip').write_bytes(data)
        write_json(folder/'progress.json',{'status':'returned','provider_stop_confirmed':True})
        result=self.manager.reconcile(run,0)
        self.assertEqual(result['status'],'complete')
        self.assertTrue(result['download_available'])
        self.assertEqual(result['results'][0]['expected'],'KEEP_TARGET_LOCAL')
        self.assertEqual(result['results'][0]['review'],'pending')
        exported=self.manager.export(self.ws,self.job,run['id'])
        with zipfile.ZipFile(io.BytesIO(exported)) as archive:
            self.assertIn('adapter/adapter_model.safetensors',archive.namelist())
            self.assertIn('run_model.py',archive.namelist())
            self.assertNotIn('KEEP_TARGET_LOCAL',archive.read('request.json').decode())
        (folder/'result.zip').write_bytes(b'changed')
        with self.assertRaises(Problem):self.manager.export(self.ws,self.job,run['id'])

    def test_nonzero_exit_fake_result_and_unconfirmed_stop_cannot_be_complete(self):
        for code,progress in ((1,{'status':'returned','provider_stop_confirmed':True}),
                              (0,{'status':'returned','provider_stop_confirmed':False}),
                              (0,{'status':'cancelled','provider_stop_confirmed':False})):
            run=self.run_record()
            folder=self.manager.folder(run)
            data,_=fixture(payload=run['payload'])
            (folder/'result.zip').write_bytes(data)
            write_json(folder/'progress.json',progress)
            result=self.manager.reconcile(run,code)
            self.assertNotEqual(result['status'],'complete')
            self.assertFalse(result['download_available'])
            self.manager.repo.update(self.ws,self.job,run['id'],status='failed')

    def test_stop_ack_is_required_and_stop_during_return_does_not_import(self):
        run=self.run_record()
        folder=self.manager.folder(run)
        self.manager.repo.update(self.ws,self.job,run['id'],status='stopping')
        data,_=fixture(payload=run['payload'])
        (folder/'result.zip').write_bytes(data)
        write_json(folder/'progress.json',{'status':'returned','provider_stop_confirmed':True})
        result=self.manager.reconcile(run,0)
        self.assertEqual(result['status'],'cancelled')
        self.assertFalse(result['download_available'])


if __name__=='__main__':unittest.main()
