#!/usr/bin/env python3
"""Run one Codex task from a brief file and wait for its report.

Usage:
  scripts/run-codex-task-from-brief.py -C <checkout> --brief <file> -o <report>
      [--sandbox read-only|workspace-write] [-m <model>] [--effort <effort>]
      [--network] [--writable-root <folder>]... [--outside-git-checkout]
      [--web-search] [--deadline-minutes <minutes>] [--run-log <file>]
      [--prefetch-github '<gh arguments>']...

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

Options that widen what Codex may do, each off by default:
  --network               let Codex's commands reach the network;
  --writable-root <folder>  let Codex write in this folder as well as the
                          checkout, with --sandbox workspace-write; repeatable;
  --outside-git-checkout  let -C name a folder that is not a git checkout;
  --web-search            give Codex its live web search tool.

  --prefetch-github '<gh arguments>'  run `gh <gh arguments>` before Codex
                          starts and give Codex its output as a file;
                          repeatable. Codex cannot run `gh` itself, because
                          its permission profile denies the folder holding
                          gh's login. Only reading commands are accepted:
                          `pr list`, `pr view`, `issue list`, `issue view`,
                          and `api` without a method or field option.
                          The files go in `<report>.github-data/`, and the
                          brief Codex gets ends with a list of them.

On success it prints `report: <path>` and exits 0. It exits 1, saying what
failed, when a --prefetch-github command fails or passes the deadline, or when
Codex cannot be started, exits nonzero, writes no report, or passes the
deadline. It exits 2 on bad arguments. It needs no terminal, so
it can run as a background task.
"""

import argparse
import importlib.util
import os
import pathlib
import re
import shlex
import shutil
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
# The gh commands --prefetch-github runs: each only reads from GitHub.
PREFETCH_READING_SUBCOMMANDS = {("pr", "list"), ("pr", "view"), ("issue", "list"),
                                ("issue", "view")}
# `gh api` sends a request other than GET with these, or with -X/--method.
PREFETCH_API_WRITING_OPTIONS = ("-X", "--method", "-f", "--raw-field", "-F", "--field",
                                "--input")


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
    parser.add_argument("--network", action="store_true",
                        help="let Codex's commands reach the network")
    parser.add_argument("--writable-root", action="append", default=[], metavar="FOLDER",
                        help="a folder Codex may write in besides the checkout; repeatable")
    parser.add_argument("--outside-git-checkout", action="store_true",
                        help="let -C name a folder that is not a git checkout")
    parser.add_argument("--web-search", action="store_true",
                        help="give Codex its live web search tool")
    parser.add_argument("--deadline-minutes", type=float,
                        default=DEFAULT_DEADLINE_MINUTES,
                        help=f"stop Codex after this long (default {DEFAULT_DEADLINE_MINUTES})")
    parser.add_argument("--run-log", help="file for Codex's output (default <report>.run.log)")
    parser.add_argument("--prefetch-github", action="append", default=[],
                        metavar="GH_ARGUMENTS",
                        help="arguments for one reading gh command run before Codex "
                             "starts, its output given to Codex as a file; repeatable")
    return parser


def prefetch_refusal(gh_arguments: str):
    """Return why --prefetch-github must not run these gh arguments, or None when it may."""
    try:
        words = shlex.split(gh_arguments)
    except ValueError as error:
        return f"its quoting cannot be read ({error})"
    if tuple(words[:2]) in PREFETCH_READING_SUBCOMMANDS:
        return None
    if words[:1] == ["api"]:
        for word in words[1:]:
            option = word.split("=", 1)[0]
            # A short option can carry its value attached, as in -XPOST or -fbody=x.
            if option not in PREFETCH_API_WRITING_OPTIONS and re.match(r"-[XfF].", word):
                option = word[:2]
            if option in PREFETCH_API_WRITING_OPTIONS:
                return f"`gh api` with {option} can send a request that changes GitHub"
        return None
    return "it is not `pr list`, `pr view`, `issue list`, `issue view` or `api`"


def prefetch_github_data(commands, data_folder: pathlib.Path, deadline_seconds: float):
    """Run each gh command and save its output; return (files, None) or (None, error)."""
    shutil.rmtree(data_folder, ignore_errors=True)
    data_folder.mkdir(parents=True)
    files = []
    for number, gh_arguments in enumerate(commands, start=1):
        words = shlex.split(gh_arguments)
        target = data_folder / f"{number:02d}-{'-'.join(re.sub(r'[^A-Za-z0-9]+', '-', w).strip('-') for w in words[:4])}.txt"
        try:
            result = subprocess.run(["gh", *words], stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=deadline_seconds)
        except subprocess.TimeoutExpired:
            return None, (f"`gh {gh_arguments}` passed the deadline and was stopped; "
                          f"Codex was not started.\n"
                          f"If the command needs longer, run again with a larger "
                          f"--deadline-minutes.")
        except OSError as error:
            return None, f"could not run `gh {gh_arguments}`: {error}; Codex was not started."
        if result.returncode != 0:
            return None, (f"`gh {gh_arguments}` exited {result.returncode}; Codex was not "
                          f"started. gh said: {result.stderr.strip() or '(nothing)'}")
        target.write_text(result.stdout, encoding="utf-8")
        files.append((target, gh_arguments))
    return files, None


def brief_with_prefetched_files(prompt: str, files) -> str:
    listing = "\n".join(f"- {path}: the output of `gh {arguments}`" for path, arguments in files)
    return (f"{prompt.rstrip()}\n\n"
            f"GitHub data fetched for you before you started, one file per command. "
            f"`gh` cannot run where you are, so read these files instead:\n{listing}\n")


def codex_command(checkout: pathlib.Path, report: pathlib.Path, sandbox: str,
                  model, effort, prompt: str, network: bool = False,
                  writable_roots=(), outside_git_checkout: bool = False,
                  web_search: bool = False) -> list:
    command = [
        "codex", "exec",
        *common.codex_credential_denying_permission_profile_arguments(
            PERMISSION_PROFILE_NAME, SANDBOX_TO_PROFILE_BASE[sandbox], network=network),
        "--disable", "memories",
        "-C", str(checkout),
        "-o", str(report),
    ]
    for root in writable_roots:
        command += ["--add-dir", str(root)]
    if outside_git_checkout:
        command.append("--skip-git-repo-check")
    if web_search:
        # `codex exec` does not accept --search; this config key is what that flag sets.
        command += ["-c", 'web_search="live"']
    if model:
        command += ["-m", model]
    if effort:
        command += ["-c", f"model_reasoning_effort={effort}"]
    # `--` keeps a brief that begins with "-", such as front matter, from being read as an option.
    return command + ["--", prompt]


def stop_process_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=STOP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        pass
    # Codex exiting is not enough: a process it started may outlive SIGTERM in the same group.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def fail(message: str) -> int:
    print(f"{PROGRAM}: {message}", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    for gh_arguments in args.prefetch_github:
        refusal = prefetch_refusal(gh_arguments)
        if refusal:
            parser.error(
                f"refused --prefetch-github '{gh_arguments}': {refusal}. The gh command runs "
                f"with the login Codex is kept from, so it may only read from GitHub.\n"
                f"Use `pr list`, `pr view`, `issue list`, `issue view`, or `api` without "
                f"-X, --method, -f, -F, --field, --raw-field or --input.")
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
    deadline_seconds = args.deadline_minutes * 60
    if args.prefetch_github:
        files, error = prefetch_github_data(
            args.prefetch_github, report.with_name(report.name + ".github-data"),
            deadline_seconds)
        if error:
            return fail(error)
        prompt = brief_with_prefetched_files(prompt, files)
    command = codex_command(
        checkout, report, args.sandbox, args.model, args.effort, prompt,
        network=args.network,
        writable_roots=[pathlib.Path(root).resolve() for root in args.writable_root],
        outside_git_checkout=args.outside_git_checkout, web_search=args.web_search)
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
