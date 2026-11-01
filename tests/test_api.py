import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from own.api import create_app
from own.store import Problem


class EngineFixture:
    def __init__(self):
        self.available = True
        self.failure = False

    def status(self):
        return {'connected': self.available, 'models': [{'name': 'local-small', 'size': 1000}], 'message': 'Ready'}

    def chat(self, model, messages):
        if self.failure:
            raise Problem('The local model stopped. Open Ollama and try again.', 503)
        return 'Delivery takes five working days.'


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = EngineFixture()
        self.app = create_app(Path(self.tmp.name), self.engine)
        self.client = TestClient(self.app, base_url='http://127.0.0.1:8765')
        self.client.__enter__()
        self.token = self.client.get('/api/bootstrap').json()['csrf_token']
        self.headers = {'X-Own-Token': self.token, 'Origin': 'http://127.0.0.1:8765'}
        self.ws = self.post('/api/workspaces', {'name': 'Studio'})['id']
        self.base = f'/api/workspaces/{self.ws}'
        self.job = self.post(f'{self.base}/jobs', {'name': 'Delivery helper', 'goal': 'Answer questions'})['id']
        self.route = f'{self.base}/jobs/{self.job}'
        self.client.patch(self.route, json={'revision': 1, 'changes': {'model': 'local-small'}}, headers=self.headers)

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def post(self, route, data):
        response = self.client.post(route, json=data, headers=self.headers)
        self.assertLess(response.status_code, 300, response.text)
        return response.json()

    def test_cross_site_and_missing_token_cannot_mutate(self):
        self.assertEqual(self.client.post('/api/workspaces', json={'name': 'Bad'}).status_code, 403)
        headers = dict(self.headers, Origin='https://untrusted.example')
        self.assertEqual(self.client.post('/api/workspaces', json={'name': 'Bad'}, headers=headers).status_code, 403)
        self.assertEqual(self.client.get('/api/bootstrap', headers={'Host': 'untrusted.example'}).status_code, 403)

    def test_real_pipeline_records_answer_and_workspace_references(self):
        self.post(f'{self.base}/sources', {'title': 'Shipping', 'content': 'Delivery takes five working days.'})
        other = self.post('/api/workspaces', {'name': 'Other'})['id']
        self.post(f'/api/workspaces/{other}/sources', {'title': 'Secret', 'content': 'Delivery secret information'})
        answer = self.post(f'{self.route}/try', {'input': 'How long does delivery take?', 'mode': 'draft'})
        self.assertEqual(answer['output'], 'Delivery takes five working days.')
        self.assertEqual(answer['references'][0]['title'], 'Shipping')
        state = self.client.get(self.route).json()
        self.assertEqual(state['runs'][0]['id'], answer['id'])

    def test_model_failure_does_not_invent_or_record_an_answer(self):
        self.engine.failure = True
        response = self.client.post(f'{self.route}/try', json={'input': 'Hello', 'mode': 'draft'}, headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.get(self.route).json()['runs'], [])

    def test_upload_rejects_binary_oversize_and_unsupported_format(self):
        for name, content in [('file.pdf', b'%PDF'), ('file.txt', b'\xff\x00'), ('big.txt', b'x' * 1048577)]:
            response = self.client.post(f'{self.base}/upload', files={'file': (name, content)}, headers=self.headers)
            self.assertIn(response.status_code, (400, 413), response.text)
        response = self.client.post(f'{self.base}/upload', files={'file': ('notes.md', b'# Shipping\nFive days.')}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['title'], 'notes.md')

    def test_training_route_never_pretends_to_train(self):
        response = self.client.post(f'{self.route}/train', json={}, headers=self.headers)
        self.assertEqual(response.status_code, 404)
        bootstrap = self.client.get('/api/bootstrap').json()
        self.assertFalse(bootstrap['capabilities']['weight_training'])

    def test_malformed_request_reports_actionable_error(self):
        response = self.client.post('/api/workspaces', json={'name': ''}, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertIsInstance(response.json()['error'], str)

    def test_check_review_and_version_approval_run_end_to_end(self):
        check = self.post(f'{self.route}/examples', {'kind': 'check', 'input': 'How long is delivery?', 'output': 'Five working days'})
        evaluation = self.post(f'{self.route}/evaluations', {})
        saved = self.client.get(self.route).json()['evaluations'][0]
        self.assertEqual(saved['status'], 'complete')
        self.assertEqual(saved['results'][0]['output'], 'Delivery takes five working days.')
        self.assertEqual(self.client.post(f'{self.route}/approve', json={}, headers=self.headers).status_code, 400)
        self.post(f'{self.route}/evaluations/{evaluation["id"]}/review', {'check_id': check['id'], 'review': 'pass'})
        version = self.post(f'{self.route}/approve', {})
        answer = self.post(f'{self.route}/try', {'input': 'Delivery?', 'mode': 'live'})
        self.assertEqual(answer['version_id'], version['id'])
        self.post(f'{self.base}/sources', {'title': 'Changed policy', 'content': 'New delivery policy'})
        self.assertEqual(self.client.post(f'{self.route}/approve', json={}, headers=self.headers).status_code, 400)

    def test_failed_checks_remain_failed_and_can_be_retried(self):
        self.post(f'{self.route}/examples', {'kind': 'check', 'input': 'Delivery?', 'output': 'Five days'})
        self.engine.failure = True
        failed = self.post(f'{self.route}/evaluations', {})
        state = self.client.get(self.route).json()
        row = state['evaluations'][0]['results'][0]
        self.assertTrue(row['error'])
        response = self.client.post(f'{self.route}/evaluations/{failed["id"]}/review', json={'check_id': row['check_id'], 'review': 'pass'}, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.engine.failure = False
        self.post(f'{self.route}/evaluations', {})
        self.assertIsNone(self.client.get(self.route).json()['evaluations'][0]['results'][0]['error'])


if __name__ == '__main__':
    unittest.main()
