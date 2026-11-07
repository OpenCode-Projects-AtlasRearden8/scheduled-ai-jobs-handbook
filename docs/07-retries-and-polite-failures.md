# 07 · Retries and polite failures

Networks hiccup. Ollama reboots. A model server takes forty seconds to load
a big model and your job timed out at twenty. None of that means "give up
on today's digest" — it means *try again, gently, then fail with dignity*.

## The retry sandwich

When `ai_job.py` calls a flaky endpoint, here's what actually happens:

1. **Try** — one POST to `/chat/completions` with your timeout attached.
2. **If it fails** — disconnects, timeouts, HTTP 500-class errors, empty
   responses — sleep 2s, then 4s, then 8s (doubling, capped at 30s).
3. **After N attempts** — give up, log one clear `FAILED ... model call
   error: ...` line, leave exit code 1.

```bash
python3 scripts/ai_job.py \
  --base-url http://127.0.0.1:11434/v1 \
  --prompt "Digest today's notes" \
  --input-file my-notes.md \
  --retries 3 --timeout 120
```

Defaults: `--retries 3` attempts, `--timeout 120` seconds each. Backoff
starts at 2 seconds.

## Which errors to retry (and which *not* to)

- **Retry**: connection refused/reset, timeouts, DNS blips, 500-class HTTP
  errors, empty/garbled responses. These are *maybe it just passed*.
- **Don't retry**: HTTP 4xx-class errors that mean *your request itself is
  bad* — a bad model name, malformed request. Retrying a broken prompt six
  times is just a slower way to fail.

`ai_job.py` currently retries everything failing above the application
layer; given 4xx are commonly "bad model name," check the model name first
in your `FAILED` line before assuming infrastructure. Quick check:

```bash
curl http://127.0.0.1:11434/v1/models      # what does it actually have?
```

## Timeouts: the quarantine for slow endpoints

The model didn't fail; the model is *loading*. Either way, at 7:05 you care
less about why than when it stops. `--timeout` sets the per-request
deadline: bigger models — the 70B-class local models — are slow. Having a
timeout is why *hung* is a state your job exits from, not a state it lives
in.

| Model class | Suggested `--timeout` |
| --- | --- |
| 1–3B (llama3.2, phi3) | 60s |
| 7–8B | 120s |
| 13–14B | 180–300s |
| 70B-class on modest hardware | 600s — or reconsider for real-time-ish jobs |

## Failing politely: what "polite" means for a scheduled job

How failure behaves determines whether a job earns trust or quietly gets
deleted by someone tired of false alarms. Rules the scripts here follow:

1. **Exit codes are promises.** 0 healthy, 1 real failure, 2 bad input.
   Your `.cmd`/`.sh` wrappers, scheduler conditions, and any mailers can
   branch on them.
2. **The failure message names the layer.** "model call error: HTTP Error
   500 after 3 attempts" is friendlier than a traceback — it's the *if you
   read one sentence, this one*.
3. **Skip is not fail.** An empty-notes digest week logs `[OK] ... nothing
   to digest` and exits 0. Too much alarm fatigue is how people ignore
   real failures.
4. **One line of truth.** A failing retry doesn't spam the log; the
   attempts live in memory, the log gets one failure record.

## Retries on a schedule are different from retries in a session

In a chat, you retry by re-typing. On a clock, *the next run is the
retry*, which changes the calculus:

- **One job's failure is recoverable by the next tick.** A daily digest
  missing Tuesday is annoying; a *crashed* job that grinds forever is a
  bigger problem (Chapter 8).
- **That's why `--retries` stays modest.** 3 attempts across ~30 seconds of
  backoff is a *flaky-hiccup* catch; the daily rhythm itself is your deep
  retry. Big retries on tight schedules stack (the classic cron-job
  overlap), which Chapter 9's locks exist for.

## The alerting question

Polite failure quietly backstops one gap: *nobody's watching at 7 AM*. The
generous rule is a building rule:

- **First level:** the humble log. Check it at your weekly review.
- **Second level:** make the failure *surface* once a week — the watchdog
  (Chapter 9) runs on a schedule, summarizes fails from logs' recent
  window, and exits 2 so your wrapper script can say "email me" or
  "notification."

A `notify-if-failed.cmd` pattern:

```bat
cd /d C:\scheduled-ai-jobs
C:\Python313\python.exe scripts\watchdog.py --job-dir logs --failure-window-hours 24
if errorlevel 2 echo AI jobs had findings on %date% >> logs\alerter.log
```

(Who gets emailed is your infrastructure; until you wire a mailer, "you
watching the logs" *is* the alert — which is fine if the watchdog runs on a
schedule and its findings land somewhere you look weekly.)

## The one test that matters

`tests/run_tests.py` exercises both sides: a mock endpoint that fails the
first 2 requests (`MOCK_FAIL_FIRST=2`) → the job succeeds on the 3rd try;
a persistently failing one (`MOCK_FAIL=1`) → the job logs one FAILED line
and exits 1. If you wrap `ai_job.py` with your own retry or alerting
layer, write those two tests first. They're the whole contract.
