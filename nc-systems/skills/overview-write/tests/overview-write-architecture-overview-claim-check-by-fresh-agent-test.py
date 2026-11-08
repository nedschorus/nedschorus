#!/usr/bin/env python3
"""Check the overview claim check's stages, its refusals and the reports it writes.

Each case runs the program in a disposable git repository. A stand-in `claude`,
first on PATH, logs the prompt it is given and prints a canned report, or, for
a recheck prompt naming an assertion the case lists, that assertion's canned
answer; the
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
import re
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
PROPOSALS = "nc-systems/example/docs/example-architecture-overview-proposed-improvements-or-changes-entries.md"
CONTROL_VARIABLE = "OVERVIEW_CLAIM_CHECK_TEST_CONTROL_DIRECTORY"
TIMEOUT_SECONDS = 120
RECHECK_SLEEP_SECONDS = 3
failures = []

STAND_IN_CLAUDE = f"""#!{sys.executable}
import json, os, pathlib, sys
control = pathlib.Path(os.environ[{CONTROL_VARIABLE!r}])
prompt = sys.stdin.read()
with (control / "claude-calls.jsonl").open("a", encoding="utf-8") as log:
    log.write(json.dumps({{"argv": sys.argv[1:], "stdin": prompt, "cwd": os.getcwd(), "started": __import__("time").time(),
                          "overview_there": pathlib.Path({OVERVIEW!r}).read_text(encoding="utf-8")}}) + "\\n")
answer = json.loads((control / "claude.json").read_text(encoding="utf-8"))
for assertion, recheck in answer.get("rechecks", {{}}).items():
    if f"The assertion: {{assertion}}\\n" in prompt:
        answer = recheck
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
UNSUPPORTED_REPORT = "VERDICT 1 unsupported must-fix: the program exists\nCOUNTS supported=0 contradicted=0 unsupported=1\n"


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
        self.git("update-ref", "refs/remotes/origin/main", self.code_commit)

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
               claude_sleep=0, lint_sleep=0, rechecks=None):
        """rechecks maps an assertion to the {"stdout", "exit_code"} the stand-in gives a recheck prompt naming it."""
        (self.control / "claude.json").write_text(json.dumps(
            {"stdout": claude_stdout, "exit_code": claude_exit, "sleep_seconds": claude_sleep,
             "rechecks": rechecks or {}}))
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

    def run_in_process_with_timeouts(self, *, fresh_agent_seconds=60, lint_seconds=60, run_git=None):
        """Run main() here, so a test can shorten a timeout or replace run_git, which the program cannot be told from outside."""
        saved = (claim_check.FRESH_AGENT_TIMEOUT_SECONDS, claim_check.MD_DRIFT_LINT_TIMEOUT_SECONDS,
                 dict(os.environ), os.getcwd(), claim_check.run_git)
        claim_check.FRESH_AGENT_TIMEOUT_SECONDS, claim_check.MD_DRIFT_LINT_TIMEOUT_SECONDS = fresh_agent_seconds, lint_seconds
        claim_check.run_git = run_git or claim_check.run_git
        os.environ.clear()
        os.environ.update(self.environment)
        os.chdir(self.repository)
        try:
            with contextlib.redirect_stderr(io.StringIO()) as stderr, contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = claim_check.main(["--overview", OVERVIEW, "--report-directory", str(self.reports)])
            self.last_in_process_stdout = stdout.getvalue()
            return code, stderr.getvalue()
        finally:
            claim_check.FRESH_AGENT_TIMEOUT_SECONDS, claim_check.MD_DRIFT_LINT_TIMEOUT_SECONDS = saved[0], saved[1]
            claim_check.run_git = saved[4]
            os.environ.clear()
            os.environ.update(saved[2])
            os.chdir(saved[3])

    def reports_written(self):
        return sorted(self.reports.rglob("*.md")) if self.reports.exists() else []

    def worktrees(self):
        return self.git("worktree", "list", "--porcelain").count("worktree ")


def recheck(verdict_and_rank, assertion="b"):
    verdict = verdict_and_rank.split()[0]
    counts = " ".join(f"{name}={int(name == verdict)}" for name in claim_check.VERDICTS)
    return f"VERDICT 1 {verdict_and_rank}: {assertion}\nCOUNTS {counts}\n"


def run_unit_cases():
    def result(report, rechecks=None):
        return claim_check.result_from_fresh_agent_report(report, rechecks)[1]

    all_supported = claim_check.OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED
    no_must_fix = claim_check.OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_NO_MUST_FIX_CLAIM_REMAINS
    must_fix_report = "VERDICT 1 supported: a\nVERDICT 2 contradicted must-fix: b\nCOUNTS supported=1 contradicted=1 unsupported=0\n"
    check("every claim supported gives the all-supported result", result(GOOD_REPORT) == all_supported)
    check("a must-fix claim the recheck ranks must-fix again gives the counts of what remains",
          result(must_fix_report, {2: recheck("contradicted must-fix")})
          == "must-fix claims remain: 1 must-fix, 0 fix-later, 0 nit")
    claims, _ = claim_check.result_from_fresh_agent_report(must_fix_report, {2: recheck("unsupported fix-later")})
    check("a must-fix claim the recheck ranks fix-later is ranked fix-later, and no must-fix claim remains",
          result(must_fix_report, {2: recheck("unsupported fix-later")}) == no_must_fix
          and claims[1].rank == claim_check.RANK_FIX_LATER, claims)
    check("a must-fix claim the recheck finds supported is ranked fix-later",
          claim_check.result_from_fresh_agent_report(must_fix_report, {2: recheck("supported")})[0][1].rank
          == claim_check.RANK_FIX_LATER)
    check("a must-fix claim the recheck ranks nit is ranked fix-later",
          claim_check.result_from_fresh_agent_report(must_fix_report, {2: recheck("contradicted nit")})[0][1].rank
          == claim_check.RANK_FIX_LATER)
    check("fix-later and nit claims alone leave no must-fix claim, with no recheck",
          result("VERDICT 1 unsupported fix-later: a\nVERDICT 2 contradicted nit: b\n"
                 "COUNTS supported=0 contradicted=1 unsupported=1\n") == no_must_fix)
    check("an unsupported claim with no rank is malformed",
          result("VERDICT 1 unsupported: a\nCOUNTS supported=0 contradicted=0 unsupported=1\n")
          == "malformed: VERDICT 1 is unsupported with the rank missing, not one of must-fix, fix-later, nit")
    check("a claim with a rank outside the three is malformed",
          result("VERDICT 1 contradicted later: a\nCOUNTS supported=0 contradicted=1 unsupported=0\n").startswith(
              "malformed: VERDICT 1 is contradicted with the rank later"))
    check("a supported claim with a rank is malformed",
          result("VERDICT 1 supported nit: a\nCOUNTS supported=1 contradicted=0 unsupported=0\n")
          == "malformed: VERDICT 1 is supported but has the rank nit")
    check("a malformed recheck makes the result malformed",
          result(must_fix_report, {2: "I could not check it.\n"})
          == "malformed: the recheck of VERDICT 2 is malformed: no VERDICT line")
    check("a recheck with two VERDICT lines makes the result malformed",
          result(must_fix_report, {2: "VERDICT 1 supported: b\nVERDICT 2 supported: c\n"
                                      "COUNTS supported=2 contradicted=0 unsupported=0\n"})
          == "malformed: the recheck of VERDICT 2 has 2 VERDICT lines, not one")
    claims, _ = claim_check.claims_from_fresh_agent_report(
        "VERDICT 1 contradicted fix-later: a\n  x.py:3 `y`\nVERDICT 2 supported: b\n  z.py:1 `w`\n"
        "COUNTS supported=1 contradicted=1 unsupported=0\n")
    check("each claim keeps the lines after its VERDICT line as its evidence, without the COUNTS line",
          [claim.evidence for claim in claims] == ["  x.py:3 `y`", "  z.py:1 `w`"], claims)
    check("a COUNTS line that disagrees with the VERDICT lines is malformed",
          result("VERDICT 1 supported: a\nCOUNTS supported=2 contradicted=0 unsupported=0\n").startswith("malformed: the COUNTS line"))
    check("VERDICT lines out of order are malformed",
          result("VERDICT 2 supported: a\nCOUNTS supported=1 contradicted=0 unsupported=0\n").startswith("malformed: the VERDICT lines"))
    check("no VERDICT line is malformed", result("I could not check it.\n") == "malformed: no VERDICT line")
    check("a missing COUNTS line is malformed", result("VERDICT 1 supported: a\n") == "malformed: 0 COUNTS lines, not one")
    check("the how-to page matches the template, so callers must check nc-systems/<system>",
          claim_check.nc_architecture_overview_described_system_name_from_page_path(
              "docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md") == "how-to-write-an")
    check("a proposed-improvements file beside an overview is not an overview path",
          claim_check.nc_architecture_overview_described_system_name_from_page_path(
              "docs/nedschorus-wiki/nedschorus-handoff-architecture-overview-proposed-improvements-or-changes-x.md") is None)
    check("an overview's one proposed-improvements-or-changes-file is in its system's docs/, outside the wiki folder",
          claim_check.architecture_overview_proposed_improvements_or_changes_file_path(OVERVIEW) == PROPOSALS)
    check("the pointer line names the file and its directory in separate backtick spans, so md-drift-lint at an older "
          "commit, where the file is missing, finds no path to check",
          claim_check.overview_pointer_line_to_proposed_improvements_or_changes_file(OVERVIEW)
          == "This document has proposed improvements or changes: read "
             "`example-architecture-overview-proposed-improvements-or-changes-entries.md` in `nc-systems/example/docs/`.")


def last_stdout_line(result):
    lines = result.stdout.strip().splitlines()
    return lines[-1] if lines else ""


def next_action_line(action):
    return claim_check.NEXT_ACTION_LINE_PREFIX + action


MUST_FIX_REPORT = ("VERDICT 1 supported: the tool sets x\n  nc-systems/example/tool.py:1 `x = 1`\n"
                   "VERDICT 2 contradicted must-fix: the program exists\n  FIRST-EVIDENCE-LINE\n"
                   "COUNTS supported=1 contradicted=1 unsupported=0\n")


def proposed_improvements_or_changes_files(fixture):
    """Every proposed-improvements-or-changes-file in the checkout, resolved, as the program prints them: the test
    sandbox's temporary directory is a symlink."""
    return sorted(path.resolve() for path in fixture.repository.rglob("*-proposed-improvements-or-changes*")
                  if ".git" not in path.parts)


def run_ranked_claim_cases(fixture, blob):
    def newest_report():
        return claim_check.find_newest_architecture_overview_claim_check_report_path_and_result_for_overview_git_blob(
            fixture.reports, OVERVIEW, blob)

    fixture.answer(claude_stdout=MUST_FIX_REPORT,
                   rechecks={"the program exists": {"stdout": recheck("contradicted must-fix", "the program exists")}})
    result = fixture.run()
    calls = fixture.claude_calls()
    newest = newest_report()
    check("a must-fix claim the recheck ranks must-fix again exits 5, and the newest report counts what remains",
          result.returncode == 5 and newest[1] == "must-fix claims remain: 1 must-fix, 0 fix-later, 0 nit",
          (result, newest))
    check("a remaining must-fix claim ends with the next action: fix the must-fix claims, or bring round 3 to the user",
          last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_WHEN_MUST_FIX_CLAIMS_REMAIN), result.stdout)
    check("both prompts give the three ranks", len(calls) == 2
          and all(claim_check.CLAIM_RANK_DEFINITIONS_FOR_FRESH_AGENT_PROMPT in call["stdin"] for call in calls), calls)
    recheck_prompt = calls[1]["stdin"] if len(calls) == 2 else ""
    check("the recheck prompt names the must-fix assertion alone, without the first verdict, rank or evidence",
          "The assertion: the program exists\n" in recheck_prompt and "FIRST-EVIDENCE-LINE" not in recheck_prompt
          and "contradicted must-fix" not in recheck_prompt and "the tool sets x" not in recheck_prompt
          and fixture.code_commit in recheck_prompt and calls[1]["cwd"] == calls[0]["cwd"], recheck_prompt)
    report_text = newest[0].read_text() if newest else ""
    check("the report holds the ranks after the recheck in its header, and the recheck's answer after the report",
          report_text.split("\n\n", 1)[0].endswith("\nranks after the recheck: 1 must-fix, 0 fix-later, 0 nit")
          and "# Recheck of VERDICT 2, which the report above ranks must-fix" in report_text, report_text)
    check("a run with no fix-later claim writes no proposed-improvements-or-changes-file",
          not proposed_improvements_or_changes_files(fixture))

    fixture.answer(claude_stdout=MUST_FIX_REPORT,
                   rechecks={"the program exists": {"stdout": recheck("contradicted fix-later", "the program exists")}})
    result = fixture.run()
    newest = newest_report()
    written = proposed_improvements_or_changes_files(fixture)
    check("a must-fix claim the recheck does not rank must-fix exits 0 with the no-must-fix result",
          result.returncode == 0 and newest[1] == claim_check.OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_NO_MUST_FIX_CLAIM_REMAINS,
          (result, newest))
    entry = written[0].read_text() if len(written) == 1 else ""
    check("the fix-later claim is written, with its evidence, its report and an open state, to the overview's one "
          "file in its system's docs/, outside the wiki folder",
          written == [(fixture.repository / PROPOSALS).resolve()]
          and entry.startswith(f"# Proposed improvements or changes: {Path(OVERVIEW).name}\n")
          and "## E1 — possible problem: an assertion of the overview is contradicted" in entry
          and "\nClaim: the program exists\n" in entry and ">   FIRST-EVIDENCE-LINE" in entry
          and "State: open" in entry and str(newest[0]) in entry and fixture.code_commit in entry, (written, entry))
    pointer_line = claim_check.overview_pointer_line_to_proposed_improvements_or_changes_file(OVERVIEW)
    check("with a fix-later file written and no pointer line, the next action says to commit the file, open the "
          "follow-up, add the pointer line and run again",
          last_stdout_line(result) == next_action_line(
              claim_check.NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS
              + claim_check.NEXT_ACTION_SUFFIX_WHEN_FIX_LATER_CLAIMS_WRITTEN_TO_PROPOSED_IMPROVEMENTS_OR_CHANGES_FILE.format(path=written[0] if written else None)
              + claim_check.NEXT_ACTION_SUFFIX_WHEN_OVERVIEW_LACKS_PROPOSED_IMPROVEMENTS_OR_CHANGES_POINTER_LINE.format(line=pointer_line)), result.stdout)

    result = fixture.run()
    check("a fix-later claim the file already holds is not written again, and the file is left as it was",
          result.returncode == 0 and proposed_improvements_or_changes_files(fixture) == written
          and written[0].read_text() == entry
          and last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS),
          result.stdout)

    real_run_git = claim_check.run_git

    def run_git_whose_worktree_remove_fails(repository, *arguments, check=True):
        if arguments[:2] == ("worktree", "remove"):
            return subprocess.CompletedProcess(["git", *arguments], 128, "", "fatal: injected removal failure")
        return real_run_git(repository, *arguments, check=check)

    code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_remove_fails)
    fixture.git("worktree", "prune")
    check("no must-fix claim with a worktree git cannot remove exits 6, with the next action to push and clean up",
          code == 6 and fixture.last_in_process_stdout.strip().splitlines()[-1] == next_action_line(
              claim_check.NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS_AND_WORKTREE_STAYS), (code, stderr))

    count = len(fixture.reports_written())
    fixture.answer(claude_stdout=MUST_FIX_REPORT,
                   rechecks={"the program exists": {"stdout": "", "exit_code": 1, "stderr": "usage limit reached"}})
    result = fixture.run()
    check("a recheck fresh-agent that fails exits 4, quotes its stderr and writes no report",
          result.returncode == 4 and "usage limit reached" in result.stderr and len(fixture.reports_written()) == count,
          result.stderr)

    fixture.answer(claude_stdout=MUST_FIX_REPORT,
                   rechecks={"the program exists": {"stdout": "I could not decide.\n"}})
    result = fixture.run()
    newest = newest_report()
    check("a malformed recheck exits 5 with a malformed result, and ends with the next action: run again",
          result.returncode == 5 and newest[1] == "malformed: the recheck of VERDICT 2 is malformed: no VERDICT line"
          and last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_WHEN_FRESH_AGENT_REPORT_IS_MALFORMED_FIRST_TIME),
          (result, newest))
    for report in fixture.reports_written():
        if report.read_text().count("result: malformed"):
            report.unlink()

    fixture.answer(claude_stdout="VERDICT 1 contradicted must-fix: alpha claim\nVERDICT 2 unsupported must-fix: beta claim\n"
                                 "COUNTS supported=0 contradicted=1 unsupported=1\n",
                   rechecks={"alpha claim": {"stdout": recheck("contradicted must-fix", "alpha claim"),
                                             "sleep_seconds": RECHECK_SLEEP_SECONDS},
                             "beta claim": {"stdout": recheck("unsupported fix-later", "beta claim"),
                                            "sleep_seconds": RECHECK_SLEEP_SECONDS}})
    result = fixture.run()
    rechecks = fixture.claude_calls()[1:]
    starts = sorted(call["started"] for call in rechecks)
    # Run one after the other, the second recheck would start only after the first's sleep ended.
    check("the rechecks run in parallel: the second starts before the first has finished",
          len(starts) == 2 and starts[1] - starts[0] < RECHECK_SLEEP_SECONDS, starts)
    check("each must-fix claim gets its own recheck, which names only that claim",
          result.returncode == 5 and len(rechecks) == 2
          and sorted(("alpha claim" in call["stdin"], "beta claim" in call["stdin"]) for call in rechecks)
          == [(False, True), (True, False)] and newest_report()[1] == "must-fix claims remain: 1 must-fix, 1 fix-later, 0 nit",
          (result, rechecks))
    appended = written[0].read_text() if written else ""
    check("a fix-later claim is appended to the same file as the next entry, even when a must-fix claim remains, and "
          "the next action names that file",
          proposed_improvements_or_changes_files(fixture) == written and appended.startswith(entry)
          and "## E2 — possible problem: an assertion of the overview is unsupported" in appended
          and "Claim: beta claim" in appended and appended.count("Claim: the program exists") == 1
          and "alpha claim" not in appended
          and last_stdout_line(result).startswith(next_action_line(claim_check.NEXT_ACTION_WHEN_MUST_FIX_CLAIMS_REMAIN))
          and str(written[0]) in last_stdout_line(result), (appended, result.stdout))

    for written_file in proposed_improvements_or_changes_files(fixture):
        written_file.unlink()
    with_pointer = fixture.commit_overview(body=f"# Example overview\n\n{pointer_line}\n\nThe example system.\n")
    fixture.answer(claude_stdout="VERDICT 1 unsupported fix-later: gamma claim\nVERDICT 2 contradicted nit: delta claim\n"
                                 "COUNTS supported=0 contradicted=1 unsupported=1\n")
    result = fixture.run()
    written = proposed_improvements_or_changes_files(fixture)
    check("fix-later and nit claims need no recheck; only the fix-later one is written, and with the pointer line "
          "present the next action leaves it out",
          result.returncode == 0 and len(fixture.claude_calls()) == 1 and len(written) == 1
          and "gamma claim" in written[0].read_text() and "delta claim" not in written[0].read_text()
          and last_stdout_line(result) == next_action_line(
              claim_check.NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS
              + claim_check.NEXT_ACTION_SUFFIX_WHEN_FIX_LATER_CLAIMS_WRITTEN_TO_PROPOSED_IMPROVEMENTS_OR_CHANGES_FILE.format(path=written[0] if written else None)),
          (with_pointer, result.stdout))
    for written_file in written:
        written_file.unlink()

    main_before = fixture.git("rev-parse", "refs/remotes/origin/main")
    entries_without_claims = ("# Proposed improvements or changes: the example overview\n\n"
                              "## E7 — improvement: an entry an overview writer recorded\n\nState: open")
    fixture.write(PROPOSALS, entries_without_claims)
    fixture.git("update-ref", "refs/remotes/origin/main", fixture.commit("the file on main, with no claim-check entry"))
    fixture.answer(claude_stdout="VERDICT 1 unsupported fix-later: epsilon claim\n"
                                 "COUNTS supported=0 contradicted=0 unsupported=1\n")
    result = fixture.run()
    appended = (fixture.repository / PROPOSALS).read_text()
    check("when the file on origin/main holds no claim from the claim check, a follow-up pull request fixes the new "
          "claims, appended after the highest entry number",
          result.returncode == 0 and appended.startswith(entries_without_claims + "\n\n## E8 — possible problem:")
          and "Claim: epsilon claim" in appended and "Fixed by: a follow-up pull request, in the overview." in appended
          and last_stdout_line(result).startswith(next_action_line(
              claim_check.NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS
              + claim_check.NEXT_ACTION_SUFFIX_WHEN_FIX_LATER_CLAIMS_WRITTEN_TO_PROPOSED_IMPROVEMENTS_OR_CHANGES_FILE.format(
                  path=(fixture.repository / PROPOSALS).resolve()))), (appended, result.stdout))

    fixture.git("update-ref", "refs/remotes/origin/main", fixture.commit("the file on main, with a claim-check entry"))
    fixture.answer(claude_stdout="VERDICT 1 unsupported fix-later: zeta claim\n"
                                 "COUNTS supported=0 contradicted=0 unsupported=1\n")
    result = fixture.run()
    appended = (fixture.repository / PROPOSALS).read_text()
    check("when the file on origin/main already holds a claim from the claim check, new claims ranked fix later go "
          "to regular maintenance, not to another follow-up pull request",
          result.returncode == 0 and "## E9 — possible problem:" in appended and "Claim: zeta claim" in appended
          and "Fixed by: regular maintenance, in the overview." in appended
          and last_stdout_line(result) == next_action_line(
              claim_check.NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS
              + claim_check.NEXT_ACTION_SUFFIX_WHEN_FOLLOW_UP_PULL_REQUEST_LEAVES_FIX_LATER_CLAIMS_TO_REGULAR_MAINTENANCE.format(
                  path=(fixture.repository / PROPOSALS).resolve())), (appended, result.stdout))
    check("without a claim from the claim check on origin/main, the entry says a follow-up pull request fixes it",
          "Fixed by: a follow-up pull request, in the overview." in entry, entry)
    (fixture.repository / PROPOSALS).unlink()
    fixture.commit("remove the file")
    fixture.git("update-ref", "refs/remotes/origin/main", main_before)
    fixture.commit_overview()


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
    check("every claim supported ends with the next action: push",
          last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_BY_EXIT_CODE[0]), result.stdout)

    run_ranked_claim_cases(fixture, blob)

    real_run_git = claim_check.run_git

    def run_git_whose_worktree_remove_fails(repository, *arguments, check=True):
        if arguments[:2] == ("worktree", "remove"):
            if check:
                raise claim_check.ClaimCheckRefusal("`git worktree remove` failed with exit 128: fatal: injected removal failure")
            return subprocess.CompletedProcess(["git", *arguments], 128, "", "fatal: injected removal failure")
        return real_run_git(repository, *arguments, check=check)

    count = len(fixture.reports_written())
    fixture.answer()
    code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_remove_fails)
    check("a worktree that git cannot remove exits 6, with git's words and the worktree's path, after writing the report",
          code == 6 and "injected removal failure" in stderr and "checkout-at-checked-against-commit" in stderr
          and len(fixture.reports_written()) == count + 1, stderr)
    cleanup = re.search(r"To clean up, once this program has exited: run `git -C (\S+) (worktree remove --force) (\S+)`",
                        stderr)
    worktree_path = Path(cleanup.group(3)) if cleanup else None
    check("after a failed removal the worktree's folder is gone and git still records the worktree",
          worktree_path is not None and not worktree_path.exists() and str(worktree_path) in fixture.git("worktree", "list"),
          stderr)
    if cleanup:
        fixture.git("worktree", "remove", "--force", str(worktree_path))
    check("the cleanup command the program prints after a failed removal clears git's record of the worktree",
          worktree_path is not None and str(worktree_path) not in fixture.git("worktree", "list"), stderr)
    fixture.git("worktree", "prune")
    fixture.answer(claude_stdout="", claude_exit=1)
    code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_remove_fails)
    check("a worktree that git cannot remove after a failed fresh-agent keeps exit 4 and still reports the removal",
          code == 4 and "injected removal failure" in stderr and len(fixture.reports_written()) == count + 1, stderr)
    fixture.git("worktree", "prune")
    fixture.answer(claude_stdout=UNSUPPORTED_REPORT)
    code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_remove_fails)
    check("a worktree that git cannot remove after an unsupported claim keeps exit 5, writes the report and still "
          "reports the removal",
          code == 5 and "injected removal failure" in stderr and len(fixture.reports_written()) == count + 2, stderr)
    fixture.git("worktree", "prune")

    for raised in (subprocess.TimeoutExpired(["git", "worktree", "remove"], 1), OSError("injected OSError")):
        def run_git_whose_worktree_remove_raises(repository, *arguments, check=True, raised=raised):
            if arguments[:2] == ("worktree", "remove"):
                raise raised
            return real_run_git(repository, *arguments, check=check)

        kind = type(raised).__name__
        fixture.answer(claude_stdout="", claude_exit=1)
        code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_remove_raises)
        check(f"a worktree removal that raises {kind} after a failed fresh-agent keeps exit 4 and reports the removal",
              code == 4 and "could not run" in stderr and "checkout-at-checked-against-commit" in stderr, stderr)
        fixture.git("worktree", "prune")
        fixture.answer(claude_stdout=UNSUPPORTED_REPORT)
        code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_remove_raises)
        check(f"a worktree removal that raises {kind} after an unsupported claim keeps exit 5", code == 5, stderr)
        fixture.git("worktree", "prune")
        fixture.answer()
        code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_remove_raises)
        check(f"a worktree removal that raises {kind} with every claim supported exits 6 and reports the removal",
              code == 6 and "could not run" in stderr, stderr)
        fixture.git("worktree", "prune")

        def run_git_whose_worktree_prune_raises(repository, *arguments, check=True, raised=raised):
            if arguments[:2] == ("worktree", "prune"):
                raise raised
            return real_run_git(repository, *arguments, check=check)

        fixture.answer()
        code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_prune_raises)
        check(f"a `git worktree prune` that would raise {kind} after a successful removal leaves an all-supported run "
              "at exit 0", code == 0 and "could not run" not in stderr and fixture.worktrees() == worktrees_before,
              stderr)

    fixture.answer(claude_stdout="I ran out of time.\n")
    result = fixture.run()
    newest = claim_check.find_newest_architecture_overview_claim_check_report_path_and_result_for_overview_git_blob(fixture.reports, OVERVIEW, blob)
    check("a malformed report exits 5 and is kept with a malformed result",
          result.returncode == 5 and newest[1] == "malformed: no VERDICT line", (result, newest))
    check("a first malformed report for this overview text ends with the next action: run again",
          last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_WHEN_FRESH_AGENT_REPORT_IS_MALFORMED_FIRST_TIME), result.stdout)
    result = fixture.run()
    check("a second malformed report for the same overview text ends with the next action: tell the user",
          result.returncode == 5 and last_stdout_line(result) == next_action_line(
              claim_check.NEXT_ACTION_WHEN_FRESH_AGENT_REPORT_IS_MALFORMED_AGAIN.format(
                  directory=claim_check.overview_write_architecture_overview_claim_check_report_directory_for_overview(
                      fixture.reports, OVERVIEW), blob=blob)), result.stdout)

    undecodable_report = claim_check.overview_write_architecture_overview_claim_check_report_directory_for_overview(
        fixture.reports, OVERVIEW) / f"{blob}-x.md"
    undecodable_report.write_bytes(b"\xff\xfe not UTF-8\n")
    result = fixture.run()
    undecodable_report.unlink()
    check("a program defect, here an earlier report that is not UTF-8, exits 2 and ends with the next action for exit 2",
          result.returncode == 2 and "program defect" in result.stderr
          and last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_BY_EXIT_CODE[2]),
          (result.returncode, result.stdout, result.stderr))

    count = len(fixture.reports_written())
    fixture.answer(claude_stdout="", claude_exit=1)
    (fixture.control / "claude.json").write_text(json.dumps({"stdout": "", "stderr": "Not logged in", "exit_code": 1}))
    result = fixture.run()
    check("a fresh-agent that fails exits 4, quotes its stderr and writes no report",
          result.returncode == 4 and "Not logged in" in result.stderr and len(fixture.reports_written()) == count, result.stderr)
    check("a failed fresh-agent ends with the next action for exit 4",
          last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_BY_EXIT_CODE[4]), result.stdout)
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
    fixture.answer(claude_stdout=UNSUPPORTED_REPORT)
    result = fixture.run("--writer-answers", str(answers))
    calls = fixture.claude_calls()
    check("the recheck prompt names the answers file with the wording for one assertion",
          len(calls) == 2 and claim_check.RECHECK_WRITER_ANSWERS_TEMPLATE.format(answers=answers.resolve()) in calls[1]["stdin"]
          and claim_check.FRESH_AGENT_WRITER_ANSWERS_TEMPLATE.format(answers=answers.resolve()) in calls[0]["stdin"],
          calls)

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
    fixture.commit_overview()
    fixture.git("update-ref", "-d", "refs/remotes/origin/main")
    fixture.answer()
    result = fixture.run()
    fixture.git("update-ref", "refs/remotes/origin/main", fixture.code_commit)
    check("a repository without origin/main is refused with the fetch command, before any fresh-agent runs",
          result.returncode == 1 and "origin/main is missing" in result.stderr and "fetch origin" in result.stderr
          and not fixture.claude_calls(), result.stderr)
    result = fixture.run("--no-such-flag")
    check("a malformed argument is refused with exit 1, not the program-defect exit",
          result.returncode == 1 and "--help" in result.stderr, result.stderr)
    check("a refusal's last line tells the agent to do what the refusal says",
          last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_BY_EXIT_CODE[1]), result.stdout)


def main():
    run_unit_cases()
    with tempfile.TemporaryDirectory(prefix="overview-claim-check-test-") as temporary:
        run_program_cases(Fixture(Path(temporary)))
    print(f"{len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
