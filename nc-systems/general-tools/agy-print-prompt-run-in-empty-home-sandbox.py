#!/usr/bin/env python3
"""Run one `agy --print` prompt inside a sandbox, and print agy's answer.

Usage:
  nc-systems/general-tools/agy-print-prompt-run-in-empty-home-sandbox.py --model MODEL PROMPT

MODEL is a model name agy accepts, such as gemini-3.8-flash-medium.

Runs `agy --model MODEL --output-format text --print PROMPT` with stdin closed,
without --dangerously-skip-permissions, and passes agy's stdout, stderr and
exit code through. bwrap or sandbox-exec, the sandbox program, runs agy and
passes agy's exit code on; whenever the code that reaches this program is
nonzero, whether agy or the sandbox program set it, this program adds one line
of its own to stderr, after agy's or the sandbox program's own messages. GEMINI_API_KEY is removed from agy's environment, because a
key is billed per call and agy's own Google login, in ~/.gemini, is not.

The program's name describes the Linux sandbox; on macOS the home is not
emptied, as the macOS paragraph below says.

On Linux the sandbox is `bwrap`: the home directory holds only ~/.gemini,
where agy keeps its login, bound read-write; /usr and
/etc are read-only; the network is shared; the working directory is a fresh
empty directory in a tmpfs /tmp. The agy binary is bound read-only at
/run/agy-bin/agy, outside the home and off PATH, so a plain `agy` command
inside the sandbox, such as one a model's tool call types, finds nothing.
That does not block a nested agy: the agy running in the sandbox, or a tool
call it makes, could still start a second agy by that full path, so Linux,
like macOS, leaves a nested agy possible.

/run is an empty tmpfs, so /run/systemd/resolve is bound
in when it exists: on ned-box /etc/resolv.conf is a link to
/run/systemd/resolve/stub-resolv.conf, and without the bind agy could not
look up any host name. On a Linux machine whose /etc/resolv.conf links into
/run/systemd/resolve while the host has no /run/systemd/resolve directory,
nothing is bound in, and agy fails with its own network error.

On macOS the sandbox is `sandbox-exec`, started by the command prefix that
`credential_sandbox_prefix()` returns in nc-systems/cold-read/cold-read-agy-cell.py,
the program that runs agy for cold reads. The sandbox-exec profile, built by
`sandbox_exec_profile()` in the same file, denies reading and writing only the
credential paths, which that function assembles from the lists in
nc-systems/cold-read/cold-read-cell-common.py: ~/.config/nedschorus,
~/.config/gh and ~/.ssh, Claude's and Codex's login files, and files named
*.token or .env. The
rest of the home stays readable and writable, and agy stays on PATH, so a plain `agy`
command starts another agy. On macOS this program blocks neither that home access nor that
nested agy; there it
is only as
tight as the cold reads' own agy runs. On macOS the working directory is a fresh empty
temporary directory, removed afterwards.

Exit codes: 2, from argument parsing, on any argument error, such as a
missing --model or PROMPT or an unknown option;
1, with a line on stderr, when agy or the sandbox program is not
on PATH, so nothing was run. Otherwise this program exits with the code
bwrap or sandbox-exec exited with, which is agy's own code when agy ran,
and bwrap's or sandbox-exec's own code when that program failed before agy
started: 1 for bwrap's own errors, such as a bind it cannot make, and for
sandbox-exec a code of its own choosing, which neither this program nor
its caller can tell from a code of agy's. So a nonzero code can come from this program, the sandbox
program or agy, and the same code from more than one of them: a 1 can mean
a program missing from PATH, a sandbox that could not start, or a failure
inside agy, and a 2 can come from agy as well as from argument parsing.
Only stderr tells them apart. Nothing is retried.
"""

import argparse
import contextlib
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
        "--bind", str(home / ".gemini"), str(home / ".gemini"),
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
    working_directory_context = (tempfile.TemporaryDirectory(prefix="agy-working-directory-")
                                 if sys.platform == "darwin" else contextlib.nullcontext())
    with working_directory_context as working_directory:
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
