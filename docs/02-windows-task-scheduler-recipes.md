# 02 · Windows Task Scheduler recipes

Task Scheduler is Windows' built-in alarm clock for programs — the same thing
that runs Windows Update while you sleep. It's older-looking and a bit
buried, but it never needs installing, and it can wake the computer up to do
your job.

## The five-minute setup (by hand)

Say you want a morning digest at 7:00 AM daily, with Ollama running on your
machine.

**Step 1 — make a job script.** A `.bat` file that runs one thing, so if the
job changes you edit one file:

```bat
:: jobs\daily-digest.cmd
cd /d C:\scheduled-ai-jobs
C:\Python313\python.exe scripts\morning_digest.py ^
  --base-url http://127.0.0.1:11434/v1 ^
  --model llama3.2 ^
  --notes-file C:\scheduled-ai-jobs\my-notes.md ^
  --out-dir logs
```

`cd /d` matters: scheduled jobs start in a different folder than you'd
expect, so absolute paths or an explicit `cd` save you a mystifying "file
not found."

**Step 2 — run it once by double-clicking.** Manual test first. Watch the
`logs\` folder for the digest file and the `.log` file. Only when this works
do we schedule it — never automate something untested.

**Step 3 — create the task.**

1. Press the Start button, type **Task Scheduler**, open it.
2. In the right panel: **Create Basic Task...**
3. **Name**: `Morning AI digest` — names you'll recognize in a list later.
4. **Trigger**: Daily. Set the time you'd actually read it (7:00 AM).
5. **Action**: Start a program. **Program/script**:
   `C:\scheduled-ai-jobs\jobs\daily-digest.cmd`
6. **Start in**: `C:\scheduled-ai-jobs` (belt and suspenders with `cd /d`).
7. Finish. Find it in the *Task Scheduler Library* in the middle panel.

**Step 4 — the two checkboxes that matter.** Double-click the task:

- **General** tab: set the job to *"Run whether user is logged on or not."*
  Otherwise the job misses every morning you haven't logged in yet.
- **Conditions** tab: check **"Wake the computer to run this task"** if your
  PC sleeps at 7 AM. Untick "Start the task only if the computer is on AC
  power" on a desktop; keep it ticked on a laptop you don't want drained.
- **Settings** tab: *"Do not start a new instance"* — Task Scheduler's
  version of our lock file (Chapter 9 explains why double-runs happen).

**One Ollama-specific catch:** Task Scheduler runs under *your* account, and
Ollama has to be running for the job to reach it. The simplest reliable
route: install Ollama so it starts with Windows (the installer's default),
then it's there before 7 AM. Alternatively, add `ollama serve` as the first
line of your `.cmd`, or make Ollama's startup its own scheduled task.

## The same task from the command line

For any templating/p2p replication, `schtasks` does what the GUI does:

```bat
schtasks /Create /tn "Morning AI digest" ^
  /tr "C:\scheduled-ai-jobs\jobs\daily-digest.cmd" ^
  /sc daily /st 07:00 ^
  /ru "%USERNAME%" /rl limited ^
  /np
```

- `/sc daily /st 07:00` — daily at 7:00 AM
- `/np` — no password prompt (runs as the current user)
- `schtasks /Run /tn "Morning AI digest"` — fire it right now by hand
- `schtasks /Query /tn "Morning AI digest" /v` — last run result; `0x0` means
  success, anything else is chapter 6's territory
- `schtasks /Delete /tn "Morning AI digest" /f` — retirement plan before you
  schedule anything, know how to cancel it

## The once-a-week task

Same flow, trigger = Weekly. In `schtasks` form:

```bat
schtasks /Create /tn "Weekly AI review" ^
  /tr "C:\scheduled-ai-jobs\jobs\weekly-review.cmd" ^
  /sc weekly /d MON /st 08:30 /np
```

## Recipes by interval

| You want | Trigger type | In `schtasks` |
| --- | --- | --- |
| Every morning | Daily | `/sc daily /st 07:00` |
| Monday mornings | Weekly | `/sc weekly /d MON /st 08:00` |
| First of the month | Monthly | `/sc monthly /d 1 /st 09:00` |
| Few hours apart on a workday | Multiple tasks | create a second task with another name/time (simplest) |
| Catch-up after missed run | Settings tab | "Run task as soon as possible after a scheduled start is missed" |

## Troubleshooting, in order of likelihood

1. **Last Run Result is `0x1` or `0x2`, file not found** — wrong paths. The
   `cd /d` line in your `.cmd`, plus **Start in**, fixes most of these.
2. **Python not found** — use the full path
   (`C:\Python313\python.exe`), not `python`. Scheduler's PATH isn't yours.
3. **Job runs but the model call fails** — Ollama was asleep. Make sure it
   launches at startup (Chapter 9 covers endpoints in detail).
4. **Job runs twice** — you copied the task with two names, or missed the
   "Do not start a new instance" setting. If a `.lock` file lingers in your
   `logs\` folder after a crash, run the watchdog (Chapter 9):
   `python scripts\watchdog.py --job-dir logs --clean-locks`
5. **You can't tell what happened at all** — that's what the logging is
   for. Chapter 6, and your `.cmd` should look like:

```bat
cd /d C:\scheduled-ai-jobs
C:\Python313\python.exe scripts\ai_job.py --prompt "say hello" ^
  --out-dir logs --job-name smoke-test
echo exit code: %errorlevel% >> logs\smoke-test.log
```

## Laptop note

Laptops win the sleep battle. If "wake the computer" doesn't work for you,
flip it around: run the digest at the moment *you arrive*, triggered by
log-on instead of a fixed time (`/sc onlogon`, or Trigger → "At log on").
A digest at 7:41 when you sat down beats a perfect 7:00 that never ran.
