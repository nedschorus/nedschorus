#!/usr/bin/env python3
"""Cases for design-ghi-md-approval-walk-minutes-and-cold-read-records-user-turns-with-file-and-line-extract.py,
run against a throwaway repository, log-store and agents directory.

Run: scripts/design-ghi-md-approval-walk-minutes-and-cold-read-records-user-turns-with-file-and-line-extract-test.py
Exit codes: 0 all passed, 1 any failed.
"""

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parent / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = (Path(__file__).resolve().parent
           / "design-ghi-md-approval-walk-minutes-and-cold-read-records-user-turns-with-file-and-line-extract.py")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(checkout, *arguments):
    subprocess.run(["git", "-C", str(checkout), *arguments], check=True, capture_output=True)


def build(root):
    checkout, log_store, agents = root / "checkout", root / "logs", root / "agents"
    checkout.mkdir()
    git(checkout, "init", "-q")
    git(checkout, "config", "user.email", "test@example.invalid")
    git(checkout, "config", "user.name", "test")
    write(checkout / "docs/issues/5-old-name-design.md", "---\nkind: design\n---\n\n# Five\n")
    write(checkout / "docs/issues/6-not-a-design.md", "# Six\n")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "one")
    git(checkout, "mv", "docs/issues/5-old-name-design.md", "docs/issues/5-new-name-design.md")
    git(checkout, "commit", "-q", "-m", "rename")

    records = log_store / "cold-read-records"
    # Found only by the old file name in its target/, as a renamed design's first records are.
    write(records / "first-review-2026-10-01/target/docs/issues/5-old-name-design.md", "# Five\n")
    write(records / "first-review-2026-10-01/triage.md",
          "# Triage\nA1: the user ruled \"keep it small\" (walk x, item 2).\nA2: agent fixed a typo.\n")
    write(records / "6-plain-2026-10-02/cold-read-triage.md", "the user ruled on six\n")

    walk = log_store / "walk"
    write(walk / "first-review-2026-10-01-minutes.md",
          "# Minutes\n## Item 1 — scope\nThe user, 2026-10-01: \"Why not code?\" <rejected>\nAgent note.\n")
    write(walk / "5-later-walk-minutes.md", "# Later\nitem 1 of 2: the user answered approved (2026-10-02 10:00), "
          "which makes its change. Fast reads:\n")
    write(walk / "mixed-topics-minutes.md", "# Mixed\n## Item 3\nOn GHI 5, he asked \"what does the user see?\"\n")
    write(walk / "other-design-minutes.md", "# Other\nOn GHI 55 the user said \"no\".\n")
    # Bare speaker labels, as the older walk-minutes write them, and a quotation hard-wrapped over two lines.
    write(walk / "5-labels-minutes.md",
          "# Labels\n"
          "User: \"Why is it skipped?\"\n"
          "  - User: \"does this cover designs too?\"\n"
          "User asked whether the count is right.\n"
          "User (2026-10-19): keep it.\n"
          "RULING: close it.\n"
          "Rulings recorded: both items.\n"
          "Quoting his words: \"no guard\".\n"
          "User-facing text changed.\n"
          "3. Whether to close it: the user asked the direct question, \"is 120\n"
          "   done or not. If done, then close it,\" and it is\n"
          "   done: verified.\n"
          "\n"
          "Agent note.\n")
    # Where a user turn's following lines stop: a list item, a heading, another user turn, a blank line. Line 2
    # is the nested, truncated quotation that once swallowed the next item's walk record.
    write(walk / "5-stops-minutes.md",
          "# Stops\n"
          "- Item 34: the user answered \"keep the \"old name and\n"
          "item 35 of 42: the user answered approved (2026-11-05 10:00).\n"
          "  agent note one\n"
          "- Item 36: agent narrative.\n"
          "RULING: keep it,\n"
          "  wrapped on.\n"
          "## Next item\n"
          "User: \"y\"\n"
          "said on.\n"
          "\n"
          "Agent note.\n")
    # A user turn followed by more plain lines than FOLLOWING_LINES_LIMIT, with no stop among them.
    write(walk / "5-cap-minutes.md",
          "# Cap\nUser: \"keep going\n" + "".join(f"plain line {n}\n" for n in range(1, 26)))
    # The agent-seat's copy loses to the log-store's copy of the same name.
    write(agents / "seat-a/docs/walk/mixed-topics-minutes.md", "# Stale\nissues/5 the user said \"stale\"\n")
    write(agents / "seat-a/docs/walk/seat-only-minutes.md", "# Seat\nSee issues/5). The user: \"seat copy\"\n")
    return checkout, log_store, agents


def run(*arguments):
    return subprocess.run([sys.executable, str(PROGRAM), *arguments], capture_output=True, text=True)


def main():
    failures = []

    def check(name, condition, detail=""):
        if not condition:
            failures.append(f"{name}: {detail}")

    with tempfile.TemporaryDirectory() as temporary:
        checkout, log_store, agents = build(Path(temporary))
        done = run("--repository-checkout", str(checkout), "--log-store", str(log_store),
                   "--agents-directory", str(agents))
        check("exit 0", done.returncode == 0, done.stderr)
        rows = [json.loads(line) for line in done.stdout.splitlines()]
        found = {(Path(row["source"]).name, row["line"]): row for row in rows}

        check("only the design is read", {row["design"] for row in rows} == {"docs/issues/5-new-name-design.md"},
              {row["design"] for row in rows})
        minutes = found.get(("first-review-2026-10-01-minutes.md", 3))
        check("walk named after a record found by a past file name", minutes is not None, sorted(found))
        if minutes:
            check("record-name match", minutes["walk_minutes_match"] == "record-name", minutes)
            check("heading carried", minutes["heading"] == "Item 1 — scope", minutes)
        check("agent narrative not printed", ("first-review-2026-10-01-minutes.md", 4) not in found)
        check("number-prefix match",
              found.get(("5-later-walk-minutes.md", 2), {}).get("walk_minutes_match") == "number-prefix", found)
        mixed = found.get(("mixed-topics-minutes.md", 3), {})
        check("cites match, log-store copy wins", mixed.get("walk_minutes_match") == "cites"
              and str(log_store) in mixed.get("source", ""), mixed)
        check("agent-seat copy read when the log-store has none", ("seat-only-minutes.md", 2) in found, sorted(found))
        check("GHI 55 is not GHI 5", not any(name == "other-design-minutes.md" for name, _ in found))
        triage = found.get(("triage.md", 2), {})
        check("triage line from the design's record", triage.get("source_kind") == "cold-read-triage", triage)
        check("other design's record not read", ("cold-read-triage.md", 1) not in found)
        labels = {line for name, line in found if name == "5-labels-minutes.md"}
        for line, form in ((2, "User:"), (3, "- User:"), (4, "User asked"), (5, "User (date):"), (6, "RULING:"),
                           (7, "Rulings recorded:"), (8, "his words without in")):
            check(f"bare label {form} printed", line in labels, sorted(labels))
        check("User-facing is no speaker", 9 not in labels, sorted(labels))
        wrapped = found.get(("5-labels-minutes.md", 10), {})
        check("wrapped line's following lines printed with their line numbers, up to the blank line",
              wrapped.get("following_lines") == [{"line": 11, "text": "   done or not. If done, then close it,\" and it is"},
                                                 {"line": 12, "text": "   done: verified."}],
              wrapped)
        check("no following lines before a user turn", found.get(("5-labels-minutes.md", 2), {}).get("following_lines") == [],
              found.get(("5-labels-minutes.md", 2)))
        stops = {line: row.get("following_lines") for (name, line), row in found.items() if name == "5-stops-minutes.md"}
        check("nested truncated quotation stops at the next user turn", stops.get(2) == [], stops)
        check("following lines stop at a list item", stops.get(3) == [{"line": 4, "text": "  agent note one"}], stops)
        check("following lines stop at a heading", stops.get(6) == [{"line": 7, "text": "  wrapped on."}], stops)
        check("following lines stop at a blank line", stops.get(9) == [{"line": 10, "text": "said on."}], stops)
        check("list item that is no user turn is not printed", 5 not in stops, stops)
        capped = found.get(("5-cap-minutes.md", 2), {}).get("following_lines") or []
        check("following lines stop at the limit of 20", [row["line"] for row in capped] == list(range(3, 23)),
              capped)
        check("count line", "docs/issues/5-new-name-design.md: 7 walk-minutes, 1 cold-read-records, 18 user turns"
              in done.stderr, done.stderr)

        missing = run("--log-store", str(Path(temporary) / "absent"))
        check("missing directory exits 2", missing.returncode == 2
              and "--log-store" in missing.stderr and "is not a directory" in missing.stderr, missing.stderr)
        check("a given directory that is missing is named as given, with what to name instead",
              missing.stderr == f"--log-store {Path(temporary) / 'absent'} is not a directory.\n"
              "Run this program again with --log-store naming the log-store, whose walk/*-minutes.md and "
              "cold-read-records/ this program reads.\n", missing.stderr)

        # A default directory cannot be made absent from outside, so the program is loaded and its default
        # pointed at a directory that does not exist.
        spec = importlib.util.spec_from_file_location("user_turns_extract", PROGRAM)
        program = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(program)
        absent = Path(temporary) / "absent-default"
        program.DIRECTORY_COMMAND_LINE_OPTION_TO_DEFAULT_DIRECTORY_AND_FILES_READ_THERE["--log-store"] = (absent, program.DIRECTORY_COMMAND_LINE_OPTION_TO_DEFAULT_DIRECTORY_AND_FILES_READ_THERE["--log-store"][1])
        stderr, sys.stderr = sys.stderr, io.StringIO()
        try:
            code = program.main(["--repository-checkout", str(checkout), "--agents-directory", str(agents)])
            told = sys.stderr.getvalue()
        finally:
            sys.stderr = stderr
        check("a missing default exits 2 and says the option was left out", code == 2 and told ==
              f"--log-store was left out, and its default {absent} is not a directory on this machine.\n"
              "Run this program again with --log-store naming the log-store, whose walk/*-minutes.md and "
              "cold-read-records/ this program reads.\n", (code, told))

    for failure in failures:
        print(f"FAIL {failure}")
    print("all passed" if not failures else f"{len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
