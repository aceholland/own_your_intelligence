"""Start Own on loopback. --launch creates a hidden server and opens the browser."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent


def ready(url):
    try:
        with urlopen(url + '/api/bootstrap', timeout=1) as response:
            data = json.loads(response.read())
        return 'csrf_token' in data and 'capabilities' in data
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description='Your local business AI workbench')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--launch', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Choose a port between 1024 and 65535.')
    url = f'http://127.0.0.1:{args.port}'
    if args.launch:
        if not ready(url):
            args.data_dir.mkdir(parents=True, exist_ok=True)
            executable = Path(sys.executable)
            if os.name == 'nt' and executable.with_name('pythonw.exe').exists():
                executable = executable.with_name('pythonw.exe')
            log = open(args.data_dir / 'server.log', 'a', encoding='utf-8')
            subprocess.Popen([str(executable), str(ROOT / 'run.py'), '--no-browser', '--port', str(args.port), '--data-dir', str(args.data_dir.resolve())],
                             cwd=str(ROOT), stdout=log, stderr=log,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            log.close()
            for _ in range(50):
                if ready(url):
                    break
                time.sleep(.2)
            else:
                print('Own could not start. Open data/server.log, or run SETUP.cmd and try again.')
                return 1
        webbrowser.open(url)
        print(f'Own is ready at {url}')
        return 0
    try:
        import uvicorn
        from own.api import create_app
    except ImportError:
        print('A dependency is missing. Run SETUP.cmd once, then open START.cmd.')
        return 1
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', args.port))
        except OSError:
            print(f'Port {args.port} is already in use. Open {url} if Own is running, or choose --port 8766.')
            return 1
    app = create_app(args.data_dir)
    if not args.no_browser:
        import threading
        def open_when_ready():
            for _ in range(50):
                if ready(url):
                    webbrowser.open(url)
                    return
                time.sleep(.2)
        threading.Thread(target=open_when_ready, daemon=True).start()
    print(f'Own is running at {url}. Press Ctrl+C to stop.')
    uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning', access_log=False)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
