# 10 · Recipe cards

Copy, adjust the three uppercase things, done. Each recipe assumes this
repo sits in its folder (`scheduled-ai-jobs/`) and that a small Ollama
model (`llama3.2`) is pulled (`ollama pull llama3.2`).

**Universal swap:** before trusting *any* schedule, run the job once by
hand with `--base-url` pointed at the mock server to confirm the plumbing
(`python3 scripts/mock_ai_server.py` prints its `PORT=`), then flip to
Ollama. Testing costs two minutes; a broken 7 AM job costs one morning.

---

## The morning digest

**What you'll change:** `MY-NOTES.md`, the times.
**Where:** every non-recipe file path is absolute on purpose.

`jobs/daily-digest.sh` (Linux/Mac). For Windows, write the same thing as a
`.cmd` file — Chapter 2's `daily-digest.cmd` is the identical shape:

```bash
#!/bin/bash
cd "$HOME/scheduled-ai-jobs"
/usr/bin/python3 scripts/morning_digest.py \
  --base-url http://127.0.0.1:11434/v1 \
  --model llama3.2 \
  --notes-file "$HOME/scheduled-ai-jobs/MY-NOTES.md" \
  --out-dir logs
```

The schedule (cron; Task Scheduler equivalent in Chapter 2):

```cron
0 7 * * *  $HOME/scheduled-ai-jobs/jobs/daily-digest.sh
```

Read the result over coffee: `logs/morning-digest-YYYY-MM-DD.md`.

---

## The weekly review (this week vs last)

```bash
#!/bin/bash
cd "$HOME/scheduled-ai-jobs"
LASTWEEK=$(date -d '7 days ago' +%Y-%m-%d)     # macOS: date -v-7d +%Y-%m-%d
LAST="$HOME/scheduled-ai-jobs/logs/morning-digest-$LASTWEEK.md"

prompt="Using today's notes and last week's digest (attached), write a weekly review. Sections: Wins / Loose ends / Next week's movers / Something odd. Compare explicitly. Max 400 words."

/usr/bin/python3 scripts/ai_job.py \
  --prompt "$prompt" \
  --input-file "$LAST" \
  --out-dir logs --job-name weekly-review
```

```cron
30 8 * * 1  $HOME/scheduled-ai-jobs/jobs/weekly-review.sh
```

(Monday 8:30 — see Chapter 5 on Friday-getting-lost.)

---

## The watchdog (runaway alarm)

```cron
0 */6 * * *  /usr/bin/python3 $HOME/scheduled-ai-jobs/scripts/watchdog.py --job-dir $HOME/scheduled-ai-jobs/logs
```

Rings (exits 2) when: logs got oversized, a lock went stale, or a job
failed in the last 24 h. How the ring reaches *you* — a wrapper script or
desktop notification — is yours to wire; Chapter 7 has one pattern.

---

## The first-draft listing description (eBay/reselling)

Input: a text file per item. Output: a listing draft you *always* skim
before it ships —

```bash
python3 scripts/ai_job.py \
  --prompt "Write a friendly eBay auction description from these item notes: title, condition (be honest about flaws), measurements. End with a plain shipping/handling line. Max 200 words." \
  --input-file "$HOME/ebay/ITEM-NOTES.md" \
  --out-dir "$HOME/ebay/logs" --job-name listing-draft \
  --force
```

`--force` for manual runs only (it overrides a held lock) — scheduled, it
should be omitted. See everyday-batch-file-automation-handbook for the
many-items batch loop this pairs with in human-eye discipline.

---

## The study-notes checker (healthcare study aid — education, never advice)

**Not medical advice, ever.** Education notes you authored *yourself*:

```bash
python3 scripts/ai_job.py \
  --prompt "From my study notes below, give: 1) three likely-section questions a quiz might ask, 2) one-paragraph plain-English explanations for each. Cite only my notes; say 'not in my notes' otherwise." \
  --input-file "$HOME/study/UNIT-3-NOTES.md" \
  --out-dir "$HOME/study/logs" --job-name study-checker
```

Grounding language is the safety bar: "cite only my notes" walls off
invention. Your clinical decisions stay with clinicians.

---

## The docs-table-of-contents checker (GitHub Actions)

From Chapter 4: a workflow that lists the numbered headings in `docs/`
each Monday so a drifted TOC shows up in the Actions log. Chapter 4's
changelog recipe is the fuller template — its "collect inputs / prompt /
retries" spine always stays the same; only the collection step changes.

```yaml
on:
  schedule: [{cron: "0 14 * * 1"}]
  workflow_dispatch:
permissions:
  contents: read
jobs:
  toc-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          python3 - <<'PY'
          import re
          from pathlib import Path
          for p in sorted(Path("docs").glob("*.md")):
              heads = re.findall(r"^#+ (.+)$", p.read_text(), re.M)
              print(f"{p}: {len(heads)} headings")
              for h in heads:
                  if re.match(r"^#* ?\d", h):
                      print(f"   chapter: {h}")
          PY
```

---

## The retirement plan (un-scheduling)

Time zones of the future may take shifts, or a job may retire. Where the
kill switch lives, per chapter:

| Scheduler | Kill switch |
| --- | --- |
| Task Scheduler | `schtasks /Delete /tn "Name" /f` (or GUI, right-click → Delete) |
| cron | `crontab -e` → delete the line |
| systemd timers | `systemctl --user disable --now <name>.timer` |
| GitHub Actions | Actions tab → workflow → ⋯ → Disable |

Know these *before* you schedule anything. It's Chapter 8's whole point,
restated from the exit-side: every good scheduled job has a kill switch
you know where to find.
