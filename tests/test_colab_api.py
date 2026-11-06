import ast
import io
import json
import unittest
import zipfile

import test_gpu_api
from test_gpu_result import fixture


class ColabApiTests(unittest.TestCase):
    setUp = test_gpu_api.GpuApiTests.setUp
    tearDown = test_gpu_api.GpuApiTests.tearDown
    post = test_gpu_api.GpuApiTests.post

    def prepare(self):
        plan = self.client.get(self.route).json()['training_plan']
        return self.post(self.route + '/colab/runs', {
            'dataset_hash': plan['dataset_hash'], 'permission': True,
        })

    def result_path(self, run):
        return self.route + '/colab/runs/' + run['id']

    def import_result(self, run, data):
        return self.client.post(self.result_path(run) + '/result', content=data, headers=self.headers)

    def test_frozen_notebook_and_verified_import_survive_draft_changes(self):
        self.post(f'/api/workspaces/{self.ws}/sources', {'title': 'Private', 'content': 'LOCAL_REFERENCE_DOCUMENT'})
        run = self.prepare()
        self.assertEqual(run['status'], 'awaiting_result')
        self.assertEqual(run['id'], self.prepare()['id'])
        self.assertFalse(self.client.get(self.route).json()['gpu_busy'])
        notebook = self.client.get(self.result_path(run) + '/notebook')
        self.assertEqual(notebook.status_code, 200)
        self.assertIn('.ipynb', notebook.headers['content-disposition'])
        self.assertNotIn('LOCAL_EXPECTED_TARGET', notebook.text)
        self.assertNotIn('LOCAL_REFERENCE_DOCUMENT', notebook.text)
        self.assertIn('Question 0', notebook.text)
        self.assertIn('Another question', notebook.text)
        for cell in notebook.json()['cells']:
            if cell['cell_type'] == 'code':
                ast.parse(''.join(cell['source']))
        original = self.app.state.gpu_jobs.repo.get(self.ws, self.job, run['id'])
        archive, _ = fixture(payload=original['payload'])

        self.post(self.route + '/examples', {'kind': 'teach', 'input': 'New draft question', 'output': 'New answer'})
        self.assertEqual(notebook.content, self.client.get(self.result_path(run) + '/notebook').content)
        self.assertEqual(self.import_result(run, b'broken archive').status_code, 422)
        self.assertEqual(self.client.get(self.route).json()['colab_runs'][0]['status'], 'awaiting_result')
        imported = self.import_result(run, archive)
        self.assertEqual(imported.status_code, 200, imported.text)
        result = imported.json()
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['results'][0]['expected'], 'LOCAL_EXPECTED_TARGET')
        self.assertEqual(result['results'][0]['review'], 'pending')
        self.assertNotIn('payload', result)
        self.assertEqual(self.import_result(run, archive).status_code, 409)
        reviewed = self.post(self.result_path(run) + '/review', {
            'check_id': result['results'][0]['check_id'], 'review': 'pass',
        })
        self.assertEqual(reviewed['results'][0]['review'], 'pass')
        job = self.client.get(self.route).json()
        self.assertEqual(job['colab_runs'][0]['status'], 'complete')
        self.assertEqual(job['gpu_runs'], [])
        self.assertEqual(job['model'], '')
        exported = self.client.get(self.result_path(run) + '/export')
        self.assertEqual(exported.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(exported.content)) as files:
            self.assertIn('adapter/adapter_model.safetensors', files.namelist())
            self.assertEqual(json.loads(files.read('manifest.json'))['results'][0]['review'], 'pass')

    def test_requires_permission_current_examples_and_matching_run(self):
        path = self.route + '/colab/runs'
        old = self.client.get(self.route).json()['training_plan']['dataset_hash']
        self.assertEqual(self.client.post(path, json={'dataset_hash': old, 'permission': False}, headers=self.headers).status_code, 400)
        first = self.prepare()
        original = self.app.state.gpu_jobs.repo.get(self.ws, self.job, first['id'])
        result, _ = fixture(payload=original['payload'])
        self.post(self.route + '/examples', {'kind': 'teach', 'input': 'Fresh example', 'output': 'Fresh answer'})
        self.assertEqual(self.client.post(path, json={'dataset_hash': old, 'permission': True}, headers=self.headers).status_code, 409)
        second = self.prepare()
        self.assertEqual(self.import_result(second, result).status_code, 422)
        other = self.post(f'/api/workspaces/{self.ws}/jobs', {'name': 'Other job', 'goal': 'Other goal'})
        foreign = f'/api/workspaces/{self.ws}/jobs/{other["id"]}/colab/runs/{first["id"]}'
        self.assertEqual(self.client.get(foreign + '/notebook').status_code, 404)
        self.assertEqual(self.client.post(foreign + '/result', content=result, headers=self.headers).status_code, 404)
        self.assertEqual(self.import_result(second, b'x' * 1_300_000).status_code, 422)
        self.assertEqual(self.client.post(self.result_path(second) + '/result', content=b'ZIP').status_code, 403)
