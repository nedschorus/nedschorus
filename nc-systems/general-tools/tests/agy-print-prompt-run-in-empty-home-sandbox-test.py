#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/agy-print-prompt-run-in-empty-home-sandbox.py.

Run: python3 nc-systems/general-tools/tests/agy-print-prompt-run-in-empty-home-sandbox-test.py

No case runs the real agy. A scratch home holds .gemini beside other entries,
and a stub agy stands in for the real one.

  - `ls -A $HOME` run inside the sandbox prefix the program builds shows
    .gemini and nothing else.
  - Inside that prefix /usr and /etc are mounted read-only, and so is
    /run/systemd/resolve when this machine has it.
  - With bwrap missing from PATH the program refuses, exit 1, naming bwrap,
    with that one line and nothing else on stderr.
  - With agy missing from PATH the program refuses, exit 1, naming agy,
    with that one line and nothing else on stderr.
  - A stub agy that fails exits the program with the stub's code, its stderr
    passed through and a line naming the failure; a stub that succeeds has
    its stdout passed through and its arguments as the program built them;
    it runs as the sandbox's agy with only .gemini in its home, in the empty
    /tmp/agy-working-directory, with no agy on PATH and the caller's stdin not
    reaching it, and a GEMINI_API_KEY the caller set does not reach it, while
    other variables do.
  - Without --model the program refuses, exit 2.
  - The Gemini launcher path the macOS branch loads names an existing file.

The real bwrap cannot start inside the nc-test-sandbox. So the checks only
it makes true, the home holding nothing but .gemini, the read-only mounts and
the empty working directory, run only with --real-sandbox-cases-only, which
nc-systems/general-tools/tests/agy-print-prompt-run-in-empty-home-sandbox-real-sandbox-test.py
passes; that suite needs bwrap on PATH and fails without it. Every other case
runs with the cold-read fixture's pass-through stand-in for bwrap, which logs
the prefix the program built so a case can compare it with the program's own.

Linux only: elsewhere every case is skipped, with a line saying why. Prints
one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

SCRIPT_PATH = (pathlib.Path(__file__).resolve().parent.parent
               / "agy-print-prompt-run-in-empty-home-sandbox.py")
_spec = importlib.util.spec_from_file_location("agy_print_prompt_run", SCRIPT_PATH)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)
# The cold-read fixture holds the pass-through stand-in for bwrap that the other
# suites whose programs start bwrap use too.
_fixture_spec = importlib.util.spec_from_file_location(
    "cold_read_scratch_repository_test_fixture",
    pathlib.Path(__file__).resolve().parents[2] / "cold-read" / "tests"
    / "cold-read-scratch-repository-test-fixture.py")
fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(fixture)

failures = []


def check(case_name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail}")


def scratch_home(root: pathlib.Path) -> pathlib.Path:
    home = root / "home"
    for directory in (".gemini", ".ssh", ".config/nedschorus", ".local/bin"):
        (home / directory).mkdir(parents=True)
    (home / ".bashrc").write_text("export SECRET=1\n")
    (home / ".config/nedschorus/gemini-api.key").write_text("key\n")
    return home


def stub_agy(bin_directory: pathlib.Path, body: str) -> None:
    bin_directory.mkdir(parents=True, exist_ok=True)
    stub = bin_directory / "agy"
    stub.write_text("#!/bin/sh\n" + body)
    stub.chmod(0o755)


def read_only_mount_points(mountinfo: str) -> set:
    """Return the mount points that /proc/self/mountinfo lists with the ro option."""
    read_only = set()
    for line in mountinfo.splitlines():
        fields = line.split()
        if len(fields) > 5 and "ro" in fields[5].split(","):
            read_only.add(fields[4])
    return read_only


def run_program(home, path, *arguments, extra_environment=None):
    environment = {**os.environ, "HOME": str(home), "PATH": path,
                   "GEMINI_API_KEY": "caller-key", "AAA_CALLER_VARIABLE": "kept-a",
                   "ZZZ_CALLER_VARIABLE": "kept-z", **(extra_environment or {})}
    return subprocess.run([sys.executable, str(SCRIPT_PATH), *arguments],
                          input="caller-stdin", capture_output=True, text=True,
                          env=environment)


# What the echoing stub agy prints, field by field: its arguments, then what it
# sees of its key, the caller's variables, its own path, its home, its working
# directory, PATH and stdin.
ECHOING_AGY_BODY = ('printf "%s|" "$@" "key=${GEMINI_API_KEY-unset}" '
                    '"${AAA_CALLER_VARIABLE-unset}" "${ZZZ_CALLER_VARIABLE-unset}" "$0" '
                    '"$(ls -A "$HOME" | tr "\\n" " ")" "cwd=$(pwd)" '
                    '"cwd-entries=$(ls -A)" "agy-on-path=$(command -v agy || echo none)" '
                    '"stdin=$(cat)"\n')
ECHOED_FIELDS = ["--model", "gemini-x", "--output-format", "text", "--print", "say hi",
                 "key=unset", "kept-a", "kept-z", program.AGY_PATH_INSIDE_SANDBOX,
                 ".gemini ", "cwd=/tmp/agy-working-directory", "cwd-entries=",
                 "agy-on-path=none", "stdin=", ""]
# The fields only the real bwrap makes true: agy's own path is the bind's
# destination, the home holds only .gemini, and the working directory is empty.
# The stand-in starts the bind's source instead, so a case using it checks the
# path the program asked for in the stand-in's log.
FIELDS_ONLY_THE_REAL_SANDBOX_MAKES_TRUE = (9, 10, 12)

# With this flag only the cases that need the real bwrap run;
# nc-systems/general-tools/tests/agy-print-prompt-run-in-empty-home-sandbox-real-sandbox-test.py
# runs this suite so, and is listed in scripts/run-all-test-suites.py's
# SUITES_RUN_WITHOUT_ANY_SANDBOX. Without it the other cases run with the cold-read
# fixture's pass-through stand-in for bwrap, so this suite runs inside the nc-test-sandbox.
REAL_SANDBOX_CASES_ONLY_FLAG = "--real-sandbox-cases-only"


def real_sandbox_cases(root, home):
    bwrap_directory = str(pathlib.Path(shutil.which("bwrap")).parent)
    stub_agy(home / ".local/bin", "exit 0\n")
    listing = subprocess.run(
        [*program.empty_home_sandbox_prefix(home, str(home / ".local/bin/agy")),
         "ls", "-A", str(home)], capture_output=True, text=True)
    check("the sandbox shows .gemini and no other home entry",
          listing.returncode == 0 and listing.stdout.split() == [".gemini"],
          repr((listing.returncode, listing.stdout, listing.stderr)))
    mounts = subprocess.run(
        [*program.empty_home_sandbox_prefix(home, str(home / ".local/bin/agy")),
         "cat", "/proc/self/mountinfo"], capture_output=True, text=True)
    read_only = read_only_mount_points(mounts.stdout)
    check("the sandbox mounts /usr and /etc read-only",
          mounts.returncode == 0 and {"/usr", "/etc"} <= read_only,
          repr((mounts.returncode, sorted(read_only), mounts.stderr)))
    if pathlib.Path("/run/systemd/resolve").is_dir():
        check("the sandbox mounts /run/systemd/resolve read-only, as this machine has it",
              "/run/systemd/resolve" in read_only, repr(sorted(read_only)))
    else:
        print("SKIP  the /run/systemd/resolve bind: this machine has no /run/systemd/resolve.")
    echoing = root / "echoing-agy"
    stub_agy(echoing, ECHOING_AGY_BODY)
    result = run_program(home, f"{echoing}:{bwrap_directory}", "--model", "gemini-x", "say hi")
    check("agy succeeding under the real bwrap: run as the sandbox's agy with only "
          ".gemini in its home, in an empty working directory, with agy off PATH, "
          "stdin closed and no GEMINI_API_KEY, exit 0",
          result.returncode == 0 and result.stdout.split("|") == ECHOED_FIELDS
          and result.stderr == "",
          repr((result.returncode, result.stdout, result.stderr)))


def cases_with_the_stand_in_sandbox(root, home):
    fake_directory = str(fixture.install_fake_sandbox_programs(root / "fake-sandbox-programs"))
    no_bwrap = root / "path-without-bwrap"
    stub_agy(no_bwrap, "exit 0\n")
    result = run_program(home, str(no_bwrap), "--model", "m", "prompt")
    check("bwrap missing from PATH: refused, exit 1, naming bwrap",
          result.returncode == 1 and result.stderr == f"{program.PROGRAM}: refused: "
          "bwrap is not on PATH, so agy was not run.\n",
          repr((result.returncode, result.stderr)))

    result = run_program(home, fake_directory, "--model", "m", "prompt")
    check("agy missing from PATH: refused, exit 1, naming agy",
          result.returncode == 1 and result.stderr == f"{program.PROGRAM}: refused: "
          "agy is not on PATH, so agy was not run.\n",
          repr((result.returncode, result.stderr)))

    failing = root / "failing-agy"
    stub_agy(failing, "echo agy-stub-failure-text >&2\nexit 7\n")
    result = run_program(home, f"{failing}:{fake_directory}", "--model", "m", "prompt")
    check("agy failing: exit code passed through, its stderr kept, failure named",
          result.returncode == 7 and "agy-stub-failure-text" in result.stderr
          and "failed with exit code 7" in result.stderr,
          repr((result.returncode, result.stderr)))

    echoing = root / "echoing-agy"
    stub_agy(echoing, ECHOING_AGY_BODY)
    argv_log = root / "fake-sandbox-argv.jsonl"
    result = run_program(home, f"{echoing}:{fake_directory}", "--model", "gemini-x", "say hi",
                         extra_environment={"FAKE_SANDBOX_PROGRAM_ARGV_LOG": str(argv_log)})
    fields = result.stdout.split("|")
    check("agy succeeding: stdout passed through, arguments as built, no "
          "GEMINI_API_KEY but every other variable, in "
          "/tmp/agy-working-directory, with agy off PATH and stdin closed, exit 0",
          result.returncode == 0 and len(fields) == len(ECHOED_FIELDS)
          and all(field == expected for index, (field, expected)
                  in enumerate(zip(fields, ECHOED_FIELDS))
                  if index not in FIELDS_ONLY_THE_REAL_SANDBOX_MAKES_TRUE)
          and result.stderr == "",
          repr((result.returncode, result.stdout, result.stderr)))
    launches = ([json.loads(line) for line in argv_log.read_text().splitlines()]
                if argv_log.is_file() else [])
    expected_prefix = program.empty_home_sandbox_prefix(home, str(echoing / "agy"))
    check("the program starts bwrap with the empty-home prefix, then the sandbox's agy",
          len(launches) == 1 and launches[0][1:len(expected_prefix)] == expected_prefix[1:]
          and launches[0][0] == "bwrap"
          and launches[0][len(expected_prefix)] == program.AGY_PATH_INSIDE_SANDBOX,
          repr(launches))

    result = run_program(home, f"{echoing}:{fake_directory}", "say hi")
    check("--model missing: refused by argument parsing, exit 2, agy not run",
          result.returncode == 2 and "--model" in result.stderr and result.stdout == "",
          repr((result.returncode, result.stdout, result.stderr)))


def main() -> int:
    if not sys.platform.startswith("linux"):
        print("SKIP  every case: the empty-home sandbox is bwrap on Linux, and this "
              "machine is not Linux.")
        return 0
    real_sandbox_cases_only = REAL_SANDBOX_CASES_ONLY_FLAG in sys.argv[1:]
    if real_sandbox_cases_only and shutil.which("bwrap") is None:
        print("FAIL  the real-sandbox cases need bwrap on PATH, and this machine has none")
        return 1
    with tempfile.TemporaryDirectory() as temporary:
        root = pathlib.Path(temporary)
        home = scratch_home(root)
        if real_sandbox_cases_only:
            real_sandbox_cases(root, home)
        else:
            cases_with_the_stand_in_sandbox(root, home)

    if not real_sandbox_cases_only:
        check("the macOS branch's Gemini launcher path names the launcher file",
              program.GEMINI_LAUNCHER_PATH.is_file()
              and program.GEMINI_LAUNCHER_PATH.name == "cold-read-agy-cell.py",
              str(program.GEMINI_LAUNCHER_PATH))
    print(f"\n{len(failures)} failure(s)" if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
