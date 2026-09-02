#!/usr/bin/env python3
"""Tests for protection-experiment-dismiss-stale-reviews.py.

Run: python3 scripts/protection-experiment-dismiss-stale-reviews-test.py

Everything here is offline and needs no credential. The program under test
writes branch protection on the live repository, so nothing in this file
invokes it: every case calls one of its pure functions directly.

The protection fixture is a real capture. It is
`gh api repos/nedschorus/nedschorus/branches/main/protection` read on
2026-09-02, trimmed to the fields the payload builder reads, in the same
spirit as the git-gatekeeper's --protection-file seam: a captured reply
replaces the fetch, and nothing else is replaced.

Coverage:
  - protection_payload_from: every field copied from a real capture,
    including require_last_push_approval, which an earlier version dropped
  - refuse_if_main: the guard that carries the whole restraint, since GitHub
    cannot scope branch-protection permission to one branch
  - judge_partial_patch_result: THE MISSING TEST. The defect that made
    PR #228 CHANGES_REQUESTED was a failed call reported as a measurement,
    and a payload-shape test would never have found it — the payload was
    correct. This is the test that fails on the old code, because the old
    code compared a count against nothing and called the difference a
    finding.
  - removal_commands: protection before branch, the order cleanup depends on

Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name(
    "protection-experiment-dismiss-stale-reviews.py")

_spec = importlib.util.spec_from_file_location(
    "protection_experiment_dismiss_stale_reviews", SCRIPT_PATH)
experiment = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(experiment)

failures = []
cases_run = 0


def check(case_name, condition, detail=""):
    global cases_run
    cases_run += 1
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


# main's live protection on 2026-09-02, trimmed to the read fields.
LIVE_MAIN_PROTECTION = {
    "restrictions": {
        "users": [{"login": "ned-review-merge"}, {"login": "nedlern"}],
        "teams": [],
        "apps": [],
    },
    "required_pull_request_reviews": {
        "dismiss_stale_reviews": False,
        "require_code_owner_reviews": False,
        "require_last_push_approval": False,
        "required_approving_review_count": 1,
    },
    "enforce_admins": {"enabled": True},
    "required_linear_history": {"enabled": False},
    "allow_force_pushes": {"enabled": False},
    "allow_deletions": {"enabled": False},
}


# --- protection_payload_from: the payload sent to the throwaway branch -----

payload = experiment.protection_payload_from(
    LIVE_MAIN_PROTECTION, dismiss_stale=False)
reviews = payload["required_pull_request_reviews"]

check("the payload copies main's required_approving_review_count",
      reviews["required_approving_review_count"] == 1, payload)
check("the payload copies require_code_owner_reviews",
      reviews["require_code_owner_reviews"] is False, payload)
check("dismiss_stale_reviews takes the argument, not main's value",
      reviews["dismiss_stale_reviews"] is False, payload)
check("dismiss_stale=True reaches the payload",
      experiment.protection_payload_from(
          LIVE_MAIN_PROTECTION, dismiss_stale=True
      )["required_pull_request_reviews"]["dismiss_stale_reviews"] is True)
check("enforce_admins is unwrapped from its {enabled: bool} envelope",
      payload["enforce_admins"] is True, payload)
check("allow_force_pushes is unwrapped and stays False",
      payload["allow_force_pushes"] is False, payload)
check("allow_deletions is unwrapped and stays False — cleanup deletes "
      "protection first because of it",
      payload["allow_deletions"] is False, payload)
check("restrictions are dropped, so the experiment's own pushes are not "
      "refused by a push allow-list",
      payload["restrictions"] is None, payload)
check("required_status_checks is sent as null",
      payload["required_status_checks"] is None, payload)

# The field an earlier version dropped. main has it off today, matching the
# default that was sent, so only a source that has it ON shows the defect.
check("require_last_push_approval is copied when main has it off",
      reviews["require_last_push_approval"] is False, payload)
last_push_on = {
    **LIVE_MAIN_PROTECTION,
    "required_pull_request_reviews": {
        **LIVE_MAIN_PROTECTION["required_pull_request_reviews"],
        "require_last_push_approval": True,
    },
}
check("require_last_push_approval is copied when main has it ON — the "
      "throwaway branch must not silently differ in the field closest to "
      "the one under test",
      experiment.protection_payload_from(
          last_push_on, dismiss_stale=False
      )["required_pull_request_reviews"]["require_last_push_approval"] is True)

# A protection reply that omits the review block entirely: the builder must
# fall back to defaults rather than raise, because the reply is GitHub's.
bare = experiment.protection_payload_from({}, dismiss_stale=True)
check("a protection reply with no review block yields defaults, not a crash",
      bare["required_pull_request_reviews"] == {
          "required_approving_review_count": 1,
          "dismiss_stale_reviews": True,
          "require_code_owner_reviews": False,
          "require_last_push_approval": False,
      }, bare)
check("a protection reply with no enforce_admins block yields False",
      bare["enforce_admins"] is False, bare)


# --- refuse_if_main: the guard that holds the whole restraint --------------

def refuses(branch):
    try:
        experiment.refuse_if_main(branch)
    except experiment.Refusal:
        return True
    return False


check("refuse_if_main refuses 'main'", refuses("main"))
check("refuse_if_main refuses 'MAIN' — the comparison casefolds",
      refuses("MAIN"))
check("refuse_if_main refuses 'refs/heads/main' — the fully qualified form",
      refuses("refs/heads/main"))
check("refuse_if_main refuses ' main ' — surrounding space is stripped",
      refuses(" main "))
try:
    experiment.refuse_if_main("MAIN")
    refusal_text = ""
except experiment.Refusal as refusal:
    refusal_text = str(refusal)
check("the refusal names the branch it was asked to write to and says "
      "nothing was changed",
      "'MAIN'" in refusal_text and "Nothing was changed" in refusal_text,
      refusal_text)

check("refuse_if_main allows the experiment branch",
      not refuses(experiment.EXPERIMENT_BRANCH))
check("refuse_if_main allows the feature branch",
      not refuses(experiment.FEATURE_BRANCH))
check("refuse_if_main allows a branch that merely contains 'main'",
      not refuses("maintenance-branch"))


# --- judge_partial_patch_result: the test PR #228's defect needed ----------
# The old code did `count_before != count_after` and nothing else. Cases 1
# and 2 below are the two shapes it got wrong; both passed through it as a
# printed finding and exit 0.

NOT_MEASURED = experiment.PATCH_SEMANTICS_NOT_MEASURED
CLOBBERED = experiment.PATCH_SEMANTICS_CLOBBERED
PRESERVED = experiment.PATCH_SEMANTICS_PRESERVED

before_reading = {"required_approving_review_count": 1,
                  "dismiss_stale_reviews": False,
                  "require_code_owner_reviews": False}

outcome, sentence = experiment.judge_partial_patch_result(before_reading, None)
check("a PATCH whose reading is missing is NOT a measurement — the exact "
      "PR #228 defect, where 1 was compared against nothing",
      outcome == NOT_MEASURED, (outcome, sentence))
check("and that sentence does not claim the count CHANGED",
      "CHANGED" not in sentence, sentence)
check("and it says so as an ERROR, not a FINDING",
      sentence.startswith("ERROR:"), sentence)

outcome, sentence = experiment.judge_partial_patch_result(None, {
    "required_approving_review_count": 1, "dismiss_stale_reviews": True})
check("a missing 'before' reading is NOT a measurement either",
      outcome == NOT_MEASURED, (outcome, sentence))

# The mirror image: the call reports success without taking effect.
outcome, sentence = experiment.judge_partial_patch_result(before_reading, {
    "required_approving_review_count": 1, "dismiss_stale_reviews": False})
check("a PATCH that reports success but reads back unchanged is NOT a "
      "measurement — the mirror image on the success path",
      outcome == NOT_MEASURED, (outcome, sentence))
check("and it names what the setting actually read back as",
      "dismiss_stale_reviews=False" in sentence, sentence)

outcome, _ = experiment.judge_partial_patch_result(before_reading, {
    "required_approving_review_count": 1})
check("a read-back with no dismiss_stale_reviews at all is NOT a measurement",
      outcome == NOT_MEASURED, outcome)

outcome, _ = experiment.judge_partial_patch_result(before_reading, {
    "dismiss_stale_reviews": True})
check("a read-back with no review count is NOT a measurement",
      outcome == NOT_MEASURED, outcome)

outcome, sentence = experiment.judge_partial_patch_result(before_reading, {
    "required_approving_review_count": 0, "dismiss_stale_reviews": True})
check("a PATCH that took effect and dropped the count is the clobbered "
      "finding",
      outcome == CLOBBERED, (outcome, sentence))
check("the clobbered sentence names both counts and is a FINDING",
      "(1 -> 0)" in sentence and sentence.startswith("FINDING:"), sentence)

outcome, sentence = experiment.judge_partial_patch_result(before_reading, {
    "required_approving_review_count": 1, "dismiss_stale_reviews": True})
check("a PATCH that took effect and preserved the count is the safe finding",
      outcome == PRESERVED, (outcome, sentence))
check("the preserved sentence is a FINDING and names the surviving count",
      sentence.startswith("FINDING:") and "(1)" in sentence, sentence)

check("the three outcomes are distinct",
      len({NOT_MEASURED, CLOBBERED, PRESERVED}) == 3)


# --- removal_commands: the two commands cleanup prints when it is stuck ----

commands = experiment.removal_commands(experiment.EXPERIMENT_BRANCH)
check("removal_commands gives exactly two commands", len(commands) == 2,
      commands)
check("protection is removed first — the copied protection sets "
      "allow_deletions=false, so the reverse order deadlocks",
      "/protection" in commands[0] and "git/refs/heads/" in commands[1],
      commands)
check("both commands name the branch",
      all(experiment.EXPERIMENT_BRANCH in command for command in commands),
      commands)


print()
print(f"{cases_run} cases run")
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
