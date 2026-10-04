#!/usr/bin/env python3
"""Fail when a Python comment or docstring carries a history marker: an ISO
date, a ruling, a pull request or issue number, or a commit hash.

History belongs in the commit message and the pull request. Agents copy the
comment style of the code around them, so one history comment breeds more.
"""
import ast
import importlib.util
import io
import os
import re
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

REPOSITORY = Path(__file__).resolve().parent.parent
SUITE = "scripts/python-comments-carry-no-history-markers-test.py"

MARKER_PATTERNS = {
    "date": re.compile(r"\b20\d\d-[01]\d-[0-3]\d\b"),
    "ruling": re.compile(r"\b(?:user-)?ruled\b", re.IGNORECASE),
    "pull request or issue number": re.compile(
        r"\b(?:PR|GHI|issue)\s+#?\d{2,5}\b|(?<![\w&])#\d{2,5}\b|\bnedschorus#\d+\b"),
    "commit hash": re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b"),
}

# Files that still carried markers when this suite landed, each with the most
# markers it may hold: awaiting the comment trim. A file may only go down.
FILES_AWAITING_THE_COMMENT_TRIM = {
    ".claude/hooks/backup-and-snapshot-write-guard-test.py": 3,
    ".claude/hooks/ghi-issue-write-redirect-test.py": 2,
    ".claude/hooks/ghi-issue-write-redirect.py": 21,
    ".claude/hooks/instruction-file-guard-test.py": 8,
    ".claude/hooks/session-location-write-guard-test.py": 6,
    "nc-systems/cold-read/cold-read-agy-cell.py": 14,
    "nc-systems/cold-read/cold-read-claude-cell.py": 3,
    "nc-systems/cold-read/cold-read-codex-cell.py": 22,
    "nc-systems/cold-read/cold-read-fast-read.py": 24,
    "nc-systems/cold-read/cold-read-grid.py": 16,
    "nc-systems/cold-read/cold-read-record-ship.py": 15,
    "nc-systems/cold-read/cold-read-restater-judge-cell.py": 11,
    "nc-systems/cold-read/cold-read-restater-judge-runner.py": 6,
    "nc-systems/cold-read/tests/cold-read-agy-cell-test.py": 10,
    "nc-systems/cold-read/tests/cold-read-cell-common-test.py": 72,
    "nc-systems/cold-read/tests/cold-read-codex-cell-test.py": 4,
    "nc-systems/cold-read/tests/cold-read-fast-read-test.py": 30,
    "nc-systems/cold-read/tests/cold-read-grid-test.py": 53,
    "nc-systems/cold-read/tests/cold-read-record-names-test.py": 5,
    "nc-systems/cold-read/tests/cold-read-record-ship-test.py": 20,
    "nc-systems/cold-read/tests/cold-read-restater-judge-cell-test.py": 6,
    "nc-systems/cold-read/tests/cold-read-restater-judge-runner-test.py": 4,
    "nc-systems/cold-read/tests/cold-read-reviewer-score-test.py": 5,
    "nc-systems/cold-read/tests/cold-read-scratch-repository-fixture-ignores-git-redirecting-environment-test.py": 3,
    "nc-systems/cold-read/tests/cold-read-scratch-repository-test-fixture.py": 9,
    "nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py": 6,
    "nc-systems/general-tools/tests/install-scheduled-jobs-on-this-machine-test.py": 1,
    "nc-systems/handoff/handoff-supervisor.py": 7,
    "nc-systems/handoff/handoff-write-and-check-supervisor.py": 1,
    "nc-systems/handoff/tests/daily-memory-review-mark-test.py": 4,
    "nc-systems/handoff/tests/daily-overview-refresh-reminder-mark-test.py": 4,
    "nc-systems/handoff/tests/handoff-supervisor-session-end-and-resume-test.py": 26,
    "nc-systems/handoff/tests/handoff-supervisor-session-launch-and-seat-lock-test.py": 19,
    "nc-systems/handoff/tests/handoff-supervisor-successor-prompt-test.py": 82,
    "nc-systems/handoff/tests/handoff-write-and-check-supervisor-test.py": 39,
    "nc-systems/main-gatekeeper/tests/main-gatekeeper-test.py": 62,
    "nc-systems/skills/explain/tests/explain-reply-cold-read-fast-read-test.py": 3,
    "scripts/backup-health-check-test.py": 1,
    "scripts/backup-health-check.py": 2,
    "scripts/branch-conflict-check-test.py": 20,
    "scripts/checkout-freshness-catch-up-test.py": 43,
    "scripts/checkout-freshness-catch-up.py": 85,
    "scripts/clean-worktrees-test.py": 5,
    "scripts/clean-worktrees.py": 3,
    "scripts/code-review-codex-cell-test.py": 12,
    "scripts/code-review-codex-cell.py": 25,
    "scripts/daily-full-test-run-of-main-test.py": 4,
    "scripts/daily-full-test-run-of-main.py": 8,
    "scripts/dangling-path-citation-check-test.py": 11,
    "scripts/design-to-main/design-to-main-state-diagram-generator.py": 5,
    "scripts/design-to-main/tests/design-to-main-counters-contract-revisions-redesigns-and-resets-test.py": 2,
    "scripts/design-to-main/tests/design-to-main-counters-write-and-ruling-ceilings-test.py": 9,
    "scripts/design-to-main/tests/design-to-main-design-names-exist-in-state-tables-test.py": 2,
    "scripts/design-to-main/tests/design-to-main-design-rows-pair-with-state-tables-test.py": 6,
    "scripts/design-to-main/tests/design-to-main-scenario-runner-test.py": 10,
    "scripts/design-to-main/tests/design-to-main-state-diagram-generator-test.py": 4,
    "scripts/design-to-main/tests/design-to-main-transitions-test.py": 7,
    "scripts/design-to-main/tests/design-to-main-whole-run-arbitrator-test.py": 17,
    "scripts/design-to-main/tests/design-to-main-whole-run-investigations-test.py": 3,
    "scripts/design-to-main/tests/design-to-main-whole-run-record-and-recovery-test.py": 17,
    "scripts/design-to-main/tests/design-to-main-whole-run-work-streams-and-redesigns-test.py": 15,
    "scripts/file-name-collision-warning-hook-test.py": 5,
    "scripts/find-deleted-path-across-backups-test.py": 37,
    "scripts/find-deleted-path-across-backups.py": 33,
    "scripts/force-push-with-open-pull-request-guard-hook-test.py": 2,
    "scripts/ghi-info-ask-test.py": 18,
    "scripts/ghi-info-ask.py": 38,
    "scripts/ghi-issue-body-edit-test.py": 2,
    "scripts/ghi-issue-body-edit.py": 10,
    "scripts/ghi-issue-write-test.py": 38,
    "scripts/ghi-issue-write.py": 76,
    "scripts/ghi-mirror-refresh-test.py": 4,
    "scripts/ghi-mirror-refresh.py": 2,
    "scripts/ghi-prose-body-migration-test.py": 1,
    "scripts/git-client-side-hooks-pre-commit-test.py": 4,
    "scripts/git-client-side-hooks-pre-push-test.py": 1,
    "scripts/git-redirecting-environment-removal-test-fixture.py": 3,
    "scripts/handoff-context-threshold-hook-test.py": 24,
    "scripts/handoff-extract-conversation-test.py": 4,
    "scripts/install-restart-live-seats-at-login-launch-agent-test.py": 1,
    "scripts/install-restart-live-seats-at-login-launch-agent.py": 2,
    "scripts/install-restart-live-seats-at-login-systemd-unit-test.py": 5,
    "scripts/install-restart-live-seats-at-login-systemd-unit.py": 4,
    "scripts/launch-claude-mac-test.py": 18,
    "scripts/launch-claude-pre-trust-step-test.py": 5,
    "scripts/launch-claude-ubuntu-test.py": 20,
    "scripts/locate-file-copies-across-machines-test.py": 19,
    "scripts/md-drift-lint-test.py": 21,
    "scripts/md-drift-lint.py": 1,
    "scripts/merge-gate-test.py": 19,
    "scripts/nedschorus-glossary-alphabetical-order-test.py": 10,
    "scripts/obsolete-file-edit-warning-hook-test.py": 6,
    "scripts/obsolete-file-edit-warning-hook.py": 18,
    "scripts/open-iterm-window-running-command-test.py": 3,
    "scripts/post-compaction-session-continues-hook-test.py": 1,
    "scripts/pr-reviewer-instructions-copies-test.py": 5,
    "scripts/protection-experiment-dismiss-stale-reviews-test.py": 11,
    "scripts/protection-experiment-dismiss-stale-reviews.py": 12,
    "scripts/recover-crashed-seats-test.py": 168,
    "scripts/recover-crashed-seats.py": 31,
    "scripts/restart-live-seats-at-login-test.py": 38,
    "scripts/restart-live-seats-at-login.py": 17,
    "scripts/resupervise-seat-test.py": 24,
    "scripts/resupervise-seat.py": 10,
    "scripts/run-all-test-suites-test.py": 8,
    "scripts/run-all-test-suites.py": 24,
    "scripts/sanity-check-attacks-test.py": 47,
    "scripts/sanity-check-attacks.py": 93,
    "scripts/sanity-check-record-ship-test.py": 4,
    "scripts/sanity-check-record-ship.py": 5,
    "scripts/seat-shared-file-ship-test.py": 10,
    "scripts/seat-task-list-read-test.py": 7,
    "scripts/session-statusline-command-test.py": 3,
    "scripts/stale-code-citation-check-test.py": 3,
    "scripts/supervisor-file-names-defined-once-test.py": 32,
    "scripts/synthetic-keystroke-guard-hook-test.py": 5,
    "scripts/system-glossaries-listed-on-the-project-glossary-test.py": 11,
    "scripts/test-suites-run-directly-ignore-git-redirecting-environment-test.py": 4,
    "scripts/transcript-mirror-to-log-store.py": 9,
    "scripts/walk-file-endings-match-the-skill-test.py": 3,
    "scripts/walk-files-ship-test.py": 12,
    "scripts/walk-files-ship.py": 12,
    "scripts/watch-agent-dialog-alerts-test.py": 7,
    "scripts/watch-agent-dialogs-test.py": 2,
}

# Lines whose marker is data the code needs, not history: "path:line": reason.
ALLOWED_DATA_LINES = {
}


def comment_and_docstring_lines(source):
    """Yield (line number, text) for every comment and docstring line."""
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                yield token.start[0], token.string
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) \
                    and isinstance(first.value.value, str):
                for offset, text in enumerate(first.value.value.splitlines()):
                    yield first.lineno + offset, text


def markers_in(path, source):
    """Return [(line, kind, marker)] for the history markers in one file."""
    found = []
    for line, text in comment_and_docstring_lines(source):
        if f"{path}:{line}" in ALLOWED_DATA_LINES:
            continue
        for kind, pattern in MARKER_PATTERNS.items():
            found.extend((line, kind, match.group()) for match in pattern.finditer(text))
    return found


def scan_tree(repository):
    """Return (failures, paths that do not parse, number of .py files listed)."""
    paths = subprocess.run(["git", "-C", str(repository), "ls-files", "*.py"],
                           capture_output=True, text=True, check=True).stdout.split()
    failures, unparseable = [], []
    for path in paths:
        source = (repository / path).read_text(encoding="utf-8")
        try:
            ast.parse(source)
            list(tokenize.generate_tokens(io.StringIO(source).readline))
        except (SyntaxError, tokenize.TokenError):
            unparseable.append(path)
            continue
        found = markers_in(path, source)
        ceiling = FILES_AWAITING_THE_COMMENT_TRIM.get(path, 0)
        if len(found) > ceiling:
            failures.append((path, found, ceiling))
    return failures, unparseable, len(paths)


def a_file_that_does_not_parse_is_reported():
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        subprocess.run(["git", "init", "-q", str(scratch)], check=True)
        (scratch / "broken.py").write_text("def (:\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(scratch), "add", "broken.py"], check=True)
        _, unparseable, listed = scan_tree(scratch)
    return unparseable == ["broken.py"] and listed == 1


def the_suite_run_with_git_dir_set_still_scans_this_repository():
    # A child copy of this suite, started with GIT_DIR naming an empty repository.
    with tempfile.TemporaryDirectory() as scratch:
        subprocess.run(["git", "init", "-q", "--bare", scratch], check=True)
        environment = dict(os.environ, GIT_DIR=scratch, HISTORY_MARKER_SUITE_CHILD="1")
        child = subprocess.run([sys.executable, __file__], capture_output=True, text=True,
                               env=environment)
    return child.returncode == 0 and "PASS  git ls-files lists this repository's .py files" in child.stdout


def report(failures):
    for path, found, ceiling in failures:
        print(f"FAILED: {path} — {len(found)} history markers in comments and docstrings, "
              f"where {ceiling} are allowed; history belongs in the commit message and the "
              f"pull request, not in the code.")
        for line, kind, marker in found:
            print(f"  {path}:{line}: {kind}: {marker}")
    if failures:
        print("When a marker is history, delete it, or move what it records to your commit message.")
        print(f"When a marker is data the code needs, such as a date the code compares against, "
              f"add its line to ALLOWED_DATA_LINES in {SUITE} with the reason.")


def check(name, condition):
    print(f"{'PASS' if condition else 'FAIL'}  {name}")
    return condition


def main():
    results = [
        check("a date, a ruling, an issue number and a commit hash in a comment are each found",
              {kind for _, kind, _ in markers_in("x.py", "# 2026-09-30 user-ruled, PR 931, fix in a82b49e\n")}
              == set(MARKER_PATTERNS)),
        check("a docstring's marker is found, and a string that is not a docstring is not",
              [k for _, k, _ in markers_in("x.py", 'def f():\n    """See GHI 913."""\n    return "2026-09-30"\n')]
              == ["pull request or issue number"]),
        check("plain words and hex-free numbers are not markers",
              markers_in("x.py", "# deadbeef retries 1234567 times; feed the cafe\n") == []),
        check("a line in ALLOWED_DATA_LINES is skipped",
              all(not markers_in(key.rsplit(":", 1)[0], "") for key in ALLOWED_DATA_LINES)),
    ]
    if not os.environ.get("HISTORY_MARKER_SUITE_CHILD"):
        results.append(check("run with GIT_DIR set, the suite still scans this repository",
                             the_suite_run_with_git_dir_set_still_scans_this_repository()))
        results.append(check("a tracked .py file that does not parse is reported, not skipped",
                             a_file_that_does_not_parse_is_reported()))
    failures, unparseable, listed = scan_tree(REPOSITORY)
    results.append(check("git ls-files lists this repository's .py files", listed > 0))
    results.append(check("every tracked .py file parses"
                         + (f"; these do not: {', '.join(unparseable)}" if unparseable else ""),
                         not unparseable))
    report(failures)
    results.append(check("no tracked .py file carries more history markers than it is allowed", not failures))
    if all(results):
        print("all cases passed")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
