#!/usr/bin/env python3
"""A tiny OpenAI-compatible mock server, for testing scheduled AI jobs.

Speaks just enough of the OpenAI chat-completions dialect that everything in
this handbook can be tested without a real model, without Ollama running, and
without any network access beyond your own machine.

Usage:
    python3 scripts/mock_ai_server.py [--port 8099]

The chosen port is printed as `PORT=<n>` on stdout — start it in the
background, read that line, and point your job runner at it.

Test switches (environment variables):
    MOCK_FAIL=1        every request returns HTTP 500
    MOCK_FAIL_FIRST=N  the first N requests fail, then it starts succeeding
                       (perfect for testing retries)

Stdlib only. No data leaves your machine. Nothing is written to disk.
"""

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_fail_count = {"n": 0}


def make_reply(messages: list[dict]) -> str:
    user = next((m["content"] for m in messages if m.get("role") == "user"), "")
    first_line = user.strip().splitlines()[0][:120] if user.strip() else "(empty)"
    n = sum(len(m.get("content", "")) for m in messages)
    return (
        f"MOCK RESPONSE (received {n} chars total).\n"
        f"First line of your prompt was: {first_line}\n"
        f"This is pretend-model output so scheduled scripts can be tested "
        f"without a real AI endpoint."
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the test output clean
        pass

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            body = json.dumps({"object": "list", "data": [{"id": "mock-model"}]}).encode()
            self._send(200, body)
        else:
            self._send(404, b'{"error": {"message": "not found"}}')

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/chat/completions"):
            self._send(404, b'{"error": {"message": "not found"}}')
            return

        if os.environ.get("MOCK_FAIL") == "1":
            self._fail("mock server is configured to always fail (MOCK_FAIL=1)")
            return
        try:
            fail_first = int(os.environ.get("MOCK_FAIL_FIRST", "0"))
        except ValueError:
            fail_first = 0
        _fail_count["n"] += 1
        if fail_first >= _fail_count["n"]:
            self._fail(
                f"mock failing on purpose for test (MOCK_FAIL_FIRST={fail_first}, "
                f"request #{_fail_count['n']})"
            )
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, OSError):
            self._send(400, b'{"error": {"message": "bad request"}}')
            return
        reply = make_reply(data.get("messages", []))
        body = json.dumps(
            {
                "id": "mock-1",
                "object": "chat.completion",
                "model": data.get("model", "mock-model"),
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": reply},
                     "finish_reason": "stop"}
                ],
            }
        ).encode("utf-8")
        self._send(200, body)

    def _fail(self, why: str):
        body = json.dumps({"error": {"message": why}}).encode("utf-8")
        self._send(500, body)

    def _send(self, code: int, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="mock OpenAI-compatible server")
    parser.add_argument("--port", type=int, default=0, help="0 = pick a free port")
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        print(f"error: could not bind: {exc}", file=sys.stderr)
        return 1
    port = server.server_address[1]
    print(f"PORT={port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
