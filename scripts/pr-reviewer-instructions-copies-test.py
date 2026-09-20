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

EQUALITY, NOT CONTAINMENT. Until 2026-09-20 this test asked only whether
each of the file's paragraphs appeared somewhere in CLAUDE.md. Containment
passes two one-sided edits that leave the copies different, both measured
against the head of PR "CLAUDE.md's review-scope bullet is the instructions
file's section verbatim, and a test keeps it so": deleting the last sentence
of a bullet in the instructions file alone, and appending a sentence to
CLAUDE.md's bullet alone. A shorter string is still contained in a longer
one. Found by the merge-lane seat reviewing that pull request; its two cases
are the mutation cases below, which fail if the comparison ever weakens
again.

The three bullets must match one for one, in order. The intro cannot: in the
file it is a paragraph under a heading, and in CLAUDE.md it is the middle of
one bullet, between the heading restated inline and the sentence naming the
file and this test. So the intro is pinned on both sides instead — what
precedes it must be exactly the restated heading, and what follows it must
begin the naming sentence — which catches an edit to either end of it.

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

# CLAUDE.md's bullet restates the heading inline before the copied intro, and
# names the file and this test after it. Both are CLAUDE.md's own framing, not
# part of the copy, so they bound the intro rather than being compared to it.
CLAUDE_MD_PREFIX = ("Reviewing a pull request — **review scope: code blocks, "
                    "prose does not.** ")
CLAUDE_MD_SUFFIX_OPENING = "This bullet is the"

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


def claude_md_copy(claude_md: str):
    """CLAUDE.md's copy: the top-level bullet carrying the rule, and its
    indented sub-bullets, each collapsed. Returns (None, []) when the bullet
    is not there at all, which is its own failure below."""
    lines = claude_md.splitlines()
    for index, line in enumerate(lines):
        if not (line.startswith("- ") and CLAUDE_MD_PREFIX.strip() in collapse(line)):
            continue
        sub_bullets = []
        for following in lines[index + 1:]:
            if following.startswith("  - "):
                sub_bullets.append(following[4:])
            elif following.strip() and following.startswith("    ") and sub_bullets:
                sub_bullets[-1] += " " + following.strip()
            else:
                break
        return collapse(line[2:]), [collapse(bullet) for bullet in sub_bullets]
    return None, []


def differences(instructions: str, claude_md: str) -> list:
    """Every way the two copies fail to say the same thing. Empty means
    identical. Kept separate from the file reads so the mutation cases below
    can run it on text that is not on disk."""
    problems = []
    if SECTION_HEADING not in instructions:
        return [f"the instructions file has no {SECTION_HEADING!r} section"]

    paragraphs = section_paragraphs(review_scope_section(instructions))
    if len(paragraphs) != 4:
        return [f"the section holds {len(paragraphs)} paragraph(s), expected an "
                f"intro and three bullets: {paragraphs}"]
    file_intro, file_bullets = paragraphs[0], paragraphs[1:]

    claude_intro, claude_bullets = claude_md_copy(claude_md)
    if claude_intro is None:
        return ["CLAUDE.md has no bullet carrying the review-scope rule"]

    # The intro, pinned on both sides by CLAUDE.md's own framing.
    if file_intro not in claude_intro:
        problems.append("CLAUDE.md's bullet does not carry the section's intro "
                        "paragraph")
    else:
        before, after = claude_intro.split(file_intro, 1)
        if before != collapse(CLAUDE_MD_PREFIX) + " ":
            problems.append(
                f"CLAUDE.md's bullet says {before!r} before the copied intro; "
                f"expected only the restated heading")
        if not after.lstrip().startswith(CLAUDE_MD_SUFFIX_OPENING):
            problems.append(
                f"CLAUDE.md's bullet says {after[:60]!r} after the copied intro; "
                f"expected the sentence naming the file and this test")

    # The bullets, one for one and in order.
    if len(claude_bullets) != len(file_bullets):
        problems.append(f"CLAUDE.md carries {len(claude_bullets)} sub-bullet(s), "
                        f"the file's section has {len(file_bullets)}")
    for position, file_bullet in enumerate(file_bullets):
        if position >= len(claude_bullets):
            break
        if claude_bullets[position] != file_bullet:
            problems.append(
                f"bullet {position + 1} differs.\n"
                f"    file:      {file_bullet}\n"
                f"    CLAUDE.md: {claude_bullets[position]}")
    return problems


instructions = INSTRUCTIONS_FILE.read_text(encoding="utf-8")
claude_md = CLAUDE_MD.read_text(encoding="utf-8")

found = differences(instructions, claude_md)
check("the two copies say the same thing",
      not found,
      "\n  " + "\n  ".join(found) + "\n  The file is the rule's home; make "
      "CLAUDE.md's bullet its section again.")

check("CLAUDE.md names the file and this test beside its copy",
      "docs/agents/pr-reviewer-instructions.md" in collapse(claude_md)
      and "scripts/pr-reviewer-instructions-copies-test.py" in collapse(claude_md),
      "the copy must say where the rule lives and what keeps the two identical")

# --- The two one-sided edits containment used to pass --------------------
# Both run differences() over a pair of synthetic copies built here, never
# over the real files, so they keep testing the comparison rather than
# today's wording. They are the cases the merge-lane seat measured, and they
# are here so a future simplification cannot quietly go back to containment.

FIXTURE_INSTRUCTIONS = """# Reviewer instructions

## Review scope: code blocks, prose does not

Intro sentence one. Intro sentence two.

- **A.** Alpha one. Alpha two.
- **B.** Beta one.
- **C.** Gamma one.

## Some later section

Not part of the copy.
"""

FIXTURE_CLAUDE_MD = """# Project

- Reviewing a pull request — **review scope: code blocks, prose does not.** \
Intro sentence one. Intro sentence two. This bullet is the section, kept \
identical by a test.
  - **A.** Alpha one. Alpha two.
  - **B.** Beta one.
  - **C.** Gamma one.
- An unrelated rule.
"""
# The bullet is one line; the backslashes above are Python's, not the file's.
FIXTURE_CLAUDE_MD = FIXTURE_CLAUDE_MD.replace("\\\n", "")

check("the fixtures agree to begin with, or the mutations prove nothing",
      differences(FIXTURE_INSTRUCTIONS, FIXTURE_CLAUDE_MD) == [],
      str(differences(FIXTURE_INSTRUCTIONS, FIXTURE_CLAUDE_MD)))

shortened_file = FIXTURE_INSTRUCTIONS.replace(
    "- **A.** Alpha one. Alpha two.", "- **A.** Alpha one.", 1)
check("a sentence deleted from the file's bullet alone is caught",
      differences(shortened_file, FIXTURE_CLAUDE_MD) != [],
      "the shorter bullet is still contained in CLAUDE.md's; the comparison "
      "has gone back to containment")

lengthened_claude_md = FIXTURE_CLAUDE_MD.replace(
    "  - **C.** Gamma one.", "  - **C.** Gamma one. Gamma two.", 1)
check("a sentence appended to CLAUDE.md's bullet alone is caught",
      differences(FIXTURE_INSTRUCTIONS, lengthened_claude_md) != [],
      "the file's bullet is still contained in the longer one; the comparison "
      "has gone back to containment")

check("an edit to the framing around the copied intro is caught",
      differences(FIXTURE_INSTRUCTIONS,
                  FIXTURE_CLAUDE_MD.replace(
                      "**review scope: code blocks, prose does not.** ",
                      "**review scope: code blocks, prose does not.** Also: ",
                      1)) != [],
      "text inserted between the restated heading and the copied intro passed")

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
