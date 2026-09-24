#!/bin/bash
# Gate a merge. Exits 0 only if every check passes; any problem exits non-zero
# with a reason on stderr. It GATES -- it does not print a count and continue.
#
#   scripts/merge-gate.sh <pr-number> <expected-head-sha> <reviewed-since-iso8601>
#
# EXIT CODES. 0 the merge may proceed; 1 the gate REFUSES, a named reason on
# stderr; 2 the gate COULD NOT RUN -- bad invocation, missing jq, unreadable
# token. 1 and 2 are distinguished because the fleet's near-miss shape is a gate
# that could not run being read as a gate that passed.
#
# Deliberately: no gating command is piped, because a pipeline's exit status is
# its last command's and that has cost this fleet three separate near-misses.
# Where a page of JSON must be combined, the capture and the jq run are separate
# statements over a here-string, never a pipe.
#
# THE PIN (user-ruled 2026-08-29). The gate derives the commit to merge from the
# LATEST APPROVING REVIEW's recorded commit_id, not from the head it happens to
# observe, and prints a merge command pinned to it with --match-head-commit. An
# approval then only ever merges the exact code that approval covered: GitHub
# refuses at the merge instant if the head has moved since, which closes the
# window between this gate passing and `gh pr merge` running. dismiss_stale_reviews
# stays OFF; the no-approval case still refuses here.
#
# MEASURED before relying on it (2026-08-29, PR #156): a review's commit_id is
# STABLE when the head moves. #156's head was 560936804 while its 2026-08-24
# reviews still recorded 8d4305f55. This is NOT true of comments -- see the note
# on the comment channels below -- so the two are read differently on purpose.
#
# WHY EVERY CHANNEL READ PAGINATES (F1, the worst of seven false passes an
# independent review demonstrated 2026-09-22 against the pre-repository copy).
# GitHub returns 30 items per page, OLDEST FIRST, on all three channels. Without
# --paginate everything newer than the 30th item is invisible, so a "nothing new
# since" check counts zero on exactly the pull requests that have the most
# activity. Demonstrated with 35 inline comments, 5 of them after SINCE: the gate
# passed. gh's own --slurp is not used because it is refused alongside --jq and
# is absent from older gh releases -- ned-box ran 2.46.0 when this was written;
# jq -s over a captured here-string is equivalent and portable.
#
# WHY SINCE IS BOUNDED (F2). SINCE was caller-supplied and unbounded, so
# `$(date -u +%FT%TZ)` -- "since now" -- turned all three activity checks into
# no-ops. SINCE may be no later than the last moment the merge account
# demonstrably acted on the pull request: the pinned approval, or the merge
# account's own latest submitted review if that is later. Anything later is
# refused rather than trusted.
#
# The second half exists for pull requests the merge account itself opened.
# GitHub refuses an approval from a pull request's author, so there mac-claude
# approves (the pin) and the merge account then posts its required review as
# COMMENTED. Bounded by the pin alone, that flow was refused at every SINCE: at
# or before the approval its own review counted as new activity, after the
# approval SINCE was out of bounds. The last nine pull requests the merge
# account opened before 2026-09-23T23:45Z, 616 to 687, all have this shape (PR
# 687 is the case in the suite). What this allows: a SINCE at the merge account's own latest review,
# so activity by any account between the pin and that review is not counted --
# the same trust the ordinary flow already places in SINCE, which is the merge
# account's own approval there. A review with findings from any account still
# counts when it lands after SINCE, and a CHANGES_REQUESTED still refuses
# through reviewDecision.
#
# WHY THE FORMAT IS STRICT (F3). Timestamps were compared as strings inside jq,
# where an RFC 3339 SINCE carrying a positive offset under-counts to a FALSE PASS.
# Rather than parse offsets, the gate accepts only the exact form GitHub itself
# returns, YYYY-MM-DDTHH:MM:SSZ, and compares epoch seconds via fromdateiso8601.
# A different-but-valid RFC 3339 spelling is refused with its reason, which is a
# false refusal by design and cheap to correct at the call site.
#
# WHY ANY ACCOUNT'S APPROVAL MAY BE THE PIN. The 2026-09-22 cleanup added a
# filter refusing an approval by the merge account, on the belief that the
# approval must come from the commissioned independent reviewer. The merge
# account approves every pull request it merges, and on 13 of the 20 merges
# before 2026-09-23T22:44Z its approval was the only one at the head, so the
# filter refused most real merges. The user ruled it out 2026-09-23. GitHub's
# required review already refuses an approval from the pull request's author.
#
# WHY THE REVIEW CHANNEL NO LONGER EXCLUDES AN ACCOUNT (F5). It excluded every
# review by the merge account unconditionally, so that account's own later
# COMMENTED review -- the merge lane reviewing the code itself and recording
# findings -- was read by nobody. Only the pinned approving review is excluded
# now, by its id, because counting it would refuse every merge it authorises.
#
# WHY COMMENTS ARE READ BY THEIR LATEST TIMESTAMP (F6). created_at alone missed a
# comment EDITED after the review to add a finding.
#
# UNSTABLE REMAINS ON THE ALLOW-LIST (F7) and is deliberately NOT changed here.
# It permits merging with red non-required checks, which may be intended; it was
# not demonstrated as a false pass and changing it is the user's ruling, not this
# rebuild's. Recorded so the next reader knows it was seen and left.
set -u

REPO=nedschorus/nedschorus
MERGE_ACCOUNT=ned-review-merge
TOKEN_FILE=$HOME/.config/nedschorus/$MERGE_ACCOUNT.token

fail()    { echo "GATE REFUSED (#${PR:-?}): $*" >&2; exit 1; }
cannot()  { echo "GATE COULD NOT RUN: $*" >&2; exit 2; }

[ $# -eq 3 ] || cannot "usage: merge-gate.sh <pr-number> <expected-head-sha> <reviewed-since-iso8601>"
PR=$1; EXPECTED=$2; SINCE=$3

command -v jq >/dev/null 2>&1 || cannot "jq is not on PATH. Put jq on PATH, then rerun the gate."
command -v gh >/dev/null 2>&1 || cannot "gh is not on PATH"

# An abbreviated or malformed EXPECTED used to refuse as "head moved", naming the
# wrong cause: the head had not moved, the caller had passed a short sha.
case "$EXPECTED" in
  *[!0-9a-f]*|"") cannot "expected-head-sha is not a full 40-character hex sha: $EXPECTED" ;;
esac
[ ${#EXPECTED} -eq 40 ] || cannot "expected-head-sha is ${#EXPECTED} characters, not 40: $EXPECTED"

case "$SINCE" in
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z) : ;;
  *) cannot "reviewed-since must be exactly YYYY-MM-DDTHH:MM:SSZ, the form GitHub returns: $SINCE" ;;
esac

# export's own status masked cat's, so a missing token file was swallowed and
# GH_TOKEN was set to the empty string -- which gh treats as unset, falling back
# to the stored credential, on this Mac the account that AUTHORS these pull
# requests. Read, check, then export.
token=$(cat "$TOKEN_FILE" 2>/dev/null)
[ $? -eq 0 ] || cannot "could not read the merge account's token at $TOKEN_FILE"
[ -n "$token" ] || cannot "the token file $TOKEN_FILE is empty"
export GH_TOKEN="$token"

state=$(gh pr view "$PR" --repo "$REPO" --json headRefOid,mergeStateStatus,reviewDecision,isDraft)
[ $? -eq 0 ] || fail "could not read pull request state"

head=$(jq -r .headRefOid <<<"$state")
merge_state=$(jq -r .mergeStateStatus <<<"$state")
decision=$(jq -r .reviewDecision <<<"$state")
draft=$(jq -r .isDraft <<<"$state")

# The authoritative commit is the one the newest approving review was recorded
# against -- never $head, and never $EXPECTED, both of which are what someone
# BELIEVES was reviewed. Paginated, because an approval at index 32 was invisible
# and refused as "no APPROVED review found". Not piped: the exit status must be
# this call's.
reviews_raw=$(gh api "repos/$REPO/pulls/$PR/reviews" --paginate)
[ $? -eq 0 ] || fail "could not read the review channel for the approving commit"

approval=$(jq -s -c \
  '[.[][] | select(.state == "APPROVED")]
   | sort_by(.submitted_at) | last // empty' <<<"$reviews_raw")
[ $? -eq 0 ] || cannot "could not parse the review channel"
[ -n "$approval" ] || fail "no APPROVED review found"

approved_sha=$(jq -r '.commit_id' <<<"$approval")
approval_id=$(jq -r '.id' <<<"$approval")
approval_at=$(jq -r '.submitted_at' <<<"$approval")
approver=$(jq -r '.user.login' <<<"$approval")
[ -n "$approved_sha" ] && [ "$approved_sha" != "null" ] || fail "the approving review records no commit_id to pin to"

# "Since now" made every activity check below a no-op (F2). A PENDING review has
# no submitted_at and is left out of the bound.
bound_at=$(jq -s -r --arg merge_account "$MERGE_ACCOUNT" --arg approved "$approval_at" \
  '[$approved] + [.[][] | select(.user.login == $merge_account and .submitted_at != null)
                          | .submitted_at]
   | max_by(fromdateiso8601)' <<<"$reviews_raw")
[ $? -eq 0 ] || cannot "could not parse the review channel"
since_ok=$(jq -n --arg since "$SINCE" --arg bound "$bound_at" \
  '($since | fromdateiso8601) <= ($bound | fromdateiso8601)')
[ $? -eq 0 ] || cannot "could not compare reviewed-since against $bound_at"
[ "$since_ok" = "true" ] || fail "reviewed-since $SINCE is later than $bound_at, the approval or the merge account's own latest review. Rerun with a reviewed-since no later than $bound_at."

[ "$head" = "$EXPECTED" ] || fail "head moved: reviewed $EXPECTED, now $head"
# Merging past this would land code no approval covered.
[ "$approved_sha" = "$head" ] || fail "the approval covers $approved_sha but the head is now $head. Review and approve $head before merging."
[ "$draft" = "false" ]    || fail "pull request is a draft"
[ "$decision" = "APPROVED" ] || fail "reviewDecision is $decision, not APPROVED"
case "$merge_state" in
  CLEAN|UNSTABLE|HAS_HOOKS) : ;;
  *) fail "mergeStateStatus is $merge_state" ;;
esac

# Both comment channels, by their LATEST timestamp -- NOT by commit_id, which
# GitHub remaps to the new head and which therefore proves nothing about age.
inline_raw=$(gh api "repos/$REPO/pulls/$PR/comments" --paginate)
[ $? -eq 0 ] || fail "could not read the inline comment channel"
issue_raw=$(gh api "repos/$REPO/issues/$PR/comments" --paginate)
[ $? -eq 0 ] || fail "could not read the issue comment channel"

inline=$(jq -s --arg since "$SINCE" \
  '[.[][] | select(([.created_at, .updated_at] | map(select(. != null)) | max | fromdateiso8601)
                   > ($since | fromdateiso8601))] | length' <<<"$inline_raw")
[ $? -eq 0 ] || cannot "could not parse the inline comment channel"
issue=$(jq -s --arg since "$SINCE" \
  '[.[][] | select(([.created_at, .updated_at] | map(select(. != null)) | max | fromdateiso8601)
                   > ($since | fromdateiso8601))] | length' <<<"$issue_raw")
[ $? -eq 0 ] || cannot "could not parse the issue comment channel"

# Every account's later reviews count, including the merge account's own
# findings. Only the pinned approval is excluded, by id: counting it would refuse
# every merge it authorises.
reviews=$(jq -s --arg since "$SINCE" --argjson approval_id "$approval_id" \
  '[.[][] | select(.id != $approval_id and (.submitted_at | fromdateiso8601) > ($since | fromdateiso8601))] | length' <<<"$reviews_raw")
[ $? -eq 0 ] || cannot "could not parse the review channel"

[ "$inline" -eq 0 ]  || fail "$inline NEW inline comment(s) since $SINCE -- read them before merging"
[ "$issue" -eq 0 ]   || fail "$issue NEW issue comment(s) since $SINCE -- read them before merging"
[ "$reviews" -eq 0 ] || fail "$reviews NEW review(s) since $SINCE -- read them before merging"

echo "gate passed (#$PR): approved commit $approved_sha by $approver at $approval_at, $decision, $merge_state, no new channel activity since $SINCE"
# The pin (--match-head-commit) is what makes the approval binding: GitHub
# refuses the merge if the head has moved since the approval.
echo "MERGE WITH THIS EXACT COMMAND:"
echo "  gh pr merge $PR --repo $REPO --merge --delete-branch --match-head-commit $approved_sha"
