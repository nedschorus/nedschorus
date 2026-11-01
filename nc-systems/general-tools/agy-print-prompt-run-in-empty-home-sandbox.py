#!/usr/bin/env python3
"""Run one `agy --print` prompt inside a sandbox, and print agy's answer.

Usage:
  nc-systems/general-tools/agy-print-prompt-run-in-empty-home-sandbox.py --model MODEL PROMPT

Runs `agy --model MODEL --output-format text --print PROMPT` with stdin closed,
without --dangerously-skip-permissions, and passes agy's stdout, stderr and
exit code through. GEMINI_API_KEY is removed from agy's environment, because a
key is billed per call and agy's own Google login, in ~/.gemini, is not.

On Linux the sandbox is `bwrap`: the home directory is an empty tmpfs with
only ~/.gemini, where agy keeps its login, bound back read-write; /usr and
/etc are read-only; the network is shared; the working directory is a fresh
empty directory in a tmpfs /tmp. The agy binary is bound read-only at
/run/agy-bin/agy, outside the home and off PATH, so agy cannot start another
agy. /run/systemd/resolve, which /etc/resolv.conf points into on ned-box, is
bound when it exists; where it does not and DNS needs it, agy fails with its
own network error.

On macOS the sandbox is the Gemini launcher's, `credential_sandbox_prefix()`
in nc-systems/cold-read/cold-read-agy-cell.py, which denies the credential
paths but leaves the rest of the home readable; the working directory is a
fresh empty temporary directory, removed afterwards.

Fails, with a line on stderr and exit 1, when agy is not on PATH or the
sandbox program is not; exits with agy's own code, after a line on stderr,
when agy or bwrap fails. Nothing is retried.
"""

import argparse
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

PROGRAM = "agy-print-prompt-run-in-empty-home-sandbox"
AGY_PATH_INSIDE_SANDBOX = "/run/agy-bin/agy"
GEMINI_LAUNCHER_PATH = (pathlib.Path(__file__).resolve().parents[1]
                        / "cold-read" / "cold-read-agy-cell.py")


def empty_home_sandbox_prefix(home: pathlib.Path, agy_path: str) -> list:
    """Return the bwrap argv prefix; the command after it is run as agy is."""
    return [
        "bwrap",
        "--ro-bind", "/usr", "/usr", "--ro-bind", "/etc", "/etc",
        "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64", "--symlink", "usr/sbin", "/sbin",
        "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp", "--tmpfs", "/run",
        "--ro-bind-try", "/run/systemd/resolve", "/run/systemd/resolve",
        "--tmpfs", str(home), "--bind", str(home / ".gemini"), str(home / ".gemini"),
        "--ro-bind", agy_path, AGY_PATH_INSIDE_SANDBOX,
        "--dir", "/tmp/agy-working-directory", "--chdir", "/tmp/agy-working-directory",
        "--unshare-pid", "--unshare-ipc", "--unshare-uts", "--die-with-parent",
        "--setenv", "HOME", str(home), "--setenv", "PATH", "/usr/bin:/bin",
    ]


def launcher_credential_sandbox_prefix() -> list:
    """Return the Gemini launcher's macOS sandbox-exec prefix."""
    spec = importlib.util.spec_from_file_location("cold_read_agy_cell", GEMINI_LAUNCHER_PATH)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    return launcher.credential_sandbox_prefix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True, help="agy model id, e.g. gemini-3.8-flash-medium")
    parser.add_argument("prompt")
    arguments = parser.parse_args()
    agy_arguments = ["--model", arguments.model, "--output-format", "text",
                     "--print", arguments.prompt]
    sandbox_program = "sandbox-exec" if sys.platform == "darwin" else "bwrap"
    agy_path = shutil.which("agy")
    for needed, found in (("agy", agy_path), (sandbox_program, shutil.which(sandbox_program))):
        if found is None:
            print(f"{PROGRAM}: refused: {needed} is not on PATH, so agy was not run.",
                  file=sys.stderr)
            return 1
    with tempfile.TemporaryDirectory(prefix="agy-working-directory-") as working_directory:
        if sys.platform == "darwin":
            command = [*launcher_credential_sandbox_prefix(), agy_path, *agy_arguments]
        else:
            command = [*empty_home_sandbox_prefix(pathlib.Path.home(), agy_path),
                       AGY_PATH_INSIDE_SANDBOX, *agy_arguments]
        environment = {name: value for name, value in os.environ.items()
                       if name != "GEMINI_API_KEY"}
        exit_code = subprocess.run(command, stdin=subprocess.DEVNULL, cwd=working_directory,
                                   env=environment).returncode
    if exit_code != 0:
        print(f"{PROGRAM}: the sandboxed agy run failed with exit code {exit_code}; "
              f"{sandbox_program}'s or agy's own message is above.", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
