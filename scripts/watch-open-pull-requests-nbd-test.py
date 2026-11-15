#!/usr/bin/env python3
"""Tests for watch-open-pull-requests-nbd.py.

Run: python3 scripts/watch-open-pull-requests-nbd-test.py
Prints one line per case and exits non-zero if any case fails.

No case reaches GitHub. The subprocess cases put a fake `gh` first on the
watcher's PATH: a small script that answers from a control file the test
rewrites between phases, records the GH_TOKEN it was handed, and logs every
call. That fake is what makes the interesting properties testable at all —
a failed query, a query that leaks the token into its own stderr, a
response that is HTTP-fine but GraphQL-broken — and it exercises the real
`gh` invocation path rather than a seam added for the tests. The token the
fixture holds is a string invented here, not a credential.

A reader thread drains the watcher's stdout as it flows, which is also what
proves the flushing: every "a line appears mid-run" wait would hang on a
buffered stdout.

Synchronization without sleeps: the fake `gh` appends to a call log, so a
test can wait for the Nth poll rather than guessing a duration — which is
how "no event for an unchanged poll" is checked (polls demonstrably
happened and produced nothing) and how "the blind line fires once, not once
per failed poll" is checked.

The control file is written temp-then-rename throughout: at a 0.05s poll
interval the fake would otherwise read a half-written file and the suite
would flake.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

WATCH_SCRIPT = Path(__file__).with_name("watch-open-pull-requests-nbd.py")

_spec = importlib.util.spec_from_file_location("watch_open_pull_requests",
                                               WATCH_SCRIPT)
watcher_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watcher_module)

# Invented here, never a credential: long enough to be a plausible token
# (the program refuses shorter ones) and distinctive enough that a leak
# into any output stream is unmistakable.
FIXTURE_TOKEN = "fixture-token-never-a-real-credential-0123456789"

CONTROL_DIRECTORY_VARIABLE = "WATCH_OPEN_PULL_REQUESTS_TEST_CONTROL_DIR"

# Every wait returns as soon as its event happens, so this limit only stops a
# wait whose event never comes. Each poll starts a Python process for the fake
# gh, which takes seconds on a busy ned-box: 10 s failed a correct watcher
# there. 60 s keeps a total failure, every wait timing out, inside the
# runner's 600 s suite limit only because wait_for and wait_for_calls give up
# when the watcher has exited.
EVENT_WAIT_BACKSTOP_SECONDS = 60.0

# The fake gh. It answers from control.json (one file, so a phase change is
# atomic), records the token it was handed, and logs each call. A call
# carrying a `cursor=` argument answers from control-next-page.json instead,
# which is how the pagination case is driven.
FAKE_GH_SOURCE = f'''#!/usr/bin/env python3
import json, os, pathlib, sys

control = pathlib.Path(os.environ["{CONTROL_DIRECTORY_VARIABLE}"])
(control / "token-seen.txt").write_text(os.environ.get("GH_TOKEN", "<unset>"),
                                        encoding="utf-8")
arguments = " ".join(sys.argv[1:])
with (control / "calls.log").open("a", encoding="utf-8") as handle:
    handle.write(("page2" if "cursor=" in arguments else "page1") + "\\n")
name = "control-next-page.json" if "cursor=" in arguments else "control.json"
answer = json.loads((control / name).read_text(encoding="utf-8"))
sys.stdout.write(answer.get("stdout", ""))
sys.stderr.write(answer.get("stderr", ""))
sys.exit(answer.get("exit_code", 0))
'''

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def pull_request_node(number, head_sha, title="a title", draft=False,
                      author="nedlern"):
    return {"number": number, "title": title, "isDraft": draft,
            "headRefOid": head_sha, "author": {"login": author}}


def graphql_body(nodes, has_next_page=False, end_cursor=None):
    return json.dumps({"data": {"repository": {"pullRequests": {
        "nodes": nodes,
        "pageInfo": {"hasNextPage": has_next_page, "endCursor": end_cursor}}}}})


class FakeGitHubCommand:
    """The fake `gh` on disk, plus the control file the tests rewrite."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.binary_directory = directory / "bin"
        self.binary_directory.mkdir(parents=True)
        gh_path = self.binary_directory / "gh"
        gh_path.write_text(FAKE_GH_SOURCE, encoding="utf-8")
        gh_path.chmod(0o755)
        self.answer(graphql_body([]))
        self.answer(graphql_body([]), name="control-next-page.json")

    def answer(self, stdout="", exit_code=0, stderr="",
               name="control.json"):
        """Set what the fake `gh` says next — temp-then-rename, so a poll
        landing mid-write never reads half a file."""
        payload = json.dumps({"stdout": stdout, "exit_code": exit_code,
                              "stderr": stderr})
        temporary = self.directory / (name + ".partial")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(self.directory / name)

    def call_count(self):
        try:
            return len((self.directory / "calls.log")
                       .read_text(encoding="utf-8").splitlines())
        except OSError:
            return 0

    def token_seen(self):
        try:
            return (self.directory / "token-seen.txt").read_text(encoding="utf-8")
        except OSError:
            return None

    def environment(self):
        return {**os.environ,
                "PATH": f"{self.binary_directory}{os.pathsep}{os.environ['PATH']}",
                CONTROL_DIRECTORY_VARIABLE: str(self.directory),
                "PYTHONIOENCODING": "utf-8"}


class WatcherProcess:
    """The watcher as a subprocess, both its streams drained by threads."""

    def __init__(self, *flags, environment=None, token_file=None,
                 needs_a_look_directory=None):
        self.lines = []
        self.error_lines = []
        # The default is merge-lane-2's real notices directory, whose files would be events here.
        if needs_a_look_directory is None:
            needs_a_look_directory = Path(tempfile.gettempdir()) / "no-such-needs-a-look-directory-for-watcher-tests"
        self.process = subprocess.Popen(
            [sys.executable, str(WATCH_SCRIPT),
             "--poll-seconds", "0.05",
             "--token-file", str(token_file),
             "--needs-a-look-directory", str(needs_a_look_directory), *flags],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env=environment)
        self._threads = [
            threading.Thread(target=self._drain, args=(self.process.stdout,
                                                       self.lines), daemon=True),
            threading.Thread(target=self._drain, args=(self.process.stderr,
                                                       self.error_lines),
                             daemon=True)]
        for thread in self._threads:
            thread.start()

    @staticmethod
    def _drain(stream, sink):
        for line in stream:
            sink.append(line.rstrip("\n"))

    def wait_for(self, fragment, timeout=EVENT_WAIT_BACKSTOP_SECONDS):
        """True once some stdout line contains the fragment; False on timeout,
        or once the watcher has exited and its stdout is drained without it."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if any(fragment in line for line in self.lines):
                return True
            if self.process.poll() is not None and not self._threads[0].is_alive():
                return any(fragment in line for line in self.lines)
            time.sleep(0.02)
        return False

    def count(self, fragment):
        return sum(1 for line in self.lines if fragment in line)

    def stop(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        for thread in self._threads:
            thread.join(timeout=2)
        return list(self.lines)


def wait_for_calls(fake_gh, wanted, watcher, timeout=EVENT_WAIT_BACKSTOP_SECONDS):
    """Block until the fake `gh` has been called `wanted` times, and CHECK it.

    Gives up early once the watcher process has exited, since no more calls
    can come.

    This used to return a boolean that every one of its call sites discarded,
    which made the polls it waits for unproven. The damage was not theoretical:
    the cases that read "polls that change nothing produce no further lines"
    passed vacuously, because zero polls also produce no further lines. A fake
    that was never invoked — a broken control-directory variable, a hung child
    — would have timed out here silently and left the suite reporting success
    for a watcher it never ran.

    So the wait now records a failure of its own when it times out. Waiting for
    a count and never checking it is the same defect this whole program exists
    to prevent, one level up: a signal whose absence is indistinguishable from
    the quiet everything-is-fine case.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if fake_gh.call_count() >= wanted:
            return True
        if watcher.process.poll() is not None:
            break
        time.sleep(0.02)
    if fake_gh.call_count() >= wanted:
        return True
    check(f"the fake gh was called at least {wanted} time(s) within {timeout:g}s, "
          "while the watcher ran "
          "— everything asserted after this point depends on those polls",
          False, f"call_count={fake_gh.call_count()}")
    return False


def run_unit_cases():
    # ------------------------------------------------------------------
    # The event key is (number, head sha, is_draft) and nothing else.
    # ------------------------------------------------------------------
    events_for_poll = watcher_module.events_for_poll
    by_number = watcher_module.pull_requests_by_number

    def state(head_sha="aaaaaaaaaaaa", is_draft=False, title="t",
              author="nedlern"):
        return [{"number": 7, "head_sha": head_sha, "title": title,
                 "is_draft": is_draft, "author": author}]

    unchanged = state()
    retitled = state(title="EDITED", author="someone-else")
    moved = state(head_sha="bbbbbbbbbbbb")
    draft = state(is_draft=True)
    draft_moved = state(head_sha="bbbbbbbbbbbb", is_draft=True)

    check("a pull request not seen before is OPENED",
          events_for_poll({}, unchanged) == [
              "PR #7 OPENED aaaaaaaa nedlern: t"],
          str(events_for_poll({}, unchanged)))
    check("the same head sha again is not an event",
          events_for_poll(by_number(unchanged), unchanged) == [], "")
    check("a title or author change alone is not an event",
          events_for_poll(by_number(unchanged), retitled) == [],
          str(events_for_poll(by_number(unchanged), retitled)))
    check("a changed head sha is NEW-HEAD",
          events_for_poll(by_number(unchanged), moved) == [
              "PR #7 NEW-HEAD bbbbbbbb nedlern: t"],
          str(events_for_poll(by_number(unchanged), moved)))
    check("a draft not seen before raises no event",
          events_for_poll({}, draft) == [], str(events_for_poll({}, draft)))
    check("a new head commit on a draft raises no event",
          events_for_poll(by_number(draft), draft_moved) == [],
          str(events_for_poll(by_number(draft), draft_moved)))
    check("a draft marked ready is one READY line",
          events_for_poll(by_number(draft), unchanged) == [
              "PR #7 READY aaaaaaaa nedlern: t"],
          str(events_for_poll(by_number(draft), unchanged)))
    check("a draft marked ready with a moved head is one READY line, "
          "carrying the current head",
          events_for_poll(by_number(draft), moved) == [
              "PR #7 READY bbbbbbbb nedlern: t"],
          str(events_for_poll(by_number(draft), moved)))
    check("a pull request turned back into a draft raises no event",
          events_for_poll(by_number(unchanged), draft) == [],
          str(events_for_poll(by_number(unchanged), draft)))
    baseline_with_draft = watcher_module.baseline_line(
        "o/n", 60, [unchanged[0], {**draft[0], "number": 8}], False)
    check("the baseline line lists a draft apart, as not to be reviewed",
          "1 open at baseline: #7 " in baseline_with_draft
          and "1 draft(s), not to be reviewed until marked ready, which "
              "raises READY: #8" in baseline_with_draft,
          baseline_with_draft)

    # ------------------------------------------------------------------
    # Redaction: every printed line goes through it, so it must replace
    # the token wherever it sits in a line.
    # ------------------------------------------------------------------
    saved_secrets = list(watcher_module.SECRETS_TO_REDACT)
    try:
        watcher_module.SECRETS_TO_REDACT[:] = [FIXTURE_TOKEN]
        redacted = watcher_module.redact_secrets(
            f"gh said: Authorization: Bearer {FIXTURE_TOKEN} (twice: "
            f"{FIXTURE_TOKEN})")
        check("redaction replaces every occurrence of the token",
              FIXTURE_TOKEN not in redacted and redacted.count("[REDACTED]") == 2,
              redacted)
    finally:
        watcher_module.SECRETS_TO_REDACT[:] = saved_secrets

    # ------------------------------------------------------------------
    # A node that is not the shape the query asked for fails the poll,
    # rather than being dropped — a dropped pull request would be
    # reported as OPENED again at the next poll.
    # ------------------------------------------------------------------
    from_node = watcher_module.pull_request_from_node
    check("pull_request_from_node reports a missing head sha as a reason",
          from_node({"number": 3, "title": "t"})[0] is None
          and "head commit sha" in from_node({"number": 3, "title": "t"})[1],
          str(from_node({"number": 3, "title": "t"})))
    check("pull_request_from_node reports a node that is not an object",
          from_node([1, 2]) == (None, "a pull request came back as JSON that is not an object"),
          str(from_node([1, 2])))

    # The case above tests the HELPER. The property that matters is the
    # CALLER's: fetch_open_pull_requests must return the failure rather than
    # skip the node. Nothing asserted that until now, and the gap was not
    # cosmetic — changing the caller's `return None, reason` to `continue`
    # left the entire suite passing, while producing exactly the behaviour the
    # program's docstring calls wrong: the dropped pull request would be
    # re-reported as OPENED at every poll, forever.
    class FakeCompletedProcess:
        def __init__(self, stdout):
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ""

    saved_run_gh = watcher_module.run_gh
    try:
        watcher_module.run_gh = lambda *_a, **_k: FakeCompletedProcess(
            graphql_body([pull_request_node(3, "c" * 12),
                          {"number": 4, "title": "malformed"}]))
        fetched, reason = watcher_module.fetch_open_pull_requests("o/n", "tok")
        check("one malformed node fails the whole poll, dropping nothing",
              fetched is None and reason is not None and "head commit sha" in reason,
              f"fetched={fetched!r} reason={reason!r}")

        # Proves the harness above can succeed, so the case before it is a
        # real refusal rather than a fake that never worked.
        watcher_module.run_gh = lambda *_a, **_k: FakeCompletedProcess(
            graphql_body([pull_request_node(3, "c" * 12)]))
        fetched, reason = watcher_module.fetch_open_pull_requests("o/n", "tok")
        check("the same harness with only well-formed nodes returns them",
              reason is None and fetched is not None and len(fetched) == 1
              and fetched[0]["number"] == 3,
              f"fetched={fetched!r} reason={reason!r}")
    finally:
        watcher_module.run_gh = saved_run_gh
    check("a deleted author becomes (unknown), not a crash",
          from_node(pull_request_node(3, "cccccccccccc"))[0] is not None
          and from_node({"number": 3, "headRefOid": "c" * 12,
                         "author": None})[0]["author"] == "(unknown)",
          str(from_node({"number": 3, "headRefOid": "c" * 12, "author": None})))

    # ------------------------------------------------------------------
    # Titles are folded then truncated, so a multi-line title cannot
    # break the one-line-per-event contract.
    # ------------------------------------------------------------------
    folded = watcher_module.event_line(
        {"number": 9, "head_sha": "d" * 40, "title": "first\nsecond",
         "is_draft": False, "author": "nedlern"}, "OPENED")
    check("a newline in a title becomes ' ¶ ', keeping one line per event",
          folded == "PR #9 OPENED dddddddd nedlern: first ¶ second", folded)
    long_title = "T" * (watcher_module.TITLE_SNIPPET_CHARS + 50)
    long_line = watcher_module.event_line(
        {"number": 9, "head_sha": "d" * 40, "title": long_title,
         "is_draft": False, "author": "nedlern"}, "OPENED")
    check("a long title is truncated to the documented length",
          long_line.endswith("T" * watcher_module.TITLE_SNIPPET_CHARS)
          and "T" * (watcher_module.TITLE_SNIPPET_CHARS + 1) not in long_line,
          str(len(long_line)))

    # ------------------------------------------------------------------
    # The token file: refused at startup rather than half-trusted.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch:
        short_token_file = Path(scratch) / "short.token"
        short_token_file.write_text("abc\n", encoding="utf-8")
        token, reason = watcher_module.read_token(short_token_file)
        check("a too-short token file is refused (it would corrupt redaction)",
              token is None and "not a GitHub token" in reason, str(reason))
        missing = Path(scratch) / "absent.token"
        token, reason = watcher_module.read_token(missing)
        check("a missing token file is refused, and the reason names the path",
              token is None and str(missing) in reason, str(reason))
        good = Path(scratch) / "good.token"
        good.write_text(FIXTURE_TOKEN + "\n", encoding="utf-8")
        check("the token is read with its trailing newline stripped",
              watcher_module.read_token(good) == (FIXTURE_TOKEN, None),
              str(watcher_module.read_token(good)))


def run_needs_a_look_unit_cases():
    events = watcher_module.needs_a_look_events
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        directory = scratch / "needs-a-look"
        state = {}
        check("a notices directory that does not exist yet raises nothing",
              events(directory, state) == [], str(state))

        directory.mkdir()
        (directory / "pr9-bbbbbbbbbbbb.txt").write_text(
            "GHI-MD edit pull request 9 needs a look: https://x/pull/9\nTitle: t\n",
            encoding="utf-8")
        (directory / "handled").mkdir()
        (directory / "handled" / "pr8-aaaaaaaaaaaa.txt").write_text("old\n", encoding="utf-8")
        (directory / "dangling.txt").symlink_to(scratch / "no-such-file")
        lines = events(directory, state)
        handled = directory / "handled"
        check("a notice present at the first listing is one NEEDS A LOOK line with its first "
              "line and the move that marks it handled; handled/ and a dangling link raise nothing",
              lines == [f"NEEDS A LOOK pr9-bbbbbbbbbbbb.txt: GHI-MD edit pull request 9 needs a "
                        f"look: https://x/pull/9 -- read {directory / 'pr9-bbbbbbbbbbbb.txt'}, "
                        f"then at once, before acting on it, move it, or each restart of this "
                        f"watcher reports it again first: mkdir -p {handled} && mv "
                        f"{directory / 'pr9-bbbbbbbbbbbb.txt'} {handled}/"], "\n".join(lines))
        check("the same notice, unchanged, is not reported again",
              events(directory, state) == [], str(state))

        stopped = directory / "invocation-stopped.txt"
        stopped.write_text("stopped once\n", encoding="utf-8")
        os.utime(stopped, ns=(1, 1))
        first = events(directory, state)
        stopped.write_text("stopped again\n", encoding="utf-8")
        os.utime(stopped, ns=(2, 2))
        second = events(directory, state)
        check("a notice replaced by a later write is reported again",
              len(first) == 1 and "stopped once" in first[0]
              and len(second) == 1 and "stopped again" in second[0], f"{first}\n{second}")

        notice = directory / "pr9-bbbbbbbbbbbb.txt"
        saved_status = notice.stat()
        notice.rename(handled / notice.name)
        events(directory, state)
        (handled / notice.name).rename(notice)
        os.utime(notice, ns=(saved_status.st_atime_ns, saved_status.st_mtime_ns + 1))
        check("a notice that leaves the directory and comes back is reported again",
              len(events(directory, state)) == 1, str(state))
        saved_status = notice.stat()
        notice.rename(handled / notice.name)
        events(directory, state)
        (handled / notice.name).rename(notice)
        os.utime(notice, ns=(saved_status.st_atime_ns, saved_status.st_mtime_ns))
        check("a notice that a poll found missing is reported again when it comes back with "
              "the same modification time",
              len(events(directory, state)) == 1, str(state))

        looping = directory / "looping.txt"
        looping.symlink_to(looping)
        first = events(directory, state)
        second = events(directory, state)
        looping.unlink()
        check("an entry whose status cannot be read, other than a dangling link, is one NEEDS A "
              "LOOK line naming the error, not repeated while it stays so",
              first == [f"NEEDS A LOOK looping.txt: (could not read its status: Too many levels "
                        f"of symbolic links) -- look at {looping}"]
              and second == [], f"{first}\n{second}")

        empty = directory / "empty.txt"
        empty.write_text("", encoding="utf-8")
        check("an empty notice is reported as an empty file",
              any("NEEDS A LOOK empty.txt: (empty file)" in line
                  for line in events(directory, state)), str(state))

        unreadable = directory / "unreadable.txt"
        unreadable.write_text("secret\n", encoding="utf-8")
        unreadable.chmod(0)
        lines = events(directory, state)
        unreadable.chmod(0o600)
        check("a notice that cannot be read is reported with the error in place of its first line",
              len(lines) == 1 and lines[0].startswith(
                  "NEEDS A LOOK unreadable.txt: (could not read it: Permission denied)"),
              "\n".join(lines))

        not_a_directory = scratch / "a-file"
        not_a_directory.write_text("", encoding="utf-8")
        first = events(not_a_directory, state)
        second = events(not_a_directory, state)
        check("a notices directory that cannot be listed is one NEEDS A LOOK line naming it, "
              "not repeated while it stays unlistable",
              first == [f"NEEDS A LOOK: cannot list the GHI-MD edit job's notices in "
                        f"{not_a_directory}: Not a directory; notices there go unreported "
                        f"until it can be listed"]
              and second == [], f"{first}\n{second}")
        events(directory, state)
        again = events(not_a_directory, state)
        check("it is reported again after a listing succeeds in between",
              len(again) == 1, str(again))
        events(not_a_directory, state)
        events(scratch / "missing", state)
        check("a missing directory between two unlistable ones also lets the second be reported",
              len(events(not_a_directory, state)) == 1, str(state))

    job = watcher_module.ghi_md_edit_job
    check("the watcher's default notices directory is the one the GHI-MD edit job writes",
          watcher_module.parse_arguments([]).needs_a_look_directory
          == job.needs_a_look_directory()
          == job.common.DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY
          / job.STATE_DIRECTORY_NAME / "needs-a-look", "")


def run_bad_invocation_cases(token_file, missing_token_file):
    """Bad invocations exit 2 with one stderr line, before any query."""
    for flags, label in [
            (["--poll-seconds", "0"], "--poll-seconds 0"),
            (["--poll-seconds", "-1"], "--poll-seconds -1"),
            (["--repo", "no-slash"], "--repo no-slash"),
            (["--repo", "a/b/c"], "--repo a/b/c")]:
        try:
            result = subprocess.run(
                [sys.executable, str(WATCH_SCRIPT),
                 "--token-file", str(token_file), *flags],
                capture_output=True, text=True, timeout=EVENT_WAIT_BACKSTOP_SECONDS)
            ok = (result.returncode == 2
                  and len(result.stderr.strip().splitlines()) == 1)
            detail = f"rc={result.returncode} stderr={result.stderr!r}"
        except subprocess.TimeoutExpired:
            ok, detail = False, (f"still running after {EVENT_WAIT_BACKSTOP_SECONDS:g}s"
                                  " — validation never fired")
        check(f"bad invocation {label} exits 2 with one stderr line", ok, detail)

    result = subprocess.run(
        [sys.executable, str(WATCH_SCRIPT),
         "--token-file", str(missing_token_file)],
        capture_output=True, text=True, timeout=EVENT_WAIT_BACKSTOP_SECONDS)
    check("an unreadable token file exits 2 and names the path",
          result.returncode == 2 and str(missing_token_file) in result.stderr,
          f"rc={result.returncode} stderr={result.stderr!r}")


def run_subprocess_cases():
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        token_file = scratch / "fixture.token"
        token_file.write_text(FIXTURE_TOKEN + "\n", encoding="utf-8")

        run_bad_invocation_cases(token_file, scratch / "no-such.token")

        # ------------------------------------------------------------------
        # The main sequence, one watcher across every phase: baseline is
        # silent, a new pull request is an event, a moved head is an event,
        # an unchanged poll is not, a title edit is not.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "sequence")
        fake_gh.answer(graphql_body([pull_request_node(145, "a" * 40,
                                                       "already open")]))
        watcher = WatcherProcess(environment=fake_gh.environment(),
                                 token_file=token_file)
        baseline = watcher.wait_for("WATCH: watching nedschorus/nedschorus "
                                    "every 0.05s; 1 open at baseline: #145")
        check("the first poll prints a baseline line naming what is open",
              baseline, "\n".join(watcher.lines))

        wait_for_calls(fake_gh, 4, watcher)
        check("a pull request open at the first poll is not an event",
              watcher.count("PR #145") == 0, "\n".join(watcher.lines))

        check("the credential reaches gh through the environment",
              fake_gh.token_seen() == FIXTURE_TOKEN,
              repr(fake_gh.token_seen()))

        fake_gh.answer(graphql_body([
            pull_request_node(145, "a" * 40, "already open"),
            pull_request_node(146, "b" * 40, "newly opened")]))
        opened = watcher.wait_for("PR #146 OPENED bbbbbbbb nedlern: "
                                  "newly opened")
        check("a newly opened pull request is one OPENED line", opened,
              "\n".join(watcher.lines))

        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4, watcher)
        check("polls that change nothing produce no further lines",
              watcher.count("PR #146") == 1 and watcher.count("PR #145") == 0,
              "\n".join(watcher.lines))

        # A title edit on both pull requests, no head movement.
        fake_gh.answer(graphql_body([
            pull_request_node(145, "a" * 40, "RETITLED 145"),
            pull_request_node(146, "b" * 40, "RETITLED 146")]))
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4, watcher)
        check("a changed title is not an event",
              "RETITLED" not in "\n".join(watcher.lines), "\n".join(watcher.lines))

        # A new head commit on 146 only.
        fake_gh.answer(graphql_body([
            pull_request_node(145, "a" * 40, "RETITLED 145"),
            pull_request_node(146, "c" * 40, "RETITLED 146")]))
        moved = watcher.wait_for("PR #146 NEW-HEAD cccccccc")
        check("a new head commit on an open pull request is one NEW-HEAD line",
              moved and watcher.count("PR #146 NEW-HEAD") == 1,
              "\n".join(watcher.lines))
        check("the pull request whose head did not move stays silent",
              watcher.count("PR #145") == 0, "\n".join(watcher.lines))

        # A closed pull request that reopens is announced again — the
        # documented choice, since the seat must look at it again.
        fake_gh.answer(graphql_body([pull_request_node(146, "c" * 40,
                                                       "RETITLED 146")]))
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 3, watcher)
        fake_gh.answer(graphql_body([
            pull_request_node(145, "a" * 40, "reopened"),
            pull_request_node(146, "c" * 40, "RETITLED 146")]))
        reopened = watcher.wait_for("PR #145 OPENED aaaaaaaa nedlern: reopened")
        lines = watcher.stop()
        check("a pull request that closes and reopens is announced again",
              reopened, "\n".join(lines))
        check("closing a pull request is not itself announced",
              not any("CLOSED" in line for line in lines), "\n".join(lines))

        # ------------------------------------------------------------------
        # Drafts: one open at baseline and one opened later raise nothing,
        # nor does a new head commit on a draft; each raises one READY line
        # when marked ready, and nothing more after.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "drafts")
        fake_gh.answer(graphql_body([
            pull_request_node(170, "a" * 40, "draft at baseline", draft=True)]))
        watcher = WatcherProcess(environment=fake_gh.environment(),
                                 token_file=token_file)
        baseline = watcher.wait_for("0 open at baseline")
        check("a draft at baseline is listed apart in the baseline line",
              baseline and any("not to be reviewed until marked ready"
                               in line and "#170" in line
                               for line in watcher.lines),
              "\n".join(watcher.lines))
        fake_gh.answer(graphql_body([
            pull_request_node(170, "a" * 40, "draft at baseline", draft=True),
            pull_request_node(171, "b" * 40, "opened as a draft", draft=True)]))
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4, watcher)
        check("a pull request opened as a draft raises no line",
              watcher.count("PR #171") == 0, "\n".join(watcher.lines))
        fake_gh.answer(graphql_body([
            pull_request_node(170, "a" * 40, "draft at baseline", draft=True),
            pull_request_node(171, "c" * 40, "opened as a draft", draft=True)]))
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4, watcher)
        check("a new head commit on a draft raises no line",
              watcher.count("PR #171") == 0, "\n".join(watcher.lines))
        fake_gh.answer(graphql_body([
            pull_request_node(170, "a" * 40, "draft at baseline"),
            pull_request_node(171, "c" * 40, "opened as a draft")]))
        ready_baseline = watcher.wait_for("PR #170 READY aaaaaaaa nedlern: "
                                          "draft at baseline")
        ready_later = watcher.wait_for("PR #171 READY cccccccc nedlern: "
                                       "opened as a draft")
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4, watcher)
        lines = watcher.stop()
        check("a draft open at baseline and marked ready is one READY line",
              ready_baseline and watcher.count("PR #170") == 1,
              "\n".join(lines))
        check("a draft opened later and marked ready is one READY line, "
              "carrying the current head",
              ready_later and watcher.count("PR #171") == 1, "\n".join(lines))

        # ------------------------------------------------------------------
        # --exit-after-first-poll-with-events does not exit for a draft, and
        # does exit for the draft marked ready.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "exit-on-ready")
        fake_gh.answer(graphql_body([]))
        watcher = WatcherProcess("--exit-after-first-poll-with-events",
                                 environment=fake_gh.environment(),
                                 token_file=token_file)
        watcher.wait_for("0 open at baseline")
        fake_gh.answer(graphql_body([
            pull_request_node(172, "d" * 40, "a draft", draft=True)]))
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4, watcher)
        check("--exit-after-first-poll-with-events keeps polling when only a "
              "draft opened",
              watcher.process.poll() is None and watcher.count("PR #172") == 0,
              "\n".join(watcher.lines))
        fake_gh.answer(graphql_body([
            pull_request_node(172, "d" * 40, "a draft")]))
        try:
            exit_code = watcher.process.wait(timeout=EVENT_WAIT_BACKSTOP_SECONDS)
        except subprocess.TimeoutExpired:
            exit_code = None
        lines = watcher.stop()
        check("--exit-after-first-poll-with-events exits 0 on a draft marked "
              "ready, printing its READY line",
              exit_code == 0
              and any("PR #172 READY dddddddd" in line for line in lines),
              f"exit {exit_code}\n" + "\n".join(lines))

        # ------------------------------------------------------------------
        # --exit-after-first-poll-with-events: polls on through a silent baseline, then
        # prints every event of the first poll that has one and exits 0.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "exit-after-first-poll-with-events")
        fake_gh.answer(graphql_body([pull_request_node(145, "a" * 40, "open")]))
        watcher = WatcherProcess("--exit-after-first-poll-with-events",
                                 environment=fake_gh.environment(),
                                 token_file=token_file)
        wait_for_calls(fake_gh, 3, watcher)
        check("--exit-after-first-poll-with-events keeps polling while no event comes",
              watcher.process.poll() is None, "\n".join(watcher.lines))
        fake_gh.answer(graphql_body([
            pull_request_node(145, "d" * 40, "open"),
            pull_request_node(147, "e" * 40, "opened with the move")]))
        try:
            exit_code = watcher.process.wait(timeout=EVENT_WAIT_BACKSTOP_SECONDS)
        except subprocess.TimeoutExpired:
            exit_code = None
        lines = watcher.stop()
        check("--exit-after-first-poll-with-events exits 0 after the first poll with an event",
              exit_code == 0, f"exit {exit_code}\n" + "\n".join(lines))
        check("--exit-after-first-poll-with-events prints every event of that poll",
              any("PR #145 NEW-HEAD dddddddd" in line for line in lines)
              and any("PR #147 OPENED eeeeeeee" in line for line in lines),
              "\n".join(lines))

        # ------------------------------------------------------------------
        # Blindness: announced once, recovery announced, and no event lost
        # while blind.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "blindness")
        fake_gh.answer(graphql_body([pull_request_node(145, "a" * 40, "open")]))
        watcher = WatcherProcess(environment=fake_gh.environment(),
                                 token_file=token_file)
        watcher.wait_for("1 open at baseline")

        fake_gh.answer(stdout="", exit_code=1,
                       stderr="gh: HTTP 503 Service Unavailable")
        blind = watcher.wait_for("WATCH: query failed")
        check("a failed query announces the watch is blind, in plain words",
              blind and any("BLIND until it recovers" in line
                            and "HTTP 503" in line for line in watcher.lines),
              "\n".join(watcher.lines))
        # The blind line promises to FLAG what the blindness cost, and that
        # verb is load-bearing. An earlier wording promised the recovery line
        # would say "what was and was not captured"; with a baseline the
        # recovery line reports only counts and duration, so a reader had to
        # take the ABSENCE of a loss clause as the reassurance — the
        # absence-as-signal shape this program exists to avoid. A promise to
        # flag is kept by saying nothing when nothing was lost, which is what
        # the pair of checks here and after recovery pins.
        check("the blind line promises to flag what the blindness cost",
              any("BLIND until it recovers" in line
                  and "flags anything the blindness cost" in line
                  for line in watcher.lines),
              "\n".join(watcher.lines))

        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 5, watcher)
        check("the blind line is printed once per episode, not once per poll",
              watcher.count("WATCH: query failed") == 1,
              "\n".join(watcher.lines))

        # A pull request opens while the watch is blind; the head of the
        # one already known moves at the same time.
        fake_gh.answer(graphql_body([
            pull_request_node(145, "z" * 40, "open"),
            pull_request_node(150, "d" * 40, "opened while blind")]))
        recovered = watcher.wait_for("WATCH: query recovered after ")
        missed_open = watcher.wait_for("PR #150 OPENED dddddddd nedlern: "
                                       "opened while blind")
        missed_move = watcher.wait_for("PR #145 NEW-HEAD zzzzzzzz")
        lines = watcher.stop()
        check("recovery is announced, with how many polls failed", recovered,
              "\n".join(lines))
        check("a pull request opened while blind is reported on recovery",
              missed_open, "\n".join(lines))
        # The other half of the flagging promise: a baseline existed, so
        # nothing was lost, so the recovery line flags nothing — and the
        # events it delayed arrive right behind it. Silence here is the
        # promise being kept, not the promise going unmet.
        check("with a baseline, the recovery line flags no loss",
              all("NO BASELINE" not in line
                  for line in lines if "query recovered" in line),
              "\n".join(lines))
        check("a head that moved while blind is reported on recovery",
              missed_move, "\n".join(lines))
        check("the recovery line comes before the events it delayed",
              [index for index, line in enumerate(lines)
               if "query recovered" in line][0]
              < [index for index, line in enumerate(lines)
                 if "PR #150 OPENED" in line][0],
              "\n".join(lines))

        # ------------------------------------------------------------------
        # Blindness BEFORE the first successful poll is the case the block
        # above does not cover, and the one the program used to describe
        # wrongly. With no baseline there is nothing to compare against, so a
        # pull request that opened during the outage is indistinguishable from
        # one that was open all along: it is absorbed into the baseline and
        # gets no OPENED line. That is unavoidable. What is not unavoidable is
        # a recovery line that reads exactly like the recoverable case — an
        # agent following the stated contract would see recovery, see no
        # events, and conclude nothing had opened. Seat boot is when a first
        # poll is likeliest to fail, so this is the common blind episode.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "blind-before-baseline")
        fake_gh.answer(stdout="", exit_code=1,
                       stderr="gh: HTTP 503 Service Unavailable")
        watcher = WatcherProcess(environment=fake_gh.environment(),
                                 token_file=token_file)
        watcher.wait_for("WATCH: query failed")
        fake_gh.answer(graphql_body([
            pull_request_node(160, "e" * 40, "opened before any baseline"),
            pull_request_node(161, "f" * 40, "also opened before any baseline")]))
        recovered = watcher.wait_for("WATCH: query recovered after ")
        watcher.wait_for("open at baseline")
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 3, watcher)
        lines = watcher.stop()
        check("recovering with no baseline says the openings are absorbed",
              recovered and any("query recovered" in line and "NO BASELINE" in line
                                for line in lines),
              "\n".join(lines))
        check("and it does not silently claim those pull requests as events",
              not any("PR #160 OPENED" in line or "PR #161 OPENED" in line
                      for line in lines),
              "\n".join(lines))

        # ------------------------------------------------------------------
        # The same blind-before-baseline episode under --from-start, where the
        # absorption does not happen: the baseline is seeded empty, so every
        # open pull request IS emitted as OPENED. Announcing a loss here would
        # be the block above's defect pointing the other way — an agent
        # reading the stream by its stated contract would believe it had
        # missed openings it actually received, and the remedy the line offers
        # is the flag it is already running under.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "blind-before-baseline-from-start")
        fake_gh.answer(stdout="", exit_code=1,
                       stderr="gh: HTTP 503 Service Unavailable")
        watcher = WatcherProcess("--from-start",
                                 environment=fake_gh.environment(),
                                 token_file=token_file)
        watcher.wait_for("WATCH: query failed")
        fake_gh.answer(graphql_body([
            pull_request_node(160, "e" * 40, "opened before any baseline"),
            pull_request_node(161, "f" * 40, "also opened before any baseline")]))
        watcher.wait_for("WATCH: query recovered after ")
        watcher.wait_for("PR #161 OPENED")
        lines = watcher.stop()
        recovery = [line for line in lines if "query recovered" in line]
        check("--from-start recovery does not claim the openings were absorbed",
              bool(recovery) and "NO BASELINE" not in recovery[0],
              "\n".join(lines))
        check("--from-start recovery does not recommend the flag already in use",
              bool(recovery) and "--from-start" not in recovery[0],
              "\n".join(lines))
        check("and both pull requests really were reported as OPENED, which is "
              "what makes the absorption claim false here",
              any("PR #160 OPENED" in line for line in lines)
              and any("PR #161 OPENED" in line for line in lines),
              "\n".join(lines))

        # ------------------------------------------------------------------
        # The credential never reaches any output stream, including the
        # failure path that quotes gh's own stderr back.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "leak")
        fake_gh.answer(
            stdout="", exit_code=1,
            stderr=f"gh: request failed: Authorization: Bearer {FIXTURE_TOKEN}")
        watcher = WatcherProcess(environment=fake_gh.environment(),
                                 token_file=token_file)
        blind = watcher.wait_for("WATCH: query failed")
        fake_gh.answer(graphql_body([]))
        watcher.wait_for("WATCH: query recovered")
        lines = watcher.stop()
        everything = "\n".join(lines + watcher.error_lines)
        check("gh's stderr is quoted back, so the failure is diagnosable",
              blind and "request failed" in everything, everything)
        check("the token never reaches stdout or stderr, even quoting gh",
              FIXTURE_TOKEN not in everything and "[REDACTED]" in everything,
              everything)
        check("the fake gh was nonetheless handed the real fixture token",
              fake_gh.token_seen() == FIXTURE_TOKEN,
              repr(fake_gh.token_seen()))

        # ------------------------------------------------------------------
        # The same guarantee when gh's stderr is long enough that the snippet's
        # length cut falls INSIDE the token. Redaction replaces whole
        # occurrences, so a cut taken before redaction leaves an unmatchable
        # prefix on the line. The case above cannot catch that: its stderr is
        # shorter than the cut, so the token is never bisected. Measured
        # before the fix — 20 of the token's characters printed, no [REDACTED]
        # in the line.
        # ------------------------------------------------------------------
        cut = watcher_module.FAILURE_REASON_SNIPPET_CHARS
        surviving_characters = 20
        opening = "gh: request failed: "
        bisecting_stderr = (opening
                            + "x" * (cut - surviving_characters - len(opening))
                            + FIXTURE_TOKEN)
        check("the fixture stderr really does straddle the cut, or this case "
              "proves nothing",
              bisecting_stderr.index(FIXTURE_TOKEN) < cut < len(bisecting_stderr),
              f"token at {bisecting_stderr.index(FIXTURE_TOKEN)}, "
              f"cut at {cut}, reason length {len(bisecting_stderr)}")
        fake_gh = FakeGitHubCommand(scratch / "leak-across-the-cut")
        fake_gh.answer(stdout="", exit_code=1, stderr=bisecting_stderr)
        watcher = WatcherProcess(environment=fake_gh.environment(),
                                 token_file=token_file)
        watcher.wait_for("WATCH: query failed")
        fake_gh.answer(graphql_body([]))
        watcher.wait_for("WATCH: query recovered")
        lines = watcher.stop()
        everything = "\n".join(lines + watcher.error_lines)
        check("a token bisected by the length cut leaves no surviving prefix",
              FIXTURE_TOKEN[:surviving_characters] not in everything,
              everything)
        check("and the whole token is absent from a bisected line too",
              FIXTURE_TOKEN not in everything, everything)

        # ------------------------------------------------------------------
        # Answers that are not a failed exit status: a GraphQL error beside
        # a partial body (HTTP 200), and output that is not JSON at all.
        # Both are failures, and neither may reach the compared state.
        # ------------------------------------------------------------------
        for label, answer, expected_fragment in [
                ("a GraphQL error beside a partial body",
                 json.dumps({"data": {"repository": None},
                             "errors": [{"message": "Could not resolve to a "
                                                    "Repository"}]}),
                 "Could not resolve"),
                ("output that is not JSON",
                 "gh printed something else entirely",
                 "unparseable JSON")]:
            fake_gh = FakeGitHubCommand(scratch / f"answer-{len(label)}")
            fake_gh.answer(graphql_body([pull_request_node(145, "a" * 40,
                                                           "open")]))
            watcher = WatcherProcess(environment=fake_gh.environment(),
                                     token_file=token_file)
            watcher.wait_for("1 open at baseline")
            fake_gh.answer(stdout=answer, exit_code=0)
            blind = watcher.wait_for("WATCH: query failed")
            fake_gh.answer(graphql_body([pull_request_node(145, "a" * 40,
                                                           "open")]))
            recovered = watcher.wait_for("WATCH: query recovered")
            lines = watcher.stop()
            check(f"{label} (exit status 0) is a failure, not an empty answer",
                  blind and any(expected_fragment in line for line in lines),
                  "\n".join(lines))
            check(f"{label}: the compared state survives it",
                  recovered and not any("PR #145 OPENED" in line
                                        for line in lines), "\n".join(lines))

        # ------------------------------------------------------------------
        # A gh that never runs at all is a failure with a message, not a
        # traceback and not silence.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "no-gh")
        environment_without_gh = {**fake_gh.environment(),
                                  "PATH": str(scratch / "empty-path")}
        (scratch / "empty-path").mkdir()
        watcher = WatcherProcess(environment=environment_without_gh,
                                 token_file=token_file)
        blind = watcher.wait_for("WATCH: query failed")
        lines = watcher.stop()
        check("a gh that cannot be run at all announces blindness",
              blind and any("FileNotFoundError" in line for line in lines),
              "\n".join(lines + watcher.error_lines))

        # ------------------------------------------------------------------
        # --from-start reports what is already open, and a paginated answer
        # assembles into one poll rather than two rounds of events.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "from-start")
        fake_gh.answer(graphql_body([pull_request_node(145, "a" * 40, "first")],
                                    has_next_page=True, end_cursor="CURSOR"))
        fake_gh.answer(graphql_body([pull_request_node(146, "b" * 40, "second")]),
                       name="control-next-page.json")
        watcher = WatcherProcess("--from-start",
                                 environment=fake_gh.environment(),
                                 token_file=token_file)
        first = watcher.wait_for("PR #145 OPENED aaaaaaaa nedlern: first")
        second = watcher.wait_for("PR #146 OPENED bbbbbbbb nedlern: second")
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4, watcher)
        lines = watcher.stop()
        check("--from-start reports every already-open pull request",
              first and second, "\n".join(lines))
        check("a second page is fetched and joins the same poll",
              watcher.count("PR #145") == 1 and watcher.count("PR #146") == 1,
              "\n".join(lines))
        check("--from-start says so in the baseline line",
              any("each reported below as OPENED" in line for line in lines),
              "\n".join(lines))

        # ------------------------------------------------------------------
        # A notice of the GHI-MD edit job already there at the first poll is
        # an event that ends --exit-after-first-poll-with-events, and so is
        # one that appears while every query fails.
        # ------------------------------------------------------------------
        notices = scratch / "needs-a-look"
        notices.mkdir()
        (notices / "pr9-bbbbbbbbbbbb.txt").write_text("pull request 9 needs a look\n",
                                                       encoding="utf-8")
        fake_gh = FakeGitHubCommand(scratch / "notice-at-start")
        watcher = WatcherProcess("--exit-after-first-poll-with-events",
                                 environment=fake_gh.environment(), token_file=token_file,
                                 needs_a_look_directory=notices)
        try:
            exit_code = watcher.process.wait(timeout=EVENT_WAIT_BACKSTOP_SECONDS)
        except subprocess.TimeoutExpired:
            exit_code = None
        lines = watcher.stop()
        check("a notice present at the first poll is reported and ends "
              "--exit-after-first-poll-with-events with exit 0",
              exit_code == 0 and watcher.count(
                  "NEEDS A LOOK pr9-bbbbbbbbbbbb.txt: pull request 9 needs a look") == 1,
              f"exit {exit_code}\n" + "\n".join(lines + watcher.error_lines))

        fake_gh = FakeGitHubCommand(scratch / "notice-while-blind")
        fake_gh.answer(exit_code=1, stderr="HTTP 502")
        empty_notices = scratch / "needs-a-look-empty"
        watcher = WatcherProcess("--exit-after-first-poll-with-events",
                                 environment=fake_gh.environment(), token_file=token_file,
                                 needs_a_look_directory=empty_notices)
        blind = watcher.wait_for("WATCH: query failed")
        wait_for_calls(fake_gh, fake_gh.call_count() + 2, watcher)
        still_running = watcher.process.poll() is None
        empty_notices.mkdir()
        (empty_notices / "invocation-stopped.txt").write_text("the job stopped\n",
                                                              encoding="utf-8")
        try:
            exit_code = watcher.process.wait(timeout=EVENT_WAIT_BACKSTOP_SECONDS)
        except subprocess.TimeoutExpired:
            exit_code = None
        lines = watcher.stop()
        check("a notice that appears while every query fails is reported and ends "
              "--exit-after-first-poll-with-events with exit 0",
              blind and still_running and exit_code == 0
              and watcher.count("NEEDS A LOOK invocation-stopped.txt: the job stopped") == 1,
              f"exit {exit_code}\n" + "\n".join(lines + watcher.error_lines))


if __name__ == "__main__":
    run_unit_cases()
    run_needs_a_look_unit_cases()
    run_subprocess_cases()
    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("all cases passed")
