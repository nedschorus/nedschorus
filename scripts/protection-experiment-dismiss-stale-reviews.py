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
nothing about whether dismissal works, and nothing about whether the PR
process can recover from a dismissal.

THE CREDENTIAL. The experiment runs under `ned-review-merge`, unattended
(user-ruled 2026-09-01, PR #228 review item 1). Both endpoints it writes
need the repository ADMIN role: a classic token needs the `repo` scope
held by an admin account, a fine-grained token needs
"Administration: write". GitHub does NOT scope branch-protection
permission per branch, so an account that can protect the throwaway
branch can also rewrite main's protection; the restraint therefore lives
in refuse_if_main below, where it is tested, and not in the credential.

The account's role and the token's permission are different things, and
no read proves the second (PR #228 review round 2, merge-lane's
measurement: ned-review-merge reports admin=true, reads main's
protection, and cannot write it). check_experiment_credential runs
BEFORE anything is created and refuses on what a read can show: an
account without the admin role, or a classic token whose X-OAuth-Scopes
header omits `repo`. A fine-grained token's permissions cannot be read
back at all, so write capability is proven by a write that is safe by
construction: the run's first two calls create the throwaway branch and
PUT protection on it, before the clone and before anything else. A 403
there means the token cannot write protection; it is named as such, the
run exits 2, and cleanup deletes a branch that nothing protects.

WHERE IT RUNS FROM. The program clones the repository into a temporary
directory of its own and commits and pushes from there, removing the
directory when it is done. It never commits into the repository the
operator happens to be standing in (user-ruled 2026-09-01, PR #228
review item 2). The throwaway branch is created from main's tip as
GitHub reports it and the clone is taken afterwards; main cannot be
force-pushed, so the clone's tip descends from the branch's base and a
push probe from the clone is a fast-forward on the clone's side. The
destination side is guarded by the refusal to start while either
throwaway branch already exists, so a push probe can only be refused by
branch protection -- which is the thing being measured -- and never as a
stale non-fast-forward.

SAFETY. Every write targets a throwaway branch this script creates and
deletes. It refuses to operate on main by name, and it refuses if either
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
3). judge_partial_patch_result holds that judgment for RISK 1 and
judge_push_probe_result holds it for RISK 2, each alone and pure, and
judge_run_report turns the two into the exit code and the summary, so all
three can be tested without a network: see
scripts/protection-experiment-dismiss-stale-reviews-test.py.

USAGE
  python3 scripts/protection-experiment-dismiss-stale-reviews.py --dry-run
  python3 scripts/protection-experiment-dismiss-stale-reviews.py --run

Exit codes: 0 every measurement completed and every push probe came out
as expected (findings are in the report, which is printed and may still
say the PATCH is unsafe); 1 a measurement could not be completed, or a
push probe contradicted its expectation, and the report says which; 2 bad
invocation, a safety refusal, or a credential that cannot do the work.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Callable

REPO_SLUG = "nedschorus/nedschorus"
REPO_CLONE_URL = "https://github.com/nedschorus/nedschorus.git"
MAIN_BRANCH = "main"
# Fixed branch names make leftovers from interrupted runs recognizable.
EXPERIMENT_BRANCH = "protection-experiment-dismiss-stale-reviews"
FEATURE_BRANCH = "protection-experiment-dismiss-stale-reviews-feature"
EXPERIMENT_BRANCHES = (EXPERIMENT_BRANCH, FEATURE_BRANCH)
PUSH_PROBES = (
    (FEATURE_BRANCH, True, "unprotected branch"),
    (EXPERIMENT_BRANCH, False, "protected, reviews required"),
)
# Check capability rather than account name; another admin account may run the experiment.
RULED_EXPERIMENT_ACCOUNT = "ned-review-merge"
CLASSIC_TOKEN_PROTECTION_SCOPE = "repo"
FINE_GRAINED_PROTECTION_PERMISSION = "Administration: write"
SCRATCH_CLONE_PREFIX = "protection-experiment-dismiss-stale-reviews-clone-"

COMMAND_TIMEOUT_SECONDS = 30
CLONE_TIMEOUT_SECONDS = 300

PATCH_SEMANTICS_PRESERVED = "count-preserved"
PATCH_SEMANTICS_CLOBBERED = "count-clobbered"
PATCH_SEMANTICS_NOT_MEASURED = "not-measured"

PUSH_PROBE_AS_EXPECTED = "as-expected"
PUSH_PROBE_CONTRADICTED = "contradicted"
PUSH_PROBE_NOT_MEASURED = "not-measured"


class Refusal(Exception):
    """A safety refusal or impossible measurement carrying its fix."""


class CredentialRefusal(Refusal):
    """A credential failure that prevents measurement and exits 2."""


def refuse_if_main(branch: str) -> None:
    # GitHub cannot restrict branch-protection credentials to the throwaway branch.
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
    # Captured credential prompts cannot be answered; disable prompting and bound the wait.
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


def split_headers_and_body(output: str) -> tuple[dict[str, str], str]:
    """Return lowercased headers and body text from gh api -i output."""
    lines = output.split("\n")
    headers: dict[str, str] = {}
    body_start = len(lines)
    for index, line in enumerate(lines[1:], start=1):
        line = line.rstrip("\r")
        if not line:
            body_start = index + 1
            break
        name, separator, value = line.partition(":")
        if separator:
            headers[name.strip().lower()] = value.strip()
    return headers, "\n".join(lines[body_start:])


def api_json_with_headers(path: str) -> tuple[dict[str, str], dict]:
    """Return response headers and the JSON body from one GET."""
    completed = gh(["api", "-i", path])
    headers, body = split_headers_and_body(completed.stdout)
    try:
        return headers, json.loads(body)
    except json.JSONDecodeError as error:
        raise Refusal(f"{path} did not answer JSON: {error}") from None


def classic_token_scopes(headers: dict[str, str]) -> list[str] | None:
    """Return reported classic-token scopes, or None when unavailable."""
    # An absent or empty scope header cannot establish fine-grained token permissions.
    raw = headers.get("x-oauth-scopes")
    if raw is None:
        return None
    scopes = [scope.strip() for scope in raw.split(",") if scope.strip()]
    return scopes or None


def refuse_if_classic_scopes_lack_repo(
    login: str, classic_scopes: list[str] | None
) -> None:
    # Unknown scopes prove nothing; the first protection PUT checks write capability.
    if classic_scopes is None or CLASSIC_TOKEN_PROTECTION_SCOPE in classic_scopes:
        return
    raise CredentialRefusal(
        f"{login}'s token is a classic token whose scopes, as GitHub reports "
        f"them ({', '.join(classic_scopes)}), do not include "
        f"`{CLASSIC_TOKEN_PROTECTION_SCOPE}`, the scope GitHub documents for "
        "the branch-protection endpoints. The account's admin role does not "
        "substitute: the role belongs to the account, the scope to the token. "
        f"Re-run under {RULED_EXPERIMENT_ACCOUNT} with a token that carries "
        f"`{CLASSIC_TOKEN_PROTECTION_SCOPE}` (classic) or "
        f"{FINE_GRAINED_PROTECTION_PERMISSION} (fine-grained). "
        "Nothing was created."
    )


def check_experiment_credential() -> tuple[str, list[str] | None]:
    """Check readable permissions and return (login, classic scopes or None)."""
    # An account’s admin role does not prove its token can write; the protection PUT must establish that.
    headers, identity = api_json_with_headers("user")
    login = (identity or {}).get("login") or "(unknown)"
    classic_scopes = classic_token_scopes(headers)
    repository = api_json(f"repos/{REPO_SLUG}")
    if repository is None:
        raise CredentialRefusal(
            f"could not read {REPO_SLUG} as {login}. The experiment needs a "
            "credential that can reach the repository; authenticate gh and "
            "re-run. Nothing was created."
        )
    if not bool((repository.get("permissions") or {}).get("admin")):
        raise CredentialRefusal(
            f"{login} does not hold the admin role on {REPO_SLUG}, and both "
            "endpoints this experiment writes -- PUT branch protection and "
            "PATCH required_pull_request_reviews -- need it. Re-run under "
            f"{RULED_EXPERIMENT_ACCOUNT}, whose token must carry the "
            f"`{CLASSIC_TOKEN_PROTECTION_SCOPE}` scope (classic) or "
            f"{FINE_GRAINED_PROTECTION_PERMISSION} (fine-grained). "
            "Nothing was created."
        )
    refuse_if_classic_scopes_lack_repo(login, classic_scopes)
    return login, classic_scopes


def credential_startup_lines(
    login: str, classic_scopes: list[str] | None
) -> list[str]:
    lines = [
        f"credential: {login} holds the admin role on {REPO_SLUG}, and main's "
        "protection reads. That proves the role and a read; it does not "
        "prove the token can write protection."
    ]
    if classic_scopes is None:
        lines.append(
            "  GitHub reports no scopes for this token (no X-OAuth-Scopes "
            "header: a fine-grained or app token), and a fine-grained token's "
            "permissions cannot be read back. The first protection PUT, on "
            f"{EXPERIMENT_BRANCH}, is the write check; a 403 there names "
            f"{FINE_GRAINED_PROTECTION_PERMISSION} as the missing permission."
        )
    elif CLASSIC_TOKEN_PROTECTION_SCOPE in classic_scopes:
        lines.append(
            "  classic token; GitHub reports its scopes as: "
            f"{', '.join(classic_scopes)}. `{CLASSIC_TOKEN_PROTECTION_SCOPE}` "
            "is among them, the scope GitHub documents for the "
            "branch-protection endpoints. The first protection PUT, on "
            f"{EXPERIMENT_BRANCH}, is still the write check."
        )
    else:
        lines.append(
            "  classic token; GitHub reports its scopes as: "
            f"{', '.join(classic_scopes)}, without "
            f"`{CLASSIC_TOKEN_PROTECTION_SCOPE}`. It cannot write protection."
        )
    return lines


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


def read_main_tip_sha() -> str:
    reference = api_json(f"repos/{REPO_SLUG}/git/ref/heads/{MAIN_BRANCH}")
    sha = ((reference or {}).get("object") or {}).get("sha")
    if not sha:
        raise Refusal(
            f"could not read {MAIN_BRANCH}'s tip from GitHub ({reference!r}). "
            "Nothing was created."
        )
    return sha


def protection_payload_from(main_protection: dict, *, dismiss_stale: bool) -> dict:
    """Return main’s protection settings without push restrictions."""
    # Copying the real-account allow-list would prevent the experiment’s setup pushes.
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
    """Return (outcome, report sentence) for the PATCH read-back."""
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
            f"stderr: {completed.stderr.strip() or '(empty)'}"
        )
    return directory


def protection_write_refusal(branch: str, returncode: int, stderr: str) -> Refusal:
    """Return a refusal for a failed protection PUT."""
    # Preserve stderr: HTTP 403 can mean insufficient permissions or a secondary rate limit.
    detail = stderr.strip() or "(empty)"
    if "HTTP 403" in detail:
        return CredentialRefusal(
            f"GitHub refused to write protection on {branch} (exit "
            f"{returncode}).\nstderr: {detail}\n"
            "A 403 here means this token cannot write branch protection, "
            "whatever role the account holds: it needs "
            f"`{CLASSIC_TOKEN_PROTECTION_SCOPE}` (classic) or "
            f"{FINE_GRAINED_PROTECTION_PERMISSION} (fine-grained). Nothing is "
            f"protected; cleanup below deletes {branch}. Re-run under "
            f"{RULED_EXPERIMENT_ACCOUNT} with a token that carries the "
            "permission."
        )
    return Refusal(
        f"applying protection to {branch} failed with exit {returncode}.\n"
        f"stderr: {detail}"
    )


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
        raise protection_write_refusal(
            branch, completed.returncode, completed.stderr
        )


def read_review_settings(branch: str) -> dict:
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
    """PATCH only dismiss_stale_reviews and return the response body."""
    # Only a fresh GET establishes stored state; the PATCH response may echo the request.
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


def push_probe(
    branch: str, *, expect_accepted: bool, reason: str, clone_directory: str
) -> dict:
    """Push an empty commit and return the observed and expected outcomes."""
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
        "expected": f"{'accepted' if expect_accepted else 'refused'} ({reason})",
        "expect_accepted": expect_accepted,
        "accepted": completed.returncode == 0,
        "gh006": "GH006" in combined,
        "detail": combined[-400:] or "(no output)",
    }


def judge_push_probe_result(probe: dict) -> tuple[str, str]:
    """Return (outcome, report sentence) for one push probe."""
    # A rejection without GH006 does not establish that branch protection was exercised.
    branch = probe.get("branch") or "(unknown branch)"
    expected = probe.get("expected") or "(no expectation recorded)"
    expect_accepted = probe.get("expect_accepted")
    accepted = probe.get("accepted")
    if not isinstance(expect_accepted, bool) or not isinstance(accepted, bool):
        return (
            PUSH_PROBE_NOT_MEASURED,
            f"ERROR: the push probe on {branch} is incomplete "
            f"(expect_accepted={expect_accepted!r}, accepted={accepted!r}), "
            "so nothing was measured.",
        )
    detail = probe.get("detail") or "(no output)"
    if accepted:
        if expect_accepted:
            return (
                PUSH_PROBE_AS_EXPECTED,
                f"FINDING: the push to {branch} was accepted, as expected "
                f"({expected}).",
            )
        return (
            PUSH_PROBE_CONTRADICTED,
            f"DISCREPANCY: the push to {branch} was ACCEPTED, but branch "
            f"protection was expected to refuse it ({expected}). The "
            "protection this run applied did not stop a direct push, so RISK "
            "2 was not measured against a protected branch. This run "
            "licenses nothing.",
        )
    if not probe.get("gh006"):
        return (
            PUSH_PROBE_NOT_MEASURED,
            f"ERROR: the push to {branch} was refused, but not by branch "
            "protection -- git's output carries no GH006 -- so nothing was "
            f"measured. git said: {detail}. A leftover {branch} from an "
            "earlier run, or a credential git cannot use, produces this.",
        )
    if expect_accepted:
        return (
            PUSH_PROBE_CONTRADICTED,
            f"DISCREPANCY: branch protection refused (GH006) the push to "
            f"{branch}, which is unprotected and was expected to accept it "
            f"({expected}). Ordinary pushes ARE affected. This run licenses "
            f"nothing until that is understood. git said: {detail}",
        )
    return (
        PUSH_PROBE_AS_EXPECTED,
        f"FINDING: branch protection refused (GH006) the push to {branch}, "
        f"as expected ({expected}).",
    )


def judge_run_report(report: dict) -> tuple[int, list[str]]:
    """Return (exit code, summary) from the measured report."""
    # An unsafe PATCH finding is still a completed measurement and exits 0.
    exit_code = 0
    lines: list[str] = []
    risk_1 = report.get("risk_1_patch_semantics")
    if not isinstance(risk_1, dict):
        lines.append(
            "RISK 1: not measured -- the run stopped before the partial "
            "PATCH was judged."
        )
        exit_code = 1
    else:
        lines.append(f"RISK 1: {risk_1.get('sentence')}")
        if risk_1.get("outcome") == PATCH_SEMANTICS_NOT_MEASURED:
            exit_code = 1
    probes = report.get("risk_2_pushes") or []
    for probe in probes:
        sentence = probe.get("sentence") or (
            f"ERROR: the probe on {probe.get('branch')} was never judged."
        )
        lines.append(f"RISK 2: {sentence}")
        if probe.get("outcome") != PUSH_PROBE_AS_EXPECTED:
            exit_code = 1
    if len(probes) < len(PUSH_PROBES):
        lines.append(
            f"RISK 2: not measured -- {len(probes)} of {len(PUSH_PROBES)} "
            "push probes ran."
        )
        exit_code = 1
    return exit_code, lines


def branch_exists(branch: str) -> bool:
    return api_json(
        f"repos/{REPO_SLUG}/branches/{branch}", allow_failure=True
    ) is not None


def leftover_experiment_branches(exists: Callable[[str], bool]) -> list[str]:
    return [branch for branch in EXPERIMENT_BRANCHES if exists(branch)]


def leftover_refusal_message(leftover: list[str]) -> str:
    # A leftover feature branch can cause a non-fast-forward rejection unrelated to protection.
    lines = [
        f"already on the repository: {', '.join(leftover)} -- a leftover from "
        "an interrupted run, or from a cleanup that could not finish. A "
        "leftover is inspected by a person, not reused: a push to it would be "
        "a stale non-fast-forward, not a measurement. Remove it by hand, "
        "protection first (a 404 from the protection delete means it had "
        "none), then re-run:"
    ]
    for branch in leftover:
        for command in removal_commands(branch):
            lines.append(f"  {command}")
    return "\n".join(lines)


def removal_commands(branch: str) -> list[str]:
    """Return commands to remove protection and then the branch."""
    # allow_deletions=false prevents branch deletion until protection is removed.
    return [
        f"gh api -X DELETE repos/{REPO_SLUG}/branches/{branch}/protection",
        f"gh api -X DELETE repos/{REPO_SLUG}/git/refs/heads/{branch}",
    ]


def cleanup_command(argv: list[str]) -> tuple[int, str]:
    """Run a cleanup call and return failures without raising."""
    # Raising from finally would replace the failure that triggered cleanup.
    try:
        completed = run_command(argv)
    except Refusal as refusal:
        return 1, str(refusal)
    return completed.returncode, (
        completed.stderr.strip() or completed.stdout.strip() or "(no output)"
    )


def cleanup(branches: list[str], protected: set[str]) -> tuple[list[str], list[str]]:
    """Remove created branches and return (notes, unfinished)."""
    # Use the API because the scratch clone may be unavailable.
    # Only a failed ref deletion leaves a branch; a failed protection deletion alone does not.
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
            unfinished.append(branch)
    return notes, unfinished


def report_unfinished_cleanup(unfinished: list[str]) -> None:
    print(
        "\nTHE LIVE REPOSITORY HAS BEEN LEFT MODIFIED. Cleanup could not "
        f"finish for: {', '.join(unfinished)}.\n"
        "Each leftover branch still exists on GitHub. Remove it by hand, "
        "protection first -- while the protection copied from main stands it "
        "forbids deleting the branch; a 404 from the protection delete means "
        "it has none:",
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
        login, classic_scopes = check_experiment_credential()
        main_protection = read_main_protection()
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2

    for line in credential_startup_lines(login, classic_scopes):
        print(line)
    if login.casefold() != RULED_EXPERIMENT_ACCOUNT.casefold():
        print(f"note: the ruled account for this experiment is "
              f"{RULED_EXPERIMENT_ACCOUNT}; this run is {login}.")

    reviews_now = main_protection.get("required_pull_request_reviews") or {}
    print("main's live review settings (read-only):")
    print(json.dumps(reviews_now, indent=2))

    if arguments.dry_run:
        print("\nplan, in order:")
        print("  1. check the credential by reading: admin role, classic-token")
        print("     scopes where GitHub reports them, main's protection (done above)")
        print(f"  2. refuse if {EXPERIMENT_BRANCH} or {FEATURE_BRANCH}")
        print("     already exists")
        print(f"  3. create {EXPERIMENT_BRANCH} from main's tip as GitHub reports it")
        print("  4. apply main-shaped protection to it, dismiss_stale_reviews=false")
        print("     -> this PUT is the credential's WRITE check: a 403 names the")
        print("        missing permission, exits 2, and leaves only an unprotected")
        print("        branch, which cleanup deletes")
        print("  5. clone the repository into a temporary directory of its own, so")
        print("     nothing is committed into the repository you are standing in")
        print("  6. read required_pull_request_reviews, PATCH naming ONLY")
        print("     dismiss_stale_reviews=true, then read it back with a FRESH GET")
        print("     -> if required_approving_review_count survives, the partial")
        print("        PATCH is safe; if it changes, the full form is required;")
        print("        if the PATCH did not take effect, nothing was measured")
        print(f"  7. push from the clone to {FEATURE_BRANCH}, unprotected")
        print("     -> expect accepted")
        print(f"  8. push from the clone to {EXPERIMENT_BRANCH}")
        print("     -> expect refused by branch protection (GH006)")
        print("     -> a probe that contradicts its expectation, or is refused for")
        print("        any reason other than protection, exits 1")
        print("  9. delete both branches and their protection, and remove the clone")
        print("\nnothing was written.")
        return 0

    try:
        leftover = leftover_experiment_branches(branch_exists)
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2
    if leftover:
        print(f"refused: {leftover_refusal_message(leftover)}", file=sys.stderr)
        return 2

    report: dict = {"risk_1_patch_semantics": None, "risk_2_pushes": []}
    created: list[str] = []
    protected: set[str] = set()
    clone_directory: str | None = None
    exit_code = 0
    try:
        # Check protection write capability before cloning; a refused PUT leaves an unprotected branch to clean up.
        gh(["api", "-X", "POST", f"repos/{REPO_SLUG}/git/refs",
            "-f", f"ref=refs/heads/{EXPERIMENT_BRANCH}",
            "-f", f"sha={read_main_tip_sha()}"])
        created.append(EXPERIMENT_BRANCH)

        # Record protection intent before the PUT: a failed reply can follow a successful write.
        protected.add(EXPERIMENT_BRANCH)
        put_protection(
            EXPERIMENT_BRANCH,
            protection_payload_from(main_protection, dismiss_stale=False),
        )
        print(f"\ncredential: the protection PUT on {EXPERIMENT_BRANCH} "
              f"succeeded, so {login}'s token writes branch protection.")

        clone_directory = clone_scratch_repository()

        before = read_review_settings(EXPERIMENT_BRANCH)
        patch_response = patch_reviews_partial(EXPERIMENT_BRANCH)
        # Read stored state afresh; the PATCH response may only echo the request.
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

        for branch, expect_accepted, reason in PUSH_PROBES:
            probe = push_probe(
                branch,
                expect_accepted=expect_accepted,
                reason=reason,
                clone_directory=clone_directory,
            )
            # A rejected push created no branch, so cleanup must not try deleting one.
            if probe["accepted"] and branch not in created:
                created.append(branch)
            probe["outcome"], probe["sentence"] = judge_push_probe_result(probe)
            report["risk_2_pushes"].append(probe)
    except KeyboardInterrupt:
        print("\ninterrupted; cleaning up before exiting.", file=sys.stderr)
        exit_code = 1
    except CredentialRefusal as refusal:
        print(f"\nrefused: {refusal}", file=sys.stderr)
        exit_code = 2
    except Refusal as failure:
        print(f"\nmeasurement stopped: {failure}", file=sys.stderr)
        exit_code = 1
    finally:
        # Returning from finally would swallow the original exception.
        notes, unfinished = cleanup(created, protected)
        print("\ncleanup:", *(notes or ["nothing to clean up"]), sep="\n  ")
        if clone_directory:
            shutil.rmtree(clone_directory, ignore_errors=True)
            print(f"  scratch clone removed: {clone_directory}")
        if unfinished:
            report_unfinished_cleanup(unfinished)

    print("\nreport:")
    print(json.dumps(report, indent=2))
    judged_code, summary = judge_run_report(report)
    print("\nsummary:", *summary, sep="\n  ")
    return exit_code or judged_code


if __name__ == "__main__":
    sys.exit(main())
