#!/usr/bin/env python3
"""Tests for nc-systems/skills/explain/explain-reply-cold-read-fast-read.py.

The program under test runs the cold-read-fast-read on a draft /explain reply
and prints only the part of the report the explain skill acts on. The fast
read itself is replaced by a stand-in program named through the program's
test seam, EXPLAIN_REPLY_COLD_READ_FAST_READ_PROGRAM_OVERRIDE. The stand-in
records what it was given and answers as the plan in its environment says.
Its report is `fast-read-report-captured-2026-09-29.md` in
`explain-reply-cold-read-fast-read-fixtures/` beside this test, a real report
captured from the real fast read; the capture note beside it records how.

Each case names its oracle, what it compares, and its red condition, the
reading that means the program is wrong.

The timeout case imports the program and lowers its timeout constant, because
the real limit is nine minutes; the case runs the stand-in as a process that
starts a child of its own, so the case sees whether the whole process group
was stopped, not only the direct child.

Run: python3 nc-systems/skills/explain/tests/explain-reply-cold-read-fast-read-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

TESTS_DIRECTORY = pathlib.Path(__file__).resolve().parent
SKILL_DIRECTORY = TESTS_DIRECTORY.parent
REPO_ROOT = SKILL_DIRECTORY.parent.parent.parent
PROGRAM = SKILL_DIRECTORY / "explain-reply-cold-read-fast-read.py"
FIXTURE_REPORT = (TESTS_DIRECTORY / "explain-reply-cold-read-fast-read-fixtures"
                  / "fast-read-report-captured-2026-09-29.md")
OVERRIDE_VARIABLE = "EXPLAIN_REPLY_COLD_READ_FAST_READ_PROGRAM_OVERRIDE"

# A sentence that appears in the fixture's Question 1 section only, and one
# that appears in its Question 2 section only; checked against the fixture
# below so a changed fixture cannot make the cases pass vacuously.
QUESTION_1_ONLY_TEXT = "## Question 1: What it says"
QUESTION_2_HEADING = "## Question 2: Where you struggled"
QUESTION_3_HEADING = "## Question 3: What it does not cover that it implies it should"
COVERAGE_HEADING = "## Sentence coverage (added by cold-read-fast-read)"

GOOD_INPUT = (
    'The user wrote: "what does block mean here?"\n'
    "The reply to him:\n"
    "Block means the launcher refuses to start the seat.\n"
    "Nothing needs you.\n"
)

STAND_IN_SOURCE = r'''#!/usr/bin/env python3
import json, os, pathlib, shutil, subprocess, sys, time
plan = json.loads(os.environ["STAND_IN_PLAN"])
log = pathlib.Path(os.environ["STAND_IN_LOG"])
target = pathlib.Path(sys.argv[sys.argv.index("--target") + 1])
log.write_text(json.dumps({
    "argv": sys.argv[1:],
    "cwd": os.getcwd(),
    "target_name": target.name,
    "target_text": target.read_text(),
    "target_directory": str(target.parent),
}))
if plan.get("start_child_then_hang"):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    pathlib.Path(plan["child_pid_file"]).write_text(str(child.pid))
    time.sleep(120)
if "report_source" in plan:
    report = pathlib.Path(plan["report_copy"])
    shutil.copyfile(plan["report_source"], report)
    print("stand-in progress line", file=sys.stderr)
    print(plan.get("record_line", "cold-read-fast-read: record: FAILED: ned-box "
          "could not be reached; the record stays on disk."), file=sys.stderr)
    print(report)
    sys.exit(0)
print(plan.get("stdout", ""), end="")
print(plan.get("stderr", ""), end="", file=sys.stderr)
sys.exit(plan.get("exit", 0))
'''

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}{': ' + detail if detail else ''}")
        failures.append(case_name)


def write_stand_in(directory: pathlib.Path) -> pathlib.Path:
    stand_in = directory / "fast-read-stand-in.py"
    stand_in.write_text(STAND_IN_SOURCE)
    stand_in.chmod(0o755)
    return stand_in


def run_program(directory: pathlib.Path, plan: dict, stdin_text: str, arguments=()):
    stand_in = write_stand_in(directory)
    log = directory / "stand-in-log.json"
    if log.exists():
        log.unlink()
    environment = dict(os.environ)
    environment[OVERRIDE_VARIABLE] = str(stand_in)
    environment["STAND_IN_PLAN"] = json.dumps(plan)
    environment["STAND_IN_LOG"] = str(log)
    # Run from outside the repository, so the case on the working directory
    # sees the program set the directory itself rather than inherit it.
    completed = subprocess.run(
        [sys.executable, str(PROGRAM), *arguments], input=stdin_text,
        capture_output=True, text=True, env=environment, check=False, timeout=60,
        cwd=directory)
    logged = json.loads(log.read_text()) if log.exists() else None
    return completed, logged


def load_program_module():
    specification = importlib.util.spec_from_file_location(
        "explain_reply_cold_read_fast_read", PROGRAM)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def main() -> int:
    fixture_text = FIXTURE_REPORT.read_text()
    check("fixture holds the four headings the cases rely on",
          all(heading in fixture_text for heading in
              (QUESTION_1_ONLY_TEXT, QUESTION_2_HEADING, QUESTION_3_HEADING,
               COVERAGE_HEADING)))

    with tempfile.TemporaryDirectory() as scratch:
        scratch = pathlib.Path(scratch)
        report_copy = scratch / "fast-read.md"
        success_plan = {"report_source": str(FIXTURE_REPORT),
                        "report_copy": str(report_copy)}

        # Oracle: stdout against the fixture's sections. Red: Question 1
        # printed, or Question 2, Question 3 or the coverage section missing.
        completed, logged = run_program(scratch, success_plan, GOOD_INPUT)
        output = completed.stdout
        check("success exits 0", completed.returncode == 0,
              f"exit {completed.returncode}, stdout {output!r}")
        check("success leaves out Question 1", QUESTION_1_ONLY_TEXT not in output)
        check("success prints Question 2, Question 3 and the coverage section",
              all(heading in output for heading in
                  (QUESTION_2_HEADING, QUESTION_3_HEADING, COVERAGE_HEADING)))
        expected_tail = fixture_text[fixture_text.index(QUESTION_2_HEADING):].strip("\n")
        check("success prints the report from Question 2 to the end, unchanged",
              expected_tail in output)
        check("success opens on the Question 2 heading",
              output.startswith(QUESTION_2_HEADING), output[:80])
        check("success names the report's path and says not to cite the report",
              f"Report: {report_copy}" in output
              and "Do not cite this report to the user unless he asks." in output)
        check("success keeps the fast read's progress lines off stdout",
              "stand-in progress line" not in output)
        check("success passes on the fast read's record-shipping line",
              "cold-read-fast-read: record: FAILED: ned-box could not be reached; "
              "the record stays on disk." in output, output[-400:])
        check("a record line saying FAILED is followed by the instruction to tell him",
              "cold-read-fast-read: record: FAILED: ned-box could not be reached; "
              "the record stays on disk.\nTell the user what the record line above "
              "says, remedy included, before your closing line." in output,
              output[-400:])

        # Oracle: stdout. Red: the tell-him instruction printed after a record
        # line that says the record arrived.
        shipped_line = ("cold-read-fast-read: record: shipped: explain-reply-draft-"
                        "2026-09-30 — 3 file(s) added")
        completed, _ = run_program(
            scratch, dict(success_plan, record_line=shipped_line), GOOD_INPUT)
        check("a record line saying shipped carries no instruction",
              shipped_line in completed.stdout
              and "Tell the user what the record line" not in completed.stdout,
              completed.stdout[-400:])

        # Oracle: what the stand-in logged. Red: a different file name, text,
        # working directory or argument list than the program promises.
        check("the fast read gets exactly --target <file>",
              logged is not None and logged["argv"][0] == "--target"
              and len(logged["argv"]) == 2, str(logged))
        check("the draft file is named explain-reply-draft.md",
              logged is not None and logged["target_name"] == "explain-reply-draft.md",
              str(logged))
        check("the draft file holds standard input unchanged",
              logged is not None and logged["target_text"] == GOOD_INPUT)
        check("the fast read runs from the repository root",
              logged is not None
              and pathlib.Path(logged["cwd"]).resolve() == REPO_ROOT, str(logged))
        check("the draft file is outside the repository",
              logged is not None
              and not pathlib.Path(logged["target_directory"]).resolve()
              .is_relative_to(REPO_ROOT))
        check("the temporary directory is deleted afterwards",
              logged is not None
              and not pathlib.Path(logged["target_directory"]).exists())

        # Oracle: stdout and exit code. Red: exit 0, or no instruction to send
        # anyway, or the fast read's FAILED line not passed on.
        failed_line = "FAILED (exit 1 from the fast-clarify cell; no report)"
        completed, _ = run_program(
            scratch, {"stdout": failed_line + "\n", "exit": 1}, GOOD_INPUT)
        check("a FAILED fast read exits 1", completed.returncode == 1,
              f"exit {completed.returncode}")
        check("a FAILED fast read says to send the reply anyway, in the skill's words",
              "Send your reply anyway, with one line before your closing line "
              "saying the fresh-reader's read failed." in completed.stdout,
              completed.stdout)
        check("a FAILED fast read passes its FAILED line on",
              failed_line in completed.stdout, completed.stdout)

        completed, _ = run_program(scratch, {"stdout": "", "exit": 0}, GOOD_INPUT)
        check("a fast read that exits 0 printing nothing counts as failed",
              completed.returncode == 1 and "Send your reply anyway" in completed.stdout,
              f"exit {completed.returncode}, stdout {completed.stdout!r}")

        missing_report = scratch / "no-such-report.md"
        completed, _ = run_program(
            scratch, {"stdout": f"{missing_report}\n", "exit": 0}, GOOD_INPUT)
        check("a report path that cannot be read counts as failed",
              completed.returncode == 1 and str(missing_report) in completed.stdout,
              f"exit {completed.returncode}, stdout {completed.stdout!r}")

        # Oracle: exit code and stdout. Red: a traceback, or no instruction to
        # send anyway, when the fast read program cannot be started.
        environment = dict(os.environ)
        environment[OVERRIDE_VARIABLE] = str(scratch / "no-such-fast-read-program")
        completed = subprocess.run(
            [sys.executable, str(PROGRAM)], input=GOOD_INPUT, capture_output=True,
            text=True, env=environment, check=False, timeout=60, cwd=scratch)
        check("a fast read program that cannot be started counts as failed",
              completed.returncode == 1 and "Send your reply anyway" in completed.stdout
              and "Traceback" not in completed.stderr
              and "could not start" in completed.stdout,
              f"exit {completed.returncode}, stdout {completed.stdout!r}, "
              f"stderr {completed.stderr[-300:]!r}")

        # Oracle: stdout. Red: a report with no Question 2 heading prints
        # nothing of the report.
        headless = scratch / "headless-report.md"
        headless.write_text("A report whose model skipped the headings.\n")
        completed, _ = run_program(
            scratch, {"stdout": f"{headless}\n", "exit": 0}, GOOD_INPUT)
        check("a report with no Question 2 heading is printed whole",
              completed.returncode == 0
              and "A report whose model skipped the headings." in completed.stdout,
              completed.stdout)

        # Oracle: exit code and whether the stand-in ran. Red: exit other
        # than 64, or the stand-in launched on input it should refuse.
        refused_inputs = {
            "input not opening with the user's words":
                "The reply to him:\nSome reply.\n",
            "input with no reply label":
                'The user wrote: "why?"\nSome reply.\n',
            "input with nothing after the reply label":
                'The user wrote: "why?"\nThe reply to him:\n   \n',
            "empty input": "",
        }
        for case_name, text in refused_inputs.items():
            completed, logged = run_program(scratch, success_plan, text)
            check(f"{case_name} exits 64 and launches nothing",
                  completed.returncode == 64 and logged is None
                  and "Nothing was run." in completed.stdout,
                  f"exit {completed.returncode}, launched {logged is not None}")
        completed, logged = run_program(scratch, success_plan, GOOD_INPUT,
                                        arguments=("--target", "x.md"))
        check("any argument exits 64 and launches nothing",
              completed.returncode == 64 and logged is None,
              f"exit {completed.returncode}, launched {logged is not None}")

        # Oracle: the return value, the elapsed time and the child process.
        # Red: no timeout reported, a wait near the stand-in's 120 s, or the
        # stand-in's own child still alive after the timeout.
        module = load_program_module()
        module.FAST_READ_TIMEOUT_SECONDS = 2
        child_pid_file = scratch / "child.pid"
        stand_in = write_stand_in(scratch)
        draft = scratch / "explain-reply-draft.md"
        draft.write_text(GOOD_INPUT)
        saved_environment = dict(os.environ)
        os.environ[OVERRIDE_VARIABLE] = str(stand_in)
        os.environ["STAND_IN_PLAN"] = json.dumps(
            {"start_child_then_hang": True, "child_pid_file": str(child_pid_file)})
        os.environ["STAND_IN_LOG"] = str(scratch / "timeout-log.json")
        try:
            started = time.monotonic()
            exit_code, _, _ = module.run_fast_read(draft)
            elapsed = time.monotonic() - started
        finally:
            os.environ.clear()
            os.environ.update(saved_environment)
        check("a fast read past the timeout is reported as a timeout",
              exit_code is None, f"exit code {exit_code}")
        check("the timeout returns within seconds of the limit",
              elapsed < 20, f"{elapsed:.1f} s")
        child_pid = int(child_pid_file.read_text()) if child_pid_file.exists() else None
        child_stopped = False
        if child_pid is not None:
            for _ in range(50):
                if not process_is_alive(child_pid):
                    child_stopped = True
                    break
                time.sleep(0.1)
        check("the timeout stops the fast read's whole process group",
              child_pid is not None and child_stopped,
              f"child pid {child_pid}, stopped {child_stopped}")
        if child_pid is not None and not child_stopped:
            os.kill(child_pid, 9)

    print(f"{len(failures)} failed" if failures else "all cases pass")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
