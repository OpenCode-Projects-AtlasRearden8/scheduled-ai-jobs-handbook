# 06 · Logging: knowing what actually happened

A scheduled job you can't inspect is a rumor. Logging is how the rumor
becomes a record — and it matters far more for scheduled AI jobs than for
ordinary ones, because the output is text nobody wanted to check *before*
it mattered.

The scripts in this repo all follow the same log discipline. Here's what it
is and why.

## The one-line-per-run log

Every job writes one line per event to `logs/<job-name>.log`:

```
2026-11-07T06:47:02Z [NOTE] lock acquired
2026-11-07T06:47:02Z [START] job 'morning-digest' started from notes.md (1240 chars)
2026-11-07T06:47:09Z [DONE] success; prompt 1513 chars, reply 708 chars -> morning-digest-2026-11-07.md
```

Five habits make these lines worth having:

1. **UTC timestamp, ISO-shaped.** `YYYY-MM-DDTHH:MM:SSZ`. One timezone, no
   ambiguity at 7:14 AM when the wall clock changed on Sunday.
2. **A small status word in brackets** — `START`, `DONE`, `OK`, `FAILED`,
   `SKIPPED`, `NOTE`. Grep-able by a human or by the watchdog
   (`grep "\[FAILED\]" logs/*.log` answers "is anything failing?" in a
   second).
3. **The log records outcomes and sizes, never contents.** Notice the line
   says *reply 708 chars*, not the reply itself. Two reasons: your notes
   may be private, and logs have poor security habits. Prompt and reply
   live in the dated output files; the log just points at them.
4. **One line, one event, no stack traces by default.** Runaway-error
   dumps are Chapter 8's problem; one calm line per run is Chapter 6's.
5. **Append-only.** The next run never rewrites history. Debugging a job is
   archaeology; you need the layers.

## What to log for an AI job, specifically

An AI job has two failure families, and the log should let you tell them
apart at a glance:

- **Plumbing failures** — endpoint down, timeout, HTTP 500. These live in
  the `FAILED` line's message ("model call error: HTTP Error 500..."). They
  mean: *the job didn't run today* — retry or fix infra.
- **Bad-output days** — endpoint fine, reply bland or wrong. The log can't
  catch quality (only a human reads it), but the char counts in `DONE` give
  one useful signal: a reply four times larger than usual is a model that
  decided to write an essay.

## Rotating: no log grows forever

Left alone, a log a misbehaving job spams is a runaway job wearing a hat.
`ai_job.py` rotates a log past 5 MB into a timestamped side file before
appending — plus the watchdog (Chapter 9) reports and prunes oversized
logs on a schedule:

```bash
python3 scripts/watchdog.py --job-dir logs           # report only
python3 scripts/watchdog.py --job-dir logs --prune   # clean oversized
```

Log math worth knowing: a 100-line/month log will never rotate. A job
writing 5 lines *per retry attempt* chews through 5 MB in a few weeks.
Rotation isn't bureaucracy; it's the alarm bell itself.

## From cron's mouth vs the job's mouth

Two logs are better than one:

- The **job log** (`logs/<job>.log`) is the *content* — did it run, what
  happened inside. Written by the job itself.
- The **scheduler log** is the *heartbeat* — did the scheduler even fire it.

Chapter 3 shows the scheduler-side line:

```cron
0 7 * * *  $HOME/scheduled-ai-jobs/jobs/daily-digest.sh >> $HOME/scheduled-ai-jobs/logs/cron.log 2>&1
```

The diagnosis flows naturally:

| Symptom | Suspect |
| --- | --- |
| Nothing in cron.log, nothing in job log | The scheduler didn't fire the job at all |
| cron.log has output, job log doesn't | The job crashed before writing a log line (wrong path to python, etc.) |
| Job log shows START but no DONE | The job died mid-run (timeout, machine shut down) |
| Job log shows `[FAILED]` with HTTP errors | Endpoint/model trouble |
| Job log shows `[DONE]` but output looks wrong | A bad-output day (quality — your eyes) |

`START`-with-no-`DONE` is worth its own emphasis: it's the log entry for "a
job was taken halfway" — exactly what a stale lock in Chapter 9 catches.

## The smoke test

Every scheduling chapter here ends the same way: run the job *by hand*
once, and then run it from the scheduler once, then read the log. It's the
non-negotiable onboarding step:

1. `python3 scripts/ai_job.py --prompt "say hello" --out-dir logs` — manual
   run; expect exit code 0 and a fresh DONE line.
2. Fire it from the scheduler with an imminent trigger (Chapter 2's
   `schtasks /Run`, or a temporary `*/2 * * * *` cron line) then remove the
   temporary trigger.
3. Read the log. If it says `[DONE]`, the schedule is honest.
