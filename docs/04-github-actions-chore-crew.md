# 04 · GitHub Actions for small repo chores

Some AI chores don't belong to your computer — they belong to a *repo*.
Drafting a weekly changelog, summarizing the last week of commits, tidying a
docs index, reviewing a TODO file for stale items. GitHub Actions runs those
on GitHub's clock, in the background, with your machine off.

The catch, up front: on GitHub's own runners, your repo files go wherever
the model runs — which is the cloud. If the chore touches private data, use
the local-first variant at the bottom of this chapter instead.

## Recipe: hosted runner + a model API

A hosted runner has no Ollama, so you need **some** OpenAI-compatible API
and its key. Rules for that, in order of how much they matter:

1. Put the key in **Settings → Secrets and variables → Actions** as a
   secret; never in the workflow file, never in a commit.
2. Set a monthly spend limit on the provider *before* scheduling. A runaway
   monthly job is Chapter 8's nightmare, hosted.
3. Fine for public repo content. Not fine for private docs you'd never want
   on someone else's servers.

`.github/workflows/weekly-changelog.yml`:

```yaml
name: Weekly changelog draft
on:
  schedule:
    - cron: "0 14 * * 1"   # Mondays 14:00 UTC — GitHub reads UTC only
  workflow_dispatch:        # "Run workflow" button for testing by hand

permissions:
  contents: read

jobs:
  changelog:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # full history; the changelog's raw material

      - name: Collect the week's commits
        run: git log --since="7 days ago" --oneline > last-week.txt

      - name: Ask the model for a draft changelog
        env:
          AI_API_KEY: ${{ secrets.AI_API_KEY }}
          AI_BASE_URL: https://api.openai-compatible-provider.example/v1
          AI_MODEL: gpt-4o-mini
        run: |
          python3 - <<'PY'
          import os, sys
          sys.path.insert(0, ".")
          from scripts.ai_job import call_chat

          notes = open("last-week.txt").read()
          reply = call_chat(
              os.environ["AI_BASE_URL"],
              os.environ["AI_MODEL"],
              [
                  {"role": "system",
                   "content": "Write a weekly changelog in Markdown. Use only the supplied commits. Never invent features."},
                  {"role": "user", "content": notes},
              ],
              timeout=120,
              retries=3,
          )
          open("weekly-changelog-draft.md", "w").write(reply)
          print(reply)
          PY

      - name: Save the draft as an artifact
        uses: actions/upload-artifact@v4
        with:
          name: weekly-changelog-draft
          path: weekly-changelog-draft.md
```

That reuses `scripts/ai_job.py`'s `call_chat()` — the same endpoint logic,
retries, and timeout behavior you tested locally. One client, everywhere.

## Recipes by chore

| Chore | Reads | Writes | Cadence |
| --- | --- | --- | --- |
| Weekly changelog draft | `git log` | artifact / PR | Mondays |
| Docs TOC check | `docs/*.md` | report artifact | Daily |
| TODO-file staleness review | `TODO.md` | suggested-edits PR | Weekly |
| Issue-triage *suggestions* | open issues | comment draft | Daily |

Names matter here too: `weekly-changelog.yml` reads better in a list than
`workflows[0].yml`.

## The local-first recipe

If the job should touch private data, don't send it to a hosted runner.
Run a **self-hosted runner** on an always-on machine of yours:

1. **Settings → Actions → Runners → New self-hosted runner** on the repo,
   and follow the install commands GitHub shows. One download, one install,
   one service start.
2. Point the job at your own Ollama and set `runs-on: self-hosted`.

```yaml
jobs:
  digest:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v4
      - run: |
          python3 scripts/morning_digest.py \
            --base-url http://127.0.0.1:11434/v1 \
            --model llama3.2 \
            --notes-file NOTES.md \
            --out-dir logs
      - uses: actions/upload-artifact@v4
        with:
          name: morning-digest
          path: logs/morning-digest*.md
```

One honest warning: a self-hosted runner executes your repo's code as a
full-trust process on that machine. Only attach one to a repo you control,
and don't do it to public repos where anyone can open PRs that run code.

## The quirks to know

- **UTC only.** Actions read cron in UTC. 14:00 UTC is 9:00 AM Eastern, 7:30
  PM in Bangalore. Convert once, write it as a comment, stop converting.
- **Schedules fire from the default branch only.** A workflow file on a dev
  branch is scheduled to do nothing.
- **The clock is best-effort.** On free plans, scheduled runs can slide by
  some minutes (occasionally longer when GitHub is busy). Fine for repo
  chores; wrong tool for anything that must run at a precise minute.
- **`workflow_dispatch` is your debugger.** Add it, run by hand from the
  Actions tab, read the log, and only then trust the schedule.

## Guardrails, Actions-flavored

- Disable the schedule in a month it stops being loved: **Actions tab →
  the workflow → ⋯ → Disable**. Cheaper than debugging an error email
  months later.
- Keep runs lean; Actions stores logs and artifacts with retention limits
  (**Settings → Actions → retention days**), and very chatty jobs eat them.
- For anything writing back to the repo, let the job open a *pull request*
  (e.g. via `peter-evans/create-pull-request`) instead of pushing to
  `main`, so the unattended job always has a human checkpoint.

## When to skip Actions altogether

The job is about *your machine's* files, the model must be local anyway, or
you're the only beings awake at that hour but not on the internet — then
Chapter 2 (Task Scheduler) or Chapter 3 (cron) is simply the smaller tool.
Actions earn their keep for repo chores because the repo already lives
there; don't send local chores on a trip.
