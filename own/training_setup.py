"""Fixed one-time installer. Downloads public dependencies/model, never business data."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import venv

from .training_data import BASE


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    for attempt in range(10):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(.05)


def runtime_python(root):
    executable = root.resolve() / 'environment' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    # pip installs deeply nested PyTorch headers. This avoids a machine-wide registry change.
    if os.name == 'nt' and not str(executable).startswith('\\\\?\\'):
        executable = Path('\\\\?\\' + str(executable))
    return executable


def setup(root):
    root.mkdir(parents=True, exist_ok=True)
    status = root / 'setup.json'
    def stage(phase, state='installing', **extra):
        write_json(status, dict(status=state, phase=phase, base=BASE, **extra))
    try:
        stage('Preparing a separate training environment')
        executable = runtime_python(root)
        if not executable.exists():
            venv.EnvBuilder(with_pip=True).create(root / 'environment')
        env = dict(os.environ, HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1',
                   HF_HUB_DISABLE_XET='1', HF_HUB_DISABLE_SYMLINKS_WARNING='1', TOKENIZERS_PARALLELISM='false')
        env.pop('HF_TOKEN', None)
        stage('Installing the CPU training engine')
        subprocess.run([str(executable), '-m', 'pip', 'install', '--disable-pip-version-check',
            'torch==2.9.1+cpu', '--index-url', 'https://download.pytorch.org/whl/cpu'],
            check=True, env=env, timeout=1200)
        stage('Installing model training tools')
        requirements = Path(__file__).resolve().parent.parent / 'requirements-training.txt'
        subprocess.run([str(executable), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(requirements)],
            check=True, env=env, timeout=1200)
        stage('Downloading the small shared model · about 270 MB')
        subprocess.run([str(executable), '-m', 'own.training_worker', 'download', str(root)],
            check=True, env=env, timeout=1200)
        stage('Local training is ready', 'ready', error=None)
    except Exception:
        stage('Setup could not finish', 'failed', error='Check your internet connection and free disk space, then choose Set up local training again. Details are in data/training/setup.log.')
        raise


if __name__ == '__main__':
    setup(Path(sys.argv[1]).resolve())
