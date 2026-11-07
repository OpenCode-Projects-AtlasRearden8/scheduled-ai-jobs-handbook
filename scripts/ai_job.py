#!/usr/bin/env python3
"""Run one scheduled AI job against any OpenAI-compatible endpoint.

Local-first: point it at Ollama, LM Studio, llama.cpp's server, or anything
else speaking the OpenAI chat-completions dialect. No API keys required.

Built-in guardrails (the things Chapter 8 and 9 of the handbook are about):
  * a lock file, so a schedule can't stack copies of the same job
  * log rotation, so a chatty job can't eat your disk
  * response-size caps, so a confused model can't write a novel
  * retries with backoff, so a hiccup doesn't fail the whole run
  * privacy: the log records outcomes and byte counts, never prompt contents

Uses only the Python standard library. Exit codes:
  0 = ran fine (or was skipped because another run is already active)
  1 = failed after all retries
  2 = bad arguments / bad input file
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_MODEL = "llama3.2"
DEFAULT_TIMEOUT = 120
DEFAULT_RETRIES = 3
MAX_LOG_BYTES = 5 * 1024 * 1024
MAX_RESPONSE_CHARS = 50_000
LOCK_STALE_SECONDS = 3 * 60 * 60  # a lock older than 3h is presumed dead


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_log(log_path: Path, status: str, message: str) -> None:
    """Append one line. We log outcomes, never prompt or response text."""
    msg = message.replace("\n", " ").strip()
    line = f"{now_utc()} [{status}] {msg}\n"
    try:
        with open(log_path, "a", encoding="utf-8", errors="replace") as f:
            f.write(line)
    except OSError:
        pass  # never let logging kill the job


def rotate_log_if_big(log_path: Path, max_bytes: int = MAX_LOG_BYTES) -> str | None:
    """If the log got huge, move it aside instead of writing forever."""
    try:
        if not log_path.exists() or log_path.stat().st_size < max_bytes:
            return None
    except OSError:
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rotated = log_path.with_name(f"{log_path.name}.{stamp}")
    try:
        log_path.rename(rotated)
        return rotated.name
    except OSError:
        return None


def read_lock(lock_path: Path) -> dict | None:
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def acquire_lock(
    lock_path: Path, stale_seconds: int = LOCK_STALE_SECONDS
) -> tuple[bool, str]:
    """Try to claim the job lock.

    Returns (held_by_us, reason). If another healthy run holds the lock, we
    skip instead of stacking (Chapter 9's golden rule). If the lock is stale,
    we take it over and say so.
    """
    existing = read_lock(lock_path)
    if existing is not None:
        try:
            age = time.time() - float(existing.get("ts", 0))
        except (TypeError, ValueError):
            age = -1
        if 0 <= age < stale_seconds:
            pid = existing.get("pid", "?")
            return False, f"another run (pid {pid}) is still active; skipping"
        # Stale lock: the previous run probably crashed without cleanup.
    json.dump(
        {"pid": os.getpid(), "ts": time.time(), "started": now_utc()},
        open(lock_path, "w", encoding="utf-8"),
    )
    if existing is not None:
        return True, "took over a stale lock (previous run likely died)"
    return True, "lock acquired"


def release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except OSError:
        pass


def call_chat(
    base_url: str,
    model: str,
    messages: list[dict],
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> str:
    """POST to /chat/completions with retries + backoff. Returns reply text."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = json.dumps(
        {"model": model, "messages": messages, "stream": False}
    ).encode("utf-8")
    attempt = 0
    backoff = 2
    last_error = ""
    while attempt < max(1, retries):
        attempt += 1
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8", errors="replace"))
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("empty or non-text response from endpoint")
            return content
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError,
                KeyError, IndexError) as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
    raise RuntimeError(f"chat request failed after {attempt} attempt(s): {last_error}")


def build_messages(prompt: str, input_text: str | None, system: str | None) -> list[dict]:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    if input_text:
        msgs.append({"role": "user", "content": f"{prompt}\n\n--- INPUT ---\n{input_text}"})
    else:
        msgs.append({"role": "user", "content": prompt})
    return msgs


def read_input_text(input_file: str | None) -> str | None:
    if not input_file:
        return None
    path = Path(input_file)
    if not path.is_file():
        raise FileNotFoundError(f"input file not found: {input_file}")
    data = path.read_text(encoding="utf-8", errors="replace").strip()
    return data or None  # empty file counts as "nothing to do"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one scheduled AI job against a local OpenAI-compatible endpoint."
    )
    parser.add_argument("--base-url", default=os.environ.get("AI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.environ.get("AI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--prompt", required=True, help="the instruction for the model")
    parser.add_argument("--input-file", help="optional text/markdown file pasted after the prompt")
    parser.add_argument("--system", help="optional system prompt")
    parser.add_argument("--out-dir", default="logs")
    parser.add_argument("--job-name", default="ai-job")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--force", action="store_true", help="run even if another run looks active")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"{args.job_name}.log"
    lock_path = out_dir / f"{args.job_name}.lock"

    # Guardrail 1: don't let the log grow forever.
    rotated = rotate_log_if_big(log_path)

    held, reason = acquire_lock(lock_path)
    if not held and args.force:
        held, reason = True, "forced run (lock overridden)"
        json.dump(
            {"pid": os.getpid(), "ts": time.time(), "started": now_utc()},
            open(lock_path, "w", encoding="utf-8"),
        )
    if not held:
        append_log(log_path, "SKIPPED", reason)
        print(reason)
        return 0

    try:
        try:
            input_text = read_input_text(args.input_file)
        except FileNotFoundError as exc:
            append_log(log_path, "FAILED", f"bad input file: {exc}")
            print(f"error: {exc}", file=sys.stderr)
            return 2

        if rotated:
            append_log(log_path, "OK", f"log rotated to {rotated}")
        append_log(log_path, "NOTE", reason)
        append_log(log_path, "START", f"job '{args.job_name}' started; attempts allowed: {args.retries}")

        prompt_chars = len(args.prompt) + (len(input_text or ""))
        if args.input_file and input_text is None:
            append_log(log_path, "OK", "nothing to do: input file was empty; skipping politely")
            print("nothing to do: input file was empty; skipping politely")
            return 0

        prompt_chars = len(args.prompt) + (len(input_text or ""))
        try:
            reply = call_chat(
                args.base_url, args.model,
                build_messages(args.prompt, input_text, args.system),
                timeout=args.timeout, retries=args.retries,
            )
        except RuntimeError as exc:
            append_log(log_path, "FAILED", f"model call error: {exc}")
            print(f"error: {exc}", file=sys.stderr)
            return 1

        cap = MAX_RESPONSE_CHARS
        if len(reply) > cap:
            reply = reply[:cap] + "\n\n[TRUNCATED: response exceeded the size cap]"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_file = out_dir / f"{args.job_name}-{stamp}.md"
        try:
            out_file.write_text(reply, encoding="utf-8")
        except OSError as exc:
            append_log(log_path, "FAILED", f"could not write output: {exc}")
            return 1
        append_log(log_path, "DONE", f"success; prompt {prompt_chars} chars, reply {len(reply)} chars -> {out_file.name}")
        print(str(out_file))
        return 0
    finally:
        release_lock(lock_path)


if __name__ == "__main__":
    sys.exit(main())
