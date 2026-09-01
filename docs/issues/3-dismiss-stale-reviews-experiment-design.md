# Experiment design — what enabling `dismiss_stale_reviews` on main would do

Issue: [nedschorus#3](https://github.com/nedschorus/nedschorus/issues/3) ·
Program: `scripts/protection-experiment-dismiss-stale-reviews.py`

## The question this answers

main requires one approving review before anything merges (live since
2026-08-20). A companion setting, `dismiss_stale_reviews`, is off. Off means
an approval keeps covering the branch after further commits are pushed to it,
so commits nobody read can merge under an earlier approval. Turning it on
makes GitHub discard the approval when new commits arrive.

The user's condition for turning it on, verbatim: that we have tested it,
"especially to make sure that it doesn't mess up pushes or other stuff", and
carefully reviewed the change.

## What is measured, and what each result would mean

**Measurement 1 — does a partial PATCH clobber neighbouring settings?**
The setting is changed with a PATCH on
`.../branches/<branch>/protection/required_pull_request_reviews`. If that
endpoint resets fields the caller omits, then sending only
`dismiss_stale_reviews=true` would drop `required_approving_review_count` to a
default — weakening protection while appearing to strengthen it, and doing so
silently, since the call would return success either way.

The measurement applies main-shaped protection to a throwaway branch, records
`required_approving_review_count`, PATCHes naming *only*
`dismiss_stale_reviews`, and reads the count back.

- Count unchanged → the partial form is safe; the explicit-every-field form is
  still preferred, and now by choice rather than by hope.
- Count changed → any change to main must send every field explicitly, and the
  2026-08-20 call's shape was load-bearing rather than incidental.

**Measurement 2 — are ordinary pushes affected?**
Two probes on the throwaway branches: a push to an unprotected feature branch,
expected accepted; and a direct push to the protected branch, expected refused.
Each probe records what was expected and what actually happened, so a
divergence is reported rather than assumed away.

- Feature push accepted and protected push refused → pushes behave as they do
  on main today, and this setting did not change that.
- Anything else → reported as a finding; do not change main.

## What this deliberately does not cover

Observing an approval actually being dismissed requires two GitHub accounts,
because GitHub forbids a pull request's author from approving it, and this
program runs as one. That half is exercised with the merge-lane seat, which
holds `ned-review-merge`.

So a clean run here supports two claims and no others: the PATCH is safe, and
pushes are unaffected. It does not show that dismissal works, and it does not
show that the lane can recover once an approval is dismissed — which is the
operational risk, since with admin enforcement on there is no override.

## Why this is safe to run

Every write targets a throwaway branch the program creates and deletes. It
refuses by name to write to main, and that refusal is applied inside every
mutating call rather than once at the top. It refuses to start if the throwaway
branch already exists, so a leftover from an interrupted run is inspected by a
person rather than silently reused. main's protection is read and never
written; no code path PATCHes, PUTs, or DELETEs anything under main's
protection.

Failures are reported, never silenced: `gh` stderr is captured and printed with
the failing command, per the defect class recorded at
[nedschorus PR #111](https://github.com/nedschorus/nedschorus/pull/111).

## How to judge the result

A pass does not license changing main by itself. It licenses the *first* half:
that the mechanism of the change is understood and reversible. The second half —
what happens to the lane when an approval is dismissed mid-review — is the
merge-lane exercise, and the decision to enable the setting on main is the
user's, not this document's.
