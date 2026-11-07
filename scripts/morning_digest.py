#!/usr/bin/env python3
"""The morning digest: one scheduled job that reads your notes and asks a
local model for a short, friendly summary you'd actually read over coffee.

Pattern (from Chapter 5 of the handbook):
  1. collect yesterday's notes (here: one markdown file, newest lines win)
  2. bail out gracefully if there's nothing new — never run on junk
  3. ask the local model for a digest with a fixed shape
  4. save the digest next to the job log, ready to read

Tested against scripts/mock_ai_server.py — see tests/run_tests.py.
Stdlib only, no API keys. The model runs on your machine (or wherever you
point --base-url); your notes never have to leave the house.
"""

import argparse
import datetime
import os
import sys
from pathlib import Path

# Import the shared plumbing from ai_job (same folder by design).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ai_job import (  # noqa: E402
    build_messages,
    call_chat,
    append_log,
    acquire_lock,
    release_lock,
    rotate_log_if_big,
)

DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
DIGEST_SYSTEM = (
    "You are a helpful assistant writing a short briefing. "
    "Use plain language. Never invent facts that are not in the notes. "
    "If the notes are trivial, say so in one sentence."
)
DIGEST_PROMPT = (
    "Turn the notes below into a short morning digest with exactly these "
    "sections: 'Top priorities' (max 3 bullets), 'Quick wins' (max 3 bullets), "
    "'Worth a look' (anything interesting, max 3 bullets). "
    "If the notes are empty or trivial, reply with one sentence saying so. "
    "Do not add sections. Do not pad. Keep it under 150 words."
)
NOTHING_SENTINEL = "NO-DIGEST"


def nothing_to_digest(reason: str) -> str:
    return f"Nothing to digest today: {reason}."


def collect_notes(notes_path: Path) -> str | None:
    """Read the notes file; return None if there's nothing worth digesting."""
    if not notes_path.is_file():
        return None
    text = notes_path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None
    # Ignore notes files that contain only headings/whitespace.
    meaningful = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    return text if meaningful else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="generate a morning digest from your notes")
    parser.add_argument("--notes-file", required=True, help="markdown/text file with today's notes")
    parser.add_argument("--base-url", default=os.environ.get("AI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.environ.get("AI_MODEL", "llama3.2"))
    parser.add_argument("--out-dir", default="logs")
    parser.add_argument("--job-name", default="morning-digest")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"{args.job_name}.log"
    lock_path = out_dir / f"{args.job_name}.lock"
    rotate_log_if_big(log_path)

    held, reason = acquire_lock(lock_path)
    if not held and not args.force:
        append_log(log_path, "SKIPPED", reason)
        print(reason)
        return 0  # a skipped digest is not a failure

    try:
        notes = collect_notes(Path(args.notes_file))
        if notes is None:
            digest = nothing_to_digest(f"{args.notes_file} is missing or empty")
            append_log(log_path, "OK", "skipped: no meaningful notes; wrote placeholder digest")
        else:
            prompt = f"{DIGEST_PROMPT}\n\n--- NOTES ({args.notes_file}) ---\n{notes}"
            append_log(log_path, "START", f"digest job started from {args.notes_file} ({len(notes)} chars)")
            try:
                digest = call_chat(
                    args.base_url,
                    args.model,
                    build_messages(prompt, None, DIGEST_SYSTEM),
                    timeout=args.timeout,
                    retries=args.retries,
                )
            except RuntimeError as exc:
                append_log(log_path, "FAILED", f"model call error: {exc}")
                print(f"error: {exc}", file=sys.stderr)
                return 1

        today = datetime.date.today().strftime("%Y-%m-%d")
        digest_path = out_dir / f"{args.job_name}-{today}.md"
        header = (
            f"# Morning digest — {today}\n\n"
            f"_Source: `{args.notes_file}` | Model: `{args.model}` | "
            f"Endpoint: local ({args.base_url})_\n\n---\n\n"
        )
        digest_path.write_text(header + digest + "\n", encoding="utf-8")
        append_log(log_path, "DONE", f"digest written -> {digest_path.name}")
        print(str(digest_path))
        return 0
    finally:
        release_lock(lock_path)


if __name__ == "__main__":
    sys.exit(main())
