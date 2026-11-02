import io
import json
import tempfile
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

    def test_setup_capability_never_claims_remote_training_enabled(self):
        caps=self.client.get('/api/bootstrap').json()['capabilities']
        self.assertTrue(caps['gpu_setup'])
        self.assertFalse(caps['cloud_training'])
        status=self.client.get('/api/gpu').json()
        self.assertFalse(status['connected'])
        self.assertFalse(status['remote_training_enabled'])
        self.assertEqual(self.client.post('/api/gpu/setup',json={}).status_code,403)
        self.assertEqual(self.client.post(self.route+'/gpu/launch',json={},headers=self.headers).status_code,404)

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
