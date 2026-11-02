import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from own.store import Store, Problem
from own.credential_vault import CredentialVault
from own.gpu_setup import GpuSetup


class GpuSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / 'db.sqlite3')
        self.gpu = GpuSetup(self.store, self.root)
        original_source=self.gpu.source
        self.gpu.source=self.root/'source'
        shutil.copytree(original_source/'gpu',self.gpu.source/'gpu',ignore=shutil.ignore_patterns('__pycache__'))
        self.ws = self.store.create_workspace('Fictional business')['id']
        self.job = self.store.create_job(self.ws, 'Replies', 'Answer briefly')['id']
        for n in range(3):
            self.store.add_example(self.ws, self.job, 'teach', f'Request {n}', f'Answer {n}')
        self.store.add_example(self.ws, self.job, 'check', 'Held-out request', 'SECRET_HELD_OUT_TARGET')
        self.store.add_source(self.ws, 'Private reference', 'REFERENCE_NOT_NEEDED_FOR_TRAINING')

    def tearDown(self):
        self.gpu.close()
        self.store.close()
        self.tmp.cleanup()

    def test_local_package_requires_permission_and_current_dataset(self):
        plan = self.gpu.plan(self.ws, self.job)
        with self.assertRaises(Problem):
            self.gpu.prepare(self.ws, self.job, plan['dataset_hash'], 2.0, False)
        self.store.add_source(self.ws, 'Changed', 'New facts')
        with self.assertRaises(Problem):
            self.gpu.prepare(self.ws, self.job, plan['dataset_hash'], 2.0, True)
        self.assertEqual(self.gpu.packages(self.ws, self.job), [])

    def test_package_is_frozen_scoped_and_never_claims_training_or_upload(self):
        plan = self.gpu.plan(self.ws, self.job)
        record = self.gpu.prepare(self.ws, self.job, plan['dataset_hash'], 2.0, True)
        other = self.store.create_workspace('Other')['id']
        with self.assertRaises(Problem):
            self.gpu.export(other, self.job, record['id'])
        self.store.add_example(self.ws, self.job, 'teach', 'A later request', 'A later answer')
        with zipfile.ZipFile(io.BytesIO(self.gpu.export(self.ws, self.job, record['id']))) as z:
            manifest = json.loads(z.read('manifest.json'))
            self.assertFalse(manifest['training_performed'])
            self.assertFalse(manifest['upload_performed'])
            payload = z.read('request.json').decode()
            self.assertNotIn('SECRET_HELD_OUT_TARGET', payload)
            self.assertNotIn('REFERENCE_NOT_NEEDED_FOR_TRAINING', payload)
            self.assertNotIn('A later answer', payload)
            self.assertIn('SECRET_HELD_OUT_TARGET', z.read('local-checks.json').decode())
            self.assertIn('train_on_gpu.py', z.namelist())
            self.assertIn('run_model.py', z.namelist())
            self.assertEqual(len(json.loads(payload)['training_rows']), 3)

    def test_budget_quote_is_finite_and_not_a_hard_invoice_cap(self):
        for invalid in (float('nan'), float('inf'), -1, 0.49, 26, True):
            with self.assertRaises(Problem):
                self.gpu.quote(invalid)
        quote = self.gpu.quote(2.0)
        self.assertFalse(quote['hard_invoice_cap'])
        self.assertEqual(quote['preparation_cost_usd'], 0)
        self.assertLessEqual(quote['timeout_seconds'], 1800)

    def test_prepared_package_freezes_code_as_well_as_examples(self):
        plan=self.gpu.plan(self.ws,self.job)
        record=self.gpu.prepare(self.ws,self.job,plan['dataset_hash'],2.,True)
        script=self.gpu.source/'gpu/train_on_gpu.py'
        original=script.read_text()
        script.write_text(original+'\n# A later implementation change\n')
        with zipfile.ZipFile(io.BytesIO(self.gpu.export(self.ws,self.job,record['id']))) as archive:
            self.assertEqual(archive.read('train_on_gpu.py').decode(),original)
            self.assertIn('source_hashes',json.loads(archive.read('manifest.json')))

    def test_read_only_connection_does_not_deploy_or_return_credentials(self):
        pair = {'token_id':'ak-fictional-test-id', 'token_secret':'as-fictional-test-secret'}
        with patch.object(self.gpu, 'sdk_ready', return_value=True), patch.object(self.gpu,'_workspace_name',return_value='ac-'+'a'*22), patch('own.gpu_setup.subprocess.run', return_value=SimpleNamespace(returncode=0)) as run:
            response = self.gpu.connect(**pair)
        command = run.call_args.args[0]
        self.assertEqual(command[-4:], ['app','list','--json','--limit=1'])
        self.assertNotIn(pair['token_id'], str(command))
        self.assertNotIn(pair['token_secret'], str(response))
        self.assertTrue(response['connected'])
        self.gpu.disconnect()
        self.assertFalse(self.gpu.status()['connected'])

    def test_failed_connection_cannot_replace_verified_credentials(self):
        pair = {'token_id':'ak-fictional-test-id', 'token_secret':'as-fictional-test-secret'}
        self.gpu.vault.save(pair)
        with patch.object(self.gpu, 'sdk_ready', return_value=True), patch('own.gpu_setup.subprocess.run', return_value=SimpleNamespace(returncode=1)):
            with self.assertRaises(Problem) as error:
                self.gpu.connect('ak-another-test-id','as-another-test-secret')
        self.assertNotIn('as-another', str(error.exception))
        self.assertEqual(self.gpu.vault.load(), pair)

    def test_recovery_connection_must_match_the_original_provider_workspace(self):
        old={'token_id':'ak-old-connection','token_secret':'as-old-connection','workspace_name':'ac-'+'a'*22}
        self.gpu.vault.save(old)
        with patch.object(self.gpu,'sdk_ready',return_value=True), patch('own.gpu_setup.subprocess.run',return_value=SimpleNamespace(returncode=0)):
            with patch.object(self.gpu,'_workspace_name',return_value='ac-'+'b'*22):
                with self.assertRaises(Problem):
                    self.gpu.connect('ak-new-connection','as-new-connection',expected_workspace_name=old['workspace_name'])
            self.assertEqual(self.gpu.vault.load(),old)
            with patch.object(self.gpu,'_workspace_name',return_value=old['workspace_name']):
                self.gpu.connect('ak-new-connection','as-new-connection',expected_workspace_name=old['workspace_name'])
        self.assertEqual(self.gpu.vault.load()['workspace_name'],old['workspace_name'])
        self.assertEqual(self.gpu.vault.load()['token_id'],'ak-new-connection')

    @unittest.skipUnless(os.name == 'nt', 'Windows user-scoped protection')
    def test_dpapi_survives_restart_without_plaintext_secrets(self):
        vault = CredentialVault(self.root / 'credentials.dpapi')
        value = {'token_id':'test-id','token_secret':'test-secret-do-not-log'}
        vault.save(value)
        self.assertNotIn(value['token_secret'].encode(), vault.path.read_bytes())
        self.assertEqual(CredentialVault(vault.path).load(), value)
        vault.clear()
        self.assertIsNone(vault.load())


if __name__ == '__main__':
    unittest.main()
