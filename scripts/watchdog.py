#!/usr/bin/env python3
"""A quiet watchdog for your scheduled AI jobs (Chapter 9 of the handbook).

Scheduled jobs are like houseplants: fine for weeks, then suddenly a crisis,
and nobody knew because nobody was looking. This script looks.

It surveys a job directory and reports, with human words:
  * log files that grew suspiciously big (runaway-ish)
  * lock files that are still "held" from long ago (a job that died mid-run,
    or one that's genuinely still going — it says which)
  * recent FAILED lines in the logs (a job that's failing nightly)

By default it only REPORTS and exits with a code your scheduler can detect:
  0 = all quiet      2 = something worth a look      3 = nothing found at all

Optional actions (scoped to the job directory you point it at):
  --prune        rename oversized logs to NAME.log.oversized-<stamp>
  --clean-locks  delete lock files that are older than the staleness cutoff

Stdlib only. It never deletes your outputs or digests — only reports/prunes
the specific oversized artifacts you point it at.
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

DEFAULT_MAX_LOG_BYTES = 5 * 1024 * 1024
DEFAULT_STALE_LOCK_SECONDS = 3 * 60 * 60
TAIL_LINES = 200


def human_size(n: int) -> str:
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.0f} {unit}" if unit == "bytes" else f"{n:,.1f} {unit}"
        n /= 1024
    return f"{n:,.1f} GB"


def count_recent_failures(log_path: Path, look_back_seconds: int) -> int:
    """Count FAILED lines in the tail of the log that happened recently."""
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-TAIL_LINES:]
    except OSError:
        return 0
    cutoff = time.time() - look_back_seconds
    recent = 0
    for line in lines:
        if " [FAILED] " not in line:
            continue
        # Log lines start with "YYYY-MM-DDTHH:MM:SSZ".
        try:
            stamp = datetime.strptime(line[:20].rstrip("Z"), "%Y-%m-%dT%H:%M:%S")
            if time.mktime(stamp.timetuple()) >= cutoff:
                recent += 1
        except ValueError:
            continue
    return recent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="check up on scheduled AI jobs")
    parser.add_argument("--job-dir", required=True, help="directory holding .log/.lock files")
    parser.add_argument("--max-log-bytes", type=int, default=DEFAULT_MAX_LOG_BYTES)
    parser.add_argument("--stale-lock-seconds", type=int, default=DEFAULT_STALE_LOCK_SECONDS)
    parser.add_argument("--failure-window-hours", type=int, default=24)
    parser.add_argument("--prune", action="store_true", help="rename oversized logs")
    parser.add_argument("--clean-locks", action="store_true", help="delete stale lock files")
    args = parser.parse_args(argv)

    job_dir = Path(args.job_dir)
    if not job_dir.is_dir():
        print(f"nothing found: {args.job_dir} is not a directory")
        return 3

    logs = sorted(job_dir.glob("*.log"))
    locks = sorted(job_dir.glob("*.lock"))
    if not logs and not locks:
        print(f"nothing found: no logs or locks in {args.job_dir}")
        return 3

    findings: list[str] = []
    acted: list[str] = []

    for log in logs:
        try:
            size = log.stat().st_size
        except OSError:
            continue
        if size > args.max_log_bytes:
            findings.append(f"oversized log: {log.name} is {human_size(size)} > {human_size(args.max_log_bytes)}")
            if args.prune:
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                target = log.with_name(f"{log.name}.oversized-{stamp}")
                try:
                    log.rename(target)
                    acted.append(f"pruned {log.name} -> {target.name}")
                except OSError as exc:
                    findings.append(f"could not prune {log.name}: {exc}")

        fails = count_recent_failures(log, args.failure_window_hours * 3600)
        if fails:
            findings.append(
                f"recent failures: {log.name} shows {fails} FAILED entr"
                f"{'y' if fails == 1 else 'ies'} in the last {args.failure_window_hours}h"
            )

    for lock in locks:
        try:
            age = time.time() - lock.stat().st_mtime
        except OSError:
            continue
        if age > args.stale_lock_seconds:
            findings.append(
                f"stale lock: {lock.name} untouched for {age / 3600:.1f} hours "
                f"— the job probably died mid-run"
            )
            if args.clean_locks:
                try:
                    lock.unlink()
                    acted.append(f"cleaned stale lock {lock.name}")
                except OSError as exc:
                    findings.append(f"could not clean {lock.name}: {exc}")

    if acted:
        for a in acted:
            print(f"action: {a}")
    if findings:
        for f in findings:
            print(f"findings: {f}")
        return 2
    print("all quiet: logs are a sane size, no stale locks, no recent failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
