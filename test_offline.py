"""Built-in tests; do not require Ollama or internet access."""
import base64
import importlib
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import server


class EinsteinTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = server.DB_FILE
        server.DB_FILE = Path(self.temp.name) / 'test.sqlite3'
        server.initialize()

    def tearDown(self):
        server.DB_FILE = self.original
        self.temp.cleanup()

    def test_memory_and_retrieval(self):
        server.add_memory('My project uses Java 21')
        self.assertIn('Java', server.get_memories()[0]['note'])
        server.import_file('notes.txt', b'Project Orion runs on PostgreSQL with Java 21')
        passages = server.relevant_documents('Does Orion use PostgreSQL?')
        self.assertTrue(passages)
        self.assertIn('PostgreSQL', passages[0]['content'])
        prompt, sources = server.make_messages('Which database does Orion use?')
        self.assertIn('PostgreSQL', prompt[0]['content'])
        self.assertEqual(sources[0]['source'], 'notes.txt')

    def test_reimport_replaces_old_content(self):
        server.import_file('same.txt', b'The answer is red')
        server.import_file('same.txt', b'The answer is blue')
        self.assertFalse(server.relevant_documents('red'))
        self.assertTrue(server.relevant_documents('blue'))
        server.delete_document('same.txt')
        self.assertFalse(server.document_index())

    def test_ollama_json_protocol_with_fake_local_server(self):
        # Tests exact Ollama API request and response wire format, without an AI model.
        from http.server import BaseHTTPRequestHandler
        class FakeOllama(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers['Content-Length'])
                payload = json.loads(self.rfile.read(length))
                assert self.path == '/api/chat'
                assert payload['stream'] is False
                assert payload['model'] == server.MODEL
                body = json.dumps({'message': {'role': 'assistant', 'content': 'Local fake inference OK'}}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args): pass
        http = ThreadingHTTPServer(('127.0.0.1', 0), FakeOllama)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        original_url = server.OLLAMA_URL
        try:
            server.OLLAMA_URL = f'http://127.0.0.1:{http.server_port}'
            answer = server.ollama_chat([{'role':'user', 'content':'test'}])
            self.assertEqual(answer,'Local fake inference OK')
        finally:
            server.OLLAMA_URL = original_url
            http.shutdown(); http.server_close(); thread.join(timeout=2)

    def test_http_endpoints_without_a_model(self):
        original_chat = server.ollama_chat
        server.ollama_chat = lambda messages: 'Offline mock answer (no model was called)'
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{http.server_port}'
        def post(path, payload):
            req = Request(url+path, data=json.dumps(payload).encode(),
                          headers={'Content-Type':'application/json'}, method='POST')
            with urlopen(req) as r: return json.load(r)
        try:
            self.assertEqual(post('/api/remember', {'note':'I use a Mac'})['saved'], 'I use a Mac')
            data = base64.b64encode(b'Project Orion has a local database').decode()
            self.assertEqual(post('/api/import', {'filename':'notes.txt','data':data})['passages'],1)
            answer = post('/api/chat', {'message':'What database does Orion have?'})
            self.assertEqual(answer['answer'], 'Offline mock answer (no model was called)')
            with urlopen(url+'/api/history') as r:
                self.assertEqual(len(json.load(r)['messages']), 2)
            with urlopen(url+'/api/status') as r:
                state=json.load(r);self.assertEqual(state['documents'],1)
        finally:
            http.shutdown();http.server_close();thread.join(timeout=2)
            server.ollama_chat=original_chat


if __name__ == '__main__':
    unittest.main(verbosity=2)
