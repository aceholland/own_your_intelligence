"""Scoped GPU job snapshots, free-only consent and human reviews."""
from datetime import datetime, timezone

from .store import Problem, atomic

ACTIVE = ('queued', 'starting', 'running', 'comparing', 'stopping', 'interrupted')
PRIVATE = ('payload', 'checks', 'source_files')


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
        return self.store._new('gpu_run', ws, job, workspace_id=ws, job_id=job,
            payload=frozen['payload'], checks=frozen['checks'], source_files=frozen['source_files'],
            source_hashes=frozen['source_hashes'], package_id=package['id'], request_hash=frozen['request_hash'],
            dataset_hash=dataset_hash, base=frozen['base'], quote=frozen['quote'],
            approval={'upload': True, 'free_only': True, 'out_of_pocket_usd': 0, 'available_credits': True,
                      'billing_source': 'owner-confirmed', 'confirmed_at': datetime.now(timezone.utc).isoformat()},
            status='queued', phase='Preparing the GPU job', step=0,
            total_steps=len(frozen['payload']['training_rows']) * frozen['payload']['config']['epochs'],
            results=[], error=None, app_id=None, call_id=None, provider_stop_confirmed=False,
            training_performed=False, download_available=False)

    @atomic
    def get(self, ws, job, run_id):
        self.store._get('job', job, ws)
        return self.store._get('gpu_run', run_id, ws, job)

    @atomic
    def list(self, ws, job):
        self.store._get('job', job, ws)
        return [self.summary(run) for run in reversed(self.store._list('gpu_run', ws, job))]

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
