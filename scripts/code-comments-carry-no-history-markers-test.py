#!/usr/bin/env python3
"""Fail when a comment or docstring in a tracked Python file, or a comment in a
tracked shell script, carries a history marker: an ISO date, a ruling, a pull
request or issue number, or a commit hash.

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
SUITE = "scripts/code-comments-carry-no-history-markers-test.py"

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
    "scripts/daily-full-test-run-of-main.py": 8,
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
    "scripts/open-iterm-window-running-command-test.py": 3,
    "scripts/post-compaction-session-continues-hook-test.py": 1,
    "scripts/pr-reviewer-instructions-copies-test.py": 5,
    "scripts/recover-crashed-seats-test.py": 168,
    "scripts/recover-crashed-seats.py": 31,
    "scripts/restart-live-seats-at-login-test.py": 38,
    "scripts/restart-live-seats-at-login.py": 17,
    "scripts/resupervise-seat-test.py": 24,
    "scripts/resupervise-seat.py": 10,
    "scripts/run-all-test-suites-test.py": 8,
    "scripts/run-all-test-suites.py": 24,
    "scripts/sanity-check-attacks-test.py": 47,
    "scripts/sanity-check-attacks.py": 19,
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

# Lines whose marker is data the code needs, not history: "path:line": reason.
ALLOWED_DATA_LINES = {
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


def _escaped(source, position):
    """Return whether the byte at position is escaped by an odd run of backslashes before it."""
    backslashes = 0
    while position - 1 - backslashes >= 0 and source[position - 1 - backslashes] == ord("\\"):
        backslashes += 1
    return backslashes % 2 == 1


def _begins_a_word(source, position):
    """Return whether bash starts a word at position: after a line end, or an unescaped blank or operator."""
    if position == 0 or source[position - 1] == ord("\n"):
        return True
    return source[position - 1] in b" \t;&|()<>" and not _escaped(source, position - 1)


def _comment_start(source, start, end):
    """Return where bash starts the comment tree-sitter-bash reports at start, or None.

    tree-sitter-bash takes a # after an escaped space for a comment; bash reads
    that # as part of a word, and a comment starts only at a later # on the line
    that begins a word, after an unescaped blank or operator such as ;.
    """
    position = start
    while position != -1 and not _begins_a_word(source, position):
        position = source.find(b"#", position + 1, end)
    return None if position == -1 else position


def _bash_reports_a_quote_never_closed(source):
    """Return bash -n's complaint when bash cannot read source to its end, or None."""
    checked = subprocess.run(["bash", "-n"], input=source, capture_output=True)
    if checked.returncode == 0:
        return None
    return checked.stderr.decode("utf-8", "replace").strip() or f"bash -n exited {checked.returncode}"


def shell_comment_lines(source):
    """Return [(line number, text)] for every comment in a shell script.

    The script is parsed with tree-sitter-bash, the parser the project's Bash
    guards use, so quoting, command substitution and arithmetic are read as bash
    reads them. Here-document bodies are taken out first by the shared reader,
    as bash's lexer takes them, so a body line such as `EOF # note` is data,
    not a comment. A #! first line is not a comment.

    Raise ShellScriptDoesNotParse when a here-document never closes, or when a
    quote or substitution never closes, as bash -n reports it, because a
    comment after it would go unread. tree-sitter-bash also cannot read some
    valid bash, such as a case pattern made of several quoted parts joined by *,
    and marks that span as an error: a span bash reads, with no # in it, holds
    no comment, so it is passed over, and one with a # in it raises.
    """
    encoded = source.encode("utf-8", "surrogatepass")
    edits = []
    edited, tree, taken = shell_reader._source_with_heredoc_bodies_taken_out(encoded, edits=edits)
    for heredoc in taken.values():
        if not heredoc.ending:
            raise ShellScriptDoesNotParse(
                f"the here-document {heredoc.written} never reaches its closing line")
    comments, pending, checked_with_bash = [], [tree.root_node], False
    while pending:
        node = pending.pop()
        pending.extend(node.children)
        if node.is_missing:
            raise ShellScriptDoesNotParse(
                f"a {node.type} that line {node.start_point[0] + 1} needs never comes")
        if node.type == "ERROR":
            if not checked_with_bash:
                checked_with_bash = True
                complaint = _bash_reports_a_quote_never_closed(encoded)
                if complaint:
                    raise ShellScriptDoesNotParse(f"bash cannot read it: {complaint}")
            if b"#" in edited[node.start_byte:node.end_byte]:
                at = shell_reader._offset_before_edits(node.start_byte, edits) or 0
                line = encoded.count(b"\n", 0, at) + 1
                raise ShellScriptDoesNotParse(
                    f"tree-sitter-bash cannot read line {line}, which holds a #")
        if node.type != "comment":
            continue
        original_start = shell_reader._offset_before_edits(node.start_byte, edits)
        original_end = shell_reader._offset_before_edits(node.end_byte, edits)
        if original_start == 0 and encoded.startswith(b"#!"):
            continue
        start = _comment_start(encoded, original_start, original_end)
        if start is not None:
            line = encoded.count(b"\n", 0, start) + 1
            comments.append((line, encoded[start:original_end].decode("utf-8", "surrogatepass")))
    return sorted(comments)


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


def markers_in(path, source, language="python"):
    """Return [(line, kind, marker)] for the history markers in one file."""
    found = []
    lines = shell_comment_lines(source) if language == "shell" else python_comment_and_docstring_lines(source)
    for line, text in lines:
        if f"{path}:{line}" in ALLOWED_DATA_LINES:
            continue
        for kind, pattern in MARKER_PATTERNS.items():
            found.extend((line, kind, match.group()) for match in pattern.finditer(text))
    return found


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


def scan_tree(repository):
    """Return (failures, paths that do not parse, {language: number of files listed})."""
    paths = subprocess.run(["git", "-C", str(repository), "ls-files", "-z"],
                           capture_output=True, text=True, check=True).stdout.split("\0")
    failures, unparseable, listed = [], [], {"python": 0, "shell": 0}
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
            found = markers_in(path, source, language)
        except (SyntaxError, tokenize.TokenError, ShellScriptDoesNotParse):
            unparseable.append(path)
            continue
        ceiling = FILES_AWAITING_THE_COMMENT_TRIM.get(path, 0)
        if len(found) > ceiling:
            failures.append((path, found, ceiling))
    return failures, unparseable, listed


def a_file_that_does_not_parse_is_reported():
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        subprocess.run(["git", "init", "-q", str(scratch)], check=True)
        (scratch / "broken.py").write_text("def (:\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(scratch), "add", "broken.py"], check=True)
        _, unparseable, listed = scan_tree(scratch)
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
        _, unparseable, listed = scan_tree(scratch)
    return sorted(unparseable) == ["unclosed-heredoc.sh", "unclosed-quote"] \
        and listed == {"python": 0, "shell": 3}


def the_suite_run_with_git_dir_set_still_scans_this_repository():
    # A child copy of this suite, started with GIT_DIR naming an empty repository.
    with tempfile.TemporaryDirectory() as scratch:
        subprocess.run(["git", "init", "-q", "--bare", scratch], check=True)
        environment = dict(os.environ, GIT_DIR=scratch, HISTORY_MARKER_SUITE_CHILD="1")
        child = subprocess.run([sys.executable, __file__], capture_output=True, text=True,
                               env=environment)
    return child.returncode == 0 and "PASS  git ls-files lists this repository's .py files and shell scripts" in child.stdout


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
        check("a quote that never closes raises, with no # after it",
              shell_script_does_not_parse("echo 'never closed\n")),
        check("a double quote that never closes raises, with no # after it",
              shell_script_does_not_parse('echo "never closed\n')),
        check("a here-document that never closes raises, with no # in its body",
              shell_script_does_not_parse("cat <<EOF\nno end\n")),
        check("a line in ALLOWED_DATA_LINES is skipped",
              all(not markers_in(key.rsplit(":", 1)[0], "") for key in ALLOWED_DATA_LINES)),
    ]
    if not os.environ.get("HISTORY_MARKER_SUITE_CHILD"):
        results.append(check("run with GIT_DIR set, the suite still scans this repository",
                             the_suite_run_with_git_dir_set_still_scans_this_repository()))
        results.append(check("a tracked .py file that does not parse is reported, not skipped",
                             a_file_that_does_not_parse_is_reported()))
        results.append(check("a tracked shell script whose quote or here-document never closes "
                             "is reported, not skipped, and one tree-sitter-bash misreads with no # in the span is read",
                             a_shell_script_that_does_not_parse_is_reported()))
    failures, unparseable, listed = scan_tree(REPOSITORY)
    results.append(check("git ls-files lists this repository's .py files and shell scripts",
                         listed["python"] > 0 and listed["shell"] > 0))
    results.append(check("every tracked .py file and every tracked shell script parses"
                         + (f"; these do not: {', '.join(unparseable)}" if unparseable else ""),
                         not unparseable))
    report(failures)
    results.append(check("no tracked .py file or shell script carries more history markers than it is allowed",
                         not failures))
    if all(results):
        print("all cases passed")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
