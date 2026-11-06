#!/usr/bin/env python3
"""Check an nc-architecture-overview's claims about the code with a fresh-agent, and keep the report.

This is the check of the section "Checking an overview" of
docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md, run by
a program so that no step depends on an agent remembering it:

1. Reads the overview as --revision holds it (HEAD by default), and the commit
   its **Checked against:** line names.
2. Makes a detached worktree at that commit, in a temporary directory, and puts
   the overview's text at its path there.
3. Stage 1: runs that commit's scripts/md-drift-lint.py on the overview. A
   finding stops the program before any model runs.
4. Stage 2: runs one fresh-agent, `claude -p` with hooks disabled and only
   read and search tools, in that worktree. The prompt points it at stage 2
   of the page, gives the three ranks of a contradicted or unsupported claim
   (must fix, fix later, nit), since the page at an older commit lacks them,
   and fixes the report's form, so this program can count the verdicts and
   ranks. --writer-answers gives it the writer's answers to verdicts the
   writer disputes, as the page's rounds allow.
5. For each claim ranked must fix, runs one more fresh-agent, all of them in
   parallel, given that claim and not the first verdict or rank. The claim
   keeps the rank must fix only when that second answer ranks it must fix
   again; otherwise it is ranked fix later.
6. Writes the report, the second answers after it, under a header this
   program writes, to
   <report directory>/<overview file name without .md>/<overview blob>-<UTC time>.md.
   The blob names the overview's exact text, which holds the commit it is
   checked against, so a report stays valid across a rebase or a fix-round
   that leaves the overview's text alone, and no model runs again for it.
7. Writes each claim ranked fix later that no
   proposed-improvements-or-changes-file beside the overview holds yet,
   matched by its exact text, to a new such file in the checkout the program
   runs from. A follow-up pull request fixes them, except when origin/main
   already holds such a file from this program: the run is then taken to be
   that follow-up, or a later one, and its claims ranked fix later are left
   to regular maintenance, so "later" is one step. Nits are listed in the
   report only.

scripts/pull-request-review-plan.py refuses a pull request that adds or changes
an overview until the newest report for the overview's blob at the pull
request's head says OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED or
OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_NO_MUST_FIX_CLAIM_REMAINS; it reads reports with
find_newest_architecture_overview_claim_check_report_path_and_result_for_overview_git_blob() from this file.

Does not handle: counting rounds (the page stops the check at round 3 and
sends what is left to the user; no report records what he decides); an
overview not on the path the page gives; a run on the Mac, where the
log-store is not local; the same claim ranked fix later, worded differently
by two runs, which is written twice; a repository without origin/main, which
is refused.
Failures: every failure is printed to stderr with what to do and exits
nonzero; no report is written unless every fresh-agent produced output. The
temporary worktree is removed on every path, including a failure; when git
cannot remove it, the program prints git's words and the worktree's path, and
exits 6 only when the run would otherwise exit 0; any other exit code is
kept. The worktree's folder is deleted with the temporary directory either
way, but git's record of the worktree stays in the checkout until the
cleanup command the program prints is run. Apart from that record and the
proposed-improvements-or-changes-file of step 7, the program writes nothing in
the checkout it is run from.

Usage:
  python3 nc-systems/skills/overview-write/overview-write-architecture-overview-claim-check-by-fresh-agent.py \\
      --overview docs/nedschorus-wiki/nedschorus-handoff-architecture-overview.md \\
      [--revision <commit or branch>] [--writer-answers FILE] [--report-directory DIR]

Exit 0: report written, and no claim ranked must fix remains. 1: refused,
nothing run. 2: program defect. 3: md-drift-lint found problems, so no
fresh-agent ran. 4: a fresh-agent failed, so no report was written. 5: report
written, and a claim ranked must fix remains, or the report is malformed. 6:
no claim ranked must fix remains, but git could not remove the temporary
worktree; the report
was still written, its result printed, and scripts/pull-request-review-plan.py
accepts it as it accepts an exit-0 report.

The last line printed, on stdout, starts with "Next: " and says what to do for
that exit, so the overview-write skill's step 3 is only to do what it says.
For exits 0, 5 and 6, when step 7 wrote a file, the line says to commit it
and either to open a follow-up pull request for its claims once this one
merges or that regular maintenance takes them, and, when the overview lacks
the line pointing to such files, to add that line and run the program again.
For exit 5 the program tells a malformed report apart from claims ranked
must fix. On the first malformed report for an overview text, its
last line tells the agent to run the program again; on the second and each
later one, to bring the reports to the user.
"""

import argparse
import collections
import concurrent.futures
import datetime
import importlib.util
import re
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

PROGRAM = "overview-write-architecture-overview-claim-check-by-fresh-agent"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _load(module_name, relative_path):
    specification = importlib.util.spec_from_file_location(module_name, REPOSITORY_ROOT / relative_path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


overview_path_reader = _load(
    "architecture_overview_path_template_and_checked_against_commit_reader_common",
    "scripts/architecture-overview-path-template-and-checked-against-commit-reader-common.py")
git_redirecting_removal = _load(
    "git_redirecting_environment_variables_removal_common",
    "nc-systems/general-tools/git-redirecting-environment-variables-removal-common.py")
ned_box_home_path_constants = _load(
    "ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
    "nc-systems/general-tools/ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
cold_read_claude_cell = _load("cold_read_claude_cell", "nc-systems/cold-read/cold-read-claude-cell.py")
command_line_prefix = _load(
    "claude_code_headless_run_command_line_prefix_with_no_connectors_and_explicit_permission_mode_common",
    "nc-systems/general-tools/claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")

LOG_STORE_DIRECTORY = Path(ned_box_home_path_constants.NED_BOX_HOME) / "nedschorus-logs"
OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_REPORT_DIRECTORY = LOG_STORE_DIRECTORY / "overview-write-architecture-overview-claim-check-reports"
HOW_TO_PAGE = "docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md"

ARCHITECTURE_OVERVIEW_PATH = re.compile(
    re.escape(overview_path_reader.PATH_TEMPLATE).replace(re.escape("{system}"), r"(?P<system>[^/]+)"))

# The fresh-agent checks claims against code; a weaker model misses confident errors, the defect this check exists for.
FRESH_AGENT_MODEL = "claude-opus-5-5"
FRESH_AGENT_EFFORT = "high"
# --tools is the whole tool set: with --allowedTools alone the agent kept Agent and ran seven subagents in one check.
FRESH_AGENT_TOOLS = "Read,Grep,Glob"
FRESH_AGENT_TIMEOUT_SECONDS = 3600
GIT_TIMEOUT_SECONDS = 120
MD_DRIFT_LINT_TIMEOUT_SECONDS = 600

RESULT_LINE_PREFIX = "result: "
OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED = "all claims supported"
OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_NO_MUST_FIX_CLAIM_REMAINS = "no must-fix claim remains"

VERDICTS = ("supported", "contradicted", "unsupported")
RANK_MUST_FIX, RANK_FIX_LATER, RANK_NIT = "must-fix", "fix-later", "nit"
RANKS = (RANK_MUST_FIX, RANK_FIX_LATER, RANK_NIT)
VERDICT_LINE = re.compile(r"^VERDICT (\d+) (supported|contradicted|unsupported)(?: (\S+))?:[ \t]*(.*)$", re.MULTILINE)
COUNTS_LINE = re.compile(r"^COUNTS supported=(\d+) contradicted=(\d+) unsupported=(\d+)\s*$", re.MULTILINE)
Claim = collections.namedtuple("Claim", "number verdict rank assertion evidence")

PROPOSED_IMPROVEMENTS_OR_CHANGES_INFIX = "-proposed-improvements-or-changes-"
PROPOSED_IMPROVEMENTS_OR_CHANGES_SOURCE = "overview-write-claim-check-by-fresh-agent"
PROPOSED_IMPROVEMENTS_OR_CHANGES_POINTER_LINE_TEMPLATE = (
    "This document has proposed improvements or changes: read every file in this folder whose name starts with "
    "`{prefix}`.")
FIX_LATER_ENTRY_CLAIM_PREFIX = "Claim: "

CLAIM_RANK_DEFINITIONS_FOR_FRESH_AGENT_PROMPT = """\
Give each contradicted or unsupported assertion one of three ranks:
- must fix, written must-fix in the report: an agent relying on the claim would act wrongly, such as open the wrong file.
- fix later, written fix-later in the report: loose, incomplete or badly worded, but no agent would act wrongly on it.
- nit: a matter of style.
"""

FRESH_AGENT_PROMPT_TEMPLATE = """\
You are the fresh-agent of stage 2 of the section "Checking an overview" in {page}. Read that page, then check the nc-architecture-overview {overview} against the repository in your working directory, a checkout at commit {commit}, which the overview's last line names. Stage 1 has passed. Do stage 2 as the page says, leaving out what the page says is not checked against the code. You have the Read, Grep and Glob tools only, and cannot change files or run commands.
{ranks}{writer_answers}
Your final message is the report. A program counts its verdicts and ranks and treats a report in any other form as a failed check, so write it in this form:
- One block per assertion, which the page calls a row, numbered from 1 in the overview's order. Each block starts with the line `VERDICT <number> supported: <the assertion>`, or `VERDICT <number> <verdict> <rank>: <the assertion>`, where <verdict> is contradicted or unsupported and <rank> is must-fix, fix-later or nit. The lines after it, in any form, give the evidence the page asks for that verdict; the program copies them into the record of an assertion ranked fix later.
- The last line is `COUNTS supported=<number> contradicted=<number> unsupported=<number>`.
"""

RECHECK_PROMPT_TEMPLATE = """\
You are a fresh-agent checking one assertion of the nc-architecture-overview {overview} against the repository in your working directory, a checkout at commit {commit}, which the overview's last line names. Read stage 2 of the section "Checking an overview" in {page} for how to check an assertion and the evidence each verdict needs, then check this assertion only. You have the Read, Grep and Glob tools only, and cannot change files or run commands.
The assertion: {assertion}
{ranks}{recheck_writer_answers}
Your final message is the report. A program reads it and treats a report in any other form as a failed check, so write it in this form:
- The first line is `VERDICT 1 supported: <the assertion>`, or `VERDICT 1 <verdict> <rank>: <the assertion>`, where <verdict> is contradicted or unsupported and <rank> is must-fix, fix-later or nit. The lines after it, in any form, give the evidence the page asks for that verdict.
- The last line is `COUNTS supported=<number> contradicted=<number> unsupported=<number>`.
"""

FRESH_AGENT_WRITER_ANSWERS_TEMPLATE = """\
The overview's writer disputes verdicts of an earlier check. The file {answers} names each disputed assertion and gives the writer's answer, with the quoted line it rests on. Check every assertion as above; for each disputed one, read the writer's answer too, and give the verdict the code bears out.
"""

RECHECK_WRITER_ANSWERS_TEMPLATE = """\
The overview's writer disputes verdicts of an earlier check. The file {answers} names each disputed assertion and gives the writer's answer, with the quoted line it rests on. Check the assertion as above; if it is one the writer disputes, read the writer's answer too, and give the verdict the code bears out.
"""


NEXT_ACTION_LINE_PREFIX = "Next: "
NEXT_ACTION_BY_EXIT_CODE = {
    0: "every assertion is supported. Push your branch.",
    1: "nothing was checked. Do what the refusal above says, then run this program again.",
    2: "this program has a defect. Tell the user what it printed above, and stop.",
    3: "scripts/md-drift-lint.py found problems in the overview. Fix each one it printed above, commit, then run "
       "this program again.",
    4: "no report was written. If the lines above say `claude` is logged out or a usage limit is reached, tell the "
       "user what they say, and stop. Otherwise run this program again once; if it ends with this line again, tell "
       "the user what it printed, and stop.",
    6: "every assertion is supported, but the temporary worktree could not be removed. Push your branch, then do "
       "the clean-up the lines above give.",
}
NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS = "no claim ranked must fix remains. Push your branch."
NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS_AND_WORKTREE_STAYS = (
    "no claim ranked must fix remains, but the temporary worktree could not be removed. Push your branch, then do "
    "the clean-up the lines above give.")
NEXT_ACTION_WHEN_MUST_FIX_CLAIMS_REMAIN = (
    "open the report named above. Only the assertions still ranked must fix after the recheck need work in this pull "
    "request. For each of them you believe is wrong, answer it as step 4 of the overview-write skill "
    "(.claude/skills/overview-write/SKILL.md) says, and leave that statement as it is. Correct or remove each other "
    "statement ranked must fix in the overview; where it is unsupported, you may instead name in it the repository "
    "files that bear it out. Commit, then run this program again, unless this was round 3 of the check on this pull "
    "request: then bring the report to the user, and stop.")
NEXT_ACTION_SUFFIX_WHEN_FIX_LATER_CLAIMS_WRITTEN_TO_PROPOSED_IMPROVEMENTS_OR_CHANGES_FILE = (
    " The claims ranked fix later that are new to this check are in {path}: commit that file on this branch. Once "
    "this pull request merges, open a follow-up pull request that fixes those claims in the overview and settles the "
    "file's entries. Nits are listed in the report only; regular maintenance cleans them up.")
NEXT_ACTION_SUFFIX_WHEN_FOLLOW_UP_PULL_REQUEST_LEAVES_FIX_LATER_CLAIMS_TO_REGULAR_MAINTENANCE = (
    " The claims ranked fix later that are new to this check are in {path}: commit that file on this branch. "
    "origin/main already holds a proposed-improvements-or-changes-file from this program for the overview, so this "
    "is a follow-up pull request, and regular maintenance takes these claims, not another follow-up. Nits are listed "
    "in the report only; regular maintenance cleans them up too.")
NEXT_ACTION_SUFFIX_WHEN_OVERVIEW_LACKS_PROPOSED_IMPROVEMENTS_OR_CHANGES_POINTER_LINE = (
    " Before you push: add the line \"{line}\" under the overview's first heading, commit it, and run this program "
    "again, because this report covers the overview's text without that line.")
NEXT_ACTION_WHEN_FRESH_AGENT_REPORT_IS_MALFORMED_FIRST_TIME = "the fresh-agent's report is malformed. Run this program again."
NEXT_ACTION_WHEN_FRESH_AGENT_REPORT_IS_MALFORMED_AGAIN = (
    "the fresh-agent's report for this overview text is malformed for the second time or more. Tell the user, giving "
    "the report paths in {directory} whose names start with {blob}, and stop.")


def malformed_report_count_for_overview_git_blob(destination_directory, blob):
    count = 0
    for report in destination_directory.glob(f"{blob}-*.md"):
        for line in report.read_text(encoding="utf-8").splitlines():
            if line.startswith(RESULT_LINE_PREFIX):
                count += line.removeprefix(RESULT_LINE_PREFIX).startswith("malformed")
                break
    return count


class ClaimCheckRefusal(Exception):
    def __init__(self, message, exit_code=1):
        super().__init__(message)
        self.exit_code = exit_code


class RefusingArgumentParser(argparse.ArgumentParser):
    """Keep exit 2 for program defects: malformed arguments are a refusal."""

    def error(self, message):
        raise ClaimCheckRefusal(f"{message}\nTo see the arguments: run this with --help.")


def nc_architecture_overview_described_system_name_from_page_path(path):
    """Return the <system> of a path the page gives for an overview, or None.

    The template alone also matches the how-to page itself; a caller checks
    that nc-systems/<system> exists at the revision it reads."""
    match = ARCHITECTURE_OVERVIEW_PATH.fullmatch(path)
    return match.group("system") if match else None


def overview_write_architecture_overview_claim_check_report_directory_for_overview(report_directory, overview_path):
    return Path(report_directory) / Path(overview_path).name.removesuffix(".md")


def find_newest_architecture_overview_claim_check_report_path_and_result_for_overview_git_blob(report_directory, overview_path, blob):
    """Return (report path, result) of the newest report for this overview text, or None.

    The result is the text after "result: " on the report's header line."""
    reports = sorted(overview_write_architecture_overview_claim_check_report_directory_for_overview(report_directory, overview_path).glob(f"{blob}-*.md"))
    if not reports:
        return None
    newest = reports[-1]
    for line in newest.read_text(encoding="utf-8").splitlines():
        if line.startswith(RESULT_LINE_PREFIX):
            return newest, line.removeprefix(RESULT_LINE_PREFIX)
        if not line.strip():
            break
    return newest, "no result line in the report's header"


def claims_from_fresh_agent_report(report):
    """Return (the report's claims, None), or (None, a result saying why the report is malformed)."""
    matches = list(VERDICT_LINE.finditer(report))
    counts = COUNTS_LINE.findall(report)
    if not matches:
        return None, "malformed: no VERDICT line"
    numbers = [int(match.group(1)) for match in matches]
    if numbers != list(range(1, len(numbers) + 1)):
        return None, "malformed: the VERDICT lines are not numbered 1, 2, 3 and on in order"
    if len(counts) != 1:
        return None, f"malformed: {len(counts)} COUNTS lines, not one"
    claims = []
    for index, match in enumerate(matches):
        number, verdict, rank, assertion = int(match.group(1)), match.group(2), match.group(3), match.group(4).strip()
        if verdict == "supported" and rank is not None:
            return None, f"malformed: VERDICT {number} is supported but has the rank {rank}"
        if verdict != "supported" and rank not in RANKS:
            return None, (f"malformed: VERDICT {number} is {verdict} with the rank {rank or 'missing'}, not one of "
                          f"{', '.join(RANKS)}")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(report)
        evidence = COUNTS_LINE.sub("", report[match.end():end]).strip("\n")
        claims.append(Claim(number, verdict, rank, assertion, evidence))
    tally = {verdict: sum(1 for claim in claims if claim.verdict == verdict) for verdict in VERDICTS}
    stated = dict(zip(VERDICTS, (int(value) for value in counts[0])))
    if stated != tally:
        return None, f"malformed: the COUNTS line says {stated}, but the VERDICT lines give {tally}"
    return claims, None


def rank_counts(claims):
    return {rank: sum(1 for claim in claims if claim.rank == rank) for rank in RANKS}


def result_from_ranked_claims(claims):
    """Return OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED,
    OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_NO_MUST_FIX_CLAIM_REMAINS, or a result that counts the
    claims ranked must fix that remain."""
    if all(claim.verdict == "supported" for claim in claims):
        return OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED
    counts = rank_counts(claims)
    if counts[RANK_MUST_FIX] == 0:
        return OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_NO_MUST_FIX_CLAIM_REMAINS
    return (f"must-fix claims remain: {counts[RANK_MUST_FIX]} must-fix, {counts[RANK_FIX_LATER]} fix-later, "
            f"{counts[RANK_NIT]} nit")


def claims_ranked_after_recheck(claims, recheck_reports):
    """Return (the claims, each one ranked must fix re-ranked by its recheck, None), or (None, why a recheck is
    malformed).

    recheck_reports maps the number of a claim ranked must fix to its second fresh-agent's report; the claim keeps
    that rank only when the report ranks it must fix again, and is ranked fix later otherwise."""
    ranked = []
    for claim in claims:
        if claim.rank != RANK_MUST_FIX:
            ranked.append(claim)
            continue
        recheck, malformed = claims_from_fresh_agent_report(recheck_reports[claim.number])
        if malformed:
            return None, f"malformed: the recheck of VERDICT {claim.number} is {malformed}"
        if len(recheck) != 1:
            return None, f"malformed: the recheck of VERDICT {claim.number} has {len(recheck)} VERDICT lines, not one"
        ranked.append(claim._replace(rank=RANK_MUST_FIX if recheck[0].rank == RANK_MUST_FIX else RANK_FIX_LATER))
    return ranked, None


def result_from_fresh_agent_report(report, recheck_reports=None):
    """Return the claims after the recheck, or None for a malformed report, and the result for the report's header."""
    claims, malformed = claims_from_fresh_agent_report(report)
    if malformed:
        return None, malformed
    claims, malformed = claims_ranked_after_recheck(claims, recheck_reports or {})
    if malformed:
        return None, malformed
    return claims, result_from_ranked_claims(claims)


def overview_pointer_line_to_proposed_improvements_or_changes_files(overview_path):
    return PROPOSED_IMPROVEMENTS_OR_CHANGES_POINTER_LINE_TEMPLATE.format(
        prefix=Path(overview_path).stem + PROPOSED_IMPROVEMENTS_OR_CHANGES_INFIX)


def normalized_claim(text):
    return " ".join(text.split())


def write_fix_later_claims_to_proposed_improvements_or_changes_file(repository, overview_path, claims, commit,
                                                                    report_path, for_regular_maintenance):
    """Write the claims ranked fix later that no file beside the overview holds yet to a new
    proposed-improvements-or-changes-file in the checkout; return its path, or None when no claim is new."""
    directory = repository / Path(overview_path).parent
    prefix = Path(overview_path).stem + PROPOSED_IMPROVEMENTS_OR_CHANGES_INFIX
    recorded = {normalized_claim(line.removeprefix(FIX_LATER_ENTRY_CLAIM_PREFIX))
                for existing in directory.glob(f"{prefix}*.md")
                for line in existing.read_text(encoding="utf-8").splitlines()
                if line.startswith(FIX_LATER_ENTRY_CLAIM_PREFIX)}
    new_claims = []
    for claim in claims:
        if claim.rank == RANK_FIX_LATER and normalized_claim(claim.assertion) not in recorded:
            recorded.add(normalized_claim(claim.assertion))
            new_claims.append(claim)
    if not new_claims:
        return None
    date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    name = f"{prefix}{PROPOSED_IMPROVEMENTS_OR_CHANGES_SOURCE}-{date}"
    destination, suffix = directory / f"{name}.md", 1
    while destination.exists():
        suffix += 1
        destination = directory / f"{name}-{suffix}.md"
    lines = [f"# Proposed improvements or changes: {Path(overview_path).name} (overview claim check, {date})", "",
             f"Assertions of the overview that the claim check against commit {commit} found contradicted or "
             "unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on "
             f"them. Its report is {report_path}. "
             + ("Regular maintenance fixes them in the overview." if for_regular_maintenance
                else "A follow-up pull request fixes them in the overview.")]
    for entry, claim in enumerate(new_claims, start=1):
        lines += ["", f"## E{entry} — possible problem: an assertion of the overview is {claim.verdict}", "",
                  f"{FIX_LATER_ENTRY_CLAIM_PREFIX}{normalized_claim(claim.assertion)}",
                  "Goes wrong when: a reader takes the assertion as exact.",
                  "The claim check's evidence:"]
        lines += [f"> {line}".rstrip() for line in claim.evidence.splitlines()] or ["> none given"]
        lines += ["State: open"]
    directory.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


def run_git(repository, *arguments, check=True):
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments], capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS,
        env=git_redirecting_removal.environment_without_git_redirecting_variables())
    if check and result.returncode:
        raise ClaimCheckRefusal(
            f"`git {' '.join(arguments)}` failed with exit {result.returncode}: {result.stderr.strip()}\n"
            "If the repository is damaged or the revision is wrong: fix that, then run this again.")
    return result


def fresh_agent_prompt(template, overview_path, commit, writer_answers, assertion=None):
    return template.format(
        page=HOW_TO_PAGE, overview=overview_path, commit=commit, assertion=assertion,
        ranks=CLAIM_RANK_DEFINITIONS_FOR_FRESH_AGENT_PROMPT,
        writer_answers=FRESH_AGENT_WRITER_ANSWERS_TEMPLATE.format(answers=writer_answers) if writer_answers else "",
        recheck_writer_answers=RECHECK_WRITER_ANSWERS_TEMPLATE.format(answers=writer_answers) if writer_answers else "")


def recheck_reports_for_must_fix_claims(worktree, overview_path, commit, writer_answers, report):
    """Run one fresh-agent per claim the report ranks must fix, in parallel; return {claim number: its report}.

    A malformed report has no claims to recheck; the caller reports it as malformed."""
    claims, _malformed = claims_from_fresh_agent_report(report)
    must_fix = [claim for claim in claims or () if claim.rank == RANK_MUST_FIX]
    if not must_fix:
        return {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(must_fix)) as executor:
        futures = {claim.number: executor.submit(
            run_fresh_agent, worktree,
            fresh_agent_prompt(RECHECK_PROMPT_TEMPLATE, overview_path, commit, writer_answers, claim.assertion))
            for claim in must_fix}
        return {number: future.result() for number, future in futures.items()}


def run_fresh_agent(worktree, prompt):
    command = [*command_line_prefix.claude_code_headless_run_command_line_prefix_build(
                   "dontAsk", own_settings=cold_read_claude_cell.SETTINGS),
               "--model", FRESH_AGENT_MODEL, "--effort", FRESH_AGENT_EFFORT,
               "--output-format", "text", "--tools", FRESH_AGENT_TOOLS, "--allowedTools", FRESH_AGENT_TOOLS]
    try:
        # The prompt goes on stdin: variadic --allowedTools can swallow a trailing positional argument.
        result = subprocess.run(command, input=prompt, cwd=worktree, capture_output=True, text=True,
                                timeout=FRESH_AGENT_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as failure:
        raise ClaimCheckRefusal(f"the fresh-agent could not run: {failure}\n"
                                "If `claude` is missing or logged out on this machine: fix that, then run this again.",
                                exit_code=4) from failure
    if result.returncode or not result.stdout.strip():
        raise ClaimCheckRefusal(
            f"the fresh-agent exited {result.returncode} with {'no' if not result.stdout.strip() else 'some'} report, "
            f"so no report was written.\nIts stderr: {result.stderr.strip()[-2000:] or 'empty'}\n"
            f"Its stdout: {result.stdout.strip()[-2000:] or 'empty'}\n"
            "If it says `claude` is logged out or a usage limit is reached: tell the user what it said, then run this "
            "again once it is fixed.", exit_code=4)
    return result.stdout


def failure_removing_worktree(repository, worktree):
    """Remove the temporary worktree; return why that failed, or None.

    Runs inside a `finally`, so it raises nothing: an exception here would replace the refusal in flight and
    turn its exit code into 2."""
    try:
        removal = run_git(repository, "worktree", "remove", "--force", str(worktree), check=False)
    except (OSError, subprocess.TimeoutExpired) as failure:
        return f"`git worktree remove --force {worktree}` could not run: {failure}"
    if removal.returncode:
        return f"`git worktree remove --force {worktree}` failed with exit {removal.returncode}: {removal.stderr.strip()}"
    return None


def check_overview_claims(arguments):
    top_level = run_git(Path.cwd(), "rev-parse", "--show-toplevel", check=False)
    if top_level.returncode:
        raise ClaimCheckRefusal(f"{Path.cwd()} is not inside a git repository, so there is no overview to read.\n"
                                "To check an overview: run this from a checkout of this repository.")
    repository = Path(top_level.stdout.strip())
    overview_path = arguments.overview
    system = nc_architecture_overview_described_system_name_from_page_path(overview_path)
    revision = run_git(repository, "rev-parse", "--verify", f"{arguments.revision}^{{commit}}").stdout.strip()
    if system is None or not run_git(repository, "ls-tree", "-d", "--name-only", revision,
                                     f"nc-systems/{system}").stdout.strip():
        raise ClaimCheckRefusal(
            f"{overview_path} is not an nc-architecture-overview at {revision[:12]}: an overview is at "
            f"{overview_path_reader.PATH_TEMPLATE}, where nc-systems/<system> is a directory.\n"
            "To check an overview: pass its path, relative to the top of the checkout, with --overview.")
    blob = run_git(repository, "rev-parse", "--verify", "--quiet", f"{revision}:{overview_path}", check=False)
    if blob.returncode:
        raise ClaimCheckRefusal(f"{overview_path} is not in {revision[:12]}, so there is nothing to check.\n"
                                "To check it: commit the overview, or pass the revision that holds it with --revision.")
    blob = blob.stdout.strip()
    text = run_git(repository, "cat-file", "blob", blob).stdout
    named_commit = overview_path_reader.checked_against_commit(text)
    if named_commit is None:
        raise ClaimCheckRefusal(
            f"{overview_path} has no **Checked against:** last line, so no commit names the code to check it against.\n"
            f"To check it: end the overview with the line the page {HOW_TO_PAGE} gives, naming the commit you "
            "checked it against, commit it, then run this again.")
    commit = run_git(repository, "rev-parse", "--verify", "--quiet", f"{named_commit}^{{commit}}", check=False)
    if commit.returncode:
        raise ClaimCheckRefusal(f"commit {named_commit}, which the overview's **Checked against:** line names, is not "
                                f"in the repository at {repository}.\n"
                                f"To make it available: run `git -C {repository} fetch origin`, then run this again.")
    commit = commit.stdout.strip()
    if run_git(repository, "rev-parse", "--verify", "--quiet", "refs/remotes/origin/main", check=False).returncode:
        raise ClaimCheckRefusal(f"origin/main is missing from the repository at {repository}, so this program cannot "
                                "tell whether a follow-up pull request is due for claims ranked fix later.\n"
                                f"To make it available: run `git -C {repository} fetch origin`, then run this again.")
    program_file_prefix = (Path(overview_path).stem + PROPOSED_IMPROVEMENTS_OR_CHANGES_INFIX
                           + PROPOSED_IMPROVEMENTS_OR_CHANGES_SOURCE + "-")
    fix_later_for_regular_maintenance = any(
        Path(path).name.startswith(program_file_prefix)
        for path in run_git(repository, "ls-tree", "--name-only", "refs/remotes/origin/main",
                            f"{Path(overview_path).parent}/").stdout.splitlines())
    report_directory = Path(arguments.report_directory)
    if not report_directory.parent.is_dir():
        raise ClaimCheckRefusal(
            f"{report_directory.parent} does not exist on this machine, so the report has nowhere to go.\n"
            "If you are on the Mac: run this on ned-box, where the log-store is, as "
            "ssh nedlern@ned-box 'cd <a checkout there> && python3 <this program> ...'.")
    if arguments.writer_answers is not None and not arguments.writer_answers.is_file():
        raise ClaimCheckRefusal(f"--writer-answers {arguments.writer_answers} is not a file.\n"
                                "To pass the writer's answers: write them to a file and give its path.")
    writer_answers = arguments.writer_answers.resolve() if arguments.writer_answers else None

    with tempfile.TemporaryDirectory(prefix=PROGRAM + "-") as temporary:
        # git records a worktree by its resolved path; once the folder is deleted, an unresolved path (macOS /var is a
        # symlink) no longer matches that record, and the printed `worktree remove --force` would fail.
        worktree = Path(temporary).resolve() / "checkout-at-checked-against-commit"
        run_git(repository, "worktree", "add", "--quiet", "--detach", str(worktree), commit)
        try:
            (worktree / overview_path).parent.mkdir(parents=True, exist_ok=True)
            (worktree / overview_path).write_text(text, encoding="utf-8")
            try:
                lint = subprocess.run([sys.executable, str(worktree / "scripts" / "md-drift-lint.py"),
                                       str(worktree / overview_path)], cwd=worktree, capture_output=True, text=True,
                                      timeout=MD_DRIFT_LINT_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired as failure:
                raise ClaimCheckRefusal(f"md-drift-lint did not finish in {MD_DRIFT_LINT_TIMEOUT_SECONDS} s, "
                                        "so no fresh-agent ran.\nRun this again; if it times out again, tell the user.",
                                        exit_code=4) from failure
            if lint.returncode == 1:
                raise ClaimCheckRefusal(
                    "md-drift-lint found problems in the overview, so no fresh-agent ran:\n"
                    + lint.stdout.replace(str(worktree) + "/", "")
                    + "To go on: fix each problem in the overview, commit it, then run this again.", exit_code=3)
            if lint.returncode != 0:
                raise ClaimCheckRefusal(f"md-drift-lint exited {lint.returncode}, so no fresh-agent ran:\n"
                                        f"{lint.stdout}{lint.stderr}"
                                        "Do what its output says, then run this again.", exit_code=4)
            report = run_fresh_agent(worktree, fresh_agent_prompt(
                FRESH_AGENT_PROMPT_TEMPLATE, overview_path, commit, writer_answers))
            recheck_reports = recheck_reports_for_must_fix_claims(worktree, overview_path, commit, writer_answers,
                                                                  report)
        finally:
            worktree_removal_failure = failure_removing_worktree(repository, worktree)
            if worktree_removal_failure:
                print(f"{PROGRAM}: {worktree_removal_failure}\n"
                      "Only the cleanup failed: the claim check's own result is printed apart from this.\n"
                      f"To clean up, once this program has exited: run `git -C {repository} worktree remove --force "
                      f"{worktree}`, then check that `git -C {repository} worktree list` no longer shows {worktree}; if it does, tell "
                      "the user.", file=sys.stderr)

    claims, result = result_from_fresh_agent_report(report, recheck_reports)
    destination_directory = overview_write_architecture_overview_claim_check_report_directory_for_overview(report_directory, overview_path)
    destination_directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
    destination = destination_directory / f"{blob}-{stamp}.md"
    ranks = ", ".join(f"{count} {rank}" for rank, count in rank_counts(claims).items()) if claims else "none"
    rechecks = "".join(f"\n\n# Recheck of VERDICT {number}, which the report above ranks must-fix\n\n{recheck}"
                       for number, recheck in sorted(recheck_reports.items()))
    destination.write_text(
        f"overview: {overview_path}\noverview blob: {blob}\nrevision: {revision}\nchecked against: {commit}\n"
        f"writer answers: {writer_answers or 'none'}\n{RESULT_LINE_PREFIX}{result}\n"
        f"ranks after the recheck: {ranks}\n\n{report}{rechecks}", encoding="utf-8")
    print(f"{PROGRAM}: {result}. Report: {destination}")
    if claims is None:
        arguments.next_action = (
            NEXT_ACTION_WHEN_FRESH_AGENT_REPORT_IS_MALFORMED_FIRST_TIME
            if malformed_report_count_for_overview_git_blob(destination_directory, blob) < 2
            else NEXT_ACTION_WHEN_FRESH_AGENT_REPORT_IS_MALFORMED_AGAIN.format(directory=destination_directory, blob=blob))
        return 5
    fix_later_file = write_fix_later_claims_to_proposed_improvements_or_changes_file(
        repository, overview_path, claims, commit, destination, fix_later_for_regular_maintenance)
    all_supported = result == OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED
    if not all_supported and result != OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_NO_MUST_FIX_CLAIM_REMAINS:
        code, action = 5, NEXT_ACTION_WHEN_MUST_FIX_CLAIMS_REMAIN
    elif worktree_removal_failure:
        code, action = 6, (NEXT_ACTION_BY_EXIT_CODE[6] if all_supported
                           else NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS_AND_WORKTREE_STAYS)
    else:
        code, action = 0, NEXT_ACTION_BY_EXIT_CODE[0] if all_supported else NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS
    if fix_later_file:
        print(f"{PROGRAM}: claims ranked fix later written to {fix_later_file}")
        action += (NEXT_ACTION_SUFFIX_WHEN_FOLLOW_UP_PULL_REQUEST_LEAVES_FIX_LATER_CLAIMS_TO_REGULAR_MAINTENANCE
                   if fix_later_for_regular_maintenance
                   else NEXT_ACTION_SUFFIX_WHEN_FIX_LATER_CLAIMS_WRITTEN_TO_PROPOSED_IMPROVEMENTS_OR_CHANGES_FILE
                   ).format(path=fix_later_file)
        pointer_line = overview_pointer_line_to_proposed_improvements_or_changes_files(overview_path)
        if pointer_line not in text.splitlines():
            action += NEXT_ACTION_SUFFIX_WHEN_OVERVIEW_LACKS_PROPOSED_IMPROVEMENTS_OR_CHANGES_POINTER_LINE.format(line=pointer_line)
    arguments.next_action = action
    return code


def main(argv=None):
    parser = RefusingArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--overview", required=True, metavar="PATH",
                        help="the overview's path, relative to the top of the checkout")
    parser.add_argument("--revision", default="HEAD", help="the commit or branch whose overview text is checked")
    parser.add_argument("--writer-answers", type=Path, metavar="FILE",
                        help="the writer's answers to disputed verdicts of an earlier report")
    parser.add_argument("--report-directory", type=Path, default=OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_REPORT_DIRECTORY,
                        metavar="DIR")
    arguments = None
    try:
        arguments = parser.parse_args(argv)
        code = check_overview_claims(arguments)
    except ClaimCheckRefusal as refusal:
        print(f"{PROGRAM}: {refusal}", file=sys.stderr)
        code = refusal.exit_code
    print_next_action(code, getattr(arguments, "next_action", None))
    return code


def print_next_action(code, action=None):
    """Print the next action as the run's last line: the overview-write skill's step 3 is to do what it says.

    It goes to stdout after stderr is flushed, so a reader of both streams together sees it last."""
    sys.stderr.flush()
    action = action or NEXT_ACTION_BY_EXIT_CODE[code]
    print(f"{NEXT_ACTION_LINE_PREFIX}{action}", flush=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as defect:
        print(f"{PROGRAM}: program defect: {type(defect).__name__}: {defect}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print_next_action(2)
        sys.exit(2)
