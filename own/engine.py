"""Actual Ollama inference; no fabricated or remote fallback responses."""
import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .store import Problem


class OllamaEngine:
    BASE = 'http://127.0.0.1:11434'

    def status(self):
        try:
            with urlopen(self.BASE + '/api/tags', timeout=3) as response:
                data = json.loads(response.read(1048576))
            models = [{'name': m['name'], 'size': m.get('size', 0)} for m in data.get('models', [])
                      if isinstance(m.get('name'), str)
                      and not m['name'].endswith((':cloud', '-cloud'))
                      and not m.get('remote_host') and not m.get('remote_model')]
            return {'connected': True, 'models': models, 'message': 'Ready on this laptop' if models else 'Install a local model to try your AI.'}
        except (URLError, OSError, ValueError, KeyError):
            return {'connected': False, 'models': [], 'message': 'Open Ollama, then check the connection again.'}

    def chat(self, model, messages):
        payload = {'model': model, 'messages': messages, 'stream': False, 'think': False,
                   'keep_alive': '2m', 'options': {'temperature': 0.1, 'num_ctx': 8192, 'num_predict': 650}}
        request = Request(self.BASE + '/api/chat', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=180) as response:
                data = json.loads(response.read(2097152))
        except HTTPError as error:
            if error.code == 404:
                raise Problem('That model is not installed. Choose an installed model in Teach it.', 503) from error
            raise Problem('Ollama could not run this model. Open Ollama, check available memory, and try again.', 503) from error
        except (socket.timeout, TimeoutError) as error:
            raise Problem('This answer took longer than three minutes. Try a shorter request or a smaller model.', 504) from error
        except (URLError, OSError, ValueError) as error:
            raise Problem('The local model is unavailable. Open Ollama and check the connection.', 503) from error
        content = data.get('message', {}).get('content', '').strip()
        if not content or not data.get('done'):
            raise Problem('The model returned no complete answer. Try a shorter request.', 502)
        if data.get('done_reason') == 'length':
            raise Problem('The answer reached its length limit. Ask for a shorter answer and try again.', 502)
        return content
