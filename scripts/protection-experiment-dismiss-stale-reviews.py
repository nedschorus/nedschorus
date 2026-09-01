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

SAFETY. Every write targets a throwaway branch this script creates and
deletes. It refuses to operate on main by name, and it refuses if the
branch it is about to create already exists. Protection settings for the
throwaway branch are copied from main's live settings so the experiment
runs against the real shape rather than an invented one. main's own
protection is read, never written -- there is no code path in this file
that PATCHes, PUTs, or DELETEs anything under main's protection, and the
refuse_if_main guard is applied to every mutating call.

USAGE
  python3 scripts/protection-experiment-dismiss-stale-reviews.py --dry-run
  python3 scripts/protection-experiment-dismiss-stale-reviews.py --run

Exit codes: 0 every measurement completed (findings are in the report,
which is printed and may still say the PATCH is unsafe); 1 a measurement
could not be completed and the report says which; 2 bad invocation or a
safety refusal.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

REPO_SLUG = "nedschorus/nedschorus"
MAIN_BRANCH = "main"
# Named, not generated: a fixed name is greppable, and a leftover from a
# crashed run is recognizable rather than one of a family of random names.
EXPERIMENT_BRANCH = "protection-experiment-dismiss-stale-reviews"
FEATURE_BRANCH = "protection-experiment-dismiss-stale-reviews-feature"


class Refusal(Exception):
    """A safety refusal or an impossible measurement. Carries its own fix."""


def refuse_if_main(branch: str) -> None:
    """Every mutating call passes through here first."""
    if branch.strip().casefold() in {MAIN_BRANCH, "refs/heads/" + MAIN_BRANCH}:
        raise Refusal(
            f"this script never writes to {MAIN_BRANCH}; it was asked to "
            f"write to {branch!r}. Nothing was changed."
        )


def gh(args: list[str], *, allow_failure: bool = False) -> subprocess.CompletedProcess:
    """Run gh. stderr is captured and REPORTED, never discarded.

    A silenced failure that is later trusted is the defect class recorded
    at nedschorus PR #111, so the caller always sees what failed.
    """
    completed = subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=False
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
        },
        "restrictions": None,
        "allow_force_pushes": bool(
            (main_protection.get("allow_force_pushes") or {}).get("enabled")
        ),
        "allow_deletions": bool(
            (main_protection.get("allow_deletions") or {}).get("enabled")
        ),
    }


def put_protection(branch: str, payload: dict) -> None:
    refuse_if_main(branch)
    completed = subprocess.run(
        [
            "gh", "api", "-X", "PUT",
            f"repos/{REPO_SLUG}/branches/{branch}/protection",
            "--input", "-",
        ],
        input=json.dumps(payload), capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise Refusal(
            f"applying protection to {branch} failed with exit "
            f"{completed.returncode}.\nstderr: {completed.stderr.strip()}"
        )


def patch_reviews_partial(branch: str) -> dict | None:
    """RISK 1, measured: PATCH naming ONLY dismiss_stale_reviews.

    If the endpoint preserves omitted fields, required_approving_review_count
    survives. If it resets them, this is where that shows -- on a throwaway
    branch, where being wrong costs nothing.
    """
    refuse_if_main(branch)
    completed = subprocess.run(
        [
            "gh", "api", "-X", "PATCH",
            f"repos/{REPO_SLUG}/branches/{branch}/protection/"
            "required_pull_request_reviews",
            "-F", "dismiss_stale_reviews=true",
        ],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        return {
            "call_failed": True,
            "exit": completed.returncode,
            "stderr": completed.stderr.strip(),
        }
    return json.loads(completed.stdout)


def push_probe(branch: str, *, expect: str) -> dict:
    """Push an empty commit to `branch` and report what actually happened.

    `expect` is recorded in the result rather than asserted, so the report
    states both what was expected and what occurred.
    """
    refuse_if_main(branch)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-q", "-m",
         f"protection experiment probe on {branch}"],
        check=True,
    )
    completed = subprocess.run(
        ["git", "push", "origin", f"HEAD:refs/heads/{branch}"],
        capture_output=True, text=True, check=False,
    )
    combined = (completed.stdout + completed.stderr).strip()
    return {
        "branch": branch,
        "expected": expect,
        "accepted": completed.returncode == 0,
        "gh006": "GH006" in combined,
        "detail": combined[-400:] or "(no output)",
    }


def cleanup(branches: list[str]) -> list[str]:
    notes = []
    for branch in branches:
        refuse_if_main(branch)
        removed = gh(
            ["api", "-X", "DELETE",
             f"repos/{REPO_SLUG}/branches/{branch}/protection"],
            allow_failure=True,
        )
        notes.append(
            f"{branch}: protection delete exit {removed.returncode}"
            + ("" if removed.returncode == 0 else f" ({removed.stderr.strip()})")
        )
        deleted = subprocess.run(
            ["git", "push", "origin", "--delete", branch],
            capture_output=True, text=True, check=False,
        )
        notes.append(f"{branch}: branch delete exit {deleted.returncode}")
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="print the plan and main's live settings; write nothing")
    mode.add_argument("--run", action="store_true",
                      help="create the throwaway branch, measure, then clean up")
    arguments = parser.parse_args()

    try:
        main_protection = read_main_protection()
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2

    reviews_now = main_protection.get("required_pull_request_reviews") or {}
    print("main's live review settings (read-only):")
    print(json.dumps(reviews_now, indent=2))

    if arguments.dry_run:
        print("\nplan, in order:")
        print(f"  1. create {EXPERIMENT_BRANCH} from main's tip")
        print("  2. apply main-shaped protection to it, dismiss_stale_reviews=false")
        print("  3. PATCH naming ONLY dismiss_stale_reviews=true, then read back")
        print("     -> if required_approving_review_count survives, the partial")
        print("        PATCH is safe; if it changes, the full form is required")
        print(f"  4. push to {FEATURE_BRANCH}, unprotected -> expect accepted")
        print(f"  5. push directly to {EXPERIMENT_BRANCH} -> expect refused")
        print("  6. delete both branches and their protection")
        print("\nnothing was written.")
        return 0

    existing = api_json(
        f"repos/{REPO_SLUG}/branches/{EXPERIMENT_BRANCH}", allow_failure=True
    )
    if existing is not None:
        print(
            f"refused: {EXPERIMENT_BRANCH} already exists — it may be a leftover "
            f"from an interrupted run. Inspect and delete it, then re-run.",
            file=sys.stderr,
        )
        return 2

    report: dict = {"risk_1_patch_semantics": None, "risk_2_pushes": []}
    created: list[str] = []
    try:
        head = subprocess.run(
            ["git", "rev-parse", f"origin/{MAIN_BRANCH}"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        gh(["api", "-X", "POST", f"repos/{REPO_SLUG}/git/refs",
            "-f", f"ref=refs/heads/{EXPERIMENT_BRANCH}", "-f", f"sha={head}"])
        created.append(EXPERIMENT_BRANCH)

        put_protection(
            EXPERIMENT_BRANCH,
            protection_payload_from(main_protection, dismiss_stale=False),
        )
        before = api_json(
            f"repos/{REPO_SLUG}/branches/{EXPERIMENT_BRANCH}/protection/"
            "required_pull_request_reviews"
        )
        after = patch_reviews_partial(EXPERIMENT_BRANCH)
        report["risk_1_patch_semantics"] = {
            "before": before,
            "after": after,
            "count_before": (before or {}).get("required_approving_review_count"),
            "count_after": (after or {}).get("required_approving_review_count"),
            "dismiss_after": (after or {}).get("dismiss_stale_reviews"),
        }

        report["risk_2_pushes"].append(
            push_probe(FEATURE_BRANCH, expect="accepted (unprotected branch)")
        )
        created.append(FEATURE_BRANCH)
        report["risk_2_pushes"].append(
            push_probe(EXPERIMENT_BRANCH, expect="refused (protected, reviews required)")
        )
    except (Refusal, subprocess.CalledProcessError) as failure:
        print(f"\nmeasurement stopped: {failure}", file=sys.stderr)
        print("cleanup notes:", *cleanup(created), sep="\n  ", file=sys.stderr)
        return 1

    print("\ncleanup:", *cleanup(created), sep="\n  ")
    print("\nreport:")
    print(json.dumps(report, indent=2))

    semantics = report["risk_1_patch_semantics"]
    if semantics["count_before"] != semantics["count_after"]:
        print(
            "\nFINDING: the partial PATCH CHANGED required_approving_review_count "
            f"({semantics['count_before']} -> {semantics['count_after']}). "
            "Any change to main must send every field explicitly."
        )
    else:
        print(
            "\nFINDING: the partial PATCH preserved "
            f"required_approving_review_count ({semantics['count_after']}). "
            "Sending every field explicitly remains the safer form."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
