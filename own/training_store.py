"""Scoped frozen datasets and human decisions, independent of ML dependencies."""
from datetime import datetime, timezone

from .store import Problem, atomic, normalized
from .training_data import BASE, CONFIG, dataset_hash, freeze_dataset

ACTIVE = ('queued', 'running', 'comparing', 'cancelling')


class TrainingRepository:
    def __init__(self, store):
        self.store, self.lock, self.db = store, store.lock, store.db

    @atomic
    def prepare(self, ws, job):
        snapshot = self.store.snapshot(ws, job)
        blockers = []
        if len(snapshot['examples']) < 3:
            blockers.append('Add at least 3 teaching examples in Teach it.')
        if not snapshot['checks']:
            blockers.append('Add at least 1 separate check in Check it.')
        teaching = {normalized(e['input']) for e in snapshot['examples']}
        if any(normalized(c['input']) in teaching for c in snapshot['checks']):
            blockers.append('Teaching requests and check requests must be different.')
        return {'ready': not blockers, 'blockers': blockers, 'dataset_hash': dataset_hash(snapshot),
                'teaching_count': len(snapshot['examples']), 'check_count': len(snapshot['checks']),
                'base': BASE, 'config': CONFIG, 'provider_cost': 0, 'location': 'this laptop'}

    @atomic
    def begin(self, ws, job, expected_hash, permission):
        plan = self.prepare(ws, job)
        if permission is not True:
            raise Problem('Confirm you have permission to train on these examples.')
        if plan['dataset_hash'] != expected_hash:
            raise Problem('Your examples or instructions changed. Review the training plan again.', 409)
        if plan['blockers']:
            raise Problem(' '.join(plan['blockers']))
        if any(t['status'] in ACTIVE for t in self.store._list('training')):
            raise Problem('Training is already running on this laptop. Wait or stop it first.', 409)
        return self.store._new('training', ws, job, workspace_id=ws, job_id=job,
            dataset_hash=plan['dataset_hash'], dataset=freeze_dataset(self.store.snapshot(ws, job)),
            permission={'confirmed': True, 'confirmed_at': datetime.now(timezone.utc).isoformat(),
                        'statement': 'I have permission to use these business examples for local model training.'},
            base=dict(BASE), config=dict(CONFIG), status='queued', phase='Preparing training',
            step=0, total_steps=plan['teaching_count'] * CONFIG['epochs'], results=[], error=None)

    @atomic
    def get(self, ws, job, run_id):
        self.store._get('job', job, ws)
        return self.store._get('training', run_id, ws, job)

    @atomic
    def list(self, ws, job):
        self.store._get('job', job, ws)
        # Frozen datasets are available separately in exports, not duplicated on each poll.
        return [self.summary(t) for t in reversed(self.store._list('training', ws, job))]

    @staticmethod
    def summary(record):
        return {k: v for k, v in record.items() if k != 'dataset'}

    @atomic
    def update(self, ws, job, run_id, **changes):
        run = self.get(ws, job, run_id)
        run.update(changes)
        return self.store._put('training', ws, job, run)

    @atomic
    def review(self, ws, job, run_id, check_id, review):
        if review not in ('pass', 'fail'):
            raise Problem('Choose looks right or needs work.')
        run = self.get(ws, job, run_id)
        if run['status'] != 'complete':
            raise Problem('Wait for training and the before-and-after checks to finish.')
        row = next((r for r in run['results'] if r['check_id'] == check_id), None)
        if not row or row.get('error') or not row.get('after') or not (row.get('before') or row.get('before_error')):
            raise Problem('This comparison did not finish. Train and compare again.')
        row['review'] = review
        return self.update(ws, job, run_id, results=run['results'])

    @atomic
    def select(self, ws, job, run_id):
        run = self.get(ws, job, run_id)
        expected = {c['id'] for c in run['dataset']['checks']}
        actual = {r['check_id'] for r in run['results']}
        if run['status'] != 'complete' or not expected or actual != expected or len(run['results']) != len(expected):
            raise Problem('Finish training and every comparison before using this update.')
        if any(r.get('error') or r.get('review') != 'pass' or not (r.get('before') or r.get('before_error')) or not r.get('after') for r in run['results']):
            raise Problem('Review every trained answer and mark it looks right before using this update.')
        if self.prepare(ws, job)['dataset_hash'] != run['dataset_hash']:
            raise Problem('Your teaching data or instructions changed. Train a fresh update before selecting it.', 409)
        item = self.store._get('job', job, ws)
        return self.store.update_job(ws, job, {'model': 'own:' + run_id}, item['revision'])

    @atomic
    def interrupt(self):
        for run in self.store._list('training'):
            if run['status'] in ACTIVE:
                self.update(run['workspace_id'], run['job_id'], run['id'], status='interrupted',
                    phase='Training stopped', error='The app restarted before this training finished. Your examples are safe; start a new training.')
