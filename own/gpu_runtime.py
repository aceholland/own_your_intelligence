"""Supervise cloud workers and import only complete, verified, business-scoped results."""
import io
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import zipfile

from .gpu_jobs import ACTIVE, GpuJobRepository
from .gpu_result import validate_result
from .gpu_worker import FAILED, UNKNOWN, provider_environment
from .store import Problem
from .training_runtime import TrainingManager, read_json
from .training_setup import runtime_python, write_json


class GpuJobManager:
    def __init__(self, store, setup):
        self.repo = GpuJobRepository(store, setup)
        self.setup, self.root, self.source = setup, setup.root, setup.source
        self.lock = threading.RLock()
        self.current = None
        self.thread = None
        self.closed = False
        self.repo.interrupt()

    def folder(self, run):
        # UUIDs originate in Store, never from a client-supplied path.
        return self.root / 'runs' / run['id']

    def _launch(self, run, mode='train'):
        credentials = self.setup.vault.load()
        if not credentials:
            raise Problem('Connect your Modal account before starting or stopping a cloud job.', 409)
        folder = self.folder(run)
        folder.mkdir(parents=True, exist_ok=True)
        if mode == 'train':
            for name, content in run['source_files'].items():
                (folder / name).write_text(content, encoding='utf-8', newline='')
            task = {key: value for key, value in run.items() if key not in ('source_files', 'checks')}
            write_json(folder / 'task.json', task)
            (folder / 'cancel').unlink(missing_ok=True)
        else:
            write_json(folder / 'recovery.json', {key: run.get(key) for key in ('app_id', 'call_id', 'provider_app_name')})
        (folder / 'heartbeat').touch()
        (folder / 'progress.json').unlink(missing_ok=True)
        process = subprocess.Popen([str(runtime_python(self.root)), '-m', 'own.gpu_worker', mode, str(folder)],
            cwd=self.source, env=provider_environment(self.root, credentials), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.current = {'run': run, 'process': process}
        self.thread = threading.Thread(target=self._monitor, args=(process, run), daemon=True)
        self.thread.start()

    def start(self, ws, job, **approvals):
        with self.lock:
            if self.closed:
                raise Problem('Own is closing. Reopen the app before training.', 409)
            if self.current:
                raise Problem('A cloud job is already running or stopping. Wait for it to finish.', 409)
            if not self.setup.sdk_ready() or self.setup.vault.load() is None:
                raise Problem('Set up the GPU tools and connect your Modal account first.', 409)
            run = self.repo.begin(ws, job, **approvals)
            try:
                self._launch(run)
            except Exception as error:
                self.repo.update(ws, job, run['id'], status='failed', phase='GPU job could not start',
                                 error='The local connection process could not start. Close and reopen Own, then try again.',
                                 provider_stop_confirmed=True)
                raise Problem('The GPU process could not start. No cloud work was launched.', 503) from error
            return self.repo.summary(run)

    def _monitor(self, process, run):
        folder = self.folder(run)
        stopping_since = None
        try:
            while not self.closed and process.poll() is None:
                (folder / 'heartbeat').touch()
                progress = read_json(folder / 'progress.json')
                saved = self.repo.get(run['workspace_id'], run['job_id'], run['id'])
                changes = {key: progress[key] for key in ('app_id', 'call_id', 'provider_stop_confirmed', 'step', 'total_steps', 'loss') if key in progress}
                if saved['status'] != 'stopping':
                    status = progress.get('status')
                    if status in ('starting', 'running', 'comparing', 'stopping'):
                        changes.update(status=status, phase=progress.get('phase', saved['phase']))
                    elif status == 'returned':
                        changes.update(status='comparing', phase='Verifying the trained model')
                if changes:
                    self.repo.update(run['workspace_id'], run['job_id'], run['id'], **changes)
                if saved['status'] == 'stopping' or progress.get('status') == 'stopping':
                    stopping_since = stopping_since or time.monotonic()
                    if time.monotonic() - stopping_since > 90:
                        TrainingManager._stop(process)
                time.sleep(.5)
            if not self.closed:
                self.reconcile(run, process.returncode)
        except Exception:
            if not self.closed:
                self.repo.update(run['workspace_id'], run['job_id'], run['id'], status='interrupted',
                                 phase='Cloud job needs attention', error=UNKNOWN, download_available=False)
        finally:
            with self.lock:
                if self.current and self.current['process'] is process:
                    self.current = None

    def reconcile(self, run, exit_code):
        ws, job, run_id = run['workspace_id'], run['job_id'], run['id']
        saved = self.repo.get(ws, job, run_id)
        progress = read_json(self.folder(run) / 'progress.json')
        acknowledged = progress.get('provider_stop_confirmed') is True
        common = dict(provider_stop_confirmed=acknowledged, download_available=False)
        for key in ('app_id', 'call_id'):
            if progress.get(key): common[key] = progress[key]
        stopped = saved['status'] == 'stopping' or progress.get('status') == 'cancelled'
        if not acknowledged:
            return self.repo.update(ws, job, run_id, **common, status='interrupted', phase='Cloud stop unconfirmed', error=UNKNOWN)
        if stopped:
            return self.repo.update(ws, job, run_id, **common, status='cancelled', phase='Cloud job stopped',
                                    error='The provider acknowledged the stop. Your examples and previous model are safe.')
        if exit_code != 0 or progress.get('status') != 'returned':
            return self.repo.update(ws, job, run_id, **common, status='failed', phase='GPU job did not finish', error=FAILED)
        try:
            manifest, files = validate_result((self.folder(run) / 'result.zip').read_bytes(), saved['payload'])
            expected = {check['id']: check['output'] for check in saved['checks']}
            rows = [dict(row, expected=expected[row['check_id']]) for row in manifest['results']]
            adapter = self.folder(run) / 'adapter'
            adapter.mkdir(exist_ok=True)
            for name, data in files.items():
                (adapter / name).write_bytes(data)
            write_json(self.folder(run) / 'manifest.json', manifest)
        except (Problem, OSError, KeyError):
            return self.repo.update(ws, job, run_id, **common, status='failed', phase='GPU result could not be verified',
                error='The returned model did not pass the file and training checks. No model was imported. Keep the cloud run details for diagnosis.')
        common.update(download_available=True)
        return self.repo.update(ws, job, run_id, **common, status='complete', phase='Ready for your review', error=None,
            training_performed=True, results=rows, artifacts=manifest['artifacts'], step=manifest['steps'],
            changed_parameters=manifest['changed_parameters'], first_loss=manifest['first_loss'], last_loss=manifest['last_loss'])

    def cancel(self, ws, job, run_id):
        with self.lock:
            run = self.repo.get(ws, job, run_id)
            if run['status'] not in ACTIVE:
                raise Problem('This cloud job has already stopped.', 409)
            if self.current:
                if self.current['run']['id'] != run_id:
                    raise Problem('Another cloud job is stopping. Wait for it to finish.', 409)
                (self.folder(run) / 'cancel').touch()
                self.repo.update(ws, job, run_id, status='stopping', phase='Asking Modal to stop the cloud job')
            else:
                if not run.get('app_id') and not run.get('provider_app_name'):
                    raise Problem('The connection ended before its cloud ID was saved. Open Modal Apps and verify the job has stopped. Own cannot confirm it automatically.', 409)
                self.repo.update(ws, job, run_id, status='stopping', phase='Checking and stopping the cloud job')
                try:
                    self._launch(run, 'stop')
                except Exception as error:
                    self.repo.update(ws, job, run_id, status='interrupted', phase='Cloud stop unconfirmed', error=UNKNOWN)
                    raise Problem('The provider stop could not start. Check your saved connection and try Stop cloud job again.', 503) from error
            return self.repo.summary(self.repo.get(ws, job, run_id))

    def export(self, ws, job, run_id):
        run = self.repo.get(ws, job, run_id)
        if run['status'] != 'complete' or not run.get('download_available'):
            raise Problem('Wait for a complete, verified model before downloading it.', 409)
        try:
            manifest, files = validate_result((self.folder(run) / 'result.zip').read_bytes(), run['payload'])
        except OSError as error:
            raise Problem('The saved GPU result is missing. Restore the original private result.', 409) from error
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            manifest['results'] = run['results']
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.writestr('request.json', json.dumps(run['payload'], ensure_ascii=False, indent=2))
            archive.writestr('local-checks.json', json.dumps(run['checks'], ensure_ascii=False, indent=2))
            archive.writestr('run.json', json.dumps(self.repo.summary(run), ensure_ascii=False, indent=2))
            for name, data in files.items(): archive.writestr('adapter/' + name, data)
            for name in ('run_model.py', 'training_core.py', 'requirements.txt'):
                archive.writestr(name, run['source_files'][name])
            archive.writestr('README.txt', 'Own GPU-trained business model\n\nReal verified LoRA adapter weights are included. Keep this ZIP private: it includes business teaching examples, separate expected answers, human reviews and provenance. No credentials or base weights are included.\n\nRun on your own supported CUDA GPU, separately from the local Own app:\npython -m pip install -r requirements.txt\npython run_model.py --model . --question "Your request"\n\nThe runner downloads the exact pinned public base model separately (about 8 GB). GPU hardware/hosting may cost money; this download does not authorize a new paid job. Training completion and lower loss do not prove answer quality. Read the comparisons and human reviews.\n')
        return stream.getvalue()

    def close(self):
        with self.lock:
            self.closed = True
            current = self.current
            if current:
                (self.folder(current['run']) / 'cancel').touch()
                run = current['run']
                self.repo.update(run['workspace_id'], run['job_id'], run['id'], status='stopping', phase='Closing and stopping the cloud job')
        if current:
            try: current['process'].wait(timeout=12)
            except subprocess.TimeoutExpired: TrainingManager._stop(current['process'])
        if self.thread: self.thread.join(timeout=5)
        if current:
            self.reconcile(current['run'], current['process'].returncode)
        self.repo.interrupt()
