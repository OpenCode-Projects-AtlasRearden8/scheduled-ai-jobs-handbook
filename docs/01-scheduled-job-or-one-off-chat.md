# 01 · Scheduled job or one-off chat?

Before you automate anything, spend two minutes deciding whether it deserves
a schedule at all. This is the judgment call the whole book rests on, and
it's honestly just three questions.

## The three questions

**1. Would you run this again, on roughly the same clock?**

If you'd prompt it today and prompt it again next Tuesday in mostly the same
words — schedule it. If today's request is shaped around today's weird
problem ("help me understand why my spreadsheet total is off"), keep it as a
one-off chat.

**2. Can the job be described once, in advance, as a fixed recipe?**

A scheduled job has to survive with zero context from you. "Summarize
everything I saved in `notes.md` over the last day" works because the inputs
and the instruction are both knowable ahead of time. "Help me think through
what I should do about David's email" isn't — it needs you in the loop.

**3. Is a wrong answer cheap, or at least visible?**

Every scheduled job will someday produce something confidently wrong. model
misreads your notes, or the output is bland when you wanted sharp. If the
output is a draft digest you'll skim for two minutes — fine, wrong-ish for a
day costs nothing. If the output directly sends money, sends email on your
behalf, or feeds medical decisions — don't schedule it raw. This book is
education, never medical advice, and that goes double for anything that runs
while you're asleep.

## Scoring your chores

| The chore | Schedule it? | Why |
| --- | --- | --- |
| Morning digest of your notes | Yes | Same time daily, fixed inputs, cheap if wrong |
| Weekly "what did I do this week" summary | Yes | Same clock weekly (Chapter 5) |
| Draft eBay listing description from item notes | Maybe | Repeatable shape, but you should eyeball before shipping — good *first draft* job |
| Reply to this specific customer email | No | One-off context |
| Batch-rename 400 files by reading a manifest | No, and also — | This is plain automation, not AI. That's a different handbook (batch files need careful logic, not fluent text). See everyday-batch-file-automation-handbook |
| "Check my blood-pressure readings and advise" | **Never, as advice** | Healthcare education is fine; medical advice from an unattended scheduled job is not |

## The spectrum, from click to clock

It's not two buckets, it's a dial:

1. **Click every time** — daily one-off chat. Fine for genuinely creative work.
2. **Click, but from a saved prompt** — a script you paste into chat by hand.
   Already better. (automation-friend-guide calls this your prompt library.)
3. **One click, whole job** — `scripts/ai_job.py --prompt "..." --input-file
   my-notes.md`. The job exists; you just trigger it.
4. **On the clock** — the same script, plus Task Scheduler, cron, or GitHub
   Actions. You never trigger it again.
5. **On the clock, self-monitoring** — plus logging, retries, and the
   watchdog so it can be left alone (Chapters 6–9).

This handbook is steps 3–5. If you hover at step 1 for a chore that's
actually step 2, you're paying a tax every single day.

## When NOT to schedule (gently)

- **You'd want your judgment in the loop anyway.** Scheduling removes you
  from the loop. If removing yourself makes the output useless, don't.
- **Nothing about it repeats.** Setup cost, even a small one, only pays for
  itself with repetition.
- **It's really a batch-files job.** If no reasoning is needed — just a loop
  and rules — plain shell/batch is faster, deterministic, and AI creates
  more failure modes than value. Different book, as above.
- **The model needs to be *right*, not *helpful*.** Summaries are self-
  checking (you'll notice gibberish). Translations, extraction into a
  ledger, anything feeding money or health decisions — keep your hands on it.

## A good first scheduled job

Pick something where the failure mode is "bland summary, deleted tomorrow."
The morning digest (Chapter 5) is the classic. Yours might be a weekly
review of your todo file, or a Friday summary of your eBay activity file.
Whatever it is, it should be: same input file, same instruction, same clock,
and human-skimmed output.

Chapter 2 gets it on the clock.
