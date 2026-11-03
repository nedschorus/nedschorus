#!/usr/bin/env python3
"""Run the five merge-lane steps that review a pull request, the last three at the same time.

Usage:
  scripts/merge-lane-pull-request-worktrees-reviewer-brief-codex-review-and-head-tests-run-without-merge.py
      <pull request number> <brief specifications file> [--head-commit-reviewed-before COMMIT]
      [--merge-lane-worktrees-and-outputs-directory DIR] [--merge-lane-review-worktrees-directory DIR] [--review-tools-worktree-at-main DIR]

Before any step runs, git in --review-tools-worktree-at-main fetches main and
refs/pull/<n>/head from origin and reads the two commits once. The Codex
review's base is the merge base of those two commits, or, for a fix-round,
the commit given as --head-commit-reviewed-before.

The brief specifications file holds merge-lane-2's judgments in exactly one
entry, for this pull request: tag, number, title, author, tests, hazards and
claude_reviewer, true when the pull request's review tier calls for a Claude
reviewer and false when it does not, and optionally overlaps. A fix-round entry also has reviewed_before,
previous_reviews, new_commits and answer; an entry is a fix-round exactly
when --head-commit-reviewed-before is given, and its reviewed_before names
that same commit. The entry need not name head or main; when it does, each
must name the commit read from origin, so a push after the facts were written
stops the run. The file given is never changed: a copy with head and main
filled in is written to
briefs/reviewer-brief-specifications-pr<n>-with-head-and-main-commits-from-origin.json under the
worktrees and outputs directory, and step 2 reads that copy. Last,
--review-tools-worktree-at-main is checked out, detached, at the main commit
read from origin, so every step runs main's scripts, and only then is each
step script looked for there.

Runs at the same time need separate --review-tools-worktree-at-main
worktrees: each run checks its worktree out at main, and moving a worktree
that a running Codex cell reads from makes that cell exit 64.

Then each step runs from --review-tools-worktree-at-main's scripts/, never
the pull request's, with those commits and all three directory options:
  1. merge-lane-pull-request-head-and-merged-worktrees-rebuild.py <n> <head> <main>
  2. merge-lane-pull-request-reviewer-brief-compose-with-facts.py <the filled-in copy>
  3. merge-lane-code-review-codex-cell-run-on-pull-request-head.py <n> <base>
  4. merge-lane-pull-request-head-test-run-on-merged-worktree.py <n>
  5. merge-lane-pull-request-claude-reviewer-headless-run-and-review-post.py <n> <tag> <head>,
     which runs the Claude reviewer and posts its review, only when the entry's
     claude_reviewer is true; when it is false, step 5 is skipped and the output
     says so.
Steps 1 and 2 run one after the other, and the run stops at the first of
them that fails, before steps 3 to 5 start, because those read what steps 1
and 2 made. Steps 3, 4 and 5 then start at the same time, since none reads
what another writes, and the run waits for all of them; one failing does not
stop the others. Each step's own output passes through: steps 1 and 2 as it
is, and each line of steps 3 to 5 prefixed with its step's number, as in
"step 4 of 5 | ", because their lines interleave. When one of steps 3 to 5
fails, the output names each step that failed with its exit code, says what
each other step did, and gives each failed step's own command, with the same
commits, for running that step alone: running this program again would run
the other steps again, and post a second Claude review. If this program is
interrupted while steps run, it stops them: steps 3 and 4 get SIGKILL, and step
5 gets SIGTERM, so that it stops the Claude reviewer before any review is
posted, then SIGKILL if it has not ended within
CLAUDE_REVIEWER_STEP_STOP_SECONDS. If this program cannot write its own
output while steps 3 to 5 run, as when the reader of its stdout has gone, it
still reads every step's output to its end, so no step blocks, and once every
step has ended it exits 1, naming the error and each step's exit code on
stderr. Nothing here
merges: merging is
merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py.

Exit codes: 0 every step that ran exited 0; 1 a step exited nonzero, named on
stdout: when it was step 1 or 2, no later step ran, and when it was one of
steps 3 to 5, the others ran to their end; also 1 when this program's own
output could not be written while steps 3 to 5 ran, named on stderr; 2 refused before any step ran: a step script
is missing, git could not fetch, read or check out a commit, the brief
specifications file is unreadable, lacks a field, has a claude_reviewer that
is not true or false, or disagrees with the
commits, or the filled-in copy could not be written, named on stdout.
"""

import argparse
import importlib.util
import json
import shlex
import subprocess
import sys
import threading
from pathlib import Path

WORKTREES_REBUILD_STEP = "merge-lane-pull-request-head-and-merged-worktrees-rebuild.py"
REVIEWER_BRIEF_STEP = "merge-lane-pull-request-reviewer-brief-compose-with-facts.py"
CODEX_REVIEW_STEP = "merge-lane-code-review-codex-cell-run-on-pull-request-head.py"
HEAD_TEST_RUN_STEP = "merge-lane-pull-request-head-test-run-on-merged-worktree.py"
CLAUDE_REVIEWER_STEP = "merge-lane-pull-request-claude-reviewer-headless-run-and-review-post.py"
STEPS = (WORKTREES_REBUILD_STEP, REVIEWER_BRIEF_STEP, CODEX_REVIEW_STEP, HEAD_TEST_RUN_STEP,
         CLAUDE_REVIEWER_STEP)
CLAUDE_REVIEWER_STEP_STOP_SECONDS = 10

# The fields REVIEWER_BRIEF_STEP reads from every entry and from a fix-round
# entry, apart from head and main, which this program fills in. Keep in step
# with that script's compose().
ENTRY_FIELDS = ("tag", "number", "title", "author", "tests", "hazards", "claude_reviewer")
FIX_ROUND_ENTRY_FIELDS = ("reviewed_before", "previous_reviews", "new_commits", "answer")
FILLED_IN_BRIEF_SPECIFICATIONS_FILE_NAME = (
    "reviewer-brief-specifications-pr{number}-with-head-and-main-commits-from-origin.json")

GENERIC_INSTRUCTION = ("If the message above names a cause you can fix, fix it and run this "
                       "again.\n"
                       "Otherwise, tell the user this message.")
CORRECT_THE_FILE_INSTRUCTION = "Correct the file and run this again."
FILE_OR_FLAG_INSTRUCTION = (
    "Correct whichever of the two is wrong, the file's entry or the "
    "--head-commit-reviewed-before option, which a first round leaves out, and run this "
    "again.")
NEWLINE = "\n"
# The words git prints when a checkout would overwrite local changes,
# tracked or untracked.
CHECKOUT_WOULD_OVERWRITE_CHANGES = "would be overwritten by checkout"

_common_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_helpers_common", Path(__file__).resolve().with_name(
        "merge-lane-pull-request-helpers-common-options-paths-and-token.py"))
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)
run_all_test_suites = common.run_all_test_suites


class RefusedBeforeAnyStep(Exception):
    """What stopped the run; instruction is printed after it, or nothing when None."""

    def __init__(self, what_stopped, instruction=GENERIC_INSTRUCTION):
        super().__init__(what_stopped)
        self.instruction = instruction


class OutputCouldNotBeWritten(Exception):
    """This program's stdout failed while steps ran; exit_codes holds how each step ended."""

    def __init__(self, failure, exit_codes):
        super().__init__(str(failure))
        self.exit_codes = exit_codes


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Move the review tools worktree to main, then rebuild a pull request's "
                    "worktrees, compose its reviewer brief, run the Codex review, run the "
                    "head tests and, when the entry asks for one, run the Claude reviewer "
                    "and post its review; the last three run at the same time. Does not "
                    "merge. "
                    "Runs at the same time need separate --review-tools-worktree-at-main "
                    "worktrees, because moving a worktree that a running Codex cell reads "
                    "from makes that cell exit 64.")
    parser.add_argument("pull_request", type=int, help="the pull request's number")
    parser.add_argument("brief_specifications_file", type=Path,
                        help="merge-lane-2's JSON brief specifications file for this pull "
                             "request; head and main may be left out, because this program "
                             "fills them in from origin; a head or main the file does name "
                             "must be origin's commit for that field")
    parser.add_argument("--head-commit-reviewed-before",
                        help="for a fix-round, the nc-head-commit reviewed before; the Codex "
                             "review runs from it instead of from the merge base")
    common.add_directory_options(parser, "briefs/, cx/, hr/, claude-reviews/ and tripwire-bin/")
    return common.resolve_path_options(parser.parse_args(argv))


def git(directory, *arguments, accepted_exit_codes=(0,)):
    completed = subprocess.run(
        ["git", "-C", str(directory), *arguments], capture_output=True, text=True,
        stdin=subprocess.DEVNULL,
        env=run_all_test_suites.environment_without_git_redirecting_variables())
    if completed.returncode not in accepted_exit_codes:
        raise RefusedBeforeAnyStep(
            f"git {' '.join(arguments)} in {directory} exited {completed.returncode}: "
            f"{completed.stderr.strip()}")
    return completed.stdout.strip()


def fetched_commit(checkout, reference):
    # One reference per fetch, so FETCH_HEAD names that reference's commit alone.
    git(checkout, "fetch", "-q", "origin", reference)
    return git(checkout, "rev-parse", "--verify", "FETCH_HEAD^{commit}")


def resolved_commit(checkout, commit):
    """Return commit's full name, or None when the checkout has no such commit."""
    # With --quiet, git exits 1 and prints nothing when there is no such commit.
    return git(checkout, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}",
               accepted_exit_codes=(0, 1)) or None


def brief_specification_disagreement(checkout, specifications, number, head, main,
                                     head_reviewed_before):
    """Return (what is wrong with the brief specifications, what to do), or None."""
    if not isinstance(specifications, list) or len(specifications) != 1:
        return (f"it must hold a JSON list of exactly one entry, for pull request {number}, "
                f"because the brief step composes a brief for every entry",
                CORRECT_THE_FILE_INSTRUCTION)
    entry = specifications[0]
    if not isinstance(entry, dict) or entry.get("number") != number:
        return f"its one entry is not for pull request {number}", CORRECT_THE_FILE_INSTRUCTION
    if head_reviewed_before is None and "reviewed_before" in entry:
        return (f"its entry is a fix-round, with reviewed_before {entry['reviewed_before']}, "
                f"but --head-commit-reviewed-before was not given, so the Codex review would "
                f"run from the merge base", FILE_OR_FLAG_INSTRUCTION)
    if head_reviewed_before is not None and "reviewed_before" not in entry:
        return (f"--head-commit-reviewed-before {head_reviewed_before} makes this a "
                f"fix-round, but its entry has no reviewed_before, so the brief would "
                f"describe a first round", FILE_OR_FLAG_INSTRUCTION)
    fields = ENTRY_FIELDS + (FIX_ROUND_ENTRY_FIELDS if head_reviewed_before is not None else ())
    missing = [field for field in fields if field not in entry]
    if missing:
        return (f"its entry has no {', '.join(missing)}, which the brief step reads; "
                f"an entry needs {', '.join(ENTRY_FIELDS)}, and a fix-round entry also "
                f"needs {', '.join(FIX_ROUND_ENTRY_FIELDS)}", CORRECT_THE_FILE_INSTRUCTION)
    if not isinstance(entry["claude_reviewer"], bool):
        return (f"its claude_reviewer is {entry['claude_reviewer']!r}, not true or false",
                CORRECT_THE_FILE_INSTRUCTION)
    for field, commit in (("head", head), ("main", main)):
        if field in entry and resolved_commit(checkout, str(entry[field])) != commit:
            return (f"its {field} is {entry[field]}, but origin's {field} commit is {commit}, "
                    f"so the entry's judgments may be about another commit",
                    f"If the entry's judgments hold for {commit}, delete {field} from the "
                    f"entry, and this program fills it in.\n"
                    f"If they do not, rewrite the judgments for {commit} and delete {field} "
                    f"from the entry.\n"
                    f"Then run this again.")
    if head_reviewed_before is not None and resolved_commit(
            checkout, str(entry["reviewed_before"])) != head_reviewed_before:
        return (f"its reviewed_before is {entry['reviewed_before']}, but "
                f"--head-commit-reviewed-before is {head_reviewed_before}",
                FILE_OR_FLAG_INSTRUCTION)
    return None


def step_command(step, arguments, step_arguments):
    return [sys.executable, str(arguments.review_tools_worktree_at_main / "scripts" / step),
            *step_arguments, *common.directory_options_argv(arguments)]


def run_step(position, step, arguments, step_arguments):
    print(f"step {position} of {len(STEPS)}: {step}", flush=True)
    return subprocess.run(
        step_command(step, arguments, step_arguments), stdin=subprocess.DEVNULL,
        env=run_all_test_suites.environment_without_git_redirecting_variables()).returncode


def run_steps_at_the_same_time(positioned_steps, arguments):
    """Run each (position, step, step arguments) at once; return {position: exit code}.

    When this program's own output cannot be written, a start line included, every
    step still starts and its output is still read to its end, so no step blocks on a
    full pipe; nothing more is printed, and the first such error is raised, as
    OutputCouldNotBeWritten, once every step has ended.
    """
    print_lock = threading.Lock()
    output_failures = []

    def print_unless_output_failed(text):
        with print_lock:
            if output_failures:
                return
            try:
                print(text, flush=True)
            except (OSError, ValueError) as failure:
                output_failures.append(failure)

    def pass_output_through(position, stream):
        for line in stream:
            print_unless_output_failed(f"step {position} of {len(STEPS)} | {line.rstrip(NEWLINE)}")

    processes, readers = {}, []
    try:
        for position, step, step_arguments in positioned_steps:
            print_unless_output_failed(f"step {position} of {len(STEPS)}: {step}")
            # errors= opens the pipe as text.
            process = subprocess.Popen(
                step_command(step, arguments, step_arguments), stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, errors="replace",
                env=run_all_test_suites.environment_without_git_redirecting_variables())
            processes[position] = process
            reader = threading.Thread(target=pass_output_through,
                                      args=(position, process.stdout))
            reader.start()
            readers.append(reader)
        exit_codes = {position: process.wait() for position, process in processes.items()}
    except BaseException:
        # The Claude reviewer step's SIGTERM handler stops claude before gh can post
        # its review; SIGKILL would skip that handler.
        for position, process in processes.items():
            if process.poll() is None:
                if STEPS[position - 1] == CLAUDE_REVIEWER_STEP:
                    process.terminate()
                else:
                    process.kill()
        for position, process in processes.items():
            if STEPS[position - 1] == CLAUDE_REVIEWER_STEP:
                try:
                    process.wait(timeout=CLAUDE_REVIEWER_STEP_STOP_SECONDS)
                except subprocess.TimeoutExpired:
                    process.kill()
        raise
    for reader in readers:
        reader.join()
    if output_failures:
        raise OutputCouldNotBeWritten(output_failures[0], exit_codes) from output_failures[0]
    return exit_codes


def main(argv=None):
    arguments = parse_arguments(argv)
    number = arguments.pull_request
    checkout = arguments.review_tools_worktree_at_main
    filled_in_specifications_file = (
        arguments.merge_lane_worktrees_and_outputs_directory / "briefs"
        / FILLED_IN_BRIEF_SPECIFICATIONS_FILE_NAME.format(number=number))
    try:
        if not checkout.is_dir():
            raise RefusedBeforeAnyStep(
                common.review_tool_missing_message(arguments, Path("scripts") / STEPS[0]),
                instruction=None)
        main_commit = fetched_commit(checkout, "refs/heads/main")
        head_commit = fetched_commit(checkout, f"refs/pull/{number}/head")
        head_reviewed_before = None
        if arguments.head_commit_reviewed_before is not None:
            head_reviewed_before = resolved_commit(checkout, arguments.head_commit_reviewed_before)
            if head_reviewed_before is None:
                raise RefusedBeforeAnyStep(
                    f"--head-commit-reviewed-before {arguments.head_commit_reviewed_before} "
                    f"is not a commit in {checkout}.",
                    instruction=f"If the commit is right, fetch it into {checkout} and run "
                                f"this again.\n"
                                f"If the commit is wrong, run this again with "
                                f"--head-commit-reviewed-before set to the nc-head-commit that "
                                f"was reviewed before.")
            base, base_kind = head_reviewed_before, "nc-head-commit reviewed before"
        else:
            base, base_kind = git(checkout, "merge-base", main_commit, head_commit), "merge base"
        try:
            specifications = json.loads(arguments.brief_specifications_file.read_text())
        except (OSError, ValueError) as failure:
            raise RefusedBeforeAnyStep(
                f"could not read the brief specifications file "
                f"{arguments.brief_specifications_file}: {failure}") from failure
        disagreement = brief_specification_disagreement(
            checkout, specifications, number, head_commit, main_commit, head_reviewed_before)
        if disagreement:
            what_is_wrong, instruction = disagreement
            raise RefusedBeforeAnyStep(
                f"the brief specifications file {arguments.brief_specifications_file} "
                f"cannot be used for this run: {what_is_wrong}.", instruction=instruction)
        try:
            filled_in_specifications_file.parent.mkdir(parents=True, exist_ok=True)
            filled_in_specifications_file.write_text(json.dumps(
                [{**specifications[0], "head": head_commit, "main": main_commit,
                  **({"reviewed_before": head_reviewed_before}
                     if head_reviewed_before is not None else {})}],
                indent=2) + "\n")
        except OSError as failure:
            raise RefusedBeforeAnyStep(
                f"could not write the brief specifications with head and main filled in to "
                f"{filled_in_specifications_file}: {failure}") from failure
        try:
            git(checkout, "checkout", "-q", "--detach", main_commit)
        except RefusedBeforeAnyStep as failure:
            if CHECKOUT_WOULD_OVERWRITE_CHANGES not in str(failure):
                raise
            raise RefusedBeforeAnyStep(
                str(failure),
                instruction=f"Tell the user this message and wait for the user's answer. "
                            f"Leave the changes in {checkout} as they are, whatever git "
                            f"suggests above: do not move, remove, discard, stash or "
                            f"overwrite them, because they may be someone's unsaved "
                            f"work.") from failure
        for step in STEPS:
            missing = common.review_tool_missing_message(arguments, Path("scripts") / step)
            if missing:
                raise RefusedBeforeAnyStep(missing, instruction=None)
    except RefusedBeforeAnyStep as refusal:
        print(f"PR {number}: no step run: {refusal}", flush=True)
        if refusal.instruction:
            print(refusal.instruction, flush=True)
        return 2

    print(f"PR {number}: head {head_commit}, main {main_commit}, Codex review base {base} "
          f"({base_kind})", flush=True)
    steps = ((WORKTREES_REBUILD_STEP, [str(number), head_commit, main_commit]),
             (REVIEWER_BRIEF_STEP, [str(filled_in_specifications_file)]),
             (CODEX_REVIEW_STEP, [str(number), base]),
             (HEAD_TEST_RUN_STEP, [str(number)]),
             (CLAUDE_REVIEWER_STEP, [str(number), str(specifications[0]["tag"]), head_commit]))
    claude_reviewer = specifications[0]["claude_reviewer"]
    for position, (step, step_arguments) in enumerate(steps[:2], start=1):
        exit_code = run_step(position, step, arguments, step_arguments)
        if exit_code != 0:
            print(f"PR {number}: stopped at step {position} of {len(STEPS)}, {step}, which "
                  f"exited {exit_code}; no later step ran, and nothing was merged.\n"
                  f"Act on that step's own message, printed above.\n"
                  f"If that message says to run the step again, run this program again "
                  f"instead, so every step uses the same commits.", flush=True)
            return 1
    at_the_same_time = []
    for position, (step, step_arguments) in enumerate(steps[2:], start=3):
        if step == CLAUDE_REVIEWER_STEP and not claude_reviewer:
            print(f"step {position} of {len(STEPS)}: {step}: skipped, because the entry's "
                  f"claude_reviewer is false: this pull request's review tier calls for no "
                  f"Claude reviewer.", flush=True)
            continue
        at_the_same_time.append((position, step, step_arguments))
    try:
        exit_codes = run_steps_at_the_same_time(at_the_same_time, arguments)
    except OutputCouldNotBeWritten as failure:
        # Python's own flush of the broken stdout at exit would change the exit code to 120.
        sys.stdout = None
        outputs = arguments.merge_lane_worktrees_and_outputs_directory
        records = {CODEX_REVIEW_STEP: outputs / "cx" / f"pr{number}-{base[:8]}",
                   HEAD_TEST_RUN_STEP: outputs / "hr" / f"pr{number}",
                   CLAUDE_REVIEWER_STEP: outputs / "claude-reviews" / f"pr{number}-{head_commit}*"}
        def what_to_do(position, step, step_arguments):
            """One step's line: its exit code, and its records or its command."""
            exit_code = failure.exit_codes[position]
            if exit_code != 0:
                return (f"step {position} exited {exit_code}: run it alone, with the same "
                        f"commits, to see its message: "
                        f"{shlex.join(step_command(step, arguments, step_arguments))}")
            why = (", because it has posted its Claude review" if step == CLAUDE_REVIEWER_STEP
                   else "")
            return (f"step {position} exited 0: read its records in {records[step]}, and do "
                    f"not run it again{why}")
        ran = {positioned[0]: positioned for positioned in at_the_same_time}
        steps_to_do = "\n".join(
            f"  {what_to_do(*ran[position])}" if position in ran else
            f"  step {position} was skipped: the entry's claude_reviewer is false"
            for position in range(3, len(STEPS) + 1))
        print(f"PR {number}: the stdout of scripts/{Path(__file__).name} failed while its "
              f"steps 3 to 5 ran at the same time ({failure}), so the lines they printed are "
              f"lost, though each step that ran keeps its own records on disk; steps 1 and 2 "
              f"had exited 0, and nothing was merged.\n"
              f"Each of steps 3 to 5, with what to do for it:\n{steps_to_do}\n"
              f"For this head commit, act on each line above as for any run of this program, "
              f"and do not run this program again for it: it would run every step again.\n"
              f"Before you next run this program, find why its stdout closed, such as a pipe "
              f"into a command that exited early.", file=sys.stderr, flush=True)
        return 1
    failed = [position for position, exit_code in exit_codes.items() if exit_code != 0]
    if failed:
        def what_it_did(position):
            if position not in exit_codes:
                return f"step {position} was skipped"
            if exit_codes[position] != 0:
                return f"step {position}, {STEPS[position - 1]}, exited {exit_codes[position]}"
            if STEPS[position - 1] == CLAUDE_REVIEWER_STEP:
                return f"step {position} exited 0, so its review is posted"
            return f"step {position} exited 0"
        rerun_commands = "\n".join(
            f"  step {position}: {shlex.join(step_command(step, arguments, step_arguments))}"
            for position, step, step_arguments in at_the_same_time if position in failed)
        print(f"PR {number}: {'; '.join(what_it_did(position) for position in (3, 4, 5))}; "
              f"nothing was merged.\n"
              f"Act on each failed step's own message, in the lines above that start "
              f"\"step <n> of {len(STEPS)} | \".\n"
              f"If such a message says to run its step again, run that step alone with its "
              f"command below, not this program: the command uses the same commits, and the "
              f"steps that exited 0 do not run again, so no second Claude review is posted:\n"
              f"{rerun_commands}", flush=True)
        return 1
    outcome = (f"all {len(STEPS)} steps exited 0" if claude_reviewer else
               f"steps 1 to {len(STEPS) - 1} exited 0 and step {len(STEPS)} was skipped")
    print(f"PR {number}: {outcome}; nothing was merged.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
