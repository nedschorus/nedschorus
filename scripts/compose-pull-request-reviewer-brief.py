#!/usr/bin/env python3
"""Compose a reviewer brief with the reviewing instructions inserted verbatim.

The default instructions come from the reference checkout on main so a pull
request cannot change the rule used to review itself. The brief is local to
the machine, so the caller supplies its path.

Byte I/O preserves instruction text exactly. Substitute the pull request
number only in the brief, never in the inserted instructions.
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
    """Use exit 1 for malformed arguments; the project reserves exit 2 for defects."""

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
    """Return the composed prompt or raise Refusal."""
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
