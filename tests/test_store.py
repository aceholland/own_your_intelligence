import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from own.store import Store, Problem
from own.retrieval import build_messages


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'own.sqlite3'
        self.store = Store(self.path)
        self.ws = self.store.create_workspace('North Studio')['id']
        self.job = self.store.create_job(self.ws, 'Reply to customers', 'Answer delivery questions')['id']
        self.store.update_job(self.ws, self.job, {'model': 'local-small'}, 1)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_workspace_records_survive_restart_and_remain_separate(self):
        other = self.store.create_workspace('Other business')['id']
        self.store.add_source(other, 'Private', 'Secret bluebird account details')
        self.store.add_source(self.ws, 'Delivery', 'Orders arrive in five working days.')
        self.store.close()
        self.store = Store(self.path)
        state = self.store.workspace(self.ws)
        self.assertEqual(state['jobs'][0]['name'], 'Reply to customers')
        self.assertEqual([s['title'] for s in state['sources']], ['Delivery'])
        with self.assertRaises(Problem):
            self.store.job(other, self.job)

    def test_checks_never_enter_prompt_or_training_file(self):
        self.store.add_example(self.ws, self.job, 'teach', 'When will it arrive?', 'In five days.')
        self.store.add_example(self.ws, self.job, 'check', 'What is the return window?', 'HIDDEN_CHECK_ANSWER')
        snapshot = self.store.snapshot(self.ws, self.job)
        prompt = json.dumps(build_messages(snapshot, 'When does delivery arrive?')[0])
        self.assertIn('In five days.', prompt)
        self.assertNotIn('HIDDEN_CHECK_ANSWER', prompt)
        exported = self.store.training_jsonl(self.ws, self.job)
        self.assertNotIn('HIDDEN_CHECK_ANSWER', exported)
        self.assertEqual(len(exported.strip().splitlines()), 1)

    def test_duplicate_input_cannot_cross_teaching_and_check_split(self):
        self.store.add_example(self.ws, self.job, 'teach', '  Delivery TIME? ', 'Five days')
        with self.assertRaises(Problem):
            self.store.add_example(self.ws, self.job, 'check', 'delivery time?', 'Five days')

    def test_approval_requires_reviewed_current_checks_and_preserves_versions(self):
        self.store.add_source(self.ws, 'Delivery policy', 'Delivery takes five days.')
        check = self.store.add_example(self.ws, self.job, 'check', 'When?', 'Five days')
        snap = self.store.snapshot(self.ws, self.job)
        with self.assertRaises(Problem):
            self.store.approve(self.ws, self.job)
        evaluation = self.store.record_evaluation(self.ws, self.job, snap, [
            {'check_id': check['id'], 'input': 'When?', 'expected': 'Five days', 'output': 'Five days', 'error': None}
        ])
        with self.assertRaises(Problem):
            self.store.approve(self.ws, self.job)
        self.store.review_check(self.ws, self.job, evaluation['id'], check['id'], 'pass')
        version = self.store.approve(self.ws, self.job)
        self.assertEqual(version['number'], 1)
        self.store.add_source(self.ws, 'New policy', 'Delivery now takes seven days.')
        with self.assertRaises(Problem):
            self.store.approve(self.ws, self.job)
        live, version_id = self.store.resolve_snapshot(self.ws, self.job, 'live')
        self.assertEqual(version_id, version['id'])
        self.assertEqual(len(live['sources']), 1)

    def test_failed_or_incomplete_checks_cannot_approve(self):
        check = self.store.add_example(self.ws, self.job, 'check', 'When?', 'Five days')
        snap = self.store.snapshot(self.ws, self.job)
        evaluation = self.store.record_evaluation(self.ws, self.job, snap, [
            {'check_id': check['id'], 'input': 'When?', 'expected': 'Five days', 'output': '', 'error': 'Model unavailable'}
        ])
        with self.assertRaises(Problem):
            self.store.review_check(self.ws, self.job, evaluation['id'], check['id'], 'pass')
        with self.assertRaises(Problem):
            self.store.approve(self.ws, self.job)

    def test_correction_is_saved_without_mutating_published_model(self):
        snap = self.store.snapshot(self.ws, self.job)
        run = self.store.record_run(self.ws, self.job, snap, 'When?', 'Tomorrow', [], 35, None)
        self.store.correct_run(self.ws, self.job, run['id'], 'Five working days')
        updated = self.store.job(self.ws, self.job)
        self.assertEqual(updated['examples'][0]['output'], 'Five working days')
        self.assertEqual(updated['runs'][0]['corrected_output'], 'Five working days')
        self.assertEqual(snap['examples'], [])
        self.assertIsNone(updated['active_version_id'])

    def test_stale_edits_and_long_inputs_fail_without_overwriting(self):
        with self.assertRaises(Problem):
            self.store.update_job(self.ws, self.job, {'instructions': 'outdated'}, 1)
        with self.assertRaises(Problem):
            self.store.add_source(self.ws, 'Too large', 'x' * 200001)
        self.assertEqual(self.store.job(self.ws, self.job)['instructions'], '')

    def test_archive_contains_only_selected_workspace_and_honest_manifest(self):
        other = self.store.create_workspace('Other business')['id']
        self.store.add_source(other, 'Secret', 'NEVER_EXPORT_THIS')
        self.store.add_example(self.ws, self.job, 'teach', 'Hello', 'Welcome')
        data = self.store.export_workspace(self.ws)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            raw = archive.read('workspace.json').decode()
            self.assertNotIn('NEVER_EXPORT_THIS', raw)
            manifest = json.loads(archive.read('manifest.json'))
            self.assertFalse(manifest['model_weights_included'])
            self.assertIn('README.txt', archive.namelist())
            self.assertEqual(len(archive.read(f'training/{self.job}.jsonl').splitlines()), 1)

    def test_eleventh_check_is_rejected_without_stranding_the_job(self):
        for index in range(10):
            self.store.add_example(self.ws, self.job, 'check', f'New case {index}', 'A good answer')
        with self.assertRaises(Problem):
            self.store.add_example(self.ws, self.job, 'check', 'An eleventh case', 'A good answer')
        self.assertEqual(len(self.store.snapshot(self.ws, self.job)['checks']), 10)
        evaluation = self.store.begin_evaluation(self.ws, self.job, self.store.snapshot(self.ws, self.job))
        self.assertEqual(len(evaluation['results']), 10)

    def test_later_correction_refines_existing_teaching_example(self):
        snapshot = self.store.snapshot(self.ws, self.job)
        first = self.store.record_run(self.ws, self.job, snapshot, 'Delivery time?', 'Tomorrow', [], 1, None)
        self.store.correct_run(self.ws, self.job, first['id'], 'Five days')
        later = self.store.record_run(self.ws, self.job, self.store.snapshot(self.ws, self.job), 'Delivery time?', 'Five days', [], 1, None)
        self.store.correct_run(self.ws, self.job, later['id'], 'Five working days, excluding holidays')
        examples = self.store.snapshot(self.ws, self.job)['examples']
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]['output'], 'Five working days, excluding holidays')


if __name__ == '__main__':
    unittest.main()
