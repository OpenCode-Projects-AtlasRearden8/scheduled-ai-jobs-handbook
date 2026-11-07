# The Scheduled AI Jobs Handbook

By [Asdale Dynamics, LLC](https://dylanasdale.github.io) — plain-English manuals and practical tools.

You already know AI can do the chore. The problem isn't the chore — it's the
clicking. You type the same prompt every morning. You paste the list into the
little box, you hit reply, you close the tab. That's a job, and jobs can run on
a schedule instead of you.

This handbook shows you how to take the AI chores you already do by hand and
hand them to a scheduler: Windows Task Scheduler, cron, or GitHub Actions. It
covers the judgment calls (what belongs on a schedule, what doesn't), the exact
recipes, and the guardrails that keep a scheduled job from becoming a runaway
job. Everything is designed to run against **local, OpenAI-compatible
endpoints** — including Ollama — with no API keys, so your private data never
leaves your machine.

It's written the way Dylan Asdale explains AI in *The Massive AI Manual*: like
a friend would. Step by step, never condescending, no jargon left unexplained.

## What's in here

| Path | What it is |
| --- | --- |
| `docs/` | The handbook itself — start at `docs/00-start-here.md` |
| `scripts/` | Tested, working recipes: a local AI job runner, a digest generator, a watchdog, and a mock server for testing |
| `tests/` | Test suite that runs the real scripts against the included mock AI server |
| `site/` | The handbook as a plain static website (no build server needed) |

## The chapters

1. [Start here](docs/00-start-here.md) — how to use this book
2. [Scheduled job or one-off chat?](docs/01-scheduled-job-or-one-off-chat.md) — the judgment call
3. [Windows Task Scheduler recipes](docs/02-windows-task-scheduler-recipes.md)
4. [cron recipes (Linux & Mac)](docs/03-cron-recipes.md)
5. [GitHub Actions for repo chores](docs/04-github-actions-chore-crew.md)
6. [Morning digest & weekly summary patterns](docs/05-digest-patterns.md)
7. [Logging: knowing what actually happened](docs/06-logging.md)
8. [Retries and polite failures](docs/07-retries-and-polite-failures.md)
9. [Stopping runaway jobs](docs/08-stopping-runaway-jobs.md)
10. [Local endpoints & Ollama](docs/09-local-endpoints.md)
11. [Recipe cards](docs/10-recipe-cards.md) — quick copy-paste recipes

## Quick start (90 seconds)

Test scripts against the included mock server — no Ollama required:

```bash
python3 tests/run_tests.py
```

Run a digest for real, assuming Ollama on your own machine:

```bash
python3 scripts/mock_ai_server.py &        # or: have Ollama running on 11434
python3 scripts/ai_job.py --base-url http://127.0.0.1:11434/v1 \
  --model llama3.2 --prompt "Summarize my notes file" \
  --input-file examples/notes-sample.md --out-dir logs/
```

## Works against local, no keys

Every script in this handbook talks plain HTTP to an OpenAI-compatible
endpoint. Ollama (`http://127.0.0.1:11434/v1`), LM Studio
(`http://127.0.0.1:1234/v1`), llama.cpp's server, or anything else speaking the
same dialect. No API keys. No telemetry. Your notes stay in your house.

## Related books by Asdale Dynamics

- **automation-friend-guide** — the mindset: when to automate at all
- **everyday-batch-file-automation-handbook** — batch files and shell loops, no AI
- **this handbook** — AI chores, on a clock

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Asdale Dynamics, LLC.
