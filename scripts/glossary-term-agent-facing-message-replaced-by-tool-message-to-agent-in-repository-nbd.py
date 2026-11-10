#!/usr/bin/env python3
"""Rename the project-term agent-facing-message to tool-message-to-agent across the repository.

Run from the top level of a clean checkout:

    python3 scripts/glossary-term-agent-facing-message-replaced-by-tool-message-to-agent-in-repository-nbd.py

What it does: moves each file whose name holds the old term with `git mv`, then rewrites every
spelling of the term in every file git tracks: kebab-case in prose and file names, snake_case and
UPPER_CASE in code, the article before it ("an" becomes "a"), and the plural, which becomes
tool-messages-to-agent; and moves the renamed glossary entry to its alphabetical place. It can be
run again, after a rebase onto a main that added new uses: a file already moved is skipped, and
text already rewritten no longer matches.

What it does not handle: history keeps the old term, so the script leaves alone the files in
HISTORY_FILES and every string in HISTORY_STRINGS, such as cold-read-record and walk names in
the log-store, branch names, GitHub issue and pull request titles, captured test fixtures, and
archived notes that use "agent-facing" in another sense. A new use of the old term in a form it
has no rule for is not rewritten.

How it fails: it exits 1 and lists each line that still holds "agent-facing" or "agent_facing"
outside that history, so a new form is seen rather than left behind; the files it already
rewrote stay rewritten, so review them with `git diff` and add a rule or a history string, then
run it again. A `git mv` that fails stops it with git's error before any file text is changed.
It changes only the working tree and the index of the checkout it runs in, never a commit.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

THIS_SCRIPT = "scripts/glossary-term-agent-facing-message-replaced-by-tool-message-to-agent-in-repository-nbd.py"

# Each moved file's new path. Its old path is derived by OLD_NAME_PARTS, so no line of this
# script cites a path the rename removes: branch-leaves-no-citations-of-removed-paths-test.py
# fails on such a citation.
MOVED_FILES_NEW_PATHS = (
    "docs/nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md",
    "nc-systems/general-tools/failed-command-tool-message-to-agent-rerun-once-then-stop-and-report-lines-common.py",
    "nc-systems/general-tools/tests/failed-command-tool-message-to-agent-rerun-once-then-stop-and-report-lines-common-test.py",
    "nc-systems/general-tools/python-edit-changed-tool-message-to-agent-strings-check-reminder-hook.py",
    "nc-systems/general-tools/tests/python-edit-changed-tool-message-to-agent-strings-check-reminder-hook-test.py",
    "nc-systems/general-tools/python-source-tool-message-to-agent-string-collector-common.py",
    "nc-systems/general-tools/tests/python-source-tool-message-to-agent-string-collector-common-test.py",
    "scripts/tool-message-to-agent-ask-two-fresh-agents-next-step-and-check-named-script-flags.py",
    "scripts/tool-message-to-agent-ask-two-fresh-agents-next-step-and-check-named-script-flags-test.py",
)
# Applied in order to a new path to give its old one.
OLD_NAME_PARTS = (
    ("tool-message-to-agent-strings-check", "agent-facing-message-check"),
    ("tool-message-to-agent-string-collector", "agent-facing-string-collector"),
    ("how-to-write-a-tool-message-to-agent", "how-to-write-an-agent-facing-message"),
    ("tool-message-to-agent", "agent-facing-message"),
)

# Whole files that are history or use "agent-facing" in another sense.
HISTORY_FILES = (
    THIS_SCRIPT,
    "docs/issues/9-neds-notes.md",
    "nc-queue/archived/",
    "scripts/merge-gate-test-captured-github-responses/",
    "scripts/handoff-context-threshold-hook-recorded-handoff-deferrals-replay-test-fixtures/",
)

# Names outside the repository, or titles written on GitHub, that keep the old term.
HISTORY_STRINGS = (
    "python-edit-changed-agent-facing-message-check-reminder-hook-topic-branch",
    "fast-cold-read-of-agent-facing-prose-design-questions-",
    "dangling-path-citation-check-bare-names-and-agent-facing-message-pointer-approval-walk-",
    "record names contain `agent-facing-message`",
    "Wiki: How to write an agent-facing-message]",
    "silently drops agent-facing text and split test suites when run from a subdirectory of the checkout",
    "agent-facing string collector's scope rules",
    "2393-base-the-agent-facing-string-collector-s-scope",
    "base-the-agent-facing-string-collector-scope-",
)
# A cold-read-record's directory name in the log-store.
HISTORY_PATTERN = re.compile(r"[A-Za-z0-9._/-]*-agent-facing-message-\d{4}-\d{2}-\d{2}")

# Applied in order; each later rule sees the text the earlier ones left.
REWRITES = (
    (r"python-edit-changed-agent-facing-message-check-reminder",
     "python-edit-changed-tool-message-to-agent-strings-check-reminder"),
    (r"python_edit_changed_agent_facing_message_check_reminder",
     "python_edit_changed_tool_message_to_agent_strings_check_reminder"),
    (r"how-to-write-an-agent-facing-message", "how-to-write-a-tool-message-to-agent"),
    (r"\b([Aa])n agent-facing[- ]message\b", r"\1 tool-message-to-agent"),
    (r"agent-facing-message\(s\)", "tool-message(s)-to-agent"),
    # The reminder hook's test checks for the end of that plural.
    (r'"\(s\), text" in text', '"(s)-to-agent, text" in text'),
    (r"\bagent-facing[- ]messages\b", "tool-messages-to-agent"),
    (r"\bAgent-facing messages\b", "Tool-messages-to-agent"),
    (r"\bagent-facing[- ]message\b", "tool-message-to-agent"),
    (r"which strings are agent-facing and", "which strings are tool-messages-to-agent and"),
    (r"# Agent-facing: ", "# Tool-messages-to-agent: "),
    (r"\bagent-facing([-\s])", r"tool-message-to-agent\1"),
    (r"\bAgent-facing(\s)", r"Tool-message-to-agent\1"),
    (r"\bAGENT-FACING ", "TOOL-MESSAGE-TO-AGENT "),
    (r"agent_facing_message", "tool_message_to_agent"),
    (r"agent_facing", "tool_message_to_agent"),
    (r"AGENT_FACING_MESSAGE", "TOOL_MESSAGE_TO_AGENT"),
    (r"AGENT_FACING", "TOOL_MESSAGE_TO_AGENT"),
)
GLOSSARY = "docs/nedschorus-wiki/nedschorus-glossary.md"
GLOSSARY_ENTRY_START = "- **tool-message-to-agent**"
# The glossary is in alphabetical order, word by word; the renamed entry goes just above this one.
GLOSSARY_ENTRY_AFTER_START = "- **topic-worktree**"
LEFTOVER = re.compile(r"agent[-_ ]facing", re.IGNORECASE)


def git(*arguments) -> str:
    # git's stderr goes to the terminal, so a failed git mv shows why before the traceback.
    return subprocess.run(["git", *arguments], check=True, stdout=subprocess.PIPE, text=True).stdout


def is_history_file(path: str) -> bool:
    return any(path == entry or (entry.endswith("/") and path.startswith(entry)) for entry in HISTORY_FILES)


def masked(text: str):
    """The text with each history string replaced by a placeholder, and the strings in order."""
    kept = []

    def keep(match):
        kept.append(match.group(0))
        return f"\x00{len(kept) - 1}\x00"

    pattern = re.compile("|".join([HISTORY_PATTERN.pattern] + [re.escape(s) for s in HISTORY_STRINGS]))
    return pattern.sub(keep, text), kept


def unmasked(text: str, kept) -> str:
    return re.sub("\x00(\\d+)\x00", lambda match: kept[int(match.group(1))], text)


def rewritten(text: str) -> str:
    text, kept = masked(text)
    for pattern, replacement in REWRITES:
        text = re.sub(pattern, replacement, text)
    return unmasked(text, kept)


def glossary_entry_moved_to_its_alphabetical_place():
    lines = Path(GLOSSARY).read_text(encoding="utf-8").split("\n")
    entry = lines.pop(next(n for n, line in enumerate(lines) if line.startswith(GLOSSARY_ENTRY_START)))
    after = next(n for n, line in enumerate(lines) if line.startswith(GLOSSARY_ENTRY_AFTER_START))
    lines.insert(after, entry)
    Path(GLOSSARY).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    for new in MOVED_FILES_NEW_PATHS:
        old = new
        for new_part, old_part in OLD_NAME_PARTS:
            old = old.replace(new_part, old_part)
        if Path(old).exists():
            git("mv", old, new)
    leftovers = []
    for path in git("ls-files", "-z").split("\0"):
        if not path or is_history_file(path) or not Path(path).is_file():
            continue
        try:
            text = Path(path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if not LEFTOVER.search(text):
            continue
        new_text = rewritten(text)
        if new_text != text:
            Path(path).write_text(new_text, encoding="utf-8")
        remaining, _ = masked(new_text)
        for number, line in enumerate(remaining.splitlines(), 1):
            if LEFTOVER.search(line):
                leftovers.append(f"{path}:{number}: {line.strip()[:200]}")
    glossary_entry_moved_to_its_alphabetical_place()
    if leftovers:
        print("These lines still hold the old term in a form this script has no rule for. "
              "Add a rewrite rule or a history string for each, then run the script again:")
        print("\n".join(leftovers))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
