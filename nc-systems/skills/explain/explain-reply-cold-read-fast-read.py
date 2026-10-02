#!/usr/bin/env python3
"""Run a cold-read-fast-read on a draft /explain reply and print actionable findings.

Pipe a draft beginning with `The user wrote:` and containing a line
`The reply to him:` followed by the reply. Exit 0 means a report was printed,
1 means the fast read failed or timed out, and 64 means invalid input.

Every output line requiring action must carry its own instruction, because
the explain skill delegates output handling to this program.
The timeout stays below the skill's ten-minute limit so failure instructions
reach the caller before the caller's tool times out.
"""

import datetime
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
FAST_READ_PROGRAM = REPO_ROOT / "nc-systems" / "cold-read" / "cold-read-fast-read.py"
FAST_READ_PROGRAM_OVERRIDE_VARIABLE = "EXPLAIN_REPLY_COLD_READ_FAST_READ_PROGRAM_OVERRIDE"
FAST_READ_TIMEOUT_SECONDS = 540
DRAFT_FILE_STEM = "explain-reply-draft"
# The handoff-supervisor sets nedschorus-<seat name>-tasks in each seat's environment.
SEAT_NAME_ENVIRONMENT_VARIABLE = "CLAUDE_CODE_TASK_LIST_ID"
SEAT_NAME_PREFIX = "nedschorus-"
SEAT_NAME_SUFFIX = "-tasks"
NO_SEAT_NAME = "no-seat"
USER_WORDS_LABEL = "The user wrote:"
REPLY_LABEL = "The reply to him:"
QUESTION_2_MARKER = "Question 2"
RECORD_SHIP_LINE_PREFIX = "cold-read-fast-read: record:"
RECORD_SHIP_FAILED_MARKER = "FAILED"
RECORD_SHIP_REFUSED_MARKER = "REFUSED"
RECORD_SHIP_FAILED_INSTRUCTION = (
    "Tell the user what the record line above says, remedy included, before "
    "your closing line.")
RECORD_SHIP_REFUSED_INSTRUCTION = (
    "Rename {record_directory} with a -2 suffix, or the next number not taken, "
    "then run python3 nc-systems/cold-read/cold-read-record-ship.py on the "
    "renamed directory.")
CELL_LAUNCHER_LINE = re.compile(r"cold-read-[a-z-]+-cell: ")
CELL_LAUNCHER_LINES_INSTRUCTION = (
    "Tell the user what the cell launcher's lines above say, remedy included, "
    "before your closing line.")
EXIT_FAST_READ_FAILED = 1
EXIT_BAD_INPUT = 64

INPUT_SHAPE_INSTRUCTIONS = (
    "Nothing was run. Pipe the draft in on standard input, in this shape:",
    f"  {USER_WORDS_LABEL} \"<his words>\"",
    f"  {REPLY_LABEL}",
    "  <your draft reply>",
)
FAILURE_INSTRUCTIONS = (
    "The fresh-reader's read failed.",
    "Send your reply anyway, with one line before your closing line saying the "
    "fresh-reader's read failed.",
    "Do not run this command again for this reply.",
)
SUCCESS_INSTRUCTION = "Do not cite the findings to the user unless he asks."


def seat_name_from_environment():
    """Return the seat name from the supervisor's task-list ID, or None for an unknown shape."""
    value = os.environ.get(SEAT_NAME_ENVIRONMENT_VARIABLE, "").strip()
    if not value.startswith(SEAT_NAME_PREFIX) or not value.endswith(SEAT_NAME_SUFFIX):
        return None
    return value[len(SEAT_NAME_PREFIX):-len(SEAT_NAME_SUFFIX)] or None


def draft_file_name(seat_name, now: datetime.datetime) -> str:
    # Seat and local time distinguish records shipped by different checkouts to the shared log-store.
    return f"{DRAFT_FILE_STEM}-{seat_name or NO_SEAT_NAME}-{now.strftime('%H%M%S')}.md"


def input_shape_problem(text: str):
    """Return a description of invalid labels or missing reply text, or None."""
    if not text.lstrip().startswith(USER_WORDS_LABEL):
        return f"the text does not open with `{USER_WORDS_LABEL}`"
    lines = text.split("\n")
    label_indexes = [index for index, line in enumerate(lines)
                     if line.strip() == REPLY_LABEL]
    if not label_indexes:
        return f"no line reads `{REPLY_LABEL}`"
    reply = "\n".join(lines[label_indexes[0] + 1:])
    if not reply.strip():
        return f"nothing follows `{REPLY_LABEL}`"
    return None


def report_from_question_2(report_text: str) -> str:
    """Return the report from Question 2 onward, or the whole report if that heading is absent."""
    lines = report_text.split("\n")
    for index, line in enumerate(lines):
        if line.lstrip().startswith("#") and QUESTION_2_MARKER in line:
            return "\n".join(lines[index:]).strip("\n")
    return report_text.strip("\n")


def run_fast_read(draft_path: pathlib.Path):
    """Return (exit code or None on timeout, stdout, stderr)."""
    program = os.environ.get(FAST_READ_PROGRAM_OVERRIDE_VARIABLE) or str(FAST_READ_PROGRAM)
    try:
        process = subprocess.Popen(
            [program, "--target", str(draft_path)],
            cwd=REPO_ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, start_new_session=True)
    except OSError as error:
        return EXIT_FAST_READ_FAILED, "", f"could not start {program}: {error.strerror}"
    try:
        stdout, stderr = process.communicate(timeout=FAST_READ_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = process.communicate()
        return None, stdout, stderr
    return process.returncode, stdout, stderr


def record_ship_lines(stderr: str) -> list:
    return [line.strip() for line in (stderr or "").split("\n")
            if line.strip().startswith(RECORD_SHIP_LINE_PREFIX)]


def cell_launcher_lines(stderr: str) -> list:
    return [line.strip() for line in (stderr or "").split("\n")
            if CELL_LAUNCHER_LINE.match(line.strip())]


def last_nonempty_line(text: str) -> str:
    lines = [line for line in (text or "").split("\n") if line.strip()]
    return lines[-1].strip() if lines else ""


def print_failure(cause: str, stderr: str = "") -> int:
    for line in FAILURE_INSTRUCTIONS:
        print(line)
    if cause:
        print(f"The fast read's last line: {cause}")
    launcher_lines = cell_launcher_lines(stderr)
    for line in launcher_lines:
        print(line)
    if launcher_lines:
        print(CELL_LAUNCHER_LINES_INSTRUCTION)
    return EXIT_FAST_READ_FAILED


def main() -> int:
    if len(sys.argv) > 1:
        for line in INPUT_SHAPE_INSTRUCTIONS:
            print(line)
        print("Pass no arguments.")
        return EXIT_BAD_INPUT
    text = sys.stdin.read()
    problem = input_shape_problem(text)
    if problem is not None:
        print(f"The draft was not read: {problem}.")
        for line in INPUT_SHAPE_INSTRUCTIONS:
            print(line)
        return EXIT_BAD_INPUT

    directory = pathlib.Path(tempfile.mkdtemp(prefix="explain-reply-"))
    try:
        draft_path = directory / draft_file_name(
            seat_name_from_environment(), datetime.datetime.now())
        draft_path.write_text(text if text.endswith("\n") else text + "\n")
        exit_code, stdout, stderr = run_fast_read(draft_path)
    finally:
        shutil.rmtree(directory, ignore_errors=True)

    if exit_code is None:
        return print_failure(
            f"none; stopped after {FAST_READ_TIMEOUT_SECONDS} seconds", stderr)
    report_line = last_nonempty_line(stdout)
    if exit_code != 0 or not report_line or report_line.startswith("FAILED"):
        return print_failure(report_line or last_nonempty_line(stderr), stderr)
    report_path = pathlib.Path(report_line)
    try:
        report_text = report_path.read_text()
    except OSError as error:
        return print_failure(
            f"{report_line} (could not be read: {error.strerror})", stderr)
    print(report_from_question_2(report_text))
    print()
    print(f"Report: {report_path}")
    for line in record_ship_lines(stderr):
        print(line)
        outcome = line[len(RECORD_SHIP_LINE_PREFIX):].strip()
        if outcome.startswith(RECORD_SHIP_FAILED_MARKER):
            print(RECORD_SHIP_FAILED_INSTRUCTION)
        elif outcome.startswith(RECORD_SHIP_REFUSED_MARKER):
            print(RECORD_SHIP_REFUSED_INSTRUCTION.format(
                record_directory=report_path.parent))
    print(SUCCESS_INSTRUCTION)
    return 0


if __name__ == "__main__":
    sys.exit(main())
