#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py.

Reads commands with the real tree-sitter-bash: the word values and the order
bash runs commands in, the child shells a cd stays inside, redirections, and
heredocs, including the forms tree-sitter-bash itself reads differently from
bash. Then drives the install of a missing parser with stubs, and each Bash
guard with a parser that cannot be installed.

Run: python3 nc-systems/general-tools/tests/shell-command-tree-sitter-bash-reader-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = Path(__file__).resolve().parents[1] / "shell-command-tree-sitter-bash-reader-common.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reader = load(MODULE_PATH, "shell_command_tree_sitter_bash_reader_common")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def words_of(command, glob_markers=None):
    return [list(found) for found in reader.simple_commands(command, glob_markers)]


# --- words, from the Codex CLI's reader tests (codex-rs/shell-command/src/bash.rs) ---
# Codex accepts these as literal; this reader returns the same words.
for command, expected in [
    ("ls -1", [["ls", "-1"]]),
    ("ls && pwd; echo 'hi there' | wc -l", [["ls"], ["pwd"], ["echo", "hi there"], ["wc", "-l"]]),
    ('echo "hello world"', [["echo", "hello world"]]),
    ('git commit -m "line1\nline2"', [["git", "commit", "-m", "line1\nline2"]]),
    ('echo "/usr"\'/\'"local"/bin', [["echo", "/usr/local/bin"]]),
    ("echo '/usr'\"/\"'local'/bin", [["echo", "/usr/local/bin"]]),
    ("echo 123 456", [["echo", "123", "456"]]),
    ('rg -g"*.py" pattern', [["rg", "-g*.py", "pattern"]]),
    ('echo "\\n"', [["echo", "\\n"]]),
    ('echo "~HOME" \'HEAD~1\' "HEAD^" \'foo#bar\' "=sh" \'file~\'',
     [["echo", "~HOME", "HEAD~1", "HEAD^", "foo#bar", "=sh", "file~"]]),
    ("echo -\"{a,b}\" '*?[]~^#=\\\\'", [["echo", "-{a,b}", "*?[]~^#=\\\\"]]),
    ('rg -n "foo" -g"*.py"', [["rg", "-n", "foo", "-g*.py"]]),
    ("grep -n 'pattern' -g'*.txt'", [["grep", "-n", "pattern", "-g*.txt"]]),
]:
    check(f"Codex literal case reads as bash passes it: {command!r}",
          words_of(command) == expected, words_of(command))

# Codex refuses to prove these literal. This reader still collects them, with
# each expansion kept as written: its words never prove a command safe.
for command, expected in [
    ('echo "hi ${USER}"', [["echo", "hi ${USER}"]]),
    ("echo $HOME", [["echo", "$HOME"]]),
    ("FOO=bar ls", [["FOO=bar", "ls"]]),
    ('rg -g"$VAR" pattern', [["rg", "-g$VAR", "pattern"]]),
    ("echo $(pwd)", [["pwd"], ["echo", "$(pwd)"]]),
    ("echo `pwd`", [["pwd"], ["echo", "`pwd`"]]),
    ("ls || (pwd && echo hi)", [["ls"], ["pwd"], ["echo", "hi"]]),
]:
    check(f"Codex non-literal case is collected with expansions as written: {command!r}",
          words_of(command) == expected, words_of(command))

# --- words, from the hand-written reader's own tests ---
check("a substitution's commands come first and the word keeps its text unexpanded",
      words_of('echo "at $(date +%H) today" done')
      == [["date", "+%H"], ["echo", "at $(date +%H) today", "done"]],
      words_of('echo "at $(date +%H) today" done'))
check("a substitution nested in another, both double-quoted, is read innermost first",
      words_of('cd "$(dirname "$(git rev-parse --git-dir)")" && ls')
      == [["git", "rev-parse", "--git-dir"], ["dirname", "$(git rev-parse --git-dir)"],
          ["cd", '$(dirname "$(git rev-parse --git-dir)")'], ["ls"]],
      words_of('cd "$(dirname "$(git rev-parse --git-dir)")" && ls'))
found = words_of('echo "$(printf \')\'; printf "%s)" x; (cd /tmp; ls); '
                 'tmux send-keys -t seat-a x) end"')
check("a ) in quotes or closing a subshell does not close the substitution",
      found[:5] == [["printf", ")"], ["printf", "%s)", "x"], ["cd", "/tmp"], ["ls"],
                    ["tmux", "send-keys", "-t", "seat-a", "x"]]
      and len(found) == 6 and found[5][0] == "echo", found)
# tree-sitter-bash rejects a last branch ended by ;& and loses the commands after the case.
found = words_of('X="$(case $v in (a|b) c;; *) d;;& e) f;; esac)" && g')
check("a case's branches are commands and its patterns are not",
      found[:3] == [["c"], ["d"], ["f"]] and found[-1] == ["g"], found)
check("$'...' ends at its unescaped quote, and a plain '...' at its first quote",
      words_of("a $'it\\'s' b; c 'x'") == [["a", "it's", "b"], ["c", "x"]],
      words_of("a $'it\\'s' b; c 'x'"))
check("export and unset are read as commands with their words",
      words_of("export A=1; unset B") == [["export", "A=1"], ["unset", "B"]],
      words_of("export A=1; unset B"))
check("if, then and fi are not words of the commands they hold",
      words_of("if git push -f o b; then echo y; fi") == [["git", "push", "-f", "o", "b"],
                                                          ["echo", "y"]],
      words_of("if git push -f o b; then echo y; fi"))

# --- child shells: where a cd stays ---
found = reader.simple_commands("(cd /tmp/other && make); git push --force-with-lease o b")
check("a cd inside ( ... ) runs in a child shell; the command after it does not",
      found[0].child_shell and found[1].child_shell == found[0].child_shell
      and found[2].child_shell == (), [(list(f), f.child_shell) for f in found])
found = reader.simple_commands('X="$(cd /x; pwd)" `ls` <(git log); y')
check("command and process substitutions run in child shells of their own",
      all(f.child_shell for f in found[:4]) and found[-1].child_shell == ()
      and len({f.child_shell for f in found[:4]}) == 3,
      [(list(f), f.child_shell) for f in found])
found = reader.simple_commands("cd /x | true; git push")
check("each stage of a pipeline runs in a child shell of its own",
      found[0].child_shell and found[1].child_shell
      and found[0].child_shell != found[1].child_shell and found[2].child_shell == (),
      [(list(f), f.child_shell) for f in found])
found = reader.simple_commands('echo "$(cd /a; echo "$(cd /b)")"')
check("a substitution inside another runs inside the outer one's child shell",
      found[1].child_shell[:len(found[0].child_shell)] == found[0].child_shell
      and len(found[1].child_shell) == len(found[0].child_shell) + 1,
      [(list(f), f.child_shell) for f in found])

# --- redirections ---
found = reader.simple_commands("git push --force origin 2> err.log the-pr-branch")
check("a word after a redirection's target is an argument, not a second target",
      list(found[0]) == ["git", "push", "--force", "origin", "the-pr-branch"]
      and found[0].redirects == [("2>", "err.log")], (list(found[0]), found[0].redirects))
found = reader.simple_commands('git push o b 2>&1 >out; cat <<<"here string" x; y &>/dev/null')
check("redirections are left out of the words and kept with their targets",
      [list(f) for f in found] == [["git", "push", "o", "b"], ["cat", "x"], ["y"]]
      and found[0].redirects == [("2>&", "1"), (">", "out")]
      and found[1].redirects == [("<<<", "here string")]
      and found[2].redirects == [("&>", "/dev/null")],
      [(list(f), f.redirects) for f in found])

# --- glob markers ---
MARKERS = {"*": "<star>", "?": "<query>"}
check("only glob characters outside quotes and not escaped are marked",
      words_of('ls *.py "*.md" \\*.txt a?b', MARKERS)
      == [["ls", "<star>.py", "*.md", "*.txt", "a<query>b"]],
      words_of('ls *.py "*.md" \\*.txt a?b', MARKERS))

# --- heredocs ---
found = reader.simple_commands("ssh ned-box <<'EOF'\ntmux send-keys -t x y\nEOF\nls")
check("a quoted heredoc's body is data, given to the command it feeds",
      [list(f) for f in found] == [["ssh", "ned-box"], ["ls"]]
      and found[0].heredocs[0].body == "tmux send-keys -t x y\n"
      and found[0].heredocs[0].expanded is False,
      [(list(f), f.heredocs) for f in found])
found = reader.simple_commands("cat <<EOF | sh\n$(rm x)\nEOF")
check("an unquoted body's substitution runs; the pipeline on the heredoc's line shares it",
      [list(f) for f in found] == [["rm", "x"], ["cat"], ["sh"]]
      and found[0].child_shell and found[2].heredocs[0].body == "$(rm x)\n"
      and found[2].heredocs[0].expanded,
      [(list(f), f.child_shell, f.heredocs) for f in found])
found = reader.simple_commands("cat <<-EOF\n\tone\n\tEOF\nls")
check("a <<- body loses its leading tabs, and its \\t-indented delimiter ends it",
      found[0].heredocs[0].body == "one\n" and [list(f) for f in found] == [["cat"], ["ls"]],
      [(list(f), f.heredocs) for f in found])
for body_line in ("EOF2", "EOF ", "EOFX=1 gh issue comment 1 -b x"):
    command = f"cat <<'EOF'\n{body_line}\ngh issue comment 1 -b x\nEOF\nls"
    found = reader.simple_commands(command)
    check(f"a body line that only starts with the delimiter stays in the body: {body_line!r}",
          [list(f) for f in found] == [["cat"], ["ls"]]
          and found[0].heredocs[0].body == f"{body_line}\ngh issue comment 1 -b x\n",
          [(list(f), f.heredocs) for f in found])
found = reader.simple_commands("git commit -m \"$(cat <<'EOF'\nmessage EOF2\nEOF\n)\"; ls")
check("the command's own delimiter is kept in its words and heredocs",
      found[1][3] == "$(cat <<'EOF'\nmessage EOF2\nEOF\n)"
      and found[0].heredocs[0].delimiter == "'EOF'",
      [(list(f), [h.delimiter for h in f.heredocs]) for f in found])
found = reader.simple_commands('git commit -m "$(cat <<\'EOF\'\nmessage\nEOF)"\ntmux send-keys -t a b')
check("inside $( ... ), a body also ends at the delimiter followed by )",
      [list(f) for f in found][-1] == ["tmux", "send-keys", "-t", "a", "b"], [list(f) for f in found])
found = reader.simple_commands("cat > n.md <<EOF\nnever `tmux send-keys -t a b` here\nEOF")
check("a backticked command in an unquoted body is read; tree-sitter-bash leaves it as text",
      ["tmux", "send-keys", "-t", "a", "b"] in [list(f) for f in found], [list(f) for f in found])
found = reader.simple_commands("cat <<'EOF'\nnever `tmux send-keys -t a b` here\nEOF")
check("a backticked command in a quoted body is data",
      [list(f) for f in found] == [["cat"]], [list(f) for f in found])
found = reader.simple_commands("cat > n.md <<EOF\nuse $(a it's) form\nEOF\ntmux send-keys -t a b")
check("a lone quote in an unquoted body's substitution does not hide the command after the heredoc",
      [list(f) for f in found][-1] == ["tmux", "send-keys", "-t", "a", "b"],
      [list(f) for f in found])
found = reader.simple_commands("cat > n.md <<EOF\n$(tmux send-keys -t a b) then $(date\nEOF")
check("a body's closed substitution runs, and one that never closes runs nothing",
      ["tmux", "send-keys", "-t", "a", "b"] in [list(f) for f in found]
      and ["date"] not in [list(f) for f in found], [list(f) for f in found])
found = reader.simple_commands("cat <<EOF\npid $$(tmux send-keys -t a b)\nEOF")
check("$$( in a body is the process id and a parenthesis, not a substitution",
      [list(f) for f in found] == [["cat"]], [list(f) for f in found])
found = reader.simple_commands("cat ${output:-<(tmux send-keys -t a b)} ${x:-`date`}")
check("a process substitution or backtick in a ${name:-...} default is read",
      [list(f) for f in found][:2] == [["tmux", "send-keys", "-t", "a", "b"], ["date"]]
      and all(f.child_shell for f in found[:2]), [(list(f), f.child_shell) for f in found])

# --- what bash rejects, and depth ---
check("a line bash rejects for an unclosed quote yields no command after the quote",
      ["tmux", "send-keys", "-t", "a", "b"] not in words_of(
          'echo "$(a \'unclosed)"; tmux send-keys -t a b'),
      words_of('echo "$(a \'unclosed)"; tmux send-keys -t a b'))
deep = "tmux send-keys -t a b"
for _level in range(1500):
    deep = 'echo "$(' + deep + ')"'
try:
    deep_found = words_of(deep)
    crashed = None
except RecursionError as error:
    deep_found, crashed = [], error
check("1,500 nested substitutions are read without exhausting Python's recursion",
      crashed is None and deep_found[:1] == [["tmux", "send-keys", "-t", "a", "b"]],
      crashed)
check("the recursion limit is restored after a read", sys.getrecursionlimit() < 100_000,
      sys.getrecursionlimit())

check("is_program matches a bare name or a path ending in it, and nothing else",
      reader.is_program("tmux", "tmux") and reader.is_program("/usr/bin/tmux", "tmux")
      and not reader.is_program("xtmux", "tmux") and not reader.is_program("tmux.sh", "tmux"))


# --- the install of a missing parser ---
class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def importer_after(installs_needed):
    """An importer that fails until the installer has run installs_needed times."""
    state = {"installs": 0, "imports": 0}

    def importer():
        state["imports"] += 1
        if state["installs"] < installs_needed:
            raise ImportError("No module named 'tree_sitter'")
        return reader.import_tree_sitter_bash()

    def installer():
        state["installs"] += 1
        return "installed"
    return importer, installer, state


def failing_installer(state):
    def installer():
        state["installs"] += 1
        raise reader.ShellParserUnavailable("pip: network is unreachable")
    return installer


with tempfile.TemporaryDirectory() as scratch:
    reader.STATE_DIRECTORY = Path(scratch) / "state"

    importer, installer, state = importer_after(1)
    parser = reader.load_parser(importer, installer, Clock(1000.0))
    check("a missing parser is installed once, then the read goes on",
          state["installs"] == 1 and parser.parse(b"ls").root_node.type == "program", state)

    importer, installer, state = importer_after(0)
    reader.load_parser(importer, installer, Clock(1000.0))
    check("an installed parser runs no install", state["installs"] == 0, state)

    importer, _installer, state = importer_after(99)
    try:
        reader.load_parser(importer, failing_installer(state), Clock(1000.0))
        raised = None
    except reader.ShellParserUnavailable as error:
        raised = error
    record = reader.STATE_DIRECTORY / reader.INSTALL_FAILURE_FILE_NAME
    check("a failed install raises ShellParserUnavailable with what the install printed",
          raised is not None and "network is unreachable" in raised.install_output, raised)
    check("a failed install is recorded", record.is_file()
          and "network is unreachable" in record.read_text(encoding="utf-8"))
    os.utime(record, (1000.0, 1000.0))

    importer, _installer, state = importer_after(99)
    try:
        reader.load_parser(importer, failing_installer(state), Clock(1000.0 + 60))
        raised = None
    except reader.ShellParserUnavailable as error:
        raised = error
    check("within ten minutes of a failed install, no install runs and the same output is given",
          state["installs"] == 0 and raised is not None
          and "network is unreachable" in raised.install_output, (state, raised))

    importer, installer, state = importer_after(1)
    reader.load_parser(importer, installer, Clock(1000.0 + reader.INSTALL_RETRY_SECONDS + 1))
    check("after ten minutes the install runs again, and success clears the record",
          state["installs"] == 1 and not record.exists(), (state, record.exists()))

    def importer_never():
        raise ImportError("No module named 'tree_sitter_bash'")
    try:
        reader.load_parser(importer_never, lambda: "installed", Clock(5000.0))
        raised = None
    except reader.ShellParserUnavailable as error:
        raised = error
    check("an install that finishes but leaves the import failing raises ShellParserUnavailable",
          raised is not None and "importing still fails" in raised.install_output, raised)
    record.unlink()

    def runner_exiting(returncode, stdout="", stderr=""):
        def run(command, **kwargs):
            run.command, run.kwargs = command, kwargs
            return subprocess.CompletedProcess(command, returncode, stdout, stderr)
        return run

    run = runner_exiting(0, "Successfully installed tree-sitter-0.25.2")
    printed = reader.install_compiled_libraries(run)
    check("the install runs pip per user, from the pinned requirements file, within its timeout",
          run.command[1:7] == ["-m", "pip", "install", "--user", "--break-system-packages",
                               "--disable-pip-version-check"]
          and run.command[-2:] == ["-r", str(reader.REQUIREMENTS_FILE)]
          and run.kwargs["timeout"] == reader.INSTALL_TIMEOUT_SECONDS
          and "Successfully installed" in printed, (run.command, run.kwargs))
    try:
        reader.install_compiled_libraries(runner_exiting(1, "", "ERROR: No matching distribution"))
        raised = None
    except reader.ShellParserUnavailable as error:
        raised = error
    check("pip exiting nonzero raises ShellParserUnavailable with its output",
          raised is not None and "No matching distribution" in raised.install_output
          and "exited 1" in raised.install_output, raised)

    def runner_timing_out(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])
    try:
        reader.install_compiled_libraries(runner_timing_out)
        raised = None
    except reader.ShellParserUnavailable as error:
        raised = error
    check("pip timing out raises ShellParserUnavailable saying it did not finish",
          raised is not None and "did not finish" in raised.install_output, raised)
    check("the pinned requirements file pins tree-sitter and tree-sitter-bash",
          {line.split("==")[0] for line in reader.REQUIREMENTS_FILE.read_text().splitlines()
           if "==" in line} == {"tree-sitter", "tree-sitter-bash"})

    # Failures of the state directory itself.
    real_state_directory = reader.STATE_DIRECTORY
    blocking_file = Path(scratch) / "a-file-not-a-directory"
    blocking_file.write_text("x")
    reader.STATE_DIRECTORY = blocking_file / "state"
    importer, installer, state = importer_after(1)
    try:
        reader.load_parser(importer, installer, Clock(9000.0))
        raised = None
    except reader.ShellParserUnavailable as error:
        raised = error
    check("a state directory that cannot be made raises ShellParserUnavailable saying so",
          raised is not None and "install lock" in raised.install_output
          and state["installs"] == 0, (raised, state))
    check("an agent-session is still told when its marker cannot be written",
          reader._claim_telling_the_user("session-unwritable"))
    reader.STATE_DIRECTORY = real_state_directory

    read_only = Path(scratch) / "read-only-state"
    read_only.mkdir()
    (read_only / reader.INSTALL_LOCK_FILE_NAME).write_text("")
    read_only.chmod(0o555)
    reader.STATE_DIRECTORY = read_only
    importer, _installer, state = importer_after(99)
    try:
        reader.load_parser(importer, failing_installer(state), Clock(9000.0))
        raised = None
    except reader.ShellParserUnavailable as error:
        raised = error
    except OSError as error:
        raised = error
    check("a failed install whose record cannot be written still raises ShellParserUnavailable",
          isinstance(raised, reader.ShellParserUnavailable) and state["installs"] == 1,
          (raised, state))
    read_only.chmod(0o755)
    reader.STATE_DIRECTORY = real_state_directory

    # --- the message when the parser is missing and the install failed ---
    error = reader.ShellParserUnavailable("pip: network is unreachable")
    attended = {}

    def context_of(output):
        hook_output = json.loads(output)["hookSpecificOutput"]
        assert "permissionDecision" not in hook_output, hook_output
        return hook_output["additionalContext"]

    first = context_of(reader.parser_unavailable_hook_output(
        "The force-push guard", error, {"session_id": "session-one"}, attended))
    again = context_of(reader.parser_unavailable_hook_output(
        "The tmux kill guard", error, {"session_id": "session-one"}, attended))
    other = context_of(reader.parser_unavailable_hook_output(
        "The tmux kill guard", error, {"session_id": "session-two"}, attended))
    unattended = context_of(reader.parser_unavailable_hook_output(
        "The tmux kill guard", error, {"session_id": "session-three"},
        {"CLAUDE_CODE_SESSION_ATTENDED": "0"}))
    check("the first report in an agent-session says the command was not checked and has the "
          "user told, with what the install printed",
          "let this command through without checking it" in first
          and "Tell the user" in first and "network is unreachable" in first
          and str(reader.REQUIREMENTS_FILE) in first and "subagent" in first, first)
    on_ned_box = __import__("socket").gethostname().split(".")[0] == "ned-box"
    check("the install command for ned-box is given in the ssh form the user runs from the Mac",
          on_ned_box == ("ssh nedlern@ned-box 'python3 -m pip install" in first), first)
    check("a later report in the same agent-session says the command was not checked, "
          "and not to tell the user again",
          "without checking it" in again and "Tell the user" not in again
          and "do not tell the user again" in again and "An earlier message" in again, again)
    check("another agent-session is told to tell the user", "Tell the user" in other, other)
    check("an agent-session no user attends is not told to tell the user",
          "Tell the user" not in unattended and "without checking it" in unattended
          and "No user attends" in unattended, unattended)

    # --- each Bash guard lets the command through and says so ---
    GUARDS = [
        ("scripts/synthetic-keystroke-guard-hook.py", "The synthetic keystroke guard"),
        ("scripts/force-push-with-open-pull-request-guard-hook.py", "The force-push guard"),
        (".claude/hooks/ghi-issue-write-redirect.py", "The GHI write redirect guard"),
        ("scripts/search-file-argument-read-as-option-guard-hook.py",
         "The search-file-argument guard"),
        ("nc-systems/general-tools/claude-code-tmux-kill-server-and-kill-session-missing-"
         "server-selection-refusal-hook.py", "The tmux kill guard"),
    ]
    for relative, guard_name in GUARDS:
        guard = load(REPOSITORY_ROOT / relative, "guard_" + Path(relative).stem.replace("-", "_"))
        guard.shell_reader.STATE_DIRECTORY = reader.STATE_DIRECTORY

        def unavailable(*arguments, **keywords):
            raise guard.shell_reader.ShellParserUnavailable("pip: network is unreachable")
        guard.shell_reader.simple_commands = unavailable
        payload = {"tool_name": "Bash", "session_id": f"guard-{relative}", "cwd": scratch,
                   "tool_input": {"command": "tmux kill-server; git push --force o b"}}
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = guard.main(stdin=io.StringIO(json.dumps(payload)))
        try:
            context = context_of(stdout.getvalue())
        except (ValueError, KeyError, AssertionError) as problem:
            context = f"<{problem!r}: {stdout.getvalue()!r}>"
        check(f"with no parser, {relative} lets the command through and says it was not checked",
              code == 0 and context.startswith(guard_name + " let this command through"),
              (code, context))

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
