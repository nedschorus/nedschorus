#!/usr/bin/env python3
"""Tests for merge-lane-ghi-md-edit-pull-requests-provisional-additions-only-check-approve-and-merge.py.

The program is loaded by path and its main() is called in this process, with
a fake `gh` first on PATH, HOME pointing at a scratch home that holds the
merge account's token file, and scratch outputs and review worktrees
directories. The fake `gh` logs every call with the GH_TOKEN it saw and
answers from a routes file the case writes. The program's CHECKOUT is a
clone of a scratch origin repository, so the review tools worktree is made
and moved by real git, and its MERGE_PROGRAM is a fake that logs its
arguments and exits with the code the case writes.

Run: python3 scripts/merge-lane-ghi-md-edit-pull-requests-provisional-additions-only-check-approve-and-merge-test.py
"""

import contextlib
import fcntl
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = Path(__file__).with_name(
    "merge-lane-ghi-md-edit-pull-requests-provisional-additions-only-check-approve-and-merge.py")
_spec = importlib.util.spec_from_file_location("ghi_md_edit_auto_merge", PROGRAM)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)

TOKEN = "ghi-md-edit-auto-merge-test-token-not-a-credential"
HEAD = "b" * 40
NEW_HEAD = "c" * 40
SUBMITTED = "2026-11-07T22:00:00Z"
HEADING = "## Provisional additions (not yet vetted by the user)"
PASSING_DIFF = (
    "diff --git a/docs/issues/9-x.md b/docs/issues/9-x.md\n"
    "--- a/docs/issues/9-x.md\n+++ b/docs/issues/9-x.md\n"
    "@@ -10,0 +11,3 @@\n+\n+" + HEADING + "\n+- an addition\n")
FILE = [{"path": "docs/issues/9-x.md"}]
# The file at HEAD that PASSING_DIFF yields: its lines 11 to 13 are the added ones.
PASSING_FILE_TEXT = "".join(f"line {number}\n" for number in range(1, 11)) + (
    "\n" + HEADING + "\n- an addition\n")

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
directory = os.environ["GHI_MD_AUTO_MERGE_TEST_DIRECTORY"]
argv = sys.argv[1:]
with open(os.path.join(directory, "gh-calls.log"), "a") as log:
    log.write(json.dumps({"argv": argv, "gh_token": os.environ.get("GH_TOKEN")}) + "\n")
routes = json.load(open(os.path.join(directory, "gh-routes.json")))
if argv[:2] == ["pr", "view"]:
    key = f"view {argv[2]} {argv[argv.index('--json') + 1]}"
elif argv[:2] == ["pr", "diff"]:
    key = f"diff {argv[2]}"
elif argv[0] == "api" and "/contents/" in argv[-1]:
    key = "contents"
elif argv[0] == "api":
    key = "api " + argv[3].split("/")[4]
else:
    key = " ".join(argv[:2])
route = routes[key]
if route.get("killed"):
    os.kill(os.getpid(), 9)
sys.stdout.write(route.get("out", ""))
sys.stderr.write(route.get("err", ""))
sys.exit(route.get("exit", 0))
'''

FAKE_MERGE = r'''#!/usr/bin/env python3
import json, os, sys
directory = os.environ["GHI_MD_AUTO_MERGE_TEST_DIRECTORY"]
with open(os.path.join(directory, "merge-calls.log"), "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\n")
print("merge line one\nmerge line two\nmerge program last line", flush=True)
code = int(open(os.path.join(directory, "merge.exit")).read())
if code < 0:
    os.kill(os.getpid(), -code)
sys.exit(code)
'''

failures = []


def check(name, condition, detail=""):
    if not condition:
        failures.append(name)
        print(f"FAIL: {name}\n{detail}")
    else:
        print(f"ok: {name}")


def git(*arguments, cwd=None):
    subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True)


def listed(*entries):
    return json.dumps([{"number": number, "title": title, "headRefOid": head, "isDraft": draft}
                       for number, title, head, draft in entries])


def routes_for(number=9, head=HEAD, files=FILE, diff=PASSING_DIFF, head_after_diff=None,
               review=None, review_exit=0, entries=None, file_text=PASSING_FILE_TEXT,
               contents_exit=0):
    entries = entries if entries is not None else [
        (number, f"GHI-MD edit for issue {number}: a title", head, False)]
    return {
        "pr list": {"out": listed(*entries)},
        f"view {number} files,headRefOid": {"out": json.dumps({"files": files,
                                                                 "headRefOid": head})},
        f"diff {number}": {"out": diff},
        "contents": ({"out": file_text} if contents_exit == 0
                     else {"exit": contents_exit, "err": "HTTP 404"}),
        f"view {number} headRefOid": {"out": json.dumps({"headRefOid": head_after_diff or head})},
        f"api {number}": ({"out": json.dumps(review if review is not None
                                             else {"submitted_at": SUBMITTED})}
                          if review_exit == 0 else {"exit": review_exit, "err": "refused"}),
    }


class Scratch:
    def __init__(self, root, name):
        self.directory = root / name
        self.directory.mkdir()
        self.home = self.directory / "home"
        (self.home / ".config" / "nedschorus").mkdir(parents=True)
        (self.home / ".config" / "nedschorus" / "ned-review-merge.token").write_text(TOKEN + "\n")
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        (self.bin / "gh").write_text(FAKE_GH)
        (self.bin / "gh").chmod(0o755)
        self.merge_program = self.directory / "fake-merge.py"
        self.merge_program.write_text(FAKE_MERGE)
        (self.directory / "merge.exit").write_text("0")
        self.outputs = self.directory / "outputs"
        self.review_worktrees = self.directory / "review-worktrees"
        self.state = self.outputs / "merge-lane-ghi-md-edit-pull-requests-check-approve-and-merge-hold-list-reported-heads-and-needs-a-look-messages"
        self.origin = self.directory / "origin"
        git("init", "-q", "-b", "main", str(self.origin))
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m",
            "one", cwd=self.origin)
        self.checkout = self.directory / "checkout"
        git("clone", "-q", str(self.origin), str(self.checkout))
        self.worktree = self.review_worktrees / "merge-lane-ghi-md-edit-pull-requests-check-approve-and-merge-review-tools-worktree-at-main"

    def routes(self, routes):
        (self.directory / "gh-routes.json").write_text(json.dumps(routes))

    def run(self, extra=(), checkout=None, path_only_fake_bin=False):
        saved = dict(os.environ), program.CHECKOUT, program.MERGE_PROGRAM
        os.environ["HOME"] = str(self.home)
        os.environ["PATH"] = (str(self.bin) if path_only_fake_bin
                              else f"{self.bin}{os.pathsep}{os.environ['PATH']}")
        os.environ["GHI_MD_AUTO_MERGE_TEST_DIRECTORY"] = str(self.directory)
        program.CHECKOUT = checkout or self.checkout
        program.MERGE_PROGRAM = self.merge_program
        printed = io.StringIO()
        try:
            with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(printed):
                code = program.main(["--merge-lane-worktrees-and-outputs-directory",
                                     str(self.outputs), "--merge-lane-review-worktrees-directory",
                                     str(self.review_worktrees), *extra])
        finally:
            os.environ.clear()
            os.environ.update(saved[0])
            program.CHECKOUT, program.MERGE_PROGRAM = saved[1], saved[2]
        return code, printed.getvalue()

    def gh_calls(self):
        log = self.directory / "gh-calls.log"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text().splitlines()]

    def merge_calls(self):
        log = self.directory / "merge-calls.log"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def messages(self):
        directory = self.state / "needs-a-look"
        return sorted(path.name for path in directory.iterdir()) if directory.is_dir() else []

    def message(self, name):
        return (self.state / "needs-a-look" / name).read_text()

    def record(self):
        path = self.state / "reported-nc-head-commits.json"
        return json.loads(path.read_text()) if path.exists() else None


def approvals(scratch):
    return [call["argv"] for call in scratch.gh_calls()
            if call["argv"][0] == "api" and "/contents/" not in call["argv"][-1]]


def main():
    root = Path(tempfile.mkdtemp(prefix="ghi-md-edit-auto-merge-test-"))
    try:
        # --- a passing pull request is approved at its nc-head-commit and merged
        scratch = Scratch(root, "passes")
        scratch.routes(routes_for())
        code, output = scratch.run()
        approval = approvals(scratch)
        merges = scratch.merge_calls()
        check("a pull request that only adds provisional-additions is approved, pinned to its "
              "nc-head-commit, and merged with the approval's time, exit 0",
              code == 0 and len(approval) == 1 and f"commit_id={HEAD}" in approval[0]
              and "event=APPROVE" in approval[0]
              and any(argument.startswith("body=") and "adding a \"Provisional additions"
                      in argument for argument in approval[0])
              and merges and merges[0][:3] == ["9", HEAD, SUBMITTED]
              and "merged: merge program last line" in output and scratch.messages() == [],
              f"exit {code}\n{output}\n{approval}\n{merges}")
        check("the file is read at the nc-head-commit",
              any(call["argv"][-1] == f"repos/nedschorus/nedschorus/contents/docs/issues/9-x.md"
                  f"?ref={HEAD}" for call in scratch.gh_calls()), scratch.gh_calls())
        check("every gh call carries the merge account's token",
              all(call["gh_token"] == TOKEN for call in scratch.gh_calls()), scratch.gh_calls())
        check("the merge runs merge-gate.sh from the program's own review tools worktree, made at "
              "origin/main",
              merges and merges[0][merges[0].index("--review-tools-worktree-at-main") + 1]
              == str(scratch.worktree.resolve())
              and (scratch.worktree / ".git").exists(), merges)

        # --- adding lines to an existing section is approved with the other wording
        scratch = Scratch(root, "existing-section")
        scratch.routes(routes_for(
            diff=PASSING_DIFF.replace("+" + HEADING + "\n", ""),
            file_text="line 1\n" + HEADING + "\n" + "".join(f"line {number}\n"
                                                             for number in range(3, 11))
            + "\n- an addition\n"))
        code, output = scratch.run()
        check("lines added under an existing section are approved with that section's wording",
              code == 0 and any("adding lines to its existing" in argument
                                for argument in approvals(scratch)[0]), f"exit {code}\n{output}")

        # --- each failed condition is reported to merge-lane-2 once per nc-head-commit
        for name, routes, why in (
                ("two-files", routes_for(files=FILE + [{"path": "docs/issues/1-y.md"}]),
                 "changes 2 files"),
                ("outside-docs-issues", routes_for(files=[{"path": "scripts/x.py"}]),
                 "not exactly one under docs/issues/"),
                ("removes-a-line", routes_for(diff=PASSING_DIFF + "-a removed line\n"),
                 "removes 1 lines"),
                ("other-heading", routes_for(diff=PASSING_DIFF + "+## Another heading\n"),
                 "lines starting \"#\" other than the heading"),
                ("new-file", routes_for(diff=PASSING_DIFF.replace("--- a/docs/issues/9-x.md",
                                                                  "--- /dev/null")),
                 "does not change docs/issues/9-x.md in place"),
                ("adds-nothing", routes_for(diff=PASSING_DIFF.split("@@")[0]),
                 "adds no line"),
                ("heading-missing", routes_for(file_text=PASSING_FILE_TEXT.replace(HEADING, "x")),
                 "1 times, not once".replace("1", "0")),
                ("addition-above-the-section", routes_for(
                    diff=PASSING_DIFF.replace("+" + HEADING + "\n", ""),
                    file_text="".join(f"line {number}\n" for number in range(1, 11))
                    + "\n- an addition\n" + HEADING + "\n"),
                 "outside the section"),
                ("addition-under-a-later-heading", routes_for(
                    diff=PASSING_DIFF.replace("+" + HEADING + "\n", ""),
                    file_text="line 1\n" + HEADING + "\nline 3\n## Deferred-decisions\n"
                    + "".join(f"line {number}\n" for number in range(5, 11))
                    + "\n- an addition\n"),
                 "first line 12: '- an addition'")):
            scratch = Scratch(root, name)
            scratch.routes(routes)
            code, output = scratch.run()
            message_name = f"pr9-{HEAD[:12]}.txt"
            check(f"{name}: merge-lane-2 gets one message naming why, nothing is approved or "
                  f"merged, exit 0",
                  code == 0 and scratch.messages() == [message_name]
                  and why in scratch.message(message_name)
                  and "https://github.com/nedschorus/nedschorus/pull/9" in scratch.message(
                      message_name)
                  and approvals(scratch) == [] and scratch.merge_calls() == []
                  and scratch.record() == {"9": HEAD}, f"exit {code}\n{output}")
        handled = scratch.state / "needs-a-look" / "handled"
        check("the message tells merge-lane-2 to move it into needs-a-look/handled/ once read",
              f"Move this file into {handled.resolve()} as soon as you have read it"
              in scratch.message(message_name), scratch.message(message_name))
        calls_before = len(scratch.gh_calls())
        handled.mkdir()
        (scratch.state / "needs-a-look" / message_name).rename(handled / message_name)
        code, output = scratch.run()
        check("a pull request reported at its nc-head-commit, its message moved into handled/, "
              "is not read or reported again",
              code == 0 and scratch.messages() == ["handled"]
              and len(scratch.gh_calls()) == calls_before + 1
              and output == "", f"exit {code}\n{output}")
        scratch.routes(routes_for(head=NEW_HEAD, diff=PASSING_DIFF + "+## Another heading\n"))
        code, output = scratch.run()
        check("a reported pull request with a new nc-head-commit is reported again",
              code == 0 and scratch.messages() == ["handled", f"pr9-{NEW_HEAD[:12]}.txt"]
              and scratch.record() == {"9": NEW_HEAD}, f"exit {code}\n{output}")
        scratch.routes({"pr list": {"out": "[]"}})
        code, output = scratch.run()
        check("a pull request no longer open is dropped from the record",
              code == 0 and scratch.record() == {}, f"exit {code}\n{output}")

        # --- held, draft and other titles are left alone
        scratch = Scratch(root, "held")
        scratch.state.mkdir(parents=True)
        (scratch.state / "held-pull-requests.txt").write_text("# held by merge-lane-2\n\n9\n")
        scratch.routes(routes_for(entries=[(9, "GHI-MD edit for issue 9: t", HEAD, False),
                                           (10, "GHI-MD edit for issue 10: t", HEAD, True),
                                           (11, "GHI-MD for issue 11: t", HEAD, False)]))
        code, output = scratch.run()
        check("a held pull request, a draft and another title are neither read, merged nor "
              "reported",
              code == 0 and [call["argv"][:2] for call in scratch.gh_calls()] == [["pr", "list"]]
              and scratch.messages() == [] and "9 is on the held list" in output,
              f"exit {code}\n{output}")
        (scratch.state / "held-pull-requests.txt").write_text("9\npull request 12\n")
        code, output = scratch.run()
        check("a malformed held list stops the invocation before any gh call, exit 2, and tells "
              "merge-lane-2",
              code == 2 and "line 2 of the held list" in output and len(scratch.gh_calls()) == 1
              and "line 2 of the held list" in scratch.message("invocation-stopped.txt")
              and f"Move this file into {(scratch.state / 'needs-a-look').resolve() / 'handled'} "
              "as soon as "
              in scratch.message("invocation-stopped.txt")
              and "line 2 of the held list" in scratch.message("invocation-stopped.txt")
              .splitlines()[0],
              f"exit {code}\n{output}")
        (scratch.state / "held-pull-requests.txt").unlink()
        (scratch.state / "held-pull-requests.txt").mkdir()
        code, output = scratch.run()
        check("an unreadable held list stops the invocation, exit 2",
              code == 2 and "could not read the held list" in output, f"exit {code}\n{output}")

        # --- a pull request whose nc-head-commit moves while it is read waits
        scratch = Scratch(root, "moved")
        scratch.routes(routes_for(head_after_diff=NEW_HEAD))
        code, output = scratch.run()
        check("a pull request whose nc-head-commit moved while it was read is left for the next "
              "invocation, unapproved and unreported",
              code == 0 and approvals(scratch) == [] and scratch.messages() == []
              and "moved while it was read" in output, f"exit {code}\n{output}")

        # --- approval and merge failures are reported, exit 1
        scratch = Scratch(root, "approval-refused")
        scratch.routes(routes_for(review_exit=1))
        code, output = scratch.run()
        check("a refused approval is reported to merge-lane-2 with gh's error, nothing is merged, "
              "exit 1",
              code == 1 and scratch.merge_calls() == []
              and "its approval failed" in scratch.message(f"pr9-{HEAD[:12]}.txt")
              and "refused" in scratch.message(f"pr9-{HEAD[:12]}.txt"), f"exit {code}\n{output}")
        scratch = Scratch(root, "approval-without-time")
        scratch.routes(routes_for(review={"state": "APPROVED"}))
        code, output = scratch.run()
        check("an approval answer without submitted_at is reported, nothing is merged, exit 1",
              code == 1 and scratch.merge_calls() == []
              and "its approval failed" in scratch.message(f"pr9-{HEAD[:12]}.txt"),
              f"exit {code}\n{output}")
        for merge_exit, outcome in ((1, "not merged"), (2, "not merged"),
                                    (3, "merged, but a step after the merge was not done"),
                                    (4, "not merged"), (-9, "not merged")):
            scratch = Scratch(root, f"merge-exit-{merge_exit}")
            (scratch.directory / "merge.exit").write_text(str(merge_exit))
            scratch.routes(routes_for())
            code, output = scratch.run()
            message = scratch.message(f"pr9-{HEAD[:12]}.txt")
            check(f"a merge program exit {merge_exit} is reported with its last lines, exit 1",
                  code == 1 and f"exited {merge_exit}: {outcome}" in message
                  and "merge line one\nmerge line two\nmerge program last line" in message
                  and scratch.record() == {"9": HEAD}, f"exit {code}\n{output}\n{message}")

        scratch = Scratch(root, "contents-fails")
        scratch.routes(routes_for(contents_exit=1))
        code, output = scratch.run()
        check("a file that cannot be read at the nc-head-commit stops the invocation before any "
              "approval, exit 2",
              code == 2 and approvals(scratch) == [] and "HTTP 404" in output,
              f"exit {code}\n{output}")

        # --- the review tools worktree is moved to origin/main
        scratch = Scratch(root, "worktree-moved")
        scratch.routes(routes_for())
        git("-C", str(scratch.checkout), "worktree", "add", "-q", "--detach",
            str(scratch.worktree), "HEAD")
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m",
            "two", cwd=scratch.origin)
        code, output = scratch.run()
        worktree_head = subprocess.run(["git", "-C", str(scratch.worktree), "rev-parse", "HEAD"],
                                       capture_output=True, text=True).stdout.strip()
        origin_head = subprocess.run(["git", "-C", str(scratch.origin), "rev-parse", "HEAD"],
                                     capture_output=True, text=True).stdout.strip()
        check("an existing review tools worktree is fetched and moved to origin/main before the "
              "merge", code == 0 and worktree_head == origin_head, f"exit {code}\n{output}")
        scratch = Scratch(root, "worktree-fails")
        scratch.routes(routes_for())
        code, output = scratch.run(checkout=scratch.directory / "not-a-checkout")
        check("a review tools worktree that cannot be made stops the invocation before any "
              "approval, exit 2",
              code == 2 and approvals(scratch) == [] and "git -C" in output
              and scratch.messages() == ["invocation-stopped.txt"], f"exit {code}\n{output}")
        scratch = Scratch(root, "worktree-checkout-fails")
        scratch.routes(routes_for())
        scratch.worktree.mkdir(parents=True)
        code, output = scratch.run()
        check("a review tools worktree path that is not a git checkout stops the invocation, exit 2",
              code == 2 and approvals(scratch) == [] and "fetch" in output,
              f"exit {code}\n{output}")

        scratch = Scratch(root, "git-killed")
        scratch.routes(routes_for())
        (scratch.bin / "git").write_text("#!/bin/sh\nkill -9 $$\n")
        (scratch.bin / "git").chmod(0o755)
        code, output = scratch.run()
        check("a git killed by a signal stops the invocation before any approval, exit 2",
              code == 2 and approvals(scratch) == [] and "exited -9" in output,
              f"exit {code}\n{output}")

        # --- failures that stop the invocation
        scratch = Scratch(root, "list-fails")
        scratch.routes({"pr list": {"exit": 1, "err": "HTTP 502"}})
        code, output = scratch.run()
        check("a failed gh pr list stops the invocation with gh's error, exit 2, and tells "
              "merge-lane-2",
              code == 2 and "gh pr list --repo exited 1: HTTP 502" in output
              and "HTTP 502" in scratch.message("invocation-stopped.txt"), f"exit {code}\n{output}")
        scratch.routes({"pr list": {"exit": 1}})
        code, output = scratch.run()
        check("a failed gh that prints no error is named so, exit 2",
              code == 2 and "no error printed" in output, f"exit {code}\n{output}")
        scratch.routes({"pr list": {"killed": True}})
        code, output = scratch.run()
        check("a gh killed by a signal stops the invocation, exit 2",
              code == 2 and "gh pr list --repo exited -9" in output, f"exit {code}\n{output}")
        scratch.routes({"pr list": {"out": "x" * 300}})
        code, output = scratch.run()
        check("gh output that is not JSON stops the invocation, quoting its first 200 "
              "characters, exit 2",
              code == 2 and f"gh pr list --repo printed no JSON: '{'x' * 200}'" in output,
              f"exit {code}\n{output}")
        (scratch.bin / "gh").unlink()
        code, output = scratch.run(path_only_fake_bin=True)
        check("a gh that cannot run stops the invocation, exit 2",
              code == 2 and "gh pr list --repo could not run" in output,
              f"exit {code}\n{output}")

        scratch = Scratch(root, "git-missing")
        scratch.routes(routes_for())
        (scratch.bin / "python3").symlink_to(sys.executable)
        code, output = scratch.run(path_only_fake_bin=True)
        check("a git that cannot run stops the invocation before any approval, exit 2",
              code == 2 and approvals(scratch) == [] and "git -C" in output
              and "could not run" in output, f"exit {code}\n{output}")

        scratch = Scratch(root, "no-token")
        (scratch.home / ".config" / "nedschorus" / "ned-review-merge.token").unlink()
        scratch.routes(routes_for())
        code, output = scratch.run()
        check("a missing token stops the invocation before any gh call, exit 2",
              code == 2 and scratch.gh_calls() == [] and "token" in output,
              f"exit {code}\n{output}")

        scratch = Scratch(root, "bad-record")
        scratch.state.mkdir(parents=True)
        (scratch.state / "reported-nc-head-commits.json").write_text('{"nine": "x"}')
        scratch.routes(routes_for())
        code, output = scratch.run()
        check("a record that is not pull request numbers to nc-head-commits stops the "
              "invocation, exit 2",
              code == 2 and "is not a JSON object" in output and scratch.gh_calls() == [],
              f"exit {code}\n{output}")
        (scratch.state / "reported-nc-head-commits.json").write_text("{")
        code, output = scratch.run()
        check("a record that is not JSON stops the invocation, exit 2",
              code == 2 and "could not read the record" in output, f"exit {code}\n{output}")

        scratch = Scratch(root, "message-unwritable")
        scratch.state.mkdir(parents=True)
        (scratch.state / "needs-a-look").write_text("a file, not a directory")
        scratch.routes(routes_for(files=[{"path": "scripts/x.py"}]))
        code, output = scratch.run()
        check("a message that cannot be written stops the invocation, records nothing, exit 2, "
              "and says the stop message could not be written either",
              code == 2 and "could not write merge-lane-2's message" in output
              and scratch.record() is None
              and "invocation-stopped.txt" in output, f"exit {code}\n{output}")

        scratch = Scratch(root, "record-unwritable")
        scratch.state.mkdir(parents=True)
        (scratch.state / "reported-nc-head-commits.json.being-written").mkdir()
        scratch.routes(routes_for(files=[{"path": "scripts/x.py"}]))
        code, output = scratch.run()
        check("a record that cannot be written stops the invocation, exit 2",
              code == 2 and "could not write the record" in output, f"exit {code}\n{output}")

        scratch = Scratch(root, "lock-held")
        scratch.state.mkdir(parents=True)
        scratch.routes(routes_for())
        with open(scratch.state / ".lock", "a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            code, output = scratch.run()
        check("an invocation that finds the lock held does nothing, exit 0",
              code == 0 and "another invocation holds" in output and scratch.gh_calls() == [],
              f"exit {code}\n{output}")

        scratch = Scratch(root, "lock-unopenable")
        scratch.outputs.mkdir()
        scratch.state.write_text("a file, not a directory")
        code, output = scratch.run()
        check("a lock that cannot be opened stops the invocation, exit 2",
              code == 2 and "could not open the lock" in output, f"exit {code}\n{output}")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
