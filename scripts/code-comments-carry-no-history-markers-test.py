#!/usr/bin/env python3
"""Fail when a comment or docstring in a tracked Python file, or a comment in a
tracked shell script, carries a history marker: an ISO date, a ruling, a pull
request or issue number, or a commit hash.

History belongs in the commit message and the pull request. Agents copy the
comment style of the code around them, so one history comment breeds more.
"""
import ast
import contextlib
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

_date_pattern_spec = importlib.util.spec_from_file_location(
    "citation_and_history_marker_tests_date_pattern_common",
    Path(__file__).resolve().with_name("citation-and-history-marker-tests-date-pattern-common.py"))
_date_pattern = importlib.util.module_from_spec(_date_pattern_spec)
_date_pattern_spec.loader.exec_module(_date_pattern)

REPOSITORY = Path(__file__).resolve().parent.parent
SUITE = "scripts/code-comments-carry-no-history-markers-test.py"

MARKER_PATTERNS = {
    "date": _date_pattern.DATE_MARKER_PATTERN,
    "ruling": re.compile(r"\b(?:user-)?ruled\b", re.IGNORECASE),
    "pull request or issue number": re.compile(
        r"\b(?:PR|GHI|issue)\s+#?\d{2,5}\b|(?<![\w&])#\d{2,5}\b|\bnedschorus#\d+\b"),
    "commit hash": re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b"),
}

# Files that still carried markers when this suite landed, each with the most
# markers it may hold: awaiting the comment trim. A file may only go down.
FILES_AWAITING_THE_COMMENT_TRIM = {
    ".claude/hooks/backup-and-snapshot-write-guard-test.py": 3,
    ".claude/hooks/ghi-issue-write-redirect-test.py": 3,
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
    "nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py": 7,
    "nc-systems/general-tools/tests/install-scheduled-jobs-on-this-machine-test.py": 1,
    "nc-systems/handoff/handoff-supervisor.py": 7,
    "nc-systems/handoff/handoff-write-and-check-supervisor.py": 1,
    "nc-systems/handoff/tests/daily-memory-review-mark-test.py": 4,
    "nc-systems/handoff/tests/daily-overview-refresh-reminder-mark-test.py": 4,
    "nc-systems/handoff/tests/handoff-supervisor-session-end-and-resume-test.py": 26,
    "nc-systems/handoff/tests/handoff-supervisor-session-launch-and-seat-lock-test.py": 19,
    "nc-systems/handoff/tests/handoff-supervisor-successor-prompt-test.py": 82,
    "nc-systems/handoff/tests/handoff-write-and-check-supervisor-test.py": 40,
    "nc-systems/main-gatekeeper/tests/main-gatekeeper-test.py": 58,
    "nc-systems/skills/explain/tests/explain-reply-cold-read-fast-read-test.py": 3,
    "scripts/backup-health-check-test.py": 1,
    "scripts/backup-health-check.py": 2,
    "scripts/branch-conflict-check-test.py": 20,
    "scripts/checkout-freshness-catch-up-test.py": 40,
    "scripts/checkout-freshness-catch-up.py": 5,
    "scripts/clean-worktrees-test.py": 5,
    "scripts/clean-worktrees.py": 3,
    "scripts/code-review-codex-cell-test.py": 12,
    "scripts/code-review-codex-cell.py": 25,
    "scripts/daily-full-test-run-of-main-test.py": 4,
    "scripts/daily-full-test-run-of-main.py": 11,
    "scripts/dangling-path-citation-check-test.py": 11,
    "scripts/design-to-main/design-to-main-state-diagram-generator.py": 5,
    "scripts/design-to-main/tests/design-to-main-counters-contract-revision-and-redesign-ceilings-and-zeroing-test.py": 2,
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
    "scripts/ghi-issue-write-test.py": 38,
    "scripts/ghi-issue-write.py": 76,
    "scripts/ghi-mirror-refresh-test.py": 4,
    "scripts/ghi-mirror-refresh.py": 2,
    "scripts/git-client-side-hooks-pre-commit-test.py": 4,
    "scripts/git-client-side-hooks-pre-push-test.py": 1,
    "scripts/git-redirecting-environment-removal-test-fixture.py": 3,
    "scripts/handoff-context-threshold-hook-test.py": 24,
    "scripts/handoff-extract-conversation-test.py": 5,
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
    "scripts/merge-gate-test.py": 20,
    "scripts/nedschorus-glossary-alphabetical-order-test.py": 10,
    "scripts/obsolete-file-edit-warning-hook-test.py": 6,
    "scripts/open-iterm-window-running-command-test.py": 3,
    "scripts/post-compaction-session-continues-hook-test.py": 1,
    "scripts/pr-reviewer-instructions-copies-test.py": 5,
    "scripts/recover-crashed-seats-test.py": 170,
    "scripts/recover-crashed-seats.py": 32,
    "scripts/restart-live-seats-at-login-test.py": 39,
    "scripts/restart-live-seats-at-login.py": 17,
    "scripts/resupervise-seat-test.py": 24,
    "scripts/resupervise-seat.py": 10,
    "scripts/run-all-test-suites-test.py": 8,
    "scripts/run-all-test-suites.py": 24,
    "scripts/sanity-check-adversarial-prompts-test.py": 47,
    "scripts/sanity-check-adversarial-prompts.py": 19,
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
}

# Lines whose marker is data the code needs, not history: (path, text): reason.
# The text is part of the line, keyed by text rather than line number so that an
# edit above the line does not move it; it must be found in exactly one comment
# or docstring line of the file that holds a marker.
ALLOWED_DATA_LINES = {
    ("scripts/agent-seat-due-task-raise-hook.py", 'such as "2026-10-03T09:00:00Z"'):
        "an example of the timestamp form the due_utc field takes",
    ("scripts/transcript-mirror-to-log-store.py", "like `2026-10-03T23:40:12Z`, to MIRROR_PASS_STAMP_FILE_NAME"):
        "an example of the timestamp form the pass stamp file holds",
    ("scripts/locate-user-approval-by-question-subject-test.py", "# 2026-10-01T02:00:00Z"):
        "the time the epoch constant on the same line stands for",
    ("scripts/merge-gate-test.py", "# malfet's approval, 2023-12-14T15:16:51Z"):
        "the time the fixture's pinned review id stands for, in an outside project's data",
}


SHELL_SHEBANG = re.compile(rb"^#!\S*(?:/|\s)(?:ba|da|z)?sh\b")
_shell_reader_spec = importlib.util.spec_from_file_location(
    "shell_command_tree_sitter_bash_reader_common",
    Path(__file__).resolve().parent.parent / "nc-systems" / "general-tools"
    / "shell-command-tree-sitter-bash-reader-common.py")
shell_reader = importlib.util.module_from_spec(_shell_reader_spec)
_shell_reader_spec.loader.exec_module(shell_reader)


class ShellScriptDoesNotParse(ValueError):
    pass


def _bash_reports_a_quote_never_closed(source):
    """Return bash's complaint when bash cannot read source to its end, or None.

    extglob is on, as in a script that turns it on before its first extended
    pattern: bash -n runs no shopt, so without it a valid @(a|b) case pattern
    is a syntax error.
    """
    checked = subprocess.run(["bash", "-O", "extglob", "-n"], input=source, capture_output=True)
    if checked.returncode == 0:
        return None
    return checked.stderr.decode("utf-8", "replace").strip() or f"bash -n exited {checked.returncode}"


def shell_comment_lines(source):
    """Return [(line number, text)] for every comment in a shell script.

    The comments are tree-sitter-bash's own, after the shared reader's
    corrections, the parser and corrections the project's Bash guards use, so
    quoting, command substitution, arithmetic and here-document bodies are read
    as bash reads them. A #! first line is not a comment.

    Raise ShellScriptDoesNotParse when a here-document never closes, or when a
    quote or substitution never closes, as bash -n reports it, because a
    comment after it would go unread. tree-sitter-bash also cannot read some
    valid bash, such as a case pattern made of several quoted parts joined by *,
    and marks that span as an error: a span bash reads, with no # in it, holds
    no comment, so it is passed over, and one with a # in it raises.
    """
    encoded = source.encode("utf-8", "surrogatepass")
    read = shell_reader.shell_source_comments_and_unreadable_spans_after_reader_corrections(encoded)
    if read.heredocs_never_closed:
        raise ShellScriptDoesNotParse(
            f"the here-document {read.heredocs_never_closed[0]} never reaches its closing line")
    if read.missing_tokens:
        token, line = read.missing_tokens[0]
        raise ShellScriptDoesNotParse(f"a {token} that line {line} needs never comes")
    if read.unreadable_spans:
        complaint = _bash_reports_a_quote_never_closed(encoded)
        if complaint:
            raise ShellScriptDoesNotParse(f"bash cannot read it: {complaint}")
        for at, holds_a_hash in read.unreadable_spans:
            if holds_a_hash:
                line = encoded.count(b"\n", 0, at) + 1
                raise ShellScriptDoesNotParse(f"tree-sitter-bash cannot read line {line}, which holds a #")
    return [(encoded.count(b"\n", 0, start) + 1, encoded[start:end].decode("utf-8", "surrogatepass"))
            for start, end in read.comments
            if not (start == 0 and encoded.startswith(b"#!"))]


def python_comment_and_docstring_lines(source):
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


def markers_and_allowed_line_counts(path, source, language="python", allowed=ALLOWED_DATA_LINES):
    """Return ([(line, kind, marker)] for the history markers in one file, outside
    its allowed lines, and {allowed key for this file: how many lines it was found in})."""
    found = []
    counts = {key: 0 for key in allowed if key[0] == path}
    lines = shell_comment_lines(source) if language == "shell" else python_comment_and_docstring_lines(source)
    for line, text in lines:
        markers = [(line, kind, match.group())
                   for kind, pattern in MARKER_PATTERNS.items() for match in pattern.finditer(text)]
        if not markers:
            continue
        allowing = [key for key in counts if key[1] in text]
        for key in allowing:
            counts[key] += 1
        if not allowing:
            found.extend(markers)
    return found, counts


def markers_in(path, source, language="python", allowed=ALLOWED_DATA_LINES):
    """Return [(line, kind, marker)] for the history markers in one file, outside its allowed lines."""
    return markers_and_allowed_line_counts(path, source, language, allowed)[0]


def language_of(repository, path):
    """Return "python", "shell", or None for a file this suite does not read."""
    if path.endswith(".py"):
        return "python"
    if path.endswith(".sh"):
        return "shell"
    if "." in Path(path).name or not (repository / path).is_file():
        return None
    with open(repository / path, "rb") as file:
        return "shell" if SHELL_SHEBANG.match(file.readline()) else None


def scan_tree(repository, allowed=ALLOWED_DATA_LINES):
    """Return (failures, paths that do not parse, {language: number of files listed},
    [(allowed key, number of lines it was found in)] for each key not found in exactly one)."""
    paths = subprocess.run(["git", "-C", str(repository), "ls-files", "-z"],
                           capture_output=True, text=True, check=True).stdout.split("\0")
    failures, unparseable, listed = [], [], {"python": 0, "shell": 0}
    allowed_line_counts = {key: 0 for key in allowed}
    for path in filter(None, paths):
        language = language_of(repository, path)
        if language is None:
            continue
        listed[language] += 1
        source = (repository / path).read_text(encoding="utf-8")
        try:
            if language == "python":
                ast.parse(source)
                list(tokenize.generate_tokens(io.StringIO(source).readline))
            found, counts = markers_and_allowed_line_counts(path, source, language, allowed)
        except (SyntaxError, tokenize.TokenError, ShellScriptDoesNotParse):
            unparseable.append(path)
            continue
        allowed_line_counts.update(counts)
        ceiling = FILES_AWAITING_THE_COMMENT_TRIM.get(path, 0)
        if len(found) > ceiling:
            failures.append((path, found, ceiling))
    misfits = [(key, count) for key, count in allowed_line_counts.items() if count != 1]
    return failures, unparseable, listed, misfits


def a_file_that_does_not_parse_is_reported():
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        subprocess.run(["git", "init", "-q", str(scratch)], check=True)
        (scratch / "broken.py").write_text("def (:\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(scratch), "add", "broken.py"], check=True)
        _, unparseable, listed, _ = scan_tree(scratch)
    return unparseable == ["broken.py"] and listed == {"python": 1, "shell": 0}


def shell_script_does_not_parse(text):
    try:
        shell_comment_lines(text)
    except ShellScriptDoesNotParse:
        return True
    return False


def a_shell_script_that_does_not_parse_is_reported():
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        subprocess.run(["git", "init", "-q", str(scratch)], check=True)
        (scratch / "unclosed-quote").write_text("#!/bin/sh\necho 'never closed\n# PR 931\n",
                                                encoding="utf-8")
        (scratch / "unclosed-heredoc.sh").write_text("cat <<EOF\n# PR 931\n", encoding="utf-8")
        # Valid bash that tree-sitter-bash cannot read, with no # in the span it cannot read.
        (scratch / "case-pattern.sh").write_text(
            'case "$x" in\n  *"a"*"b"*) echo hit ;;\nesac\n', encoding="utf-8")
        subprocess.run(["git", "-C", str(scratch), "add", "."], check=True)
        _, unparseable, listed, _ = scan_tree(scratch)
    return sorted(unparseable) == ["unclosed-heredoc.sh", "unclosed-quote"] \
        and listed == {"python": 0, "shell": 3}


def scan_of_a_scratch_repository(files, allowed):
    """Return scan_tree's (failures, allowed keys not found in exactly one line) for files {path: text}."""
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        subprocess.run(["git", "init", "-q", str(scratch)], check=True)
        for path, text in files.items():
            (scratch / path).write_text(text, encoding="utf-8")
        subprocess.run(["git", "-C", str(scratch), "add", "."], check=True)
        failures, _, _, misfits = scan_tree(scratch, allowed)
    return failures, misfits


ALLOWED_IN_THE_SCRATCH_REPOSITORY = {("data.py", "such as 2026-10-03"): "an example"}


def an_edit_above_an_allowed_line_does_not_break_the_suite():
    edited = "# a new first line\n# and a second\n\n# the form, such as 2026-10-03\n"
    return scan_of_a_scratch_repository({"data.py": edited}, ALLOWED_IN_THE_SCRATCH_REPOSITORY) == ([], [])


def an_allowed_entry_that_matches_no_line_fails():
    stale = [(("data.py", "such as 2026-10-03"), 0)]
    line_changed = scan_of_a_scratch_repository({"data.py": "# such as 2026-10-04\n"},
                                                ALLOWED_IN_THE_SCRATCH_REPOSITORY)
    only_in_code = scan_of_a_scratch_repository({"data.py": "x = 'such as 2026-10-03'\n"},
                                                ALLOWED_IN_THE_SCRATCH_REPOSITORY)
    in_another_file = scan_of_a_scratch_repository({"other.py": "# such as 2026-10-03\n"},
                                                   ALLOWED_IN_THE_SCRATCH_REPOSITORY)
    return line_changed[1] == stale and len(line_changed[0]) == 1 \
        and only_in_code == ([], stale) \
        and in_another_file[1] == stale and len(in_another_file[0]) == 1


def an_allowed_entry_is_counted_only_on_lines_that_hold_a_marker():
    key = ("data.py", "the form")
    _, misfits = scan_of_a_scratch_repository({"data.py": "# the form\n# the form, 2026-10-03\n"},
                                              {key: "an example"})
    return misfits == []


def an_allowed_entry_that_matches_two_lines_fails():
    twice = "# such as 2026-10-03\nx = 1\n# such as 2026-10-03, again\n"
    _, misfits = scan_of_a_scratch_repository({"data.py": twice}, ALLOWED_IN_THE_SCRATCH_REPOSITORY)
    return misfits == [(("data.py", "such as 2026-10-03"), 2)]


def the_repository_checks_fail_on_an_allowed_entry_found_in_no_line():
    def passes(allowed):
        with tempfile.TemporaryDirectory() as scratch:
            scratch = Path(scratch)
            subprocess.run(["git", "init", "-q", str(scratch)], check=True)
            (scratch / "data.py").write_text("# such as 2026-10-03\n", encoding="utf-8")
            (scratch / "run.sh").write_text("echo hi\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(scratch), "add", "."], check=True)
            with contextlib.redirect_stdout(io.StringIO()):
                return all(repository_checks(scratch, allowed))
    stale = {("data.py", "such as 2026-10-03"): "an example", ("data.py", "such as 2026-10-04"): "an example"}
    return passes(ALLOWED_IN_THE_SCRATCH_REPOSITORY) and not passes(stale)


def the_suite_run_with_git_dir_set_still_scans_this_repository():
    # A child copy of this suite, started with GIT_DIR naming an empty repository.
    with tempfile.TemporaryDirectory() as scratch:
        subprocess.run(["git", "init", "-q", "--bare", scratch], check=True)
        environment = dict(os.environ, GIT_DIR=scratch, HISTORY_MARKER_SUITE_CHILD="1")
        child = subprocess.run([sys.executable, __file__], capture_output=True, text=True,
                               env=environment)
    return child.returncode == 0 and "PASS  git ls-files lists this repository's .py files and shell scripts" in child.stdout


def report_allowed_lines(misfits):
    for (path, text), count in misfits:
        print(f"FAILED: the ALLOWED_DATA_LINES entry for {path} with the text {text!r} is found in "
              f"{count} comment or docstring lines that hold a marker, where it must be found in exactly one.")
    if misfits:
        print(f"When an entry is found in no line, because its line or its marker is gone, "
              f"delete the entry from ALLOWED_DATA_LINES in {SUITE}.")
        print("When an entry is found in no line because its line's text changed, "
              "change the entry's text to part of the line as it now reads.")
        print("When an entry is found in two or more lines, lengthen its text until it is found in one.")


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
              f"add the file and part of the line's text to ALLOWED_DATA_LINES in {SUITE} with the reason.")


def check(name, condition):
    print(f"{'PASS' if condition else 'FAIL'}  {name}")
    return condition


def repository_checks(repository, allowed=ALLOWED_DATA_LINES):
    """Scan the repository, print each check and each failure, and return the checks' results."""
    results = []
    failures, unparseable, listed, misfits = scan_tree(repository, allowed)
    results.append(check("git ls-files lists this repository's .py files and shell scripts",
                         listed["python"] > 0 and listed["shell"] > 0))
    results.append(check("every tracked .py file and every tracked shell script parses"
                         + (f"; these do not: {', '.join(unparseable)}" if unparseable else ""),
                         not unparseable))
    report(failures)
    report_allowed_lines(misfits)
    results.append(check("each ALLOWED_DATA_LINES entry is found in exactly one comment or docstring line "
                         "that holds a marker", not misfits))
    results.append(check("no tracked .py file or shell script carries more history markers than it is allowed",
                         not failures))
    return results


def main():
    results = [
        check("a date, a ruling, an issue number and a commit hash in a comment are each found",
              {kind for _, kind, _ in markers_in("x.py", "# 2026-09-30 user-ruled, PR 931, fix in a82b49e\n")}
              == set(MARKER_PATTERNS)),
        check("a timestamp and a range of days in a comment are found as dates",
              [m for _, k, m in markers_in("x.py", "# at 2026-09-19T04:00:31Z, 2026-09-07/08, 2026-08-10-11\n")
               if k == "date"] == ["2026-09-19T04:00:31Z", "2026-09-07/08", "2026-08-10-11"]),
        check("a path or file name that starts with a date or a timestamp is not a date",
              [k for _, k, _ in markers_in("x.py", "# read 2026-09-19T04:00:31Z.log, logs/2026-10-14/x, "
                                                   "2026-08-10-11.md\n")] == []),
        check("a date that ends a name, such as a walk's, is still found",
              [k for _, k, _ in markers_in("x.py", "# walk open-items-2026-09-24, item 3\n")] == ["date"]),
        check("a docstring's marker is found, and a string that is not a docstring is not",
              [k for _, k, _ in markers_in("x.py", 'def f():\n    """See GHI 913."""\n    return "2026-09-30"\n')]
              == ["pull request or issue number"]),
        check("plain words and hex-free numbers are not markers",
              markers_in("x.py", "# deadbeef retries 1234567 times; feed the cafe\n") == []),
        check("a shell comment's markers are found, at a line's start and after code",
              [(line, kind) for line, kind, _ in markers_in(
                  "x.sh", "#!/bin/sh\n# see PR 931\necho hi  # 2026-09-30\n", "shell")]
              == [(2, "pull request or issue number"), (3, "date")]),
        check("a shell script's shebang, quoted text, $#, ${#x} and here-document bodies are not comments",
              markers_in("x.sh", "#!/bin/sh\n"
                                 "echo '# PR 931' \"# 2026-09-30\" \\# GHI 12 $# ${#x} PR 931\n"
                                 "cat <<'EOF'\n# PR 931\nEOF\n"
                                 "cat <<-END\n\t# PR 931\n\tEND\n"
                                 "tr a b <<<\"$x\" # ok\n", "shell") == []),
        check("nested quotes inside \"$(...)\" are not a quote left open, and a comment inside it is read",
              [(line, kind) for line, kind, _ in markers_in(
                  "x.sh", "value=\"$(printf '%s' \"don't\")\"\nx=\"$(\n  # GHI 12\n  echo hi)\"\n", "shell")]
              == [(3, "pull request or issue number")]),
        check("$((1 << shift)) is arithmetic, not a here-document, so later comments are read",
              [(line, kind) for line, kind, _ in markers_in(
                  "x.sh", "value=$((1 << shift))\n# PR 931\n", "shell")]
              == [(2, "pull request or issue number")]),
        check("the here-document delimiters EOF-1 and 123 end their bodies",
              [(line, kind) for line, kind, _ in markers_in(
                  "x.sh", "cat <<EOF-1\n# PR 1\nEOF-1\ncat <<123\n# PR 2\n123\n# PR 931\n", "shell")]
              == [(7, "pull request or issue number")]),
        check("a # after an escaped space is part of a word, and a # after an escaped backslash starts a comment",
              [(line, kind) for line, kind, _ in markers_in(
                  "x.sh", "printf '%s\\n' \\ # PR 931\nprintf '%s\\n' \\\\ # GHI 12\n", "shell")]
              == [(2, "pull request or issue number")]),
        check("a here-document body line that only starts with its delimiter is data, not a comment",
              [(line, kind) for line, kind, _ in markers_in(
                  "x.sh", "cat <<EOF\nEOF # PR 931\nEOF\n# GHI 12\n", "shell")]
              == [(4, "pull request or issue number")]),
        check("a # after ; starts a comment, even after an escaped space earlier on the line, and a # after an escaped ; does not",
              [(line, kind) for line, kind, _ in markers_in(
                  "x.sh", "echo \\ #word;# PR 931\necho \\;# GHI 12\n", "shell")]
              == [(1, "pull request or issue number")]),
        check("a comment at the start of a backtick substitution is read",
              [(line, kind) for line, kind, _ in markers_in(
                  "x.sh", "x=`# PR 931\necho hi`\necho done\n", "shell")]
              == [(1, "pull request or issue number")]),
        check("a # after an escaped space, and a ;# inside the quote that follows it, are data, not comments",
              [(line, kind) for line, kind, _ in markers_in(
                  "x.sh", "echo \\ #word\";# PR 931\"\n# GHI 12\n", "shell")]
              == [(2, "pull request or issue number")]),
        check("a # after an escaped space followed by a quote that never closes raises",
              shell_script_does_not_parse("echo \\ #word\";# PR 931\n")),
        check("an extglob case pattern in a script tree-sitter-bash cannot fully read is valid bash, so its comments are read",
              [(line, kind) for line, kind, _ in markers_in(
                  "x.sh", 'case "$x" in\n  *"a"*"b"*) echo hit ;;\nesac\n'
                          "case $y in\n  @(a|b)) echo y ;;\nesac\n# PR 931\n", "shell")]
              == [(7, "pull request or issue number")]),
        check("a span bash reads but tree-sitter-bash cannot, with a # in it, raises",
              shell_script_does_not_parse('case "$x" in\n  *"a#"*"b"*) echo hit ;;\nesac\n')),
        check("a quote that never closes raises, with no # after it",
              shell_script_does_not_parse("echo 'never closed\n")),
        check("a double quote that never closes raises, with no # after it",
              shell_script_does_not_parse('echo "never closed\n')),
        check("a here-document that never closes raises, with no # in its body",
              shell_script_does_not_parse("cat <<EOF\nno end\n")),
        check("a marker on a line ALLOWED_DATA_LINES names by its text is skipped, and one on another line is not",
              [line for line, _, _ in markers_in(
                  "data.py", "# such as 2026-10-03\n# on 2026-10-03\n", allowed=ALLOWED_IN_THE_SCRATCH_REPOSITORY)]
              == [2]),
    ]
    if not os.environ.get("HISTORY_MARKER_SUITE_CHILD"):
        results.append(check("run with GIT_DIR set, the suite still scans this repository",
                             the_suite_run_with_git_dir_set_still_scans_this_repository()))
        results.append(check("a tracked .py file that does not parse is reported, not skipped",
                             a_file_that_does_not_parse_is_reported()))
        results.append(check("a tracked shell script whose quote or here-document never closes "
                             "is reported, not skipped, and one tree-sitter-bash misreads with no # in the span is read",
                             a_shell_script_that_does_not_parse_is_reported()))
        results.append(check("lines added above an allowed line do not break the suite",
                             an_edit_above_an_allowed_line_does_not_break_the_suite()))
        results.append(check("an allowed entry found in no line fails: its line changed, its text is only in code, or it is in another file",
                             an_allowed_entry_that_matches_no_line_fails()))
        results.append(check("an allowed entry found in two lines fails",
                             an_allowed_entry_that_matches_two_lines_fails()))
        results.append(check("a comment line that holds an allowed entry's text but no marker is not counted",
                             an_allowed_entry_is_counted_only_on_lines_that_hold_a_marker()))
        results.append(check("the repository checks fail when an allowed entry is found in no line",
                             the_repository_checks_fail_on_an_allowed_entry_found_in_no_line()))
    results.extend(repository_checks(REPOSITORY))
    if all(results):
        print("all cases passed")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
