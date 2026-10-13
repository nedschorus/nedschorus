#!/usr/bin/env python3
"""Tests for scripts/run-codex-task-from-brief.py, with a fake `codex` on PATH.

The fake records its arguments and, by the FAKE_CODEX_MODE environment
variable, writes a report, fails with or without a report, writes nothing,
sleeps past the deadline with a child that may ignore SIGTERM, or blocks
reading stdin. Each case runs the real program as a process.

Run: python3 scripts/run-codex-task-from-brief-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROGRAM = Path(__file__).with_name("run-codex-task-from-brief.py")

FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, signal, sys, time
arguments = sys.argv[1:]
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
    checkout = scratch / "checkout"
    checkout.mkdir()
    brief = scratch / "brief.md"
    brief.write_text("Do the task.\nSecond line.\n")
    arguments_file = scratch / "arguments.json"
    child_pid_file = scratch / "child.pid"

    def run(mode, *extra, stdin=None, timeout=60):
        environment = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                           FAKE_CODEX_MODE=mode,
                           FAKE_CODEX_ARGUMENTS_FILE=str(arguments_file),
                           FAKE_CODEX_CHILD_PID_FILE=str(child_pid_file))
        report = scratch / f"report-{mode}.md"
        started = time.monotonic()
        completed = subprocess.run(
            [sys.executable, str(PROGRAM), "-C", str(checkout), "--brief", str(brief),
             "-o", str(report), *extra],
            env=environment, stdin=stdin, capture_output=True, text=True,
            timeout=timeout, check=False)
        return completed, report, time.monotonic() - started

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
                       FAKE_CODEX_MODE="report", FAKE_CODEX_ARGUMENTS_FILE=str(arguments_file))
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

    child_pid_file.unlink(missing_ok=True)
    completed, report, elapsed = run("sleep", "--deadline-minutes", "0.05")
    child_pid = int(child_pid_file.read_text()) if child_pid_file.exists() else None
    time.sleep(0.5)
    child_alive = False
    if child_pid:
        try:
            os.kill(child_pid, 0)
            child_alive = True
        except ProcessLookupError:
            pass
    check("the deadline stops Codex, exits 1 and says so",
          completed.returncode == 1 and "deadline" in completed.stderr and elapsed < 30,
          f"exit {completed.returncode}, {elapsed:.1f}s, stderr {completed.stderr!r}")
    check("the deadline also stops the processes Codex started",
          child_pid is not None and not child_alive, f"child {child_pid} alive={child_alive}")

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

    # The caller's own stdin is an open pipe that never closes; the fake must still see EOF.
    holder = subprocess.Popen(["sleep", "60"], stdout=subprocess.PIPE)
    try:
        completed, report, elapsed = run("read-stdin", stdin=holder.stdout, timeout=30)
    except subprocess.TimeoutExpired:
        completed, elapsed = None, 30
    finally:
        holder.kill()
        holder.wait()
    check("Codex's stdin is closed even when the caller's stdin is an open pipe",
          completed is not None and completed.returncode == 0
          and report.read_text().strip() == "stdin held 0 characters",
          f"completed {completed!r}")

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
