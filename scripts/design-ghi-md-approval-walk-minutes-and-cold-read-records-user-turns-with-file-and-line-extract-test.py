#!/usr/bin/env python3
"""Cases for design-ghi-md-approval-walk-minutes-and-cold-read-records-user-turns-with-file-and-line-extract.py,
run against a throwaway repository, log-store and agents directory.

Run: scripts/design-ghi-md-approval-walk-minutes-and-cold-read-records-user-turns-with-file-and-line-extract-test.py
Exit codes: 0 all passed, 1 any failed.
"""

import importlib.util
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
        check("count line", "docs/issues/5-new-name-design.md: 4 walk-minutes, 1 cold-read-records, 5 user turns"
              in done.stderr, done.stderr)

        missing = run("--log-store", str(Path(temporary) / "absent"))
        check("missing directory exits 2", missing.returncode == 2
              and "--log-store" in missing.stderr and "is not a directory" in missing.stderr, missing.stderr)

    for failure in failures:
        print(f"FAIL {failure}")
    print("all passed" if not failures else f"{len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
