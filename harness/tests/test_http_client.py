"""Send one real HTTP request through Inspect's ollama/ provider to a local stub server.

The mock model never builds an HTTP client, so it can't catch inspect-ai/openai mismatches: an old
inspect-ai with openai 3.x broke every real request ("unsupported operand type(s) for +: 'float' and
'Timeout'"), and a new inspect-ai with openai 2.x refuses to create the ollama/ model at all.
No GPU or Ollama needed."""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from inspect_ai.model import GenerateConfig, get_model

COMPLETION = {
    "id": "chatcmpl-stub",
    "object": "chat.completion",
    "created": 0,
    "model": "stub",
    "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "pong"}}],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}


class _Handler(BaseHTTPRequestHandler):
    paths: list[str] = []

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.paths.append(self.path)
        body = json.dumps(COMPLETION).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def test_ollama_provider_round_trip():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        model = get_model(
            "ollama/stub",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            config=GenerateConfig(timeout=10, max_retries=0),  # timeout set, as in our configs
        )
        output = asyncio.run(model.generate("ping"))
    finally:
        server.shutdown()
        server.server_close()
    assert output.error is None, output.error
    assert output.completion == "pong"
    assert _Handler.paths == ["/v1/chat/completions"]
