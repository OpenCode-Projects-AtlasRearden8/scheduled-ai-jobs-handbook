# 05 · Morning digest & weekly summary patterns

This chapter is about **shape**. Once a job runs on a clock (Chapter 2, 3,
or 4), the difference between a digest you actually read and one you click
past is the shape of what comes out. Get the shape right and you'll look
forward to it; skip this chapter and you'll quietly stop opening the file
by week three.

## Pattern 1: the morning digest

**One file, short, same sections every day.** The ritual is the product,
and these four habits are what make it stick:

- **Same sections every single morning.** Predictability *is* the point.
  Ours: *Top priorities* / *Quick wins* / *Worth a look*.
- **Hard caps per section** ("max 3 bullets"). A digest that can grow is a
  document; one that can't is a briefing. The prompt does the capping.
- **A word ceiling on the whole thing** (150 in our default). Enough room
  for three tight sections, a lid on waffle.
- **Say "nothing" politely.** An empty-notes day gets one honest sentence,
  not a padded hallucination. Our script even skips the model call entirely
  and writes the placeholder itself — the "don't run on junk" rule from
  Chapter 8.

`scripts/morning_digest.py` has the exact prompts as plain text you can
edit: the system prompt says *plain language, never invent facts, trivial
notes deserve one sentence*; the user prompt fixes the section names, caps,
and word ceiling. The shape is text, not code — change it to yours.

Wire it up (Linux/Mac; Windows identical via Chapter 2):

```cron
0 7 * * *  $HOME/scheduled-ai-jobs/jobs/daily-digest.sh
```

Output lands in `logs/morning-digest-2026-11-07.md`. Today's file, same
place every morning, a log telling you what happened if it didn't.

**An ADHD-friendly note**, from the life-admin side of
Asdale Dynamics: the value of a morning ritual is that it's already there
when your brain won't architect one. Same file, same name, same three
sections — the activation energy to read it drops to zero. That's why the
shape is rigid on purpose.

## Pattern 2: the weekly summary

The weekly summary follows opposite rules: it may be **longer**, should be
**comparative**, and earns one opinion.

- **It references last week.** "Same as last week, smaller" is the most
  useful sentence a summary can produce — and it needs last week's file to
  exist. Digests are cheap; keep them. A folder of dated files is a free
  history.
- **Sections that age well.** We like: *Wins* / *Loose ends* / *Next week's
  movers* / *Something odd*.
- **One opinion allowed.** Weekly is where a short paragraph of judgment
  genuinely helps. Daily summaries shouldn't editorialize (you can't tell
  one cloudy morning from another); weekly can see the fog week over week.
- **Clock it where you'd read it.** Monday 8:30, not Friday 5:00 — the
  result should greet the week, not vanish into the weekend.

A weekly prompt that works:

```
Using my notes below AND last week's summary (also below), write a weekly
review with exactly these sections: Wins, Loose ends, Next week's movers,
Something odd (a genuine anomaly — not an opinion wearing a costume).
Explicitly compare against last week. Max 400 words.
```

Then hand it `logs/morning-digest-<last-week>.md` alongside this week's
notes. The digest job archived it for a reason.

## Pattern 3: the diff digest ("what changed")

Machine finds the changes, model phrasing-lubricates the wording. It's the
split-responsibility pattern — detection mechanically, wording to the
model — and it's the right way to summarize *changes* without asking a
model to be reliable about noticing them:

```bash
diff -u logs/todo-2026-11-06.md logs/todo-2026-11-07.md > todo-changes.txt
python3 scripts/ai_job.py \
  --prompt "List each change from this diff in one plain sentence. No opinions." \
  --input-file todo-changes.txt \
  --out-dir logs --job-name todo-shift-digest
```

The machine found the changes; the model transliterated them. Every step
owns the job it's good at.

## Pattern 4: a themed day, in a fixed frame

If same-sections-every-day feels too rigid, add one **theme** keyed by
weekday — the frame stays fixed, a small decoration makes it feel alive:

```bash
THEME=$(case $(date +%A) in
  Monday) echo "Pick one thing I've been avoiding.";;
  Friday) echo "Name three tiny wins.";;
  *) echo "Standard top priorities.";;
esac)
```

Feed `$THEME` into the digest prompt as one extra sentence. You can still
predict the shape; the content gets freshness. Rigid frame, small
decorations — that balance is the whole trick.

## What "good shape" means in this one paragraph

A scheduled digest is a **reporter**, not a co-writer: same sections in the
same order, hard caps, permission to say "nothing today," and inputs it
can't hallucinate around (the notes file *is* the material). If your digest
prompt can be paraphrased as "say something interesting," it will produce a
document you learn to skim — which is the failure mode this whole pattern
exists to avoid.

## Verify before you trust the schedule

The morning-digest pattern above is implemented and tested in
`scripts/morning_digest.py`, with three test cases in
`tests/run_tests.py`: a normal digest, a polite skip on empty notes, and a
skip on headings-only notes. Run `python3 tests/run_tests.py` — trust by
verification, not by hope. Chapters 6, 7, and 8 take over from here on
guardrails.
