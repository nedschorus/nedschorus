#!/usr/bin/env python3
"""Every program in the repository that a person or an agent runs offers --help.

The test finds the programs itself, so a program added later is checked the
moment it is committed:

  - every tracked `*.py` file holding an `if __name__ == "__main__":` guard;
  - every tracked file whose first line is a `#!` naming sh, bash or zsh.

It leaves out the files no person or agent runs by hand, by kind:

  - test suites, `*-test.py` and `*-test.sh`, which run-all-test-suites.py runs;
  - Claude Code hooks, `*-hook.py` and everything under `.claude/hooks/`,
    which Claude Code runs with a JSON payload on stdin;
  - git hooks, everything under `scripts/git-client-side-hooks/`, which git runs;

and the single files in EXEMPT_PROGRAMS, each with its reason. An exempt
entry that names no program the search finds fails the test, so the list
cannot keep a path that is gone.

Each program runs as `<interpreter> <path> --help`, from an empty temporary
directory with stdin closed, and passes when it exits 0 within
HELP_TIMEOUT_SECONDS and prints a line starting with "usage" on stdout. A
program that ignores --help would otherwise pass by doing its real work, so
the run is confined: HOME is a scratch directory, and the commands in
STUBBED_COMMANDS come first on PATH as stubs that record the call and exit
nonzero; a program that starts one of them fails. The network stays reachable
for anything that does not go through those commands. A Python program runs
under the interpreter running this test; a shell program under the
interpreter its `#!` line names, so a file without the executable bit is
still checked.

Run: python3 scripts/every-repository-program-help-option-test.py
Prints one line per case and exits 1 if any case fails.
"""

import concurrent.futures
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HELP_TIMEOUT_SECONDS = 20
MAIN_GUARD_PATTERN = re.compile(r"""^if __name__ == ["']__main__["']\s*:""", re.MULTILINE)
SHELL_INTERPRETER_NAMES = ("sh", "bash", "zsh")
USAGE_LINE_PATTERN = re.compile(r"^\s*usage\b", re.IGNORECASE | re.MULTILINE)
# The commands through which a program reaches models, other machines, GitHub, git state or the Mac's desktop.
STUBBED_COMMANDS = ("claude", "codex", "agy", "gemini", "ssh", "scp", "rsync", "gh", "git",
                    "osascript", "open", "tmux", "launchctl", "crontab")
STUB_CALLS_FILE_NAME = "stubbed-command-calls.log"

EXCLUDED_KINDS = (
    ("a test suite, run by run-all-test-suites.py",
     lambda path: path.endswith(("-test.py", "-test.sh"))),
    ("a Claude Code hook, run by Claude Code with a JSON payload on stdin",
     lambda path: path.endswith("-hook.py") or path.startswith(".claude/hooks/")),
    ("a git hook, run by git",
     lambda path: path.startswith("scripts/git-client-side-hooks/")),
)

EXEMPT_PROGRAMS = {
    "scripts/git-client-side-hooks-pre-push-conflict-check.py":
        "run only by the git pre-push hook scripts/git-client-side-hooks/pre-push, "
        "which hands it git's arguments and the refs being pushed on stdin",
    "scripts/git-client-side-hooks-pre-push-mutation-testing-worktree-push-refusal.py":
        "run only by the git pre-push hook scripts/git-client-side-hooks/pre-push, "
        "which hands it git's arguments and the refs being pushed on stdin",
    "scripts/git-client-side-hooks-pre-push-open-pull-request-branch-non-fast-forward-or-deletion-refusal.py":
        "run only by the git pre-push hook scripts/git-client-side-hooks/pre-push, "
        "which hands it git's arguments and the refs being pushed on stdin",
    "scripts/git-client-side-hooks-pre-push-selective-test-run.py":
        "run only by the git pre-push hook scripts/git-client-side-hooks/pre-push, with no "
        "arguments and nothing on stdin; it ignores its arguments, so --help would start a "
        "selective test run",
}

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}" + (f": {detail}" if detail else ""))
        failures.append(case_name)


def tracked_files():
    listing = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT,
                             capture_output=True, check=True)
    return [name for name in listing.stdout.decode().split("\0") if name]


def interpreter_for(path):
    """The command that runs `path`, or None when the file is not a program."""
    full_path = REPO_ROOT / path
    if not full_path.is_file():
        return None
    # Bytes that are not UTF-8, as in an image, cannot make a file a program, so they are replaced, not refused.
    text = full_path.read_bytes().decode("utf-8", errors="replace")
    if path.endswith(".py"):
        return [sys.executable] if MAIN_GUARD_PATTERN.search(text) else None
    first_line = text.split("\n", 1)[0]
    if not first_line.startswith("#!"):
        return None
    words = first_line[2:].split()
    if words and Path(words[0]).name == "env":
        words = words[1:]
    if words and Path(words[0]).name in SHELL_INTERPRETER_NAMES:
        return words
    return None


def all_programs():
    """Map each tracked program's path to the command that runs it."""
    programs = {}
    for path in tracked_files():
        interpreter = interpreter_for(path)
        if interpreter is not None:
            programs[path] = interpreter
    return programs


def excluded_kind(path):
    for reason, matches in EXCLUDED_KINDS:
        if matches(path):
            return reason
    return None


def confined_environment(scratch):
    """An environment whose HOME is scratch/home and whose PATH starts with stubs of STUBBED_COMMANDS."""
    home = scratch / "home"
    stubs = scratch / "stubs"
    home.mkdir()
    stubs.mkdir()
    calls = scratch / STUB_CALLS_FILE_NAME
    for name in STUBBED_COMMANDS:
        stub = stubs / name
        stub.write_text(f'#!/bin/sh\nprintf "%s\\n" "{name} $*" >> "{calls}"\nexit 97\n')
        stub.chmod(0o755)
    environment = dict(os.environ, HOME=str(home), PATH=f"{stubs}{os.pathsep}{os.environ.get('PATH', '')}")
    return environment, calls


def help_option_problem(interpreter, program_path, timeout_seconds=HELP_TIMEOUT_SECONDS):
    """None when `program_path --help` exits 0 printing a usage line and starts no stubbed command, else what went wrong."""
    with tempfile.TemporaryDirectory(prefix="help-option-test-") as scratch:
        scratch = Path(scratch)
        working_directory = scratch / "empty"
        working_directory.mkdir()
        environment, calls = confined_environment(scratch)
        try:
            result = subprocess.run([*interpreter, str(program_path), "--help"],
                                    cwd=working_directory, env=environment, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            return f"--help did not finish within {timeout_seconds} seconds"
        started = calls.read_text().strip() if calls.exists() else ""
    if started:
        return f"--help started {started.splitlines()[0]!r}, so the program did its work instead of printing help"
    if result.returncode != 0:
        return (f"--help exited {result.returncode}; stderr: "
                f"{result.stderr.strip()[-300:]!r}")
    if not USAGE_LINE_PATTERN.search(result.stdout):
        return ("--help exited 0 but printed no line starting with \"usage\" on stdout; "
                f"stdout began {result.stdout.strip()[:120]!r}")
    return None


def check_the_checker_reports_each_failure():
    """help_option_problem must report each way a program can fail; a checker that
    passes everything would leave the rule unenforced."""
    with tempfile.TemporaryDirectory(prefix="help-option-checker-") as directory:
        directory = Path(directory)
        cases = {
            "refuses --help": "import sys\nprint('unknown option', file=sys.stderr)\nsys.exit(2)\n",
            "prints nothing": "pass\n",
            "prints help only on stderr": "import sys\nprint('usage: x', file=sys.stderr)\n",
            "hangs": "import time\ntime.sleep(30)\n",
            "ignores --help and prints its normal output":
                "print('3 dialogs written, 0 failed')\n",
            "ignores --help and starts claude":
                "import subprocess\nsubprocess.run(['claude', '-p', 'x'])\nprint('usage: ran claude')\n",
        }
        for label, source in cases.items():
            program = directory / (label.replace(" ", "-") + ".py")
            program.write_text(source)
            problem = help_option_problem([sys.executable], program, timeout_seconds=2)
            check(f"the checker reports a program that {label}", problem is not None, problem)
        good = directory / "good.py"
        good.write_text("print('usage: good')\n")
        problem = help_option_problem([sys.executable], good, timeout_seconds=10)
        check("the checker passes a program that prints help and exits 0", problem is None, problem)


def main():
    check_the_checker_reports_each_failure()

    programs = all_programs()
    check("the search finds programs", len(programs) > 0, "no program found")
    for path, reason in EXEMPT_PROGRAMS.items():
        check(f"exempt entry names a program the search finds: {path}",
              path in programs and excluded_kind(path) is None,
              "remove the entry, or fix its path" if path not in programs
              else f"already left out as {excluded_kind(path)}; remove the entry")

    to_run = sorted(path for path in programs
                    if excluded_kind(path) is None and path not in EXEMPT_PROGRAMS)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        problems = dict(zip(to_run, pool.map(
            lambda path: help_option_problem(programs[path], REPO_ROOT / path), to_run)))
    for path in to_run:
        check(f"{path} --help exits 0 and prints its usage", problems[path] is None,
              f"{problems[path]}. Give the program a --help that prints its usage and "
              "exits 0 without side effects, or, if no person or agent runs it by hand, "
              "add it to EXEMPT_PROGRAMS in this test with the reason")

    print()
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print(f"all cases passed ({len(to_run)} programs checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
