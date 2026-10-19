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

  --prefetch-github '<gh arguments>'  run `gh <gh arguments>` in the -C
                          checkout before Codex starts, and give Codex its
                          output as a file; repeatable. Only reading
                          commands are accepted. `pr list`, `pr view`,
                          `issue list` and `issue view` take any of their
                          options, and read the -C checkout's repository
                          unless given -R OWNER/REPO (give -R with
                          --outside-git-checkout). `api` takes exactly one
                          endpoint, which may read any repository, such as
                          repos/OWNER/REPO/pulls/12 with that repository's
                          OWNER/REPO, and only these options:
                          --jq/-q, --template/-t, --header/-H, --preview/-p
                          and --cache, each with its value as the next word
                          or after =, and --include/-i,
                          --paginate and --slurp; `api` has no -R. Any other
                          `api` option is refused, so `api graphql` cannot
                          send a query, since that needs -f, -F or --input. Codex
                          cannot run `gh` itself, because its permission
                          profile denies the folder holding
                          gh's login. The files go in
                          `<report>.github-data/`, and the brief Codex gets
                          ends with a list of them.

--deadline-minutes bounds the whole run: the --prefetch-github commands and
Codex together.

On success it prints `report: <path>` and exits 0. It exits 1, saying what
failed, when a --prefetch-github command fails, or when Codex cannot be
started, exits nonzero, writes no report, or when the run passes its
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
import time

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
# The only `gh api` options --prefetch-github accepts: each only shapes how a GET
# request is sent or printed. Every other option is refused, since a deny-list of
# writing options missed forms gh still parses, such as `-iXDELETE` and `--jq -- -XPOST`.
# --verbose and --hostname are left out: one prints the request's headers, the other
# sends the login to another host.
PREFETCH_API_OPTIONS_TAKING_VALUE = {"--cache", "-H", "--header", "-p", "--preview",
                                     "-q", "--jq", "-t", "--template"}
PREFETCH_API_FLAGS_WITHOUT_VALUE = {"-i", "--include", "--paginate", "--slurp"}
PREFETCH_API_ACCEPTED_OPTIONS_TEXT = (
    "--jq/-q, --template/-t, --header/-H, --preview/-p and --cache, each followed by "
    "its value as the next word or after =, and --include/-i, --paginate and --slurp")
# Keeps a saved file's name well under the 255-byte limit of most file systems.
PREFETCH_FILE_NAME_WORDS_MAX_CHARACTERS = 80


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
                        help="stop the run, the --prefetch-github commands and Codex "
                             f"together, after this many minutes (default {DEFAULT_DEADLINE_MINUTES})")
    parser.add_argument("--run-log", help="file for Codex's output (default <report>.run.log)")
    parser.add_argument("--prefetch-github", action="append", default=[],
                        metavar="GH_ARGUMENTS",
                        help="arguments for one reading gh command run before Codex "
                             "starts, its output given to Codex as a file; repeatable")
    return parser


def prefetch_quoting_error(gh_arguments: str):
    """Return why these gh arguments cannot be split into words, or None when they can."""
    try:
        shlex.split(gh_arguments)
    except ValueError as error:
        return str(error)
    return None


def api_refusal(words):
    """Return why these `gh api` words may do more than read, or None when they only read.

    Accepts exactly one endpoint and the options in PREFETCH_API_OPTIONS_TAKING_VALUE
    and PREFETCH_API_FLAGS_WITHOUT_VALUE. A value-taking option's value is consumed as
    gh consumes it, even when it starts with "-"."""
    endpoints = []
    index = 0
    while index < len(words):
        word = words[index]
        option, has_attached_value = word.split("=", 1)[0], "=" in word
        if not word.startswith("-") or word == "-":
            endpoints.append(word)
        elif option in PREFETCH_API_OPTIONS_TAKING_VALUE:
            if not has_attached_value:
                if index + 1 >= len(words):
                    return f"`gh api` option `{option}` has no value after it"
                index += 1
        elif word in PREFETCH_API_FLAGS_WITHOUT_VALUE:
            pass
        else:
            return f"`gh api` option `{word}` is not accepted"
        index += 1
    if len(endpoints) != 1:
        return (f"`gh api` needs exactly one endpoint, such as repos/OWNER/REPO/pulls/12, "
                f"and got {len(endpoints)}")
    return None


def prefetch_refusal(gh_arguments: str):
    """Return why --prefetch-github must not run these gh arguments, or None when it may.

    The arguments' quoting must already be readable; see prefetch_quoting_error."""
    words = shlex.split(gh_arguments)
    if tuple(words[:2]) in PREFETCH_READING_SUBCOMMANDS:
        return None
    if words[:1] == ["api"]:
        return api_refusal(words[1:])
    return "it is not `pr list`, `pr view`, `issue list`, `issue view` or `api`"


def prefetch_file_name(number: int, words) -> str:
    stem = "-".join(re.sub(r"[^A-Za-z0-9]+", "-", word).strip("-") for word in words[:4])
    return f"{number:02d}-{stem[:PREFETCH_FILE_NAME_WORDS_MAX_CHARACTERS]}.txt"


def prefetch_github_data(commands, data_folder: pathlib.Path, checkout: pathlib.Path,
                         deadline: float, deadline_minutes: float):
    """Run each gh command in the checkout and save its output, all before the monotonic
    time `deadline`; return (files, None) or (None, error)."""
    shutil.rmtree(data_folder, ignore_errors=True)
    data_folder.mkdir(parents=True)
    files = []
    for number, gh_arguments in enumerate(commands, start=1):
        words = shlex.split(gh_arguments)
        target = data_folder / prefetch_file_name(number, words)
        try:
            # In the checkout, so that gh without -R reads that checkout's repository.
            result = subprocess.run(["gh", *words], cwd=checkout, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True,
                                    timeout=max(deadline - time.monotonic(), 0.001))
        except subprocess.TimeoutExpired:
            return None, (f"`gh {gh_arguments}` was still running when the run's "
                          f"{deadline_minutes:g}-minute deadline passed, and was stopped; "
                          f"Codex was not started.\n"
                          f"The deadline covers every --prefetch-github command and Codex "
                          f"together. If the run needs longer, run it again with a larger "
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
            f"You cannot run `gh` yourself: your permission profile keeps you from the "
            f"folder holding gh's login. So the GitHub data below was fetched for you "
            f"before you started, one file per command. Read these files instead:\n"
            f"{listing}\n")


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
        quoting_error = prefetch_quoting_error(gh_arguments)
        if quoting_error:
            parser.error(
                f"could not read the quoting of --prefetch-github '{gh_arguments}': "
                f"{quoting_error}.\n"
                f"Quote it as a shell would, with every quotation mark closed, such as "
                f"--prefetch-github 'pr view 12 --json \"title,body\"'.")
        refusal = prefetch_refusal(gh_arguments)
        if refusal:
            parser.error(
                f"refused --prefetch-github '{gh_arguments}': {refusal}. The gh command runs "
                f"with the login Codex is kept from, so only commands known to read from "
                f"GitHub are accepted.\n"
                f"Use `pr list`, `pr view`, `issue list` or `issue view`, with any of their "
                f"options and -R OWNER/REPO when -C is not a checkout of that repository; "
                f"or `api` with one endpoint, which may read any repository, such as "
                f"repos/OWNER/REPO/pulls/12 with that repository's OWNER/REPO, no -R, and only "
                f"these options: {PREFETCH_API_ACCEPTED_OPTIONS_TEXT}.")
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
    # The credential-file scan that builds Codex's command line counts against no deadline.
    seconds_left = args.deadline_minutes * 60
    if args.prefetch_github:
        prefetch_started = time.monotonic()
        deadline = prefetch_started + seconds_left
        files, error = prefetch_github_data(
            args.prefetch_github, report.with_name(report.name + ".github-data"),
            checkout, deadline, args.deadline_minutes)
        if error:
            return fail(error)
        prompt = brief_with_prefetched_files(prompt, files)
        seconds_left -= time.monotonic() - prefetch_started
        if seconds_left <= 0:
            return fail(f"the --prefetch-github commands used the whole "
                        f"{args.deadline_minutes:g}-minute deadline, so Codex was not started.\n"
                        f"The deadline covers every --prefetch-github command and Codex "
                        f"together. If the run needs longer, run it again with a larger "
                        f"--deadline-minutes.")
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
                exit_code = process.wait(timeout=seconds_left)
            except subprocess.TimeoutExpired:
                stop_process_group(process)
                shared = ("The deadline covers every --prefetch-github command and Codex "
                          "together. " if args.prefetch_github else "")
                return fail(
                    f"Codex was still running when the run's {args.deadline_minutes:g}-minute "
                    f"deadline passed, and was stopped; its output so far is in {run_log}.\n"
                    f"{shared}If the run needs longer, run it again with a larger "
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
