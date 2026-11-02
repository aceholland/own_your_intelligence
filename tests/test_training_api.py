import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from own.api import create_app
from own.store import Problem


class TrainingApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.tmp.name))
        self.client = TestClient(self.app, base_url='http://127.0.0.1:8765')
        self.client.__enter__()
        self.headers = {'X-Own-Token': self.client.get('/api/bootstrap').json()['csrf_token']}
        self.ws = self.post('/api/workspaces', {'name': 'Test business'})['id']
        self.job = self.post(f'/api/workspaces/{self.ws}/jobs', {'name': 'Replies', 'goal': 'Answer briefly'})['id']
        self.route = f'/api/workspaces/{self.ws}/jobs/{self.job}'
        for n in range(3):
            self.post(self.route + '/examples', {'kind': 'teach', 'input': f'Question {n}', 'output': f'Answer {n}'})
        self.check = self.post(self.route + '/examples', {'kind': 'check', 'input': 'Unseen question', 'output': 'Expected'})

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def post(self, route, body):
        result = self.client.post(route, json=body, headers=self.headers)
        self.assertLess(result.status_code, 300, result.text)
        return result.json()

    def test_plan_and_runtime_are_honest_and_permission_is_required(self):
        plan = self.client.get(self.route + '/training-plan').json()
        self.assertTrue(plan['ready'])
        self.assertEqual(plan['provider_cost'], 0)
        runtime = self.client.get('/api/training/runtime').json()
        self.assertEqual(runtime['status'], 'not_installed')
        response = self.client.post(self.route + '/train', json={'dataset_hash': plan['dataset_hash'], 'permission': False}, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(self.route + '/trainings').json(), [])

    def test_example_editing_preserves_conflict_and_scope_checks(self):
        example = self.client.get(self.route).json()['examples'][0]
        response = self.client.patch(self.route + '/examples/' + example['id'],
            json={'input': 'Better request', 'output': 'Better response', 'expected': example}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        response = self.client.patch(self.route + '/examples/' + example['id'],
            json={'input': 'Stale request', 'output': 'Bad', 'expected': example}, headers=self.headers)
        self.assertEqual(response.status_code, 409)

    def test_foreign_training_id_cannot_be_reviewed_selected_or_exported(self):
        manager = self.app.state.training
        plan = manager.repo.prepare(self.ws, self.job)
        run = manager.repo.begin(self.ws, self.job, plan['dataset_hash'], True)
        other = self.post('/api/workspaces', {'name': 'Other'})['id']
        route = f'/api/workspaces/{other}/jobs/{self.job}/trainings/{run["id"]}'
        self.assertEqual(self.client.get(route + '/export').status_code, 404)
        self.assertEqual(self.client.post(route + '/select', json={}, headers=self.headers).status_code, 404)
        self.assertEqual(self.client.post(route + '/review', json={'check_id': self.check['id'], 'review': 'pass'}, headers=self.headers).status_code, 404)

    def test_trained_inference_routes_to_the_scoped_saved_adapter(self):
        manager = self.app.state.training
        plan = manager.repo.prepare(self.ws, self.job)
        run = manager.repo.begin(self.ws, self.job, plan['dataset_hash'], True)
        manager.repo.update(self.ws, self.job, run['id'], status='complete', results=[dict(
            check_id=self.check['id'], before='Before', after='After', review='pass', error=None)])
        manager.repo.select(self.ws, self.job, run['id'])
        with patch.object(manager, 'chat', return_value='A real transport result in this controlled test') as chat:
            result = self.post(self.route + '/try', {'input': 'Test the selected adapter', 'mode': 'draft'})
        self.assertEqual(result['model'], 'own:' + run['id'])
        self.assertEqual(chat.call_args.args[:3], (self.ws, self.job, run['id']))
        self.assertNotIn('Answer 0', str(chat.call_args.args[3]))

    def test_direct_model_edit_cannot_bypass_comparison_review(self):
        manager = self.app.state.training
        plan = manager.repo.prepare(self.ws, self.job)
        run = manager.repo.begin(self.ws, self.job, plan['dataset_hash'], True)
        job = self.client.get(self.route).json()
        response = self.client.patch(self.route, json={'revision': job['revision'],
            'changes': {'model': 'own:' + run['id']}}, headers=self.headers)
        self.assertEqual(response.status_code, 400)

    def test_setup_and_training_routes_keep_same_origin_boundary(self):
        response = self.client.post('/api/training/setup', json={})
        self.assertEqual(response.status_code, 403)
        plan = self.client.get(self.route + '/training-plan').json()
        with patch.object(self.app.state.training, 'start', return_value={'id': 'controlled-test'}) as start:
            response = self.client.post(self.route + '/train', json={'dataset_hash': plan['dataset_hash'], 'permission': True}, headers=self.headers)
        self.assertEqual(response.status_code, 202)
        start.assert_called_once_with(self.ws, self.job, plan['dataset_hash'], True)


if __name__ == '__main__':
    unittest.main()
