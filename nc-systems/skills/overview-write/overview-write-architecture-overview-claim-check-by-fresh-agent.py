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
   of the page and fixes the report's form, so this program can count the
   verdicts. --writer-answers gives it the writer's answers to verdicts the
   writer disputes, as the page's rounds allow.
5. Writes the report, under a header this program writes, to
   <report directory>/<overview file name without .md>/<overview blob>-<UTC time>.md.
   The blob names the overview's exact text, which holds the commit it is
   checked against, so a report stays valid across a rebase or a fix-round
   that leaves the overview's text alone, and no model runs again for it.

scripts/pull-request-review-plan.py refuses a pull request that adds or changes
an overview until the newest report for the overview's blob at the pull
request's head says OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED; it reads reports with
find_newest_architecture_overview_claim_check_report_path_and_result_for_overview_git_blob() from this file.

Does not handle: a verdict the user rules on after two disputed rounds (the
page sends it to the user; no report records his ruling); an overview not on
the path the page gives; a run on the Mac, where the log-store is not local.
Failures: every failure is printed to stderr with what to do and exits
nonzero; no report is written unless the fresh-agent produced output. The
temporary worktree is removed on every path, including a failure; when git
cannot remove it, the program prints git's words and the worktree's path, and
exits 6 even after writing a report, unless an earlier failure already set its
exit code, which it keeps; git's record of the worktree stays in the checkout
until `git worktree prune` runs. Apart from that record, the
program writes nothing in the checkout it is run from.

Usage:
  python3 nc-systems/skills/overview-write/overview-write-architecture-overview-claim-check-by-fresh-agent.py \\
      --overview docs/nedschorus-wiki/nedschorus-handoff-architecture-overview.md \\
      [--revision <commit or branch>] [--writer-answers FILE] [--report-directory DIR]

Exit 0: report written, every claim supported. 1: refused, nothing run.
2: program defect. 3: md-drift-lint found problems, so no fresh-agent ran.
4: the fresh-agent failed, so no report was written. 5: report written, and
not every claim is supported, or the report is malformed. 6: git could not
remove the temporary worktree; any report was still written, and its result
printed.
"""

import argparse
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

VERDICT_LINE = re.compile(r"^VERDICT (\d+) (supported|contradicted|unsupported):", re.MULTILINE)
COUNTS_LINE = re.compile(r"^COUNTS supported=(\d+) contradicted=(\d+) unsupported=(\d+)\s*$", re.MULTILINE)

FRESH_AGENT_PROMPT_TEMPLATE = """\
You are the fresh-agent of stage 2 of the section "Checking an overview" in {page}. Read that page, then check the nc-architecture-overview {overview} against the repository in your working directory, a checkout at commit {commit}, which the overview's last line names. Stage 1 has passed. Do stage 2 as the page says, leaving out what the page says is not checked against the code. You have the Read, Grep and Glob tools only, and cannot change files or run commands.
{writer_answers}
Your final message is the report. A program counts its verdicts and treats a report in any other form as a failed check, so write it in this form:
- One block per assertion, which the page calls a row, numbered from 1 in the overview's order. Each block starts with the line `VERDICT <number> <verdict>: <the assertion>`, where <verdict> is supported, contradicted or unsupported. The lines after it, in any form, give the evidence the page asks for that verdict; the program does not read them.
- The last line is `COUNTS supported=<number> contradicted=<number> unsupported=<number>`.
"""

FRESH_AGENT_WRITER_ANSWERS_TEMPLATE = """\
The overview's writer disputes verdicts of an earlier check. The file {answers} names each disputed assertion and gives the writer's answer, with the quoted line it rests on. Check every assertion as above; for each disputed one, read the writer's answer too, and give the verdict the code bears out.
"""


class ClaimCheckRefusal(Exception):
    def __init__(self, message, exit_code=1):
        super().__init__(message)
        self.exit_code = exit_code


class RefusingArgumentParser(argparse.ArgumentParser):
    """Keep exit 2 for program defects: malformed arguments are a refusal."""

    def error(self, message):
        raise ClaimCheckRefusal(f"{message}\nTo see the arguments: run this with --help.")


def architecture_overview_system_from_path(path):
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


def result_from_fresh_agent_report(report):
    """Return the report's result: OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED, the counts that fall short, or why it is malformed."""
    verdicts = VERDICT_LINE.findall(report)
    counts = COUNTS_LINE.findall(report)
    if not verdicts:
        return "malformed: no VERDICT line"
    numbers = [int(number) for number, _ in verdicts]
    if numbers != list(range(1, len(numbers) + 1)):
        return "malformed: the VERDICT lines are not numbered 1, 2, 3 and on in order"
    if len(counts) != 1:
        return f"malformed: {len(counts)} COUNTS lines, not one"
    tally = {verdict: sum(1 for _, found in verdicts if found == verdict)
             for verdict in ("supported", "contradicted", "unsupported")}
    stated = dict(zip(("supported", "contradicted", "unsupported"), (int(value) for value in counts[0])))
    if stated != tally:
        return f"malformed: the COUNTS line says {stated}, but the VERDICT lines give {tally}"
    if tally["contradicted"] == 0 and tally["unsupported"] == 0:
        return OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED
    return (f"not all claims supported: {tally['contradicted']} contradicted, "
            f"{tally['unsupported']} unsupported, {tally['supported']} supported")


def run_git(repository, *arguments, check=True):
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments], capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS,
        env=git_redirecting_removal.environment_without_git_redirecting_variables())
    if check and result.returncode:
        raise ClaimCheckRefusal(
            f"`git {' '.join(arguments)}` failed with exit {result.returncode}: {result.stderr.strip()}\n"
            "If the repository is damaged or the revision is wrong: fix that, then run this again.")
    return result


def run_fresh_agent(worktree, overview_path, commit, writer_answers):
    prompt = FRESH_AGENT_PROMPT_TEMPLATE.format(
        page=HOW_TO_PAGE, overview=overview_path, commit=commit,
        writer_answers=FRESH_AGENT_WRITER_ANSWERS_TEMPLATE.format(answers=writer_answers) if writer_answers else "")
    command = ["claude", "-p", "--model", FRESH_AGENT_MODEL, "--effort", FRESH_AGENT_EFFORT,
               "--output-format", "text", "--tools", FRESH_AGENT_TOOLS, "--allowedTools", FRESH_AGENT_TOOLS,
               "--settings", cold_read_claude_cell.SETTINGS]
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


def check_overview_claims(arguments):
    top_level = run_git(Path.cwd(), "rev-parse", "--show-toplevel", check=False)
    if top_level.returncode:
        raise ClaimCheckRefusal(f"{Path.cwd()} is not inside a git repository, so there is no overview to read.\n"
                                "To check an overview: run this from a checkout of this repository.")
    repository = Path(top_level.stdout.strip())
    overview_path = arguments.overview
    system = architecture_overview_system_from_path(overview_path)
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
            f"To check it: end the overview with the line the page {HOW_TO_PAGE} gives, naming the main commit you "
            "checked it against, commit it, then run this again.")
    commit = run_git(repository, "rev-parse", "--verify", "--quiet", f"{named_commit}^{{commit}}", check=False)
    if commit.returncode:
        raise ClaimCheckRefusal(f"commit {named_commit}, which the overview's **Checked against:** line names, is not "
                                f"in the repository at {repository}.\n"
                                f"To make it available: run `git -C {repository} fetch origin`, then run this again.")
    commit = commit.stdout.strip()
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
        worktree = Path(temporary) / "checkout-at-checked-against-commit"
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
            report = run_fresh_agent(worktree, overview_path, commit, writer_answers)
        finally:
            worktree_removal = run_git(repository, "worktree", "remove", "--force", str(worktree), check=False)
            run_git(repository, "worktree", "prune", check=False)
            if worktree_removal.returncode:
                print(f"{PROGRAM}: `git worktree remove --force {worktree}` failed with exit "
                      f"{worktree_removal.returncode}: {worktree_removal.stderr.strip()}\n"
                      f"To clean up, once this program has exited: run `git -C {repository} worktree prune`, then "
                      f"check that `git -C {repository} worktree list` no longer shows {worktree}; if it does, tell "
                      "the user.", file=sys.stderr)

    result = result_from_fresh_agent_report(report)
    destination_directory = overview_write_architecture_overview_claim_check_report_directory_for_overview(report_directory, overview_path)
    destination_directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
    destination = destination_directory / f"{blob}-{stamp}.md"
    destination.write_text(
        f"overview: {overview_path}\noverview blob: {blob}\nrevision: {revision}\nchecked against: {commit}\n"
        f"writer answers: {writer_answers or 'none'}\n{RESULT_LINE_PREFIX}{result}\n\n{report}", encoding="utf-8")
    print(f"{PROGRAM}: {result}. Report: {destination}")
    if worktree_removal.returncode:
        return 6
    return 0 if result == OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED else 5


def main(argv=None):
    parser = RefusingArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--overview", required=True, metavar="PATH",
                        help="the overview's path, relative to the top of the checkout")
    parser.add_argument("--revision", default="HEAD", help="the commit or branch whose overview text is checked")
    parser.add_argument("--writer-answers", type=Path, metavar="FILE",
                        help="the writer's answers to disputed verdicts of an earlier report")
    parser.add_argument("--report-directory", type=Path, default=OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_REPORT_DIRECTORY,
                        metavar="DIR")
    try:
        return check_overview_claims(parser.parse_args(argv))
    except ClaimCheckRefusal as refusal:
        print(f"{PROGRAM}: {refusal}", file=sys.stderr)
        return refusal.exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as defect:
        print(f"{PROGRAM}: program defect: {type(defect).__name__}: {defect}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(2)
