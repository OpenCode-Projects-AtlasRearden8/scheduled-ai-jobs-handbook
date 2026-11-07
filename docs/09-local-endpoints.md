# 09 · Local endpoints & Ollama

Every script in this handbook talks to an **OpenAI-compatible endpoint**. If
your picture of "endpoint" is "send my notes to a datacenter," this chapter
is the plot twist: the whole dialect is just plain HTTP, and your own laptop
speaks it. Notes in, digest out, **nothing leaves the house**, **no API keys
anywhere**.

## What "OpenAI-compatible" actually means

OpenAI was first to publish a chat-completions API shape. So many tools
adopted the shape that it became a dialect rather than a product. You POST
JSON to `/v1/chat/completions` and get JSON back:

```json
{
  "model": "llama3.2",
  "messages": [
    {"role": "system", "content": "You write a short briefing."},
    {"role": "user", "content": "Digest my notes."}
  ],
  "stream": false
}
```

and the answer's text rides back in
`choices[0].message.content`. That's the whole interface. The scripts here
speak exactly this and nothing more — which is why they run against
anything that speaks the dialect, with no client library.

## The two-minute Ollama setup

1. Install [Ollama](https://ollama.com) (Windows/macOS/Linux). It starts a
   local server on port 11434 and opens the dialect at `/v1/`.
2. Pull a small model — for scheduled digests you want *fast*, not genius:

   ```bash
   ollama pull llama3.2     # ~2 GB, fits a modest laptop
   ```

3. Check the endpoint yourself:

   ```bash
   curl http://127.0.0.1:11434/v1/models
   ```

   You'll get a JSON list; the `id` field is the model name your job will
   use (e.g. `llama3.2:latest`).

Now your job runner takes exactly one extra switch to become local-first:

```bash
python3 scripts/ai_job.py \
  --base-url http://127.0.0.1:11434/v1 \
  --model llama3.2 \
  --prompt "Digest my notes" \
  --input-file my-notes.md \
  --out-dir logs
```

Those defaults — Ollama on 11434 — are in `DEFAULT_BASE_URL` at the top of
the scripts, so most of the time you never pass them at all.

## Same trick, different hosts

| Program | Base URL | Notes |
| --- | --- | --- |
| Ollama | `http://127.0.0.1:11434/v1` | easiest; starts at login |
| LM Studio | `http://127.0.0.1:1234/v1` | enable the server tab; check port |
| llama.cpp (`llama-server`) | `http://127.0.0.1:8080/v1` | start with `-a <model-name>` |
| Anything else speaking the dialect | `(your machine)/v1` | same client code runs everywhere |

Try one quick endpoint probe with any of them — hit `/v1/models` — and you
know it's alive before you even schedule a job.

# Model choice, in one paragraph

Scheduled jobs reward **small, fast, boring**. A 2–3B model producing a
150-word digest each morning is the right tool: it finishes in seconds,
never warms up in your way, and its failure modes (a bland bullet, not a
wrong claim) are the cheap ones. Genius models are for chats you're
watching; scheduled jobs are where "good enough, every day, forever" wins.
Start at `llama3.2` or a similar small model; scale up only if a specific
job's output genuinely needs it.

## Privacy, concretely

What "local endpoint" buys you, itemized:

- **Transit:** the HTTP call stays on your machine (or LAN). It doesn't
  touch the internet. Verify any time: disconnect from Wi-Fi, run a digest,
  watch it still work.
- **Storage:** notes and digests live in your files (`out-dir`, `logs/`).
  Nothing phones home; there's no account to leak.
- **Keys:** the scripts accept none. There's no secret to store, rotate, or
  accidentally commit.
- **Logs:** the job log records outcomes and char counts, never prompt
  content — the log file which *does* live in plaintext won't contain what
  your notes said. That's why logging (Chapter 6) and privacy agree here.

The one honest boundary: **training / provider policy** becomes not-applicable
because there is no provider. The content that stays your machine's problem
is only *your theft/exposure risk*, not a remote one — back up like any
other private file.

## Keep Ollama alive for the 7 o'clock job

The scheduled job assumes the endpoint is up. The recipes in Chapters 2
and 3 cover that in depth, including:

- start Ollama at login (the simplest; the installer's default), so the
  digest fires at 7:00 without you touching anything;
- on Linux servers, install it as a systemd service so it starts at boot;
- add a 5-second probe at the top of the job script:

```bash
curl -s --max-time 5 http://127.0.0.1:11434/v1/models \
  || echo "OLLAMA DOWN at $(date -u)" >> logs/morning-digest.log
```

With that probe, a downed endpoint produces a **readable** failure in your
log instead of a *mysterious* one ("HTTP error" at 7:00:41 does not tell
you WHY, but `OLLAMA DOWN` does).

## Testing without a model at all: the mock

You don't even need a model installed to *test the scheduling plumbing*.
`scripts/mock_ai_server.py` speaks the same dialect and always answers:

```bash
python3 scripts/mock_ai_server.py &          # prints PORT=<something>
python3 scripts/ai_job.py \
  --base-url http://127.0.0.1:<port>/v1 \
  --prompt "hello" --out-dir /tmp/logs
```

It's fake but honest: replies are a canned "MOCK RESPONSE" naming how many
characters your prompt reached it. That's enough to verify the whole
schedule machinery — locking, logging, digest writing — without waiting on
a model. `tests/run_tests.py` builds on it. Mock first, real model second.
