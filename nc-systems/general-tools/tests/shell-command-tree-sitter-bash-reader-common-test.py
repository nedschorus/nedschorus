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
found = reader.simple_commands("cd /x && ls | head; git push")
check("a cd before && in a pipeline's first stage counts for the commands after it",
      [f.child_shell == () for f in found] == [True, False, False, True],
      [(list(f), f.child_shell) for f in found])
# tree-sitter-bash reads this one as `(cd /x && ls 2>/dev/null) | head`.
found = reader.simple_commands("cd /x && ls 2>/dev/null | head; git push")
check("a cd before && counts after a pipeline whose first stage has a redirection, which stays on ls",
      [f.child_shell == () for f in found] == [True, False, False, True]
      and found[1].redirects == [("2>", "/dev/null")] and found[0].redirects == [],
      [(list(f), f.child_shell, f.redirects) for f in found])
found = reader.simple_commands("cd /tmp | cat; grep -l needle *")
check("a cd that is a pipeline stage runs in a child shell, so the command after it is in the start directory",
      found[0].child_shell != () and found[-1].child_shell == (),
      [(list(f), f.child_shell) for f in found])
# tree-sitter-bash nests the misparse one level deeper when two stages have a redirection.
found = reader.simple_commands("git push origin w$i > $X/push$i.log 2>&1")
check("a redirection target that tree-sitter-bash splits after its last $ stays one target",
      [list(f) for f in found] == [["git", "push", "origin", "w$i"]]
      and found[0].redirects == [(">", "$X/push$i.log"), ("2>&", "1")],
      [(list(f), f.redirects) for f in found])
found = reader.simple_commands("cd /o && git log 2>/dev/null | head 2>/dev/null | cat; git push")
check("a cd before && counts after a pipeline in which two stages have a redirection",
      [list(f) for f in found] == [["cd", "/o"], ["git", "log"], ["head"], ["cat"], ["git", "push"]]
      and [f.child_shell == () for f in found] == [True, False, False, False, True]
      and found[1].redirects == [("2>", "/dev/null")] and found[2].redirects == [("2>", "/dev/null")],
      [(list(f), f.child_shell, f.redirects) for f in found])
# tree-sitter-bash joins a redirected command on the next line onto a long pipeline's last stage.
found = reader.simple_commands("make 2>&1 | tail -1 | sed s/a/b/\ncd /other >/dev/null\ngit push")
check("a redirected cd on the line after a pipeline of three stages runs in the parent shell",
      [list(f) for f in found] == [["make"], ["tail", "-1"], ["sed", "s/a/b/"], ["cd", "/other"],
                                    ["git", "push"]]
      and [f.child_shell == () for f in found] == [False, False, False, True, True]
      and found[3].redirects == [(">", "/dev/null")] and found[2].redirects == [],
      [(list(f), f.child_shell, f.redirects) for f in found])
found = reader.simple_commands("cat <<EOF | bash && ls\nx\nEOF")
check("a pipeline after a heredoc's delimiter ends at &&, and the heredoc reaches its later stage",
      [list(f) for f in found] == [["cat"], ["bash"], ["ls"]]
      and found[1].heredocs and found[1].heredocs[0].body == "x\n" and found[2].child_shell == ()
      and not found[2].heredocs, [(list(f), f.child_shell, f.heredocs) for f in found])
found = reader.simple_commands("(cd /a); f $(g) | h")
check("each child shell says its kind: a subshell, a substitution, or a pipeline stage that "
      "knows whether it is its pipeline's first",
      [[(shell.kind, shell.first_stage) for shell in f.child_shell] for f in found]
      == [[("subshell", False)], [("pipeline stage", True), ("substitution", False)],
          [("pipeline stage", True)], [("pipeline stage", False)]]
      and [f.inside_substitution() for f in found] == [False, True, False, False],
      [(list(f), f.child_shell) for f in found])
found = reader.simple_commands("x | cd /a && ls >o | head")
check("each stage of both pipelines in `x | cd /a && ls >o | head` runs in a child shell",
      all(f.child_shell != () for f in found) and found[2].redirects == [(">", "o")],
      [(list(f), f.child_shell, f.redirects) for f in found])
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


# --- the words and redirections after a heredoc's delimiter, on its own line ---
found = reader.simple_commands("git push <<EOF --force origin the-pr-branch >/dev/null\nx\nEOF")
check("a redirection after the words that follow a heredoc delimiter stays a redirection",
      [list(f) for f in found] == [["git", "push", "--force", "origin", "the-pr-branch"]]
      and (">", "/dev/null") in found[0].redirects, [(list(f), f.redirects) for f in found])
found = reader.simple_commands("git push <<EOF --force origin b | cat\nx\nEOF")
check("words after a heredoc delimiter followed by a pipe stay the command's words",
      [list(f) for f in found] == [["git", "push", "--force", "origin", "b"], ["cat"]],
      [(list(f), f.redirects) for f in found])
found = reader.simple_commands("f $(cat <<EOF -n) y\nx\nEOF\n")
check("a heredoc in a substitution that closes on its line is not moved out of it to the outer command",
      found and not any(f[:1] == ["f"] and f.heredocs for f in found),
      [(list(f), f.heredocs) for f in found])
found = reader.simple_commands("cat <<A <<B\na\nA\nb\nB")
check("of two heredocs on one line, the first keeps its own body",
      found and found[0].heredocs and found[0].heredocs[0].body == "a\n",
      [(list(f), f.heredocs) for f in found])
found = reader.simple_commands("cat <<'EOF' 2>/dev/null | bash\nx\nEOF")
check("a heredoc whose command has a redirection after the delimiter reaches the piped bash",
      [list(f) for f in found] == [["cat"], ["bash"]] and found[1].heredocs
      and found[1].heredocs[0].body == "x\n" and ("2>", "/dev/null") in found[0].redirects,
      [(list(f), f.redirects, f.heredocs) for f in found])
found = reader.simple_commands("cat <<EOF $(tmux send-keys -t a x) 2>&1 >out\nx\nEOF")
check("a substitution among the words after a heredoc delimiter still runs, with the line read again",
      ["tmux", "send-keys", "-t", "a", "x"] in [list(f) for f in found]
      and [list(f) for f in found][-1][:1] == ["cat"], [(list(f), f.redirects) for f in found])

# --- ;;& and ;& before esac ---
found = words_of("tmux send-keys -t 'a;& esac' Enter; case x in x) :;;& esac")
check("a ;& inside a quoted word is left as written when the case's ;;& is read as ;;",
      found[0] == ["tmux", "send-keys", "-t", "a;& esac", "Enter"], found)
found = words_of("cat <<'D'\n:;;& esac\nD\ncase x in x) :;& esac\ntmux kill-server")
check("a ;;& inside a heredoc body is left as written",
      found == [["cat"], [":"], ["tmux", "kill-server"]]
      and reader.simple_commands("cat <<'D'\n:;;& esac\nD\ncase x in x) :;& esac\ntmux kill-server")
      [0].heredocs[0].body == ":;;& esac\n", found)


# --- heredoc bodies with lines that only start with a delimiter, and nested heredocs ---
nested = ("bash <<'EOF'\ncat <<'EOF2' >a\nx\nEOF2\ncat <<'EOF3' >b\ny\nEOF3\n"
          "tmux send-keys -t seat-a x\nEOF")
found = reader.simple_commands(nested)
inner = words_of(found[0].heredocs[0].body) if found and found[0].heredocs else []
check("a body line starting with the outer delimiter, then a later heredoc: the body is whole",
      [list(f) for f in found] == [["bash"]]
      and "NEDSCHORUS_HEREDOC_END" not in found[0].heredocs[0].body
      and inner[-1:] == [["tmux", "send-keys", "-t", "seat-a", "x"]],
      ([(list(f), f.heredocs) for f in found], inner))
# A real Mac agent's command (cold-read-research, 2026-09), with a guarded line added before its end.
REAL_MAC_SSH_BASH_S = (
    "ssh -o BatchMode=yes nedlern@ned-box 'bash -s' <<'EOF'\n"
    "S=$(mktemp -d /tmp/cold-read-heredoc-probe-XXXXXX); echo \"S=$S\"\n"
    "for shell in bash sh; do\n"
    "  small=$($shell -c 'cat <<EOF\nSMALL_OK\nEOF' 2>&1)\n"
    "  big=$($shell -c \"cat <<'EOF' | wc -c\n$(head -c 100000 /dev/zero | tr '\\0' 'x')\nEOF\" 2>&1)\n"
    "  echo \"$shell outside any sandbox: small=[$small] big=[$big]\"\n"
    "done\n"
    "cd /; rm -rf $S\n"
    "tmux send-keys -t seat-a x\n"
    "EOF")
found = reader.simple_commands(REAL_MAC_SSH_BASH_S)
body = found[0].heredocs[0].body if found and found[0].heredocs else ""
check("the real Mac ssh 'bash -s' heredoc keeps its whole body, with no renamed word in it",
      "NEDSCHORUS_HEREDOC_END" not in body and body.endswith("tmux send-keys -t seat-a x\n")
      and ["tmux", "send-keys", "-t", "seat-a", "x"] in words_of(body), body[-200:])
found = words_of("cat <<OUTER\n$(tmux send-keys -t a Enter <<INNER\nx\nINNER\n)\nOUTER")
check("a heredoc inside a substitution inside another heredoc's body is read",
      ["tmux", "send-keys", "-t", "a", "Enter"] in found, found)
found = reader.simple_commands("cat <<EOF\n$(cat <<X\nXfoo\ntmux send-keys -t a x\nX\n)\nEOF\n")
check("a nested heredoc in a $( ) inside a body ends at its own delimiter line, not at a line starting with it",
      ["tmux", "send-keys", "-t", "a", "x"] not in [list(f) for f in found]
      and any(h.body == "Xfoo\ntmux send-keys -t a x\n" for f in found for h in f.heredocs),
      [(list(f), f.heredocs) for f in found])
found = reader.simple_commands("cat <<A\n$(cat <<B\nB)\ntmux send-keys -t s x\n")
check("a body that holds a renamed nested delimiter gets the original delimiter back",
      found and all("NEDSCHORUS_HEREDOC_END" not in h.body for f in found for h in f.heredocs)
      and any("$(cat <<B\nB)" in h.body for f in found for h in f.heredocs),
      [(list(f), f.heredocs) for f in found])
found = words_of('cat <<"E\'OF"\nbody\nE\'OF\ntmux kill-server')
check("a quote inside another quoting form in a delimiter ends the body at the bare word",
      found == [["cat"], ["tmux", "kill-server"]], found)
found = words_of("cat > n <<X\n$(a it's)\nEOF\nmore\nX\nls")
check("a body bash rejects, holding an EOF line, is read whole and none of it is a command",
      found == [["cat"], ["ls"]], found)

found = words_of("bash <<'EOF'\nEOFA\ncat <<'Z'\nEOF\ncat <<'Q'\nQx\ntmux kill-server\nQ\nls")
check("a heredoc the first parse lost inside a misplaced body is found on a later pass",
      found == [["bash"], ["cat"], ["ls"]], found)
found = words_of("cat > n <<X\nEOF\ntmux kill-server\n$(a it's)\nX\nls")
check("a rejected unquoted body holding an EOF line is reread whole: its lines are not commands",
      found == [["cat"], ["ls"]], found)

# --- words the first parse gives to the wrong node ---
for command, expected in [
    ("cat | tmux 2>/dev/null kill-server", [["cat"], ["tmux", "kill-server"]]),
    ("printf x | git push >err --force origin topic",
     [["printf", "x"], ["git", "push", "--force", "origin", "topic"]]),
    ("tmux <<EOF kill-server\nx\nEOF", [["tmux", "kill-server"]]),
    # A real fleet-restart-at-login command (Mac, 2026-09), shortened: tree-sitter-bash joins
    # the line after a pipeline of three or more onto its last stage when that line has a
    # redirection.
    ("diff <(cat a) <(cat b) | grep -c '^[<>]' | sed 's/^/x /'\n"
     "gh issue edit 343 --body-file b.md 2>&1 | tail -1",
     [["cat", "a"], ["cat", "b"], ["diff", "<(cat a)", "<(cat b)"], ["grep", "-c", "^[<>]"],
      ["sed", "s/^/x /"], ["gh", "issue", "edit", "343", "--body-file", "b.md"], ["tail", "-1"]]),
    ("a | b | c\ngit push -f o b 2>&1", [["a"], ["b"], ["c"], ["git", "push", "-f", "o", "b"]]),
    ("echo a \\\nb", [["echo", "a", "b"]]),
    ("case $v in a) b;;& esac; tmux kill-server", [["b"], ["tmux", "kill-server"]]),
    ("case $v in a) b;& esac\ngit push -f", [["b"], ["git", "push", "-f"]]),
]:
    check(f"every word reaches its command: {command!r}", words_of(command) == expected,
          words_of(command))
found = words_of('echo "`echo \\`tmux send-keys -t a b\\` x`"')
check("a backticked command nested in another, with escaped backticks, is read",
      found[0] == ["tmux", "send-keys", "-t", "a", "b"], found)

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
        reader.load_parser(importer_never, lambda: "installed", Clock(5000.0), lambda: False)
        raised = None
    except reader.ShellParserUnavailable as error:
        raised = error
    check("an install that finishes but leaves the import failing raises ShellParserUnavailable",
          raised is not None and "importing still fails" in raised.install_output
          and not isinstance(raised, reader.ShellParserInstalledForANewProcess), raised)
    record.unlink()

    try:
        reader.load_parser(importer_never, lambda: "installed", Clock(5100.0), lambda: True)
        raised = None
    except reader.ShellParserUnavailable as error:
        raised = error
    check("an install whose copy loads in a new process but not in this one is reported as "
          "installed for a new process, and is not recorded as a failure",
          isinstance(raised, reader.ShellParserInstalledForANewProcess) and not record.exists(),
          (raised, record.exists()))
    # This process cannot load the installed copy, so the command is read in a new process.
    command = "cd /x && ls 2>/dev/null | head; cat <<'E' >o\nbody\nE\ntmux send-keys -t a x"
    expected = [(list(f), f.child_shell, f.redirects, [(h.body, h.expanded, h.delimiter)
                                                      for h in f.heredocs])
                for f in reader.simple_commands(command, {"*": "<glob>"})]
    real_parser = reader.parser

    loads = []

    def parser_installed_for_a_new_process():
        loads.append(1)
        raise reader.ShellParserInstalledForANewProcess("installed")
    reader.parser = parser_installed_for_a_new_process
    try:
        found = [(list(f), f.child_shell, f.redirects, [(h.body, h.expanded, h.delimiter)
                                                       for h in f.heredocs])
                 for f in reader.simple_commands(command, {"*": "<glob>"})]
        found_again = [list(f) for f in reader.simple_commands("ls")]
    finally:
        reader.parser = real_parser
        reader._read_in_a_new_process = False
    check("when this process cannot load the installed parser, the command is read in a new process, "
          "with the same result", found == expected, (found, expected))
    check("later commands in the same process are read in a new process too, with no second try at "
          "loading the parser", found_again == [["ls"]] and loads == [1], (found_again, loads))

    def runner_failing(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, b"", b"Traceback: no parser")
    try:
        reader._simple_commands_in_a_new_process("ls", None, runner_failing)
        raised = None
    except reader.ShellParserUnavailable as error:
        raised = error
    check("a new process that fails to read the command raises ShellParserUnavailable with its error",
          raised is not None and "no parser" in raised.install_output, raised)

    # A copy that imported but could not be used stays in sys.modules until it is forgotten.
    class CachedUnusableTreeSitter:
        @staticmethod
        def Language(_language):
            raise TypeError("an incompatible tree-sitter version")
    saved_module = sys.modules.get("tree_sitter")
    sys.modules["tree_sitter"] = CachedUnusableTreeSitter
    installs = []
    try:
        parser = reader.load_parser(reader.import_tree_sitter_bash,
                                    lambda: installs.append(1) or "installed", Clock(5200.0),
                                    lambda: False)
        raised = None
    except reader.ShellParserUnavailable as error:
        parser, raised = None, error
    finally:
        if sys.modules.get("tree_sitter") is CachedUnusableTreeSitter and saved_module is not None:
            sys.modules["tree_sitter"] = saved_module
    check("before importing inside the lock, a cached copy that could not be used is dropped, "
          "so the installed one loads with no install",
          raised is None and parser is not None and parser.parse(b"ls").root_node.type == "program"
          and installs == [], (raised, installs))

    # The copy on disk is unusable until the install replaces it; the import inside the lock
    # caches it again, so it must be dropped once more after the install.
    MARKER = "tree_sitter.unusable_copy_marker"
    disk = {"usable": False}

    def importer_of_the_disk_copy():
        if MARKER in sys.modules:
            raise ImportError("the cached copy cannot be used")
        if not disk["usable"]:
            sys.modules[MARKER] = object()
            raise ImportError("the copy on disk cannot be used")
        return reader.import_tree_sitter_bash()
    try:
        parser = reader.load_parser(importer_of_the_disk_copy,
                                    lambda: disk.update(usable=True) or "installed",
                                    Clock(5300.0), lambda: False)
        raised = None
    except reader.ShellParserUnavailable as error:
        parser, raised = None, error
    finally:
        sys.modules.pop(MARKER, None)
    check("after an install, the unusable copy cached inside the lock is dropped and the "
          "installed one loads", raised is None and parser is not None, raised)

    # The real importer, in a process whose user site did not exist when it started.
    import tree_sitter as installed_tree_sitter
    import tree_sitter_bash as installed_tree_sitter_bash
    installed_site = Path(installed_tree_sitter.__file__).resolve().parents[1]
    probe = f"""
import importlib.util, json, shutil, site, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("r", {str(MODULE_PATH)!r})
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
r.STATE_DIRECTORY = Path(sys.argv[1]) / "state"
installs = []
def copy_libraries():
    target = Path(site.getusersitepackages()); target.mkdir(parents=True, exist_ok=True)
    for name in ("tree_sitter", "tree_sitter_bash"):
        shutil.copytree(Path({str(installed_site)!r}) / name, target / name)
def installer():
    installs.append(1); copy_libraries(); return "installed"
if sys.argv[2] == "installed-by-another-guard":
    copy_libraries()
try:
    parser = r.load_parser(installer=installer)
    print(json.dumps({{"ok": parser.parse(b"ls").root_node.type, "installs": len(installs)}}))
except r.ShellParserUnavailable as error:
    print(json.dumps({{"unavailable": error.install_output, "installs": len(installs)}}))
"""
    for situation, expected_installs in (("first-install", 1), ("installed-by-another-guard", 0)):
        user_base = Path(scratch) / f"user-base-{situation}"
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("PYTHONNOUSERSITE", "PYTHONPATH")}
        environment["PYTHONUSERBASE"] = str(user_base)
        completed = subprocess.run([sys.executable, "-c", probe, str(user_base), situation],
                                   capture_output=True, text=True, env=environment, timeout=120)
        try:
            outcome = json.loads(completed.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            outcome = {"stdout": completed.stdout, "stderr": completed.stderr[-2000:]}
        check(f"with a user site that did not exist at start-up ({situation}), the real import "
              f"succeeds after {expected_installs} install(s)",
              outcome.get("ok") == "program" and outcome.get("installs") == expected_installs,
              outcome)

    # A tree-sitter that imports but cannot build the bash language counts as missing.
    class BrokenTreeSitter:
        Parser = installed_tree_sitter.Parser

        @staticmethod
        def Language(_language):
            raise TypeError("an incompatible tree-sitter version")
    saved = sys.modules.get("tree_sitter")
    sys.modules["tree_sitter"] = BrokenTreeSitter
    try:
        reader.import_tree_sitter_bash()
        raised = None
    except ImportError as error:
        raised = error
    finally:
        sys.modules["tree_sitter"] = saved
    check("an installed tree-sitter that cannot build the bash language raises ImportError, "
          "so the pinned version is installed",
          raised is not None and "cannot be used" in str(raised), raised)

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

    first = context_of(reader.parser_unavailable_hook_output("The force-push guard", error, {}))
    again = context_of(reader.parser_unavailable_hook_output("The tmux kill guard", error, {}))
    unattended = context_of(reader.parser_unavailable_hook_output(
        "The tmux kill guard", error, {"CLAUDE_CODE_SESSION_ATTENDED": "0"}))
    check("the message says the command was not checked and has the user told, with what the "
          "install printed",
          "let this command through without checking it" in first
          and "Tell the user" in first and "network is unreachable" in first
          and str(reader.REQUIREMENTS_FILE) in first and "subagent" in first, first)
    check("every report has the user told again; nothing is counted",
          "Tell the user" in again and again.replace("tmux kill", "force-push") == first, again)
    on_ned_box = __import__("socket").gethostname().split(".")[0] == "ned-box"
    check("the install command for ned-box is given in the ssh form the user runs from the Mac",
          on_ned_box == ("ssh nedlern@ned-box 'python3 -m pip install" in first), first)
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
