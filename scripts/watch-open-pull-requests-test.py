#!/usr/bin/env python3
"""Tests for watch-open-pull-requests.py.

Run: python3 scripts/watch-open-pull-requests-test.py
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

WATCH_SCRIPT = Path(__file__).with_name("watch-open-pull-requests.py")

_spec = importlib.util.spec_from_file_location("watch_open_pull_requests",
                                               WATCH_SCRIPT)
watcher_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watcher_module)

# Invented here, never a credential: long enough to be a plausible token
# (the program refuses shorter ones) and distinctive enough that a leak
# into any output stream is unmistakable.
FIXTURE_TOKEN = "fixture-token-never-a-real-credential-0123456789"

CONTROL_DIRECTORY_VARIABLE = "WATCH_OPEN_PULL_REQUESTS_TEST_CONTROL_DIR"

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

    def wait_for(self, fragment, timeout=10.0):
        """True once some stdout line contains the fragment; False on timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if any(fragment in line for line in self.lines):
                return True
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


def wait_for_calls(fake_gh, wanted, timeout=10.0):
    """True once the fake `gh` has been called at least `wanted` times."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if fake_gh.call_count() >= wanted:
            return True
        time.sleep(0.02)
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
    check("a node with no head sha is a failure, not a dropped pull request",
          from_node({"number": 3, "title": "t"})[0] is None
          and "head commit sha" in from_node({"number": 3, "title": "t"})[1],
          str(from_node({"number": 3, "title": "t"})))
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
                capture_output=True, text=True, timeout=15)
            ok = (result.returncode == 2
                  and len(result.stderr.strip().splitlines()) == 1)
            detail = f"rc={result.returncode} stderr={result.stderr!r}"
        except subprocess.TimeoutExpired:
            ok, detail = False, "still running after 15s — validation never fired"
        check(f"bad invocation {label} exits 2 with one stderr line", ok, detail)

    result = subprocess.run(
        [sys.executable, str(WATCH_SCRIPT),
         "--token-file", str(missing_token_file)],
        capture_output=True, text=True, timeout=15)
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

        wait_for_calls(fake_gh, 4)
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
        wait_for_calls(fake_gh, calls_now + 4)
        check("polls that change nothing produce no further lines",
              watcher.count("PR #146") == 1 and watcher.count("PR #145") == 0,
              "\n".join(watcher.lines))

        # A title edit on both pull requests, no head movement.
        fake_gh.answer(graphql_body([
            pull_request_node(145, "a" * 40, "RETITLED 145"),
            pull_request_node(146, "b" * 40, "RETITLED 146", draft=True)]))
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4)
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
        wait_for_calls(fake_gh, calls_now + 3)
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

        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 5)
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
        check("a head that moved while blind is reported on recovery",
              missed_move, "\n".join(lines))
        check("the recovery line comes before the events it delayed",
              [index for index, line in enumerate(lines)
               if "query recovered" in line][0]
              < [index for index, line in enumerate(lines)
                 if "PR #150 OPENED" in line][0],
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
        wait_for_calls(fake_gh, calls_now + 4)
        lines = watcher.stop()
        check("--from-start reports every already-open pull request",
              first and second, "\n".join(lines))
        check("a second page is fetched and joins the same poll",
              watcher.count("PR #145") == 1 and watcher.count("PR #146") == 1,
              "\n".join(lines))
        check("--from-start says so in the baseline line",
              any("each reported below as OPENED" in line for line in lines),
              "\n".join(lines))


if __name__ == "__main__":
    run_unit_cases()
    run_subprocess_cases()
    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("all cases passed")
