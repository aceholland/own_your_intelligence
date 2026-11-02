import io
import hashlib
import json
import os
import tempfile
import threading
import unittest
import zipfile
from contextlib import nullcontext
from unittest.mock import patch
from pathlib import Path

from own.store import Store, Problem
from own.training_data import encode_example, BASE
from own.training_runtime import TrainingManager, verify_artifact
from own.training_setup import runtime_python


class TokenizerFixture:
    def apply_chat_template(self, messages, tokenize=True, add_generation_prompt=False):
        return [1, 2, 3] if len(messages) == 2 else [1, 2, 3, 4, 5]


class TrainingRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / 'test.sqlite3')
        self.manager = TrainingManager(self.store, self.root, threading.Lock())
        self.ws = self.store.create_workspace('Business')['id']
        self.job = self.store.create_job(self.ws, 'Task', 'Give an answer')['id']
        for n in range(3):
            self.store.add_example(self.ws, self.job, 'teach', f'Question {n}', f'Answer {n}')
        self.check = self.store.add_example(self.ws, self.job, 'check', 'Held out', 'Good answer')

    def tearDown(self):
        self.manager.close()
        self.store.close()
        self.tmp.cleanup()

    def run_record(self):
        plan = self.manager.repo.prepare(self.ws, self.job)
        return self.manager.repo.begin(self.ws, self.job, plan['dataset_hash'], True)

    def test_assistant_only_labels_and_no_silent_truncation(self):
        messages = [{'role': 'system', 'content': 'Goal'}, {'role': 'user', 'content': 'Ask'}, {'role': 'assistant', 'content': 'Answer'}]
        row = encode_example(TokenizerFixture(), messages, 5)
        self.assertEqual(row['labels'], [-100, -100, -100, 4, 5])
        with self.assertRaisesRegex(ValueError, 'Shorten'):
            encode_example(TokenizerFixture(), messages, 4)

    @unittest.skipUnless(os.name == 'nt', 'Windows extended-length namespace')
    def test_windows_runtime_uses_extended_length_paths_without_system_changes(self):
        self.assertTrue(str(runtime_python(self.root)).startswith('\\\\?\\'))

    def test_missing_runtime_does_not_start_or_record_training(self):
        plan = self.manager.repo.prepare(self.ws, self.job)
        with self.assertRaisesRegex(Problem, 'Set up'):
            self.manager.start(self.ws, self.job, plan['dataset_hash'], True)
        self.assertEqual(self.manager.repo.list(self.ws, self.job), [])

    def test_artifact_substitution_is_rejected(self):
        path = self.root / 'adapter'
        path.mkdir()
        (path / 'adapter_model.safetensors').write_bytes(b'example-weights')
        (path / 'adapter_config.json').write_text('{}')
        with self.assertRaises(Problem):
            verify_artifact(path, {'adapter_model.safetensors': 'wrong', 'adapter_config.json': 'wrong'})

    def test_saved_bpe_tokenizer_files_are_valid_model_artifacts(self):
        path = self.root / 'adapter'
        path.mkdir()
        hashes = {}
        for name in ['adapter_model.safetensors', 'adapter_config.json', 'vocab.json', 'merges.txt']:
            (path / name).write_bytes(b'controlled fixture')
            hashes[name] = hashlib.sha256(b'controlled fixture').hexdigest()
        verify_artifact(path, hashes)

    def test_base_identity_contains_the_pinned_weight_hash_for_portable_reloads(self):
        self.assertEqual(BASE.get('weights_sha256'), '5af571cbf074e6d21a03528d2330792e532ca608f24ac70a143f6b369968ab8c')

    def test_baseline_failure_does_not_skip_actual_candidate_generation(self):
        from own.training_worker import compare_check
        class Model:
            def disable_adapter(self):
                return nullcontext()
        run = self.run_record()
        with patch('own.training_worker.answer', side_effect=[ValueError('No complete baseline answer'), 'A complete trained answer']) as generate:
            row = compare_check(Model(), None, run['dataset'], self.check)
        self.assertEqual(generate.call_count, 2)
        self.assertEqual(row['before'], '')
        self.assertEqual(row['before_error'], 'No complete baseline answer')
        self.assertEqual(row['after'], 'A complete trained answer')
        self.assertIsNone(row['error'])

    def test_restart_marks_partial_work_interrupted(self):
        run = self.run_record()
        self.manager.repo.interrupt()
        saved = self.manager.repo.get(self.ws, self.job, run['id'])
        self.assertEqual(saved['status'], 'interrupted')
        with self.assertRaises(Problem):
            self.manager.export(self.ws, self.job, run['id'])

    def test_failed_worker_never_becomes_a_complete_model(self):
        run = self.run_record()
        folder = self.manager.job_dir(run)
        folder.mkdir(parents=True)
        (folder / 'progress.json').write_text(json.dumps({'status': 'running', 'step': 1}))
        self.manager.reconcile(run, 1)
        self.assertEqual(self.manager.repo.get(self.ws, self.job, run['id'])['status'], 'failed')

    def test_success_requires_adapter_files_and_changed_parameters(self):
        run = self.run_record()
        folder = self.manager.job_dir(run)
        folder.mkdir(parents=True)
        (folder / 'progress.json').write_text(json.dumps({'status': 'complete', 'changed_parameters': 0, 'artifacts': {}}))
        self.manager.reconcile(run, 0)
        self.assertEqual(self.manager.repo.get(self.ws, self.job, run['id'])['status'], 'failed')

    def test_cancelled_worker_cannot_publish_even_if_it_wrote_success(self):
        run = self.run_record()
        folder = self.manager.job_dir(run)
        folder.mkdir(parents=True)
        self.manager.repo.update(self.ws, self.job, run['id'], status='cancelling')
        (folder / 'progress.json').write_text(json.dumps({'status': 'complete', 'changed_parameters': 10}))
        self.manager.reconcile(run, 0)
        self.assertEqual(self.manager.repo.get(self.ws, self.job, run['id'])['status'], 'cancelled')

    def test_adapter_archive_has_real_artifacts_and_separate_teaching_rows(self):
        run = self.run_record()
        folder = self.manager.job_dir(run) / 'adapter'
        folder.mkdir(parents=True)
        contents = {'adapter_config.json': b'{}', 'adapter_model.safetensors': b'controlled artifact bytes'}
        for name, content in contents.items():
            (folder / name).write_bytes(content)
        hashes = {name: hashlib.sha256(content).hexdigest() for name, content in contents.items()}
        self.manager.repo.update(self.ws, self.job, run['id'], status='complete', artifacts=hashes)
        data = self.manager.export(self.ws, self.job, run['id'])
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertTrue(manifest['training_performed'])
            self.assertTrue(manifest['adapter_weights_included'])
            self.assertFalse(manifest['base_weights_included'])
            self.assertIn('trained_runner.py', archive.namelist())
            self.assertEqual(len(archive.read('training.jsonl').splitlines()), 3)
            self.assertNotIn('Held out', archive.read('training.jsonl').decode())
            self.assertIn('Held out', archive.read('dataset.json').decode())
            self.assertEqual(archive.read('adapter/adapter_model.safetensors'), contents['adapter_model.safetensors'])


if __name__ == '__main__':
    unittest.main()
