#!/usr/bin/env python3
"""Measure what enabling dismiss_stale_reviews does, without touching main.

WHY THIS EXISTS. main's branch protection requires one approving review
(live since 2026-08-20). Turning on `dismiss_stale_reviews` would make
GitHub discard that approval whenever new commits arrive, so a reviewer
re-reads what actually merges. Before changing a protection setting on
main, two risks need measuring rather than reasoning about:

  RISK 1, the API call itself. The setting is changed with a PATCH on
  .../branches/<b>/protection/required_pull_request_reviews. If that
  endpoint resets fields the caller omits, sending only
  dismiss_stale_reviews=true could silently drop
  required_approving_review_count to a default -- weakening protection
  while appearing to strengthen it. The 2026-08-20 call that enabled
  reviews sent all three fields explicitly, which hints at this, but a
  hint is not a measurement.

  RISK 2, ordinary pushes. The user's question, verbatim: make sure it
  "doesn't mess up pushes or other stuff". The setting governs review
  state on pull requests targeting the protected branch, so pushes to
  unprotected feature branches should be unaffected -- should is what
  this measures.

WHAT IT DOES NOT COVER, stated so a reader does not mistake a pass here
for full coverage. Observing an approval actually being dismissed needs
two GitHub accounts: GitHub forbids a pull request's author from
approving it, and this script runs as one account. That half is exercised
separately with the merge-lane seat, which holds `ned-review-merge`. A
clean run here says the PATCH is safe and pushes are unaffected. It says
nothing about whether dismissal works, and nothing about whether the lane
can recover from a dismissal.

THE CREDENTIAL. The experiment runs under `ned-review-merge`, unattended
(user-ruled 2026-09-01, PR #228 review item 1). Both endpoints it writes
need the repository ADMIN role: a classic token needs the `repo` scope
held by an admin account, a fine-grained token needs
"Administration: write". GitHub does NOT scope branch-protection
permission per branch, so an account that can protect the throwaway
branch can also rewrite main's protection; the restraint therefore lives
in refuse_if_main below, where it is tested, and not in the credential.
check_experiment_credential runs BEFORE anything is created, so a
credential that cannot do the work is refused at startup rather than
discovered mid-run with a protected branch already on the repository.

WHERE IT RUNS FROM. The program clones the repository into a temporary
directory of its own and commits and pushes from there, removing the
directory when it is done. It never commits into the repository the
operator happens to be standing in (user-ruled 2026-09-01, PR #228
review item 2). A fresh clone also sits at origin/main's tip, so a push
probe can only be refused by branch protection -- which is the thing
being measured -- and never as a stale non-fast-forward.

SAFETY. Every write targets a throwaway branch this script creates and
deletes. It refuses to operate on main by name, and it refuses if the
branch it is about to create already exists. Protection settings for the
throwaway branch are copied from main's live settings so the experiment
runs against the real shape rather than an invented one. main's own
protection is read, never written -- there is no code path in this file
that PATCHes, PUTs, or DELETEs anything under main's protection, and the
refuse_if_main guard is applied to every mutating call. Cleanup runs in a
finally block, so an interrupt, a malformed reply or a missing command
cannot leave a protected branch behind unannounced; when cleanup itself
cannot finish, the two commands that remove the leftover by hand are
printed.

A FAILED CALL IS NOT A MEASUREMENT. Every result that feeds the report is
checked before it is reported: a call that fails is an error and exits
nonzero, and a call that reports success without taking effect is also an
error, because the conclusion this program prints exists only to license a
change to main's protection (user-ruled 2026-09-02, PR #228 review item
3). judge_partial_patch_result holds that judgment, alone and pure, so it
can be tested without a network: see
scripts/protection-experiment-dismiss-stale-reviews-test.py.

USAGE
  python3 scripts/protection-experiment-dismiss-stale-reviews.py --dry-run
  python3 scripts/protection-experiment-dismiss-stale-reviews.py --run

Exit codes: 0 every measurement completed (findings are in the report,
which is printed and may still say the PATCH is unsafe); 1 a measurement
could not be completed and the report says which; 2 bad invocation, a
safety refusal, or a credential that cannot do the work.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO_SLUG = "nedschorus/nedschorus"
REPO_CLONE_URL = "https://github.com/nedschorus/nedschorus.git"
MAIN_BRANCH = "main"
# Named, not generated: a fixed name is greppable, and a leftover from a
# crashed run is recognizable rather than one of a family of random names.
EXPERIMENT_BRANCH = "protection-experiment-dismiss-stale-reviews"
FEATURE_BRANCH = "protection-experiment-dismiss-stale-reviews-feature"
# The account the ruling names. A different admin account is allowed to run
# the experiment and is only noted, never refused: the capability check below
# is the one that decides, because a name is not a permission.
RULED_EXPERIMENT_ACCOUNT = "ned-review-merge"
SCRATCH_CLONE_PREFIX = "protection-experiment-dismiss-stale-reviews-clone-"

# The sibling git-gatekeeper uses thirty seconds for its GitHub calls and the
# same named refusal; this file's runner is a copy of that one and keeps it.
# A clone is the one call that legitimately runs longer.
COMMAND_TIMEOUT_SECONDS = 30
CLONE_TIMEOUT_SECONDS = 300

PATCH_SEMANTICS_PRESERVED = "count-preserved"
PATCH_SEMANTICS_CLOBBERED = "count-clobbered"
PATCH_SEMANTICS_NOT_MEASURED = "not-measured"


class Refusal(Exception):
    """A safety refusal or an impossible measurement. Carries its own fix."""


def refuse_if_main(branch: str) -> None:
    """Every mutating call passes through here first.

    This is where the restraint lives. GitHub cannot scope branch-protection
    permission to one branch, so the credential that protects the throwaway
    branch could rewrite main's protection too; only this guard stops it, and
    a guard in the program is a guard that can be tested.
    """
    if branch.strip().casefold() in {MAIN_BRANCH, "refs/heads/" + MAIN_BRANCH}:
        raise Refusal(
            f"this script never writes to {MAIN_BRANCH}; it was asked to "
            f"write to {branch!r}. Nothing was changed."
        )


def run_command(
    argv: list[str],
    *,
    timeout: int = COMMAND_TIMEOUT_SECONDS,
    cwd: str | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess:
    """The one place an external command is run. stderr is captured, never sunk.

    Three behaviours the git-gatekeeper's copy of this function has and an
    earlier version of this one lost (PR #228 review item 6):

      - a wall-clock limit, so a run cannot hang forever. Output is captured
        to a pipe, so a credential helper's password prompt would go into
        that pipe where nobody sees it, and `timeout` does not exist on this
        Mac to rescue the operator from outside;
      - a named refusal when the command is not installed, instead of a bare
        file-not-found traceback;
      - GIT_TERMINAL_PROMPT=0, which turns git's credential prompt into an
        immediate failure rather than a wait nobody can see.
    """
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        return subprocess.run(
            argv, cwd=cwd, input=input_text, env=environment,
            capture_output=True, text=True, check=False, timeout=timeout,
        )
    except FileNotFoundError:
        raise Refusal(
            f"`{argv[0]}` is not installed on this box, so "
            f"`{' '.join(argv)}` could not run. Install it and re-run."
        ) from None
    except subprocess.TimeoutExpired:
        raise Refusal(
            f"`{' '.join(argv)}` did not finish within {timeout} seconds and "
            "was killed. This failure is safe to retry; if it repeats, check "
            "whether a credential helper is waiting for a password."
        ) from None


def gh(
    args: list[str],
    *,
    allow_failure: bool = False,
    timeout: int = COMMAND_TIMEOUT_SECONDS,
    input_text: str | None = None,
) -> subprocess.CompletedProcess:
    """Run gh. stderr is captured and REPORTED, never discarded.

    A silenced failure that is later trusted is the defect class recorded
    at nedschorus PR #111, so the caller always sees what failed.
    """
    completed = run_command(
        ["gh", *args], timeout=timeout, input_text=input_text
    )
    if completed.returncode != 0 and not allow_failure:
        raise Refusal(
            f"`gh {' '.join(args)}` failed with exit {completed.returncode}.\n"
            f"stderr: {completed.stderr.strip() or '(empty)'}\n"
            f"stdout: {completed.stdout.strip() or '(empty)'}"
        )
    return completed


def api_json(path: str, *, allow_failure: bool = False) -> dict | None:
    completed = gh(["api", path], allow_failure=allow_failure)
    if completed.returncode != 0:
        return None
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise Refusal(f"{path} did not answer JSON: {error}") from None


def check_experiment_credential() -> str:
    """Refuse at startup if this credential cannot do the experiment's writes.

    Two readings, because they answer different questions. The repository
    permissions say whether the ACCOUNT holds the admin role. Reading main's
    protection -- which read_main_protection does next, and which is itself an
    admin-only call -- says whether the TOKEN carries the scope that role
    needs. An account can be admin while its token is not, so neither reading
    alone is the check.

    Returns the login, for the report.
    """
    identity = api_json("user")
    login = (identity or {}).get("login") or "(unknown)"
    repository = api_json(f"repos/{REPO_SLUG}")
    if repository is None:
        raise Refusal(
            f"could not read {REPO_SLUG} as {login}. The experiment needs a "
            "credential that can reach the repository; authenticate gh and "
            "re-run. Nothing was created."
        )
    if not bool((repository.get("permissions") or {}).get("admin")):
        raise Refusal(
            f"{login} does not hold the admin role on {REPO_SLUG}, and both "
            "endpoints this experiment writes -- PUT branch protection and "
            "PATCH required_pull_request_reviews -- need it. Re-run under "
            f"{RULED_EXPERIMENT_ACCOUNT}, whose token must carry the `repo` "
            "scope (classic) or Administration: write (fine-grained). "
            "Nothing was created."
        )
    return login


def read_main_protection() -> dict:
    protection = api_json(f"repos/{REPO_SLUG}/branches/{MAIN_BRANCH}/protection")
    if protection is None:
        raise Refusal(
            "could not read main's protection. GitHub answers 404 both when "
            "protection is absent and when the credential may not read it, so "
            "this does not show protection is missing. Re-run under a "
            "credential that can read branch protection."
        )
    return protection


def protection_payload_from(main_protection: dict, *, dismiss_stale: bool) -> dict:
    """Build a full protection body shaped like main's, for the throwaway branch.

    Restrictions are deliberately dropped: a push allow-list naming real
    accounts is irrelevant to what is being measured here, and copying it
    would make the experiment refuse this script's own setup pushes.

    require_last_push_approval IS copied (PR #228 review item 7c). It is the
    setting closest to the one under test, so dropping it would make the claim
    that protection is copied from main false in exactly the area being
    measured, the moment someone turns it on for main.
    """
    reviews = main_protection.get("required_pull_request_reviews") or {}
    return {
        "required_status_checks": None,
        "enforce_admins": bool(
            (main_protection.get("enforce_admins") or {}).get("enabled")
        ),
        "required_pull_request_reviews": {
            "required_approving_review_count": int(
                reviews.get("required_approving_review_count", 1)
            ),
            "dismiss_stale_reviews": dismiss_stale,
            "require_code_owner_reviews": bool(
                reviews.get("require_code_owner_reviews", False)
            ),
            "require_last_push_approval": bool(
                reviews.get("require_last_push_approval", False)
            ),
        },
        "restrictions": None,
        "allow_force_pushes": bool(
            (main_protection.get("allow_force_pushes") or {}).get("enabled")
        ),
        "allow_deletions": bool(
            (main_protection.get("allow_deletions") or {}).get("enabled")
        ),
    }


def judge_partial_patch_result(
    before: dict | None, after: dict | None
) -> tuple[str, str]:
    """Decide what the partial PATCH actually showed. Pure: no network, no disk.

    RISK 1's whole conclusion is this comparison, and this is where PR #228's
    blocking defect lived: the program compared a number against nothing and
    printed the difference as a finding. Both halves are checked here.

      - `after` missing, or the readings not comparable -> nothing was
        measured. An error, not a finding.
      - dismiss_stale_reviews not True on the read-back -> the call reported
        success without taking effect. Also an error: the PATCH is the thing
        under test, and a PATCH that did nothing measured nothing.
      - the count changed -> the partial form clobbers neighbours; the full
        form is required on main.
      - the count survived -> the partial form is safe.

    Returns (outcome, the sentence to print). Sentences carry their own
    ERROR/FINDING prefix so the wording lives in one place.
    """
    if not isinstance(before, dict) or not isinstance(after, dict):
        return (
            PATCH_SEMANTICS_NOT_MEASURED,
            "ERROR: the review settings could not be read before "
            f"({before!r}) or after ({after!r}) the partial PATCH, so nothing "
            f"was measured. No conclusion about {MAIN_BRANCH}'s protection "
            "follows from this run.",
        )
    dismiss_after = after.get("dismiss_stale_reviews")
    if dismiss_after is not True:
        return (
            PATCH_SEMANTICS_NOT_MEASURED,
            "ERROR: the partial PATCH reported success, but reading the "
            f"setting back shows dismiss_stale_reviews={dismiss_after!r} "
            "rather than True. The call did not take effect, so nothing was "
            f"measured. No conclusion about {MAIN_BRANCH}'s protection "
            "follows from this run.",
        )
    count_before = before.get("required_approving_review_count")
    count_after = after.get("required_approving_review_count")
    if count_before is None or count_after is None:
        return (
            PATCH_SEMANTICS_NOT_MEASURED,
            "ERROR: required_approving_review_count is missing from the "
            f"reading before ({count_before!r}) or after ({count_after!r}) "
            "the partial PATCH, so the two cannot be compared and nothing "
            "was measured.",
        )
    if count_before != count_after:
        return (
            PATCH_SEMANTICS_CLOBBERED,
            "FINDING: the partial PATCH CHANGED "
            f"required_approving_review_count ({count_before} -> "
            f"{count_after}). Any change to {MAIN_BRANCH} must send every "
            "field explicitly.",
        )
    return (
        PATCH_SEMANTICS_PRESERVED,
        "FINDING: the partial PATCH preserved "
        f"required_approving_review_count ({count_after}). Sending every "
        "field explicitly remains the safer form.",
    )


def clone_scratch_repository() -> str:
    """Clone the repository into a temporary directory of its own.

    Every commit and push this program makes runs with cwd set here, so the
    repository the operator is standing in is never written to. The directory
    is removed in main's finally block.
    """
    directory = tempfile.mkdtemp(prefix=SCRATCH_CLONE_PREFIX)
    completed = run_command(
        ["git", "clone", "--quiet", REPO_CLONE_URL, directory],
        timeout=CLONE_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        shutil.rmtree(directory, ignore_errors=True)
        raise Refusal(
            f"cloning {REPO_CLONE_URL} into a scratch directory failed with "
            f"exit {completed.returncode}.\n"
            f"stderr: {completed.stderr.strip() or '(empty)'}\n"
            "Nothing was created on the repository."
        )
    return directory


def put_protection(branch: str, payload: dict) -> None:
    refuse_if_main(branch)
    completed = gh(
        ["api", "-X", "PUT",
         f"repos/{REPO_SLUG}/branches/{branch}/protection",
         "--input", "-"],
        allow_failure=True,
        input_text=json.dumps(payload),
    )
    if completed.returncode != 0:
        raise Refusal(
            f"applying protection to {branch} failed with exit "
            f"{completed.returncode}.\nstderr: {completed.stderr.strip()}"
        )


def read_review_settings(branch: str) -> dict:
    """Read required_pull_request_reviews for a branch, freshly, from GitHub."""
    settings = api_json(
        f"repos/{REPO_SLUG}/branches/{branch}/protection/"
        "required_pull_request_reviews"
    )
    if settings is None:
        raise Refusal(
            f"could not read the review settings of {branch}, so the partial "
            "PATCH cannot be measured. Nothing is concluded from this run."
        )
    return settings


def patch_reviews_partial(branch: str) -> dict:
    """RISK 1, measured: PATCH naming ONLY dismiss_stale_reviews.

    If the endpoint preserves omitted fields, required_approving_review_count
    survives. If it resets them, this is where that shows -- on a throwaway
    branch, where being wrong costs nothing.

    A failed call refuses rather than returning a flag, because the caller of
    the earlier version never read that flag and reported the failure as a
    measurement. The response body is returned for the record only; the
    reading that counts is the fresh GET the caller makes afterwards.
    """
    refuse_if_main(branch)
    completed = gh(
        ["api", "-X", "PATCH",
         f"repos/{REPO_SLUG}/branches/{branch}/protection/"
         "required_pull_request_reviews",
         "-F", "dismiss_stale_reviews=true"],
        allow_failure=True,
    )
    if completed.returncode != 0:
        raise Refusal(
            f"the partial PATCH on {branch} failed with exit "
            f"{completed.returncode}, so RISK 1 was NOT measured.\n"
            f"stderr: {completed.stderr.strip() or '(empty)'}\n"
            f"No conclusion about {MAIN_BRANCH}'s protection follows from "
            "this run."
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise Refusal(
            f"the partial PATCH on {branch} did not answer JSON: {error}"
        ) from None


def push_probe(branch: str, *, expect: str, clone_directory: str) -> dict:
    """Push an empty commit to `branch` and report what actually happened.

    `expect` is recorded in the result rather than asserted, so the report
    states both what was expected and what occurred. Both git calls run in
    the scratch clone, never in the operator's own repository.
    """
    refuse_if_main(branch)
    committed = run_command(
        ["git", "commit", "--allow-empty", "-q", "-m",
         f"protection experiment probe on {branch}"],
        cwd=clone_directory,
    )
    if committed.returncode != 0:
        raise Refusal(
            f"could not make the probe commit for {branch} in the scratch "
            f"clone (exit {committed.returncode}).\n"
            f"stderr: {committed.stderr.strip() or '(empty)'}"
        )
    completed = run_command(
        ["git", "push", "origin", f"HEAD:refs/heads/{branch}"],
        cwd=clone_directory,
    )
    combined = (completed.stdout + completed.stderr).strip()
    return {
        "branch": branch,
        "expected": expect,
        "accepted": completed.returncode == 0,
        "gh006": "GH006" in combined,
        "detail": combined[-400:] or "(no output)",
    }


def removal_commands(branch: str) -> list[str]:
    """The two calls that remove a leftover by hand, protection first.

    The order is load-bearing: the protection this program copies from main
    sets allow_deletions=false, so the branch cannot be deleted until its
    protection is gone.
    """
    return [
        f"gh api -X DELETE repos/{REPO_SLUG}/branches/{branch}/protection",
        f"gh api -X DELETE repos/{REPO_SLUG}/git/refs/heads/{branch}",
    ]


def cleanup_command(argv: list[str]) -> tuple[int, str]:
    """Run one cleanup call without ever raising.

    Cleanup runs in a finally block. An exception raised there would replace
    the failure that brought the program to cleanup in the first place, so
    every refusal is turned back into an exit code and a message.
    """
    try:
        completed = run_command(argv)
    except Refusal as refusal:
        return 1, str(refusal)
    return completed.returncode, (
        completed.stderr.strip() or completed.stdout.strip() or "(no output)"
    )


def cleanup(branches: list[str], protected: set[str]) -> tuple[list[str], list[str]]:
    """Remove every branch this run created. Returns (notes, unfinished).

    Deletion goes through the API rather than `git push --delete`, so cleanup
    does not depend on a scratch clone that may not exist by the time it runs.
    Protection is deleted only for the branches this run actually protected,
    so a delete is never issued against nothing (PR #228 review item 7b).
    """
    notes: list[str] = []
    unfinished: list[str] = []
    for branch in branches:
        try:
            refuse_if_main(branch)
        except Refusal as refusal:
            notes.append(f"{branch}: refused, {refusal}")
            continue
        if branch in protected:
            code, detail = cleanup_command(
                ["gh", "api", "-X", "DELETE",
                 f"repos/{REPO_SLUG}/branches/{branch}/protection"]
            )
            if code == 0:
                notes.append(f"{branch}: protection removed")
            elif "404" in detail or "Not Found" in detail:
                notes.append(f"{branch}: no protection to remove (404)")
            else:
                notes.append(
                    f"{branch}: protection could NOT be removed "
                    f"(exit {code}): {detail}"
                )
                unfinished.append(branch)
        code, detail = cleanup_command(
            ["gh", "api", "-X", "DELETE",
             f"repos/{REPO_SLUG}/git/refs/heads/{branch}"]
        )
        if code == 0:
            notes.append(f"{branch}: branch deleted")
        else:
            notes.append(
                f"{branch}: branch could NOT be deleted (exit {code}): {detail}"
            )
            if branch not in unfinished:
                unfinished.append(branch)
    return notes, unfinished


def report_unfinished_cleanup(unfinished: list[str]) -> None:
    """Say plainly that the repository is left modified, and how to fix it."""
    print(
        "\nTHE LIVE REPOSITORY HAS BEEN LEFT MODIFIED. Cleanup could not "
        f"finish for: {', '.join(unfinished)}.\n"
        "Each leftover branch still exists on GitHub, and the protection "
        "copied onto it forbids deleting it, so it must be removed by hand, "
        "protection first:",
        file=sys.stderr,
    )
    for branch in unfinished:
        for command in removal_commands(branch):
            print(f"  {command}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="print the plan and main's live settings; write nothing")
    mode.add_argument("--run", action="store_true",
                      help="create the throwaway branch, measure, then clean up")
    arguments = parser.parse_args()

    try:
        login = check_experiment_credential()
        main_protection = read_main_protection()
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2

    print(f"credential: {login}, admin on {REPO_SLUG}, and main's protection "
          "reads, so the token carries the scope the role needs.")
    if login.casefold() != RULED_EXPERIMENT_ACCOUNT.casefold():
        print(f"note: the ruled account for this experiment is "
              f"{RULED_EXPERIMENT_ACCOUNT}; this run is {login}.")

    reviews_now = main_protection.get("required_pull_request_reviews") or {}
    print("main's live review settings (read-only):")
    print(json.dumps(reviews_now, indent=2))

    if arguments.dry_run:
        print("\nplan, in order:")
        print("  1. check the credential can write protection (done above)")
        print("  2. clone the repository into a temporary directory of its "
              "own, so nothing")
        print("     is committed into the repository you are standing in")
        print(f"  3. create {EXPERIMENT_BRANCH} from the clone's tip of main")
        print("  4. apply main-shaped protection to it, dismiss_stale_reviews=false")
        print("  5. read required_pull_request_reviews, PATCH naming ONLY")
        print("     dismiss_stale_reviews=true, then read it back with a FRESH GET")
        print("     -> if required_approving_review_count survives, the partial")
        print("        PATCH is safe; if it changes, the full form is required;")
        print("        if the PATCH did not take effect, nothing was measured")
        print(f"  6. push from the clone to {FEATURE_BRANCH}, unprotected "
              "-> expect accepted")
        print(f"  7. push from the clone to {EXPERIMENT_BRANCH} -> expect refused")
        print("  8. delete both branches and their protection, and remove the clone")
        print("\nnothing was written.")
        return 0

    try:
        existing = api_json(
            f"repos/{REPO_SLUG}/branches/{EXPERIMENT_BRANCH}", allow_failure=True
        )
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2
    if existing is not None:
        print(
            f"refused: {EXPERIMENT_BRANCH} already exists — it may be a leftover "
            f"from an interrupted run. Inspect and delete it, then re-run.",
            file=sys.stderr,
        )
        return 2

    report: dict = {"risk_1_patch_semantics": None, "risk_2_pushes": []}
    created: list[str] = []
    protected: set[str] = set()
    clone_directory: str | None = None
    exit_code = 0
    try:
        # Everything fallible but harmless happens before the first write:
        # if the clone fails, `created` is still empty and GitHub is untouched.
        clone_directory = clone_scratch_repository()
        head = run_command(["git", "rev-parse", "HEAD"], cwd=clone_directory)
        if head.returncode != 0:
            raise Refusal(
                "could not read the scratch clone's tip of main "
                f"(exit {head.returncode}). Nothing was created."
            )
        gh(["api", "-X", "POST", f"repos/{REPO_SLUG}/git/refs",
            "-f", f"ref=refs/heads/{EXPERIMENT_BRANCH}",
            "-f", f"sha={head.stdout.strip()}"])
        created.append(EXPERIMENT_BRANCH)

        # Recorded as protected BEFORE the call, not after: a PUT that fails
        # after taking effect would otherwise leave an undeletable branch that
        # cleanup never tries to unprotect. A 404 from a protection delete
        # against a branch that was never protected is reported as such.
        protected.add(EXPERIMENT_BRANCH)
        put_protection(
            EXPERIMENT_BRANCH,
            protection_payload_from(main_protection, dismiss_stale=False),
        )
        before = read_review_settings(EXPERIMENT_BRANCH)
        patch_response = patch_reviews_partial(EXPERIMENT_BRANCH)
        # The read-back the plan promises, and a fresh one: the PATCH's own
        # response body may echo the request rather than report stored state.
        after = read_review_settings(EXPERIMENT_BRANCH)
        outcome, sentence = judge_partial_patch_result(before, after)
        report["risk_1_patch_semantics"] = {
            "before": before,
            "patch_response": patch_response,
            "after_fresh_read": after,
            "count_before": before.get("required_approving_review_count"),
            "count_after": after.get("required_approving_review_count"),
            "dismiss_after": after.get("dismiss_stale_reviews"),
            "outcome": outcome,
            "sentence": sentence,
        }
        if outcome == PATCH_SEMANTICS_NOT_MEASURED:
            raise Refusal(sentence)

        feature = push_probe(
            FEATURE_BRANCH,
            expect="accepted (unprotected branch)",
            clone_directory=clone_directory,
        )
        report["risk_2_pushes"].append(feature)
        # Only a branch that was actually created is handed to cleanup: a
        # rejected push leaves nothing on GitHub, and deleting nothing prints
        # failures that read like cleanup failures.
        if feature["accepted"]:
            created.append(FEATURE_BRANCH)
        report["risk_2_pushes"].append(push_probe(
            EXPERIMENT_BRANCH,
            expect="refused (protected, reviews required)",
            clone_directory=clone_directory,
        ))
    except KeyboardInterrupt:
        print("\ninterrupted; cleaning up before exiting.", file=sys.stderr)
        exit_code = 1
    except Refusal as failure:
        print(f"\nmeasurement stopped: {failure}", file=sys.stderr)
        exit_code = 1
    finally:
        # No return in this block: returning here would swallow whatever
        # exception brought the program to cleanup.
        notes, unfinished = cleanup(created, protected)
        print("\ncleanup:", *(notes or ["nothing to clean up"]), sep="\n  ")
        if clone_directory:
            shutil.rmtree(clone_directory, ignore_errors=True)
            print(f"  scratch clone removed: {clone_directory}")
        if unfinished:
            report_unfinished_cleanup(unfinished)

    print("\nreport:")
    print(json.dumps(report, indent=2))
    if exit_code != 0:
        return exit_code
    print(f"\n{report['risk_1_patch_semantics']['sentence']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
