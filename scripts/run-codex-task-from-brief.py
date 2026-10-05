#!/usr/bin/env python3
"""Run one Codex task from a brief file and wait for its report.

Usage:
  scripts/run-codex-task-from-brief.py -C <checkout> --brief <file> -o <report>
      [--sandbox read-only|workspace-write] [-m <model>] [--effort <effort>]
      [--deadline-minutes <minutes>] [--run-log <file>]

The program an agent uses to hand Codex a task. It always:
  - reads the prompt from the brief file, never from the command line;
  - closes Codex's stdin, because `codex exec` reads stdin even when the
    prompt is an argument and, started from a script or a background shell,
    otherwise waits for input forever;
  - writes Codex's whole output to a run log, by default `<report>.run.log`;
  - stops Codex, and every process Codex started, when the deadline passes;
  - runs Codex under a permission profile that denies credential files,
    extending `:read-only`, or `:workspace` with `--sandbox workspace-write`,
    and with Codex's memory store off.

On success it prints `report: <path>` and exits 0. It exits 1, saying what
failed, when Codex cannot be started, exits nonzero, writes no report, or
passes the deadline. It exits 2 on bad arguments. It needs no terminal, so
it can run as a background task.
"""

import argparse
import importlib.util
import os
import pathlib
import signal
import subprocess
import sys

_common_spec = importlib.util.spec_from_file_location(
    "cold_read_cell_common",
    pathlib.Path(__file__).resolve().parent.parent
    / "nc-systems" / "cold-read" / "cold-read-cell-common.py")
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)

PROGRAM = "run-codex-task-from-brief"
PERMISSION_PROFILE_NAME = "codex-task-no-credentials"
SANDBOX_TO_PROFILE_BASE = {"read-only": ":read-only", "workspace-write": ":workspace"}
DEFAULT_DEADLINE_MINUTES = 60
# Codex gets this long to exit after SIGTERM before its process group is killed.
STOP_GRACE_SECONDS = 10


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts/run-codex-task-from-brief.py",
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-C", dest="checkout", required=True,
                        help="the checkout Codex works in")
    parser.add_argument("--brief", required=True,
                        help="file holding the whole prompt")
    parser.add_argument("-o", dest="report", required=True,
                        help="file Codex writes its final message to")
    parser.add_argument("--sandbox", choices=tuple(SANDBOX_TO_PROFILE_BASE),
                        default="read-only")
    parser.add_argument("-m", dest="model", help="Codex model id")
    parser.add_argument("--effort", help="reasoning effort, such as medium or xhigh")
    parser.add_argument("--deadline-minutes", type=float,
                        default=DEFAULT_DEADLINE_MINUTES,
                        help=f"stop Codex after this long (default {DEFAULT_DEADLINE_MINUTES})")
    parser.add_argument("--run-log", help="file for Codex's output (default <report>.run.log)")
    return parser


def codex_command(checkout: pathlib.Path, report: pathlib.Path, sandbox: str,
                  model, effort, prompt: str) -> list:
    command = [
        "codex", "exec",
        *common.codex_credential_denying_permission_profile_arguments(
            PERMISSION_PROFILE_NAME, SANDBOX_TO_PROFILE_BASE[sandbox]),
        "--disable", "memories",
        "-C", str(checkout),
        "-o", str(report),
    ]
    if model:
        command += ["-m", model]
    if effort:
        command += ["-c", f"model_reasoning_effort={effort}"]
    return command + [prompt]


def stop_process_group(process: subprocess.Popen) -> None:
    for stop_signal, wait_seconds in ((signal.SIGTERM, STOP_GRACE_SECONDS),
                                      (signal.SIGKILL, None)):
        try:
            os.killpg(process.pid, stop_signal)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=wait_seconds)
            return
        except subprocess.TimeoutExpired:
            continue


def fail(message: str) -> int:
    print(f"{PROGRAM}: {message}", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    args = build_argument_parser().parse_args(argv)
    checkout = pathlib.Path(args.checkout).resolve()
    brief = pathlib.Path(args.brief).resolve()
    report = pathlib.Path(args.report).resolve()
    run_log = pathlib.Path(args.run_log).resolve() if args.run_log else report.with_name(
        report.name + ".run.log")
    if not checkout.is_dir():
        return fail(f"the checkout {checkout} is not a directory.")
    try:
        prompt = brief.read_text(encoding="utf-8")
    except OSError as error:
        return fail(f"could not read the brief {brief}: {error}")
    if not prompt.strip():
        return fail(f"the brief {brief} is empty.")
    # A report left by an earlier run must not pass for this run's.
    report.unlink(missing_ok=True)
    command = codex_command(checkout, report, args.sandbox, args.model,
                            args.effort, prompt)
    deadline_seconds = args.deadline_minutes * 60
    print(f"{PROGRAM}: running Codex in {checkout}; log {run_log}", file=sys.stderr)
    try:
        with open(run_log, "w", encoding="utf-8") as log:
            # Its own process group, so the deadline stops every process Codex started.
            process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True)
            try:
                exit_code = process.wait(timeout=deadline_seconds)
            except subprocess.TimeoutExpired:
                stop_process_group(process)
                return fail(
                    f"Codex passed the {args.deadline_minutes:g}-minute deadline and "
                    f"was stopped; its output so far is in {run_log}.\n"
                    f"If the task needs longer, run it again with a larger "
                    f"--deadline-minutes.")
    except OSError as error:
        return fail(f"could not start Codex: {error}")
    if exit_code != 0:
        return fail(f"Codex exited {exit_code}; its output is in {run_log}.")
    if not report.is_file() or not report.read_text(encoding="utf-8").strip():
        return fail(f"Codex exited 0 but wrote no report at {report}; "
                    f"its output is in {run_log}.")
    print(f"report: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
