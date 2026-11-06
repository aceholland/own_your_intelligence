"""Scoped GPU job snapshots, free-only consent and human reviews."""
from datetime import datetime, timezone
from uuid import uuid4

from .gpu_setup import GPU_BASE, GPU_CONFIG
from .store import Problem, atomic
from .training_data import digest, freeze_dataset

ACTIVE = ('queued', 'starting', 'running', 'comparing', 'stopping', 'interrupted')
PRIVATE = ('payload', 'checks', 'source_files')
COLAB = 'Colab'


class GpuJobRepository:
    def __init__(self, store, setup):
        self.store, self.setup, self.lock, self.db = store, setup, store.lock, store.db

    @staticmethod
    def summary(run):
        return {key: value for key, value in run.items() if key not in PRIVATE}

    @atomic
    def begin(self, ws, job, *, dataset_hash, upload, free_only, zero_limit, credits):
        self.store._get('job', job, ws)
        if not all(value is True for value in (upload, free_only, zero_limit, credits)):
            raise Problem('Confirm permission to upload, free credits only, a $0 out-of-pocket limit and enough available credits before starting.')
        if any(run['status'] in ACTIVE for run in self.store._list('gpu_run')):
            raise Problem('A GPU job is still active or its stop is unconfirmed. Finish or stop it before starting another.', 409)
        package = self.setup.prepare(ws, job, dataset_hash, 2.0, True)
        frozen = self.store._get('gpu_package', package['id'], ws, job)
        run = self.store._new('gpu_run', ws, job, workspace_id=ws, job_id=job,
            payload=frozen['payload'], checks=frozen['checks'], source_files=frozen['source_files'],
            source_hashes=frozen['source_hashes'], package_id=package['id'], request_hash=frozen['request_hash'],
            dataset_hash=dataset_hash, base=frozen['base'], quote=frozen['quote'],
            approval={'upload': True, 'free_only': True, 'out_of_pocket_usd': 0, 'available_credits': True,
                      'billing_source': 'owner-confirmed', 'confirmed_at': datetime.now(timezone.utc).isoformat()},
            status='queued', phase='Preparing the GPU job', step=0,
            total_steps=len(frozen['payload']['training_rows']) * frozen['payload']['config']['epochs'],
            results=[], error=None, app_id=None, call_id=None, provider_stop_confirmed=False,
            training_performed=False, download_available=False)
        return self.update(ws, job, run['id'], provider_app_name='own-training-' + run['id'])

    @atomic
    def get(self, ws, job, run_id):
        self.store._get('job', job, ws)
        return self.store._get('gpu_run', run_id, ws, job)

    @atomic
    def list(self, ws, job, provider='Modal'):
        self.store._get('job', job, ws)
        return [self.summary(run) for run in reversed(self.store._list('gpu_run', ws, job))
                if run.get('provider', 'Modal') == provider]

    @atomic
    def begin_colab(self, ws, job, dataset_hash, permission):
        if permission is not True:
            raise Problem('Confirm you have permission to share the examples and check questions with Google Colab.')
        plan = self.setup.repo.prepare(ws, job)
        if dataset_hash != plan['dataset_hash']:
            raise Problem('Your examples or instructions changed. Review the current draft and prepare again.', 409)
        if not plan['ready']:
            raise Problem(' '.join(plan['blockers']))
        for run in self.list(ws, job, COLAB):
            if run['status'] == 'awaiting_result' and run['dataset_hash'] == dataset_hash:
                return run
        dataset = freeze_dataset(self.store.snapshot(ws, job))
        payload = {
            'format': 'own-gpu-request-v1', 'base': GPU_BASE, 'config': GPU_CONFIG,
            'run_nonce': uuid4().hex, 'dataset_hash': dataset_hash,
            'job': {key: dataset['job'][key] for key in ('goal', 'instructions')},
            'training_rows': [{'messages': row['messages']} for row in dataset['training_rows']],
            'checks': [{'id': row['id'], 'input': row['input']} for row in dataset['checks']],
        }
        sources = {name: (self.setup.source / 'gpu' / name).read_text(encoding='utf-8')
                   for name in ('training_core.py', 'run_model.py', 'requirements.txt')}
        run = self.store._new('gpu_run', ws, job, workspace_id=ws, job_id=job, provider=COLAB,
            payload=payload, checks=dataset['checks'], source_files=sources,
            request_hash=digest(payload), dataset_hash=dataset_hash, base=GPU_BASE,
            approval={'upload': True, 'free_only': True, 'confirmed_at': datetime.now(timezone.utc).isoformat()},
            status='awaiting_result', phase='Ready to train in Colab', step=0,
            total_steps=len(payload['training_rows']) * GPU_CONFIG['epochs'],
            results=[], error=None, training_performed=False, download_available=False)
        return self.summary(run)

    def get_colab(self, ws, job, run_id):
        run = self.get(ws, job, run_id)
        if run.get('provider') != COLAB:
            raise Problem('Choose the notebook you prepared for Colab.', 404)
        return run

    @atomic
    def update(self, ws, job, run_id, **changes):
        run = self.get(ws, job, run_id)
        run.update(changes)
        return self.store._put('gpu_run', ws, job, run)

    @atomic
    def review(self, ws, job, run_id, check_id, review):
        if review not in ('pass', 'fail'):
            raise Problem('Choose looks right or needs work.')
        run = self.get(ws, job, run_id)
        row = next((row for row in run['results'] if row['check_id'] == check_id), None)
        if run['status'] != 'complete' or not row or row.get('error') or not row.get('after'):
            raise Problem('This comparison did not finish. Wait for a successful trained answer before reviewing it.')
        row['review'] = review
        return self.update(ws, job, run_id, results=run['results'])

    @atomic
    def interrupt(self):
        for run in self.store._list('gpu_run'):
            if run['status'] in ACTIVE:
                self.update(run['workspace_id'], run['job_id'], run['id'], status='interrupted',
                    phase='Check the cloud job', error='The app restarted. The cloud stop is unconfirmed. Choose Stop cloud job to confirm it before training again.')
