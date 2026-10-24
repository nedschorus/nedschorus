#!/usr/bin/env python3
"""Run a Gemini task from a UTF-8 brief file inside agy's credential sandbox.

Usage: run-gemini-task-from-brief.py -C CHECKOUT --brief FILE -o REPORT
       [--sandbox read-only|workspace-write] [-m MODEL] [--effort EFFORT]
       [--writable-root FOLDER]... [--network] [--deadline-minutes N]
       [--run-log FILE]

Reads use the cold-read agy sandbox: the filesystem, including log-store
paths, is readable except for credential paths. No --readable-root is
needed. As in that sandbox, agy's own login remains readable; Linux masks
credential files present at launch under home and the launcher's checkout,
not files created later or found elsewhere.

read-only lets agy write REPORT and nothing else, not even its own state
under ~/.gemini, so agy logs failed cache writes. workspace-write also lets
it write CHECKOUT and each --writable-root folder. The report file is bound
individually on Linux, so replacing it by rename is not supported. Existing
report content is removed before the task starts. Files in writable folders
may be overwritten by the task and are not rolled back on failure.

--network enables network access for the whole agy process, including its
model connection; without it even Gemini's API is unreachable. No proxy
separates model traffic from tool traffic. This launcher does not provision
logins, recover reports from chat, retry models, or verify report content.

Without GEMINI_API_KEY in the environment, the launcher reads the key from
~/.config/nedschorus/gemini-api.key before starting agy, since the sandbox
hides that file. A file that gives no key does not stop the launch: agy
needs the key only when ~/.gemini/antigravity-cli/settings.json sets
modelProvider to "gemini", and otherwise uses its own Antigravity login.
When agy then exits nonzero, the error the launcher prints on stderr also
says why the file gave no key.

Runs `agy models` inside the same sandbox before starting the task, refusing
unknown names with the known names. The default is gemini-4-argon-high.
Closes stdin and logs both output streams to REPORT.run.log, or to
--run-log; an existing log at that path is overwritten. The
deadline covers model discovery and task execution after sandbox setup;
the Codex launcher's process-group cleanup stops agy and its children.

Exits 0 with `report: PATH` for a nonblank report, 2 for invalid arguments,
and 1 with a diagnostic for file errors, unavailable sandbox, agy startup
or model-list failures, unknown models, timeout, nonzero exit or no report.
Requires bwrap on Linux or sandbox-exec on macOS; never runs unsandboxed.
"""

import argparse
import importlib.util
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = pathlib.Path(__file__).resolve().parent.parent
agy_cell = _load("cold_read_agy_cell", ROOT / "nc-systems/cold-read/cold-read-agy-cell.py")
codex_task = _load("run_codex_task_from_brief", ROOT / "scripts/run-codex-task-from-brief.py")
PROGRAM = "run-gemini-task-from-brief"


def _parser():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-C", dest="checkout", required=True)
    parser.add_argument("--brief", required=True)
    parser.add_argument("-o", dest="report", required=True)
    parser.add_argument("--sandbox", choices=("read-only", "workspace-write"), default="read-only")
    parser.add_argument("-m", dest="model", default="gemini-4-argon-high")
    parser.add_argument("--effort")
    parser.add_argument("--writable-root", action="append", default=[])
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--deadline-minutes", type=float, default=60)
    parser.add_argument("--run-log")
    return parser


def _run(command, checkout, log, deadline, environment, key_file_problem):
    process = subprocess.Popen(command, cwd=checkout, env=environment, stdin=subprocess.DEVNULL,
                               stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        code = process.wait(timeout=max(0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        codex_task.stop_process_group(process)
        raise RuntimeError("deadline passed; agy and its children were stopped") from None
    if code != 0:
        if key_file_problem:
            raise RuntimeError(f"agy exited {code}; GEMINI_API_KEY is not set, and "
                               f"{agy_cell.GEMINI_API_KEY_FILE} gave no key: {key_file_problem}.\n"
                               "If the file exists but cannot be read, fix that first.\n"
                               "Otherwise ask the user for the key, since an agent cannot obtain it:"
                               f" either set GEMINI_API_KEY or put the key in {agy_cell.GEMINI_API_KEY_FILE}.")
        raise RuntimeError(f"agy exited {code}")


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    if not math.isfinite(args.deadline_minutes) or args.deadline_minutes <= 0:
        parser.error("--deadline-minutes must be finite and greater than zero")
    if args.writable_root and args.sandbox != "workspace-write":
        parser.error("--writable-root requires --sandbox workspace-write")
    checkout = pathlib.Path(args.checkout).resolve()
    brief = pathlib.Path(args.brief).resolve()
    report = pathlib.Path(args.report).resolve()
    log_path = (pathlib.Path(args.run_log).resolve() if args.run_log
                else report.with_name(report.name + ".run.log"))
    roots = [pathlib.Path(root).resolve() for root in args.writable_root]
    if not checkout.is_dir() or any(not root.is_dir() for root in roots):
        parser.error("-C and every --writable-root must name existing directories")
    if len({brief, report, log_path}) != 3:
        parser.error("--brief, -o and --run-log must name different files")
    sandbox = agy_cell.credential_sandbox_program()
    stage = "preparing the sandbox"
    try:
        if sandbox is None or shutil.which(sandbox) is None:
            raise RuntimeError(f"required sandbox {sandbox or 'bwrap (Linux) or sandbox-exec (macOS)'} is unavailable")
        stage = f"reading the brief {brief}"
        prompt = brief.read_text(encoding="utf-8")
        if not prompt.strip():
            raise RuntimeError("the brief is empty")
        stage = "preparing the sandbox"
        # The sandbox masks the key file, so it is read here, before agy starts.
        environment, key_file_problem = agy_cell.agy_environment_and_key_file_problem(os.environ)
        writable_folders = [checkout, *roots] if args.sandbox == "workspace-write" else []
        prefix = agy_cell.credential_sandbox_prefix(
            writable_paths=[(report, False), *((folder, True) for folder in writable_folders)],
            network=args.network)
        stage = f"preparing report {report} and log {log_path}"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.unlink(missing_ok=True)
        # bwrap needs an existing file to bind without granting its parent directory.
        report.touch()
        with log_path.open("w+", encoding="utf-8") as log:
            deadline = time.monotonic() + args.deadline_minutes * 60
            stage = "listing models with agy models"
            _run([*prefix, "agy", "models"], checkout, log, deadline, environment, key_file_problem)
            log.seek(0)
            listing = re.sub(r"\x1b\[[0-9;]*m", "", log.read())
            # IDs in agy's human-readable listing are whitespace-delimited hyphenated words.
            known = sorted(set(re.findall(r"(?<![\w.-])[a-z][a-z0-9]*(?:[-.][a-z0-9]+)+(?![\w.-])", listing)))
            if args.model not in known:
                raise RuntimeError(f"unknown model {args.model!r}; known names: {', '.join(known) or '(none listed)'}")
            command = [*prefix, "agy", "--add-dir", str(checkout),
                       "--dangerously-skip-permissions", "--model", args.model,
                       "--print-timeout", f"{math.ceil(args.deadline_minutes * 60)}s",
                       "--output-format", "text"]
            for root in roots:
                command += ["--add-dir", str(root)]
            if args.effort:
                command += ["--effort", args.effort]
            command += ["--print", prompt + f"\n\nWrite the task's report to this exact file: {report}\n"]
            stage = "running the task"
            print(f"{PROGRAM}: running Gemini in {checkout}; log {log_path}", file=sys.stderr)
            _run(command, checkout, log, deadline, environment, key_file_problem)
        stage = f"reading report {report}"
        if not report.is_file() or not report.read_text(encoding="utf-8").strip():
            raise RuntimeError(f"agy exited 0 but wrote no report at {report}")
    except (OSError, UnicodeError, RuntimeError) as error:
        print(f"{PROGRAM}: failed while {stage}: {error}; output: {log_path}", file=sys.stderr)
        return 1
    print(f"report: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
