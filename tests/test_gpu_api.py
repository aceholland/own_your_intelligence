import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from own.api import create_app


class GpuApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=create_app(Path(self.tmp.name))
        self.client=TestClient(self.app,base_url='http://127.0.0.1:8765')
        self.client.__enter__()
        self.headers={'X-Own-Token':self.client.get('/api/bootstrap').json()['csrf_token']}
        self.ws=self.post('/api/workspaces',{'name':'GPU test business'})['id']
        self.job=self.post(f'/api/workspaces/{self.ws}/jobs',{'name':'Reply','goal':'Be concise'})['id']
        self.route=f'/api/workspaces/{self.ws}/jobs/{self.job}'
        for n in range(3):
            self.post(self.route+'/examples',{'kind':'teach','input':f'Question {n}','output':f'Answer {n}'})
        self.post(self.route+'/examples',{'kind':'check','input':'Another question','output':'LOCAL_EXPECTED_TARGET'})

    def tearDown(self):
        self.client.__exit__(None,None,None)
        self.tmp.cleanup()

    def post(self,path,body):
        response=self.client.post(path,json=body,headers=self.headers)
        self.assertLess(response.status_code,300,response.text)
        return response.json()

    def test_training_capability_is_available_but_an_unconnected_account_is_not_ready(self):
        caps=self.client.get('/api/bootstrap').json()['capabilities']
        self.assertTrue(caps['gpu_setup'])
        self.assertTrue(caps['cloud_training'])
        status=self.client.get('/api/gpu').json()
        self.assertFalse(status['connected'])
        self.assertFalse(status['remote_training_enabled'])
        self.assertEqual(self.client.post('/api/gpu/setup',json={}).status_code,403)
        self.assertEqual(self.client.post(self.route+'/gpu/launch',json={},headers=self.headers).status_code,404)

    def run_body(self,**changes):
        body={'dataset_hash':self.client.get(self.route+'/gpu/plan').json()['dataset_hash'],
              'upload':True,'free_only':True,'zero_limit':True,'credits':True}
        body.update(changes)
        return body

    def test_free_only_fields_are_strict_and_no_account_cannot_launch(self):
        path=self.route+'/gpu/runs'
        self.assertEqual(self.client.post(path,json=self.run_body()).status_code,403)
        for value in (False,'true',None):
            response=self.client.post(path,json=self.run_body(credits=value),headers=self.headers)
            self.assertGreaterEqual(response.status_code,400)
        self.assertEqual(self.client.get(path).json(),[])

    def test_scoped_job_progress_cannot_expose_frozen_data_or_secret(self):
        manager=self.app.state.gpu_jobs
        run=manager.repo.begin(self.ws,self.job,**self.run_body())
        self.assertTrue(self.client.get(self.route).json()['gpu_busy'])
        response=self.client.get(self.route+'/gpu/runs/'+run['id'])
        self.assertEqual(response.status_code,200)
        self.assertNotIn('LOCAL_EXPECTED_TARGET',response.text)
        self.assertNotIn('source_files',response.json())
        other=self.post('/api/workspaces',{'name':'Other business'})['id']
        foreign=f'/api/workspaces/{other}/jobs/{self.job}/gpu/runs/{run["id"]}'
        self.assertEqual(self.client.get(foreign).status_code,404)
        for suffix in ('/cancel','/review'):
            body={'check_id':'anything','review':'pass'} if suffix=='/review' else {}
            self.assertEqual(self.client.post(foreign+suffix,json=body,headers=self.headers).status_code,404)
        self.assertEqual(self.client.get(foreign+'/export').status_code,404)
        self.assertEqual(self.client.get(self.route+'/gpu/runs/'+run['id']+'/export').status_code,409)
        self.assertEqual(self.client.post('/api/gpu/disconnect',json={},headers=self.headers).status_code,409)
        with patch.object(self.app.state.gpu,'connect') as connect:
            response=self.client.post('/api/gpu/connection',json={'token_id':'ak-test','token_secret':'as-test'},headers=self.headers)
            self.assertEqual(response.status_code,409)
            connect.assert_not_called()
        manager.repo.update(self.ws,self.job,run['id'],status='failed')

    def test_new_job_uses_the_real_manager_and_all_approval_fields(self):
        manager=self.app.state.gpu_jobs
        with patch.object(manager,'start',return_value={'id':'test-run','status':'queued'}) as start:
            response=self.client.post(self.route+'/gpu/runs',json=self.run_body(),headers=self.headers)
        self.assertEqual(response.status_code,202)
        start.assert_called_once_with(self.ws,self.job,**self.run_body())

    def test_scoped_recovery_connection_reaches_stop_only_for_interrupted_jobs(self):
        manager=self.app.state.gpu_jobs
        run=manager.repo.begin(self.ws,self.job,**self.run_body())
        path=self.route+'/gpu/runs/'+run['id']+'/reconnect'
        pair={'token_id':'ak-replacement','token_secret':'as-replacement'}
        self.assertEqual(self.client.post(path,json=pair).status_code,403)
        self.assertEqual(self.client.post(path,json=pair,headers=self.headers).status_code,409)
        manager.repo.update(self.ws,self.job,run['id'],status='interrupted',provider_workspace_name='original-workspace')
        with patch.object(manager,'reconnect_and_stop',return_value={'status':'stopping'}) as reconnect:
            response=self.client.post(path,json=pair,headers=self.headers)
        self.assertEqual(response.status_code,200)
        reconnect.assert_called_once_with(self.ws,self.job,run['id'],**pair)
        manager.repo.update(self.ws,self.job,run['id'],status='failed')

    def test_slow_provider_connection_does_not_block_local_store_or_training_heartbeat(self):
        available=[]
        def connect(*args):
            def another_local_operation():
                acquired=self.app.state.store.lock.acquire(timeout=.2)
                available.append(acquired)
                if acquired:self.app.state.store.lock.release()
            thread=threading.Thread(target=another_local_operation)
            thread.start();thread.join(timeout=1)
            return {'connected':True}
        with patch.object(self.app.state.gpu,'connect',side_effect=connect):
            self.post('/api/gpu/connection',{'token_id':'ak-fictional','token_secret':'as-fictional'})
        self.assertEqual(available,[True])

    def test_preparation_and_download_need_no_account_and_do_not_run_compute(self):
        plan=self.client.get(self.route+'/gpu/plan').json()
        package=self.post(self.route+'/gpu/packages',{'dataset_hash':plan['dataset_hash'],'budget_usd':2.0,'permission':True})
        self.assertEqual(package['status'],'prepared')
        self.assertFalse(package['training_performed'])
        result=self.client.get(self.route+'/gpu/packages/'+package['id']+'/export')
        self.assertEqual(result.status_code,200)
        with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
            self.assertNotIn('LOCAL_EXPECTED_TARGET',archive.read('request.json').decode())
            self.assertFalse(json.loads(archive.read('manifest.json'))['upload_performed'])
        self.assertEqual(self.client.get(self.route).json()['trainings'],[])

    def test_foreign_package_and_missing_consent_are_rejected(self):
        plan=self.client.get(self.route+'/gpu/plan').json()
        result=self.client.post(self.route+'/gpu/packages',json={'dataset_hash':plan['dataset_hash'],'budget_usd':2.0,'permission':False},headers=self.headers)
        self.assertEqual(result.status_code,400)
        package=self.post(self.route+'/gpu/packages',{'dataset_hash':plan['dataset_hash'],'budget_usd':2.0,'permission':True})
        other=self.post('/api/workspaces',{'name':'Other'})['id']
        response=self.client.get(f'/api/workspaces/{other}/jobs/{self.job}/gpu/packages/{package["id"]}/export')
        self.assertEqual(response.status_code,404)

    def test_credentials_are_never_in_status_or_workspace_exports(self):
        value={'token_id':'ak-fictional','token_secret':'as-fictional-secret-value'}
        self.app.state.gpu.vault.save(value)
        self.assertNotIn(value['token_secret'],self.client.get('/api/gpu').text)
        archive=self.client.get(f'/api/workspaces/{self.ws}/export').content
        self.assertNotIn(value['token_secret'].encode(),archive)
        self.post('/api/gpu/disconnect',{})
        self.assertFalse(self.client.get('/api/gpu').json()['connected'])


if __name__=='__main__':
    unittest.main()
