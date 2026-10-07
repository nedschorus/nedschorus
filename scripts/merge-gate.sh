#!/bin/bash
# Gate a merge. Exits 0 only if every check passes; any problem exits non-zero
# with a reason on stderr. It GATES -- it does not print a count and continue.
#
#   scripts/merge-gate.sh <pr-number> <expected-head-sha> <reviewed-since-iso8601>
#
# EXIT CODES. 0 the merge may proceed; 1 the gate REFUSES, a named reason on
# stderr; 2 the gate COULD NOT RUN -- bad invocation, missing jq or gh,
# unreadable token, or a read from GitHub that failed or could not be parsed.
# 1 and 2 are distinguished because the fleet's near-miss shape is a gate
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
# WHY AN INLINE COMMENT POSTED WITH A REVIEW THE CALLER WROTE OR READ IS READ AT
# THAT REVIEW'S TIME. GHI "The merge gate refuses a merge when the merge
# account's own review carries inline comments stamped a second later",
# https://github.com/nedschorus/nedschorus/issues/729. GitHub stamps an inline
# comment posted as part of a review with its own clock, which can read one
# second after the review's submitted_at. On PR "A handoff's worktree cleaner
# stopped at its time bound is counted and leaves no process running"
# (https://github.com/nedschorus/nedschorus/pull/722) the merge account's
# COMMENTED review read 20:43:02Z and its three inline comments 20:43:03Z. F2
# bounds SINCE at that review, so no accepted SINCE was later than the
# comments, they always counted as new, and the merge could never pass.
#
# So an inline comment is read at its review's submitted_at, instead of its own
# latest timestamp, when all of these hold:
#   - its pull_request_review_id is the pinned approval, or a review by the
#     merge account;
#   - that review was submitted at or before SINCE, so it is a review the caller
#     demonstrably wrote or read;
#   - the comment's latest timestamp is no later than one second after that
#     review's submitted_at, so it is the comment as posted with the review and
#     not a later edit.
# Every other inline comment keeps its own latest timestamp: a comment from any
# other account's review, from a merge-account review or pin submitted after
# SINCE, or edited after its review was posted. That last keeps F6: an approver
# who edits its approval's comment afterwards to add a finding is still counted.
#
# The one-second allowance, and why the test is not updated_at == created_at,
# come from every captured inline channel (merge-gate-test-captured-github-
# responses/): a comment posted with its review has a latest timestamp equal to
# the review's submitted_at or one second after it, while its created_at can be
# minutes or hours earlier, because a comment drafted in a pending review keeps
# its draft time as created_at and takes the submission time as updated_at.
# pytorch/pytorch 114309's pinned approval (15:16:51Z) has two such comments,
# created 370 and 155 seconds earlier and updated at 15:16:52Z. Every larger gap
# in the captures, 6 seconds to 15 minutes, is an edit. What the allowance
# accepts: an edit made within one second of posting the review reads as
# unedited.
#
# The comment is re-dated, not dropped, so the SINCE comparison stays the one
# comparison every inline comment goes through.
#
# UNSTABLE REMAINS ON THE ALLOW-LIST (F7) and is deliberately NOT changed here.
# It permits merging with red non-required checks, which may be intended; it was
# not demonstrated as a false pass and changing it is the user's ruling, not this
# rebuild's. Recorded so the next reader knows it was seen and left.
set -u

REPO=nedschorus/nedschorus
MERGE_ACCOUNT=ned-review-merge
TOKEN_FILE=$HOME/.config/nedschorus/$MERGE_ACCOUNT.token

# The first argument follows the prefix; each further argument is a line of its own.
fail()    { printf 'GATE REFUSED (#%s): %s\n' "${PR:-?}" "$1" >&2; shift; [ $# -eq 0 ] || printf '%s\n' "$@" >&2; exit 1; }
cannot()  { printf 'GATE COULD NOT RUN: %s\n' "$1" >&2; shift; [ $# -eq 0 ] || printf '%s\n' "$@" >&2; exit 2; }

RERUN_ONCE_GH="Run the gate again once; if it fails the same way, tell the user this message and gh's error."
JQ_ERROR_ABOVE="Any error jq printed is just above this line."
RERUN_ONCE_JQ="Run the gate again once; if it fails the same way, tell the user this message and jq's error."
TOKEN_ONLY_MERGE_ACCOUNT="The gate reads GitHub only as the merge account, $MERGE_ACCOUNT, and stops rather than read as gh's stored account."
TOKEN_TELL_THE_USER="Tell the user this message: only the user can restore the token."

[ $# -eq 3 ] || cannot "merge-gate.sh takes exactly three arguments and was given $#." \
  "Call it as: scripts/merge-gate.sh <pull request number> <the head commit, all 40 characters> <reviewed-since: the submitted_at of your latest review as the merge account, or of the pin if that is later>"
PR=$1; EXPECTED=$2; SINCE=$3

command -v jq >/dev/null 2>&1 || cannot "jq is not on PATH. Put jq on PATH, then rerun the gate." \
  "If jq is not installed on this machine, tell the user this message."
command -v gh >/dev/null 2>&1 || cannot "gh is not on PATH. Put gh on PATH, then rerun the gate." \
  "If gh is not installed on this machine, tell the user this message."

# An abbreviated or malformed EXPECTED used to refuse as "head moved", naming the
# wrong cause: the head had not moved, the caller had passed a short sha.
FULL_HASH_LINE="Pass the head commit's full hash in lower case, as gh pr view $PR --json headRefOid --jq .headRefOid prints it, then run the gate again."
case "$EXPECTED" in
  *[!0-9a-f]*|"") cannot "expected-head-sha is not a full 40-character hex sha: $EXPECTED" "$FULL_HASH_LINE" ;;
esac
[ ${#EXPECTED} -eq 40 ] || cannot "expected-head-sha is ${#EXPECTED} characters, not 40: $EXPECTED" "$FULL_HASH_LINE"

SINCE_FORM="reviewed-since must be a real time in exactly the form YYYY-MM-DDTHH:MM:SSZ, which GitHub returns: $SINCE"
SINCE_FORM_LINE="Pass the review's submitted_at exactly as GitHub returns it, then run the gate again."
case "$SINCE" in
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z) : ;;
  *) cannot "$SINCE_FORM" "$SINCE_FORM_LINE" ;;
esac
# The right shape can still be no real time, such as month 13.
jq -n --arg since "$SINCE" '$since | fromdateiso8601' >/dev/null 2>&1 || cannot "$SINCE_FORM" "$SINCE_FORM_LINE"

# export's own status masked cat's, so a missing token file was swallowed and
# GH_TOKEN was set to the empty string -- which gh treats as unset, falling back
# to the stored credential, on this Mac the account that AUTHORS these pull
# requests. Read, check, then export.
token=$(cat "$TOKEN_FILE" 2>/dev/null)
[ $? -eq 0 ] || cannot "could not read the merge account's token at $TOKEN_FILE" "$TOKEN_ONLY_MERGE_ACCOUNT" "$TOKEN_TELL_THE_USER"
[ -n "$token" ] || cannot "the token file $TOKEN_FILE is empty" "$TOKEN_ONLY_MERGE_ACCOUNT" "$TOKEN_TELL_THE_USER"
export GH_TOKEN="$token"

state=$(gh pr view "$PR" --repo "$REPO" --json headRefOid,mergeStateStatus,reviewDecision,isDraft)
[ $? -eq 0 ] || cannot "could not read pull request $PR's state; any error gh printed is just above this line." \
  "If gh's error says the pull request was not found, check the number you passed, then run the gate again." \
  "Otherwise run the gate again once; if it fails the same way, tell the user this message and gh's error."

# Unchecked, an unparsable state read the head as empty and refused as "head moved".
STATE_UNPARSABLE="could not parse pull request $PR's state"
head=$(jq -r .headRefOid <<<"$state")             || cannot "$STATE_UNPARSABLE" "$JQ_ERROR_ABOVE" "$RERUN_ONCE_JQ"
merge_state=$(jq -r .mergeStateStatus <<<"$state") || cannot "$STATE_UNPARSABLE" "$JQ_ERROR_ABOVE" "$RERUN_ONCE_JQ"
decision=$(jq -r .reviewDecision <<<"$state")      || cannot "$STATE_UNPARSABLE" "$JQ_ERROR_ABOVE" "$RERUN_ONCE_JQ"
draft=$(jq -r .isDraft <<<"$state")                || cannot "$STATE_UNPARSABLE" "$JQ_ERROR_ABOVE" "$RERUN_ONCE_JQ"

# The authoritative commit is the one the newest approving review was recorded
# against -- never $head, and never $EXPECTED, both of which are what someone
# BELIEVES was reviewed. Paginated, because an approval at index 32 was invisible
# and refused as "no APPROVED review found". Not piped: the exit status must be
# this call's.
reviews_raw=$(gh api "repos/$REPO/pulls/$PR/reviews" --paginate)
[ $? -eq 0 ] || cannot "could not read the reviews of pull request $PR; any error gh printed is just above this line." "$RERUN_ONCE_GH"

approval=$(jq -s -c \
  '[.[][] | select(.state == "APPROVED")]
   | sort_by(.submitted_at) | last // empty' <<<"$reviews_raw")
[ $? -eq 0 ] || cannot "could not parse the review channel" "$JQ_ERROR_ABOVE" "$RERUN_ONCE_JQ"
[ -n "$approval" ] || fail "no APPROVED review found; the gate prints a merge command only for a commit an approving review covers." \
  "If the head commit has not been reviewed yet, commission its review, and run the gate again once the head commit is approved." \
  "If its review found a defect, do not merge until the defect is fixed and the new head commit is approved." \
  "If its review found no defect, approve the head commit as an account other than the pull request's author: the merge account, or mac-claude when the merge account opened the pull request. Then run the gate again."

approved_sha=$(jq -r '.commit_id' <<<"$approval")
approval_id=$(jq -r '.id' <<<"$approval")
approval_at=$(jq -r '.submitted_at' <<<"$approval")
approver=$(jq -r '.user.login' <<<"$approval")
[ -n "$approved_sha" ] && [ "$approved_sha" != "null" ] || fail "the approving review https://github.com/$REPO/pull/$PR#pullrequestreview-$approval_id records no commit_id, so the gate cannot tell which commit it approved." \
  "Do not merge. Tell the user this message."

# "Since now" made every activity check below a no-op (F2). A PENDING review has
# no submitted_at and is left out of the bound.
bound_at=$(jq -s -r --arg merge_account "$MERGE_ACCOUNT" --arg approved "$approval_at" \
  '[$approved] + [.[][] | select(.user.login == $merge_account and .submitted_at != null)
                          | .submitted_at]
   | max_by(fromdateiso8601)' <<<"$reviews_raw")
[ $? -eq 0 ] || cannot "could not parse the review channel" "$JQ_ERROR_ABOVE" "$RERUN_ONCE_JQ"
since_ok=$(jq -n --arg since "$SINCE" --arg bound "$bound_at" \
  '($since | fromdateiso8601) <= ($bound | fromdateiso8601)')
[ $? -eq 0 ] || cannot "could not compare reviewed-since against $bound_at" "$JQ_ERROR_ABOVE" "$RERUN_ONCE_JQ"
[ "$since_ok" = "true" ] || fail "reviewed-since $SINCE is later than $bound_at, the later of the pin and the merge account's own latest review; the gate accepts a reviewed-since only up to a review that records someone read the pull request." \
  "Run the gate again with a reviewed-since no later than $bound_at." \
  "If you have read the pull request after $bound_at, post a review as the merge account saying so, then run the gate again with that review's submitted_at."

[ "$head" = "$EXPECTED" ] || fail "head moved: you passed $EXPECTED, and the head commit is now $head." \
  "If an approving review covers $head, run the gate again with $head as the expected head commit and a reviewed-since from after you read that review." \
  "Otherwise, have $head reviewed and approved, then run the gate again the same way."
# Merging past this would land code no approval covered.
[ "$approved_sha" = "$head" ] || fail "the approval covers $approved_sha but the head commit is now $head." \
  "Have $head reviewed, and approved by an account other than the pull request's author, then run the gate again."
[ "$draft" = "false" ]    || fail "pull request is a draft pull request, which its author has marked as not ready to merge." \
  "Ask the pull request's author whether it is ready, through the pull request's agent-seat or on the pull request." \
  "Until the author marks it ready for review, do not merge it; then run the gate again."
DECISION_REFUSED="reviewDecision is $decision, not APPROVED, so GitHub does not count this pull request as approved."
case "$decision" in
  APPROVED) : ;;
  CHANGES_REQUESTED) fail "$DECISION_REFUSED" \
    "A review requesting changes still stands." \
    "If its findings have been fixed, or answered with a reason that shows they do not hold, dismiss that review with a reason naming the fix or the answer, then run the gate again." \
    "Otherwise, do not merge." ;;
  REVIEW_REQUIRED) fail "$DECISION_REFUSED" \
    "GitHub's rules on main require an approving review it has not counted: get one, then run the gate again." ;;
  *) fail "$DECISION_REFUSED" \
    "Read the pull request on GitHub; if it shows no reason a merge is refused, tell the user this message." ;;
esac
# The merge seat's wrapper retries while the output holds "mergeStateStatus is UNKNOWN":
# the first line of each refusal below must keep that text.
case "$merge_state" in
  CLEAN|UNSTABLE|HAS_HOOKS) : ;;
  UNKNOWN) fail "mergeStateStatus is $merge_state" \
    "UNKNOWN: GitHub has not computed it, or the pull request is already merged or closed. If the pull request is open, run the gate again in a minute; if it still reads UNKNOWN five minutes later, tell the user this message." ;;
  DIRTY) fail "mergeStateStatus is $merge_state" \
    "DIRTY: the branch conflicts with main. Tell the pull request's author; the author clears the conflict as CLAUDE.md says, and the new head commit then needs its own approving review." ;;
  BEHIND) fail "mergeStateStatus is $merge_state" \
    "BEHIND: the branch is behind main. Tell the user this message." ;;
  BLOCKED) fail "mergeStateStatus is $merge_state" \
    "BLOCKED: a branch rule on main blocks the merge, such as a required check that failed or is still running. Read the pull request's checks on GitHub: if one is running, run the gate again when it finishes; if one failed, tell the pull request's author; if you find no cause, tell the user this message." ;;
  *) fail "mergeStateStatus is $merge_state" \
    "For any other value, read the pull request on GitHub; if you find no cause, tell the user this message." ;;
esac

# Both comment channels, by their LATEST timestamp -- NOT by commit_id, which
# GitHub remaps to the new head and which therefore proves nothing about age.
inline_raw=$(gh api "repos/$REPO/pulls/$PR/comments" --paginate)
[ $? -eq 0 ] || cannot "could not read the inline comments of pull request $PR; any error gh printed is just above this line." "$RERUN_ONCE_GH"
issue_raw=$(gh api "repos/$REPO/issues/$PR/comments" --paginate)
[ $? -eq 0 ] || cannot "could not read the issue comments of pull request $PR; any error gh printed is just above this line." "$RERUN_ONCE_GH"

# The reviews whose inline comments are read at the review's own time, by id:
# the pin and the merge account's reviews, submitted at or before SINCE. See the
# header, "WHY AN INLINE COMMENT POSTED WITH A REVIEW THE CALLER WROTE OR READ".
reviews_read_by_caller=$(jq -s -c --arg merge_account "$MERGE_ACCOUNT" --arg since "$SINCE" \
    --argjson approval_id "$approval_id" \
  '[.[][] | select((.id == $approval_id or .user.login == $merge_account)
                   and .submitted_at != null
                   and (.submitted_at | fromdateiso8601) <= ($since | fromdateiso8601))
          | {key: (.id | tostring), value: (.submitted_at | fromdateiso8601)}]
   | from_entries' <<<"$reviews_raw")
[ $? -eq 0 ] || cannot "could not parse the review channel" "$JQ_ERROR_ABOVE" "$RERUN_ONCE_JQ"

inline=$(jq -s --arg since "$SINCE" --argjson reviews_read_by_caller "$reviews_read_by_caller" \
  '[.[][] | ([.created_at, .updated_at] | map(select(. != null)) | max | fromdateiso8601) as $latest
          | $reviews_read_by_caller[.pull_request_review_id | tostring] as $review_at
          | (if $review_at != null and $latest <= $review_at + 1 then $review_at else $latest end) as $posted
          | select($posted
                   > ($since | fromdateiso8601))] | length' <<<"$inline_raw")
[ $? -eq 0 ] || cannot "could not parse the inline comment channel" "$JQ_ERROR_ABOVE" "$RERUN_ONCE_JQ"
issue=$(jq -s --arg since "$SINCE" \
  '[.[][] | select(([.created_at, .updated_at] | map(select(. != null)) | max | fromdateiso8601)
                   > ($since | fromdateiso8601))] | length' <<<"$issue_raw")
[ $? -eq 0 ] || cannot "could not parse the issue comment channel" "$JQ_ERROR_ABOVE" "$RERUN_ONCE_JQ"

# Every account's later reviews count, including the merge account's own
# findings. Only the pinned approval is excluded, by id: counting it would refuse
# every merge it authorises.
reviews=$(jq -s --arg since "$SINCE" --argjson approval_id "$approval_id" \
  '[.[][] | select(.id != $approval_id and (.submitted_at | fromdateiso8601) > ($since | fromdateiso8601))] | length' <<<"$reviews_raw")
[ $? -eq 0 ] || cannot "could not parse the review channel" "$JQ_ERROR_ABOVE" "$RERUN_ONCE_JQ"

NEW_ACTIVITY_READ="Read everything posted or edited since $SINCE: the inline comments, the issue comments and the reviews."
NEW_ACTIVITY_FINDING="If any raises a finding, do not merge until the finding is fixed, or answered with a reason that shows it does not hold; a fix moves the head commit, which then needs its own approving review."
NEW_ACTIVITY_RECORD="When nothing is left open, post a review as the merge account saying what you read, check that nothing was posted between your reading and that review; if something was, read it and repeat from the first line. Then run the gate again with the review's submitted_at as reviewed-since."
[ "$inline" -eq 0 ]  || fail "$inline inline comment(s) posted or edited since $SINCE -- read them before merging" \
  "$NEW_ACTIVITY_READ" "$NEW_ACTIVITY_FINDING" "$NEW_ACTIVITY_RECORD"
[ "$issue" -eq 0 ]   || fail "$issue issue comment(s) posted or edited since $SINCE -- read them before merging" \
  "$NEW_ACTIVITY_READ" "$NEW_ACTIVITY_FINDING" "$NEW_ACTIVITY_RECORD"
[ "$reviews" -eq 0 ] || fail "$reviews review(s) posted or edited since $SINCE -- read them before merging" \
  "$NEW_ACTIVITY_READ" "$NEW_ACTIVITY_FINDING" "$NEW_ACTIVITY_RECORD"

echo "gate passed (#$PR): approved commit $approved_sha by $approver at $approval_at, $decision, $merge_state, no new channel activity since $SINCE"
# The pin (--match-head-commit) is what makes the approval binding: GitHub
# refuses the merge if the head has moved since the approval.
echo "MERGE WITH THIS EXACT COMMAND:"
echo "  gh pr merge $PR --repo $REPO --merge --delete-branch --match-head-commit $approved_sha"
echo "Run that command with GH_TOKEN set to the merge account's token, $TOKEN_FILE, so the merge runs as $MERGE_ACCOUNT."
