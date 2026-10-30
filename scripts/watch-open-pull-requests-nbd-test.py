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

    def __init__(self, *flags, environment=None, token_file=None):
        self.lines = []
        self.error_lines = []
        self.process = subprocess.Popen(
            [sys.executable, str(WATCH_SCRIPT),
             "--poll-seconds", "0.05",
             "--token-file", str(token_file), *flags],
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
    # The event key is (number, head sha) and nothing else.
    # ------------------------------------------------------------------
    events_for_poll = watcher_module.events_for_poll
    unchanged = [{"number": 7, "head_sha": "aaaaaaaaaaaa", "title": "t",
                  "is_draft": False, "author": "nedlern"}]
    retitled = [{"number": 7, "head_sha": "aaaaaaaaaaaa", "title": "EDITED",
                 "is_draft": True, "author": "someone-else"}]
    moved = [{"number": 7, "head_sha": "bbbbbbbbbbbb", "title": "t",
              "is_draft": False, "author": "nedlern"}]

    check("a pull request not seen before is OPENED",
          events_for_poll({}, unchanged) == [
              "PR #7 OPENED aaaaaaaa nedlern: t"],
          str(events_for_poll({}, unchanged)))
    check("the same head sha again is not an event",
          events_for_poll({7: "aaaaaaaaaaaa"}, unchanged) == [], "")
    check("a title, draft or author change alone is not an event",
          events_for_poll({7: "aaaaaaaaaaaa"}, retitled) == [],
          str(events_for_poll({7: "aaaaaaaaaaaa"}, retitled)))
    check("a changed head sha is NEW-HEAD",
          events_for_poll({7: "aaaaaaaaaaaa"}, moved) == [
              "PR #7 NEW-HEAD bbbbbbbb nedlern: t"],
          str(events_for_poll({7: "aaaaaaaaaaaa"}, moved)))
    check("a draft is marked, not filtered out",
          events_for_poll({}, retitled) == [
              "PR #7 OPENED aaaaaaaa someone-else [draft]: EDITED"],
          str(events_for_poll({}, retitled)))

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
            pull_request_node(146, "b" * 40, "newly opened", draft=True)]))
        opened = watcher.wait_for("PR #146 OPENED bbbbbbbb nedlern [draft]: "
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
            pull_request_node(146, "b" * 40, "RETITLED 146", draft=True)]))
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4, watcher)
        check("a changed title is not an event",
              "RETITLED" not in "\n".join(watcher.lines), "\n".join(watcher.lines))

        # A new head commit on 146 only.
        fake_gh.answer(graphql_body([
            pull_request_node(145, "a" * 40, "RETITLED 145"),
            pull_request_node(146, "c" * 40, "RETITLED 146", draft=True)]))
        moved = watcher.wait_for("PR #146 NEW-HEAD cccccccc")
        check("a new head commit on an open pull request is one NEW-HEAD line",
              moved and watcher.count("PR #146 NEW-HEAD") == 1,
              "\n".join(watcher.lines))
        check("the pull request whose head did not move stays silent",
              watcher.count("PR #145") == 0, "\n".join(watcher.lines))

        # A closed pull request that reopens is announced again — the
        # documented choice, since the seat must look at it again.
        fake_gh.answer(graphql_body([pull_request_node(146, "c" * 40,
                                                       "RETITLED 146",
                                                       draft=True)]))
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 3, watcher)
        fake_gh.answer(graphql_body([
            pull_request_node(145, "a" * 40, "reopened"),
            pull_request_node(146, "c" * 40, "RETITLED 146", draft=True)]))
        reopened = watcher.wait_for("PR #145 OPENED aaaaaaaa nedlern: reopened")
        lines = watcher.stop()
        check("a pull request that closes and reopens is announced again",
              reopened, "\n".join(lines))
        check("closing a pull request is not itself announced",
              not any("CLOSED" in line for line in lines), "\n".join(lines))

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


# ----------------------------------------------------------------------
# --track-who-each-open-pull-request-waits-on
# ----------------------------------------------------------------------

NOW_TEXT = "2026-10-22T12:00:00Z"
MINUTE = 60.0


def queue_node(number, head_sha, title="a title", draft=False, author="nedlern",
               created="2026-10-22T11:00:00Z", committed="2026-10-22T11:10:00Z",
               mergeable="MERGEABLE", comments=0, reviews=()):
    """A GraphQL node as QUEUE_QUERY returns it; reviews are (login, state, submitted, commit)."""
    return {"number": number, "title": title, "isDraft": draft,
            "headRefOid": head_sha, "author": {"login": author},
            "createdAt": created, "mergeable": mergeable,
            "comments": {"totalCount": comments},
            "reviews": {"totalCount": len(reviews), "nodes": [
                {"state": state, "submittedAt": submitted,
                 "author": {"login": login}, "commit": {"oid": commit}}
                for login, state, submitted, commit in reviews]},
            "commits": {"nodes": [{"commit": {"committedDate": committed}}]}}


def queue_pull_request(*arguments, **keywords):
    pull_request, reason = watcher_module.queue_pull_request_from_node(
        queue_node(*arguments, **keywords))
    assert reason is None, reason
    return pull_request


class StopDriving(Exception):
    pass


class FakeClock:
    """Stands in for the time module: sleep advances time; the answers running out ends the loop."""

    def __init__(self, start, answers, step):
        self.now = start
        self.answers = list(answers)
        self.step = step

    def time(self):
        return self.now

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += self.step if self.step is not None else seconds
        if not self.answers:
            raise StopDriving()

    def fetch(self, *_arguments, **_keywords):
        return self.answers.pop(0)


def drive_queue_monitor(answers, scratch, extra_flags=(), start=None, step=None,
                        state_file=None, hold_file=None):
    """Run run_queue_monitor in this process over the given fetch answers; return (lines, exit code or None)."""
    start = start if start is not None else watcher_module.github_time_seconds(NOW_TEXT)
    clock = FakeClock(start, answers, step)
    lines = []
    saved = (watcher_module.time, watcher_module.emit,
             watcher_module.fetch_open_pull_requests)
    watcher_module.time = clock
    watcher_module.emit = lines.append
    watcher_module.fetch_open_pull_requests = clock.fetch
    arguments = watcher_module.parse_arguments([
        "--track-who-each-open-pull-request-waits-on", "--poll-seconds", "60",
        "--who-each-open-pull-request-waits-on-state-file",
        str(state_file or scratch / "state.json"),
        "--merge-holds-pull-request-list-file",
        str(hold_file or scratch / "merge-holds.md"), *extra_flags])
    exit_code = None
    try:
        exit_code = watcher_module.run_queue_monitor(arguments, "tok")
    except StopDriving:
        pass
    finally:
        (watcher_module.time, watcher_module.emit,
         watcher_module.fetch_open_pull_requests) = saved
    return lines, exit_code


def run_who_each_waits_on_cases():
    waiting_state = watcher_module.waiting_state
    head = "a" * 40
    old_head = "b" * 40
    reviewer = "ned-review-merge"

    def state_of(*arguments, hold=None, **keywords):
        return waiting_state(queue_pull_request(*arguments, **keywords), hold, reviewer)

    # ------------------------------------------------------------------
    # Who a pull request waits on, from GitHub state and the holds.
    # ------------------------------------------------------------------
    result = state_of(1, head)
    check("no review on the head commit: waits on merge-lane-2, since the head commit",
          result[:2] == ("merge-agent-seat", "merge-lane-2")
          and "no approving or changes-requested review" in result[2]
          and result[3] == "2026-10-22T11:10:00Z", str(result))
    result = state_of(1, head, created="2026-10-22T11:30:00Z")
    check("a head commit older than the pull request: since the pull request opened",
          result[3] == "2026-10-22T11:30:00Z", str(result))
    result = state_of(1, head, reviews=[
        (reviewer, "CHANGES_REQUESTED", "2026-10-22T11:20:00Z", head)])
    check("changes requested on the head commit: waits on the author, since the review",
          result[:2] == ("author", "the author, GitHub account nedlern")
          and result[3] == "2026-10-22T11:20:00Z", str(result))
    result = state_of(1, head, committed="2026-10-22T11:40:00Z", reviews=[
        (reviewer, "CHANGES_REQUESTED", "2026-10-22T11:20:00Z", old_head)])
    check("a push after changes were requested: waits on merge-lane-2 for the fix-round",
          result[0] == "merge-agent-seat" and "fix-round" in result[2]
          and result[3] == "2026-10-22T11:40:00Z", str(result))
    result = state_of(1, head, reviews=[
        (reviewer, "APPROVED", "2026-10-22T11:20:00Z", head),
        (reviewer, "COMMENTED", "2026-10-22T11:30:00Z", head)])
    check("approved on the head commit, a later comment review aside: merge-lane-2 merges it",
          result[0] == "merge-agent-seat" and "merge it" in result[2]
          and result[3] == "2026-10-22T11:20:00Z", str(result))
    result = state_of(1, head, reviews=[
        ("mac-claude", "CHANGES_REQUESTED", "2026-10-22T11:20:00Z", head)])
    check("another account's review does not decide a pull request nedlern opened",
          result[0] == "merge-agent-seat" and "no approving" in result[2], str(result))
    result = state_of(1, head, author=reviewer, reviews=[
        ("mac-claude", "APPROVED", "2026-10-22T11:20:00Z", head)])
    check("on the reviewer account's own pull request another account's approval decides",
          result[0] == "merge-agent-seat" and "mac-claude approved" in result[2],
          str(result))
    result = state_of(1, head, author=reviewer, reviews=[
        ("zz-reviewer", "CHANGES_REQUESTED", "2026-10-22T11:20:00Z", head)])
    check("any account other than the reviewer account decides its pull request",
          result[0] == "author", str(result))
    result = state_of(1, head, author=reviewer, reviews=[
        (reviewer, "COMMENTED", "2026-10-22T11:20:00Z", head)])
    check("and the reviewer account's own review of it decides nothing",
          "no approving" in result[2], str(result))
    result = state_of(1, head, draft=True)
    check("a draft waits on its author", result[0] == "author"
          and "draft" in result[2] and result[3] == "", str(result))
    result = state_of(1, head, mergeable="CONFLICTING", reviews=[
        (reviewer, "APPROVED", "2026-10-22T11:20:00Z", head)])
    check("a branch that conflicts with main waits on its author, approved or not",
          result[0] == "author" and "conflicts" in result[2], str(result))
    result = state_of(1, head, mergeable="UNKNOWN")
    check("mergeable UNKNOWN, which GitHub reports while computing, is not a conflict",
          result[0] == "merge-agent-seat", str(result))
    result = state_of(1, head, draft=True, hold=("user", "his words on item 3"))
    check("a hold naming the user wins over GitHub state",
          result == ("user", "the user", "held: his words on item 3", ""), str(result))
    result = state_of(1, head, hold=("reboot-test", "reworks it"))
    check("a hold naming an agent-seat",
          result == ("agent-seat", "agent-seat reboot-test", "held: reworks it", ""),
          str(result))
    result = state_of(1, head, hold=("merge-lane-2", "merge after #2"))
    check("a hold naming merge-lane-2 itself",
          result[:2] == ("merge-agent-seat", "merge-lane-2"), str(result))

    # ------------------------------------------------------------------
    # Reading a node: the extra fields are required, pending reviews dropped.
    # ------------------------------------------------------------------
    from_node = watcher_module.queue_pull_request_from_node
    node = queue_node(5, head, reviews=[
        (reviewer, "PENDING", None, head), (reviewer, "APPROVED", "2026-10-22T11:20:00Z", head)])
    pull_request, reason = from_node(node)
    check("a pending review is dropped, a submitted one kept",
          reason is None and [review["state"] for review in pull_request["reviews"]]
          == ["APPROVED"], f"{pull_request} {reason}")
    node = queue_node(5, head)
    del node["reviews"]
    check("a node without reviews is a reason, not a pull request",
          from_node(node) == (None, "pull request #5 came back without its comment "
                                    "count, reviews or commits"), str(from_node(node)))
    node = queue_node(5, head)
    node["comments"]["totalCount"] = "3"
    check("a comment count that is not a number is a reason",
          from_node(node)[0] is None and "wrong JSON type" in from_node(node)[1],
          str(from_node(node)))
    node = queue_node(5, head)
    node["reviews"]["nodes"] = ["not an object"]
    check("a review that is not an object is a reason",
          from_node(node)[0] is None and "not a JSON object" in from_node(node)[1],
          str(from_node(node)))
    node = queue_node(5, head)
    node["commits"]["nodes"] = []
    check("a node with no commits has no head commit time, and is still read",
          from_node(node)[0] is not None and from_node(node)[0]["head_committed_at"] == "",
          str(from_node(node)))
    check("durations read in days and hours, hours and minutes, or minutes",
          [watcher_module.duration_text(seconds) for seconds in
           (2 * 86400 + 3 * 3600 + 5 * 60, 3 * 3600 + 7 * 60, 59, -5)]
          == ["2d3h", "3h7m", "0m", "0m"], "")
    check("a node the watcher's own reader refuses is refused here too",
          from_node({"number": 5})[0] is None, str(from_node({"number": 5})))

    # ------------------------------------------------------------------
    # The merge holds file.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        holds_file = scratch / "merge-holds.md"
        check("a missing merge holds file holds nothing and is no problem",
              watcher_module.read_holds(holds_file) == ({}, []),
              str(watcher_module.read_holds(holds_file)))
        holds_file.write_text(
            "# merge-lane-2: held pull requests\n\nRead this before every merge.\n"
            "- PR 12 waits on user: his words on item 3\n"
            "- PR 13 waits on reboot-test: reworks it (task #1)\n"
            "- PR 14: no waits-on\n"
            "- PR 12 waits on reboot-test: a second hold\n", encoding="utf-8")
        holds, problems = watcher_module.read_holds(holds_file)
        check("well-formed holds are read and prose lines skipped",
              holds == {12: ("user", "his words on item 3"),
                        13: ("reboot-test", "reworks it (task #1)")}, str(holds))
        check("a '- PR' line without 'waits on' is reported, naming its line",
              any("line 6 is not" in problem and "PR 14" in problem
                  for problem in problems), str(problems))
        check("a second hold on one pull request is reported and the first applies",
              any("line 7 holds #12 a second time" in problem for problem in problems)
              and len(problems) == 2, str(problems))
        holds, problems = watcher_module.read_holds(scratch)
        check("an unreadable merge holds file is reported, and holds nothing",
              holds == {} and len(problems) == 1
              and "cannot read the merge holds file" in problems[0], str(problems))

    # ------------------------------------------------------------------
    # One poll: events, reminders and closings.
    # ------------------------------------------------------------------
    queue_poll = watcher_module.queue_poll
    now = watcher_module.github_time_seconds(NOW_TEXT)
    unreviewed = queue_pull_request(7, head, title="seven")
    lines, entries, problems = queue_poll({}, [unreviewed], {}, now, reviewer, True)
    check("listing every pull request prints IN-QUEUE with who and since when",
          lines == ['PR #7 IN-QUEUE: "seven"; waits on merge-lane-2 since '
                    '2026-10-22T11:10Z (50m): head commit aaaaaaaa has no approving '
                    'or changes-requested review: review it'], str(lines))
    lines, entries, _ = queue_poll(entries, [unreviewed], {}, now + 10 * MINUTE, reviewer, False)
    check("an item listed IN-QUEUE counts as reminded for its wait", lines == [], str(lines))

    lines, entries, _ = queue_poll({}, [unreviewed], {}, now, reviewer, False)
    check("an unseen pull request is OPENED",
          len(lines) == 1 and lines[0].startswith('PR #7 OPENED: "seven"'), str(lines))
    opened_entries = entries
    fresh = queue_pull_request(7, head, title="seven", committed=NOW_TEXT,
                               created=NOW_TEXT)
    lines, entries, _ = queue_poll({}, [fresh], {}, now, reviewer, False)
    lines, entries, _ = queue_poll(entries, [fresh], {}, now + 4 * MINUTE, reviewer, False)
    check("waiting on merge-lane-2 under 5 minutes: no reminder", lines == [], str(lines))
    lines, entries, _ = queue_poll(entries, [fresh], {}, now + 5 * MINUTE, reviewer, False)
    check("waiting on merge-lane-2 for 5 minutes: one STALE line",
          len(lines) == 1 and "PR #7 STALE, waiting on merge-lane-2 for 5m" in lines[0],
          str(lines))
    lines, entries, _ = queue_poll(entries, [fresh], {}, now + 50 * MINUTE, reviewer, False)
    check("and only once for the same wait", lines == [], str(lines))
    _, late_entries, _ = queue_poll({}, [fresh], {}, now, reviewer, False)
    lines, _, _ = queue_poll(late_entries, [fresh], {}, now + 7 * MINUTE, reviewer, False)
    check("a first poll past the 5 minutes still reminds",
          len(lines) == 1 and "STALE" in lines[0], str(lines))

    pushed = queue_pull_request(7, old_head, title="seven", comments=2, reviews=[
        ("mac-claude", "COMMENTED", "2026-10-22T11:59:00Z", old_head)])
    lines, entries, _ = queue_poll(opened_entries, [pushed], {}, now + MINUTE, reviewer, False)
    check("a push, a review and a comment in one poll make one line naming all three",
          len(lines) == 1 and lines[0].startswith(
              'PR #7 PUSHED bbbbbbbb REVIEWED by mac-claude (COMMENTED) COMMENTED:'),
          str(lines))
    reviewed_again = queue_pull_request(7, old_head, title="seven", comments=2, reviews=[
        ("mac-claude", "COMMENTED", "2026-10-22T11:59:00Z", old_head),
        (reviewer, "APPROVED", "2026-10-22T12:00:30Z", old_head)])
    lines, _, _ = queue_poll(entries, [reviewed_again], {}, now + MINUTE, reviewer, False)
    check("a review line names the newest review",
          len(lines) == 1 and f"REVIEWED by {reviewer} (APPROVED)" in lines[0], str(lines))
    lines, entries, _ = queue_poll(entries, [pushed], {}, now + 2 * MINUTE, reviewer, False)
    check("an unchanged poll after it prints nothing", lines == [], str(lines))
    lines, entries, _ = queue_poll(entries, [pushed], {}, now + 6 * MINUTE, reviewer, False)
    check("still waiting on merge-lane-2 5 minutes after the event: one STALE line",
          len(lines) == 1 and "STALE, waiting on merge-lane-2 for 56m" in lines[0],
          str(lines))

    changes_requested = queue_pull_request(8, head, title="eight", reviews=[
        (reviewer, "CHANGES_REQUESTED", NOW_TEXT, head)])
    _, entries, _ = queue_poll({}, [changes_requested], {}, now, reviewer, True)
    lines, entries, _ = queue_poll(entries, [changes_requested], {}, now + 29 * MINUTE,
                                   reviewer, False)
    check("waiting on the author 29 quiet minutes: no reminder", lines == [], str(lines))
    lines, entries, _ = queue_poll(entries, [changes_requested], {}, now + 30 * MINUTE,
                                   reviewer, False)
    check("waiting on the author 30 quiet minutes: a QUIET line naming the author",
          len(lines) == 1 and "PR #8 QUIET for 30m, remind the author, GitHub account "
                              "nedlern" in lines[0], str(lines))
    lines, entries, _ = queue_poll(entries, [changes_requested], {}, now + 45 * MINUTE,
                                   reviewer, False)
    check("no second reminder 15 minutes later", lines == [], str(lines))
    lines, entries, _ = queue_poll(entries, [changes_requested], {}, now + 60 * MINUTE,
                                   reviewer, False)
    check("a second reminder 30 minutes after the first, counting quiet from the review",
          len(lines) == 1 and "QUIET for 1h0m" in lines[0], str(lines))
    commented = queue_pull_request(8, head, title="eight", comments=1, reviews=[
        (reviewer, "CHANGES_REQUESTED", NOW_TEXT, head)])
    lines, entries, _ = queue_poll(entries, [commented], {}, now + 70 * MINUTE,
                                   reviewer, False)
    lines, entries, _ = queue_poll(entries, [commented], {}, now + 99 * MINUTE,
                                   reviewer, False)
    check("a comment restarts the quiet time", lines == [], str(lines))
    lines, entries, _ = queue_poll(entries, [commented], {}, now + 100 * MINUTE,
                                   reviewer, False)
    check("which then runs out 30 minutes after the comment",
          len(lines) == 1 and "QUIET for 30m" in lines[0], str(lines))

    holds = {9: ("reboot-test", "reworks it")}
    held = queue_pull_request(9, head, title="nine")
    _, entries, _ = queue_poll({}, [held], holds, now, reviewer, True)
    lines, entries, _ = queue_poll(entries, [held], holds, now + 31 * MINUTE, reviewer, False)
    check("a hold on an agent-seat is reminded after 30 quiet minutes, since the hold began",
          len(lines) == 1 and "remind agent-seat reboot-test" in lines[0]
          and f"since {NOW_TEXT[:16]}Z" in lines[0], str(lines))
    lines, entries, _ = queue_poll(entries, [held], {9: ("user", "his words")},
                                   now + 40 * MINUTE, reviewer, False)
    check("a changed wait starts its own since", entries["9"]["since"] == now + 40 * MINUTE
          and entries["9"]["party"] == "the user", str(entries))
    holds = {9: ("user", "his words")}
    _, entries, _ = queue_poll({}, [held], holds, now, reviewer, True)
    lines, entries, _ = queue_poll(entries, [held], holds, now + 600 * MINUTE, reviewer, False)
    check("a hold on the user is never reminded by this program", lines == [], str(lines))

    lines, entries, problems = queue_poll(entries, [], holds, now, reviewer, False)
    check("a pull request no longer open is CLOSED, with who it waited on",
          lines == ['PR #9 CLOSED: "nine" is no longer open (merged or closed); it '
                    'waited on the user: held: his words'], str(lines))
    check("a hold on a pull request that is not open is a problem to report",
          problems == ["#9 is held, but is not an open pull request; remove its line"],
          str(problems))
    check("and the closed pull request leaves the state", entries == {}, str(entries))

    summary = watcher_module.queue_summary({
        "1": {"party": "the user"}, "2": {"party": "merge-lane-2"},
        "3": {"party": "merge-lane-2"}, "4": {"party": "agent-seat a"}})
    check("the summary puts the party with most pull requests first, ties by name",
          summary == "2 wait on merge-lane-2; 1 wait on agent-seat a; 1 wait on the user",
          summary)

    # ------------------------------------------------------------------
    # The state file.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        state_file = scratch / "deeper" / "state.json"
        _, entries, _ = queue_poll({}, [unreviewed], {}, now, reviewer, True)
        state = {"version": 1, "pull_requests": entries, "hold_problems": []}
        check("the state file is written, its directory made",
              watcher_module.save_queue_state(state_file, state) is None
              and state_file.is_file(), "")
        check("and reads back as it was written",
              watcher_module.load_queue_state(state_file) == (state, None),
              str(watcher_module.load_queue_state(state_file)))
        check("a missing state file is no state and no problem",
              watcher_module.load_queue_state(scratch / "none.json") == (None, None), "")
        bad = scratch / "bad.json"
        for label, text in [("not JSON", "{"),
                            ("another version", json.dumps({**state, "version": 2})),
                            ("an entry missing a field", json.dumps(
                                {**state, "pull_requests": {"7": {"title": "x"}}})),
                            ("a key that is not a number", json.dumps(
                                {**state, "pull_requests": {"x": entries["7"]}})),
                            ("hold problems that are not a list", json.dumps(
                                {**state, "hold_problems": "x"})),
                            ("JSON that is not an object", "[]")]:
            bad.write_text(text, encoding="utf-8")
            loaded, problem = watcher_module.load_queue_state(bad)
            check(f"a state file holding {label} is a problem, not state",
                  loaded is None and problem is not None and str(bad) in problem,
                  f"{loaded} {problem}")
        loaded, problem = watcher_module.load_queue_state(scratch)
        check("an unreadable state file is a problem naming it",
              loaded is None and "cannot read the state file" in (problem or ""),
              str(problem))
        blocker = scratch / "a-file"
        blocker.write_text("", encoding="utf-8")
        problem = watcher_module.save_queue_state(blocker / "state.json", state)
        check("a state file that cannot be written is a problem naming it",
              problem is not None and "cannot write the state file" in problem, str(problem))
        occupied = scratch / "occupied"
        (occupied / "inside").mkdir(parents=True)
        problem = watcher_module.save_queue_state(occupied, state)
        check("a state file path that is a directory is a problem naming it",
              problem is not None and "cannot write the state file" in problem, str(problem))

    # ------------------------------------------------------------------
    # The loop: first invocation, restart, failures and reports.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        answer = ([queue_pull_request(7, head, title="seven")], None)
        lines, _ = drive_queue_monitor([answer, answer], scratch)
        check("a first invocation lists the queue with a summary, then is quiet",
              lines[0] == "WAITS-ON: 1 open pull requests in nedschorus/nedschorus: "
                          "1 wait on merge-lane-2"
              and lines[1].startswith("PR #7 IN-QUEUE") and len(lines) == 2,
              str(lines))
        check("and saves its state", (scratch / "state.json").is_file(), "")
        pushed_answer = ([queue_pull_request(7, old_head, title="seven")], None)
        lines, _ = drive_queue_monitor([pushed_answer], scratch)
        check("a restart reports only what changed since the saved state",
              len(lines) == 1 and lines[0].startswith("PR #7 PUSHED bbbbbbbb"), str(lines))

        lines, exit_code = drive_queue_monitor(
            [pushed_answer], scratch,
            extra_flags=["--print-who-each-open-pull-request-waits-on-and-exit"],
            state_file=scratch / "print-state.json")
        check("--print-who-each-open-pull-request-waits-on-and-exit lists and exits 0",
              exit_code == 0 and any("PR #7 IN-QUEUE" in line for line in lines), str(lines))
        check("and writes no state", not (scratch / "print-state.json").exists(), "")
        lines, exit_code = drive_queue_monitor(
            [(None, "HTTP 503")], scratch,
            extra_flags=["--print-who-each-open-pull-request-waits-on-and-exit"])
        check("and exits 1 saying why when GitHub cannot be asked",
              exit_code == 1 and "HTTP 503" in lines[-1], str(lines))

        failure = (None, "gh: HTTP 503")
        lines, _ = drive_queue_monitor([failure] * 25 + [pushed_answer], scratch)
        blind_lines = [line for line in lines if "BLIND" in line]
        check("a failed query says the monitor is BLIND, once at the start",
              "BLIND until it recovers" in blind_lines[0] and "HTTP 503" in blind_lines[0],
              str(lines))
        check("and again every 10 minutes the failures go on",
              len(blind_lines) == 3 and "still BLIND after 11 failed polls over 10m"
              in blind_lines[1], str(blind_lines))
        check("then recovery is reported with the count",
              any("recovered after 25 failed polls" in line for line in lines), str(lines))

        (scratch / "corrupt.json").write_text("{", encoding="utf-8")
        lines, _ = drive_queue_monitor([pushed_answer], scratch,
                                       state_file=scratch / "corrupt.json")
        check("an unusable state file is reported and the queue listed as on a first invocation",
              "is not JSON" in lines[0] and any("IN-QUEUE" in line for line in lines),
              str(lines))

        blocker = scratch / "blocker"
        blocker.write_text("", encoding="utf-8")
        lines, _ = drive_queue_monitor([pushed_answer] * 3, scratch,
                                       state_file=blocker / "state.json")
        check("a state file that cannot be written is reported once, not every poll",
              sum("cannot write the state file" in line for line in lines) == 1, str(lines))

        holds_file = scratch / "holds.md"
        holds_file.write_text("- PR 7: no waits-on\n", encoding="utf-8")
        lines, _ = drive_queue_monitor([pushed_answer] * 3, scratch,
                                       state_file=scratch / "holds-state.json",
                                       hold_file=holds_file)
        check("a malformed hold is reported once, not every poll",
              sum("merge holds file:" in line for line in lines) == 1, str(lines))
        holds_file.write_text("- PR 7 waits on user: his words\n", encoding="utf-8")
        lines, _ = drive_queue_monitor([pushed_answer], scratch,
                                       state_file=scratch / "holds-state.json",
                                       hold_file=holds_file)
        holds_file.write_text("- PR 7: no waits-on again\n", encoding="utf-8")
        lines, _ = drive_queue_monitor([pushed_answer], scratch,
                                       state_file=scratch / "holds-state.json",
                                       hold_file=holds_file)
        check("a malformed hold appearing on a later invocation is reported",
              any("no waits-on again" in line for line in lines), str(lines))
        holds_file.write_text("- PR 7 waits on user: his words\n", encoding="utf-8")
        lines, _ = drive_queue_monitor([pushed_answer], scratch,
                                       state_file=scratch / "holds-state.json",
                                       hold_file=holds_file)
        check("its repair is reported too",
              any("well-formed again" in line for line in lines), str(lines))

    # ------------------------------------------------------------------
    # The real command line, with the fake gh.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        token_file = scratch / "fixture.token"
        token_file.write_text(FIXTURE_TOKEN + "\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(WATCH_SCRIPT), "--token-file", str(token_file),
             "--print-who-each-open-pull-request-waits-on-and-exit"],
            capture_output=True, text=True, timeout=15)
        check("the print flag without the tracking flag exits 2 saying so",
              result.returncode == 2
              and "needs --track-who-each-open-pull-request-waits-on" in result.stderr,
              f"rc={result.returncode} stderr={result.stderr!r}")
        fake_gh = FakeGitHubCommand(scratch / "fake")
        fake_gh.answer(json.dumps({"data": {"repository": {"pullRequests": {
            "nodes": [queue_node(21, head, title="twenty-one")],
            "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}))
        watcher = WatcherProcess(
            "--track-who-each-open-pull-request-waits-on",
            "--who-each-open-pull-request-waits-on-state-file", str(scratch / "state.json"),
            "--merge-holds-pull-request-list-file", str(scratch / "holds.md"),
            environment=fake_gh.environment(), token_file=token_file)
        listed = watcher.wait_for('PR #21 IN-QUEUE: "twenty-one"; waits on merge-lane-2')
        fake_gh.answer(stdout="", exit_code=1,
                       stderr=f"gh: HTTP 503 Bearer {FIXTURE_TOKEN}")
        blind = watcher.wait_for("WAITS-ON: GitHub query failed")
        lines = watcher.stop()
        everything = "\n".join(lines + watcher.error_lines)
        check("the command line lists the queue through the real gh call path",
              listed, everything)
        check("and reports a failed query with the token redacted",
              blind and FIXTURE_TOKEN not in everything and "[REDACTED]" in everything,
              everything)


if __name__ == "__main__":
    run_unit_cases()
    run_subprocess_cases()
    run_who_each_waits_on_cases()
    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("all cases passed")
