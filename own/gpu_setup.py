"""Setup-only GPU integration. No compute launch or business-data upload endpoint."""
import io
import hashlib
import json
import math
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
import zipfile

from .credential_vault import CredentialVault
from .store import Problem, atomic
from .training_data import digest, freeze_dataset
from .training_store import TrainingRepository
from .training_setup import runtime_python, write_json

GPU_BASE = {'id': 'Qwen/Qwen3-4B-Instruct-2507', 'revision': 'cdbee75f17c01a7cc42f958dc650907174af0554',
    'license': 'apache-2.0', 'model_card_url': 'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507',
    'weights_sha256': {
        'model-00001-of-00003.safetensors': '75311d91bb08cf0b882913da464a1e722a31fb44db35208663487efb7a3d8ed6',
        'model-00002-of-00003.safetensors': '0b48adbb1f60e901153d91907ba11ce63bd4b8b584482e730f48808d055dfba1',
        'model-00003-of-00003.safetensors': '7dd39ccca5e4de123c74c14af44c9bf2eb75df33b4614382af0134528e060d5d'}}
GPU_CONFIG = {'epochs': 3, 'rank': 8, 'alpha': 16, 'learning_rate': .0002, 'max_tokens': 1024,
              'max_new_tokens': 200, 'seed': 42, 'target_modules': ['q_proj', 'v_proj']}
PRICE = {'checked_on': '2026-11-02', 'gpu_per_second': .000222, 'cpu_cores': 2,
         'cpu_core_per_second': .0000131, 'memory_gib': 16, 'memory_gib_per_second': .00000222,
         'source': 'https://modal.com/pricing'}


class GpuSetup:
    def __init__(self, store, data_dir):
        self.store, self.lock, self.db = store, store.lock, store.db
        self.repo = TrainingRepository(store)
        self.root = Path(data_dir).resolve() / 'gpu'
        self.source = Path(__file__).resolve().parent.parent
        self.vault = CredentialVault(self.root / 'connection.dpapi')
        self.setup_lock = threading.RLock()
        self.process = None

    @staticmethod
    def quote(budget):
        if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not math.isfinite(budget) or not .5 <= budget <= 25:
            raise Problem('Choose a planning allowance from $0.50 to $25 USD.')
        rate = PRICE['gpu_per_second'] + PRICE['cpu_cores'] * PRICE['cpu_core_per_second'] + PRICE['memory_gib'] * PRICE['memory_gib_per_second']
        seconds = min(1800, math.floor((budget - .25) / rate))
        return {'planning_allowance_usd': budget, 'timeout_seconds': seconds,
            'estimated_compute_usd': round(seconds * rate, 2), 'setup_allowance_usd': .25,
            'preparation_cost_usd': 0, 'hard_invoice_cap': False, 'rates': PRICE,
            'excludes': 'Image preparation, storage, network charges and taxes; actual charges follow Modal billing.',
            'spend_limit_url': 'https://modal.com/docs/guide/budgets'}

    def sdk_ready(self):
        try:
            return json.loads((self.root / 'setup.json').read_text())['status'] == 'ready' and runtime_python(self.root).exists()
        except (OSError, ValueError, KeyError):
            return False

    def status(self):
        try:
            setup = json.loads((self.root / 'setup.json').read_text())
        except (OSError, ValueError):
            setup = {'status': 'not_installed', 'phase': 'Set up the connection tools once'}
        if setup['status'] == 'installing' and (self.process is None or self.process.poll() is not None):
            setup = {'status': 'failed', 'phase': 'Setup was interrupted', 'error': 'Choose Set up GPU tools to continue.'}
        try:
            connected = self.vault.load() is not None
            connection_error = None
        except Problem as error:
            connected, connection_error = False, str(error)
        return {'provider': 'Modal', 'sdk': setup, 'connected': connected, 'connection_error': connection_error,
                'credential_storage': 'Windows user protection' if os.name == 'nt' else 'This session only',
                'remote_training_enabled': False, 'business_data_uploaded': False, 'base': GPU_BASE}

    def install(self):
        with self.setup_lock:
            if self.sdk_ready() or self.process and self.process.poll() is None:
                return self.status()
            self.root.mkdir(parents=True, exist_ok=True)
            write_json(self.root / 'setup.json', {'status': 'installing', 'phase': 'Installing the local connection tools'})
            executable = Path(sys.executable)
            if executable.name.lower() == 'pythonw.exe':
                executable = executable.with_name('python.exe')
            with (self.root / 'setup.log').open('a', encoding='utf-8') as log:
                env = {k:v for k,v in os.environ.items() if not k.startswith('MODAL_')}
                self.process = subprocess.Popen([str(executable), '-m', 'own.gpu_install', str(self.root)],
                    cwd=self.source, env=env, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            return self.status()

    def connect(self, token_id, token_secret):
        with self.setup_lock:
            if not self.sdk_ready():
                raise Problem('Set up GPU tools before connecting your account.')
            if not all(isinstance(v, str) and 8 <= len(v) <= 300 and not any(c.isspace() for c in v) for v in (token_id, token_secret)) or not token_id.startswith('ak-') or not token_secret.startswith('as-'):
                raise Problem('Copy the token ID and secret from your Modal account. Do not use your account password.')
            env = {k:v for k,v in os.environ.items() if not k.startswith('MODAL_')}
            env.update(MODAL_TOKEN_ID=token_id, MODAL_TOKEN_SECRET=token_secret,
                       MODAL_CONFIG_PATH=str(self.root / 'unused-profile.toml'), MODAL_LOGLEVEL='ERROR')
            try:
                result = subprocess.run([str(runtime_python(self.root)), '-m', 'modal', 'app', 'list', '--json', '--limit=1'],
                    env=env, cwd=self.source, capture_output=True, timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            except (OSError, subprocess.TimeoutExpired) as error:
                raise Problem('The connection check could not finish. Check your internet connection and retry. No training was started.', 503) from error
            if result.returncode:
                raise Problem('Modal could not verify this token pair. Check the ID, secret and internet connection. No training was started.', 400)
            self.vault.save({'token_id': token_id, 'token_secret': token_secret})
            return self.status()

    def disconnect(self):
        with self.setup_lock:
            self.vault.clear()
            return self.status()

    @atomic
    def plan(self, ws, job):
        plan = self.repo.prepare(ws, job)
        return dict(plan, base=GPU_BASE, config=GPU_CONFIG, provider='Modal', quote=self.quote(2.0),
                    packages=self.packages(ws, job), training_enabled=False)

    @atomic
    def packages(self, ws, job):
        self.store._get('job', job, ws)
        return [dict({k:v for k,v in record.items() if k not in ('payload','checks','source_files')},
                     download_available=bool(record.get('source_files'))) for record in reversed(self.store._list('gpu_package', ws, job))]

    @atomic
    def prepare(self, ws, job, expected_hash, budget, permission):
        plan = self.plan(ws, job)
        quote = self.quote(budget)
        if permission is not True:
            raise Problem('Confirm you have permission to prepare these business examples for GPU training.')
        if expected_hash != plan['dataset_hash']:
            raise Problem('Your examples or instructions changed. Reopen the preparation form before continuing.', 409)
        if not plan['ready']:
            raise Problem(' '.join(plan['blockers']))
        dataset = freeze_dataset(self.store.snapshot(ws, job))
        payload = {'format': 'own-gpu-request-v1', 'base': GPU_BASE, 'config': GPU_CONFIG, 'quote': quote,
            'dataset_hash': expected_hash, 'job': {k:dataset['job'][k] for k in ('goal','instructions')},
            'training_rows': dataset['training_rows'], 'checks': [{'id':c['id'], 'input':c['input']} for c in dataset['checks']]}
        sources={name:(self.source/'gpu'/name).read_text(encoding='utf-8')
                 for name in ('train_on_gpu.py','training_core.py','run_model.py','requirements.txt','README.txt')}
        record = self.store._new('gpu_package', ws, job, status='prepared', training_performed=False,
            upload_performed=False, dataset_hash=expected_hash, request_hash=digest(payload), base=GPU_BASE,
            source_files=sources,source_hashes={name:hashlib.sha256(content.encode()).hexdigest() for name,content in sources.items()},
            quote=quote, payload=payload, checks=dataset['checks'], permission={'confirmed':True,
                'confirmed_at':datetime.now(timezone.utc).isoformat(), 'scope':'Local package preparation only; no cloud run or upload authorized.'})
        return {k:v for k,v in record.items() if k not in ('payload','checks','source_files')}

    @atomic
    def export(self, ws, job, package_id):
        self.store._get('job', job, ws)
        record = self.store._get('gpu_package', package_id, ws, job)
        if not record.get('source_files'):
            raise Problem('This early preparation does not include a frozen trainer. Prepare a new package.',409)
        manifest = {k:v for k,v in record.items() if k not in ('payload','checks','source_files')}
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps(manifest, indent=2))
            archive.writestr('request.json', json.dumps(record['payload'], ensure_ascii=False, indent=2))
            archive.writestr('local-checks.json', json.dumps(record['checks'], ensure_ascii=False, indent=2))
            for name,content in record['source_files'].items():
                archive.writestr(name,content)
        return stream.getvalue()

    def close(self):
        if self.process and self.process.poll() is None:
            from .training_runtime import TrainingManager
            TrainingManager._stop(self.process)
