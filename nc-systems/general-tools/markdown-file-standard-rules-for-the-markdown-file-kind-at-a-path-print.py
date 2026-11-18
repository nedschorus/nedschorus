#!/usr/bin/env python3
"""Print the Markdown file standard's rules for the file at a path: the common part, then the section for the file's kind.

Usage: markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print.py <path of a Markdown file>

Exits 0 if a section of the standard covers the path, and prints the common part and that
section; 1 if no section covers it, and prints the common part alone; 2 if the standard
could not be read or lacks a heading this program needs, or the program was called wrongly.

The kind is picked from the path alone, so the file need not exist yet. The path may be
relative or absolute, inside any checkout or worktree, or under the Mac's /Volumes/nedhome
mount of ned-box's home directory.
"""

import os
import re
import sys
from pathlib import Path

PROGRAM_NAME = "markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print"
MARKDOWN_FILE_STANDARD_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "nedschorus-wiki" / "queue"
    / "nedschorus-markdown-file-standard-common-part-and-one-section-per-kind.md")
COMMON_PART_HEADING = "Common part"

# A test-design and a design-contract sit beside their design, under names the Designs and
# GHI-MDs patterns also match, but design-to-main's agent-instructions say what they hold.
UNCOVERED_PATH_PATTERNS = [r"-test-design\.md$", r"-contract\.md$"]

# The first pattern that matches the path picks the section, so a narrower kind comes before
# a wider one that also matches its paths: a design in docs/issues/ before the GHI-MDs, and
# the glossary before the wiki pages. Each pattern is anchored at a path component, so it
# matches the same file in any checkout.
KIND_SECTION_HEADING_AND_PATH_PATTERNS = [
    ("Handoff next-step files", r"(^|/)\.claude/handoffs/[^/]+-next-step-[^/]*\.md$"),
    ("Seat-briefs", r"(^|/)CLAUDE\.local\.md$"),
    ("The project glossary", r"(^|/)docs/nedschorus-wiki/nedschorus-glossary\.md$"),
    ("Designs", r"(^|/)[^/]+-design\.md$"),
    # A claim-check's proposed-improvements-or-changes-file sits beside its overview but is a
    # record of what the claim-check found, not a page.
    ("Wiki pages",
     r"(^|/)docs/nedschorus-wiki/(queue/)?(?![^/]*-proposed-improvements-or-changes-)[^/]+\.md$"),
    ("GHI-MDs", r"(^|/)docs/issues/(queue/[^/]+|\d+-[^/]+)\.md$"),
]


def kind_section_heading_for_path(path):
    """The heading of the standard's section that covers the path, or None when none does."""
    normalized = Path(os.path.expanduser(path)).as_posix()
    if any(re.search(pattern, normalized) for pattern in UNCOVERED_PATH_PATTERNS):
        return None
    for heading, pattern in KIND_SECTION_HEADING_AND_PATH_PATTERNS:
        if re.search(pattern, normalized):
            return heading
    return None


class MarkdownFileStandardUnreadable(Exception):
    """The standard could not be read, or lacks a heading this program needs."""


def level_two_sections(text):
    """Map each level-2 heading's text to its section, heading line included.

    Lines inside fenced code blocks are not headings."""
    sections = {}
    current = None
    in_fence = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        elif not in_fence and line.startswith("## "):
            current = line[3:].strip()
            sections[current] = ""
        if current is not None:
            sections[current] += line
    return sections


def markdown_file_standard_sections(standard_path=MARKDOWN_FILE_STANDARD_PATH):
    """The standard's level-2 sections; raises MarkdownFileStandardUnreadable when one is missing."""
    try:
        text = Path(standard_path).read_text(encoding="utf-8")
    except OSError as error:
        raise MarkdownFileStandardUnreadable(f"cannot read {standard_path}: {error}") from error
    sections = level_two_sections(text)
    needed = [COMMON_PART_HEADING] + [heading for heading, _ in KIND_SECTION_HEADING_AND_PATH_PATTERNS]
    missing = [heading for heading in needed if heading not in sections]
    if missing:
        raise MarkdownFileStandardUnreadable(
            f"{standard_path} has no level-2 heading "
            + ", ".join(f'"## {heading}"' for heading in missing)
            + f", which {PROGRAM_NAME}.py's constants name")
    return sections


def main(argv, standard_path=MARKDOWN_FILE_STANDARD_PATH):
    if len(argv) == 1 and argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    if len(argv) != 1:
        print(f"{PROGRAM_NAME}: takes exactly one argument, the path of a Markdown file.\n"
              f"Usage: {PROGRAM_NAME}.py <path of a Markdown file>", file=sys.stderr)
        return 2
    try:
        sections = markdown_file_standard_sections(standard_path)
    except MarkdownFileStandardUnreadable as error:
        print(f"{PROGRAM_NAME}: {error}.\n"
              "Tell the user what this message says. Until the standard is fixed, write the "
              "file without it.", file=sys.stderr)
        return 2
    heading = kind_section_heading_for_path(argv[0])
    sys.stdout.write(sections[COMMON_PART_HEADING].rstrip("\n") + "\n")
    if heading is None:
        kinds = ", ".join(heading for heading, _ in KIND_SECTION_HEADING_AND_PATH_PATTERNS)
        print(f"{PROGRAM_NAME}: no section of the standard covers {argv[0]}; "
              f"its sections cover {kinds}. Follow the common part printed above.",
              file=sys.stderr)
        return 1
    sys.stdout.write("\n" + sections[heading].rstrip("\n") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
