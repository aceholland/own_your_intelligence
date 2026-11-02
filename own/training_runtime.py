"""Supervise one real local training process; never manufacture model results."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid
import zipfile

from .store import Problem
from .training_data import BASE
from .training_setup import runtime_python, write_json
from .training_store import ACTIVE, TrainingRepository

ARTIFACT_FILES = {'adapter_config.json', 'adapter_model.safetensors', 'tokenizer.json',
                  'tokenizer_config.json', 'special_tokens_map.json', 'chat_template.jinja',
                  'vocab.json', 'merges.txt', 'README.md'}


def read_json(path, fallback=None):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {} if fallback is None else fallback


def verify_artifact(folder, hashes):
    required = {'adapter_config.json', 'adapter_model.safetensors'}
    if not isinstance(hashes, dict) or not required.issubset(hashes) or set(hashes) - ARTIFACT_FILES:
        raise Problem('The saved training is incomplete. Train a new update.', 409)
    for name, expected in hashes.items():
        path = folder / name
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise Problem('The saved model files changed or are missing. Train a new update before using or exporting it.', 409)


class TrainingManager:
    def __init__(self, store, data_dir, inference_lock):
        self.repo = TrainingRepository(store)
        self.root = Path(data_dir).resolve() / 'training'
        self.source = Path(__file__).resolve().parent.parent
        self.inference_lock = inference_lock
        self.lock = threading.RLock()
        self.current = None
        self.thread = None
        self.closed = False
        self.repo.interrupt()
        setup = read_json(self.root / 'setup.json')
        if setup.get('status') == 'installing':
            write_json(self.root / 'setup.json', dict(status='failed', phase='Setup was interrupted',
                error='The app restarted during setup. Choose Set up local training to continue.'))

    def status(self):
        status = read_json(self.root / 'setup.json', {'status': 'not_installed', 'phase': 'Set up local training once'})
        if status.get('status') == 'ready' and (not runtime_python(self.root).exists() or not (self.root / 'base/model.safetensors').exists()):
            status = {'status': 'failed', 'phase': 'Training files are missing', 'error': 'Choose Set up local training to repair it.'}
        return dict(status, base=BASE, busy=self.current is not None, provider_cost=0,
                    message='Runs on this laptop. No business data is uploaded. No provider charge.')

    def job_dir(self, run):
        return self.root / 'jobs' / run['workspace_id'] / run['job_id'] / run['id']

    def _environment(self, offline=True):
        env = dict(os.environ, HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1',
                   HF_HUB_DISABLE_SYMLINKS_WARNING='1', TOKENIZERS_PARALLELISM='false',
                   HF_HUB_DISABLE_XET='1', HF_HOME=str(self.root / 'cache'))
        env.pop('HF_TOKEN', None)
        if offline:
            env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        return env

    def _launch(self, command, log_path, run=None):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('a', encoding='utf-8') as log:
            process = subprocess.Popen(command, cwd=self.source, env=self._environment(offline=run is not None),
                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.current = {'process': process, 'run': run}
        self.thread = threading.Thread(target=self._monitor, args=(process, run), daemon=True)
        self.thread.start()

    def setup(self):
        with self.lock:
            if self.current:
                raise Problem('Your laptop is already setting up or training. Wait for it to finish.', 409)
            if self.status()['status'] == 'ready':
                return self.status()
            self.root.mkdir(parents=True, exist_ok=True)
            write_json(self.root / 'setup.json', {'status': 'installing', 'phase': 'Preparing local training'})
            executable = Path(sys.executable)
            if executable.name.lower() == 'pythonw.exe':
                executable = executable.with_name('python.exe')
            try:
                self._launch([str(executable), '-m', 'own.training_setup', str(self.root)], self.root / 'setup.log')
            except OSError as error:
                write_json(self.root / 'setup.json', {'status': 'failed', 'phase': 'Setup could not start',
                    'error': 'Close and reopen Own, then try setting up local training again.'})
                raise Problem('Setup could not start. Close and reopen Own, then try again.', 503) from error
            return self.status()

    def start(self, ws, job, expected_hash, permission):
        with self.lock:
            if self.status()['status'] != 'ready':
                raise Problem('Set up local training first. You only need to do this once.')
            if self.current or not self.inference_lock.acquire(blocking=False):
                raise Problem('Your local AI is busy. Wait for it to finish before training.', 409)
            run = None
            try:
                run = self.repo.begin(ws, job, expected_hash, permission)
                folder = self.job_dir(run)
                folder.mkdir(parents=True)
                write_json(folder / 'task.json', run)
                (folder / 'heartbeat').touch()
                self._launch([str(runtime_python(self.root)), '-m', 'own.training_worker', 'train',
                              str(self.root), str(folder)], folder / 'worker.log', run)
                return self.repo.summary(run)
            except Exception:
                if run:
                    self.repo.update(ws, job, run['id'], status='failed', phase='Training could not start',
                                     error='The training process could not start. Close and reopen Own, then try again.')
                self.inference_lock.release()
                raise

    def _monitor(self, process, run):
        try:
            while process.poll() is None:
                if run:
                    folder = self.job_dir(run)
                    (folder / 'heartbeat').touch()
                    update = read_json(folder / 'progress.json')
                    if update and self.repo.get(run['workspace_id'], run['job_id'], run['id'])['status'] != 'cancelling':
                        update.pop('artifacts', None)
                        if update.get('status') == 'complete':
                            update['status'] = 'comparing'
                        self.repo.update(run['workspace_id'], run['job_id'], run['id'], **update)
                time.sleep(.5)
            if run:
                self.reconcile(run, process.returncode)
            elif process.returncode != 0:
                status = read_json(self.root / 'setup.json')
                if status.get('status') != 'failed':
                    write_json(self.root / 'setup.json', {'status': 'failed', 'phase': 'Setup stopped',
                        'error': 'Check your internet connection and disk space, then set up local training again.'})
        except Exception:
            if run and not self.closed:
                self.repo.update(run['workspace_id'], run['job_id'], run['id'], status='failed',
                    phase='Training stopped', error='The training process could not be verified. Start a new training.')
        finally:
            with self.lock:
                self.current = None
                if run:
                    self.inference_lock.release()

    def reconcile(self, run, exit_code):
        saved = self.repo.get(run['workspace_id'], run['job_id'], run['id'])
        progress = read_json(self.job_dir(run) / 'progress.json')
        if saved['status'] == 'cancelling' or progress.get('status') == 'cancelled':
            progress = {'status': 'cancelled', 'phase': 'Training stopped', 'error': 'You stopped this training. Your examples and earlier versions are safe.'}
        elif exit_code == 0 and progress.get('status') == 'complete':
            try:
                if progress.get('changed_parameters', 0) <= 0:
                    raise Problem('Training did not produce changed model weights.')
                verify_artifact(self.job_dir(run) / 'adapter', progress.get('artifacts'))
            except Problem as error:
                progress = {'status': 'failed', 'phase': 'Training could not be verified', 'error': str(error)}
        else:
            progress.update(status='failed', phase='Training could not finish',
                error=progress.get('error') or 'The training process stopped before saving a complete model. Check free memory and try again.')
        return self.repo.update(run['workspace_id'], run['job_id'], run['id'], **progress)

    @staticmethod
    def _stop(process):
        if process.poll() is not None:
            return
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        else:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()

    def cancel(self, ws, job, run_id):
        with self.lock:
            run = self.repo.get(ws, job, run_id)
            if run['status'] not in ACTIVE:
                raise Problem('This training has already stopped.', 409)
            if not self.current or not self.current['run'] or self.current['run']['id'] != run_id:
                raise Problem('This training process is no longer active. Refresh the page.', 409)
            (self.job_dir(run) / 'cancel').touch()
            self.repo.update(ws, job, run_id, status='cancelling', phase='Stopping training')
            self._stop(self.current['process'])
            return self.repo.summary(self.repo.get(ws, job, run_id))

    def checked_record(self, ws, job, run_id):
        run = self.repo.get(ws, job, run_id)
        if run['status'] != 'complete':
            raise Problem('This training has not produced a complete model.', 409)
        verify_artifact(self.job_dir(run) / 'adapter', run.get('artifacts'))
        return run

    def select(self, ws, job, run_id):
        self.checked_record(ws, job, run_id)
        return self.repo.select(ws, job, run_id)

    def chat(self, ws, job, run_id, messages):
        run = self.checked_record(ws, job, run_id)
        if self.status()['status'] != 'ready':
            raise Problem('Set up local training to run this saved model.', 503)
        folder = self.root / 'requests'
        folder.mkdir(parents=True, exist_ok=True)
        task = folder / (uuid.uuid4().hex + '.json')
        write_json(task, {'adapter': str(self.job_dir(run) / 'adapter'), 'messages': messages})
        result_file = task.with_suffix('.result.json')
        try:
            with (self.root / 'inference.log').open('a', encoding='utf-8') as log:
                process = subprocess.run([str(runtime_python(self.root)), '-m', 'own.training_worker', 'answer',
                    str(self.root), str(task)], cwd=self.source, env=self._environment(),
                    stdout=log, stderr=log, stdin=subprocess.DEVNULL, timeout=180,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            result = read_json(result_file)
            if process.returncode or not result.get('output'):
                raise Problem('The small trained model could not finish this answer. Try shorter input or clearer examples. Details are in data/training/inference.log.', 502)
            return result['output']
        except subprocess.TimeoutExpired as error:
            raise Problem('The trained model took longer than three minutes. Try a shorter request.', 504) from error
        finally:
            task.unlink(missing_ok=True)
            result_file.unlink(missing_ok=True)

    def export(self, ws, job, run_id):
        run = self.checked_record(ws, job, run_id)
        manifest = {'format': 'own-trained-adapter-v1', 'training_performed': True,
            'adapter_weights_included': True, 'base_weights_included': False, 'base': run['base'],
            'dataset_hash': run['dataset_hash'], 'artifacts': run['artifacts'], 'config': run['config'],
            'permission': run['permission'], 'contains_business_data': True}
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps(manifest, indent=2))
            archive.writestr('dataset.json', json.dumps(run['dataset'], ensure_ascii=False, indent=2))
            archive.writestr('training.jsonl', ''.join(json.dumps({'messages': row['messages']}, ensure_ascii=False) + '\n' for row in run['dataset']['training_rows']))
            archive.writestr('comparison.json', json.dumps(run['results'], ensure_ascii=False, indent=2))
            for name in run['artifacts']:
                archive.write(self.job_dir(run) / 'adapter' / name, 'adapter/' + name)
            for name in ('trained_runner.py', 'requirements-training.txt'):
                archive.write(self.source / name, name)
            license_file = self.root / 'base/LICENSE'
            if license_file.exists():
                archive.write(license_file, 'BASE-LICENSE.txt')
            archive.writestr('README.txt', 'Own trained business model\n\nReal LoRA adapter weights are included. The exact public base model is downloaded separately once by the runner; it is not included in this ZIP. Keep this archive private: it includes your teaching examples, held-out checks and consent record.\n\nExtract to a folder. Install Python 3.11-3.13, then run:\npython -m pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu\npython -m pip install -r requirements-training.txt\npython trained_runner.py --bundle . --question "Your request"\n\nAfter the first public-model download, add --offline. No Own server or paid API key is required. The small starter model has limited ability; review its answers. Training completion does not establish business quality. See manifest.json for revision and license.\n')
        return stream.getvalue()

    def close(self):
        with self.lock:
            self.closed = True
            current = self.current
            if current:
                if current['run']:
                    run = current['run']
                    self.repo.update(run['workspace_id'], run['job_id'], run['id'], status='cancelling')
                self._stop(current['process'])
        if self.thread:
            self.thread.join(timeout=20)
