# 00 · Start here

Welcome. You've been using AI for the chores. You ask it every morning to
check something. You paste the same list every Monday and ask for the same
summary. You keep meaning to automate it and never quite do.

This handbook is the "do it" part. In plain English, step by step:

1. **Decide** what gets scheduled and what stays a one-off chat (Chapter 1).
2. **Schedule it** on Windows (Chapter 2), Linux/Mac (Chapter 3), or GitHub
   Actions for repo chores (Chapter 4).
3. **Pick a shape** for the output — a morning digest, a weekly summary
   (Chapter 5).
4. **Arm it** with logs, retries, and watchdogs so it survives the week you
   forget about it (Chapters 6, 7, 8).
5. **Keep it local** — run the model on your own machine so private data
   stays home (Chapter 9).
6. **Steal recipes** (Chapter 10) when you just want the thing.

## What you need

- A computer you keep on at the relevant time (or one that sleeps and wakes
  to run the job — Chapter 2 shows how).
- A local, OpenAI-compatible model endpoint. [Ollama](https://ollama.com) is
  the easiest: install it, `ollama pull llama3.2`, done. LM Studio and
  llama.cpp's server work identically. Chapter 9 explains why "OpenAI-
  compatible" doesn't mean "OpenAI" — it's a dialect, and everyone speaks it.
- Nothing else. No API keys, no accounts, no cloud.

## What you'll build here

The `scripts/` folder in this repo contains tested, ready-to-schedule jobs:

| Script | What it does |
| --- | --- |
| `scripts/ai_job.py` | The general-purpose job runner: takes a prompt (plus an optional input file), runs it with logging, locking, retries, and size caps |
| `scripts/morning_digest.py` | The morning digest pattern from Chapter 5, ready to run |
| `scripts/watchdog.py` | The Chapter 9 watchdog: catches runaway logs, stale locks, and nightly failures |
| `scripts/mock_ai_server.py` | A pretend model endpoint, so you can test everything before trusting it |

Test them any time, no model required:

```bash
python3 tests/run_tests.py
```

Every job script works the same way at one level: prompt in, file out, log
written, lock held while running. Once that pattern clicks, you can schedule
anything.

## The one rule worth tattooing somewhere

**A scheduled job must be safe when two of it run at once, and safe when it
runs during your vacation.** Everything in this book — locks, logs, retries,
caps, watchdogs — flows from that. A job that's only safe when you're
watching isn't scheduled; it's checked in on. We'll make it scheduled.

## How to read this book

In order the first time. After that, chapters are self-contained, so skim the
table of contents and jump to the one you need. Code blocks are meant to be
copied. Nothing here assumes you're a programmer, and nothing here talks down
to you.
