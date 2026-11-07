# 08 · Stopping runaway jobs

This is the chapter that keeps scheduled AI jobs a convenience instead of a
cautionary tale. Runaway has four faces here:

1. **The double-run** — the 7:00 digest and the 7:05 *retried* digest both
   running, calling the model twice, writing over each other.
2. **The runaway log** — an error loop appending megabytes a day until your
   disk notices.
3. **The long-running** — a job that hangs forever and never releases its
   lock, so every later run skips and the job quietly stops producing
   anything.
4. **The model essayist** — the endpoint answers, but replies keep growing
   until "a digest" is 40 pages.

Four guards cover them, and this repo's scripts ship with each one.

## Guard 1: Locks — no stacking

A **lock file** is the saved game of a job. Before running, `ai_job.py`
writes `logs/<job-name>.lock` containing its PID and start time. Another
instance finding that file, *fresh*, skips instead of starting:

```
2026-11-07T07:00:32Z [SKIPPED] another run (pid 14221) is still active; skipping
```

Skipping is exit code 0 — a **healthy outcome**, not a hidden failure. The
double-run is normal in messy lives (scheduler retried, you kicked it
manually, two timezones changed on a laptop) and skipping is the correct,
calm response.

Why a file and not "task scheduler handles it"? Because locks survive the
scheduler changing, the OS changing, the job moving — and because the
scheduler only knows about *its* overlaps, not yours (manual rerun mid-
flight). A lock file is a tiny promise between *every* copies of the job.

## Guard 2: Stale locks — don't let a crash make the job miss forever

The failure mode hiding in guard 1: the job crashes hard (power flicker at
7:01), leaves a lock, and *every future run skips forever* — the job is
now dead but unless you look you never know.

So locks go stale on purpose: `ai_job.py` treats a lock older than 3 hours
(`LOCK_STALE_SECONDS`) as abandoned, takes it over, and says so in the log:

```
2026-11-08T07:00:01Z [NOTE] took over a stale lock (previous run likely died)
```

Make sure your staleness window comfortably exceeds your job's normal
runtime, including its possible timeout (`--timeout 120` each × retries
means a slow model can legitimately run for ~10 minutes). 3 hours is a
sane default, tune it for your job.

For clean-up after edits/crashes mid-test? The watchdog does this on
schedule too: `python3 scripts/watchdog.py --job-dir logs --clean-locks`
sweeps anything older than your staleness window. Or as a one-off on its
own machine:

```bash
rm logs/ai-job.lock
```

## Guard 3: Log rotation + caps — the disk never fills

Three caps ride along in the scripts, all adjustable:

| Guard | Default | Where |
| --- | --- | --- |
| Log rotation | 5 MB → renamed to `<job>.log.<timestamp>` | `ai_job.py`, every run |
| Response cap | 50,000 chars → truncated with a note | `ai_job.py` |
| Per-request timeout | 120 s (via `--timeout`) | both scripts |

The response cap is the essayist's. Models do wander — a digest weakly
prompted grows and grows. A cap doesn't make it *good*; it makes it *bound-
ed*: one page max, not forty. Cap generously (don't clip reasonable
summaries) but *think* what your output means — one page, not one novel.

## Guard 4: The watchdog — a job that watches the jobs

`scripts/watchdog.py` is a scheduled job whose whole job is reading other
jobs' logs. Around machine's quiet hours or daily before coffee:

```bash
python3 scripts/watchdog.py --job-dir logs
```

It reports, in plain English, exactly three runaway-ish conditions:

- **Oversized logs**: `chatty.log is 5.3 MB > 5 MB` → suggest `--prune`.
- **Stale locks**: `ai-job.lock untouched for 27.0 hours — the job probably
  died mid-run` → suggest `--clean-locks`.
- **Recent failures**: `ai-job.log shows 3 FAILED entries in the last 24h`
  → fires a `FAILED` grep in Chapter 7's diagnosis, not a duplicate alarm.

Exit codes make it schedulable as *the* alarm:

| Code | Meaning |
| --- | --- |
| 0 | all quiet |
| 2 | findings worth a look (detail printed) |
| 3 | nothing found at all (wrong directory?) |

Daily watchdog + weekly human-glimpse = a feedback loop that catches
anything the automation misses.

## Sizing the runaway risk by endpoint

Local endpoints are the reason runaway costs can't ruin a month. But
risk doesn't *disappear* — it shifts:

| Endpoint | Runaway cost |
| --- | --- |
| Local Ollama / LM Studio / llama.cpp | laptop fans spin; battery dips; some parallel runs slow the machine. Worst case: hours of it. |
| Hosted OpenAI-compatible API (Chapter 4's hosted recipe) | **Money, unbudgeted.** Set provider spend caps before scheduling anything; check that it succeeded with a $0.01 test call. |

If you're asking "does local-first matter?" — it's mostly *this chapter*.
Locally, the worst a runaway digest does is heat your room slightly.

## The 30-second runaway audit

Checklist for any job you're about to schedule:

1. Lock file? (`ai_job.py` — yes.)
2. Stale-lock policy? (3-hour takeover — yes.)
3. Log that can't tattoo itself to your disk? (5 MB rotation — yes.)
4. Reply cap? (`--max-response-chars` guards the essayist — yes.)
5. Per-request timeout? (`--timeout 120` — yes.)
6. A watchdog scheduled somewhere, at least weekly? (Chapter 9's command
   above — your one job.)

Six yeses and the job is hardened against all four runaway faces — safe to
schedule unattended. Run the audit once per job.
