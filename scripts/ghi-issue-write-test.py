#!/usr/bin/env python3
"""Tests for ghi-issue-write.py (nedschorus#46).

No issue is ever written: `gh` and the adjudication consult are both
monkeypatched, so nothing here reaches GitHub or ghi-info. The reference
check runs for real against this repository's own origin/main — that is the
one thing worth not stubbing, because the check's whole job is answering
"would a reader be able to open this?", and a stub would only prove the
stub agrees with itself.

Run: python3 scripts/ghi-issue-write-test.py
"""

import contextlib
import importlib.util
import io
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("ghi-issue-write.py")

_spec = importlib.util.spec_from_file_location("ghi_issue_write", SCRIPT_PATH)
writer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(writer)

failures = []

# A path that really is on origin/main, and one that really is not — both
# resolved once here so every case below cites something true.
LANDED_PATH = "docs/issues/46-ghi-info-agent-design.md"
UNLANDED_PATH = "docs/issues/this-path-does-not-exist-on-main.md"


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def stub_gh(returncode=0, stdout="https://github.com/x/y/issues/1\n", stderr=""):
    calls = []

    def fake_run_gh(arguments, timeout=120):
        calls.append(arguments)
        return FakeCompleted(returncode, stdout, stderr)
    writer.run_gh = fake_run_gh
    return calls


def stub_verdict(verdict, error=None):
    calls = []

    def fake_adjudicate(title, body, editing_issue_number, seat_dir, repo,
                        timeout_seconds=None, projects_root=None):
        calls.append({"title": title, "body": body, "editing": editing_issue_number})
        return verdict, error
    writer.ghi_info_ask.adjudicate = fake_adjudicate
    return calls


def run(argv):
    """main() with stdout/stderr captured. Returns (exit_code, out, err)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = writer.main(argv)
    return code, out.getvalue(), err.getvalue()


# --- the reference check, against this repository's real origin/main --------
check("a path that really is on main is not reported missing",
      writer.paths_missing_on_main([LANDED_PATH]) == [], LANDED_PATH)
check("a path that really is not on main is reported missing",
      writer.paths_missing_on_main([UNLANDED_PATH]) == [UNLANDED_PATH], UNLANDED_PATH)
check("a URL containing a repo-shaped path is not treated as a citation",
      writer.cited_in_repo_paths(
          f"see https://github.com/nedschorus/nedschorus/blob/main/{LANDED_PATH}") == [],
      "URL should not be checked as an in-repo path")
check("prose containing a slash is not mistaken for a path",
      writer.cited_in_repo_paths("roughly 3/4 of them, and the docs were fine") == [],
      "fraction should not parse as a path")
check("a cited path keeps its identity through trailing punctuation",
      writer.cited_in_repo_paths(f"Read {LANDED_PATH}, then stop.") == [LANDED_PATH],
      "trailing comma should be stripped")

stub_verdict({"kind": "unrelated", "issues": []})
gh_calls = stub_gh()
code, out, err = run(["create", "--title", "T", "--body",
                      f"This cites {UNLANDED_PATH} which has not landed."])
check("a body citing an unlanded path is REFUSED, and gh is never called",
      code == 1 and not gh_calls, (code, gh_calls))
check("the reference refusal names both ways forward",
      "land the MD first" in err and "add it by edit once the MD lands" in err, err)
check("every refusal ends with the reconsider-to-pass line",
      "reconsider once against its stated reason" in err
      and writer.RECONSIDERED_MARKER_NAME in err, err)

gh_calls = stub_gh()
code, out, err = run(["create", "--title", "T", "--body",
                      f"This cites {LANDED_PATH}, which is on main."])
check("a body citing only landed paths proceeds to the write",
      code == 0 and len(gh_calls) == 1, (code, gh_calls))

# --- adjudication ----------------------------------------------------------
stub_verdict({"kind": "too-similar", "issues": [13]})
gh_calls = stub_gh()
code, out, err = run(["create", "--title", "T", "--body", "plain body"])
check("a too-similar verdict REFUSES and gh is never called",
      code == 1 and not gh_calls, (code, gh_calls))
check("the too-similar refusal names the issue and instructs a merge-by-edit",
      "#13 already covers this ground" in err and "merge this content into it" in err, err)
check("the create case carries no Superseded-by clause (nothing was being edited)",
      "Superseded-by" not in err, err)

gh_calls = stub_gh()
code, out, err = run(["edit", "99", "--body", "plain body"])
check("a too-similar verdict on an EDIT adds the Superseded-by clause for the edited issue",
      code == 1 and "#99, the issue you were editing" in err
      and "Superseded-by: #13" in err, err)

adjudication_calls = stub_verdict({"kind": "related", "issues": [24, 31]})
gh_calls = stub_gh(stdout="https://github.com/x/y/issues/7\n")
code, out, err = run(["create", "--title", "T", "--body", "plain body"])
check("a related verdict lets the write through",
      code == 0 and len(gh_calls) == 1, (code, gh_calls))
check("gh's own output is relayed verbatim, before this tool's lines",
      out.startswith("https://github.com/x/y/issues/7\n"), out)
check("the related note names the issues, after gh's output",
      "Related issues worth knowing: #24, #31." in out, out)

stub_verdict({"kind": "unrelated", "issues": []})
gh_calls = stub_gh()
code, out, err = run(["create", "--title", "T", "--body", "plain body"])
check("an unrelated verdict is a plain pass with no appended note",
      code == 0 and "Related issues" not in out, out)

# Fail-open: every unavailable shape collapses to the same behavior.
for label, verdict, error in [
    ("unreachable ghi-info", None, "the box was silent"),
    ("a prose reply", None, "no usable reply"),
]:
    stub_verdict(verdict, error)
    gh_calls = stub_gh()
    code, out, err = run(["create", "--title", "T", "--body", "plain body"])
    check(f"adjudication unavailable ({label}) FAILS OPEN — the write proceeds",
          code == 0 and len(gh_calls) == 1, (code, gh_calls, err))
    check(f"the unavailable case says so on stderr ({label})",
          "proceeding without adjudication" in err, err)

adjudication_calls = stub_verdict({"kind": "unrelated", "issues": []})
gh_calls = stub_gh()
run(["edit", "42", "--body", "plain body"])
check("an edit tells ghi-info which issue to leave out of the comparison",
      adjudication_calls[0]["editing"] == 42, adjudication_calls)

# --- length ----------------------------------------------------------------
stub_verdict({"kind": "unrelated", "issues": []})
gh_calls = stub_gh()
long_body = "word " * (writer.BODY_WORD_LIMIT + 5)
code, out, err = run(["create", "--title", "T", "--body", long_body])
check("an over-length body still LANDS (measurement instructs, it does not refuse)",
      code == 0 and len(gh_calls) == 1, (code, gh_calls))
check("the over-length instruction names the count and the limit",
      f"This body is {writer.BODY_WORD_LIMIT + 5} words" in out
      and f"the limit is {writer.BODY_WORD_LIMIT}" in out, out)

gh_calls = stub_gh()
code, out, err = run(["create", "--title", "T", "--body", "short body"])
check("a body inside the limit gets no length instruction",
      "the limit is" not in out, out)

# --- delete ----------------------------------------------------------------
gh_calls = stub_gh()
code, out, err = run(["delete", "5"])
check("delete is refused, and gh is never called",
      code == 1 and not gh_calls and "never deleted" in err, (code, gh_calls, err))
check("the delete refusal teaches close-with-reason",
      "completed or not planned" in err, err)

# --- comments: the two catalog events --------------------------------------
gh_calls = stub_gh(stdout="https://github.com/x/y/issues/3#issuecomment-1\n")
code, out, err = run(["comment", "3", "--event-kind", "instance-outcome",
                      "--body", "one run of the recurring process"])
check("a comment naming a catalog event lands through gh",
      code == 0 and len(gh_calls) == 1
      and gh_calls[0][0:3] == ["issue", "comment", "3"], (code, gh_calls))
check("the comment reply points back at the body as governing",
      "The issue body still governs" in out, out)

code, out, err = run(["comment", "3", "--event-kind", "completion", "--body", "x"])
check("an event kind outside the catalog is rejected (completion is not one)",
      code != 0, (code, err))

# A comment is not the body: the reference and length checks do not apply.
gh_calls = stub_gh()
code, out, err = run(["comment", "3", "--event-kind", "ruling-challenge",
                      "--body", f"this challenges the ruling, see {UNLANDED_PATH}"])
check("a comment is not subject to the body's reference check",
      code == 0 and len(gh_calls) == 1, (code, gh_calls, err))

# --- reconsider-to-pass: one marker, exactly one write ---------------------
marker = writer.REPOSITORY_ROOT / writer.RECONSIDERED_MARKER_NAME
assert not marker.exists(), "a stale marker is sitting in the repository root"
try:
    marker.write_text("I reconsidered: the path lands in the same PR.", encoding="utf-8")
    stub_verdict({"kind": "too-similar", "issues": [13]})
    gh_calls = stub_gh()
    code, out, err = run(["create", "--title", "T", "--body",
                          f"cites {UNLANDED_PATH} and duplicates #13"])
    check("a reconsidered marker passes the write past BOTH refusals",
          code == 0 and len(gh_calls) == 1, (code, gh_calls, err))
    check("the marker is consumed by the write it approves",
          not marker.exists(), "marker survived its write")

    gh_calls = stub_gh()
    code, out, err = run(["create", "--title", "T", "--body",
                          f"cites {UNLANDED_PATH} again"])
    check("the next write is refused again — one marker, one write",
          code == 1 and not gh_calls, (code, gh_calls))

    marker.write_text("   ", encoding="utf-8")
    gh_calls = stub_gh()
    code, out, err = run(["create", "--title", "T", "--body", f"cites {UNLANDED_PATH}"])
    check("an empty marker is not an approval",
          code == 1 and not gh_calls, (code, gh_calls))
finally:
    marker.unlink(missing_ok=True)

# --- a gh failure is reported, not dressed up as success -------------------
stub_verdict({"kind": "unrelated", "issues": []})
gh_calls = stub_gh(returncode=1, stdout="", stderr="gh: rate limited\n")
code, out, err = run(["create", "--title", "T", "--body", "plain body"])
check("a failing gh exits 1 and relays gh's own stderr",
      code == 1 and "rate limited" in err, (code, err))
check("no tool lines are appended after a failed write",
      "Related issues" not in out and "the limit is" not in out, out)

# --- body-file --------------------------------------------------------------
stub_verdict({"kind": "unrelated", "issues": []})
gh_calls = stub_gh()
with tempfile.TemporaryDirectory() as temporary:
    body_path = Path(temporary) / "body.md"
    body_path.write_text("body from a file, with `backticks` and $dollars", encoding="utf-8")
    code, out, err = run(["create", "--title", "T", "--body-file", str(body_path)])
    check("--body-file carries the body through untouched",
          code == 0 and "body from a file, with `backticks` and $dollars"
          in gh_calls[0], gh_calls)


print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
