"""Deterministic transport fixture, NOT a model or a quality benchmark."""
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/api/embeddings":
            digest = hashlib.sha256(payload["prompt"].encode()).digest()
            result = {"embedding": [(x + 1) / 256 for x in digest]}
        elif self.path == "/api/generate":
            result = {"response": "Fixture response: " + payload["prompt"][-300:]}
        else:
            self.send_error(404)
            return
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 19034), Handler).serve_forever()
