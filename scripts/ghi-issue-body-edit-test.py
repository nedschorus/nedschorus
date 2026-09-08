#!/usr/bin/env python3
"""Tests for ghi-issue-body-edit.py (user-ruled 2026-09-08, "GHI edits
should check for conflicts").

`gh` is never invoked for real and no issue is ever touched: every case
monkeypatches run_gh with a fake that returns canned CompletedProcess
objects and records the argument lists it was called with — the same stub
shape ghi-mirror-refresh-test.py uses. "Wrote nothing" is therefore checked
against the call log (no `issue edit` call was ever made), not merely
against the exit code, since an exit code alone cannot tell a refusal that
wrote nothing from a refusal that wrote and then complained. Body files
live under a TemporaryDirectory.

Run: python3 scripts/ghi-issue-body-edit-test.py
"""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("ghi-issue-body-edit.py")

_spec = importlib.util.spec_from_file_location("ghi_issue_body_edit", SCRIPT_PATH)
body_edit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(body_edit)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def patch(monkey_target, value):
    setattr(body_edit, monkey_target, value)


def fake_gh(view_body="body text", view_updated_at="2026-09-08T21:48:37Z",
            view_returncode=0, view_stderr="", view_stdout=None,
            edit_returncode=0, edit_stdout="https://github.com/x/y/issues/7",
            edit_stderr=""):
    """Stubs run_gh for one run and returns the call log.

    `issue view` answers with a GitHub-shaped JSON payload (or the canned
    failure); `issue edit` answers with gh's URL line (or the canned
    failure). Any other gh subcommand is a test bug and says so.
    """
    calls = []

    def fake_run_gh(arguments, timeout=body_edit.GH_TIMEOUT_SECONDS):
        calls.append(arguments)
        if arguments[:2] == ["issue", "view"]:
            if view_returncode != 0:
                return subprocess.CompletedProcess(arguments, view_returncode, "",
                                                   view_stderr)
            stdout = (json.dumps({"body": view_body, "updatedAt": view_updated_at})
                      if view_stdout is None else view_stdout)
            return subprocess.CompletedProcess(arguments, 0, stdout, "")
        if arguments[:2] == ["issue", "edit"]:
            return subprocess.CompletedProcess(arguments, edit_returncode,
                                               edit_stdout if edit_returncode == 0 else "",
                                               edit_stderr)
        raise AssertionError(f"unexpected gh call: {arguments}")

    patch("run_gh", fake_run_gh)
    return calls


def edit_calls(calls):
    return [call for call in calls if call[:2] == ["issue", "edit"]]


def run_main(argv):
    """main() with stdout and stderr captured; returns (code, out, err)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = body_edit.main(argv)
    return code, out.getvalue(), err.getvalue()


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)

    def body_file(name, text):
        path = root / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    # --- the unchanged path: the edit is made ------------------------------
    # The base record carries the trailing newline `--jq .body` appends, the
    # real shape of a file produced by the docstring's own read command; it
    # must not be read as a change.
    base = body_file("base-1.md", "the body as read\n")
    new = body_file("new-1.md", "the body as read, plus a paragraph\n")
    calls = fake_gh(view_body="the body as read")
    code, out, err = run_main(["7", "--base-body-file", base,
                               "--new-body-file", new, "--repo", "x/y"])
    check("an unchanged body is edited, exit 0",
          code == body_edit.EXIT_EDITED, f"exit {code}; stderr={err!r}")
    check("the edit call is gh issue edit --body-file the new body",
          edit_calls(calls) == [["issue", "edit", "7", "--repo", "x/y",
                                "--body-file", new]], calls)
    check("success says which issue was rewritten and that nothing was discarded",
          "#7" in out and "still current" in out, out)
    check("gh's URL line is passed through rather than swallowed",
          "https://github.com/x/y/issues/7" in out, out)

    # --- the changed path: refuse, write nothing, non-zero -----------------
    base = body_file("base-2.md", "line one\nline two\n")
    new = body_file("new-2.md", "line one\nline two rewritten\n")
    calls = fake_gh(view_body="line one\nline two\nline three from another seat",
                    view_updated_at="2026-09-08T22:10:00Z")
    code, out, err = run_main(["7", "--base-body-file", base,
                               "--new-body-file", new, "--repo", "x/y"])
    check("a body changed since the read is REFUSED with exit 2",
          code == body_edit.EXIT_REFUSED, f"exit {code}; stderr={err!r}")
    check("a refusal makes no gh issue edit call at all",
          edit_calls(calls) == [], calls)
    check("a refusal says it changed, and when",
          "REFUSED" in err and "2026-09-08T22:10:00Z" in err, err)
    check("a refusal prints the other seat's change as a diff line",
          "+line three from another seat" in err, err)
    check("a refusal names the next action",
          "Re-read the issue" in err, err)
    check("a refusal prints nothing to stdout, so a caller reading stdout "
          "cannot mistake it for a success",
          out == "", out)

    # --- line endings alone are never a conflict ---------------------------
    # A body typed into GitHub's web editor comes back CRLF; the caller's
    # file is LF. Same text, so this must edit rather than refuse.
    base = body_file("base-3.md", "first line\nsecond line\n")
    new = body_file("new-3.md", "first line\nsecond line\nthird line\n")
    calls = fake_gh(view_body="first line\r\nsecond line")
    code, out, err = run_main(["7", "--base-body-file", base,
                               "--new-body-file", new, "--repo", "x/y"])
    check("CRLF on GitHub against LF in the base record is not a conflict",
          code == body_edit.EXIT_EDITED and len(edit_calls(calls)) == 1,
          f"exit {code}; stderr={err!r}")

    # --- an empty base record is legal: the issue had no body when read ----
    base = body_file("base-4.md", "")
    new = body_file("new-4.md", "a body where there was none\n")
    calls = fake_gh(view_body="")
    code, out, err = run_main(["7", "--base-body-file", base,
                               "--new-body-file", new, "--repo", "x/y"])
    check("an empty base record against an empty body edits, not refuses",
          code == body_edit.EXIT_EDITED and len(edit_calls(calls)) == 1,
          f"exit {code}; stderr={err!r}")

    # --- a body file that is missing or empty is a bad invocation ----------
    base = body_file("base-5.md", "the body as read\n")
    calls = fake_gh(view_body="the body as read")
    code, out, err = run_main(["7", "--base-body-file", base,
                               "--new-body-file", str(root / "no-such-file.md"),
                               "--repo", "x/y"])
    check("a new body file that does not exist exits 64 and calls no gh",
          code == body_edit.EXIT_BAD_INVOCATION and calls == [],
          f"exit {code}; calls={calls}; stderr={err!r}")

    empty_new = body_file("new-6.md", "   \n\n")
    calls = fake_gh(view_body="the body as read")
    code, out, err = run_main(["7", "--base-body-file", base,
                               "--new-body-file", empty_new, "--repo", "x/y"])
    check("an empty new body file exits 64 rather than erasing the issue's text",
          code == body_edit.EXIT_BAD_INVOCATION and calls == [],
          f"exit {code}; calls={calls}; stderr={err!r}")
    check("the empty-body refusal says why",
          "erase" in err, err)

    new = body_file("new-7.md", "a body\n")
    calls = fake_gh(view_body="the body as read")
    code, out, err = run_main(["7", "--base-body-file", str(root / "no-base.md"),
                               "--new-body-file", new, "--repo", "x/y"])
    check("a base record file that does not exist exits 64 and calls no gh",
          code == body_edit.EXIT_BAD_INVOCATION and calls == [],
          f"exit {code}; calls={calls}; stderr={err!r}")

    # --- a bad issue number is a bad invocation ---------------------------
    calls = fake_gh(view_body="the body as read")
    code, out, err = run_main(["0", "--base-body-file", base,
                               "--new-body-file", new, "--repo", "x/y"])
    check("issue number 0 exits 64 and calls no gh",
          code == body_edit.EXIT_BAD_INVOCATION and calls == [],
          f"exit {code}; calls={calls}; stderr={err!r}")

    calls = fake_gh(view_body="the body as read")
    code, out, err = run_main(["-3", "--base-body-file", base,
                               "--new-body-file", new, "--repo", "x/y"])
    check("a negative issue number exits 64 and calls no gh",
          code == body_edit.EXIT_BAD_INVOCATION and calls == [],
          f"exit {code}; calls={calls}; stderr={err!r}")

    # argparse's own refusals leave by SystemExit, and must carry 64 too —
    # exit 2 is this program's REFUSED, which a mistyped flag is not.
    calls = fake_gh(view_body="the body as read")
    refusal_code = None
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            body_edit.main(["seven", "--base-body-file", base,
                            "--new-body-file", new, "--repo", "x/y"])
        except SystemExit as refusal:
            refusal_code = refusal.code
    check("a non-numeric issue number is refused with exit 64, not argparse's 2",
          refusal_code == body_edit.EXIT_BAD_INVOCATION and calls == [],
          f"SystemExit({refusal_code}); calls={calls}")

    refusal_code = None
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            body_edit.main(["7", "--base-body-file", base, "--new-body-file", new,
                            "--nonsense"])
        except SystemExit as refusal:
            refusal_code = refusal.code
    check("an unrecognized option is refused with exit 64",
          refusal_code == body_edit.EXIT_BAD_INVOCATION,
          f"SystemExit({refusal_code})")

    refusal_code = None
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            body_edit.main(["7", "--new-body-file", new])
        except SystemExit as refusal:
            refusal_code = refusal.code
    check("omitting the base record altogether is refused with exit 64 — the "
          "check cannot be skipped by leaving it out",
          refusal_code == body_edit.EXIT_BAD_INVOCATION,
          f"SystemExit({refusal_code})")

    # --- a gh failure on the read: exit 1, nothing written ----------------
    calls = fake_gh(view_returncode=1,
                    view_stderr="GraphQL: Could not resolve to an Issue (repository.issue)")
    code, out, err = run_main(["99999", "--base-body-file", base,
                               "--new-body-file", new, "--repo", "x/y"])
    check("a gh read failure (no such issue) exits 1 and makes no edit call",
          code == body_edit.EXIT_FAILED and edit_calls(calls) == [],
          f"exit {code}; calls={calls}; stderr={err!r}")
    check("the read failure passes gh's own words through",
          "Could not resolve to an Issue" in err, err)

    # A gh that never ran at all reports GH_DID_NOT_RUN, which must read as a
    # failure and never as a comparison result.
    calls = fake_gh(view_returncode=body_edit.GH_DID_NOT_RUN,
                    view_stderr="FileNotFoundError: [Errno 2] No such file: 'gh'")
    code, out, err = run_main(["7", "--base-body-file", base,
                               "--new-body-file", new, "--repo", "x/y"])
    check("a gh that never ran exits 1 and makes no edit call",
          code == body_edit.EXIT_FAILED and edit_calls(calls) == [],
          f"exit {code}; calls={calls}; stderr={err!r}")

    # --- unparseable gh output is a clean failure, not a traceback ---------
    calls = fake_gh(view_stdout="not json")
    code, out, err = run_main(["7", "--base-body-file", base,
                               "--new-body-file", new, "--repo", "x/y"])
    check("unparseable gh output exits 1 and makes no edit call",
          code == body_edit.EXIT_FAILED and edit_calls(calls) == [],
          f"exit {code}; calls={calls}; stderr={err!r}")

    calls = fake_gh(view_stdout=json.dumps({"updatedAt": "2026-09-08T21:48:37Z"}))
    code, out, err = run_main(["7", "--base-body-file", base,
                               "--new-body-file", new, "--repo", "x/y"])
    check("a payload with no body field exits 1 rather than comparing against "
          "an invented empty body",
          code == body_edit.EXIT_FAILED and edit_calls(calls) == [],
          f"exit {code}; calls={calls}; stderr={err!r}")

    # --- a gh failure on the edit itself: exit 1, and say so --------------
    base = body_file("base-8.md", "the body as read\n")
    new = body_file("new-8.md", "the body as read, extended\n")
    calls = fake_gh(view_body="the body as read", edit_returncode=1,
                    edit_stderr="HTTP 403: Resource not accessible by integration")
    code, out, err = run_main(["7", "--base-body-file", base,
                               "--new-body-file", new, "--repo", "x/y"])
    check("a gh edit failure exits 1 and says the issue is unchanged",
          code == body_edit.EXIT_FAILED and "unchanged" in err,
          f"exit {code}; stderr={err!r}")
    check("the edit failure passes gh's own words through",
          "HTTP 403" in err, err)

    # --- the repo default is this project's, not a placeholder ------------
    check("the default repo is nedschorus/nedschorus",
          body_edit.DEFAULT_REPO == "nedschorus/nedschorus", body_edit.DEFAULT_REPO)

    # --- normalization, directly -------------------------------------------
    check("normalization strips trailing newlines and folds CRLF and bare CR",
          body_edit.normalized_body("a\r\nb\rc\n\n\n") == "a\nb\nc",
          repr(body_edit.normalized_body("a\r\nb\rc\n\n\n")))
    check("normalization leaves interior blank lines alone",
          body_edit.normalized_body("a\n\nb\n") == "a\n\nb",
          repr(body_edit.normalized_body("a\n\nb\n")))
    check("normalization does not strip leading or trailing spaces on a line, "
          "which are real body content",
          body_edit.normalized_body("  a  \n") == "  a  ",
          repr(body_edit.normalized_body("  a  \n")))


print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
