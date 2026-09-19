#!/usr/bin/env python3
"""The reviewer scope rule has two copies on purpose, and this test keeps
them identical.

`docs/agents/pr-reviewer-instructions.md` is the rule's home: its text is
pasted whole into every Claude reviewer's prompt. CLAUDE.md carries the
rule's "Review scope" section a second time, because the Codex reviewer
(scripts/code-review-codex-cell.py, Codex's built-in review) takes no custom
prompt and reads the repository's rules through AGENTS.md -> CLAUDE.md, so
CLAUDE.md is the only channel by which it receives the rule (user-ruled
2026-09-19, walk on nedschorus#210). Two copies drift: by 2026-09-18 the
CLAUDE.md paragraph and the file no longer said the same thing, and nothing
noticed for weeks. This test is what notices.

Run: python3 scripts/pr-reviewer-instructions-copies-test.py
Prints one line per case and exits non-zero if any case fails. Whitespace is
collapsed before comparing, because the file wraps its lines and CLAUDE.md
keeps one bullet per line; nothing else is normalized.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTRUCTIONS_FILE = REPO_ROOT / "docs" / "agents" / "pr-reviewer-instructions.md"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
SECTION_HEADING = "## Review scope: code blocks, prose does not"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def review_scope_section(instructions: str) -> str:
    """The section's body: from its heading to the next heading or the end."""
    start = instructions.index(SECTION_HEADING) + len(SECTION_HEADING)
    rest = instructions[start:]
    match = re.search(r"^## ", rest, flags=re.MULTILINE)
    return rest[: match.start()] if match else rest


def section_paragraphs(section: str) -> list:
    """The intro paragraph and each bullet, as the file writes them, with a
    wrapped bullet's continuation lines joined to it."""
    paragraphs = []
    for block in re.split(r"\n\s*\n", section.strip()):
        block = block.strip()
        if not block:
            continue
        if block.startswith("- "):
            # One block may hold several bullets; split at bullet starts.
            for bullet in re.split(r"\n(?=- )", block):
                paragraphs.append(collapse(re.sub(r"^- ", "", bullet.strip())))
        else:
            paragraphs.append(collapse(block))
    return paragraphs


instructions = INSTRUCTIONS_FILE.read_text(encoding="utf-8")
claude_md = collapse(CLAUDE_MD.read_text(encoding="utf-8"))

check("the instructions file has its Review scope section",
      SECTION_HEADING in instructions, str(INSTRUCTIONS_FILE))

paragraphs = section_paragraphs(review_scope_section(instructions)) \
    if SECTION_HEADING in instructions else []
check("the section holds an intro and three bullets",
      len(paragraphs) == 4, f"{len(paragraphs)} paragraph(s): {paragraphs}")

for paragraph in paragraphs:
    label = paragraph[:60]
    check(f"CLAUDE.md carries verbatim: {label}...",
          paragraph in claude_md,
          "not found in CLAUDE.md after collapsing whitespace; the two copies "
          "have drifted — make CLAUDE.md's bullet the file's section again")

check("CLAUDE.md names the file and this test beside its copy",
      "docs/agents/pr-reviewer-instructions.md" in claude_md
      and "scripts/pr-reviewer-instructions-copies-test.py" in claude_md,
      "the copy must say where the rule lives and what keeps the two identical")

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
