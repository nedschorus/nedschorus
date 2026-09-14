#!/usr/bin/env python3
"""Tests for scripts/compose-pull-request-reviewer-brief.py.

Every case runs the program as a subprocess on files written into a scratch
directory, and compares BYTES, not text: the program's promise is that the
instruction file's text lands in the composed prompt byte for byte, and a
text-mode comparison would forgive exactly the newline translation that
promise forbids. No case leans on the program's default instructions path —
that path is the reference checkout on the user's Mac, and this suite also
runs on ned-box, where it does not exist.

Run: python3 scripts/compose-pull-request-reviewer-brief-test.py   (exit 0 = all passed)
"""

import pathlib
import subprocess
import sys
import tempfile

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
COMPOSER = SCRIPTS_DIR / "compose-pull-request-reviewer-brief.py"

failures = []
cases_run = 0


def check(case_name, condition, detail=""):
    global cases_run
    cases_run += 1
    print(f"{'ok' if condition else 'FAIL'}: {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail!r}"[:600])


def run(*args):
    """Bytes in, bytes out: no text=True, so nothing is translated."""
    return subprocess.run([sys.executable, str(COMPOSER), *args],
                          capture_output=True, check=False)


INSTRUCTIONS = (
    b"# PR reviewer instructions\n"
    b"\n"
    b"This file's text is included verbatim in the prompt of every reviewer.\n"
    b"  - indented, with trailing spaces   \n"
    b"\n"
    b"\n"
    b"A `<<PR-REVIEWER-INSTRUCTIONS>>` mention mid-line is not a marker.\n"
    b"The last line, ending with a newline.\n"
)
FIRST_LINE = b"# PR reviewer instructions\n"
LAST_LINE = b"The last line, ending with a newline.\n"

BEFORE = (
    b"> You are the independent reviewer for pull request **#<N>**.\n"
    b"> The line before the marker, with <N> twice: <N>.\n"
)
AFTER = (
    b"> The line after the marker.\n"
    b">     gh api -X POST repos/o/r/pulls/<N>/reviews --input <file>\n"
    b"> Placeholders that are not <N>: <n>, < N >, <NN>, <N\n"
)
BRIEF = BEFORE + b"<<PR-REVIEWER-INSTRUCTIONS>>\n" + AFTER

with tempfile.TemporaryDirectory(prefix="compose-reviewer-brief-test-") as name:
    scratch = pathlib.Path(name)
    instructions = scratch / "instructions.md"
    instructions.write_bytes(INSTRUCTIONS)
    brief = scratch / "brief.md"
    brief.write_bytes(BRIEF)

    # --- The composed prompt -----------------------------------------------
    result = run("--pull-request", "356", "--brief-file", str(brief),
                 "--instructions-file", str(instructions))
    check("a well-formed brief composes and exits 0",
          result.returncode == 0 and result.stderr == b"", result.stderr)
    out = result.stdout
    check("the instruction file's text appears verbatim, as one contiguous run of bytes",
          INSTRUCTIONS in out, out)
    check("the instruction file's first line is in the output", FIRST_LINE in out, out)
    check("the instruction file's last line is in the output", LAST_LINE in out, out)
    check("the marker line is gone",
          b"<<PR-REVIEWER-INSTRUCTIONS>>\n" not in out.replace(INSTRUCTIONS, b""), out)
    check("<N> is substituted everywhere and no <N> remains",
          b"<N>" not in out and out.count(b"356") == 5, out)
    check("the line before the marker is preserved exactly, number substituted",
          b"> The line before the marker, with 356 twice: 356.\n" in out, out)
    check("the line after the marker is preserved exactly, number substituted",
          b"> The line after the marker.\n" in out
          and b"repos/o/r/pulls/356/reviews" in out, out)
    check("near-misses of the placeholder are left alone",
          b"Placeholders that are not 356: <n>, < N >, <NN>, <N\n" in out, out)
    expected = (BEFORE.replace(b"<N>", b"356") + INSTRUCTIONS
                + AFTER.replace(b"<N>", b"356"))
    check("the whole output is before + instructions + after, byte for byte, "
          "with nothing added at the seams",
          out == expected, out)
    check("the instructions are inserted where the marker stood, between the "
          "line before and the line after",
          out.index(b"> The line before") < out.index(INSTRUCTIONS)
          < out.index(b"> The line after"))

    # --- Bytes are bytes ---------------------------------------------------
    crlf_instructions = scratch / "instructions-crlf.md"
    crlf_bytes = b"line one\r\nline two, no final newline"
    crlf_instructions.write_bytes(crlf_bytes)
    result = run("--pull-request", "7", "--brief-file", str(brief),
                 "--instructions-file", str(crlf_instructions))
    check("CRLF line ends and a missing final newline in the instructions pass "
          "through untouched: no translation, no newline added",
          result.returncode == 0
          and result.stdout == (BEFORE.replace(b"<N>", b"7") + crlf_bytes
                                + AFTER.replace(b"<N>", b"7")),
          result.stdout)

    placeholder_in_instructions = scratch / "instructions-with-placeholder.md"
    placeholder_in_instructions.write_bytes(b"the rule says <N> here\n")
    result = run("--pull-request", "7", "--brief-file", str(brief),
                 "--instructions-file", str(placeholder_in_instructions))
    check("a <N> inside the instructions file is NOT substituted: the "
          "instruction bytes are never touched",
          result.returncode == 0 and b"the rule says <N> here\n" in result.stdout,
          result.stdout)

    crlf_brief = scratch / "brief-crlf.md"
    crlf_brief.write_bytes(b"before <N>\r\n<<PR-REVIEWER-INSTRUCTIONS>>\r\nafter\r\n")
    result = run("--pull-request", "7", "--brief-file", str(crlf_brief),
                 "--instructions-file", str(instructions))
    check("a marker line ending in CRLF is still the marker, and the brief's "
          "own CRLF ends are preserved",
          result.returncode == 0
          and result.stdout == b"before 7\r\n" + INSTRUCTIONS + b"after\r\n",
          result.stdout)

    # --- A brief with no placeholder ------------------------------------------
    plain_brief = scratch / "brief-plain.md"
    plain_brief.write_bytes(b"first\n<<PR-REVIEWER-INSTRUCTIONS>>\nlast\n")
    result = run("--pull-request", "7", "--brief-file", str(plain_brief),
                 "--instructions-file", str(instructions))
    check("a brief with no <N> composes unchanged apart from the marker",
          result.returncode == 0
          and result.stdout == b"first\n" + INSTRUCTIONS + b"last\n",
          result.stdout)

    marker_last = scratch / "brief-marker-last.md"
    marker_last.write_bytes(b"first\n<<PR-REVIEWER-INSTRUCTIONS>>")
    result = run("--pull-request", "7", "--brief-file", str(marker_last),
                 "--instructions-file", str(instructions))
    check("a marker on the final line, with no terminator, is still the marker",
          result.returncode == 0 and result.stdout == b"first\n" + INSTRUCTIONS,
          result.stdout)

    # --- Refusals: the marker ---------------------------------------------
    no_marker = scratch / "brief-no-marker.md"
    no_marker.write_bytes(b"first <N>\nno marker anywhere\n")
    result = run("--pull-request", "7", "--brief-file", str(no_marker),
                 "--instructions-file", str(instructions))
    check("zero marker lines refuses, exit 1, one line on stderr, nothing on stdout",
          result.returncode == 1 and result.stdout == b""
          and result.stderr.count(b"\n") == 1 and b"0 marker" in result.stderr,
          result.stderr)

    two_markers = scratch / "brief-two-markers.md"
    two_markers.write_bytes(b"<<PR-REVIEWER-INSTRUCTIONS>>\nmiddle\n"
                            b"<<PR-REVIEWER-INSTRUCTIONS>>\n")
    result = run("--pull-request", "7", "--brief-file", str(two_markers),
                 "--instructions-file", str(instructions))
    check("two marker lines refuses, exit 1, saying how many it found",
          result.returncode == 1 and result.stdout == b""
          and b"2 marker" in result.stderr, result.stderr)

    inline_marker = scratch / "brief-inline-marker.md"
    inline_marker.write_bytes(b"> <<PR-REVIEWER-INSTRUCTIONS>>\n")
    result = run("--pull-request", "7", "--brief-file", str(inline_marker),
                 "--instructions-file", str(instructions))
    check("a marker with anything else on its line (a blockquote prefix) is not "
          "a marker line: refused as zero markers",
          result.returncode == 1 and b"0 marker" in result.stderr, result.stderr)

    # --- Refusals: the files ----------------------------------------------
    empty = scratch / "instructions-empty.md"
    empty.write_bytes(b"")
    result = run("--pull-request", "7", "--brief-file", str(brief),
                 "--instructions-file", str(empty))
    check("an empty instructions file refuses, exit 1",
          result.returncode == 1 and result.stdout == b""
          and b"empty" in result.stderr, result.stderr)

    result = run("--pull-request", "7", "--brief-file", str(scratch / "absent.md"),
                 "--instructions-file", str(instructions))
    check("a missing brief file refuses, exit 1, naming the file",
          result.returncode == 1 and result.stdout == b""
          and b"brief file is unreadable" in result.stderr
          and b"absent.md" in result.stderr, result.stderr)

    result = run("--pull-request", "7", "--brief-file", str(brief),
                 "--instructions-file", str(scratch / "absent-rule.md"))
    check("a missing instructions file refuses, exit 1, naming the file",
          result.returncode == 1 and result.stdout == b""
          and b"instructions file is unreadable" in result.stderr
          and b"absent-rule.md" in result.stderr, result.stderr)

    result = run("--pull-request", "7", "--brief-file", str(scratch),
                 "--instructions-file", str(instructions))
    check("a directory given as the brief file is unreadable, exit 1",
          result.returncode == 1 and b"unreadable" in result.stderr, result.stderr)

    # --- Refusals: the command line, which must be exit 1 and never 2 --------
    result = run("--brief-file", str(brief), "--instructions-file", str(instructions))
    check("a missing --pull-request is a refusal, exit 1, not argparse's exit 2",
          result.returncode == 1 and b"malformed" in result.stderr, result.stderr)
    result = run("--pull-request", "abc", "--brief-file", str(brief),
                 "--instructions-file", str(instructions))
    check("a non-integer --pull-request is a refusal, exit 1",
          result.returncode == 1 and b"malformed" in result.stderr, result.stderr)
    for bad in ("0", "-5"):
        result = run("--pull-request", bad, "--brief-file", str(brief),
                     "--instructions-file", str(instructions))
        check(f"--pull-request {bad} is refused as not a positive integer, exit 1",
              result.returncode == 1 and b"positive integer" in result.stderr,
              result.stderr)
    result = run("--pull-request", "7", "--instructions-file", str(instructions))
    check("a missing --brief-file is a refusal: the standing brief has no default",
          result.returncode == 1 and b"malformed" in result.stderr, result.stderr)
    result = run("--pull-request", "7", "--brief-file", str(brief),
                 "--instructions-file", str(instructions), "--unknown-flag")
    check("an unknown flag is a refusal, exit 1",
          result.returncode == 1 and b"malformed" in result.stderr, result.stderr)

print()
# The count is printed so a short run is visible on sight: a run that ends
# early leaves the cases it never reached with no trace at all.
print(f"{cases_run} cases run")
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
