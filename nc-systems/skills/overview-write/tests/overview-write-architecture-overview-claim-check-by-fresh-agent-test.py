#!/usr/bin/env python3
"""Check the overview claim check's stages, its refusals and the reports it writes.

Each case runs the program in a disposable git repository. A stand-in `claude`,
first on PATH, logs the prompt it is given and prints a canned report; the
repository's own scripts/md-drift-lint.py is a stand-in that exits as the case
asks. No case runs a model or touches the log-store.

Run: python3 nc-systems/skills/overview-write/tests/overview-write-architecture-overview-claim-check-by-fresh-agent-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
_removal_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[4] / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_removal_module = importlib.util.module_from_spec(_removal_spec)
_removal_spec.loader.exec_module(_removal_module)
_removal_module.remove_git_redirecting_environment_variables_from_this_process()
PROGRAM = Path(__file__).resolve().parents[1] / "overview-write-architecture-overview-claim-check-by-fresh-agent.py"
_spec = importlib.util.spec_from_file_location("overview_claim_check", PROGRAM)
claim_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(claim_check)

OVERVIEW = "docs/nedschorus-wiki/nedschorus-example-architecture-overview.md"
CONTROL_VARIABLE = "OVERVIEW_CLAIM_CHECK_TEST_CONTROL_DIRECTORY"
TIMEOUT_SECONDS = 120
failures = []

STAND_IN_CLAUDE = f"""#!{sys.executable}
import json, os, pathlib, sys
control = pathlib.Path(os.environ[{CONTROL_VARIABLE!r}])
with (control / "claude-calls.jsonl").open("a", encoding="utf-8") as log:
    log.write(json.dumps({{"argv": sys.argv[1:], "stdin": sys.stdin.read(), "cwd": os.getcwd(),
                          "overview_there": pathlib.Path({OVERVIEW!r}).read_text(encoding="utf-8")}}) + "\\n")
answer = json.loads((control / "claude.json").read_text(encoding="utf-8"))
__import__("time").sleep(answer.get("sleep_seconds", 0))
sys.stdout.write(answer["stdout"])
sys.stderr.write(answer.get("stderr", ""))
sys.exit(answer.get("exit_code", 0))
"""

STAND_IN_MD_DRIFT_LINT = f"""#!/usr/bin/env python3
import json, os, pathlib, sys
control = pathlib.Path(os.environ[{CONTROL_VARIABLE!r}])
answer = json.loads((control / "lint.json").read_text(encoding="utf-8"))
(control / "lint-calls.txt").open("a").write(" ".join(sys.argv[1:]) + "\\n")
__import__("time").sleep(answer.get("sleep_seconds", 0))
sys.stdout.write(answer["stdout"])
sys.exit(answer["exit_code"])
"""

GOOD_REPORT = "VERDICT 1 supported: the program exists\n  nc-systems/example/tool.py:1 `x = 1`\nCOUNTS supported=1 contradicted=0 unsupported=0\n"


def check(name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + ("" if condition else f": {detail}"))
    if not condition:
        failures.append(name)


class Fixture:
    def __init__(self, root):
        self.root = root
        self.repository = root / "repository"
        self.control = root / "control"
        self.reports = root / "reports"
        binaries = root / "bin"
        for directory in (self.repository, self.control, binaries):
            directory.mkdir()
        (binaries / "claude").write_text(STAND_IN_CLAUDE, encoding="utf-8")
        (binaries / "claude").chmod(0o755)
        self.environment = {**os.environ, "PATH": f"{binaries}{os.pathsep}{os.environ['PATH']}",
                            CONTROL_VARIABLE: str(self.control), "PYTHONDONTWRITEBYTECODE": "1"}
        self.git("init", "-q", "-b", "main")
        self.write("nc-systems/example/tool.py", "x = 1\n")
        self.write("scripts/md-drift-lint.py", STAND_IN_MD_DRIFT_LINT)
        self.code_commit = self.commit("code")

    def git(self, *arguments):
        result = subprocess.run(["git", "-C", str(self.repository), "-c", "user.name=fixture",
                                 "-c", "user.email=fixture@nedschorus.invalid", "-c", "core.hooksPath=/dev/null",
                                 *arguments], env=self.environment, capture_output=True, text=True,
                                timeout=TIMEOUT_SECONDS)
        if result.returncode:
            raise AssertionError(f"fixture git {arguments}: {result.stderr}")
        return result.stdout.strip()

    def write(self, path, text):
        (self.repository / path).parent.mkdir(parents=True, exist_ok=True)
        (self.repository / path).write_text(text, encoding="utf-8")

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def commit_overview(self, checked_against=None, body="# Example overview\n\nThe example system.\n"):
        line = "" if checked_against is False else "\n" + claim_check.overview_path_reader.CHECKED_AGAINST_LINE_TEMPLATE.format(
            commit=checked_against or self.code_commit) + "\n"
        self.write(OVERVIEW, body + line)
        return self.commit("overview")

    def answer(self, *, claude_stdout=GOOD_REPORT, claude_exit=0, lint_stdout="", lint_exit=0,
               claude_sleep=0, lint_sleep=0):
        (self.control / "claude.json").write_text(json.dumps(
            {"stdout": claude_stdout, "exit_code": claude_exit, "sleep_seconds": claude_sleep}))
        (self.control / "lint.json").write_text(json.dumps(
            {"stdout": lint_stdout, "exit_code": lint_exit, "sleep_seconds": lint_sleep}))
        for log in ("claude-calls.jsonl", "lint-calls.txt"):
            (self.control / log).unlink(missing_ok=True)

    def claude_calls(self):
        log = self.control / "claude-calls.jsonl"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def run(self, *arguments, report_directory=None):
        return subprocess.run(
            [sys.executable, str(PROGRAM), "--overview", OVERVIEW,
             "--report-directory", str(report_directory or self.reports), *arguments],
            cwd=self.repository, env=self.environment, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)

    def run_in_process_with_timeouts(self, *, fresh_agent_seconds, lint_seconds):
        """Run main() here, so a test can shorten a timeout the program cannot be told from outside."""
        saved = (claim_check.FRESH_AGENT_TIMEOUT_SECONDS, claim_check.MD_DRIFT_LINT_TIMEOUT_SECONDS,
                 dict(os.environ), os.getcwd())
        claim_check.FRESH_AGENT_TIMEOUT_SECONDS, claim_check.MD_DRIFT_LINT_TIMEOUT_SECONDS = fresh_agent_seconds, lint_seconds
        os.environ.clear()
        os.environ.update(self.environment)
        os.chdir(self.repository)
        try:
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                code = claim_check.main(["--overview", OVERVIEW, "--report-directory", str(self.reports)])
            return code, stderr.getvalue()
        finally:
            claim_check.FRESH_AGENT_TIMEOUT_SECONDS, claim_check.MD_DRIFT_LINT_TIMEOUT_SECONDS = saved[0], saved[1]
            os.environ.clear()
            os.environ.update(saved[2])
            os.chdir(saved[3])

    def reports_written(self):
        return sorted(self.reports.rglob("*.md")) if self.reports.exists() else []

    def worktrees(self):
        return self.git("worktree", "list", "--porcelain").count("worktree ")


def run_unit_cases():
    result = claim_check.result_from_fresh_agent_report
    check("every claim supported gives the all-supported result", result(GOOD_REPORT) == claim_check.OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED)
    check("a contradicted claim gives the counts that fall short",
          result("VERDICT 1 supported: a\nVERDICT 2 contradicted: b\nCOUNTS supported=1 contradicted=1 unsupported=0\n")
          == "not all claims supported: 1 contradicted, 0 unsupported, 1 supported")
    check("a COUNTS line that disagrees with the VERDICT lines is malformed",
          result("VERDICT 1 supported: a\nCOUNTS supported=2 contradicted=0 unsupported=0\n").startswith("malformed: the COUNTS line"))
    check("VERDICT lines out of order are malformed",
          result("VERDICT 2 supported: a\nCOUNTS supported=1 contradicted=0 unsupported=0\n").startswith("malformed: the VERDICT lines"))
    check("no VERDICT line is malformed", result("I could not check it.\n") == "malformed: no VERDICT line")
    check("a missing COUNTS line is malformed", result("VERDICT 1 supported: a\n") == "malformed: 0 COUNTS lines, not one")
    check("the how-to page matches the template, so callers must check nc-systems/<system>",
          claim_check.architecture_overview_system_from_path(
              "docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md") == "how-to-write-an")
    check("a proposed-improvements file beside an overview is not an overview path",
          claim_check.architecture_overview_system_from_path(
              "docs/nedschorus-wiki/nedschorus-handoff-architecture-overview-proposed-improvements-or-changes-x.md") is None)


def run_program_cases(fixture):
    head = fixture.commit_overview()
    blob = fixture.git("rev-parse", f"{head}:{OVERVIEW}")
    worktrees_before = fixture.worktrees()

    fixture.answer()
    result = fixture.run()
    reports = fixture.reports_written()
    calls = fixture.claude_calls()
    check("every claim supported exits 0 and writes one report named by the overview's blob",
          result.returncode == 0 and len(reports) == 1 and reports[0].name.startswith(blob + "-"), result.stderr)
    header = reports[0].read_text().split("\n\n", 1)[0] if reports else ""
    check("the report's header names the overview, the commit checked against and the result",
          f"checked against: {fixture.code_commit}" in header
          and f"{claim_check.RESULT_LINE_PREFIX}{claim_check.OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED}" in header, header)
    check("the reader finds that report and its result for the overview's blob",
          claim_check.find_newest_architecture_overview_claim_check_report_path_and_result_for_overview_git_blob(fixture.reports, OVERVIEW, blob)
          == (reports[0], claim_check.OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED) if reports else False)
    check("the fresh-agent runs once, at the checked-against commit, with the overview's text in place",
          len(calls) == 1 and "The example system." in calls[0]["overview_there"]
          and fixture.code_commit in calls[0]["stdin"] and claim_check.HOW_TO_PAGE in calls[0]["stdin"], calls)
    check("the fresh-agent's whole tool set is Read, Grep and Glob, so it cannot start subagents, and hooks are off",
          len(calls) == 1 and calls[0]["argv"][calls[0]["argv"].index("--tools") + 1] == "Read,Grep,Glob"
          and '"disableAllHooks": true' in calls[0]["argv"][calls[0]["argv"].index("--settings") + 1], calls)
    check("the temporary worktree is removed after a run", fixture.worktrees() == worktrees_before)

    fixture.answer(claude_stdout="VERDICT 1 contradicted: the program exists\nCOUNTS supported=0 contradicted=1 unsupported=0\n")
    result = fixture.run()
    newest = claim_check.find_newest_architecture_overview_claim_check_report_path_and_result_for_overview_git_blob(fixture.reports, OVERVIEW, blob)
    check("a contradicted claim exits 5, and the newest report says so",
          result.returncode == 5 and newest[1].startswith("not all claims supported: 1 contradicted"), (result, newest))

    fixture.answer(claude_stdout="I ran out of time.\n")
    result = fixture.run()
    newest = claim_check.find_newest_architecture_overview_claim_check_report_path_and_result_for_overview_git_blob(fixture.reports, OVERVIEW, blob)
    check("a malformed report exits 5 and is kept with a malformed result",
          result.returncode == 5 and newest[1] == "malformed: no VERDICT line", (result, newest))

    count = len(fixture.reports_written())
    fixture.answer(claude_stdout="", claude_exit=1)
    (fixture.control / "claude.json").write_text(json.dumps({"stdout": "", "stderr": "Not logged in", "exit_code": 1}))
    result = fixture.run()
    check("a fresh-agent that fails exits 4, quotes its stderr and writes no report",
          result.returncode == 4 and "Not logged in" in result.stderr and len(fixture.reports_written()) == count, result.stderr)
    check("the temporary worktree is removed after a failed run", fixture.worktrees() == worktrees_before)
    (fixture.control / "claude.json").write_text(json.dumps({"stdout": GOOD_REPORT, "exit_code": 1}))
    result = fixture.run()
    check("a fresh-agent that exits nonzero after printing a report still writes no report",
          result.returncode == 4 and len(fixture.reports_written()) == count, result.stderr)
    fixture.answer(claude_stdout="  \n")
    result = fixture.run()
    check("a fresh-agent that exits 0 with no output writes no report",
          result.returncode == 4 and len(fixture.reports_written()) == count, result.stderr)
    bare_binaries = fixture.root / "bin-without-claude"
    bare_binaries.mkdir()
    (bare_binaries / "git").symlink_to(shutil.which("git"))
    fixture.answer()
    no_claude = subprocess.run(
        [sys.executable, str(PROGRAM), "--overview", OVERVIEW, "--report-directory", str(fixture.reports)],
        cwd=fixture.repository, env={**fixture.environment, "PATH": str(bare_binaries)},
        capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    check("no `claude` on PATH exits 4 with what to fix, and writes no report",
          no_claude.returncode == 4 and "could not run" in no_claude.stderr
          and len(fixture.reports_written()) == count, no_claude.stderr)
    fixture.answer(claude_sleep=5)
    code, stderr = fixture.run_in_process_with_timeouts(fresh_agent_seconds=1, lint_seconds=60)
    check("a fresh-agent that runs past its timeout exits 4 and writes no report",
          code == 4 and "could not run" in stderr and len(fixture.reports_written()) == count, stderr)
    fixture.answer(lint_sleep=5)
    code, stderr = fixture.run_in_process_with_timeouts(fresh_agent_seconds=60, lint_seconds=1)
    check("md-drift-lint that runs past its timeout exits 4 and runs no fresh-agent",
          code == 4 and "did not finish" in stderr and not fixture.claude_calls(), stderr)
    check("the temporary worktree is removed after a timeout", fixture.worktrees() == worktrees_before)
    result = fixture.run("--revision", fixture.code_commit)
    check("a revision that does not hold the overview is refused", result.returncode == 1
          and "is not in" in result.stderr and not fixture.claude_calls(), result.stderr)

    fixture.answer(lint_stdout=f"{OVERVIEW}:3: `nc-systems/example/gone.py` does not exist\n", lint_exit=1)
    result = fixture.run()
    check("md-drift-lint findings exit 3 before any fresh-agent runs, with the findings printed",
          result.returncode == 3 and not fixture.claude_calls() and "gone.py` does not exist" in result.stderr
          and len(fixture.reports_written()) == count, result.stderr)
    fixture.answer(lint_stdout="GitHub could not be queried\n", lint_exit=3)
    result = fixture.run()
    check("md-drift-lint that cannot finish exits 4 and runs no fresh-agent",
          result.returncode == 4 and not fixture.claude_calls(), result.stderr)

    answers = fixture.root / "writer-answers.md"
    answers.write_text("Verdict 1 is wrong: nc-systems/example/tool.py:1 `x = 1`\n")
    fixture.answer()
    result = fixture.run("--writer-answers", str(answers))
    calls = fixture.claude_calls()
    check("--writer-answers names the answers file in the fresh-agent's prompt and in the report",
          result.returncode == 0 and len(calls) == 1 and str(answers.resolve()) in calls[0]["stdin"]
          and f"writer answers: {answers.resolve()}" in claim_check.find_newest_architecture_overview_claim_check_report_path_and_result_for_overview_git_blob(
              fixture.reports, OVERVIEW, blob)[0].read_text(), result.stderr)

    fixture.answer()
    result = fixture.run("--writer-answers", str(fixture.root / "missing.md"))
    check("a --writer-answers file that does not exist is refused", result.returncode == 1 and not fixture.claude_calls(), result.stderr)
    result = fixture.run(report_directory=fixture.root / "no-such-log-store" / "reports")
    check("a report directory whose parent is missing is refused, naming ned-box",
          result.returncode == 1 and "ned-box" in result.stderr and not fixture.claude_calls(), result.stderr)
    result = subprocess.run([sys.executable, str(PROGRAM), "--overview",
                             "docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md",
                             "--report-directory", str(fixture.reports)], cwd=fixture.repository,
                            env=fixture.environment, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    check("a path with no nc-systems/<system> directory is refused as not an overview",
          result.returncode == 1 and "is not an nc-architecture-overview" in result.stderr, result.stderr)

    fixture.commit_overview(checked_against=False)
    result = fixture.run()
    check("an overview with no **Checked against:** line is refused", result.returncode == 1
          and "no **Checked against:** last line" in result.stderr and not fixture.claude_calls(), result.stderr)
    fixture.commit_overview(checked_against="1" * 40)
    result = fixture.run()
    check("a **Checked against:** commit missing from the repository is refused with the fetch command",
          result.returncode == 1 and "fetch origin" in result.stderr and not fixture.claude_calls(), result.stderr)
    result = fixture.run("--revision", "no-such-branch")
    check("a revision that does not exist is refused with git's words",
          result.returncode == 1 and "git rev-parse" in result.stderr, result.stderr)
    result = fixture.run("--no-such-flag")
    check("a malformed argument is refused with exit 1, not the program-defect exit",
          result.returncode == 1 and "--help" in result.stderr, result.stderr)


def main():
    run_unit_cases()
    with tempfile.TemporaryDirectory(prefix="overview-claim-check-test-") as temporary:
        run_program_cases(Fixture(Path(temporary)))
    print(f"{len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
