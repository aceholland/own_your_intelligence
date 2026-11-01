import json
import unittest
from unittest.mock import patch

from own.engine import OllamaEngine
from own.store import Problem


class ResponseFixture:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=None):
        return json.dumps(self.body).encode()


class EngineTests(unittest.TestCase):
    def test_remote_models_are_excluded_from_local_choices(self):
        body = {'models': [{'name': 'local-small', 'size': 1000},
                           {'name': 'large:120b-cloud'},
                           {'name': 'private-alias', 'remote_host': 'https://remote.example'},
                           {'name': 'other:cloud'}]}
        with patch('own.engine.urlopen', lambda *a, **k: ResponseFixture(body)):
            result = OllamaEngine().status()
        self.assertEqual([m['name'] for m in result['models']], ['local-small'])

    def test_chat_uses_local_endpoint_and_returns_actual_content(self):
        observed = []
        def transport(request, timeout):
            observed.append((request.full_url, json.loads(request.data)))
            return ResponseFixture({'message': {'role': 'assistant', 'content': 'Actual answer'}, 'done': True})
        with patch('own.engine.urlopen', transport):
            result = OllamaEngine().chat('small-local', [{'role': 'user', 'content': 'Question'}])
        self.assertEqual(result, 'Actual answer')
        self.assertEqual(observed[0][0], 'http://127.0.0.1:11434/api/chat')
        self.assertFalse(observed[0][1]['stream'])

    def test_empty_or_truncated_response_is_not_treated_as_success(self):
        for body in ({'done': True, 'message': {'content': ''}}, {'done': True, 'done_reason': 'length', 'message': {'content': 'partial'}}):
            with self.subTest(body=body), patch('own.engine.urlopen', lambda *a, **k: ResponseFixture(body)):
                with self.assertRaises(Problem):
                    OllamaEngine().chat('small-local', [])


if __name__ == '__main__':
    unittest.main()
