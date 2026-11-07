#!/usr/bin/env python3
"""Test suite for the Scheduled AI Jobs Handbook scripts.

Runs every real script against the included mock OpenAI-compatible server —
no Ollama needed, no keys, no network beyond localhost.

  python3 tests/run_tests.py        # run everything
  python3 tests/run_tests.py -v     # chatty mode

Exit code 0 = all tests passed.
"""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
EXAMPLES = ROOT / "examples"
PYTHON = sys.executable or "python3"


def start_mock_server(env_extra: dict | None = None) -> tuple[subprocess.Popen, int]:
    """Start mock_ai_server.py on a free port; returns (proc, port)."""
    env = os.environ.copy()
    for key in ("MOCK_FAIL", "MOCK_FAIL_FIRST"):
        env.pop(key, None)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.Popen(
        [PYTHON, str(SCRIPTS / "mock_ai_server.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    deadline = time.time() + 10
    while time.time() < deadline:
        line = proc.stdout.readline().decode()
        m = re.match(r"PORT=(\d+)", line)
        if m:
            return proc, int(m.group(1))
        if proc.poll() is not None:
            break
        time.sleep(0.05)
    proc.kill()
    raise RuntimeError("mock server did not report a port")


def stop_mock_server(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


class JobRunnerTests(unittest.TestCase):
    """scripts/ai_job.py — the general-purpose scheduled job runner."""

    def setUp(self):
        self.proc, self.port = start_mock_server()
        self.base = f"http://127.0.0.1:{self.port}/v1"
        self.tmp = Path(tempfile.mkdtemp())
        self.out_dir = self.tmp / "logs"

    def tearDown(self):
        stop_mock_server(self.proc)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *args):
        cmd = [PYTHON, str(SCRIPTS / "ai_job.py"), "--base-url", self.base, *args]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    def test_basic_success_writes_output_and_log(self):
        r = self._run("--prompt", "Summarize this", "--out-dir", str(self.out_dir))
        self.assertEqual(r.returncode, 0, r.stderr)
        log = (self.out_dir / "ai-job.log").read_text()
        self.assertIn("[START]", log)
        self.assertIn("[DONE]", log)
        # Privacy by design: the log must not contain prompt or reply text.
        self.assertNotIn("Summarize this", log)
        self.assertNotIn("MOCK RESPONSE", log)
        outputs = list(self.out_dir.glob("ai-job-*.md"))
        self.assertEqual(len(outputs), 1)
        self.assertIn("MOCK RESPONSE", outputs[0].read_text())

    def test_input_file_is_passed_to_the_model(self):
        r = self._run(
            "--prompt", "Digest these notes",
            "--input-file", str(EXAMPLES / "notes-sample.md"),
            "--out-dir", str(self.out_dir),
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        reply = next(self.out_dir.glob("ai-job-*.md")).read_text()
        self.assertIn("First line of your prompt was: Digest these notes", reply)

    def test_empty_input_file_is_reported_not_crashed(self):
        empty = self.tmp / "empty.md"
        empty.write_text("")
        r = self._run("--prompt", "go", "--input-file", str(empty),
                      "--out-dir", str(self.out_dir))
        self.assertEqual(r.returncode, 0, r.stderr)  # skipped runs are fine
        log = (self.out_dir / "ai-job.log").read_text()
        self.assertNotIn("[FAILED]", log)
        self.assertFalse(list(self.out_dir.glob("ai-job-*.md")))

    def test_missing_input_file_fails_cleanly(self):
        r = self._run("--prompt", "go", "--input-file", "nope.md",
                      "--out-dir", str(self.out_dir))
        self.assertEqual(r.returncode, 2)
        self.assertIn("[FAILED]", (self.out_dir / "ai-job.log").read_text())

    def test_retries_exhaustion_fails_with_code_1(self):
        self.proc.kill()
        self.proc, self.port = start_mock_server({"MOCK_FAIL": "1"})
        self.base = f"http://127.0.0.1:{self.port}/v1"
        r = self._run("--prompt", "go", "--out-dir", str(self.out_dir),
                      "--retries", "2")
        self.assertEqual(r.returncode, 1)
        log = (self.out_dir / "ai-job.log").read_text()
        self.assertIn("[FAILED]", log)
        self.assertIn("failed after 2 attempt", log)
        self.assertFalse(list(self.out_dir.glob("ai-job-*.md")))

    def test_flaky_endpoint_is_beaten_by_retries(self):
        self.proc.kill()
        self.proc, self.port = start_mock_server({"MOCK_FAIL_FIRST": "2"})
        self.base = f"http://127.0.0.1:{self.port}/v1"
        r = self._run("--prompt", "go", "--out-dir", str(self.out_dir),
                      "--retries", "3")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[DONE]", (self.out_dir / "ai-job.log").read_text())

    def test_fresh_lock_makes_a_second_run_skip(self):
        lock = self.out_dir / "ai-job.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({"pid": 999999, "ts": time.time()}))
        r = self._run("--prompt", "go", "--out-dir", str(self.out_dir))
        self.assertEqual(r.returncode, 0)  # skipping is a healthy outcome
        log = (self.out_dir / "ai-job.log").read_text()
        self.assertIn("[SKIPPED]", log)
        self.assertIn("still active", log)
        self.assertFalse(list(self.out_dir.glob("ai-job-*.md")))

    def test_stale_lock_is_taken_over(self):
        lock = self.out_dir / "ai-job.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        old = time.time() - 4 * 60 * 60
        lock.write_text(json.dumps({"pid": 999999, "ts": old}))
        r = self._run("--prompt", "go", "--out-dir", str(self.out_dir))
        self.assertEqual(r.returncode, 0, r.stderr)
        log = self.out_dir / "ai-job.log"
        self.assertIn("stale lock", log.read_text())
        self.assertFalse(lock.exists())  # released at the end

    def test_second_run_right_after_first_does_not_stack(self):
        """A lock left behind by a just-finished job is still fresh -> skip."""
        lock = self.out_dir / "ai-job.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({"pid": -1, "ts": time.time()}))
        r = self._run("--prompt", "go", "--out-dir", str(self.out_dir), "--force")
        # --force is the documented escape hatch for humans debugging by hand
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("forced", (self.out_dir / "ai-job.log").read_text())


class DigestTests(unittest.TestCase):
    """scripts/morning_digest.py — the morning digest pattern."""

    def setUp(self):
        self.proc, self.port = start_mock_server()
        self.base = f"http://127.0.0.1:{self.port}/v1"
        self.tmp = Path(tempfile.mkdtemp())
        self.out_dir = self.tmp / "logs"

    def tearDown(self):
        stop_mock_server(self.proc)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *args):
        cmd = [PYTHON, str(SCRIPTS / "morning_digest.py"),
               "--base-url", self.base, *args]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    def test_digest_from_sample_notes(self):
        r = self._run("--notes-file", str(EXAMPLES / "notes-sample.md"),
                      "--out-dir", str(self.out_dir))
        self.assertEqual(r.returncode, 0, r.stderr)
        digest = next(self.out_dir.glob("morning-digest-*.md"))
        text = digest.read_text()
        self.assertIn("# Morning digest", text)
        self.assertIn("MOCK RESPONSE", text)
        self.assertIn("[DONE]", (self.out_dir / "morning-digest.log").read_text())

    def test_missing_notes_writes_polite_nothing(self):
        r = self._run("--notes-file", str(self.tmp / "nope.md"),
                      "--out-dir", str(self.out_dir))
        self.assertEqual(r.returncode, 0, r.stderr)
        digest = next(self.out_dir.glob("morning-digest-*.md"))
        self.assertIn("Nothing to digest today", digest.read_text())

    def test_headings_only_notes_count_as_nothing(self):
        only = self.tmp / "only.md"
        only.write_text("# Header\n\n## Another header\n")
        r = self._run("--notes-file", str(only), "--out-dir", str(self.out_dir))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Nothing to digest today",
                      next(self.out_dir.glob("morning-digest-*.md")).read_text())


class WatchdogTests(unittest.TestCase):
    """scripts/watchdog.py — runaway-job detection."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _watch(self, *args):
        cmd = [PYTHON, str(SCRIPTS / "watchdog.py"), "--job-dir", str(self.tmp), *args]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    def test_all_quiet(self):
        (self.tmp / "ai-job.log").write_text(
            "2026-11-07T10:00:00Z [DONE] success; reply 500 chars\n")
        (self.tmp / "ai-job.lock").write_text(json.dumps({"pid": 1, "ts": time.time()}))
        r = self._watch()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("all quiet", r.stdout)

    def test_oversized_log_is_flagged_and_pruneful(self):
        (self.tmp / "chatty.log").write_text("x" * (5 * 1024 * 1024 + 10))
        r = self._watch()
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("oversized log", r.stdout)
        r2 = self._watch("--prune")
        self.assertEqual(r2.returncode, 2)
        self.assertIn("pruned", r2.stdout)
        self.assertFalse((self.tmp / "chatty.log").exists())
        self.assertTrue(list(self.tmp.glob("chatty.log.oversized-*")))
        self.assertFalse(list(self.tmp.glob("*.log")))

    def test_stale_lock_is_flagged(self):
        lock = self.tmp / "ai-job.lock"
        lock.write_text('{"pid": 1}')
        old = time.time() - 5 * 60 * 60
        os.utime(lock, (old, old))
        r = self._watch()
        self.assertEqual(r.returncode, 2)
        self.assertIn("stale lock", r.stdout)
        self.assertIn("5.0 hours", r.stdout)
        r2 = self._watch("--clean-locks")
        self.assertIn("cleaned", r2.stdout)
        self.assertFalse(lock.exists())

    def test_recent_failure_is_flagged(self):
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 600))
        (self.tmp / "ai-job.log").write_text(f"{now} [FAILED] model call error: boom\n")
        r = self._watch()
        self.assertEqual(r.returncode, 2)
        self.assertIn("FAILED", r.stdout)

    def test_empty_dir_reports_nothing(self):
        r = self._watch()
        self.assertEqual(r.returncode, 3)


class MockServerTests(unittest.TestCase):
    """scripts/mock_ai_server.py — the fake endpoint itself."""

    def test_models_endpoint(self):
        proc, port = start_mock_server()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models") as r:
                data = json.loads(r.read())
            self.assertEqual(data["data"][0]["id"], "mock-model")
        finally:
            stop_mock_server(proc)

    def test_chat_completion_shape(self):
        proc, port = start_mock_server()
        try:
            payload = json.dumps({
                "model": "m", "messages": [{"role": "user", "content": "hello"}],
            }).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/v1/chat/completions",
                data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as r:
                data = json.loads(r.read())
            content = data["choices"][0]["message"]["content"]
            self.assertIn("MOCK RESPONSE", content)
            self.assertEqual(data["choices"][0]["message"]["role"], "assistant")
        finally:
            stop_mock_server(proc)


def main() -> int:
    verbosity = 2 if "-v" in sys.argv else 1
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for case in (JobRunnerTests, DigestTests, WatchdogTests, MockServerTests):
        suite.addTests(loader.loadTestsFromTestCase(case))
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
