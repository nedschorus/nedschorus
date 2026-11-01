#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/agy-print-prompt-run-in-empty-home-sandbox.py.

Run: python3 nc-systems/general-tools/tests/agy-print-prompt-run-in-empty-home-sandbox-test.py

No case runs the real agy. A scratch home holds .gemini beside other entries,
and a stub agy stands in for the real one.

  - `ls -A $HOME` run inside the sandbox prefix the program builds shows
    .gemini and nothing else.
  - With bwrap missing from PATH the program refuses, exit 1, naming bwrap.
  - With agy missing from PATH the program refuses, exit 1, naming agy.
  - A stub agy that fails exits the program with the stub's code, its stderr
    passed through and a line naming the failure; a stub that succeeds has
    its stdout passed through and its arguments as the program built them,
    and a GEMINI_API_KEY the caller set does not reach it.

Linux only, with bwrap on PATH: elsewhere every case is skipped, with a line
saying why. Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
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


def run_program(home, path, *arguments):
    environment = {**os.environ, "HOME": str(home), "PATH": path,
                   "GEMINI_API_KEY": "caller-key"}
    return subprocess.run([sys.executable, str(SCRIPT_PATH), *arguments],
                          capture_output=True, text=True, env=environment)


def main() -> int:
    if not sys.platform.startswith("linux") or shutil.which("bwrap") is None:
        print("SKIP  every case: the empty-home sandbox is bwrap on Linux, and this "
              "machine has no bwrap on PATH or is not Linux.")
        return 0
    bwrap_directory = str(pathlib.Path(shutil.which("bwrap")).parent)
    with tempfile.TemporaryDirectory() as temporary:
        root = pathlib.Path(temporary)
        home = scratch_home(root)
        stub_agy(home / ".local/bin", "exit 0\n")
        listing = subprocess.run(
            [*program.empty_home_sandbox_prefix(home, str(home / ".local/bin/agy")),
             "ls", "-A", str(home)], capture_output=True, text=True)
        check("the sandbox shows .gemini and no other home entry",
              listing.returncode == 0 and listing.stdout.split() == [".gemini"],
              repr((listing.returncode, listing.stdout, listing.stderr)))

        no_bwrap = root / "path-without-bwrap"
        stub_agy(no_bwrap, "exit 0\n")
        result = run_program(home, str(no_bwrap), "--model", "m", "prompt")
        check("bwrap missing from PATH: refused, exit 1, naming bwrap",
              result.returncode == 1 and "bwrap is not on PATH" in result.stderr,
              repr((result.returncode, result.stderr)))

        result = run_program(home, bwrap_directory, "--model", "m", "prompt")
        check("agy missing from PATH: refused, exit 1, naming agy",
              result.returncode == 1 and "agy is not on PATH" in result.stderr,
              repr((result.returncode, result.stderr)))

        failing = root / "failing-agy"
        stub_agy(failing, "echo agy-stub-failure-text >&2\nexit 7\n")
        result = run_program(home, f"{failing}:{bwrap_directory}", "--model", "m", "prompt")
        check("agy failing: exit code passed through, its stderr kept, failure named",
              result.returncode == 7 and "agy-stub-failure-text" in result.stderr
              and "failed with exit code 7" in result.stderr,
              repr((result.returncode, result.stderr)))

        echoing = root / "echoing-agy"
        stub_agy(echoing, 'printf "%s|" "$@" "key=${GEMINI_API_KEY-unset}"\n')
        result = run_program(home, f"{echoing}:{bwrap_directory}",
                             "--model", "gemini-x", "say hi")
        check("agy succeeding: stdout passed through, arguments as built, no "
              "GEMINI_API_KEY, exit 0",
              result.returncode == 0 and result.stdout
              == "--model|gemini-x|--output-format|text|--print|say hi|key=unset|"
              and result.stderr == "",
              repr((result.returncode, result.stdout, result.stderr)))
    print(f"\n{len(failures)} failure(s)" if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
