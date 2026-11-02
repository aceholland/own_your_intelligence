"""Isolated SDK bridge. Credentials are process environment only; errors never echo them."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

from .store import Problem
from .training_data import digest
from .training_setup import write_json

SOURCES = frozenset(('train_on_gpu.py', 'training_core.py', 'run_model.py', 'requirements.txt', 'README.txt'))
UNKNOWN = 'The cloud job could not be confirmed stopped. Check Modal and choose Stop cloud job before training again.'
FAILED = 'The GPU job did not finish. Check the Modal run for account, credit, memory or model-download errors. No model was imported.'


def provider_environment(root, credentials):
    env = {key: value for key, value in os.environ.items() if not key.startswith('MODAL_')}
    env.update(MODAL_TOKEN_ID=credentials['token_id'], MODAL_TOKEN_SECRET=credentials['token_secret'],
               MODAL_CONFIG_PATH=str(root / 'unused-profile.toml'), MODAL_LOGLEVEL='ERROR',
               HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1', PYTHONUNBUFFERED='1')
    return env


def load_task(folder):
    try:
        task = json.loads((folder / 'task.json').read_text(encoding='utf-8'))
        approval = task['approval']
        if not all(approval[key] is True for key in ('upload', 'free_only', 'available_credits')) or type(approval['out_of_pocket_usd']) is not int or approval['out_of_pocket_usd'] != 0:
            raise ValueError('Missing free-only permission')
        if digest(task['payload']) != task['request_hash'] or set(task['source_hashes']) != SOURCES:
            raise ValueError('Changed request or trainer')
        for name, expected in task['source_hashes'].items():
            if hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
                raise ValueError('Changed trainer')
        return task
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise Problem('The saved GPU request, permissions or trainer changed. No cloud run was started.') from error


def run_provider(payload, launcher, modal, cancel_requested, publish, poll_seconds=.25, run_name=None):
    """Keep cancellation responsive even while the SDK is preparing its image."""
    app, function = launcher.build_app(payload['quote']['timeout_seconds'], **({'run_name': run_name} if run_name else {}))
    stop = threading.Event()
    done = threading.Event()
    shared = {'app_id': None, 'call_id': None, 'provider_stop_confirmed': False}
    lock = threading.Lock()
    def update(**fields):
        with lock: shared.update(fields)
    def stop_app():
        app.stop()  # Successful provider RPC acknowledgement; never inferred from a dead local process.
        update(provider_stop_confirmed=True)
    def invoke():
        try:
            with modal.Queue.ephemeral() as queue:
                if stop.is_set(): return
                with app.run():
                    update(app_id=app.app_id)
                    try:
                        if stop.is_set(): return
                        call = function.spawn(payload, queue)
                        update(call_id=call.object_id, call=call)
                        while not stop.is_set():
                            try:
                                events = queue.get_many(50, block=False)
                                for event in events:
                                    if isinstance(event, dict): update(progress=event)
                            except Exception:
                                pass  # A missing progress update must not turn into a fake step/result.
                            try:
                                data = call.get(timeout=0)
                            except modal.exception.TimeoutError as error:
                                if type(error) is not modal.exception.TimeoutError: raise
                                stop.wait(poll_seconds)
                                continue
                            if not isinstance(data, bytes) or not data or len(data) > 64 * 1024 * 1024:
                                raise ValueError('Invalid result')
                            update(data=data)
                            break
                    finally:
                        if not shared['provider_stop_confirmed']: stop_app()
        except Exception:
            update(failed=True)
        finally:
            done.set()
    thread = threading.Thread(target=invoke, daemon=True)
    thread.start()
    last = None
    started = time.monotonic()
    while True:
        with lock: current = dict(shared)
        app_id = current['app_id'] or app.app_id
        if app_id: update(app_id=app_id)
        event = dict(app_id=app_id, call_id=current['call_id'])
        progress = current.get('progress', {})
        phase = progress.get('phase')
        if phase in ('Downloading the public model', 'Loading the model', 'Learning your examples', 'Saving the trained model', 'Comparing answers'):
            event.update(phase=phase, status='comparing' if phase == 'Comparing answers' else 'running')
        for key in ('step', 'total_steps'):
            if type(progress.get(key)) is int and progress[key] >= 0: event[key] = progress[key]
        if type(progress.get('loss')) in (int, float) and math.isfinite(progress['loss']): event['loss'] = progress['loss']
        if event != last:
            publish(**event)
            last = event
        if cancel_requested() or time.monotonic() - started > 3600:
            stop.set()
            publish(status='stopping', phase='Asking Modal to stop the cloud job')
            if app_id and not current['provider_stop_confirmed']:
                try:
                    call = current.get('call')
                    if call: call.cancel(terminate_containers=True)
                except Exception:
                    pass  # App.stop terminates all inputs/containers even if call cancellation failed.
                try: stop_app()
                except Exception: pass
            with lock: current = dict(shared)
            if current['provider_stop_confirmed'] or app_id or done.is_set():
                return dict(status='cancelled' if current['provider_stop_confirmed'] else 'interrupted',
                    phase='Cloud job stopped' if current['provider_stop_confirmed'] else 'Cloud stop unconfirmed',
                    error=None if current['provider_stop_confirmed'] else UNKNOWN,
                    app_id=app_id, call_id=current['call_id'], provider_stop_confirmed=current['provider_stop_confirmed'])
            # No app ID yet: stay in Stopping until creation resolves, never allow a later unnoticed spawn.
        if done.wait(poll_seconds): break
    with lock: current = dict(shared)
    acknowledged = current['provider_stop_confirmed']
    status = 'returned' if current.get('data') and acknowledged and not current.get('failed') else 'failed' if acknowledged else 'interrupted'
    result = dict(status=status, phase='Verifying the trained model' if status == 'returned' else 'GPU job did not finish',
        error=None if status == 'returned' else FAILED if acknowledged else UNKNOWN,
        app_id=current['app_id'], call_id=current['call_id'], provider_stop_confirmed=acknowledged)
    if status == 'returned': result['data'] = current['data']
    return result


def stop_by_id(app_id):
    if not isinstance(app_id, str) or not re.fullmatch(r'ap-[A-Za-z0-9_-]{5,100}', app_id):
        return False
    options = dict(capture_output=True, timeout=35, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        # Official CLI is used for recovery because App.lookup accepts deployed names, not ephemeral IDs.
        stopped = subprocess.run([sys.executable, '-m', 'modal', 'app', 'stop', app_id, '--yes'], **options)
        if stopped.returncode == 0: return True
        info = subprocess.run([sys.executable, '-m', 'modal', 'app', 'info', app_id, '--json'], **options)
        return info.returncode == 0 and json.loads(info.stdout)['lifecycle']['state'] == 'stopped'
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        return False


def recover_stop(app_id, app_name):
    """Recover a lost ID only through an exact, per-run name; never touch another app."""
    if app_id:
        return stop_by_id(app_id), app_id
    if not isinstance(app_name, str) or not re.fullmatch(r'own-training-[a-f0-9]{32}', app_name):
        return False, None
    try:
        result = subprocess.run([sys.executable, '-m', 'modal', 'app', 'list', '--json', '--limit=0'],
            capture_output=True, timeout=35, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        rows = json.loads(result.stdout) if result.returncode == 0 else []
        matching = [row['App ID'] for row in rows if row.get('Description') == app_name]
        if len(matching) == 1:
            return stop_by_id(matching[0]), matching[0]
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
        pass
    # A missing listing is not proof that no work exists.
    return False, None


def main():
    folder = Path(sys.argv[2]).resolve()
    progress = folder / 'progress.json'
    def publish(**fields):
        current.update(fields)
        write_json(progress, current)
    current = {'status': 'starting', 'phase': 'Preparing the cloud environment', 'app_id': None, 'call_id': None,
               'provider_stop_confirmed': False}
    try:
        if sys.argv[1] == 'stop':
            task = json.loads((folder / 'recovery.json').read_text(encoding='utf-8'))
            app_id = task.get('app_id')
            acknowledged, app_id = recover_stop(app_id, task.get('provider_app_name'))
            publish(status='cancelled' if acknowledged else 'interrupted', phase='Cloud job stopped' if acknowledged else 'Cloud stop unconfirmed',
                    provider_stop_confirmed=acknowledged, app_id=app_id, call_id=task.get('call_id'), error=None if acknowledged else UNKNOWN)
            return
        task = load_task(folder)
        spec = importlib.util.spec_from_file_location('train_on_gpu', folder / 'train_on_gpu.py')
        launcher = importlib.util.module_from_spec(spec)
        sys.modules['train_on_gpu'] = launcher
        spec.loader.exec_module(launcher)
        launcher.validate_request(task['payload'], task, True, True, True)
        import modal
        publish()
        def cancel_requested():
            return (folder / 'cancel').exists() or not (folder / 'heartbeat').exists() or time.time() - (folder / 'heartbeat').stat().st_mtime > 30
        result = run_provider(task['payload'], launcher, modal, cancel_requested, publish, run_name=task.get('provider_app_name'))
        data = result.pop('data', None)
        if data is not None:
            temporary = folder / 'result.tmp'
            temporary.write_bytes(data)
            temporary.replace(folder / 'result.zip')
        publish(**result)
    except Problem:
        publish(status='failed', phase='GPU job could not start', error='The local request or permissions changed. Prepare a new GPU training.', provider_stop_confirmed=True)
    except Exception:
        publish(status='interrupted', phase='Cloud job needs attention', error=UNKNOWN)


if __name__ == '__main__': main()
