import tempfile
import unittest
from pathlib import Path

from own.store import Store, Problem
from own.training_store import TrainingRepository


class TrainingStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'test.sqlite3')
        self.repo = TrainingRepository(self.store)
        self.ws = self.store.create_workspace('First business')['id']
        self.job = self.store.create_job(self.ws, 'Replies', 'Answer politely')['id']
        for n in range(3):
            self.store.add_example(self.ws, self.job, 'teach', f'Teaching question {n}', f'Answer {n}')
        self.check = self.store.add_example(self.ws, self.job, 'check', 'New question', 'HIDDEN_CHECK_TARGET')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def begin(self):
        return self.repo.begin(self.ws, self.job, self.repo.prepare(self.ws, self.job)['dataset_hash'], True)

    def complete(self, run):
        return self.repo.update(self.ws, self.job, run['id'], status='complete',
            results=[dict(check_id=self.check['id'], input='New question', expected='HIDDEN_CHECK_TARGET',
                          before='Old answer', after='A new answer', review='pending', error=None)])

    def test_permission_and_stale_confirmation_block_training(self):
        plan = self.repo.prepare(self.ws, self.job)
        with self.assertRaises(Problem):
            self.repo.begin(self.ws, self.job, plan['dataset_hash'], False)
        self.store.add_example(self.ws, self.job, 'teach', 'Another request', 'Another answer')
        with self.assertRaises(Problem):
            self.repo.begin(self.ws, self.job, plan['dataset_hash'], True)
        self.assertEqual(self.repo.list(self.ws, self.job), [])

    def test_dataset_is_frozen_and_checks_do_not_enter_training_messages(self):
        run = self.begin()
        self.assertNotIn('HIDDEN_CHECK_TARGET', str(run['dataset']['training_rows']))
        self.assertEqual(len(run['dataset']['training_rows']), 3)
        self.assertTrue(run['permission']['confirmed'])
        example = self.store.job(self.ws, self.job)['examples'][0]
        self.store.edit_example(self.ws, self.job, example['id'], 'Changed question', 'Changed answer', example)
        self.assertEqual(self.repo.get(self.ws, self.job, run['id'])['dataset']['examples'][0]['output'], 'Answer 0')

    def test_edit_conflict_and_cross_split_duplicate_cannot_change_examples(self):
        example = self.store.job(self.ws, self.job)['examples'][0]
        with self.assertRaises(Problem):
            self.store.edit_example(self.ws, self.job, example['id'], 'New question', 'Bad overlap', example)
        self.store.edit_example(self.ws, self.job, example['id'], 'New teaching input', 'Better', example)
        with self.assertRaises(Problem):
            self.store.edit_example(self.ws, self.job, example['id'], 'Lost update', 'Old', example)

    def test_training_is_scoped_and_selection_requires_all_reviewed_current_checks(self):
        run = self.begin()
        other = self.store.create_workspace('Other business')['id']
        with self.assertRaises(Problem):
            self.repo.get(other, self.job, run['id'])
        with self.assertRaises(Problem):
            self.repo.select(self.ws, self.job, run['id'])
        self.complete(run)
        with self.assertRaises(Problem):
            self.repo.select(self.ws, self.job, run['id'])
        self.repo.review(self.ws, self.job, run['id'], self.check['id'], 'pass')
        self.repo.select(self.ws, self.job, run['id'])
        self.assertEqual(self.store.job(self.ws, self.job)['model'], 'own:' + run['id'])
        self.store.add_source(self.ws, 'New facts', 'Changed the business context')
        with self.assertRaises(Problem):
            self.repo.select(self.ws, self.job, run['id'])

    def test_partial_or_failed_comparison_cannot_be_selected(self):
        run = self.complete(self.begin())
        self.repo.update(self.ws, self.job, run['id'], results=[])
        with self.assertRaises(Problem):
            self.repo.select(self.ws, self.job, run['id'])
        self.repo.update(self.ws, self.job, run['id'], status='failed')
        with self.assertRaises(Problem):
            self.repo.review(self.ws, self.job, run['id'], self.check['id'], 'pass')

    def test_failed_baseline_is_an_observed_outcome_and_candidate_still_requires_review(self):
        run = self.begin()
        self.repo.update(self.ws, self.job, run['id'], status='complete', results=[dict(
            check_id=self.check['id'], before='', before_error='No complete baseline answer',
            after='A complete trained answer', review='pending', error=None)])
        with self.assertRaises(Problem):
            self.repo.select(self.ws, self.job, run['id'])
        self.repo.review(self.ws, self.job, run['id'], self.check['id'], 'pass')
        self.repo.select(self.ws, self.job, run['id'])
        self.assertEqual(self.store.job(self.ws, self.job)['model'], 'own:' + run['id'])

    def test_too_little_data_has_clear_preparation_blockers(self):
        job = self.store.create_job(self.ws, 'New', 'New job')['id']
        plan = self.repo.prepare(self.ws, job)
        self.assertFalse(plan['ready'])
        self.assertGreaterEqual(len(plan['blockers']), 2)
        with self.assertRaises(Problem):
            self.repo.begin(self.ws, job, plan['dataset_hash'], True)


if __name__ == '__main__':
    unittest.main()
