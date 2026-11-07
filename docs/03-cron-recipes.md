# 03 · cron recipes (Linux & Mac)

cron is the Unix alarm clock, and it's three things: `crontab -e` to edit
your alarms, one line per alarm, and `man 5 crontab` when you confuse the
min-hour field. This chapter is the middle one.

## Reading a cron line

```
* * * * *  command to run
│ │ │ │ │
│ │ │ │ └── day of week (0–7, 0 and 7 = Sunday)
│ │ │ └──── month (1–12)
│ │ └────── day of month (1–31)
│ └──────── hour (0–23)
└────────── minute (0–59)
```

| Line | Reads as |
| --- | --- |
| `0 7 * * *` | every day at 07:00 |
| `0 7 * * 1` | Mondays at 07:00 |
| `30 8 1 * *` | the 1st of the month at 08:30 |
| `0 */4 * * *` | every 4 hours, on the hour |
| `@reboot` | once, when the machine boots (good place to start servers) |

## Setup, in three steps

**Step 1 — the job script.** One file, absolute paths throughout:

```bash
#!/bin/bash
# jobs/daily-digest.sh
cd "$HOME/scheduled-ai-jobs"
/usr/bin/python3 scripts/morning_digest.py \
  --base-url http://127.0.0.1:11434/v1 \
  --model llama3.2 \
  --notes-file "$HOME/scheduled-ai-jobs/my-notes.md" \
  --out-dir logs
```

```bash
chmod +x jobs/daily-digest.sh   # make it executable, once
```

**Step 2 — test by hand.** `./jobs/daily-digest.sh`, then read
`logs/morning-digest.log`. cron runs in an almost-empty environment — your
login's PATH, language settings, and aliases don't exist there. That's why
the script uses absolute paths and doesn't trust `python` resolving
correctly.

**Step 3 — schedule it.**

```bash
crontab -e
```

then add:

```cron
# m  h  dom month dow   command
  0  7  *   *     *    $HOME/scheduled-ai-jobs/jobs/daily-digest.sh
```

Done — daily 07:00 digest. `crontab -l` shows what's scheduled;
`crontab -r` deletes it (the retirement plan — know it *before* you need it).
`%` has special meaning in crontab (`new-line`); if a command needs a literal
percent, escape it as `\%`.

## Where output goes

Cron mails you stdout/stderr of your job. Modern systems don't run a mail
daemon, so output silently vanishes. We covered you in another way: the
scripts log to `logs/*.log` — that's your real output. To also keep errors:

```cron
0 7 * * *  $HOME/scheduled-ai-jobs/jobs/daily-digest.sh >> $HOME/scheduled-ai-jobs/logs/cron.log 2>&1
```

## Systemd timers (the modern Linux option)

Systemd timers are what new Linux distros would rather you use: they have a
proper log (`journalctl`), run catch-ups for missed runs, and are nameable.

`~/.config/systemd/user/daily-digest.service`:

```ini
[Unit]
Description=Morning AI digest

[Service]
Type=oneshot
WorkingDirectory=%h/scheduled-ai-jobs
ExecStart=/usr/bin/python3 scripts/morning_digest.py --out-dir logs
```

`~/.config/systemd/user/daily-digest.timer`:

```ini
[Unit]
Description=Run the morning AI digest at 7am

[Timer]
OnCalendar=*-*-* 07:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now daily-digest.timer
systemctl --user list-timers          # see when it fires next
journalctl --user -u daily-digest     # read what happened
```

`Persistent=true` = "run if the machine was asleep at the appointed time" —
a laptop lifesaver. List before-and-afters: `list-timers`, `journalctl`.

For macOS, cron still works exactly as shown; launchd is Apple's native
alternative, but cron is friendlier for one-line jobs, so this chapter stays
with cron.

## Ollama, on the clock

cron won't start Ollama for you. Two reliable options:

1. Most installs start Ollama at login as a desktop app. On a
   headless/server box, install the Ollama systemd service so it starts at
   boot; the installer's Linux instructions cover this and the unit is
   typically `ollama.service`.
2. Belt and suspenders: a tiny test at the top of the job script:

```bash
curl -s --max-time 5 http://127.0.0.1:11434/v1/models >/dev/null \
  || systemctl --user start ollama \
  || echo "OLLAMA DOWN" >> logs/morning-digest.log
```

(Should ollama be shipped as a systemd unit named `ollama.service`, adjust
the name.)

## Recipes

```cron
# morning digest          — daily 7am
0 7 * * *  $HOME/scheduled-ai-jobs/jobs/daily-digest.sh

# weekly review           — Mondays 8:30am
30 8 * * 1  $HOME/scheduled-ai-jobs/jobs/weekly-review.sh

# monthly cleanup report  — the 1st, 9am
0 9 1 * *  $HOME/scheduled-ai-jobs/jobs/monthly-report.sh

# watchdog every 6 hours  — cheap insurance (chapter 9)
0 */6 * * *  /usr/bin/python3 $HOME/scheduled-ai-jobs/scripts/watchdog.py --job-dir $HOME/scheduled-ai-jobs/logs
```

## Troubleshooting checklist

1. **`crontab -l` says your line is there but nothing runs** — did you
   `chmod +x` the script? Run it by hand first.
2. **Runs by hand, empty environment** — absolute paths.
3. **Writes files nowhere** — `cd` into the project dir in the script (or
   use `--out-dir` with an absolute path).
4. **Script runs, model call fails** — endpoint down; see the curl probe
   above.
5. **Nothing in the log, nothing anywhere** — check the system's cron log:
   Linux `journalctl -u cron` or `grep CRON /var/log/syslog`; macOS
   `log show --predicate 'process == "cron"' --last 1h`.
