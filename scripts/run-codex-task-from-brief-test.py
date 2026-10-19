#!/usr/bin/env python3
"""Tests for scripts/run-codex-task-from-brief.py, with a fake `codex` on PATH.

A fake `gh` on PATH stands in for the commands --prefetch-github runs: it
logs its arguments and the folder it ran in and, by FAKE_GH_MODE, prints data,
fails, or sleeps.

The fake records its arguments and, by the FAKE_CODEX_MODE environment
variable, writes a report, fails with or without a report, writes nothing,
sleeps past the deadline with a child that may ignore SIGTERM, or blocks
reading stdin. Each case runs the real program as a process. The deadline and
stdin cases run a second time with a fake `find` that sleeps 31 s first, so the
credential-file scan done before Codex starts must not count against their limits.
Two cases check the test's own bounds: a program stalled before it starts Codex,
and one stalled after, are each stopped with every process they started.

Run: python3 scripts/run-codex-task-from-brief-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

PROGRAM = Path(__file__).with_name("run-codex-task-from-brief.py")

FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, signal, sys, time
arguments = sys.argv[1:]
if "FAKE_CODEX_PID_FILE" in os.environ:
    open(os.environ["FAKE_CODEX_PID_FILE"], "w").write(str(os.getpid()))
with open(os.environ["FAKE_CODEX_ARGUMENTS_FILE"], "w") as record:
    json.dump(arguments, record)
report = arguments[arguments.index("-o") + 1]
mode = os.environ.get("FAKE_CODEX_MODE", "report")
print("fake codex trace line")
sys.stdout.flush()
if mode == "report":
    open(report, "w").write("the report\n")
elif mode == "fail":
    print("fake codex: model refused", file=sys.stderr)
    sys.exit(3)
elif mode == "report-then-fail":
    open(report, "w").write("a partial report\n")
    sys.exit(3)
elif mode == "no-report":
    pass
elif mode in ("sleep", "sleep-child-ignores-sigterm"):
    child = os.fork()
    if child == 0:
        if mode == "sleep-child-ignores-sigterm":
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        open(os.environ["FAKE_CODEX_CHILD_PID_FILE"], "w").write(str(os.getpid()))
        time.sleep(600)
        os._exit(0)
    time.sleep(600)
elif mode == "read-stdin":
    data = sys.stdin.read()
    open(report, "w").write(f"stdin held {len(data)} characters\n")
'''

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys, time
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\n")
with open(os.environ["FAKE_GH_LOG"] + ".cwd", "a") as log:
    log.write(os.getcwd() + "\n")
mode = os.environ.get("FAKE_GH_MODE", "data")
if mode == "data":
    print("gh data for " + " ".join(sys.argv[1:]))
elif mode == "fail":
    print("HTTP 404: Not Found", file=sys.stderr)
    sys.exit(1)
elif mode == "sleep":
    time.sleep(60)
elif mode == "sleep-second":
    calls = len(open(os.environ["FAKE_GH_LOG"]).read().splitlines())
    if calls >= 2:
        open(os.environ["FAKE_GH_LOG"] + ".second-started", "w").write(str(time.time()))
        time.sleep(60)
    time.sleep(2)
    print("gh data")
'''

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


scratch = Path(tempfile.mkdtemp(prefix="run-codex-task-test-")).resolve()
try:
    bin_dir = scratch / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "codex"
    fake.write_text(FAKE_CODEX)
    fake.chmod(0o755)
    fake_gh = bin_dir / "gh"
    fake_gh.write_text(FAKE_GH)
    fake_gh.chmod(0o755)
    gh_log = scratch / "gh-calls.jsonl"
    # The runner is started from a folder other than the checkout, as an agent may start it.
    elsewhere = scratch / "elsewhere"
    elsewhere.mkdir()
    checkout = scratch / "checkout"
    checkout.mkdir()
    brief = scratch / "brief.md"
    brief.write_text("Do the task.\nSecond line.\n")
    arguments_file = scratch / "arguments.json"
    child_pid_file = scratch / "child.pid"
    codex_pid_file = scratch / "codex.pid"
    # A scratch HOME keeps each run's credential-file scan, done before Codex starts,
    # from walking the real home directory; it only shortens the suite.
    scratch_home = scratch / "home"
    scratch_home.mkdir()
    # Stands in for a scan slowed by a busy machine: the time limits must not count it.
    slow_find_dir = scratch / "slow-find-bin"
    slow_find_dir.mkdir()
    real_find = shutil.which("find")
    slow_find = slow_find_dir / "find"
    slow_find.write_text(f'#!/bin/sh\nsleep 31\nexec "{real_find}" "$@"\n')
    slow_find.chmod(0o755)

    def run(mode, *extra, stdin=None, timeout=60, path_first=None,
            start_line_timeout=600, gh_mode="data"):
        """Run the program; return (completed, report, seconds since it said it is running Codex).

        timeout counts from that stderr line, which the program prints after building
        Codex's command line, so preparing the command line counts against no limit.
        start_line_timeout bounds the wait for that line, only so a hung scan cannot
        hang the suite. When either runs out, the program, the processes it started
        and the fake Codex's process group are killed, and subprocess.TimeoutExpired
        is raised.
        """
        path = os.pathsep.join(str(d) for d in (path_first, bin_dir) if d)
        environment = dict(os.environ, PATH=f"{path}{os.pathsep}{os.environ['PATH']}",
                           HOME=str(scratch_home), FAKE_CODEX_MODE=mode,
                           FAKE_CODEX_ARGUMENTS_FILE=str(arguments_file),
                           FAKE_CODEX_CHILD_PID_FILE=str(child_pid_file),
                           FAKE_CODEX_PID_FILE=str(codex_pid_file),
                           FAKE_GH_MODE=gh_mode, FAKE_GH_LOG=str(gh_log))
        report = scratch / f"report-{mode}.md"
        codex_pid_file.unlink(missing_ok=True)
        command = [sys.executable, str(PROGRAM), "-C", str(checkout), "--brief", str(brief),
                   "-o", str(report), *extra]
        process = subprocess.Popen(command, env=environment, stdin=stdin, cwd=elsewhere,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   start_new_session=True)
        stdout_parts, stderr_lines = [], []
        codex_started = threading.Event()
        started_at = []

        def read_stderr():
            for line in process.stderr:
                if not codex_started.is_set() and "running Codex in" in line:
                    started_at.append(time.monotonic())
                    codex_started.set()
                stderr_lines.append(line)
            codex_started.set()

        readers = [threading.Thread(target=read_stderr),
                   threading.Thread(target=lambda: stdout_parts.append(process.stdout.read()))]
        for reader in readers:
            reader.start()
        try:
            if not codex_started.wait(timeout=start_line_timeout):
                raise subprocess.TimeoutExpired(command, start_line_timeout)
            start = started_at[0] if started_at else time.monotonic()
            process.wait(timeout=max(0, timeout - (time.monotonic() - start)))
        except subprocess.TimeoutExpired:
            # The program's group holds the scan; Codex runs in a session of its own.
            group_leaders = [process.pid]
            if codex_pid_file.exists():
                group_leaders.append(int(codex_pid_file.read_text()))
            for leader in group_leaders:
                try:
                    os.killpg(leader, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()
            for reader in readers:
                reader.join()
            raise
        for reader in readers:
            reader.join()
        elapsed = time.monotonic() - start
        completed = subprocess.CompletedProcess(command, process.returncode,
                                                "".join(stdout_parts), "".join(stderr_lines))
        return completed, report, elapsed

    completed, report, _ = run("report")
    arguments = json.loads(arguments_file.read_text())
    check("success exits 0 and prints the report path",
          completed.returncode == 0 and completed.stdout.strip() == f"report: {report}",
          f"exit {completed.returncode}, stdout {completed.stdout!r}, stderr {completed.stderr!r}")
    check("the brief's whole text is the prompt, after --",
          arguments[-1] == brief.read_text() and arguments[-2] == "--", repr(arguments[-2:]))
    check("Codex runs in the checkout with its memory store off",
          arguments[:1] == ["exec"] and ["-C", str(checkout)] == arguments[
              arguments.index("-C"):arguments.index("-C") + 2]
          and "memories" in arguments, repr(arguments))
    check("the default permission profile extends read-only",
          'permissions.codex-task-no-credentials.extends=":read-only"' in arguments,
          repr(arguments))
    run_log = report.with_name(report.name + ".run.log")
    check("Codex's output goes to the run log",
          "fake codex trace line" in run_log.read_text(), run_log.read_text())

    completed, report, _ = run("report", "--sandbox", "workspace-write",
                               "-m", "model-x", "--effort", "high")
    arguments = json.loads(arguments_file.read_text())
    check("workspace-write, model and effort reach Codex",
          'permissions.codex-task-no-credentials.extends=":workspace"' in arguments
          and ["-m", "model-x"] == arguments[arguments.index("-m"):arguments.index("-m") + 2]
          and "model_reasoning_effort=high" in arguments, repr(arguments))

    completed, report, _ = run("report")
    arguments = json.loads(arguments_file.read_text())
    check("without the widening options Codex gets no network, extra folder, git skip or web search",
          not any("network" in argument or "web_search" in argument for argument in arguments)
          and "--add-dir" not in arguments and "--skip-git-repo-check" not in arguments,
          repr(arguments))

    extra_root_one = scratch / "extra one"
    extra_root_two = scratch / "extra-two"
    completed, report, _ = run("report", "--sandbox", "workspace-write", "--network",
                               "--writable-root", str(extra_root_one),
                               "--writable-root", str(extra_root_two),
                               "--outside-git-checkout", "--web-search")
    arguments = json.loads(arguments_file.read_text())
    added_folders = [arguments[index + 1] for index, argument in enumerate(arguments)
                     if argument == "--add-dir"]
    check("--network turns on the permission profile's network",
          completed.returncode == 0
          and "permissions.codex-task-no-credentials.network.enabled=true" in arguments,
          f"exit {completed.returncode}, {arguments!r}, stderr {completed.stderr!r}")
    check("each --writable-root reaches Codex as its own --add-dir, path whole",
          added_folders == [str(extra_root_one), str(extra_root_two)], repr(added_folders))
    check("--outside-git-checkout passes --skip-git-repo-check",
          "--skip-git-repo-check" in arguments, repr(arguments))
    check("--web-search sets web_search to live, after exec",
          ["-c", 'web_search="live"'] == arguments[arguments.index('web_search="live"') - 1:
                                                     arguments.index('web_search="live"') + 1]
          if 'web_search="live"' in arguments else False, repr(arguments))
    check("the brief is still the last argument with every option on",
          arguments[-1] == brief.read_text(), repr(arguments[-1]))

    help_text = subprocess.run([sys.executable, str(PROGRAM), "--help"], capture_output=True,
                               text=True, check=False).stdout
    check("the usage line names every option",
          all(option in help_text for option in ("--network", "--writable-root <folder>",
                                                 "--outside-git-checkout", "--web-search")),
          help_text)

    completed, report, _ = run("fail")
    check("a Codex failure exits 1 and names the exit code and the log",
          completed.returncode == 1 and "Codex exited 3" in completed.stderr
          and ".run.log" in completed.stderr and not report.exists(),
          f"exit {completed.returncode}, stderr {completed.stderr!r}")

    completed, report, _ = run("report-then-fail")
    check("Codex exiting nonzero after writing a report still exits 1 and prints no report line",
          completed.returncode == 1 and "Codex exited 3" in completed.stderr
          and "report:" not in completed.stdout,
          f"exit {completed.returncode}, stdout {completed.stdout!r}, stderr {completed.stderr!r}")

    dash_brief = scratch / "dash-brief.md"
    dash_brief.write_text("---\ntitle: front matter\n---\nDo the task.\n")
    environment = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                       HOME=str(scratch_home), FAKE_CODEX_MODE="report",
                       FAKE_CODEX_ARGUMENTS_FILE=str(arguments_file))
    completed = subprocess.run(
        [sys.executable, str(PROGRAM), "-C", str(checkout), "--brief", str(dash_brief),
         "-o", str(scratch / "dash-report.md")], env=environment, capture_output=True,
        text=True, check=False)
    arguments = json.loads(arguments_file.read_text())
    check("a brief that begins with - reaches Codex after --, so it is not read as an option",
          completed.returncode == 0 and arguments[-2:] == ["--", dash_brief.read_text()],
          f"exit {completed.returncode}, {arguments[-2:]!r}")

    stale = scratch / "report-no-report.md"
    stale.write_text("left by an earlier run\n")
    completed, report, _ = run("no-report")
    check("no report exits 1, and an earlier run's report does not count",
          completed.returncode == 1 and "wrote no report" in completed.stderr
          and not report.exists(),
          f"exit {completed.returncode}, stderr {completed.stderr!r}")

    def check_deadline_stops_codex(case_suffix="", path_first=None):
        child_pid_file.unlink(missing_ok=True)
        completed, report, elapsed = run("sleep", "--deadline-minutes", "0.05",
                                         path_first=path_first)
        child_pid = int(child_pid_file.read_text()) if child_pid_file.exists() else None
        time.sleep(0.5)
        child_alive = False
        if child_pid:
            try:
                os.kill(child_pid, 0)
                child_alive = True
            except ProcessLookupError:
                pass
        check("the deadline stops Codex, exits 1 and says so" + case_suffix,
              completed.returncode == 1 and "deadline" in completed.stderr and elapsed < 30,
              f"exit {completed.returncode}, {elapsed:.1f}s, stderr {completed.stderr!r}")
        check("the deadline also stops the processes Codex started" + case_suffix,
              child_pid is not None and not child_alive, f"child {child_pid} alive={child_alive}")

    check_deadline_stops_codex()

    child_pid_file.unlink(missing_ok=True)
    completed, report, elapsed = run("sleep-child-ignores-sigterm", "--deadline-minutes", "0.05")
    child_pid = int(child_pid_file.read_text()) if child_pid_file.exists() else None
    time.sleep(0.5)
    child_alive = False
    if child_pid:
        try:
            os.kill(child_pid, 0)
            child_alive = True
        except ProcessLookupError:
            pass
        if child_alive:
            os.kill(child_pid, 9)
    check("the deadline also kills a process Codex started that ignores SIGTERM",
          completed.returncode == 1 and child_pid is not None and not child_alive,
          f"exit {completed.returncode}, child {child_pid} alive={child_alive}, {elapsed:.1f}s")

    def check_codex_stdin_closed(case_suffix="", path_first=None):
        # The caller's own stdin is an open pipe that never closes; the fake must still see EOF.
        holder = subprocess.Popen(["sleep", "600"], stdout=subprocess.PIPE)
        try:
            completed, report, elapsed = run("read-stdin", stdin=holder.stdout, timeout=30,
                                             path_first=path_first)
        except subprocess.TimeoutExpired:
            completed, report = None, None
        finally:
            holder.kill()
            holder.wait()
        check("Codex's stdin is closed even when the caller's stdin is an open pipe" + case_suffix,
              completed is not None and completed.returncode == 0
              and report.read_text().strip() == "stdin held 0 characters",
              f"completed {completed!r}")

    check_codex_stdin_closed()

    # The program scans for credential files with find only on Linux.
    if sys.platform.startswith("linux"):
        slow_scan_suffix = ", with a credential-file scan that takes 31 s"
        check_deadline_stops_codex(slow_scan_suffix, path_first=slow_find_dir)
        check_codex_stdin_closed(slow_scan_suffix, path_first=slow_find_dir)
    else:
        print("SKIP  the deadline and stdin cases with a 31 s credential-file scan: "
              "the program runs find only on Linux")

    def process_alive(pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        # A killed process stays a zombie until init reaps it; a zombie is not left running.
        try:
            return Path(f"/proc/{pid}/stat").read_text().split(") ")[-1][0] != "Z"
        except OSError:
            return True

    def pids_from(*pid_files):
        return [int(f.read_text()) for f in pid_files if f.exists() and f.read_text()]

    def kill_leftovers(pids):
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    if sys.platform.startswith("linux"):
        stalled_find_dir = scratch / "stalled-find-bin"
        stalled_find_dir.mkdir()
        stalled_find_pid_file = scratch / "stalled-find.pid"
        stalled_find = stalled_find_dir / "find"
        stalled_find.write_text(f'#!/bin/sh\necho $$ > "{stalled_find_pid_file}"\nexec sleep 20\n')
        stalled_find.chmod(0o755)
        started = time.monotonic()
        try:
            completed, _, _ = run("report", path_first=stalled_find_dir, start_line_timeout=2)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
        waited = time.monotonic() - started
        time.sleep(0.5)
        left = [pid for pid in pids_from(stalled_find_pid_file) if process_alive(pid)]
        kill_leftovers(left)
        check("a program stalled before it starts Codex is stopped at the start-line bound, "
              "with the scan it started",
              timed_out and waited < 15 and stalled_find_pid_file.exists() and not left,
              f"timed out {timed_out}, {waited:.1f}s, left running {left}")
    else:
        print("SKIP  a program stalled before it starts Codex: the program runs find only on Linux")

    child_pid_file.unlink(missing_ok=True)
    try:
        run("sleep", timeout=2)
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
    time.sleep(0.5)
    started_pids = pids_from(codex_pid_file, child_pid_file)
    left = [pid for pid in started_pids if process_alive(pid)]
    kill_leftovers(left)
    check("a program stalled after it starts Codex is stopped at its timeout, "
          "with Codex and the processes Codex started",
          timed_out and len(started_pids) == 2 and not left,
          f"timed out {timed_out}, started {started_pids}, left running {left}")

    def gh_calls():
        return [json.loads(line) for line in gh_log.read_text().splitlines()] \
            if gh_log.exists() else []

    def gh_folders():
        cwd_log = Path(str(gh_log) + ".cwd")
        return cwd_log.read_text().splitlines() if cwd_log.exists() else []

    def fresh_prefetch_case():
        gh_log.unlink(missing_ok=True)
        Path(str(gh_log) + ".cwd").unlink(missing_ok=True)
        arguments_file.unlink(missing_ok=True)

    fresh_prefetch_case()
    data_folder = scratch / "report-report.md.github-data"
    data_folder.mkdir(exist_ok=True)
    (data_folder / "left-by-an-earlier-run.txt").write_text("stale\n")
    completed, report, _ = run("report", "--prefetch-github", "pr list --state merged --limit 5",
                               "--prefetch-github", "api 'repos/o/r/pulls?state=closed'")
    arguments = json.loads(arguments_file.read_text()) if arguments_file.exists() else []
    saved = sorted(data_folder.glob("*.txt"))
    check("each --prefetch-github runs gh once, before Codex, with its words split as a shell would",
          completed.returncode == 0 and gh_calls() == [
              ["pr", "list", "--state", "merged", "--limit", "5"],
              ["api", "repos/o/r/pulls?state=closed"]],
          f"exit {completed.returncode}, gh calls {gh_calls()!r}, stderr {completed.stderr!r}")
    check("each gh command runs in the -C checkout, not the folder the runner was started in, "
          "so gh without -R reads the checkout's repository",
          gh_folders() == [str(checkout.resolve())] * 2, repr(gh_folders()))
    check("each gh output is saved in <report>.github-data, and an earlier run's files are gone",
          [path.read_text() for path in saved] == [
              "gh data for pr list --state merged --limit 5\n",
              "gh data for api repos/o/r/pulls?state=closed\n"],
          repr([(path.name, path.read_text()) for path in saved]))
    check("the brief Codex gets is the brief file followed by the list of saved files",
          bool(arguments) and arguments[-1].startswith(brief.read_text().rstrip())
          and all(str(path) in arguments[-1] for path in saved)
          and "`gh pr list --state merged --limit 5`" in arguments[-1]
          and "permission profile keeps you from the folder holding gh's login"
          in arguments[-1],
          repr(arguments[-1:]))

    fresh_prefetch_case()
    long_endpoint = "repos/o/r/" + "x" * 400
    completed, report, _ = run("report", "--prefetch-github", f"api {long_endpoint}")
    saved = sorted(data_folder.glob("*.txt"))
    check("a gh command with a long argument is saved under a name short enough to write",
          completed.returncode == 0 and len(saved) == 1 and len(saved[0].name) < 120,
          f"exit {completed.returncode}, files {[p.name for p in saved]!r}, "
          f"stderr {completed.stderr!r}")

    for refused_arguments, reason in (("pr merge 12", "is not `pr list`"),
                                      ("api -XPOST repos/o/r/issues", "with -X"),
                                      ("api repos/o/r/issues --method=PATCH", "with --method"),
                                      ("api repos/o/r/issues -f title=x", "with -f"),
                                      ("api repos/o/r/issues --input body.json", "with --input"),
                                      ("api -iXDELETE repos/o/r/git/refs/heads/b", "-X (in `-iXDELETE`) can send a request"),
                                      ("api -iFtitle=x repos/o/r/issues", "-F (in `-iFtitle=x`) can send a request"),
                                      ("api -ib repos/o/r", "-b (in `-ib`) is not a short option")):
        fresh_prefetch_case()
        completed, report, _ = run("report", "--prefetch-github", "pr view 1",
                                   "--prefetch-github", refused_arguments)
        check(f"--prefetch-github '{refused_arguments}' is refused with exit 2 before gh or Codex runs",
              completed.returncode == 2 and reason in completed.stderr
              and "may only read from GitHub" in completed.stderr
              and not gh_calls() and not arguments_file.exists(),
              f"exit {completed.returncode}, gh calls {gh_calls()!r}, stderr {completed.stderr!r}")

    fresh_prefetch_case()
    completed, report, _ = run("report", "--prefetch-github", "api -i -q .title -H 'Accept: x' repos/o/r/pulls/1",
                               "--prefetch-github", "api -iqX repos/o/r")
    check("short options that only read, alone or clustered, pass, and a value after -q is "
          "not read as options",
          completed.returncode == 0 and len(gh_calls()) == 2,
          f"exit {completed.returncode}, gh calls {gh_calls()!r}, stderr {completed.stderr!r}")

    fresh_prefetch_case()
    completed, report, _ = run("report", "--prefetch-github", "pr view 1",
                               "--prefetch-github", "issue view 'unclosed")
    check("arguments whose quoting cannot be read get a quoting message, not the read-only "
          "refusal, with exit 2 before gh or Codex runs",
          completed.returncode == 2 and "could not read the quoting" in completed.stderr
          and "every quotation mark closed" in completed.stderr
          and "may only read from GitHub" not in completed.stderr
          and not gh_calls() and not arguments_file.exists(),
          f"exit {completed.returncode}, gh calls {gh_calls()!r}, stderr {completed.stderr!r}")

    fresh_prefetch_case()
    completed, report, _ = run("report", "--prefetch-github", "pr view 1", gh_mode="fail")
    check("a failing gh command exits 1, names the command, its exit code and what gh said, "
          "and Codex is not started",
          completed.returncode == 1 and "`gh pr view 1` exited 1" in completed.stderr
          and "HTTP 404: Not Found" in completed.stderr and not arguments_file.exists(),
          f"exit {completed.returncode}, stderr {completed.stderr!r}")

    fresh_prefetch_case()
    completed, report, elapsed = run("report", "--prefetch-github", "pr view 1",
                                     "--deadline-minutes", "0.02", gh_mode="sleep")
    check("a gh command that passes the deadline is stopped, exits 1, and Codex is not started",
          completed.returncode == 1 and "deadline passed" in completed.stderr
          and "covers every --prefetch-github command and Codex together" in completed.stderr
          and elapsed < 30 and not arguments_file.exists(),
          f"exit {completed.returncode}, {elapsed:.1f}s, stderr {completed.stderr!r}")

    fresh_prefetch_case()
    # 3 s for the whole run: the first gh call takes 2 s and the second sleeps. The second
    # must be stopped when the run's deadline passes, about 1 s after it starts, not after
    # a fresh 3 s of its own.
    second_started_file = Path(str(gh_log) + ".second-started")
    second_started_file.unlink(missing_ok=True)
    completed, report, _ = run("report", "--prefetch-github", "pr view 1",
                               "--prefetch-github", "pr view 2",
                               "--deadline-minutes", "0.05", gh_mode="sleep-second")
    finished = time.time()
    second_ran = (finished - float(second_started_file.read_text())
                  if second_started_file.exists() else None)
    check("the deadline bounds all gh commands together: a later command gets only the time "
          "left, and Codex is not started",
          completed.returncode == 1 and "`gh pr view 2`" in completed.stderr
          and second_ran is not None and second_ran < 2.5 and not arguments_file.exists(),
          f"exit {completed.returncode}, second call ran {second_ran}, "
          f"stderr {completed.stderr!r}")

    fresh_prefetch_case()
    no_gh_dir = scratch / "no-gh-bin"
    no_gh_dir.mkdir()
    completed = subprocess.run(
        [sys.executable, str(PROGRAM), "-C", str(checkout), "--brief", str(brief),
         "-o", str(scratch / "no-gh-report.md"), "--prefetch-github", "pr view 1"],
        env=dict(os.environ, PATH=str(no_gh_dir), HOME=str(scratch_home)),
        capture_output=True, text=True, check=False)
    check("a missing gh exits 1, says gh could not run, and Codex is not started",
          completed.returncode == 1 and "could not run `gh pr view 1`" in completed.stderr
          and not arguments_file.exists(),
          f"exit {completed.returncode}, stderr {completed.stderr!r}")

    empty_brief = scratch / "empty.md"
    empty_brief.write_text("  \n")
    completed = subprocess.run(
        [sys.executable, str(PROGRAM), "-C", str(checkout), "--brief", str(empty_brief),
         "-o", str(scratch / "r.md")], capture_output=True, text=True, check=False)
    check("an empty brief exits 1 without running Codex",
          completed.returncode == 1 and "is empty" in completed.stderr, completed.stderr)

    completed = subprocess.run(
        [sys.executable, str(PROGRAM), "--brief", str(brief), "-o", str(scratch / "r.md")],
        capture_output=True, text=True, check=False)
    check("a missing -C exits 2", completed.returncode == 2, completed.stderr)
finally:
    shutil.rmtree(scratch, ignore_errors=True)

if failures:
    print(f"{len(failures)} case(s) failed: " + ", ".join(failures))
    sys.exit(1)
print("all cases passed")
