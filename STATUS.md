# STATUS.md — The Scheduled AI Jobs Handbook

Last verified: 2026-11-07

## What was built

A beginner-friendly, plain-English manual for moving recurring AI chores
from "type the same prompt every day" to real schedulers — Windows Task
Scheduler, cron/systemd timers, and GitHub Actions — designed to work
against **local, OpenAI-compatible endpoints** (Ollama first, LM Studio /
llama.cpp also supported) with **no API keys**, so private data stays on the
reader's machine.

**Structure**

- `docs/` — 11 handbook chapters: the scheduled-vs-one-off judgment call,
  Task Scheduler and cron recipes, GitHub Actions for repo chores, morning
  digest / weekly summary patterns, logging, retries and polite failures,
  stopping runaway jobs (locks, rotation, caps, watchdog), local endpoints
  and Ollama, and copy-paste recipe cards.
- `scripts/` — tested, schedulable tools:
  - `ai_job.py` — the general job runner: prompt + optional input file →
    output markdown, with a lock file (no double-runs), stale-lock takeover,
    5 MB log rotation, 50k-char response cap, per-request timeout, retries
    with backoff, and privacy-safe logging (outcomes and char counts, never
    prompt/response contents).
  - `morning_digest.py` — the Chapter 5 digest pattern: reads a notes file,
    politely skips empty/trivial notes (no wasted model calls), writes a
    dated digest file.
  - `watchdog.py` — the Chapter 9 watchdog: flags oversized logs, stale
    locks, and recent FAILED entries; optional `--prune` / `--clean-locks`;
    scheduler-friendly exit codes (0 quiet / 2 findings / 3 nothing found).
  - `mock_ai_server.py` — a stdlib-only OpenAI-compatible mock endpoint
    (with `MOCK_FAIL` / `MOCK_FAIL_FIRST` test switches) so everything can
    be verified without a model, without keys, without the internet.
- `tests/run_tests.py` — 19-test unittest suite covering the job runner
  (success, retries, retry exhaustion, input handling, locks, stale locks,
  forced runs), the digest pattern (normal, empty notes, headings-only
  notes), the watchdog (quiet, oversized+prune, stale locks+clean, recent
  failures, empty dir), and the mock server itself.
- `tools/build_site.py` — stdlib-only markdown-to-HTML site builder.
- `site/` — the handbook as plain static HTML (12 pages + stylesheet,
  linked table of contents, works from a file:// open or any static host).
- `examples/notes-sample.md` — sample notes file for the digest demos.
- `README.md`, `LICENSE` (MIT), `.gitignore`.

## How to run it

```bash
# run the full test suite (no model, no keys needed)
python3 tests/run_tests.py

# build/verify the static site
python3 tools/build_site.py          # writes site/
python3 tools/build_site.py --check  # temp-dir build + link check

# try a digest end-to-end against the mock endpoint
python3 scripts/mock_ai_server.py &   # prints PORT=<n>
python3 scripts/morning_digest.py \
  --base-url http://127.0.0.1:<n>/v1 \
  --notes-file examples/notes-sample.md \
  --out-dir logs

# night-and-day swap: point at real Ollama (no code change)
python3 scripts/morning_digest.py \
  --base-url http://127.0.0.1:11434/v1 \
  --model llama3.2 \
  --notes-file my-notes.md \
  --out-dir logs

# general job runner, digest-free
python3 scripts/ai_job.py --prompt "<your prompt>" \
  --input-file notes.md --out-dir logs --job-name my-job

# the watchdog
python3 scripts/watchdog.py --job-dir logs [--prune|--clean-locks]
```

Scheduling recipes (schtasks lines, crontab lines, systemd timer units,
GitHub Actions YAML) are in `docs/02`, `docs/03`, `docs/04`, and
`docs/10`.

## Verification results (2026-11-07)

- `python3 -m py_compile` on all Python files — clean.
- `python3 tests/run_tests.py` → **19/19 tests pass** (mock server, both
  failure-injection modes, lock/stale-lock/skip semantics, digest outputs,
  watchdog findings/pruning, exit codes).
- Static smoke test: mock server + `morning_digest.py` +
  `watchdog.py` run end-to-end in this environment — digest file produced
  with correct header, watchdog reported "all quiet".
- `python3 tools/build_site.py --check` → 12 pages built in a temp dir,
  zero broken internal links; re-ran the real build into `site/` and
  spot-rendered headings, fences, tables, and lists.
- Scanned docs/scripts for garbled text and stray non-English characters —
  clean.
- No secrets, API keys, or personal data anywhere in the tree; the job
  logs deliberately exclude prompt/response contents.

## Known gaps

- **Windows/macOS specifics are documented, not executed here:** the
  `schtasks` / `.cmd` recipes and `launchd`/macOS notes were written for
  those platforms but this environment is Linux-only, so they're verified
  by review, not by running Task Scheduler.
- **Real-model behavior is assumed, not model-tested here:** the suite
  exercises the full plumbing against the mock endpoint; against real
  Ollama, prompt *quality* (how good `llama3.2` digests actually are) still
  needs a human skim on your hardware.
- **Timezone parsing in the watchdog** parses the log's UTC stamps and
  compares in local time on the detecting machine; useful window defaults
  (24h) make this safe in practice, but absolute-UTC compare would be more
  rigorous.
- `ai_job.py` retries all HTTP errors, including 4xx (documented in
  Chapter 7: check the model name first); a finer-grained retry classifier
  is a fair future improvement.
- The GitHub Actions workflows live in `docs/04` as templates; adding a
  runnable `.github/workflows/` directory was deliberately skipped (this
  handbook repo itself doesn't need its own automation, and nothing here
  is ever pushed — keep it that way per the project's rules).
