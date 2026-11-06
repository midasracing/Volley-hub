"""Local integration test: persistent cookies survive an actual browser restart."""
import json
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

from run import Engine


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Set-Cookie', 'lab_session=persisted; Max-Age=3600; Path=/')
        self.end_headers()
        self.wfile.write(('<html><body>' + json.dumps({'cookie_received':
                         'lab_session=persisted' in self.headers.get('Cookie', '')}) + '</body></html>').encode())

    def log_message(self, *args):
        pass


class RestartIntegrationTests(unittest.TestCase):
    def test_private_profile_survives_restart(self):
        server = HTTPServer(('127.0.0.1', 0), Handler)
        Thread(target=server.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{server.server_port}/'
        try:
            for name in ('stealth', 'rebrowser', 'patchright'):
                with self.subTest(engine=name), tempfile.TemporaryDirectory() as folder:
                    engine = Engine(name, Path(folder))
                    try:
                        engine.start()
                        first = engine.get(url)
                        self.assertIn('"cookie_received": false', first['html'])
                        engine.close()
                        engine.start()
                        second = engine.get(url)
                        self.assertIn('"cookie_received": true', second['html'])
                    finally:
                        engine.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
