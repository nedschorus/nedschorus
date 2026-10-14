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
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = Path(__file__).resolve().parents[1] / "shell-command-tree-sitter-bash-reader-common.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reader = load(MODULE_PATH, "shell_command_tree_sitter_bash_reader_common")

# Every command this test reads is read again at the end in a new process, which must give the
# same commands, classes and attributes included.
COMMANDS_READ = []
_simple_commands_as_loaded = reader.simple_commands


def simple_commands_recorded(command_text, glob_markers=None):
    COMMANDS_READ.append((command_text, glob_markers))
    return _simple_commands_as_loaded(command_text, glob_markers)


reader.simple_commands = simple_commands_recorded

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


ANSI_C_WORDS = [r"$'a\nb'", r"$'\t\x41\101\e\cA\c?'", r"$'it\'s \"x\" \?'", r"$'keep \q and \x and \u'",
                r"$'nul\0after'", r"a$'\n'b", r"$'\c\\x'", r"$'\0101\x4142'", r"$'\a\b\f\r\v\E'",
                r"$'\xff\x80 \351 a\xc3 \0401'", r"$'\777 \400'", r"$'\cé \c☃ \c\xe9'",
                r"$'\u00e9\U0001F600\u2603x \u41\u7f\u80'",
                r"$'\U110000 \U7FFFFFFF a\UFFFFFFFFb \uD800\uDFFF'", r"$'\uDC80\uDCFF a\uDCA0'"]


def ansi_c_words_bash_disagrees_with():
    """Return each of ANSI_C_WORDS whose decoded bytes differ from what bash passes, with both."""
    disagreements = []
    for word in ANSI_C_WORDS:
        expected = subprocess.run(["bash", "-c", f"printf %s {word}"], capture_output=True).stdout
        found = reader.simple_commands(f"printf %s {word}")[0][2].encode("utf-8", reader.SHELL_TEXT_ERRORS)
        if found != expected:
            disagreements.append((word, found, expected))
    return disagreements


# Run by the locale cases below, in a process whose locale they set.
if sys.argv[1:] == ["--ansi-c-words-in-this-locale"]:
    disagreements = ansi_c_words_bash_disagrees_with()
    print(reader._bash_ansi_c_escapes_written().unicode, disagreements)
    sys.exit(1 if disagreements else 0)


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

# --- a descriptor written as 0 before a redirect ---
for command, expected in [
    ("bash 0<f", [(["bash"], [("0<", "f")])]),
    ("bash 0<&-", [(["bash"], [("0<&-", "")])]),
    ("bash 0<&3", [(["bash"], [("0<&", "3")])]),
    ("bash 0<<<x z", [(["bash", "z"], [("0<<<", "x")])]),
    ("x | bash 0>f", [(["x"], []), (["bash"], [("0>", "f")])]),
    ("bash 10<f", [(["bash"], [("10<", "f")])]),
    ("bash 0 <f", [(["bash", "0"], [("<", "f")])]),
    ("bash 0 <<<x", [(["bash", "0"], [("<<<", "x")])]),
    ("bash 2>f", [(["bash"], [("2>", "f")])]),
    ("bash 0<<E\ntmux kill-server\nE\nls", [(["bash"], [("<<", "tmux kill-server\n")]), (["ls"], [])]),
    ("bash 0<<-E\n\tb\n\tE\nls", [(["bash"], [("<<", "b\n")]), (["ls"], [])]),
]:
    found = [(list(f), f.redirects) for f in reader.simple_commands(command)]
    check(f"the 0 before a redirect is its descriptor, not a word: {command!r}", found == expected, found)
# bash passes 0<(xb) to xa as one word, and a wrapper's option value written so is one word too.
found = [(list(f), f.redirects) for f in reader.simple_commands("xa 0<(xb)")]
check("a 0 written against a process substitution is part of its word",
      found == [(["xb"], []), (["xa", "0<(xb)"], [])], found)
words = list(reader.simple_commands("env -u 0<(printf x) git push")[-1])
check("a wrapper's option value written as 0<(...) leaves the program after it",
      reader.simple_command_program_index_skipping_wrappers(words) == (3, True), words)

# --- the program a command runs, after wrappers ---
for words, expected in [
    (["A=1", "bash"], (1, True)),
    (["timeout", "60", "bash"], (2, True)),
    (["timeout", "-s", "KILL", "60", "bash"], (4, True)),
    (["timeout", "--signal=KILL", "60", "bash"], (3, True)),
    (["timeout", "--kill-after", "5", "60", "bash"], (4, True)),
    (["sudo", "--user", "nedlern", "bash"], (3, True)),
    (["/usr/bin/sudo", "-u", "nedlern", "env", "A=1", "nice", "-n", "5", "bash"], (8, True)),
    (["env", "-i", "A=1", "grep"], (3, True)),
    (["time", "-p", "grep"], (2, True)),
    (["sudo", "--", "bash"], (2, True)),
    (["flock", "-w", "5", "/tmp/l", "bash"], (4, True)),
    (["caffeinate", "-t", "60", "bash"], (3, True)),
    (["xargs", "-n", "1", "bash"], (3, False)),
    (["tee", "/tmp/bash"], (0, True)),
    (["sudo", "-u", "nedlern"], (None, True)),
    (["env", "-u", "HOME", "bash"], (3, True)),
    (["env", "--unset", "HOME", "bash"], (3, True)),
    (["timeout", "-k", "5", "60", "bash"], (4, True)),
    (["timeout", "--signal", "KILL", "60", "bash"], (4, True)),
    (["timeout", "60", "--signal=KILL", "bash"], (3, True)),
    (["timeout", "60", "-s", "KILL", "bash"], (4, True)),
    (["flock", "/tmp/l", "-c", "bash"], (None, True)),
    (["env", "-a", "name", "bash"], (3, True)),
    (["env", "--argv0", "name", "bash"], (3, True)),
    (["env", "-f", "x.env", "bash"], (3, True)),
    (["env", "--file", "x.env", "bash"], (3, True)),
    (["env", "-P", "/bin", "bash"], (3, True)),
    (["sudo", "-R", "/root", "bash"], (3, True)),
    (["sudo", "-T", "60", "bash"], (3, True)),
    (["sudo", "-c", "staff", "bash"], (3, True)),
    (["sudo", "-a", "pam", "bash"], (3, True)),
    (["sudo", "--chroot", "/root", "bash"], (3, True)),
    (["sudo", "--command-timeout", "60", "bash"], (3, True)),
    (["sudo", "-hhost", "bash"], (2, True)),
    (["xargs", "-J", "%", "bash"], (3, False)),
    (["xargs", "-R", "2", "bash"], (3, False)),
    (["xargs", "-S", "255", "bash"], (3, False)),
    (["sudo", "-h", "bash"], (2, True)),
]:
    check(f"the program of {' '.join(words)} is word {expected[0]}, "
          f"{'receiving' if expected[1] else 'not receiving'} the standard input",
          reader.simple_command_program_index_skipping_wrappers(words) == expected, reader.simple_command_program_index_skipping_wrappers(words))

for words, expected in [
    (["env", "-u", "X", "-C", "/w", "git"], [("env", [("-u", "X"), ("-C", "/w")])]),
    (["/usr/bin/sudo", "-n", "--chdir=/w", "env", "-i", "git"],
     [("sudo", [("-n", None), ("--chdir", "/w")]), ("env", [("-i", None)])]),
    (["timeout", "60", "-s", "KILL", "git"], [("timeout", [("-s", "KILL")])]),
    (["env", "-C", "/a", "env", "-C", "b", "git"], [("env", [("-C", "/a")]), ("env", [("-C", "b")])]),
    (["nohup", "git"], [("nohup", [])]),
    (["env", "-C"], [("env", [("-C", None)])]),
    (["git", "-C", "/w"], []),
]:
    check(f"the options the wrappers of {' '.join(words)} are given",
          reader.simple_command_wrapper_options_and_values_parsed_from_words(words) == expected,
          reader.simple_command_wrapper_options_and_values_parsed_from_words(words))

found = reader.simple_commands("a | b; c | d")
check("each stage names the first stage of its own pipeline",
      [f.child_shell[-1].shell_pipeline_first_stage_byte_offset for f in found] == [0, 0, 7, 7], [f.child_shell for f in found])

# --- $'...' decoded as bash decodes it, with bash itself as the oracle ---
for locale in ["C.UTF-8", "C"]:
    found = subprocess.run([sys.executable, __file__, "--ansi-c-words-in-this-locale"], capture_output=True,
                           text=True, env={**os.environ, "LC_ALL": locale})
    # bash 4.2 and later writes UTF-8 or escapes by locale; an older bash, such as the Mac's 3.2,
    # keeps the escape. The reader asks this machine's bash, so agreeing with it is the test.
    check(f"$'...' words are the words this machine's bash passes, with LC_ALL={locale} "
          f"(the reader read bash as writing \\u {found.stdout.split()[0] if found.stdout else '?'})",
          found.returncode == 0, found.stdout + found.stderr)
# Each word in this process's locale too, so a disagreement names its word.
for word in ANSI_C_WORDS:
    expected = subprocess.run(["bash", "-c", f"printf %s {word}"], capture_output=True).stdout
    found = reader.simple_commands(f"printf %s {word}")[0][2].encode("utf-8", reader.SHELL_TEXT_ERRORS)
    check(f"{word} is the word bash passes", found == expected, (found, expected))
for written, word, expected in [
        ("kept", r"$'\u00e9\U1F600x'", "\\u00e9\\U1F600x"),
        ("escaped", r"$'\u00e9\u41\U1F600 \U110000 a\U80000000b'", "\\u00E9A\\U0001F600 \\U00110000 ab"),
        ("utf-8", r"$'\u00e9\u41\U1F600'", "éA\U0001F600")]:
    real = reader._bash_ansi_c_escapes_written
    reader._bash_ansi_c_escapes_written = lambda: reader._BashAnsiCEscapes(written, 0x7F, True)
    try:
        found = reader.simple_commands(f"printf %s {word}")[0][2]
    finally:
        reader._bash_ansi_c_escapes_written = real
    check(f"a bash that writes \\u {written} gives {word} as {expected!r}", found == expected, found)
real_run = reader.subprocess.run
for run, wanted, why in [
        (lambda *arguments, **options: (_ for _ in ()).throw(OSError("no bash")),
         reader._BASH_ESCAPES_WHEN_BASH_CANNOT_RUN, "bash cannot be run"),
        (lambda *arguments, **options: subprocess.CompletedProcess(arguments, 0, b"odd", b""),
         reader._BASH_ESCAPES_WHEN_BASH_CANNOT_RUN, "bash prints something else"),
        (lambda *arguments, **options: subprocess.CompletedProcess(
            arguments, 0, b"\\u00e9|\x1f|\x1c\\x", b""),
         reader._BashAnsiCEscapes("kept", 0x1F, False), "bash is 3.2")]:
    reader.subprocess.run = run
    reader._bash_ansi_c_escapes_written.cache_clear()
    try:
        written = reader._bash_ansi_c_escapes_written()
    finally:
        reader.subprocess.run = real_run
        reader._bash_ansi_c_escapes_written.cache_clear()
    check(f"when {why}, the escapes are read as {wanted}", written == wanted, written)
real = reader._bash_ansi_c_escapes_written
reader._bash_ansi_c_escapes_written = lambda: reader._BashAnsiCEscapes("kept", 0x1F, False)
try:
    found = reader.simple_commands(r"printf %s $'\c? \c\\x'")[0][2]
finally:
    reader._bash_ansi_c_escapes_written = real
check("a bash that writes \\c? as 0x1F and takes one backslash after \\c gives $'\\c? \\c\\\\x' so",
      found == "\x1f \x1c\\x", found)
# A decoded word read again as a command keeps its bytes, whatever they are.
for word in [r"$'\xe9; tmux send-keys -t g Enter'", r"$'\U110000; tmux kill-server'",
             r"$'\uD800\xff; tmux kill-server'"]:
    inner = reader.simple_commands(f"sh -c {word}")[0][2]
    again = reader.simple_commands(inner)
    check(f"the decoded word {word} reads again as a command, bytes kept",
          [list(f)[-1:] for f in again][-1] in (["Enter"], ["kill-server"])
          and inner.encode("utf-8", reader.SHELL_TEXT_ERRORS)
          == subprocess.run(["bash", "-c", f"printf %s {word}"], capture_output=True).stdout,
          [list(f) for f in again])
found = reader.simple_commands("echo \ud800x \udcff; tmux kill-server")
check("a lone surrogate from a JSON payload, and a byte that is not UTF-8, keep their words",
      [list(f) for f in found] == [["echo", "\ud800x", "\udcff"], ["tmux", "kill-server"]],
      [list(f) for f in found])
# Run in its own process under a deadline: a pattern that backtracks would hang this test.
timing_code = ("import importlib.util, sys; s = importlib.util.spec_from_file_location('r', sys.argv[1]); "
               "r = importlib.util.module_from_spec(s); s.loader.exec_module(r); "
               "r.simple_commands('case x in x) :;& ' + '#' * 60 + ' y\\nesac; case z in z) :;& ' + '#' * 60)")
try:
    started = time.monotonic()
    subprocess.run([sys.executable, "-c", timing_code, str(MODULE_PATH)], timeout=20, check=True,
                   capture_output=True)
    timing = time.monotonic() - started
except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as problem:
    timing = repr(problem)
check("a run of # after a terminator is matched in linear time",
      isinstance(timing, float) and timing < 10, timing)
found = reader.simple_commands("ssh h $'true\\ntmux kill-server'")
check("an ANSI-C quoted remote command keeps its newline, so the command after it is seen",
      found[0][2] == "true\ntmux kill-server", list(found[0]))

found = words_of("echo 'a;&' 'a;;'; case x in x) :;& esac")
check("a repaired ;& leaves a quoted ;; elsewhere in the command as written", found[0] == ["echo", "a;&", "a;;"], found)
found = words_of("cat <<A\n$(echo 'a;&' 'a;;'; case x in x) :;& esac)\nA")
check("a repaired ;& in a body leaves a quoted ;; elsewhere in the body as written",
      found[0] == ["echo", "a;&", "a;;"], found)
timing_code = ("import importlib.util, sys; s = importlib.util.spec_from_file_location('r', sys.argv[1]); "
               "r = importlib.util.module_from_spec(s); s.loader.exec_module(r); "
               "print(list(r.simple_commands('cat <<A\\n' + '$(case x in x) :;& esac)\\n' * 2000 "
               "+ '$(tmux kill-server)\\nA')[-2]))")
try:
    started = time.monotonic()
    last = subprocess.run([sys.executable, "-c", timing_code, str(MODULE_PATH)], timeout=60, check=True,
                          capture_output=True, text=True).stdout.strip()
    timing = time.monotonic() - started
except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as problem:
    last, timing = None, repr(problem)
check("a body holding 2,000 cases ended by ;& is repaired in one pass, and the command after them is read",
      isinstance(timing, float) and timing < 30 and last == "['tmux', 'kill-server']", (timing, last))
# The offsets of the terminators one round writes are moved once, not once per terminator; with the
# parse's own checks made free, 30,000 of them take seconds, and a quadratic shift takes minutes.
timing_code = ("import importlib.util, sys; s = importlib.util.spec_from_file_location('r', sys.argv[1]); "
               "r = importlib.util.module_from_spec(s); s.loader.exec_module(r); "
               "r._inside_text = lambda *arguments, **options: False; "
               "found = r._source_with_case_terminators_repaired("
               "b'$(case x in x) :;& esac)\\n' * 30000, r.TEXT_NODE_TYPES, all_at_once=True); "
               "print(len(found[3]))")
try:
    started = time.monotonic()
    restored_count = subprocess.run([sys.executable, "-c", timing_code, str(MODULE_PATH)], timeout=60,
                                    check=True, capture_output=True, text=True).stdout.strip()
    timing = time.monotonic() - started
except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as problem:
    restored_count, timing = None, repr(problem)
check("30,000 terminators written in one round have their offsets moved in linear time",
      isinstance(timing, float) and timing < 10 and restored_count == "30000", (timing, restored_count))
# Each ;;& written as ;; shortens the text, so a later terminator's offset in the command as written is further on.
found = words_of("case a in a) :;;& esac; " * 20 + "echo 'x;;' $(case b in b) :;& esac)")
check("a terminator repaired after twenty that shortened the text is put back where it was written",
      found[-1] == ["echo", "x;;", "$(case b in b) :;& esac)"], found[-1])
found = words_of("cat <<A\n$( (xa) ) $((1 + 2))\nA")
check("a body's $( ( ) ) with a space between the parentheses is a substitution, and its subshell runs",
      found[0] == ["xa"], found)
found = words_of("echo $(( $(printf 1 '(') + (tmux - send-keys) ))")
check("arithmetic whose substitution holds a quoted ( is arithmetic, and only its substitution runs",
      found == [["printf", "1", "("], ["echo", "$(( $(printf 1 '(') + (tmux - send-keys) ))"]], found)
found = words_of("cat <<A\n$(( $(printf 1 '(') + (tmux - send-keys) ))\nA")
check("in a body, arithmetic whose substitution holds a quoted ( runs only its substitution",
      found == [["printf", "1", "("], ["cat"]], found)
for command, expected in [
        ("echo ';;'; case x in x) :;& esac", ["echo", ";;"]),
        ("echo \"$(case x in x) :;;& esac)\" ';;'", ["echo", "$(case x in x) :;;& esac)", ";;"]),
        ("cat <<A\n$(echo $(case x in x) :;& esac))\nA", ["echo", "$(case x in x) :;& esac)"]),
        ("cat <<A\n`echo $(case x in x) :;& esac)`\nA", ["echo", "$(case x in x) :;& esac)"]),
        ("echo `echo \\`case x in x) :;& esac\\``", ["echo", "`case x in x) :;& esac`"]),
        # The body taken out before the terminator moves its offset in the text parsed.
        ("cat <<E\nbody line\nE\necho $(case x in x) :;& esac)", ["echo", "$(case x in x) :;& esac)"]),
        # A ;;& written as ;; in the same round moves the terminator after it.
        ("cat <<A\n$(echo $(case a in a) :;;& esac) $(case b in b) :;& esac))\nA",
         ["echo", "$(case a in a) :;;& esac)", "$(case b in b) :;& esac)"]),
        # A part of a word read in parts.
        ("xa a$(case x in x) :;& esac)", ["xa", "a$(case x in x) :;& esac)"])]:
    found = words_of(command)
    check(f"a repaired terminator reads as written only in the word that holds it: {command!r}",
          expected in found, found)

# --- a leading ~ that bash expands, with bash as the oracle ---
tilde_words = ["~", "~/x", '"~/x"', "\\~/x", '~"/x"', "~'/x'", "--chdir=~/x", "-C~/x", "x~/y",
               "~nosuchuser-here/x", '~/x"y"', "$'~/x'"]
saved_home = os.environ.get("HOME")
os.environ["HOME"] = "/home-for-test"
try:
    command = "printf '%s\\n' " + " ".join(tilde_words)
    expected = subprocess.run(["bash", "-c", command], capture_output=True, text=True).stdout.split("\n")
    found = [reader.shell_word_tilde_prefix_expand_as_bash_would(word)
             for word in reader.simple_commands(command)[0][2:]]
    for word, found_word, expected_word in zip(tilde_words, found, expected):
        check(f"{word} is expanded as bash expands it", found_word == expected_word, (found_word, expected_word))
    for command, index in [("cd ~/$'\\xff'", 1), ("cd ~/\ud800x", 1)]:
        found = reader.simple_commands(command)[0]
        check(f"a word read again for a character split in two keeps its leading ~ expanded: {command!r}",
              isinstance(found[index], reader.ShellWordWithUnexpandedTildePrefixBashWouldExpand), [type(word) for word in found])
    found = reader.simple_commands("cat > ~/x$X/push$i.log")[0]
    check("a redirection target read in parts keeps its leading ~ expanded",
          isinstance(found.redirects[0][1], reader.ShellWordWithUnexpandedTildePrefixBashWouldExpand), found.redirects)
    found = reader.simple_commands("ls ~/$(cat <<E\nx\nE\n)")[-1]
    check("a word that held a heredoc keeps its leading ~ expanded",
          reader.shell_word_tilde_prefix_expand_as_bash_would(found[1])
          .startswith("/home-for-test/$(cat <<E"), list(found))
finally:
    if saved_home is None:
        os.environ.pop("HOME", None)
    else:
        os.environ["HOME"] = saved_home

# --- a heredoc body walked as bash expands it ---
for body, expected in [
    # tree-sitter-bash splits a backticked command inside ${ }.
    ("${v:-`echo $(printf x); tmux send-keys -t a b`}", [["printf", "x"], ["echo", "$(printf x)"],
                                                       ["tmux", "send-keys", "-t", "a", "b"]]),
    # tree-sitter-bash puts an escaped $( and the backticks after it outside the body's node.
    ("\\$(echo `tmux send-keys -t a b`)\n$(printf x)", [["tmux", "send-keys", "-t", "a", "b"], ["printf", "x"]]),
    # $(( whose inner ( closes before a ; is a substitution holding two subshells.
    ("$((xa); (xb))", [["xa"], ["xb"]]),
    ("$(( $(xc) + 1 ))", [["xc"]]),
    # Order is by byte offset, after multi-byte text.
    ("é" * 20 + " $(xa) `xb`", [["xa"], ["xb"]]),
]:
    found = [list(f) for f in reader.simple_commands(f"cat <<A\n{body}\nA")][:-1]
    check(f"the body {body!r} runs the commands bash runs", found == expected, found)
found = reader.simple_commands("cat <<A\n`cd /tmp; echo $(git push -f origin topic)`\nA")
check("a substitution inside a backticked command runs in its child shell, after its cd",
      [list(f) for f in found][:2] == [["cd", "/tmp"], ["git", "push", "-f", "origin", "topic"]]
      and found[1].child_shell[:len(found[0].child_shell)] == found[0].child_shell,
      [(list(f), f.child_shell) for f in found])
found = reader.simple_commands("cat <<A\n$(tmux send-keys -t 'a;& esac' Enter) $(case x in x) :;& esac)\nA")
check("a body's case repair leaves a quoted ;& esac inside a substitution as written",
      list(found[0]) == ["tmux", "send-keys", "-t", "a;& esac", "Enter"], [list(f) for f in found])

# --- ;& before a comment, and a repaired case inside a word ---
check("a ;& followed by a comment and then esac is repaired, and the command after the case is read",
      words_of("case x in x) :;& # note\nesac\ntmux kill-server")[-1] == ["tmux", "kill-server"],
      words_of("case x in x) :;& # note\nesac\ntmux kill-server"))
for command, word in [("echo $(case x in x) :;& esac)", "$(case x in x) :;& esac)"),
                      ('echo "$(case x in x) :;;& esac)" y', "$(case x in x) :;;& esac)")]:
    found = words_of(command)
    check(f"a word holding a repaired case keeps its terminator as written: {command!r}",
          found[-1][1] == word, found)
found = words_of("echo $(case a in a) :;& esac) $(case a in a) :;; esac)")
check("two words that differ only in their terminators each keep their own",
      found[-1][1:] == ["$(case a in a) :;& esac)", "$(case a in a) :;; esac)"], found)

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
# What follows && or || on a heredoc's line is read, whatever kind of command it is.
for operator in ("&&", "||"):
    for compound in ("{ git push -f o t; }", "(git push -f o t)", "if true; then git push -f o t; fi",
                     "while true; do git push -f o t; done", "case x in x) git push -f o t;; esac"):
        command = f"python3 - <<'PY' {operator} {compound}\nprint(1)\nPY"
        found = [list(f) for f in reader.simple_commands(command)]
        check(f"a command after {operator} on a heredoc's line is read: {compound}",
              ["git", "push", "-f", "o", "t"] in found and found[0][:1] == ["python3"], found)
for separator, delimiter in ((";", "'EOF'"), ("&", "'EOF'"), (";", "EOF"), ("&", "EOF")):
    found = reader.simple_commands(f"cat <<{delimiter}{separator} git push -f o t\nx\nEOF")
    check(f"a command after {separator} on a heredoc's line is a command of its own, not cat's words",
          [list(f) for f in found] == [["cat"], ["git", "push", "-f", "o", "t"]]
          and found[0].heredocs[0].body == "x\n", [(list(f), f.heredocs) for f in found])
found = reader.simple_commands("cat <<EOF|bash\nx\nEOF")
check("a bare delimiter ends at |, as bash ends it, and the heredoc reaches the piped bash",
      [list(f) for f in found] == [["cat"], ["bash"]] and found[1].heredocs
      and found[1].heredocs[0].body == "x\n", [(list(f), f.heredocs) for f in found])
for command, expected_words in [
    ("cat <<EOF # a comment\nhi\nEOF", ["cat"]),
    ("git push<<EOF --force origin b\nx\nEOF", ["git", "push", "--force", "origin", "b"]),
    ("git push 3<<EOF --force origin b\nx\nEOF", ["git", "push", "--force", "origin", "b"]),
    ("git push <<EOF \\\n --force origin b\nx\nEOF", ["git", "push", "--force", "origin", "b"]),
]:
    found = reader.simple_commands(command)
    check(f"the heredoc keeps its body and its command its words: {command!r}",
          [list(f) for f in found] == [expected_words] and found[0].heredocs
          and found[0].heredocs[0].body in ("hi\n", "x\n"),
          [(list(f), f.heredocs) for f in found])
found = reader.simple_commands("x=$(git push <<EOF --force origin b)\nx\nEOF")
check("words after the delimiter of a heredoc in a substitution that closes on its line stay the "
      "command's words, and the heredoc keeps its body",
      [list(f) for f in found][:1] == [["git", "push", "--force", "origin", "b"]]
      and found[0].heredocs and found[0].heredocs[0].body == "x\n"
      and ["x"] not in [list(f) for f in found], [(list(f), f.heredocs) for f in found])
found = reader.simple_commands('>"/tmp/probe-$(tmux send-keys -t gatekeeper Enter)"')
check("the substitution in a statement that is only a redirection is read",
      [list(f) for f in found] == [["tmux", "send-keys", "-t", "gatekeeper", "Enter"]],
      [list(f) for f in found])
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

# --- heredoc bodies are taken out before the parse, by bash's own rules ---
for command, expected in [
    # The normal form has no newline after the delimiter line.
    ("cat <<'EOF'; ls\nx\nEOF", [(["cat"], ["x\n"]), (["ls"], [])]),
    ("cat <<'EOF'; ls\nx\nEOF\n", [(["cat"], ["x\n"]), (["ls"], [])]),
    ("cat <<EOF ; xb ; xc\nx\nEOF", [(["cat"], ["x\n"]), (["xb"], []), (["xc"], [])]),
    # A here-string on the heredoc's line is not a second heredoc.
    ("cat <<EOF; grep x <<< y\ngit push -f origin topic\nEOF",
     [(["cat"], ["git push -f origin topic\n"]), (["grep", "x"], [])]),
    # A heredoc in a substitution that closes on its line keeps its body as data.
    ("y=$(cat <<EOF)\ngit push -f origin topic\nEOF", [(["cat"], ["git push -f origin topic\n"])]),
    ("cat <<EOF && x=$(xa; xb c); xd e\nbody\nEOF",
     [(["cat"], ["body\n"]), (["xa"], []), (["xb", "c"], []), (["xd", "e"], [])]),
    ("cat <<'E;F'\nb\nE;F", [(["cat"], ["b\n"])]),
    ("cat <<E\\;F; xa b\nbody\nE;F", [(["cat"], ["body\n"]), (["xa", "b"], [])]),
    ("cat <<-EOF; xb c\nbody\n\tEOF", [(["cat"], ["body\n"]), (["xb", "c"], [])]),
    # A backslash at the end of a comment does not continue the heredoc's line.
    ("cat <<EOF # note \\\nbody line\nEOF\nls", [(["cat"], ["body line\n"]), (["ls"], [])]),
    # The body starts after the line that opens it, which may run on in a quoted string.
    ('cat <<EOF && echo "a\nb"; ls\nbody\nEOF',
     [(["cat"], ["body\n"]), (["echo", "a\nb"], []), (["ls"], [])]),
    # bash keeps a body's leading blank line and leading spaces.
    ("cat <<'EOF'\n\n  x\nEOF", [(["cat"], ["\n  x\n"])]),
    # A line that only starts with the delimiter is body; the first line that is exactly
    # the delimiter ends it, as bash ends it, even inside what looks like a quoted string.
    ("bash <<'EOF'\nsh -c 'cat <<EOF\nEOF\nls", [(["bash"], ["sh -c 'cat <<EOF\n"]), (["ls"], [])]),
]:
    found = [(list(f), [h.body for h in f.heredocs]) for f in reader.simple_commands(command)]
    check(f"heredoc read as bash reads it: {command!r}", found == expected, found)
found = reader.simple_commands("cat <<EOF\n$(tmux send-keys -t a b\nEOF")
check("a substitution in a body that never closes runs nothing", [list(f) for f in found] == [["cat"]],
      [list(f) for f in found])
found = reader.simple_commands("cat <<EOF\n$(echo `tmux send-keys -t a b`)\nEOF")
check("a backticked command inside a body's $( ) is read once",
      [list(f) for f in found].count(["tmux", "send-keys", "-t", "a", "b"]) == 1, [list(f) for f in found])
found = reader.simple_commands("cat < NEDSCHORUS_HEREDOC_0 <<EOF\nx\nEOF")
check("a file of the name a heredoc stands in for is still a file",
      found and found[0].redirects == [("<", "NEDSCHORUS_HEREDOC_0"), ("<<", "x\n")],
      [(list(f), f.redirects) for f in found])
found = reader.simple_commands("python3 - <<'PY'\nprint(1)\nPY")
check("the - of `python3 - <<'PY'` stays a word", [list(f) for f in found] == [["python3", "-"]],
      [list(f) for f in found])
found = reader.simple_commands('git commit -m "$(cat <<\'EOF\'\nmessage\nEOF\n)"')
check("a word holding a heredoc is given back as written, body included",
      [list(f) for f in found] == [["cat"], ["git", "commit", "-m", "$(cat <<'EOF'\nmessage\nEOF\n)"]],
      [list(f) for f in found])

# --- a heredoc body starts at the next line, and its substitutions run in order ---
for command, expected in [
    # A group that opens on the heredoc's line and closes later: the body still starts next line.
    ("cat <<EOF && (xa\nbody\nEOF\n)\nxc d", [(["cat"], ["body\n"]), (["xa"], []), (["xc", "d"], [])]),
    ("cat <<EOF && { xa\nbody\nEOF\n}\nxc d", [(["cat"], ["body\n"]), (["xa"], []), (["xc", "d"], [])]),
    # A heredoc after a case ended by ;;& is taken out too, once the case is read.
    ("case x in x) :;;& esac; bash <<'EOF'\nEOF2\ntmux send-keys -t a b\nEOF",
     [([":"], []), (["bash"], ["EOF2\ntmux send-keys -t a b\n"])]),
    # Inside double quotes a backslash keeps " literal in a delimiter.
    ('cat <<"E\\"F"\nbody\nE"F\nls', [(["cat"], ["body\n"]), (["ls"], [])]),
    # A heredoc inside a body's substitution is taken out before the substitution is read.
    ("cat <<A\n$(cat <<B; xz\nb\nB\n)\nA",
     [(["cat"], ["b\n"]), (["xz"], []), (["cat"], ["$(cat <<B; xz\nb\nB\n)\n"])]),
    # bash rejects a body whose substitution never closes; it is still read, so a guard refuses
    # a command bash would not run rather than pass one it would.
    ("cat <<A\n$(echo $(tmux send-keys -t a b)\nA",
     [(["tmux", "send-keys", "-t", "a", "b"], []), (["cat"], ["$(echo $(tmux send-keys -t a b)\n"])]),
    # $(( that closes with )) is arithmetic, and its substitutions run; one that does not is a
    # substitution holding a subshell.
    ("cat <<A\n$(( $(tmux kill-server; printf 1) + 2 ))\nA",
     [(["tmux", "kill-server"], []), (["printf", "1"], []),
      (["cat"], ["$(( $(tmux kill-server; printf 1) + 2 ))\n"])]),
    ("cat <<A\n$((tmux kill-server); printf x)\nA",
     [(["tmux", "kill-server"], []), (["printf", "x"], []), (["cat"], ["$((tmux kill-server); printf x)\n"])]),
    # Inside backticks \` opens a nested backticked command.
    ("cat <<A\n`echo \\`xb\\``\nA", [(["xb"], []), (["echo", "`xb`"], []), (["cat"], ["`echo \\`xb\\``\n"])]),
    # A body line that the reader's own delimiter would end.
    ("cat <<A\nNEDSCHORUS_BODY_END\n'$(xa)'\nA", [(["xa"], []), (["cat"], ["NEDSCHORUS_BODY_END\n'$(xa)'\n"])]),
    # A case ended by ;;& inside a body's substitution, and a substitution after it.
    ("cat <<A\n$(case x in x) :;;& esac) $(tmux kill-server)\nA",
     [([":"], []), (["tmux", "kill-server"], []), (["cat"], ["$(case x in x) :;;& esac) $(tmux kill-server)\n"])]),
    # A backticked command that holds a substitution, an escaped backtick, and one never closed.
    ("cat <<A\n`xa $(xb) xc` \\`xd\\` `xe\nA",
     [(["xb"], []), (["xa", "$(xb)", "xc"], []), (["cat"], ["`xa $(xb) xc` \\`xd\\` `xe\n"])]),
    # Substitutions run in the order written; $(( )) is arithmetic, $$( the process id.
    ("cat <<A\n$(xa) $(xb) `xc` $(xd)\nA",
     [(["xa"], []), (["xb"], []), (["xc"], []), (["xd"], []), (["cat"], ["$(xa) $(xb) `xc` $(xd)\n"])]),
    ("cat <<A\n$((1+2)) $$(xe) \\$(xf) $(xg)\nA",
     [(["xg"], []), (["cat"], ["$((1+2)) $$(xe) \\$(xf) $(xg)\n"])]),
]:
    found = [(list(f), [h.body for h in f.heredocs]) for f in reader.simple_commands(command)]
    check(f"heredoc read as bash reads it: {command!r}", found == expected, found)
tabbed = "cat <<A\n$(cat <<-'B'\n" + "\tx\n" * 30 + "\tB\n)\n$(echo '$(tmux kill-server)')\nA"
check("a <<- heredoc inside a body's substitution is read once, and quoted text after it is no command",
      [list(f) for f in reader.simple_commands(tabbed)]
      == [["cat"], ["echo", "$(tmux kill-server)"], ["cat"]], [list(f) for f in reader.simple_commands(tabbed)])
started = time.monotonic()
found = reader.simple_commands("cat <<A\n" + "$(printf 1)\n" * 3500 + "A")
check("a body of 3,500 substitutions is read in one parse, well inside a guard's 30 s",
      len(found) == 3501 and time.monotonic() - started < 3, (len(found), time.monotonic() - started))
found = reader.simple_commands("cat <<A\n$(cd /x)\nA\ncat <<B\n$(git push -f o t)\nB")
check("substitutions in two different bodies are different child shells, so a cd in one stays there",
      found[0].child_shell != found[2].child_shell
      and found[0].child_shell[0].offset < 0 and found[2].child_shell[0].offset < 0,
      [(list(f), f.child_shell) for f in found])
many = "".join(f"cat <<E{n}\nx\nE{n}\n" for n in range(reader.MAX_HEREDOCS_TAKEN_OUT + 2))
found = reader.simple_commands(many + "bash <<Z\ntmux send-keys -t a b\nZ")
check("a heredoc past the most that are taken out is still read as data fed to its command",
      list(found[-1]) == ["bash"] and [h.body for h in found[-1].heredocs] == ["tmux send-keys -t a b\n"],
      (list(found[-1]), found[-1].heredocs))
found = reader.simple_commands("echo hi | w | od -c | head -2\ncat > f <x\ncat > g <y\n"
                               "cd $(tmux send-keys -t a b) && for t in a b; do e; done; cat o")
check("a substitution on a line folded into a redirection is read once",
      [list(f) for f in found].count(["tmux", "send-keys", "-t", "a", "b"]) == 1, [list(f) for f in found])

# --- a pipeline stage that is only a redirection, and lines folded into a redirection ---
found = reader.simple_commands("a | >f && cd /x")
check("a stage that is only a redirection ends its pipeline, so the command after && is not a stage",
      [(list(f), f.child_shell == ()) for f in found] == [(["a"], False), (["cd", "/x"], True)],
      [(list(f), f.child_shell) for f in found])
found = reader.simple_commands("echo hi | w | od -c | head -2\ncat > f <<'A'\nx\nA\ncat > g <<'B'\ny\nB\n"
                               "cd /p && ls")
check("the lines tree-sitter-bash folds into a long pipeline's redirections are commands of their own",
      [list(f) for f in found] == [["echo", "hi"], ["w"], ["od", "-c"], ["head", "-2"], ["cat"], ["cat"],
                                   ["cd", "/p"], ["ls"]]
      and [h.body for h in found[4].heredocs] == ["x\n"] and found[6].child_shell == (),
      [(list(f), f.child_shell) for f in found])

# --- ;;& and ;& before esac ---
found = words_of("cat <<'EOF'\nEOF2\ncat <<D\nEOF\ncase x in x) :;& esac\ntmux kill-server")
check("a case after a body tree-sitter-bash misplaces is repaired, and the command after it is read",
      found == [["cat"], [":"], ["tmux", "kill-server"]], found)
for command in ["case y in y) xa <<E ;&\n$(tmux send-keys -t a b)\nE\nesac\ncase x in x) :;& esac\nxc",
                "case x in x) cat <<E ;&\n$(tmux send-keys -t a b)\n;& esac\nE\nesac\nls"]:
    found = words_of(command)
    check(f"a ;& on a heredoc's line, with esac after the body, is repaired without touching the body: {command!r}",
          ["tmux", "send-keys", "-t", "a", "b"] in found and found[-1] in (["xc"], ["ls"]), found)
found = reader.simple_commands("case x in x) :;& esac; cat <<'D'\n:;& esac\nD\nls")
check("a ;& in a body that the case's error hid is left as written",
      [list(f) for f in found] == [[":"], ["cat"], ["ls"]] and found[1].heredocs[0].body == ":;& esac\n",
      [(list(f), f.heredocs) for f in found])
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
      and "NEDSCHORUS_HEREDOC" not in found[0].heredocs[0].body
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
check("the real Mac ssh 'bash -s' heredoc keeps its whole body, with no placeholder in it",
      "NEDSCHORUS_HEREDOC" not in body and body.endswith("tmux send-keys -t seat-a x\n")
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
check("a body that holds a nested heredoc keeps it as written",
      found and all("NEDSCHORUS_HEREDOC" not in h.body for f in found for h in f.heredocs)
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
          "with the same result, each child shell whole", found == expected, (found, expected))
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

    # The reader failing in the new process reaches this process as ShellCommandUnreadable.
    real_collect, real_stdin, real_stdout = reader._collect, sys.stdin, sys.stdout

    def failing_collect(*arguments, **keywords):
        raise ValueError("injected")

    class Bytes:
        def __init__(self, data=b""):
            self.buffer = io.BytesIO(data)
    child_out = Bytes()
    reader._collect, sys.stdin, sys.stdout = (
        failing_collect, Bytes(json.dumps({"command": "ls", "glob_markers": None}).encode()), child_out)
    try:
        reader._read_command_on_standard_input()
    finally:
        reader._collect, sys.stdin, sys.stdout = real_collect, real_stdin, real_stdout

    def runner_answering(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, child_out.buffer.getvalue(), b"")
    try:
        reader._simple_commands_in_a_new_process("ls", None, runner_answering)
        raised = None
    except reader.ShellParserUnavailable as error:
        raised = error
    check("the reader failing in a new process raises ShellCommandUnreadable here, with the failure",
          isinstance(raised, reader.ShellCommandUnreadable) and "ValueError: injected" in str(raised),
          (raised, child_out.buffer.getvalue()))

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
    printed = reader.install_pinned_python_libraries(run)
    check("the install runs pip per user, from the pinned requirements file, within its timeout",
          run.command[1:7] == ["-m", "pip", "install", "--user", "--break-system-packages",
                               "--disable-pip-version-check"]
          and run.command[-2:] == ["-r", str(reader.REQUIREMENTS_FILE)]
          and run.kwargs["timeout"] == reader.INSTALL_TIMEOUT_SECONDS
          and "Successfully installed" in printed, (run.command, run.kwargs))
    try:
        reader.install_pinned_python_libraries(runner_exiting(1, "", "ERROR: No matching distribution"))
        raised = None
    except reader.ShellParserUnavailable as error:
        raised = error
    check("pip exiting nonzero raises ShellParserUnavailable with its output",
          raised is not None and "No matching distribution" in raised.install_output
          and "exited 1" in raised.install_output, raised)

    def runner_timing_out(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])
    try:
        reader.install_pinned_python_libraries(runner_timing_out)
        raised = None
    except reader.ShellParserUnavailable as error:
        raised = error
    check("pip timing out raises ShellParserUnavailable saying it did not finish",
          raised is not None and "did not finish" in raised.install_output, raised)
    check("the pinned requirements file pins tree-sitter and tree-sitter-bash",
          {line.split("==")[0] for line in reader.REQUIREMENTS_FILE.read_text().splitlines()
           if "==" in line} >= {"tree-sitter", "tree-sitter-bash"})

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
    this_host = __import__("socket").gethostname().split(".")[0]
    install = reader.tree_sitter_bash_install_failure_report_words_build(
        this_host, "", "").splitlines()[1]
    check("the install command stands on a line of its own in the message",
          install in first.splitlines(), first)
    check("the words to report include the command, as a fenced code block, and what was undone",
          reader.COMMAND_AS_FENCED_CODE_BLOCK_INSTRUCTION in first and "what you undid" in first
          and "what you could not undo" in first, first)
    words = reader.tree_sitter_bash_install_failure_report_words_build(
        "ned-box", "pip: no network", "nothing is checked there").splitlines()
    check("for ned-box, the install command is the ssh form the user runs in a Terminal on the Mac",
          words[0].endswith("so nothing is checked there. To install it by hand, run this command "
                            "in a Terminal on your Mac:\" Then give the install command on a line "
                            "of its own:")
          and words[1] == f"ssh nedlern@ned-box '{sys.executable} -m pip install --user "
          f"--break-system-packages -r {reader.REQUIREMENTS_FILE}'", words)
    check("the words to report end with what the install printed, quoted as it is",
          words[2:] == ["Then pass on what the install printed, quoted as it is: pip: no network"],
          words)
    words = reader.tree_sitter_bash_install_failure_report_words_build(
        "Neds-MacBook", "pip: no network", "nothing is checked there").splitlines()
    check("for any other machine, the install command is run on that machine as it is",
          "run this command on Neds-MacBook:" in words[0]
          and words[1] == f"{sys.executable} -m pip install --user --break-system-packages "
          f"-r {reader.REQUIREMENTS_FILE}", words)
    real_executable = sys.executable
    sys.executable = "/usr/bin/python3"
    try:
        words = reader.tree_sitter_bash_install_failure_report_words_build(
            "Neds-MacBook", "pip: no network", "nothing is checked there").splitlines()
    finally:
        sys.executable = real_executable
    check("the install command names the interpreter the guard runs under, not a bare python3",
          words[1].startswith("/usr/bin/python3 -m pip install "), words)
    on_ned_box = __import__("socket").gethostname().split(".")[0] == "ned-box"
    check("the install command for ned-box is given in the ssh form the user runs from the Mac",
          on_ned_box == (f"ssh nedlern@ned-box '{sys.executable} -m pip install" in first), first)
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

    unreadable = reader.ShellCommandUnreadable("ValueError: injected")
    attended = context_of(reader.parser_unavailable_hook_output("The force-push guard", unreadable, {}))
    unattended = context_of(reader.parser_unavailable_hook_output(
        "The force-push guard", unreadable, {"CLAUDE_CODE_SESSION_ATTENDED": "0"}))
    check("when the reader fails, the guard's message says the command ran and what to check and undo",
          "the command has run" in attended and "Look at what the command did" in attended
          and "undo" in attended and "Tell the user" in attended and "ValueError: injected" in attended,
          attended)
    check("in an agent-session no user attends, the reader-failed message does not ask to tell the user",
          "do not tell the user" in unattended and "Tell the user" not in unattended
          and "If you are a subagent, tell the agent that dispatched you" in unattended, unattended)
    check("the reader-failed message says where the command goes, and in what form",
          "After those words, give the command that ran as a fenced code block of its own, between "
          "two lines of three backticks" in attended, attended)
    skip_at = unattended.find("If you are not a subagent, skip the rest of this message")
    report_at = unattended.find("If you are a subagent, tell the agent that dispatched you")
    check("in an agent-session no user attends, the condition that skips the report comes before it",
          0 <= skip_at < report_at, unattended)

    # "Skip the rest of this message" skips only the report, so the report must end every message.
    real_build = reader.report_to_user_or_dispatching_agent_instruction_build
    built = []

    def recording_build(words, environment=os.environ):
        built.append(real_build(words, environment))
        return built[-1]
    reader.report_to_user_or_dispatching_agent_instruction_build = recording_build
    try:
        for label, failure in (("the parser is missing", error), ("the reader failed", unreadable)):
            for session in ({}, {"CLAUDE_CODE_SESSION_ATTENDED": "0"}):
                built.clear()
                message = context_of(reader.parser_unavailable_hook_output(
                    "The force-push guard", failure, session))
                check(f"when {label}, with the session variables {session}, the guard's message "
                      f"ends with the report", len(built) == 1 and message.endswith(built[0]),
                      (built, message))
    finally:
        reader.report_to_user_or_dispatching_agent_instruction_build = real_build
    for session, attended_wanted in [((None, None), True), (("1", None), True), (("0", None), False),
                                     ((None, "1"), False)]:
        with reader.agent_session_attendance_environment_variables_temporarily_set_for_test(*session):
            from_session = context_of(reader.parser_unavailable_hook_output("The force-push guard", unreadable))
        check(f"with the session variables {session}, the message reads the session from them",
              ("Tell the user" in from_session) == attended_wanted
              and ("do not tell the user" in from_session) != attended_wanted, from_session)
    with reader.agent_session_attendance_environment_variables_temporarily_set_for_test("outer", None):
        with reader.agent_session_attendance_environment_variables_temporarily_set_for_test(None, "1"):
            inside = (os.environ.get("CLAUDE_CODE_SESSION_ATTENDED"),
                      os.environ.get("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER"))
        after = (os.environ.get("CLAUDE_CODE_SESSION_ATTENDED"),
                 os.environ.get("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER"))
    check("the session variables are set inside the block and put back as they were after it",
          inside == (None, "1") and after == ("outer", None), (inside, after))
    missing_unattended = context_of(reader.parser_unavailable_hook_output(
        "The force-push guard", reader.ShellParserUnavailable("pip: no network"),
        {"CLAUDE_CODE_SESSION_ATTENDED": "0"}))
    check("in an agent-session no user attends, the parser-missing message still has a subagent "
          "report to the agent that dispatched it",
          "If you are a subagent, tell the agent that dispatched you, in these words" in missing_unattended
          and "pip: no network" in missing_unattended and "Tell the user" not in missing_unattended,
          missing_unattended)

    # A failure inside the reader reaches each guard as ShellCommandUnreadable, never as another
    # error that would stop the guard.
    for relative, guard_name in GUARDS:
        guard = load(REPOSITORY_ROOT / relative, "guard_" + Path(relative).stem.replace("-", "_"))

        def failing(*arguments, **keywords):
            raise ValueError("injected")
        guard.shell_reader._collect = failing
        payload = {"tool_name": "Bash", "session_id": f"guard-{relative}", "cwd": scratch,
                   "tool_input": {"command": "tmux kill-server; git push --force o b"}}
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = guard.main(stdin=io.StringIO(json.dumps(payload)))
        try:
            context = context_of(stdout.getvalue())
        except (ValueError, KeyError, AssertionError) as problem:
            context = f"<{problem!r}: {stdout.getvalue()!r}>"
        check(f"when the reader fails inside, {relative} lets the command through and says so",
              code == 0 and context.startswith(guard_name + " let this command through")
              and "reader failed on it" in context and "ValueError: injected" in context,
              (code, context))



# --- what a new process reads is what this process reads, classes and attributes included ---
def same_reading(first, second):
    """Return whether two readings agree in value, class and every attribute."""
    if type(first) is not type(second):
        return False
    if isinstance(first, str):
        return first == second
    if isinstance(first, (list, tuple)):
        if len(first) != len(second) or not all(map(same_reading, first, second)):
            return False
    if hasattr(first, "__dict__"):
        return vars(first).keys() == vars(second).keys() and all(
            same_reading(vars(first)[name], vars(second)[name]) for name in vars(first))
    return first == second if not isinstance(first, (list, tuple)) else True


reader.simple_commands = _simple_commands_as_loaded
check("two readings whose ~ words differ in text are not the same reading",
      not same_reading([reader.ShellWordWithUnexpandedTildePrefixBashWouldExpand("~/a")], [reader.ShellWordWithUnexpandedTildePrefixBashWouldExpand("~/b")])
      and same_reading([reader.ShellWordWithUnexpandedTildePrefixBashWouldExpand("~/a")], [reader.ShellWordWithUnexpandedTildePrefixBashWouldExpand("~/a")]))
# A failure to send what the new process read is the reader failing on the command, not a missing parser.
real_encoder, real_stdin, real_stdout = reader._reader_output_to_json, sys.stdin, sys.stdout
reader._reader_output_to_json = lambda value: (_ for _ in ()).throw(TypeError("cannot send a float"))
sys.stdin = io.TextIOWrapper(io.BytesIO(json.dumps({"command": "ls", "glob_markers": None}).encode()))
sys.stdout = io.TextIOWrapper(io.BytesIO())
# A new process whose reader raises exits 1 with the error on stderr, as Python does.
child_exit, child_error = 0, b""
try:
    reader._read_command_on_standard_input()
    sys.stdout.flush()
    sent = sys.stdout.buffer.getvalue()
except Exception as error:
    sent, child_exit, child_error = b"", 1, f"{type(error).__name__}: {error}".encode()
finally:
    reader._reader_output_to_json, sys.stdin, sys.stdout = real_encoder, real_stdin, real_stdout
try:
    reader._simple_commands_in_a_new_process(
        "ls", None,
        runner=lambda *arguments, **options: subprocess.CompletedProcess(arguments, child_exit, sent,
                                                                         child_error))
    raised = None
except reader.ShellParserUnavailable as error:
    raised = error
check("an encoder failure in the new process reaches the guard as the reader failing, quoting the error",
      isinstance(raised, reader.ShellCommandUnreadable) and "TypeError: cannot send a float" in str(raised),
      (sent, raised))
# A new process that cannot load the parser reaches the guard as a missing parser, not as the reader
# failing on the command, so the guard's message keeps the install advice.
missing_parser_child = (
    "import importlib.util, sys; s = importlib.util.spec_from_file_location('r', sys.argv[1]); "
    "r = importlib.util.module_from_spec(s); s.loader.exec_module(r); "
    "r.parser = lambda: (_ for _ in ()).throw(r.ShellParserUnavailable('pip exited 1: no network')); "
    "r._read_command_on_standard_input()")
try:
    reader._simple_commands_in_a_new_process(
        "ls", None, runner=lambda arguments, **options: subprocess.run(
            [sys.executable, "-c", missing_parser_child, str(MODULE_PATH)], **options))
    raised = None
except reader.ShellParserUnavailable as error:
    raised = error
check("a parser the new process cannot load reaches the guard as a missing parser, with what pip said",
      isinstance(raised, reader.ShellParserUnavailable)
      and not isinstance(raised, reader.ShellCommandUnreadable)
      and raised.install_output == "pip exited 1: no network", raised)
# The case repair shifts offsets by bisect over the starts of one round, which must be ascending: a
# heredoc body holding terminators of two lengths before a word reads that word wrong otherwise.
several_terminators = ("echo ';&'\ncat <<EOF\n`case $v in p0) x=$(case y in y) ls;;& esac);;& p1) cat <<E\n"
                       ";;&\nE\n;;& p2) x=$(case y in y) ls;;& esac);; esac`\nEOF\n")
read_words = [[str(word) for word in command] for command in reader.simple_commands(several_terminators)]
check("a heredoc body with ;;& and ;; terminators before a word reads each word as written",
      read_words == [["echo", ";&"], ["ls"], ["cat"], ["ls"], ["cat"]], read_words)
# A new process that fails outside the reader exits with a traceback; the guard quotes only its last line.
failing_child = "raise RuntimeError('the request could not be read')"
try:
    reader._simple_commands_in_a_new_process(
        "ls", None, runner=lambda arguments, **options: subprocess.run(
            [sys.executable, "-c", failing_child], **options))
    raised = None
except reader.ShellParserUnavailable as error:
    raised = error
check("a new process that fails outside the reader reaches the guard as its exception's line, not a traceback",
      raised is not None and raised.install_output
      == "reading the command in a new process failed: RuntimeError: the request could not be read",
      raised and raised.install_output)
# A new process killed by a signal prints nothing; its exit status is then the agent's only clue.
killed_child = "import os, signal; os.kill(os.getpid(), signal.SIGKILL)"
try:
    reader._simple_commands_in_a_new_process(
        "ls", None, runner=lambda arguments, **options: subprocess.run(
            [sys.executable, "-c", killed_child], **options))
    raised = None
except reader.ShellParserUnavailable as error:
    raised = error
check("a new process killed by a signal, which prints nothing, reaches the guard as its exit status",
      raised is not None
      and raised.install_output == "reading the command in a new process failed: exit -9",
      raised and raised.install_output)
command = reader.simple_commands("cat <<E >~/x\nb\nE")[0]
command.added_attribute = (reader.ShellWordWithUnexpandedTildePrefixBashWouldExpand("~/y"), [1, None])
command.heredocs[0].added_attribute = True
check("a field added to a command or a heredoc crosses between processes with no change to the encoder",
      same_reading(reader._reader_output_from_json(json.loads(json.dumps(
          reader._reader_output_to_json([command])))), [command]), vars(command))
try:
    reader._reader_output_to_json([reader.SimpleCommand([1.5], (), [], [])])
    raised = None
except TypeError as error:
    raised = error
check("a value of a class the encoder does not name raises TypeError, not a silent loss",
      isinstance(raised, TypeError), raised)
for command in ["cd ~/x && git -C ~/y push > ~/z", "env -C ~/w git push -f",
                "cat <<E | bash\n$(tmux send-keys)\nE", "(a | b) <(c) $(d) `e`",
                "echo $'\\xff' $'\\U110000' \ud800x", "cd ~/$'\\xff'",
                "echo $(case x in x) :;& esac) ';;'", "xa 0<(xb) 2>&1 <<<x"]:
    in_this_process = reader.simple_commands(command)
    try:
        in_a_new_process = reader._simple_commands_in_a_new_process(command, None)
    except reader.ShellParserUnavailable as error:
        in_a_new_process = error
    check(f"a new process reads {command!r} as this process does, classes and attributes included",
          same_reading(in_a_new_process, in_this_process), (in_a_new_process, in_this_process))
# Every command this test read, through the same encoder in one child process.
child_code = ("import importlib.util, json, sys; s = importlib.util.spec_from_file_location('r', sys.argv[1]); "
              "r = importlib.util.module_from_spec(s); s.loader.exec_module(r); out = []\n"
              "for command, markers in json.loads(sys.stdin.buffer.read().decode('utf-8', r.SHELL_TEXT_ERRORS)):\n"
              "    try: out.append({'commands': r._reader_output_to_json(r.simple_commands(command, markers))})\n"
              "    except r.ShellCommandUnreadable as error: out.append({'unreadable': error.install_output})\n"
              "sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode('utf-8', r.SHELL_TEXT_ERRORS))")
recorded = list(dict.fromkeys((text, json.dumps(markers)) for text, markers in COMMANDS_READ))
child = subprocess.run([sys.executable, "-c", child_code, str(MODULE_PATH)], capture_output=True,
                       input=json.dumps([[text, json.loads(markers)] for text, markers in recorded],
                                        ensure_ascii=False).encode("utf-8", reader.SHELL_TEXT_ERRORS))
differing = []
if child.returncode == 0:
    for (text, markers), read in zip(recorded, json.loads(child.stdout.decode("utf-8", reader.SHELL_TEXT_ERRORS))):
        try:
            here = reader.simple_commands(text, json.loads(markers))
        except reader.ShellCommandUnreadable as error:
            here = {"unreadable": error.install_output}
        there = (read if "unreadable" in read else reader._reader_output_from_json(read["commands"]))
        if not same_reading(there, here):
            differing.append(text)
check(f"each of the {len(recorded)} commands this test read reads the same in a child process, "
      f"through the encoder, classes and attributes included",
      child.returncode == 0 and len(recorded) > 100 and not differing,
      (child.returncode, child.stderr[-500:], differing[:5]))

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
