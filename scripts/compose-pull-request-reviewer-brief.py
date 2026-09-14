#!/usr/bin/env python3
"""Compose a pull-request reviewer's brief at the moment the reviewer is commissioned.

The merge-lane seat commissions an independent reviewer for every pull request
with a fixed standing brief. The reviewing rule itself lives in ONE place,
`docs/agents/pr-reviewer-instructions.md`, whose own first lines say: "This
file's text is included verbatim in the prompt of every commissioned PR
reviewer. The instruments that commission reviewers read it at composition
time and paste it in — never point at it, never paraphrase it. (Ruled
2026-08-30: one copy, included everywhere; a pointed-at rule gets skipped, a
paraphrased one drifts.)" The standing brief used to point at that file by
absolute path, which is the pointed-at form the rule forbids; pasting the text
into the brief would make a second copy, which is the drifting form. So the
user ruled at the merge-lane seat (2026-09-14): compose the brief at commission
time. This program is that composition.

What it does. It reads the standing brief, which contains exactly one MARKER
LINE — `<<PR-REVIEWER-INSTRUCTIONS>>` on a line by itself — and may contain
the placeholder `<N>` (literal, angle brackets included) wherever the pull
request number belongs. It replaces every `<N>` in the brief with the number,
replaces the marker line (the line and its own line terminator) with the
instruction file's entire text byte for byte — no reflow, no trimming, no
added newline; the instruction file's own final newline is what separates it
from the line after the marker — and writes the composed prompt to stdout.
The `<N>` substitution runs on the brief BEFORE the instructions are inserted,
so the instruction bytes are never touched even if that file one day contains
the placeholder itself. All I/O is in bytes, so no newline translation and no
encoding step can alter either file on the way through.

Why `--instructions-file` defaults to the REFERENCE CHECKOUT'S ABSOLUTE PATH,
`/Users/el/Projects/nedschorus/docs/agents/pr-reviewer-instructions.md`, and
not to a path relative to this script: a reviewer works in a worktree checked
out at the pull request's head, and a relative path would resolve inside that
worktree — so a pull request that edited the reviewing rule would compose its
own edited rule into its own review. The reference checkout is always on main,
so the rule the reviewer reads is the rule main holds. `--brief-file` has no
default because the standing brief is machine-local (it lives in the
gitignored `walk-ledgers/` on the merge-lane seat's Mac); its location is the
caller's to state.

Refusals (one line on stderr, exit 1): the brief file has zero or more than
one marker line; the instructions file is empty (zero bytes); either file is
unreadable (missing, unreadable, or not a regular file); a malformed command
line, including a `--pull-request` that is not a positive integer. Exit 2 is
reserved for a defect in this program, per the project convention set by
`scripts/main-gatekeeper.py`'s reply contract — which is why argparse's own
usage-and-exit-2 is overridden below. No network, no git, no subprocess: pure
text.

Usage:
  compose-pull-request-reviewer-brief.py --pull-request <N> --brief-file <path>
      [--instructions-file <path>] > <composed prompt>
"""

import argparse
import sys
from pathlib import Path

MARKER_LINE = b"<<PR-REVIEWER-INSTRUCTIONS>>"
NUMBER_PLACEHOLDER = b"<N>"
DEFAULT_INSTRUCTIONS_FILE = Path(
    "/Users/el/Projects/nedschorus/docs/agents/pr-reviewer-instructions.md")

EXIT_COMPOSED = 0
EXIT_REFUSED = 1
EXIT_DEFECT = 2


class Refusal(Exception):
    """A reason the brief cannot be composed; one line for stderr."""


class RefusingArgumentParser(argparse.ArgumentParser):
    """A malformed command line is a refusal (exit 1), not a defect (exit 2).

    argparse's default is usage text on stderr and exit 2, which this project
    reserves for a program defect; `scripts/main-gatekeeper.py` overrides it
    the same way.
    """

    def error(self, message):
        raise Refusal(f"the command line is malformed: {message}")


def build_parser() -> argparse.ArgumentParser:
    parser = RefusingArgumentParser(
        prog="compose-pull-request-reviewer-brief.py",
        description="Compose the standing reviewer brief with the reviewing "
                    "rule inserted verbatim at its marker line.",
    )
    parser.add_argument("--pull-request", required=True, type=int, metavar="N",
                        help="the pull request number; replaces every <N> in the brief")
    parser.add_argument("--brief-file", required=True, type=Path, metavar="PATH",
                        help="the standing brief, holding exactly one "
                             "<<PR-REVIEWER-INSTRUCTIONS>> marker line")
    parser.add_argument("--instructions-file", type=Path, metavar="PATH",
                        default=DEFAULT_INSTRUCTIONS_FILE,
                        help="the reviewing rule to insert at the marker "
                             "(default: the reference checkout's copy, see the docstring)")
    return parser


def read_bytes_or_refuse(path: Path, what: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as failure:
        raise Refusal(f"{what} is unreadable: {path}: {failure.strerror or failure}")


def is_marker_line(line: bytes) -> bool:
    return line.rstrip(b"\r\n") == MARKER_LINE


def compose(brief: bytes, instructions: bytes, pull_request: int) -> bytes:
    """The composed prompt, or a Refusal naming why there is none."""
    if instructions == b"":
        raise Refusal("the instructions file is empty; nothing to insert at the marker")
    lines = brief.splitlines(keepends=True)
    marker_count = sum(1 for line in lines if is_marker_line(line))
    if marker_count != 1:
        raise Refusal(
            f"the brief file has {marker_count} marker lines "
            f"({MARKER_LINE.decode()}); exactly one is required")
    number = str(pull_request).encode()
    composed = []
    for line in lines:
        if is_marker_line(line):
            composed.append(instructions)
        else:
            composed.append(line.replace(NUMBER_PLACEHOLDER, number))
    return b"".join(composed)


def main(argv=None) -> int:
    try:
        arguments = build_parser().parse_args(argv)
        if arguments.pull_request <= 0:
            raise Refusal(f"--pull-request must be a positive integer, "
                          f"not {arguments.pull_request}")
        brief = read_bytes_or_refuse(arguments.brief_file, "the brief file")
        instructions = read_bytes_or_refuse(arguments.instructions_file,
                                            "the instructions file")
        composed = compose(brief, instructions, arguments.pull_request)
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return EXIT_REFUSED
    sys.stdout.buffer.write(composed)
    sys.stdout.buffer.flush()
    return EXIT_COMPOSED


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as defect:  # noqa: BLE001 - exit 2 is the defect channel
        print(f"program defect: {type(defect).__name__}: {defect}", file=sys.stderr)
        sys.exit(EXIT_DEFECT)
