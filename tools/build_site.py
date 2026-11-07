#!/usr/bin/env python3
"""Build the static site from the handbook markdown in docs/.

Writes HTML pages for every docs/*.md plus a site/index.html with a linked
table of contents. No dependencies beyond the Python standard library —
the site is fully static, plain files you can host anywhere (or just open
site/index.html in a browser).

  python3 tools/build_site.py            # build into site/
  python3 tools/build_site.py --check    # build into a temp dir + verify links
"""

import argparse
import html
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SITE = ROOT / "site"

CHAPTER_TITLES = {
    "00-start-here": "Start here",
    "01-scheduled-job-or-one-off-chat": "Scheduled job or one-off chat?",
    "02-windows-task-scheduler-recipes": "Windows Task Scheduler recipes",
    "03-cron-recipes": "cron recipes (Linux & Mac)",
    "04-github-actions-chore-crew": "GitHub Actions for repo chores",
    "05-digest-patterns": "Morning digest & weekly summary patterns",
    "06-logging": "Logging: knowing what actually happened",
    "07-retries-and-polite-failures": "Retries and polite failures",
    "08-stopping-runaway-jobs": "Stopping runaway jobs",
    "09-local-endpoints": "Local endpoints & Ollama",
    "10-recipe-cards": "Recipe cards",
}

STYLE = """\
:root {
  --ink: #24292f; --muted: #6a737d; --line: #e1e4e8;
  --accent: #0b6a28; --accent-soft: #eaf5ee;
  --code-bg: #f6f8fa; --card: #ffffff; --bg: #fbfaf7;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 17px/1.65 Georgia, "Iowan Old Style", "Times New Roman", serif;
}
header.masthead {
  background: var(--accent-soft); border-bottom: 1px solid var(--line);
  padding: 1.6rem 1.2rem 1.2rem; text-align: center;
}
header.masthead h1 { font-size: 1.7rem; margin: 0 0 .3rem; }
header.masthead p { margin: 0; color: var(--muted); font-style: italic; }
main { max-width: 46rem; margin: 0 auto; padding: 2rem 1.2rem 3rem; }
h1, h2, h3 { font-family: "Iowan Old Style", Georgia, serif; line-height: 1.25; }
h1 { font-size: 1.9rem; border-bottom: 2px solid var(--line); padding-bottom: .35rem; }
h2 { font-size: 1.35rem; margin-top: 2rem; }
h3 { font-size: 1.1rem; }
a { color: var(--accent); }
code, pre {
  font: .9em/1.55 ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  background: var(--code-bg); border-radius: 6px;
}
code { padding: .15em .35em; }
pre { padding: .9rem 1rem; overflow-x: auto; border: 1px solid var(--line); }
pre code { padding: 0; background: none; }
table { border-collapse: collapse; width: 100%; font-size: .93rem; margin: 1.2rem 0; }
th, td { border: 1px solid var(--line); padding: .5rem .7rem; text-align: left; }
th { background: var(--code-bg); }
tr:nth-child(even) td { background: #fdfdfb; }
blockquote {
  margin: 1.2rem 0; padding: .5rem 1rem; color: var(--muted);
  border-left: 4px solid var(--accent); background: var(--card);
  font-style: italic;
}
nav.chapter-nav, ol.toc { padding-left: 1.4rem; }
footer {
  text-align: center; color: var(--muted); font-size: .85rem;
  padding: 1.5rem; border-top: 1px solid var(--line);
}
footer a { color: var(--muted); }
li { margin: .25rem 0; }
"""


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def md_to_html(md: str) -> str:
    """Markdown -> HTML for the subset used in this handbook.

    Handles: fenced code blocks, ATX headings, pipe tables, blockquotes,
    bulleted/numbered lists, paragraphs, and inline code/bold/italic/links.
    """
    lines = md.splitlines()
    out: list[str] = []
    para: list[str] = []
    list_type: str | None = None
    list_items: list[str] = []
    code_lang: str | None = None
    code_lines: list[str] = []
    table_lines: list[str] = []
    quote_lines: list[str] = []

    def flush_para():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    def flush_list():
        nonlocal list_type, list_items
        if list_items:
            tag = "ol" if list_type == "ol" else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(i)}</li>" for i in list_items) + f"</{tag}>")
        list_type = None
        list_items.clear()

    def flush_code():
        nonlocal code_lang, code_lines
        if code_lang is not None:
            body = html.escape("\n".join(code_lines), quote=False)
            out.append(f'<pre><code data-lang="{esc(code_lang)}">{body}</code></pre>')
            code_lang = None
            code_lines.clear()

    def flush_table():
        nonlocal table_lines
        if table_lines:
            header = [c.strip() for c in table_lines[0].strip().strip("|").split("|")]
            rows = []
            for tl in table_lines[2:]:
                cells = [c.strip() for c in tl.strip().strip("|").split("|")]
                rows.append(cells)
            out.append("<table><thead><tr>"
                       + "".join(f"<th>{inline(c)}</th>" for c in header)
                       + "</tr></thead><tbody>"
                       + "".join(
                           "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row)
                           + "</tr>" for row in rows)
                       + "</tbody></table>")
            table_lines.clear()

    def flush_quote():
        nonlocal quote_lines
        if quote_lines:
            out.append("<blockquote>" + inline(" ".join(q.strip(">").strip() for q in quote_lines)) + "</blockquote>")
            quote_lines.clear()

    def flush_all():
        flush_para(); flush_list(); flush_code(); flush_table(); flush_quote()

    for line in lines:
        if code_lang is not None:
            if line.strip() == "```":
                flush_code()
            else:
                code_lines.append(line)
            continue

        stripped = line.strip()

        if stripped.startswith("```"):
            flush_all()
            code_lang = stripped[3:].strip() or "text"
            continue

        if stripped.startswith(("|",)):
            flush_para(); flush_list(); flush_quote()
            table_lines.append(stripped)
            continue
        if table_lines:
            flush_table()

        if not stripped:
            flush_all()
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_all()
            level = len(m.group(1))
            text = m.group(2).replace("`", "")
            out.append(f"<h{level} id='{slug(text)}'>{inline(m.group(2))}</h{level}>")
            continue

        if stripped.startswith(">"):
            flush_para(); flush_list()
            quote_lines.append(stripped)
            continue
        if quote_lines:
            flush_quote()

        m_ol = re.match(r"^(\d+)[.)]\s+(.*)$", stripped)
        m_ul = re.match(r"^[-*]\s+(.*)$", stripped)
        if m_ol:
            if list_type != "ol":
                flush_list(); list_type = "ol"
            list_items.append(m_ol.group(2))
            continue
        if m_ul:
            if list_type != "ul":
                flush_list(); list_type = "ul"
            list_items.append(m_ul.group(1))
            continue

        if para and not _continuation(line):
            flush_para()
        para.append(stripped)

    flush_all()
    return "\n".join(out)


def _continuation(line: str) -> bool:
    """A line continuing a paragraph: not starting fresh syntax."""
    s = line.strip()
    return not (not s or s.startswith(("#", "-", "*", ">", "|", "```"))
                or re.match(r"^\d+[.)]\s", s))


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", "", text.lower().replace("`", ""))
    return re.sub(r"\s+", "-", s.strip())


def page(title: str, body: str, toc_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — Scheduled AI Jobs Handbook</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>
<header class="masthead">
  <h1>The Scheduled AI Jobs Handbook</h1>
  <p>put AI chores on a schedule instead of clicking — by Asdale Dynamics, LLC</p>
</header>
<main>
{toc_html}
{body}
</main>
<footer>
  &copy; 2026 Asdale Dynamics, LLC · MIT license ·
  plain-English AI handbooks at
  <a href="https://dylanasdale.github.io">dylanasdale.github.io</a>
</footer>
</body>
</html>
"""


def build_toc() -> str:
    items = []
    for stem, title in CHAPTER_TITLES.items():
        items.append(f'<li><a href="{stem}.html">{esc(title)}</a></li>')
    return '<nav class="chapter-nav"><ol class="toc">' + "".join(items) + "</ol></nav>"


def build(output_dir: Path) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "styles.css").write_text(STYLE, encoding="utf-8")
    toc = build_toc()
    built = []
    for md_path in sorted(DOCS.glob("*.md")):
        stem = md_path.stem
        title = CHAPTER_TITLES.get(stem, stem)
        body = md_to_html(md_path.read_text(encoding="utf-8"))
        html_final = page(title, body, toc)
        target = output_dir / f"{stem}.html"
        target.write_text(html_final, encoding="utf-8")
        built.append(target.name)
    (output_dir / "index.html").write_text(
        page(
            "The Scheduled AI Jobs Handbook",
            intro_html(),
            build_toc(),
        ),
        encoding="utf-8",
    )
    built.append("index.html")
    return built


def intro_html() -> str:
    return """
<p><strong>You already know AI can do the chore.</strong> The problem
isn't the chore &mdash; it's the clicking. You type the same prompt every
morning. That's a job, and jobs can run on a schedule instead of you.</p>
<p>This handbook shows you how to hand those chores to a scheduler &mdash;
Windows Task Scheduler, cron, or GitHub Actions &mdash; and to do it with
local, OpenAI-compatible endpoints (Ollama included), needing no API keys,
so private data stays at home.</p>
<p>Pick a chapter to start with; the reading order runs from judgment
(what belongs on a schedule) through recipes to guardrails (logging,
retries, runaway control).</p>
"""


def check(built: list[str], output_dir: Path) -> bool:
    """Verify every internal link and asset referenced by the pages exists."""
    ok = True
    for name in built:
        html_path = output_dir / name
        content = html_path.read_text(encoding="utf-8")
        for href in re.findall(r'href="([^"#]+)"', content):
            if href.startswith(("http://", "https://", "#")):
                continue
            if not (output_dir / href).exists():
                print(f"BROKEN LINK in {name}: {href}")
                ok = False
    if not (output_dir / "index.html").exists():
        print("missing index.html")
        ok = False
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="build the handbook site")
    parser.add_argument("--out", default=str(SITE))
    parser.add_argument("--check", action="store_true",
                        help="build into a temporary directory and verify")
    args = parser.parse_args()

    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            built = build(Path(tmp))
            ok = check(built, Path(tmp))
            built_count = len(built)
        print(f"check: {built_count} pages built in temp dir")
        return 0 if ok else 1

    out_dir = Path(args.out)
    built = build(out_dir)
    print(f"built {len(built)} pages into {out_dir}")
    if not check(built, out_dir):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
