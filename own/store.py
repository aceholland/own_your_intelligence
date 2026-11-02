"""Persistent single-owner domain model. Never share this store as a multi-user API."""
import hashlib
import io
import json
import sqlite3
import threading
import unicodedata
import uuid
import zipfile
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path


class Problem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def text(value, name, limit, required=True):
    if not isinstance(value, str):
        raise Problem(f'{name} must be text.')
    value = value.strip()
    if required and not value:
        raise Problem(f'Add {name.lower()} to continue.')
    if len(value) > limit:
        raise Problem(f'{name} must be {limit:,} characters or fewer.')
    if '\x00' in value:
        raise Problem(f'{name} contains an unsupported character.')
    return value


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def fingerprint(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def atomic(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self.lock, self.db:
            return method(self, *args, **kwargs)
    return wrapped


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, workspace_id TEXT NOT NULL, job_id TEXT NOT NULL, payload TEXT NOT NULL)')
        self.db.execute('CREATE INDEX IF NOT EXISTS records_scope ON records(kind, workspace_id, job_id)')
        self.db.commit()

    def close(self):
        self.db.close()

    def _put(self, kind, ws, job, data):
        self.db.execute('INSERT OR REPLACE INTO records VALUES (?, ?, ?, ?, ?)',
                        (data['id'], kind, ws, job, json.dumps(data, ensure_ascii=False)))
        return data

    def _new(self, record_type, ws, job, **data):
        return self._put(record_type, ws, job, dict(id=uuid.uuid4().hex, created_at=datetime.now(timezone.utc).isoformat(), **data))

    def _get(self, kind, record_id, ws=None, job=None):
        row = self.db.execute('SELECT workspace_id, job_id, payload FROM records WHERE id=? AND kind=?', (record_id, kind)).fetchone()
        if not row or (ws is not None and row[0] != ws) or (job is not None and row[1] != job):
            raise Problem('That item is not in this workspace. Refresh and try again.', 404)
        return json.loads(row[2])

    def _list(self, kind, ws=None, job=None):
        sql, args = 'SELECT payload FROM records WHERE kind=?', [kind]
        if ws is not None:
            sql += ' AND workspace_id=?'
            args.append(ws)
        if job is not None:
            sql += ' AND job_id=?'
            args.append(job)
        sql += ' ORDER BY rowid'
        return [json.loads(row[0]) for row in self.db.execute(sql, args).fetchall()]

    @atomic
    def list_workspaces(self):
        return self._list('workspace')

    @atomic
    def create_workspace(self, name):
        if len(self._list('workspace')) >= 30:
            raise Problem('This local edition supports up to 30 workspaces.')
        name = text(name, 'Business name', 100)
        return self._new('workspace', '', '', name=name)

    @atomic
    def workspace(self, ws):
        item = self._get('workspace', ws)
        return dict(item, jobs=self._list('job', ws), sources=self._list('source', ws))

    @atomic
    def create_job(self, ws, name, goal):
        self._get('workspace', ws)
        if len(self._list('job', ws)) >= 100:
            raise Problem('This local edition supports up to 100 jobs per workspace.')
        return self._new('job', ws, '', name=text(name, 'Job name', 100), goal=text(goal, 'Job description', 1500), instructions='', model='', revision=1, active_version_id=None)

    @atomic
    def job(self, ws, job):
        item = self._get('job', job, ws)
        return dict(item, examples=self._list('example', ws, job),
                    runs=list(reversed(self._list('run', ws, job)[-20:])),
                    evaluations=list(reversed(self._list('evaluation', ws, job)[-10:])),
                    versions=list(reversed(self._list('version', ws, job))),
                    fingerprint=fingerprint(self.snapshot(ws, job)))

    @atomic
    def update_job(self, ws, job, changes, revision):
        item = self._get('job', job, ws)
        if item['revision'] != revision:
            raise Problem('This job changed in another tab. Refresh before saving your changes.', 409)
        limits = {'name': 100, 'goal': 1500, 'instructions': 4000, 'model': 150}
        for key, value in changes.items():
            if key not in limits:
                raise Problem('That job setting is not supported.')
            item[key] = text(value, key.replace('_', ' ').capitalize(), limits[key], key in ('name', 'goal'))
        item['revision'] += 1
        return self._put('job', ws, '', item)

    @atomic
    def add_source(self, ws, title, content):
        self._get('workspace', ws)
        if len(self._list('source', ws)) >= 40:
            raise Problem('This local edition supports 40 source files per workspace.')
        return self._new('source', ws, '', title=text(title, 'File name', 160), content=text(content, 'Document', 200000))

    @atomic
    def add_example(self, ws, job, kind, input_text, output, source_run_id=None):
        self._get('job', job, ws)
        if kind not in ('teach', 'check'):
            raise Problem('Choose a teaching example or a check example.')
        input_text = text(input_text, 'Example request', 4000)
        output = text(output, 'Example answer', 6000)
        existing = self._list('example', ws, job)
        if kind == 'check' and sum(e['kind'] == 'check' for e in existing) >= 10:
            raise Problem('This laptop edition supports 10 checks per job. The existing checks are kept and can still run.')
        if len(existing) >= 200:
            raise Problem('This local edition supports 200 examples per job.')
        if any(normalized(item['input']) == normalized(input_text) for item in existing):
            raise Problem('That request is already an example. Use a different request; checks must be separate from teaching examples.', 409)
        if source_run_id:
            self._get('run', source_run_id, ws, job)
        return self._new('example', ws, job, kind=kind, input=input_text, output=output, source_run_id=source_run_id)

    @atomic
    def snapshot(self, ws, job):
        item = self._get('job', job, ws)
        examples = self._list('example', ws, job)
        return {'job': {k: item[k] for k in ('name', 'goal', 'instructions', 'model')},
                'sources': self._list('source', ws),
                'examples': [e for e in examples if e['kind'] == 'teach'],
                'checks': [e for e in examples if e['kind'] == 'check']}

    @atomic
    def edit_example(self, ws, job, example_id, input_text, output, expected):
        self._get('job', job, ws)
        example = self._get('example', example_id, ws, job)
        if fingerprint(example) != fingerprint(expected):
            raise Problem('This example changed in another tab. Close and reopen it before saving.', 409)
        input_text = text(input_text, 'Example request', 4000)
        output = text(output, 'Example answer', 6000)
        if any(e['id'] != example_id and normalized(e['input']) == normalized(input_text)
               for e in self._list('example', ws, job)):
            raise Problem('That request is already an example. Keep teaching and checks separate.', 409)
        example.update(input=input_text, output=output, edited_at=datetime.now(timezone.utc).isoformat())
        return self._put('example', ws, job, example)

    @atomic
    def resolve_snapshot(self, ws, job, mode):
        item = self._get('job', job, ws)
        if mode == 'draft':
            return self.snapshot(ws, job), None
        if mode != 'live':
            raise Problem('Choose the draft or approved version.')
        if not item['active_version_id']:
            raise Problem('Approve a checked version before using it here.')
        version = self._get('version', item['active_version_id'], ws, job)
        return version['snapshot'], version['id']

    @atomic
    def record_run(self, ws, job, snapshot, input_text, output, references, duration_ms, version_id):
        self._get('job', job, ws)
        return self._new('run', ws, job, input=input_text, output=output, references=references,
                         duration_ms=duration_ms, model=snapshot['job']['model'],
                         fingerprint=fingerprint(snapshot), version_id=version_id, corrected_output=None)

    @atomic
    def correct_run(self, ws, job, run_id, corrected):
        run = self._get('run', run_id, ws, job)
        corrected = text(corrected, 'Corrected answer', 6000)
        if run['corrected_output'] is not None:
            raise Problem('A correction is already saved for this answer.', 409)
        existing = next((e for e in self._list('example', ws, job) if normalized(e['input']) == normalized(run['input'])), None)
        if existing:
            if existing['kind'] == 'check':
                raise Problem('This request belongs to a held-out check. Use a different request for teaching.', 409)
            existing.update(output=corrected, source_run_id=run_id)
            self._put('example', ws, job, existing)
        else:
            self.add_example(ws, job, 'teach', run['input'], corrected, run_id)
        run['corrected_output'] = corrected
        return self._put('run', ws, job, run)

    @atomic
    def record_evaluation(self, ws, job, snapshot, results):
        self._get('job', job, ws)
        expected_ids = {c['id'] for c in snapshot['checks']}
        if not expected_ids or len(results) != len(expected_ids) or {r['check_id'] for r in results} != expected_ids:
            raise Problem('Run every check in this job before reviewing a version.')
        rows = [dict(r, review='pending') for r in results]
        return self._new('evaluation', ws, job, fingerprint=fingerprint(snapshot), model=snapshot['job']['model'], results=rows)

    @atomic
    def review_check(self, ws, job, evaluation_id, check_id, review):
        if review not in ('pass', 'fail'):
            raise Problem('Choose looks right or needs work.')
        evaluation = self._get('evaluation', evaluation_id, ws, job)
        row = next((r for r in evaluation['results'] if r['check_id'] == check_id), None)
        if row is None:
            raise Problem('That check is not in this run.', 404)
        if row.get('error'):
            raise Problem('This check did not finish. Reconnect the model and run checks again.')
        row['review'] = review
        return self._put('evaluation', ws, job, evaluation)

    @atomic
    def begin_evaluation(self, ws, job, snapshot):
        if len(snapshot['checks']) > 10:
            raise Problem('Run up to 10 checks per job in this laptop edition.')
        existing = self._list('evaluation', ws, job)
        if any(e.get('status') == 'running' for e in existing):
            raise Problem('Checks are already running for this job.', 409)
        results = [dict(check_id=c['id'], input=c['input'], expected=c['output'], output='', error='Waiting for the model.') for c in snapshot['checks']]
        evaluation = self.record_evaluation(ws, job, snapshot, results)
        evaluation['status'] = 'running'
        return self._put('evaluation', ws, job, evaluation)

    @atomic
    def finish_check(self, ws, job, evaluation_id, check_id, output, error):
        evaluation = self._get('evaluation', evaluation_id, ws, job)
        row = next(r for r in evaluation['results'] if r['check_id'] == check_id)
        row.update(output=output, error=error)
        return self._put('evaluation', ws, job, evaluation)

    @atomic
    def finish_evaluation(self, ws, job, evaluation_id):
        evaluation = self._get('evaluation', evaluation_id, ws, job)
        evaluation['status'] = 'complete'
        return self._put('evaluation', ws, job, evaluation)

    @atomic
    def interrupt_evaluations(self):
        for evaluation in self._list('evaluation'):
            if evaluation.get('status') == 'running':
                row = self.db.execute('SELECT workspace_id, job_id FROM records WHERE id=?', (evaluation['id'],)).fetchone()
                evaluation['status'] = 'interrupted'
                for result in evaluation['results']:
                    if result.get('error') == 'Waiting for the model.':
                        result['error'] = 'The app restarted before this check finished. Run checks again.'
                self._put('evaluation', *row, evaluation)

    @atomic
    def approve(self, ws, job):
        item = self._get('job', job, ws)
        snapshot = self.snapshot(ws, job)
        if not snapshot['job']['model']:
            raise Problem('Choose a local model before approving a version.')
        evaluations = self._list('evaluation', ws, job)
        latest = evaluations[-1] if evaluations else None
        if not latest or latest['fingerprint'] != fingerprint(snapshot):
            raise Problem('Run checks on the current draft first. Teaching or file changes need fresh checks.')
        if not latest['results'] or any(r['review'] != 'pass' or r.get('error') for r in latest['results']):
            raise Problem('Review every check and mark each one looks right before approving.')
        version = self._new('version', ws, job, number=len(self._list('version', ws, job)) + 1,
                            snapshot=snapshot, evaluation_id=latest['id'], fingerprint=fingerprint(snapshot))
        item['active_version_id'] = version['id']
        item['revision'] += 1
        self._put('job', ws, '', item)
        return version

    @atomic
    def activate(self, ws, job, version_id):
        item = self._get('job', job, ws)
        self._get('version', version_id, ws, job)
        item['active_version_id'] = version_id
        item['revision'] += 1
        return self._put('job', ws, '', item)

    @atomic
    def training_jsonl(self, ws, job):
        snapshot = self.snapshot(ws, job)
        system = '\n'.join([snapshot['job']['goal'], snapshot['job']['instructions']]).strip()
        return ''.join(json.dumps({'messages': [
            {'role': 'system', 'content': system}, {'role': 'user', 'content': e['input']},
            {'role': 'assistant', 'content': e['output']} ]}, ensure_ascii=False) + '\n' for e in snapshot['examples'])

    @atomic
    def export_workspace(self, ws):
        workspace = self.workspace(ws)
        jobs = [self.job(ws, item['id']) for item in workspace['jobs']]
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps({'format': 'own-workspace-v1', 'model_weights_included': False,
                'training_performed': False, 'contains_business_data': True,
                'inference_provider': 'Ollama', 'next_step': 'Model weight training and a standalone runner are not included.'}, indent=2))
            archive.writestr('workspace.json', json.dumps(dict(workspace, jobs=jobs), ensure_ascii=False, indent=2))
            archive.writestr('README.txt', 'Own workspace export\n\nContains business documents, teaching examples, separate check examples, recent answers, evaluation history and approved configuration snapshots. Treat this archive as private business data.\n\ntraining/*.jsonl includes teaching examples only; checks are held out. No model weights or trained adapters are included. You need the named Ollama base model, subject to its license, to run inference. Prompt/example customization is not model weight training.\n')
            for job in jobs:
                archive.writestr(f"training/{job['id']}.jsonl", self.training_jsonl(ws, job['id']))
        return stream.getvalue()
