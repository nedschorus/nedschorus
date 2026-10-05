#!/usr/bin/env python3
"""Run one test suite inside the signal sandbox, optionally with a hand mutant applied.

Usage:
  python3 scripts/run-suite-in-signal-sandbox.py <suite> [--mutant PATCH]
                                                [--checkout DIR] [--python PY]
                                                [--lock-file PATH]

  <suite>      the suite's path relative to the checkout's top directory,
               such as scripts/run-all-test-suites-test.py
  --mutant     a patch `git apply` can apply in the checkout; it is applied to
               the files it names, the suite runs, and those files are put back
               byte for byte, whatever happens to the suite
  --checkout   the checkout's top directory; default the current directory
  --python     the interpreter for a Python suite; default this one
  --lock-file  default ~/.claude/.run-all-test-suites.lock, the lock
               scripts/run-all-test-suites.py takes

The suite runs exactly as scripts/run-all-test-suites.py runs it: from the
checkout's top directory, stdin closed, without the variables that redirect
git, inside `bwrap --unshare-pid`, with RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX=1,
while holding the machine's test-run lock. Before the suite starts, a check
inside the sandbox confirms that process 1 there is bwrap; if it is not, the
suite is not run. This program never runs a suite unconfined: without bwrap, on
a platform other than Linux, or for a suite listed in
SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX, it refuses. Started inside a sandbox
already, it runs the suite there, after the same check.

The patch may only change files that already exist; a patch that creates,
deletes or renames a file is refused, because putting the files back is then
more than restoring their bytes.

The last line printed is the verdict:
  VERDICT: suite passed            exit 0
  VERDICT: suite failed (...)      exit 1
  VERDICT: mutant killed (...)     exit 0   the suite failed with the mutant in
  VERDICT: mutant survived         exit 1   the suite passed with the mutant in
  VERDICT: not run (...)           exit 2   nothing was run, or the run could
                                            not be trusted
  VERDICT: not run (lock held)     exit 3   another test run holds the lock
  VERDICT: RESTORE FAILED (...)    exit 4   a mutated file could not be put
                                            back; the message names its copy

Run: python3 scripts/run-suite-in-signal-sandbox.py scripts/a-test.py --mutant /tmp/m.patch
"""

import argparse
import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = "run-suite-in-signal-sandbox"
SCRIPTS_DIR = Path(__file__).resolve().parent
INSIDE_CHECK_OPTION = "--inside-signal-sandbox-check-pid-one-then-exec"
PID_ONE_COMMAND_FILE = Path("/proc/1/comm")
PID_ONE_PROOF = "process 1 is bwrap"
SIGNALS_HELD_DURING_RESTORE = {signal.SIGTERM, signal.SIGHUP, signal.SIGINT}

EXIT_PASSED_OR_KILLED = 0
EXIT_FAILED_OR_SURVIVED = 1
EXIT_NOT_RUN = 2
EXIT_LOCKED = 3
EXIT_RESTORE_FAILED = 4


def load_run_all_test_suites():
    spec = importlib.util.spec_from_file_location(
        "run_all_test_suites", SCRIPTS_DIR / "run-all-test-suites.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_run_all_test_suites()


class NotRun(Exception):
    """Nothing was run; the message says why."""


class RestoreFailed(Exception):
    """A mutated file could not be put back; the message names where its original is kept."""


class Terminated(BaseException):
    """SIGTERM or SIGHUP arrived; raised so the mutated files are still put back."""


def raise_terminated(signal_number, frame):
    raise Terminated(signal.Signals(signal_number).name)


def pid_one_is_bwrap(command_file=PID_ONE_COMMAND_FILE):
    try:
        return command_file.read_text().strip() == "bwrap"
    except OSError:
        return False


def inside_check_then_exec(proof_file, command):
    """Inside the sandbox: write the proof and start the suite, or refuse without starting it."""
    if not pid_one_is_bwrap():
        print(f"{PROGRAM}: the suite was not started — process 1 here is not bwrap, "
              f"so the suite would not be in a PID namespace of its own.", file=sys.stderr)
        return EXIT_NOT_RUN
    if os.environ.get(runner.SIGNAL_SANDBOX_INSIDE_VARIABLE) != "1":
        print(f"{PROGRAM}: the suite was not started — "
              f"{runner.SIGNAL_SANDBOX_INSIDE_VARIABLE} is not 1 here.", file=sys.stderr)
        return EXIT_NOT_RUN
    Path(proof_file).write_text(PID_ONE_PROOF + "\n")
    os.execvp(command[0], command)


def files_the_patch_changes(top, patch):
    """Return the paths the patch modifies, or raise NotRun when it cannot be applied as it is."""
    check = runner.git(top, "apply", "--check", str(patch))
    if check.returncode != 0:
        raise NotRun(f"the mutant does not apply in {top}: {check.stderr.strip()}")
    summary = runner.git(top, "apply", "--summary", str(patch))
    if summary.returncode != 0:
        raise NotRun(f"git apply --summary failed: {summary.stderr.strip()}")
    if summary.stdout.strip():
        raise NotRun(f"the mutant creates, deletes, renames or changes the mode of a file, "
                     f"and only edits to existing files are put back: {summary.stdout.strip()}")
    numstat = runner.git(top, "apply", "--numstat", "-z", str(patch))
    if numstat.returncode != 0:
        raise NotRun(f"git apply --numstat failed: {numstat.stderr.strip()}")
    paths = [record.split("\t", 2)[2] for record in numstat.stdout.split("\0") if record]
    if not paths:
        raise NotRun("the mutant changes no file")
    return paths


def keep_originals(top, paths, keep_dir):
    """Copy each file's bytes into keep_dir and return {path: bytes}."""
    originals = {}
    for relative in paths:
        data = (top / relative).read_bytes()
        kept = keep_dir / relative
        kept.parent.mkdir(parents=True, exist_ok=True)
        kept.write_bytes(data)
        originals[relative] = data
    return originals


def restore_originals(top, originals, keep_dir):
    """Write each original back and read it back; raise RestoreFailed naming any that differ."""
    # A signal arriving half-way through would leave some files mutated.
    blocked = signal.pthread_sigmask(signal.SIG_BLOCK, SIGNALS_HELD_DURING_RESTORE)
    try:
        failed = write_back(top, originals)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, blocked)
    if failed:
        raise RestoreFailed(
            f"{', '.join(failed)}; the original of each is kept under {keep_dir}")


def write_back(top, originals):
    failed = []
    for relative, data in originals.items():
        target = top / relative
        try:
            target.write_bytes(data)
            if target.read_bytes() != data:
                failed.append(f"{relative} (read back differs)")
        except OSError as error:
            failed.append(f"{relative} ({error})")
    return failed


def suite_command(top, suite, interpreter):
    if runner.is_shell_test_suite(suite):
        return ["sh", suite]
    return [interpreter, "-u", suite]


def run_suite_confined(top, suite, interpreter, sandbox_prefix, proof_file, bytecode_dir=None):
    """Run the suite inside the sandbox; return its exit code, or raise NotRun if unproven.

    With bytecode_dir, Python reads and writes bytecode only there. The restored
    file has the mutant's size, and a write within the same second gives it the
    same mtime, so bytecode cached beside it would pass Python's staleness check
    and run the mutant after the restore, or the original during the mutant run.
    """
    command = [*sandbox_prefix, sys.executable, str(Path(__file__).resolve()),
               INSIDE_CHECK_OPTION, str(proof_file), "--",
               *suite_command(top, suite, interpreter)]
    environment = runner.environment_without_git_redirecting_variables()
    if bytecode_dir is not None:
        environment["PYTHONPYCACHEPREFIX"] = str(bytecode_dir)
    completed = subprocess.run(command, cwd=str(top), env=environment,
                               stdin=subprocess.DEVNULL, check=False)
    if proof_file.read_text().strip() != PID_ONE_PROOF:
        raise NotRun(f"the check inside the sandbox did not confirm process 1 is bwrap "
                     f"(exit {completed.returncode}), so the suite was not started")
    exit_code = completed.returncode
    if sandbox_prefix and 128 < exit_code <= 128 + runner.SIGNAL_NUMBER_LIMIT:
        exit_code = -(exit_code - 128)
    return exit_code


def verdict(code, mutant):
    """Return (line, exit code) for the suite's exit code."""
    described = runner.describe_exit(code)
    if mutant:
        if code == 0:
            return "VERDICT: mutant survived — the suite passed with the mutant in", \
                EXIT_FAILED_OR_SURVIVED
        return f"VERDICT: mutant killed — the suite failed: {described}", EXIT_PASSED_OR_KILLED
    if code == 0:
        return "VERDICT: suite passed", EXIT_PASSED_OR_KILLED
    return f"VERDICT: suite failed — {described}", EXIT_FAILED_OR_SURVIVED


def parse_arguments(argv):
    parser = argparse.ArgumentParser(prog=PROGRAM, description=__doc__.splitlines()[0])
    parser.add_argument("suite")
    parser.add_argument("--mutant")
    parser.add_argument("--checkout", default=".")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--lock-file", default=str(runner.DEFAULT_LOCK_FILE))
    return parser.parse_args(argv)


def run(arguments, platform):
    """Return (verdict line, exit code). Raises NotRun or RestoreFailed."""
    if not platform.startswith("linux"):
        raise NotRun(f"{platform} has no signal sandbox yet; this program runs only on Linux")
    try:
        top = runner.checkout_top_directory(arguments.checkout)
        interpreter, _ = runner.interpreter_and_version(arguments.python)
    except runner.CouldNotRun as error:
        raise NotRun(str(error).split("\n")[0]) from error
    suite = arguments.suite
    if not (top / suite).is_file():
        raise NotRun(f"{suite} is not a file in {top}; pass the suite's path relative to "
                     f"the checkout's top directory")
    if suite in runner.SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX:
        raise NotRun(f"{suite} cannot run inside the signal sandbox: "
                     f"{runner.SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX[suite]}")
    patch = Path(arguments.mutant).resolve() if arguments.mutant else None
    if patch is not None and not patch.is_file():
        raise NotRun(f"the mutant {arguments.mutant} is not a file")
    try:
        sandbox_prefix, unconfined_because = runner.signal_sandbox(platform=platform)
    except runner.SignalSandboxCouldNotStart as error:
        raise NotRun(f"bwrap could not start: {error}") from error
    if unconfined_because:
        raise NotRun(f"no signal sandbox: {unconfined_because}")

    lock_handle, holder, _ = runner.take_machine_lock(Path(arguments.lock_file), top)
    if lock_handle is None:
        return (f"VERDICT: not run (lock held) — {arguments.lock_file} is held by {holder}; "
                f"run again when that run has finished"), EXIT_LOCKED
    try:
        with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-") as work_name:
            work = Path(work_name)
            proof_file = work / "pid-one-proof"
            proof_file.write_text("")
            if patch is None:
                code = run_suite_confined(top, suite, interpreter, sandbox_prefix, proof_file)
                return verdict(code, mutant=False)
            paths = files_the_patch_changes(top, patch)
            keep_dir = Path(tempfile.mkdtemp(prefix=f"{PROGRAM}-originals-"))
            originals = keep_originals(top, paths, keep_dir)
            try:
                applied = runner.git(top, "apply", str(patch))
                if applied.returncode != 0:
                    raise NotRun(f"git apply failed: {applied.stderr.strip()}")
                print(f"{PROGRAM}: mutant applied to {', '.join(paths)}; originals kept "
                      f"under {keep_dir}", flush=True)
                code = run_suite_confined(top, suite, interpreter, sandbox_prefix, proof_file,
                                          bytecode_dir=work / "bytecode")
            finally:
                restore_originals(top, originals, keep_dir)
            print(f"{PROGRAM}: restored {', '.join(paths)} byte for byte", flush=True)
            shutil.rmtree(keep_dir)
            return verdict(code, mutant=True)
    finally:
        lock_handle.close()


def main(argv=None, platform=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == [INSIDE_CHECK_OPTION]:
        return inside_check_then_exec(argv[1], argv[3:])
    arguments = parse_arguments(argv)
    signal.signal(signal.SIGTERM, raise_terminated)
    signal.signal(signal.SIGHUP, raise_terminated)
    try:
        line, code = run(arguments, sys.platform if platform is None else platform)
    except NotRun as error:
        line, code = f"VERDICT: not run — {error}", EXIT_NOT_RUN
    except RestoreFailed as error:
        line, code = f"VERDICT: RESTORE FAILED — {error}", EXIT_RESTORE_FAILED
    except (Terminated, KeyboardInterrupt) as interruption:
        line = (f"VERDICT: not run — interrupted ({type(interruption).__name__} "
                f"{interruption}); any mutated file was put back")
        code = EXIT_NOT_RUN
    print(line, flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
