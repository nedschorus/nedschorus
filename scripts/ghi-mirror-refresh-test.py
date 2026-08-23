#!/usr/bin/env python3
"""Tests for ghi-mirror-refresh.py (nedschorus#46).

`gh` is never invoked for real: every case monkeypatches run_gh with a fake
that returns canned CompletedProcess objects and records the arguments it
was called with, so delta mode's --search cutoff is checked directly rather
than inferred from behavior. Every case runs against a throwaway mirror
directory under a TemporaryDirectory, so nothing here touches a real
checkout or a real GHI corpus.

Run: python3 scripts/ghi-mirror-refresh-test.py
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("ghi-mirror-refresh.py")

_spec = importlib.util.spec_from_file_location("ghi_mirror_refresh", SCRIPT_PATH)
mirror = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mirror)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def patch(monkey_target, value):
    setattr(mirror, monkey_target, value)


def issue(number, title="Untitled", state="OPEN", updated_at="2026-08-01T00:00:00Z",
          labels=None, body="body text", comments=None, state_reason=None,
          closed_at=None):
    return {
        "number": number, "title": title, "state": state,
        "updatedAt": updated_at, "createdAt": updated_at,
        "labels": [{"name": name} for name in (labels or [])],
        "body": body, "comments": comments or [],
        "stateReason": state_reason, "closedAt": closed_at,
        "author": {"login": "someone"},
    }


def fake_gh(calls_log, responses):
    """responses: list of (issues_or_None, error_or_None) popped in call order."""
    def fake_run_gh(arguments, timeout=120):
        calls_log.append(arguments)
        issues, error = responses.pop(0)
        if issues is None:
            return subprocess.CompletedProcess(arguments, 1, "", error or "gh failed")
        return subprocess.CompletedProcess(arguments, 0, json.dumps(issues), "")
    patch("run_gh", fake_run_gh)


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)

    # --- first run: no cache means forced full even without --full --------
    mirror_dir = root / "m1"
    calls = []
    fake_gh(calls, [([issue(1, "First", labels=["draft"]),
                      issue(2, "Second", state="CLOSED", state_reason="COMPLETED",
                            closed_at="2026-08-10T00:00:00Z", updated_at="2026-08-10T00:00:00Z")],
                    None)])
    exit_code = mirror.main(["--mirror-dir", str(mirror_dir), "--repo", "x/y"])
    check("first run (no cache) forces a full fetch with no --search",
          exit_code == 0 and "--search" not in calls[0], calls)

    open_text = (mirror_dir / mirror.OPEN_FILE_NAME).read_text(encoding="utf-8")
    closed_text = (mirror_dir / mirror.CLOSED_FILE_NAME).read_text(encoding="utf-8")
    check("open file carries the open issue, not the closed one",
          "#1 — First" in open_text and "#2" not in open_text, open_text)
    check("open file renders labels",
          "Labels: draft" in open_text, open_text)
    check("closed file carries the closed issue, one line, with reason and date",
          "#2 — Second — closed 2026-08-10 (completed)" in closed_text, closed_text)
    check("closed file excludes the open issue",
          "#1" not in closed_text, closed_text)
    check("no .tmp files left behind after a clean write",
          not list(mirror_dir.glob("*.tmp")), list(mirror_dir.glob("*.tmp")))

    cache = json.loads((mirror_dir / mirror.CACHE_FILE_NAME).read_text(encoding="utf-8"))
    check("cache records the newest updatedAt seen as last_refresh_at",
          cache["last_refresh_at"] == "2026-08-10T00:00:00Z", cache)

    # --- second run: delta mode searches from the cached cutoff ------------
    calls = []
    fake_gh(calls, [([issue(1, "First, edited", labels=["draft"],
                            updated_at="2026-08-15T00:00:00Z")], None)])
    exit_code = mirror.main(["--mirror-dir", str(mirror_dir), "--repo", "x/y"])
    check("second run is a delta: --search updated:> the prior cutoff",
          exit_code == 0
          and any(a == "--search" for a in calls[0])
          and "updated:>2026-08-10T00:00:00Z" in calls[0],
          calls)

    open_text = (mirror_dir / mirror.OPEN_FILE_NAME).read_text(encoding="utf-8")
    closed_text = (mirror_dir / mirror.CLOSED_FILE_NAME).read_text(encoding="utf-8")
    check("delta merge keeps the untouched closed issue from run 1",
          "#2 — Second — closed 2026-08-10 (completed)" in closed_text, closed_text)
    check("delta merge updates the touched issue's rendered title",
          "First, edited" in open_text, open_text)

    # --- state transition: open -> closed disappears from the open file ----
    mirror_dir2 = root / "m2"
    calls = []
    fake_gh(calls, [([issue(9, "Ninth")], None)])
    mirror.main(["--mirror-dir", str(mirror_dir2), "--repo", "x/y"])
    calls = []
    fake_gh(calls, [([issue(9, "Ninth", state="CLOSED", state_reason="NOT_PLANNED",
                            closed_at="2026-08-20T00:00:00Z",
                            updated_at="2026-08-20T00:00:00Z")], None)])
    mirror.main(["--mirror-dir", str(mirror_dir2), "--repo", "x/y"])
    open_text2 = (mirror_dir2 / mirror.OPEN_FILE_NAME).read_text(encoding="utf-8")
    closed_text2 = (mirror_dir2 / mirror.CLOSED_FILE_NAME).read_text(encoding="utf-8")
    check("a closed issue moves out of issues-open.md",
          "#9" not in open_text2, open_text2)
    check("a closed issue moves into issues-closed.md with its reason",
          "#9 — Ninth — closed 2026-08-20 (not_planned)" in closed_text2, closed_text2)

    # --- --full forces a full fetch even with a cache present --------------
    calls = []
    fake_gh(calls, [([issue(9, "Ninth", state="CLOSED", state_reason="NOT_PLANNED",
                            closed_at="2026-08-20T00:00:00Z",
                            updated_at="2026-08-20T00:00:00Z")], None)])
    mirror.main(["--mirror-dir", str(mirror_dir2), "--repo", "x/y", "--full"])
    check("--full omits --search even when a cache exists",
          "--search" not in calls[0], calls)

    # --- full mode purges issues the fetch no longer returns ---------------
    mirror_dir3 = root / "m3"
    calls = []
    fake_gh(calls, [([issue(1, "One"), issue(2, "Two")], None)])
    mirror.main(["--mirror-dir", str(mirror_dir3), "--repo", "x/y"])
    calls = []
    fake_gh(calls, [([issue(1, "One")], None)])  # #2 no longer returned
    mirror.main(["--mirror-dir", str(mirror_dir3), "--repo", "x/y", "--full"])
    open_text3 = (mirror_dir3 / mirror.OPEN_FILE_NAME).read_text(encoding="utf-8")
    check("--full drops an issue the fetch no longer returns",
          "#1" in open_text3 and "#2" not in open_text3, open_text3)

    # --- comments render, with author and body -----------------------------
    mirror_dir4 = root / "m4"
    calls = []
    fake_gh(calls, [([issue(1, "Commented", comments=[
        {"author": {"login": "nedlern"}, "createdAt": "2026-08-05T00:00:00Z",
         "body": "an instance outcome"},
    ])], None)])
    mirror.main(["--mirror-dir", str(mirror_dir4), "--repo", "x/y"])
    open_text4 = (mirror_dir4 / mirror.OPEN_FILE_NAME).read_text(encoding="utf-8")
    check("comments render with author and body",
          "@nedlern" in open_text4 and "an instance outcome" in open_text4, open_text4)

    # --- gh failure: nothing written, exit 1, error on stderr --------------
    mirror_dir5 = root / "m5"
    calls = []
    fake_gh(calls, [(None, "rate limited")])
    exit_code = mirror.main(["--mirror-dir", str(mirror_dir5), "--repo", "x/y"])
    check("a gh failure exits 1 and writes nothing",
          exit_code == 1 and not (mirror_dir5 / mirror.OPEN_FILE_NAME).exists(),
          exit_code)

    # --- unparseable JSON is a clean failure, not a traceback --------------
    mirror_dir6 = root / "m6"
    def fake_run_gh_bad_json(arguments, timeout=120):
        return subprocess.CompletedProcess(arguments, 0, "not json", "")
    patch("run_gh", fake_run_gh_bad_json)
    exit_code = mirror.main(["--mirror-dir", str(mirror_dir6), "--repo", "x/y"])
    check("unparseable gh output exits 1 and writes nothing",
          exit_code == 1 and not (mirror_dir6 / mirror.OPEN_FILE_NAME).exists(),
          exit_code)

    # --- stdout carries exactly one JSON line on success -------------------
    mirror_dir7 = root / "m7"
    calls = []
    fake_gh(calls, [([issue(3, "Three")], None)])
    import io
    import contextlib
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        exit_code = mirror.main(["--mirror-dir", str(mirror_dir7), "--repo", "x/y"])
    stdout_lines = captured.getvalue().splitlines()
    check("stdout is exactly one JSON line describing the run",
          exit_code == 0 and len(stdout_lines) == 1
          and json.loads(stdout_lines[0]).get("changed") == [3],
          stdout_lines)


print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
