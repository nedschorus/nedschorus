#!/usr/bin/env python3
"""Once a week, run the work-snapshot hook under a real claude session and check that it found that session.

Usage:
  nc-systems/handoff/uncommitted-work-snapshot-hook-real-claude-session-weekly-owner-check.py
      [--claude-program PATH] [--record-directory DIR] [--timeout-seconds N]

  --claude-program    the program run as claude; default, `claude` on PATH, else
                      ~/.local/bin/claude, where it is installed: cron's PATH
                      on ned-box leaves that directory out
  --record-directory  write the record into this directory on this machine,
                      instead of into the log-store; for a run by hand
  --timeout-seconds   how long claude may run; default 300

nc-systems/handoff/tests/uncommitted-work-snapshots-test.py runs the hook,
scripts/uncommitted-work-snapshot-hook.py, with a fake process tree, so no
test there shows that the hook finds a real claude session. This check does,
once a week on each machine, from
nc-systems/general-tools/scheduled-jobs-on-each-machine.json.

WHAT ONE RUN DOES, in order.

  1. Makes a scratch clone holding the hook and the two modules it loads,
     with one commit, in a temporary directory.
  2. Runs `claude -p` on Haiku from that clone, with the hook registered for
     Bash calls through --settings, and asks it to run one shell command that
     writes LIVE_CHECK_FILE_NAME.
  3. Checks that claude exited 0 with a result that is not an error; that the
     clone has exactly one work-snapshot; that the work-snapshot holds the
     file; that its owner key names the process this program started as
     claude; and that its transcript trailer names claude's session id.
  4. Writes the record, the day's lines below, to the log-store:
     nedlern@ned-box:/home/nedlern/nedschorus-logs/uncommitted-work-snapshot-hook-real-claude-session-weekly-owner-checks/<machine>/<YYYY-MM-DD>.txt,
     where <machine> is ned-box or mac and the date is in America/Los_Angeles;
     from the Mac it is written over ssh.
  5. Prints the record and its citation, removes the scratch clone, and exits
     0 when every check passed, 1 when one failed, 2 when the record could
     not be written.

A lapsed claude login or a network outage makes claude exit nonzero or
return an error result. That is a failed check, written to the record with
claude's own words, so it reaches whoever reads the records.

SCHEDULE. Once a week, Sunday 04:30 Pacific, on each machine. Installed by
nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py from the
table beside it, scheduled-jobs-on-each-machine.json, where a change to the
schedule is made.

  ned-box: one cron line.

    30 4 * * 0 /usr/bin/python3 /home/nedlern/Projects/nedschorus/nc-systems/handoff/uncommitted-work-snapshot-hook-real-claude-session-weekly-owner-check.py >> /home/nedlern/.claude/weekly-uncommitted-work-snapshot-hook-real-claude-session-owner-check.log 2>&1

  the Mac: a launchd job at the same time; a run missed while the Mac
  sleeps starts at the next wake.

A record that could not be written leaves the run's lines in that log file.
"""

import argparse
import importlib.util
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROGRAM = "uncommitted-work-snapshot-hook-real-claude-session-weekly-owner-check"
SYSTEM_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = SYSTEM_DIRECTORY.parent.parent
MODULE_RELATIVE = Path("nc-systems/handoff/uncommitted-work-snapshots.py")
HOOK_RELATIVE = Path("scripts/uncommitted-work-snapshot-hook.py")
GIT_OUTPUT_MODULE_RELATIVE = Path(
    "nc-systems/general-tools/git-machine-readable-output-runner-and-parser-common.py")
LIVE_CHECK_FILE_NAME = "live-check.txt"
LIVE_CHECK_PROMPT = (f"Run this one shell command and nothing else: "
                     f"echo live > {LIVE_CHECK_FILE_NAME}")
LIVE_CHECK_MODEL = "haiku"
LIVE_CHECK_AGENT_SEAT = PROGRAM
DEFAULT_TIMEOUT_SECONDS = 300
LOG_STORE_ROOT = "/home/nedlern/nedschorus-logs"
RECORDS_KIND_DIRECTORY_NAME = "uncommitted-work-snapshot-hook-real-claude-session-weekly-owner-checks"
RECORD_WRITE_TIMEOUT_SECONDS = 60
EXIT_PASSED, EXIT_CHECK_FAILED, EXIT_RECORD_NOT_WRITTEN = 0, 1, 2


def module_loaded_by_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mark = module_loaded_by_path("daily_memory_review_mark",
                             SYSTEM_DIRECTORY / "daily-memory-review-mark.py")
runner = module_loaded_by_path("run_all_test_suites",
                               REPOSITORY_ROOT / "scripts" / "run-all-test-suites.py")
snapshots = module_loaded_by_path("uncommitted_work_snapshots",
                                  REPOSITORY_ROOT / MODULE_RELATIVE)


def git(directory, *arguments):
    completed = subprocess.run(
        ["git", "-C", str(directory), "-c", f"user.name={PROGRAM}",
         "-c", f"user.email={PROGRAM}@nedschorus.invalid", *arguments],
        capture_output=True, text=True, check=False,
        env=runner.environment_without_git_redirecting_variables())
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)} exited {completed.returncode}: "
                           f"{completed.stderr.strip() or 'no detail'}")
    return completed.stdout


def default_claude_program():
    return shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude")


def make_scratch_clone(clone):
    git(clone.parent, "init", "-q", str(clone))
    for relative in (MODULE_RELATIVE, HOOK_RELATIVE, GIT_OUTPUT_MODULE_RELATIVE):
        (clone / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPOSITORY_ROOT / relative, clone / relative)
    (clone / ".gitignore").write_text("__pycache__/\n")
    git(clone, "add", "-A")
    git(clone, "commit", "-q", "-m", "scratch clone for the owner check")


def hook_settings_json(clone):
    command = f"{shlex.quote(sys.executable)} {shlex.quote(str(clone / HOOK_RELATIVE))}"
    return json.dumps({"hooks": {"PostToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": command}]}]}})


def process_id_in_owner_key(owner_key):
    parts = owner_key.split("-")
    # Linux keys are boot id, process id, start ticks; macOS keys are process id, start.
    return parts[1] if len(parts) == 3 else parts[0]


def start_claude(claude_program, clone, settings_path):
    """Start claude in a session of its own; raise OSError if it cannot start."""
    environment = runner.environment_without_git_redirecting_variables()
    environment[snapshots.AGENT_SEAT_ENVIRONMENT_VARIABLE] = LIVE_CHECK_AGENT_SEAT
    return subprocess.Popen(
        [claude_program, "-p", LIVE_CHECK_PROMPT, "--model", LIVE_CHECK_MODEL,
         "--allowedTools", "Bash", "--output-format", "json", "--no-session-persistence",
         "--settings", str(settings_path)],
        cwd=clone, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=environment, start_new_session=True)


def wait_for_claude(process, timeout_seconds):
    """Return (claude's process id, exit code, stdout, stderr); the exit code is None on timeout.

    A timeout, or an interruption such as Ctrl-C, kills claude's whole process group, so
    no hook or Bash command claude started outlives the check. claude runs in a session of
    its own, so a Ctrl-C at the terminal reaches only the check, which re-raises it after
    the kill. Killing the group also closes any copy of claude's output pipes a child holds,
    so the read after the kill does not wait for that child; the test's fake claude has such
    a child, and whether a real claude's children hold claude's pipes has not been checked.
    """
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        return process.pid, None, stdout, stderr
    except BaseException:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise
    return process.pid, process.returncode, stdout, stderr


def first_line_or_no_detail(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[0] if lines else "no detail"


def check_results(clone, claude_process_id, exit_code, stdout, stderr, timeout_seconds):
    """Return the record's result lines, each opening PASS or FAIL."""
    if exit_code is None:
        return [f"FAIL claude did not finish within {timeout_seconds} s and was stopped"]
    if exit_code != 0:
        return [f"FAIL claude exited {exit_code}: {first_line_or_no_detail(stderr or stdout)}"]
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return [f"FAIL claude printed no JSON result: {first_line_or_no_detail(stdout)}"]
    if result.get("is_error"):
        return [f"FAIL claude's result is an error: {first_line_or_no_detail(str(result.get('result')))}"]
    lines = ["PASS claude exited 0 with a result that is not an error"]
    found = snapshots.all_work_snapshots(clone)
    if len(found) != 1:
        lines.append(f"FAIL the hook wrote {len(found)} work-snapshots, not 1: "
                     f"{[snapshot['ref'] for snapshot in found]}")
        return lines
    snapshot = found[0]
    lines.append(f"PASS the hook wrote one work-snapshot, {snapshot['ref']}")
    held = git(clone, "ls-tree", "-r", "--name-only", snapshot["ref"]).split("\n")
    lines.append(f"{'PASS' if LIVE_CHECK_FILE_NAME in held else 'FAIL'} the work-snapshot "
                 f"holds {LIVE_CHECK_FILE_NAME}")
    owner_process_id = process_id_in_owner_key(snapshot["owner_key"])
    lines.append(f"{'PASS' if owner_process_id == str(claude_process_id) else 'FAIL'} its owner "
                 f"key names process {owner_process_id}; claude ran as process {claude_process_id}")
    session_id = str(result.get("session_id") or "")
    lines.append(f"{'PASS' if session_id and session_id in snapshot['transcript'] else 'FAIL'} "
                 f"its transcript trailer, {snapshot['transcript'] or 'empty'}, names claude's "
                 f"session {session_id or '(none in the result)'}")
    return lines


def write_record(record, record_directory, now):
    """Write the record; return its citation. Raise mark.DailyMemoryReviewReadOrWriteFailed."""
    pacific_date = mark.pacific_time_of(now).date().isoformat()
    on_ned_box = mark.this_machine_is_ned_box()
    machine = "ned-box" if on_ned_box else "mac"
    file_name = f"{pacific_date}.txt"
    if record_directory is not None:
        directory = str(record_directory)
        ssh_target = None
        citation = f"{directory}/{file_name}"
    else:
        directory = f"{LOG_STORE_ROOT}/{RECORDS_KIND_DIRECTORY_NAME}/{machine}"
        ssh_target = None if on_ned_box else mark.NED_BOX_SSH_TARGET
        citation = f"{mark.NED_BOX_SSH_TARGET}:{directory}/{file_name}"
    command = (f"mkdir -p {shlex.quote(directory)} && "
               f"cat > {shlex.quote(f'{directory}/{file_name}')}")
    mark.run_on_ned_box_or_here(command, ssh_target, RECORD_WRITE_TIMEOUT_SECONDS,
                                stdin_text=record)
    return citation


def owner_check_result_lines(arguments, scratch):
    """Make the scratch clone, run claude in it, and return the record's result lines."""
    clone = scratch / "clone"
    try:
        make_scratch_clone(clone)
        settings_path = scratch / "settings.json"
        settings_path.write_text(hook_settings_json(clone))
    except Exception as error:
        return [f"FAIL the scratch clone could not be made: {type(error).__name__}: {error}"]
    try:
        process = start_claude(arguments.claude_program, clone, settings_path)
    except OSError as error:
        return [f"FAIL {arguments.claude_program} could not be started: "
                f"{type(error).__name__}: {error}"]
    claude_process_id, exit_code, stdout, stderr = wait_for_claude(
        process, arguments.timeout_seconds)
    return check_results(clone, claude_process_id, exit_code, stdout, stderr,
                         arguments.timeout_seconds)


def main(argv=None, now=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--claude-program", default=default_claude_program())
    parser.add_argument("--record-directory", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    arguments = parser.parse_args(argv)
    now = now or datetime.now(timezone.utc)
    scratch = Path(tempfile.mkdtemp(prefix=f"{PROGRAM}-"))
    try:
        lines = owner_check_result_lines(arguments, scratch)
    except Exception as error:
        lines = [f"FAIL the check could not run: {type(error).__name__}: {error}"]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    failed = any(line.startswith("FAIL") for line in lines)
    record = "\n".join([
        f"{PROGRAM} on {'ned-box' if mark.this_machine_is_ned_box() else 'mac'}, "
        f"started {now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        *lines,
        f"VERDICT: {'FAILED' if failed else 'PASSED'}", ""])
    print(record, end="")
    try:
        citation = write_record(record, arguments.record_directory, now)
    except mark.DailyMemoryReviewReadOrWriteFailed as error:
        print(f"{PROGRAM}: the record was not written: {error}\n"
              f"Run this check again when the cause is cleared; the lines above are the "
              f"record it would have written.", file=sys.stderr)
        return EXIT_RECORD_NOT_WRITTEN
    print(f"record: {citation}")
    return EXIT_CHECK_FAILED if failed else EXIT_PASSED


if __name__ == "__main__":
    sys.exit(main())
