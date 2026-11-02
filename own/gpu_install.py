"""Install the client SDK locally; never authenticate, deploy or start cloud work."""
import os
from pathlib import Path
import subprocess
import sys
import venv

from .training_setup import runtime_python, write_json


def install(root):
    root.mkdir(parents=True, exist_ok=True)
    state = root / 'setup.json'
    try:
        write_json(state, {'status':'installing','phase':'Preparing separate connection tools'})
        executable = runtime_python(root)
        if not executable.exists():
            venv.EnvBuilder(with_pip=True).create(root / 'environment')
        write_json(state, {'status':'installing','phase':'Installing the Modal client · no cloud work'})
        subprocess.run([str(executable), '-m', 'pip', 'install', '--disable-pip-version-check', 'modal==1.6.3'], check=True, timeout=600)
        subprocess.run([str(executable), '-m', 'modal', 'app', 'list', '--help'], check=True, stdout=subprocess.DEVNULL, timeout=30)
        write_json(state, {'status':'ready','phase':'Connection tools ready','version':'1.6.3'})
    except Exception:
        write_json(state, {'status':'failed','phase':'Tools could not be installed','error':'Check your internet connection and free space, then try setup again.'})
        raise


if __name__ == '__main__':
    install(Path(sys.argv[1]).resolve())
