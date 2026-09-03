#!/usr/bin/env python3
"""Tests for protection-experiment-dismiss-stale-reviews.py.

Run: python3 scripts/protection-experiment-dismiss-stale-reviews-test.py

Everything here is offline and needs no credential. The program under test
writes branch protection on the live repository, so nothing in this file
invokes it: every case calls one of its pure functions directly, or drives
one of its command-running functions with run_command substituted by a fake
that returns canned CompletedProcess results -- the same seam the reviewer
used to demonstrate PR #228's second-round defect.

The protection fixture is a real capture. It is
`gh api repos/nedschorus/nedschorus/branches/main/protection` read on
2026-09-02, trimmed to the fields the payload builder reads, in the same
spirit as the git-gatekeeper's --protection-file seam: a captured reply
replaces the fetch, and nothing else is replaced. The header fixture is
likewise a real capture of `gh api -i user` on this Mac, 2026-09-02, with
the scope list trimmed and the body reduced to the login.

Coverage:
  - protection_payload_from: every field copied from a real capture,
    including require_last_push_approval, which an earlier version dropped
  - refuse_if_main: the guard that carries the whole restraint, since GitHub
    cannot scope branch-protection permission to one branch
  - judge_partial_patch_result: the test PR #228's first blocking defect
    needed -- a failed call reported as a measurement. A payload-shape test
    would never have found it; this is the test that fails on the old code.
  - judge_push_probe_result and judge_run_report: the second round's
    defect. push_probe recorded `expected` beside `accepted` and nothing
    compared them, so a run whose probes contradicted their expectations --
    or never reached branch protection -- exited 0. The reviewer's offline
    demonstration (run_command substituted so `git push` fails on `could not
    read Username`) is reproduced here and must exit 1.
  - leftover_experiment_branches: both throwaway branches are guarded, not
    only the protected one
  - the credential check: what a read proves (the classic token's scopes,
    when GitHub reports them) and what it cannot (a fine-grained token's
    permissions), with the startup text never claiming write capability;
    and protection_write_refusal, which classifies the first PUT's 403 as
    the credential's failure
  - cleanup: a branch whose ref delete succeeds is not a leftover, whatever
    the protection delete said -- on the credential path both deletes hit
    the same missing permission, and an earlier version announced a leftover
    for a branch that was gone
  - removal_commands: protection before branch, the order cleanup depends on

Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import subprocess
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


def completed(argv, returncode, stdout="", stderr=""):
    return subprocess.CompletedProcess(argv, returncode, stdout, stderr)


def with_run_command(fake, action):
    """Run `action` with the program's run_command replaced by `fake`.

    The real function is restored in a finally block so a failing case
    cannot poison the cases after it.
    """
    real = experiment.run_command
    experiment.run_command = fake
    try:
        return action()
    finally:
        experiment.run_command = real


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


# --- judge_push_probe_result: RISK 2 under the same rule as RISK 1 ---------
# At 2de34bc push_probe returned `expected` and `accepted` side by side and
# main() compared them against nothing. Every case below is a shape that
# exited 0 there.

AS_EXPECTED = experiment.PUSH_PROBE_AS_EXPECTED
CONTRADICTED = experiment.PUSH_PROBE_CONTRADICTED
PROBE_NOT_MEASURED = experiment.PUSH_PROBE_NOT_MEASURED
EXPERIMENT_BRANCH = experiment.EXPERIMENT_BRANCH
FEATURE_BRANCH = experiment.FEATURE_BRANCH

GH006_REFUSAL = (
    f"remote: error: GH006: Protected branch update failed for "
    f"refs/heads/{EXPERIMENT_BRANCH}.\n"
    "remote: error: Changes must be made through a pull request.\n"
    f" ! [remote rejected] HEAD -> {EXPERIMENT_BRANCH} "
    "(protected branch hook declined)"
)
NON_FAST_FORWARD = (
    f" ! [rejected]        HEAD -> {FEATURE_BRANCH} (fetch first)\n"
    "error: failed to push some refs to "
    "'https://github.com/nedschorus/nedschorus.git'"
)


def probe_result(branch, *, expect_accepted, accepted, gh006, detail):
    return {
        "branch": branch,
        "expected": "accepted (unprotected branch)" if expect_accepted
        else "refused (protected, reviews required)",
        "expect_accepted": expect_accepted,
        "accepted": accepted,
        "gh006": gh006,
        "detail": detail,
    }


outcome, sentence = experiment.judge_push_probe_result(probe_result(
    FEATURE_BRANCH, expect_accepted=True, accepted=True, gh006=False,
    detail=f" * [new branch]      HEAD -> {FEATURE_BRANCH}"))
check("an accepted push where acceptance was expected is as expected, and "
      "a FINDING",
      outcome == AS_EXPECTED and sentence.startswith("FINDING:"),
      (outcome, sentence))

outcome, sentence = experiment.judge_push_probe_result(probe_result(
    EXPERIMENT_BRANCH, expect_accepted=False, accepted=False, gh006=True,
    detail=GH006_REFUSAL))
check("a GH006 refusal where refusal was expected is as expected, and a "
      "FINDING",
      outcome == AS_EXPECTED and sentence.startswith("FINDING:"),
      (outcome, sentence))

outcome, sentence = experiment.judge_push_probe_result(probe_result(
    EXPERIMENT_BRANCH, expect_accepted=False, accepted=True, gh006=False,
    detail=f" * [new branch]      HEAD -> {EXPERIMENT_BRANCH}"))
check("an ACCEPTED push to the protected branch contradicts the expectation "
      "— protection did not refuse it, and the old code exited 0",
      outcome == CONTRADICTED, (outcome, sentence))
check("and the sentence is a DISCREPANCY that names the branch",
      sentence.startswith("DISCREPANCY:") and EXPERIMENT_BRANCH in sentence,
      sentence)

outcome, sentence = experiment.judge_push_probe_result(probe_result(
    FEATURE_BRANCH, expect_accepted=True, accepted=False, gh006=True,
    detail=GH006_REFUSAL))
check("a GH006 refusal of the UNPROTECTED branch contradicts the expectation "
      "— the user's verbatim question answered the wrong way",
      outcome == CONTRADICTED and sentence.startswith("DISCREPANCY:"),
      (outcome, sentence))
check("and that sentence says ordinary pushes ARE affected",
      "ARE affected" in sentence, sentence)

outcome, sentence = experiment.judge_push_probe_result(probe_result(
    FEATURE_BRANCH, expect_accepted=True, accepted=False, gh006=False,
    detail=NON_FAST_FORWARD))
check("a refusal WITHOUT GH006 is not a measurement — the non-fast-forward "
      "a leftover feature branch produces never reached protection",
      outcome == PROBE_NOT_MEASURED and sentence.startswith("ERROR:"),
      (outcome, sentence))
check("and the sentence quotes what git said and names the leftover cause",
      "fetch first" in sentence and "leftover" in sentence, sentence)

outcome, sentence = experiment.judge_push_probe_result(probe_result(
    EXPERIMENT_BRANCH, expect_accepted=False, accepted=False, gh006=False,
    detail="fatal: could not read Username for 'https://github.com'"))
check("a refusal without GH006 on the PROTECTED branch is not a measurement "
      "either, even though 'refused' matches the expectation",
      outcome == PROBE_NOT_MEASURED, (outcome, sentence))

outcome, sentence = experiment.judge_push_probe_result(
    {"branch": FEATURE_BRANCH, "expected": "accepted"})
check("a probe result missing its booleans is not a measurement",
      outcome == PROBE_NOT_MEASURED and sentence.startswith("ERROR:"),
      (outcome, sentence))

check("the three push-probe outcomes are distinct",
      len({AS_EXPECTED, CONTRADICTED, PROBE_NOT_MEASURED}) == 3)


# --- the reviewer's demonstration, reproduced -----------------------------
# mac-claude substituted run_command so `git push` returned 128 with
# `fatal: could not read Username`: both probes came back accepted=False,
# gh006=False, neither raised, and exit_code stayed 0. The same substitution,
# through the same seam, must now come out as two errors and exit 1.

USERNAME_FAILURE = ("fatal: could not read Username for "
                    "'https://github.com': terminal prompts disabled")
real_run_command = experiment.run_command


def push_fails_on_username(argv, **_):
    if argv[:2] == ["git", "commit"]:
        return completed(argv, 0)
    if argv[:2] == ["git", "push"]:
        return completed(argv, 128, stderr=USERNAME_FAILURE)
    raise AssertionError(f"unexpected command in the probe: {argv}")


def run_both_probes():
    return [
        experiment.push_probe(
            branch, expect_accepted=expect_accepted, reason=reason,
            clone_directory="/nonexistent/scratch-clone",
        )
        for branch, expect_accepted, reason in experiment.PUSH_PROBES
    ]


demonstration = with_run_command(push_fails_on_username, run_both_probes)
check("run_command is restored after the substitution",
      experiment.run_command is real_run_command)
check("the demonstration reproduces the reviewer's record: both probes "
      "accepted=False, gh006=False, neither raised",
      len(demonstration) == 2 and all(
          probe["accepted"] is False and probe["gh006"] is False
          for probe in demonstration),
      demonstration)
demonstration_judged = [
    dict(probe, outcome=outcome, sentence=sentence)
    for probe in demonstration
    for outcome, sentence in [experiment.judge_push_probe_result(probe)]
]
check("both probes are judged not measured",
      all(probe["outcome"] == PROBE_NOT_MEASURED
          for probe in demonstration_judged),
      [probe["outcome"] for probe in demonstration_judged])
check("and each sentence carries git's actual complaint",
      all(USERNAME_FAILURE in probe["sentence"]
          for probe in demonstration_judged),
      [probe["sentence"] for probe in demonstration_judged])

preserved_risk_1 = {
    "outcome": PRESERVED,
    "sentence": "FINDING: the partial PATCH preserved "
                "required_approving_review_count (1).",
}
exit_code, summary = experiment.judge_run_report({
    "risk_1_patch_semantics": preserved_risk_1,
    "risk_2_pushes": demonstration_judged,
})
check("the run exits 1 on the reviewer's demonstration — at 2de34bc it "
      "exited 0 with a summary that spoke only about RISK 1",
      exit_code == 1, (exit_code, summary))
check("and the summary speaks about RISK 2, as an ERROR, for both probes",
      sum(line.startswith("RISK 2: ERROR:") for line in summary) == 2,
      summary)

# The positive control: the same seam, with protection behaving. Without
# this, "exit 1 on failure" could be satisfied by a judge that always fails.


def protection_behaves(argv, **_):
    if argv[:2] == ["git", "commit"]:
        return completed(argv, 0)
    if argv[:2] == ["git", "push"]:
        if argv[-1].endswith(FEATURE_BRANCH):
            return completed(
                argv, 0, stderr=f" * [new branch]      HEAD -> {FEATURE_BRANCH}")
        return completed(argv, 1, stderr=GH006_REFUSAL)
    raise AssertionError(f"unexpected command in the probe: {argv}")


control = with_run_command(protection_behaves, run_both_probes)
control_judged = [
    dict(probe, outcome=outcome, sentence=sentence)
    for probe in control
    for outcome, sentence in [experiment.judge_push_probe_result(probe)]
]
check("positive control: feature push accepted, protected push refused with "
      "GH006 — both as expected",
      [probe["outcome"] for probe in control_judged] == [AS_EXPECTED] * 2,
      control_judged)
exit_code, summary = experiment.judge_run_report({
    "risk_1_patch_semantics": preserved_risk_1,
    "risk_2_pushes": control_judged,
})
check("positive control: the run exits 0 and the summary has a FINDING line "
      "for each probe",
      exit_code == 0
      and sum(line.startswith("RISK 2: FINDING:") for line in summary) == 2,
      (exit_code, summary))
check("the probe records the prose expectation the report shows, built from "
      "the boolean the judge reads",
      control[0]["expected"] == "accepted (unprotected branch)"
      and control[1]["expected"] == "refused (protected, reviews required)",
      [probe["expected"] for probe in control])


# --- judge_run_report: the exit code from the report alone ----------------

as_expected_probes = [
    dict(probe_result(FEATURE_BRANCH, expect_accepted=True, accepted=True,
                      gh006=False, detail=""),
         outcome=AS_EXPECTED, sentence="FINDING: accepted"),
    dict(probe_result(EXPERIMENT_BRANCH, expect_accepted=False,
                      accepted=False, gh006=True, detail=GH006_REFUSAL),
         outcome=AS_EXPECTED, sentence="FINDING: refused"),
]

exit_code, summary = experiment.judge_run_report(
    {"risk_1_patch_semantics": None, "risk_2_pushes": []})
check("an empty report — the run stopped before measuring — exits 1",
      exit_code == 1, (exit_code, summary))
check("and its summary says RISK 1 was not measured and 0 of 2 probes ran",
      any("RISK 1: not measured" in line for line in summary)
      and any("0 of 2" in line for line in summary), summary)

exit_code, _ = experiment.judge_run_report({
    "risk_1_patch_semantics": preserved_risk_1,
    "risk_2_pushes": as_expected_probes})
check("RISK 1 preserved and both probes as expected exits 0", exit_code == 0)

exit_code, _ = experiment.judge_run_report({
    "risk_1_patch_semantics": {"outcome": CLOBBERED, "sentence": "FINDING: "
                               "the partial PATCH CHANGED the count"},
    "risk_2_pushes": as_expected_probes})
check("an adverse RISK 1 finding (count clobbered) is still a completed "
      "measurement and exits 0, as the exit codes document",
      exit_code == 0)

exit_code, _ = experiment.judge_run_report({
    "risk_1_patch_semantics": {"outcome": NOT_MEASURED, "sentence": "ERROR:"},
    "risk_2_pushes": as_expected_probes})
check("RISK 1 not measured exits 1 even when both probes are as expected",
      exit_code == 1)

exit_code, summary = experiment.judge_run_report({
    "risk_1_patch_semantics": preserved_risk_1,
    "risk_2_pushes": as_expected_probes[:1]})
check("one probe of two exits 1 and the summary says 1 of 2 ran",
      exit_code == 1 and any("1 of 2" in line for line in summary),
      (exit_code, summary))

exit_code, _ = experiment.judge_run_report({
    "risk_1_patch_semantics": preserved_risk_1,
    "risk_2_pushes": [as_expected_probes[0], dict(
        as_expected_probes[1], outcome=CONTRADICTED,
        sentence="DISCREPANCY: accepted")]})
check("one contradicted probe exits 1 with RISK 1 preserved", exit_code == 1)

exit_code, summary = experiment.judge_run_report({
    "risk_1_patch_semantics": preserved_risk_1,
    "risk_2_pushes": [as_expected_probes[0],
                      probe_result(EXPERIMENT_BRANCH, expect_accepted=False,
                                   accepted=False, gh006=True, detail="")]})
check("a probe that was never judged exits 1 rather than passing by absence",
      exit_code == 1 and any("never judged" in line for line in summary),
      (exit_code, summary))


# --- leftover_experiment_branches: both branches guarded -------------------
# At 2de34bc only EXPERIMENT_BRANCH was checked. A FEATURE_BRANCH surviving
# a cleanup that could not finish sits one commit ahead of main, and the
# next run's push to it is a non-fast-forward, not a measurement.

check("no leftover when neither branch exists",
      experiment.leftover_experiment_branches(lambda _: False) == [])
check("a leftover FEATURE_BRANCH is found — the branch the old check never "
      "looked at",
      experiment.leftover_experiment_branches(
          lambda branch: branch == FEATURE_BRANCH) == [FEATURE_BRANCH])
check("a leftover EXPERIMENT_BRANCH is still found",
      experiment.leftover_experiment_branches(
          lambda branch: branch == EXPERIMENT_BRANCH) == [EXPERIMENT_BRANCH])
check("both leftovers are listed in cleanup's order",
      experiment.leftover_experiment_branches(lambda _: True)
      == [EXPERIMENT_BRANCH, FEATURE_BRANCH])
asked = []
experiment.leftover_experiment_branches(lambda branch: asked.append(branch))
check("the guard asks about exactly the two branches the program creates",
      asked == [EXPERIMENT_BRANCH, FEATURE_BRANCH], asked)

message = experiment.leftover_refusal_message([FEATURE_BRANCH])
check("the leftover refusal names the branch and says why it is not reused",
      FEATURE_BRANCH in message and "non-fast-forward" in message, message)
check("and it prints both hand-removal commands, protection first",
      all(command in message
          for command in experiment.removal_commands(FEATURE_BRANCH))
      and message.index("/protection") < message.index("git/refs/heads/"),
      message)


# --- the credential check: what a read proves, and what it cannot ---------
# merge-lane measured (2026-09-02) that ned-review-merge reports admin=true,
# reads main's protection, and cannot write it. Both stages of the old
# check tested read. These cases pin what the new check claims and refuses.

# `gh api -i user` on this Mac, 2026-09-02: status line, CR LF headers, a
# blank line, the body. The scope list is trimmed.
CAPTURED_HEADERS_AND_BODY = (
    "HTTP/2.0 200 OK\n"
    "Access-Control-Allow-Origin: *\r\n"
    "Github-Authentication-Token-Expiration: 2027-08-24 07:00:00 UTC\r\n"
    "X-Accepted-Oauth-Scopes: \r\n"
    "X-Github-Media-Type: github.v3; format=json\r\n"
    "X-Oauth-Scopes: admin:org, gist, repo, user, workflow\r\n"
    "\r\n"
    '{"login":"nedlern"}\n'
)
headers, body = experiment.split_headers_and_body(CAPTURED_HEADERS_AND_BODY)
check("the header block is split from the body and lowercased",
      headers.get("x-oauth-scopes") == "admin:org, gist, repo, user, workflow",
      headers)
check("the body after the blank line parses as the JSON gh printed",
      json.loads(body) == {"login": "nedlern"}, body)
check("an empty header value is kept as empty, not dropped",
      headers.get("x-accepted-oauth-scopes") == "", headers)

check("a classic token's scopes are read from X-OAuth-Scopes",
      experiment.classic_token_scopes(headers)
      == ["admin:org", "gist", "repo", "user", "workflow"])
check("no X-OAuth-Scopes header — a fine-grained or app token — reads as "
      "not introspectable, None",
      experiment.classic_token_scopes({"x-github-media-type": "github.v3"})
      is None)
check("an EMPTY X-OAuth-Scopes header also reads as None, not as a token "
      "with no scopes",
      experiment.classic_token_scopes({"x-oauth-scopes": ""}) is None)


def scope_refusal(scopes):
    try:
        experiment.refuse_if_classic_scopes_lack_repo("someone", scopes)
    except experiment.CredentialRefusal as refusal:
        return str(refusal)
    return None


check("CredentialRefusal is a Refusal, so every existing handler catches it",
      issubclass(experiment.CredentialRefusal, experiment.Refusal))
check("scopes that cannot be read (None) are not refused — the PUT is the "
      "check for those",
      scope_refusal(None) is None)
check("a classic token with `repo` is not refused",
      scope_refusal(["gist", "repo", "user"]) is None)
refusal_text = scope_refusal(["public_repo", "gist"])
check("a classic token WITHOUT `repo` is refused before anything is created",
      refusal_text is not None and "Nothing was created" in refusal_text,
      refusal_text)
check("and the refusal names both permissions and separates role from scope",
      refusal_text is not None and "`repo`" in refusal_text
      and "Administration: write" in refusal_text
      and "role belongs to the account" in refusal_text, refusal_text)

OLD_FALSE_CLAIM = "carries the scope the role needs"
startup = "\n".join(experiment.credential_startup_lines("someone", None))
check("with no readable scopes, the startup text names the PUT as the "
      "write check",
      "write check" in startup and EXPERIMENT_BRANCH in startup, startup)
check("and it does not repeat the old claim that the token carries the scope",
      OLD_FALSE_CLAIM not in startup
      and "writes branch protection" not in startup, startup)
startup = "\n".join(experiment.credential_startup_lines(
    "someone", ["gist", "repo"]))
check("with `repo` reported, the startup text says so and STILL names the "
      "PUT as the write check",
      "`repo`" in startup and "still the write check" in startup, startup)
check("and it never claims write capability before the PUT",
      OLD_FALSE_CLAIM not in startup
      and "writes branch protection" not in startup, startup)

# protection_write_refusal: the first PUT's 403 is the credential's failure.
FORBIDDEN = "gh: Resource not accessible by personal access token (HTTP 403)"
refusal = experiment.protection_write_refusal(EXPERIMENT_BRANCH, 1, FORBIDDEN)
check("a 403 on the protection PUT is a CredentialRefusal (exit 2), not a "
      "measurement failure",
      isinstance(refusal, experiment.CredentialRefusal), type(refusal))
check("and it quotes gh's stderr verbatim, so a rate-limit 403 can be told "
      "apart",
      FORBIDDEN in str(refusal), str(refusal))
check("and it names the missing permission for both token types and the "
      "branch cleanup will delete",
      "`repo`" in str(refusal) and "Administration: write" in str(refusal)
      and EXPERIMENT_BRANCH in str(refusal), str(refusal))
refusal = experiment.protection_write_refusal(
    EXPERIMENT_BRANCH, 1, "gh: Must have admin rights to Repository. (HTTP 403)")
check("GitHub's other 403 wording for this endpoint is classified the same",
      isinstance(refusal, experiment.CredentialRefusal), str(refusal))
refusal = experiment.protection_write_refusal(
    EXPERIMENT_BRANCH, 1, "gh: Internal Server Error (HTTP 500)")
check("a non-403 failure of the PUT stays a plain Refusal (exit 1)",
      isinstance(refusal, experiment.Refusal)
      and not isinstance(refusal, experiment.CredentialRefusal),
      type(refusal))


# --- cleanup on the credential path ---------------------------------------
# When the PUT was refused, the branch is in `protected` (recorded before
# the call, deliberately) and the protection DELETE is refused with the same
# 403. At 2de34bc that put the branch into `unfinished` even though the ref
# DELETE then succeeded, and the run announced a leftover that was gone.

PROTECTION_FORBIDDEN = "gh: Must have admin rights to Repository. (HTTP 403)"


def cleanup_with(protection_code, protection_stderr, ref_code, ref_stderr):
    def fake(argv, **_):
        if argv[-1].endswith("/protection"):
            return completed(argv, protection_code, stderr=protection_stderr)
        if "git/refs/heads/" in argv[-1]:
            return completed(argv, ref_code, stderr=ref_stderr)
        raise AssertionError(f"unexpected command in cleanup: {argv}")
    return with_run_command(
        fake, lambda: experiment.cleanup([EXPERIMENT_BRANCH], {EXPERIMENT_BRANCH}))


notes, unfinished = cleanup_with(1, PROTECTION_FORBIDDEN, 0, "")
check("credential path: protection DELETE 403 + ref DELETE ok is NOT a "
      "leftover — the branch is gone",
      unfinished == [], (notes, unfinished))
check("and the notes still record both what failed and that the branch was "
      "deleted",
      any("protection could NOT be removed" in note for note in notes)
      and any("branch deleted" in note for note in notes), notes)

notes, unfinished = cleanup_with(
    1, "gh: Branch not protected (HTTP 404)", 0, "")
check("a 404 from the protection DELETE is reported as nothing to remove",
      any("no protection to remove (404)" in note for note in notes)
      and unfinished == [], notes)

notes, unfinished = cleanup_with(
    0, "", 1, "gh: Reference does not exist (HTTP 422)")
check("a failed ref DELETE IS a leftover, whatever the protection DELETE said",
      unfinished == [EXPERIMENT_BRANCH], (notes, unfinished))

notes, unfinished = cleanup_with(
    1, "gh: Internal Server Error (HTTP 500)", 1,
    "gh: Cannot delete a protected branch (HTTP 422)")
check("protection standing and the branch undeletable is one leftover, "
      "listed once",
      unfinished == [EXPERIMENT_BRANCH], (notes, unfinished))
check("run_command is restored after the cleanup cases",
      experiment.run_command is real_run_command)


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
