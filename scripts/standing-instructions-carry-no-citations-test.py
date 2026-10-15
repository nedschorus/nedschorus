#!/usr/bin/env python3
"""Fail when a standing instruction file carries a date or a ruling marker,
the two patterns in MARKER_PATTERNS.

Standing instructions hold what an agent must do. A line that records when the
user decided tells the agent nothing to do; that history belongs in the commit
message and the pull request. The files checked are every git-tracked
CLAUDE.md, SKILL.md, *-instructions.md and *-prompt.md.

Links and paths are not checked: a date inside a markdown link target, a URL,
or a path or file name such as `docs/walk/x-YYYY-MM-DD.md` is a pointer an
agent may follow, so it stays. A date that is itself an instruction, such as
the example in a citation's form, goes in EXCEPTIONS with its reason.

Run: python3 scripts/standing-instructions-carry-no-citations-test.py
Prints one line per case and exits 1 if any case fails.
"""
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

REPOSITORY = Path(__file__).resolve().parent.parent
SUITE = "scripts/standing-instructions-carry-no-citations-test.py"

# git's pathspec `*` crosses directories, so `*-prompt.md` finds the file at any depth.
STANDING_INSTRUCTION_PATHSPECS = ("CLAUDE.md", "*/CLAUDE.md", "SKILL.md", "*/SKILL.md",
                                  "*-instructions.md", "*-prompt.md")

# A date joined to a path or file name, such as `x-YYYY-MM-DD.md` or
# `logs/YYYY-MM-DD/`, is a pointer, so the lookarounds leave it out.
MARKER_PATTERNS = {
    "date": re.compile(r"(?<![\w/.-])\d{4}-[01]\d-[0-3]\d(?![\w/-]|\.\w)"),
    "user-ruled": re.compile(r"\buser-ruled\b", re.IGNORECASE),
}

POINTER_PATTERNS = (
    re.compile(r"\]\([^)\s]*\)"),     # a markdown link's target
    re.compile(r"\bhttps?://\S+"),    # a URL
)

# (path, a snippet of the line that holds the marker): the reason the marker
# is an instruction. A line holding the snippet is skipped.
EXCEPTIONS = {
    (".claude/skills/explain/SKILL.md", "a `(user-ruled …)` line in a file"):
        "tells the agent the form a recorded ruling takes in a file, so the agent can find one",
    ("nc-systems/skills/explain/explain-how-to-write-an-identifier-instructions.md",
     '`ruled 2026-09-15 at "<which walk or'):
        "an example of a citation's form, which the agent copies when it cites a ruling",
}


def without_pointers(text):
    for pattern in POINTER_PATTERNS:
        text = pattern.sub(" ", text)
    return text


def markers_in(path, source, exceptions=EXCEPTIONS):
    """Return [(line number, kind, marker, line)] for the markers in one file."""
    snippets = [snippet for (excepted_path, snippet) in exceptions if excepted_path == path]
    found = []
    for number, line in enumerate(source.splitlines(), start=1):
        if any(snippet in line for snippet in snippets):
            continue
        checked = without_pointers(line)
        for kind, pattern in MARKER_PATTERNS.items():
            found.extend((number, kind, match.group(), line) for match in pattern.finditer(checked))
    return found


def standing_instruction_paths(repository):
    listing = subprocess.run(
        ["git", "-C", str(repository), "ls-files", "-z", "--", *STANDING_INSTRUCTION_PATHSPECS],
        capture_output=True, text=True, check=True).stdout
    return sorted(path for path in listing.split("\0") if path)


def stale_exceptions(sources, exceptions=EXCEPTIONS):
    """The exceptions whose snippet no line of their file holds."""
    return sorted(
        (path, snippet) for (path, snippet) in exceptions
        if not any(snippet in line for line in sources.get(path, "").splitlines()))


def scan_tree(repository):
    """Return ({path: markers} for files with markers, stale exceptions, files listed)."""
    paths = standing_instruction_paths(repository)
    sources = {path: (repository / path).read_text(encoding="utf-8") for path in paths}
    failures = {path: found for path, source in sources.items()
                if (found := markers_in(path, source))}
    return failures, stale_exceptions(sources), len(paths)


def the_file_listing_takes_exactly_the_standing_instruction_files():
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        subprocess.run(["git", "init", "-q", str(scratch)], check=True)
        names = ["CLAUDE.md", "x/CLAUDE.md", "x/y/SKILL.md", "a-instructions.md",
                 "x/b-prompt.md", "c-design.md", "NOTCLAUDE.md", "x/SKILL.md.bak"]
        for name in names:
            (scratch / name).parent.mkdir(parents=True, exist_ok=True)
            (scratch / name).write_text("text\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(scratch), "add", "--", *names], check=True)
        listed = standing_instruction_paths(scratch)
    return listed == sorted(["CLAUDE.md", "x/CLAUDE.md", "x/y/SKILL.md",
                             "a-instructions.md", "x/b-prompt.md"])


def the_suite_run_with_git_dir_set_still_scans_this_repository():
    # A child copy of this suite, started with GIT_DIR naming an empty repository.
    with tempfile.TemporaryDirectory() as scratch:
        subprocess.run(["git", "init", "-q", "--bare", scratch], check=True)
        environment = dict(os.environ, GIT_DIR=scratch, STANDING_INSTRUCTIONS_SUITE_CHILD="1")
        child = subprocess.run([sys.executable, __file__], capture_output=True, text=True,
                               env=environment)
    return "PASS  git ls-files lists this repository's standing instruction files" in child.stdout


def kinds(text, path="x/SKILL.md", exceptions=None):
    return [kind for _, kind, _, _ in markers_in(path, text, exceptions or {})]


def report(failures):
    for path, found in sorted(failures.items()):
        print(f"FAILED: {path} carries {len(found)} date or ruling markers; a standing instruction "
              f"file holds instructions, and when the user ruled belongs in the commit message "
              f"and the pull request.")
        lines = {}
        for number, kind, marker, line in found:
            lines.setdefault((number, line), []).append(marker)
        for (number, line), markers in lines.items():
            print(f"  {path}:{number}: {', '.join(markers)}: {line.strip()}")
    if failures:
        print("When the date or ruling is history, delete it, and keep any instruction on its line.")
        print(f"When the date is an instruction, such as an example of a citation's form, add the "
              f"file and a snippet of its line to EXCEPTIONS in {SUITE}, with the reason.")


def check(name, condition):
    print(f"{'PASS' if condition else 'FAIL'}  {name}")
    return condition


def main():
    results = [
        check("a date in prose is found",
              kinds("Adopted 2026-08-17 by the user.\n") == ["date"]),
        check("a date that ends a sentence is found",
              kinds("The user ruled on 2026-08-17.\n") == ["date"]),
        check("the word user-ruled is found, in any case",
              kinds("(user-ruled)\n(User-Ruled)\n") == ["user-ruled", "user-ruled"]),
        check("user-ruling, the glossary's noun, and a bare ruled are not markers",
              kinds("Re-read the user-ruling; he ruled on it.\n") == []),
        check("a date in a markdown link's target is not checked",
              kinds("See [the walk](docs/walk/x.md#2026-10-12).\n") == []),
        check("a date in a URL is not checked",
              kinds("See https://example.com/log?day=2026-10-12 for it.\n") == []),
        check("a date in a file name or a path is not checked",
              kinds("Read `docs/walk/open-2026-10-14.md` and logs/2026-10-14/x, "
                    "or 2026-10-14-minutes.md, on branch walk-2026-10-14 now.\n") == []),
        check("a line holding an exception's snippet is skipped, and only in that file",
              kinds("ruled 2026-09-15 at x\n", "a.md", {("a.md", "ruled 2026-09-15"): "r"}) == []
              and kinds("ruled 2026-09-15 at x\n", "b.md", {("a.md", "ruled 2026-09-15"): "r"})
              == ["date"]),
        check("an exception whose snippet no line holds is reported as stale",
              stale_exceptions({"a.md": "other text\n"}, {("a.md", "gone"): "r"})
              == [("a.md", "gone")]),
        check("every exception's snippet holds a date or user-ruled, and has a reason",
              all(reason and any(pattern.search(snippet) for pattern in MARKER_PATTERNS.values())
                  for (_, snippet), reason in EXCEPTIONS.items())),
    ]
    if not os.environ.get("STANDING_INSTRUCTIONS_SUITE_CHILD"):
        results.append(check("run with GIT_DIR set, the suite still scans this repository",
                             the_suite_run_with_git_dir_set_still_scans_this_repository()))
        results.append(check("the listing takes every CLAUDE.md, SKILL.md, -instructions.md and "
                             "-prompt.md file, at any depth, and no other file",
                             the_file_listing_takes_exactly_the_standing_instruction_files()))
    failures, stale, listed = scan_tree(REPOSITORY)
    results.append(check("git ls-files lists this repository's standing instruction files",
                         listed > 0))
    results.append(check("every exception still names a line in its file"
                         + (f"; these do not: {stale}" if stale else ""), not stale))
    report(failures)
    results.append(check("no standing instruction file carries a date or the word user-ruled",
                         not failures))
    if all(results):
        print("all cases passed")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
