#!/usr/bin/env python3
"""Give a draft /explain reply its cold-read-fast-read, and print only the
part of the report the explain skill's check 13 acts on.

Usage, from the repository root, with a ten-minute timeout on the command:
  nc-systems/skills/explain/explain-reply-cold-read-fast-read.py <<'END_OF_EXPLAIN_REPLY'
  The user wrote: "<his words>"
  The reply to him:
  <the draft reply>
  END_OF_EXPLAIN_REPLY

WHY THIS EXISTS. Check 13 of the explain skill had one fresh-reader read each
draft reply before the reply was sent, and spelled the procedure out in 33
lines of the skill: where to write the draft file, the command, the timeout,
which report sections to read, what to do on failure. The user approved moving
that procedure into a small script the skill calls in one line (walk
explain-skill-draft-2026-09-29-2, the Fable advisor's point 3, "y" on
2026-09-30), to shorten the skill. The judgement -- which findings to fix and
which to skip -- stays in the skill; this program does the mechanics.

WHAT IT DOES. Reads the draft from standard input and checks its two labels:
the text opens with `The user wrote:` and has a line `The reply to him:` with
a reply under it, the shape the skill gives. Writes the text as
`explain-reply-draft.md` in a new temporary directory outside the repository;
the file name gives the cold-read-record its name, `explain-reply-draft-<date>`,
the name the dry run of 2026-09-29 used. Runs
`nc-systems/cold-read/cold-read-fast-read.py --target <that file>` from the
repository root, which ships the cold-read-record to the log-store itself.
Deletes the temporary directory afterwards: the cold-read-record keeps its own
copy of the draft under `target/`.

WHAT IT PRINTS. On success, the report from its "Question 2" heading to the
end: where the fresh-reader struggled, what the fresh-reader found missing, and
the sentence-coverage section the fast read appends, whose own line names any
sentence never restated. Question 1, the restatement, is left out: it runs the
full length of the draft and the skill does not act on it. If the report has
no "Question 2" heading, the whole report is printed rather than nothing. Then
the report's path, the fast read's own line saying whether the cold-read-record
reached the log-store, and one instruction line. When that record line says
FAILED or REFUSED -- ned-box could not be reached, which CLAUDE.md says the
user must be told -- an instruction line follows it. The fast read's other
stderr, the cold-read-cell's progress, is dropped. On failure, instruction
lines only, then the fast read's own last line as it printed it, for the cause.

EVERY LINE AN AGENT MUST ACT ON CARRIES ITS OWN INSTRUCTION. The skill's check
13 does not describe this output; it says the command prints an instruction
wherever the agent must act, and covers output with neither findings nor
instructions. So a line added here that needs action needs its instruction
here too (six-reviewer run SKILL-explain-skill-draft-2026-09-30-2: six of its
clusters came from the skill describing this output and drifting from it). The
failure wording is the skill's own, "the fresh-reader's read failed", so the
user hears one name for one failure whichever way the read failed.

TIMEOUT. The fast read takes one to two minutes, and about four when its cell
retries. This program stops the fast read, its whole process group, after
FAST_READ_TIMEOUT_SECONDS, which is under the ten-minute timeout the skill
gives the command, so the failure instructions print before the caller's tool
gives up on the command.

EXIT. 0 when a report was printed; 1 when the fast read failed or timed out;
64 when the input is not in the shape above and nothing was launched.

TEST SEAM. FAST_READ_PROGRAM_OVERRIDE_VARIABLE names a program to run in place
of the fast read, called with the same arguments; only
nc-systems/skills/explain/tests/explain-reply-cold-read-fast-read-test.py sets
it.
"""

import os
import pathlib
import shutil
import signal
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
FAST_READ_PROGRAM = REPO_ROOT / "nc-systems" / "cold-read" / "cold-read-fast-read.py"
FAST_READ_PROGRAM_OVERRIDE_VARIABLE = "EXPLAIN_REPLY_COLD_READ_FAST_READ_PROGRAM_OVERRIDE"
FAST_READ_TIMEOUT_SECONDS = 540
DRAFT_FILE_NAME = "explain-reply-draft.md"
USER_WORDS_LABEL = "The user wrote:"
REPLY_LABEL = "The reply to him:"
QUESTION_2_MARKER = "Question 2"
# The prefix of the line nc-systems/cold-read/cold-read-fast-read.py prints on
# stderr after shipping the cold-read-record.
RECORD_SHIP_LINE_PREFIX = "cold-read-fast-read: record:"
# Words in the record line that mean the cold-read-record did not reach the
# log-store (nc-systems/cold-read/cold-read-record-ship.py's own markers).
RECORD_SHIP_FAILURE_MARKERS = ("FAILED", "REFUSED")
RECORD_SHIP_FAILURE_INSTRUCTION = (
    "Tell the user what the record line above says, remedy included, before "
    "your closing line.")
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
SUCCESS_INSTRUCTION = "Do not cite this report to the user unless he asks."


def input_shape_problem(text: str):
    """None when `text` has the two labels in order with a reply after the
    second, otherwise what is wrong, in a few words."""
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
    """The report from the first heading naming Question 2 to the end, or the
    whole report when no heading names it."""
    lines = report_text.split("\n")
    for index, line in enumerate(lines):
        if line.lstrip().startswith("#") and QUESTION_2_MARKER in line:
            return "\n".join(lines[index:]).strip("\n")
    return report_text.strip("\n")


def run_fast_read(draft_path: pathlib.Path):
    """Run the fast read on `draft_path`. Returns (exit code or None on
    timeout, stdout, stderr). A fast read that cannot be started at all, a
    missing or non-executable program, comes back as exit code
    EXIT_FAST_READ_FAILED with the reason as stderr, so the caller prints the
    failure instructions rather than a traceback (six-reviewer run
    SKILL-explain-skill-draft-2026-09-30-2, codex-hunt-deep finding 15)."""
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
    """The fast read's lines saying where the cold-read-record was shipped."""
    return [line.strip() for line in (stderr or "").split("\n")
            if line.strip().startswith(RECORD_SHIP_LINE_PREFIX)]


def last_nonempty_line(text: str) -> str:
    lines = [line for line in (text or "").split("\n") if line.strip()]
    return lines[-1].strip() if lines else ""


def print_failure(cause: str) -> int:
    for line in FAILURE_INSTRUCTIONS:
        print(line)
    if cause:
        print(f"The fast read's last line: {cause}")
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
        draft_path = directory / DRAFT_FILE_NAME
        draft_path.write_text(text if text.endswith("\n") else text + "\n")
        exit_code, stdout, stderr = run_fast_read(draft_path)
    finally:
        shutil.rmtree(directory, ignore_errors=True)

    if exit_code is None:
        return print_failure(
            f"none; stopped after {FAST_READ_TIMEOUT_SECONDS} seconds")
    report_line = last_nonempty_line(stdout)
    if exit_code != 0 or not report_line or report_line.startswith("FAILED"):
        return print_failure(report_line or last_nonempty_line(stderr))
    report_path = pathlib.Path(report_line)
    try:
        report_text = report_path.read_text()
    except OSError as error:
        return print_failure(f"{report_line} (could not be read: {error.strerror})")
    print(report_from_question_2(report_text))
    print()
    print(f"Report: {report_path}")
    for line in record_ship_lines(stderr):
        print(line)
        if any(marker in line for marker in RECORD_SHIP_FAILURE_MARKERS):
            print(RECORD_SHIP_FAILURE_INSTRUCTION)
    print(SUCCESS_INSTRUCTION)
    return 0


if __name__ == "__main__":
    sys.exit(main())
