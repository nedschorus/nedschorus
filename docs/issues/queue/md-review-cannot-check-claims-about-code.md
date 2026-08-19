# md-review cannot catch a document's false claims about code

**Status: recorded, undecided.** Raised 2026-08-19 by the git-infra seat,
from evidence produced the same day. Rides with the queued change that adds
a terminology defect class to the md-review prompts — same file, same pass,
different defect class. Nothing here is built or ruled.

## The evidence

`docs/cross-project/fleet-git-worktree-working-model.md` went to main
through PR #95 after a full md-review pass (eight reviewers across two
runtimes) plus the user's own read. Within minutes of merging, three
findings arrived from `chatgpt-codex-connector`'s inline review on the pull
request. All three were verified against the code and all three were real:

1. **R3** claimed the detached-HEAD write block covered "writes into
   repository checkouts." The check sits inside the guard's seated branch,
   so it reaches only the session's own checkout. (Fixed, PR #97.)
2. **R17** claimed `launch-claude-ubuntu` invoked the supervisor "into a
   checkout nothing pulls." That launcher had freshened the checkout at
   launch since before the document was written. (Fixed, PR #97.)
3. **`clean-worktrees.py`** promised in two docstrings that an untrusted
   vacancy answer keeps the worktree; the code returned "vacant" when lsof
   failed, so `--remove` could delete a worktree holding live work.
   (Fixed with tests, PR #100.)

A fourth, of the same kind, was then found by the same route on the fix
itself: PR #97's replacement text blamed a silent stale launch on the
launchers' `|| true`, when the real cause is that `--reference-pull`
returns success on every outcome. (Fixed, PR #101.)

## Why the review passes could not have caught them

Not reviewer error. `.claude/skills/md-review/prompts/defect-hunt.md` sets
the reviewer's context deliberately: "the checkout's instruction file
(CLAUDE.md / AGENTS.md) if one exists, this file, and whatever it
references by an explicit path." Reviewers do not read the scripts a
document describes. Every one of these four defects is a statement about
code whose falsity is invisible without opening the code, so no defect
class in the current prompt could reach them — the nine classes (a) through
(i) all test the document against itself or against the instruction file.

This is the same property that makes md-review good at what it does. The
minimal context is what forces a document to stand alone for a future agent
with no other knowledge. Widening every reviewer's context to the whole
repository would trade that away.

The gap was closed here only by accident of sequencing: the pull-request
reviewer reads the diff and the repository, so it saw what the md-review
pass structurally could not. That reviewer ran four minutes before the
merge and its inline comments were read only afterwards, so the safety net
was real but nearly missed.

## The decision this needs

Not "add a defect class." A defect class in the existing prompt cannot see
code, so adding one would produce reviewers guessing about scripts they
have not read — worse than silence. The open question is where the check
belongs:

- **A separate verification pass, run only on documents that make claims
  about code**, with one reviewer given the opposite context: the document
  plus every script it names, and one job — does each claim about code
  match the code? This keeps the existing passes minimal-context and adds
  the missing angle rather than diluting it.
- **Or: leave it to pull-request review**, and make the reliance explicit
  rather than accidental — the md-review skill would state that code claims
  are not checked and must be verified by a code-reading reviewer before
  merge. Cheaper, and it matches what actually happened, but it depends on
  a reviewer that is not part of the skill and on the merge seat reading
  inline comments before merging.

Either way, one process change is already in force at the git-infra and
merge-lane seats and needs no decision: inline pull-request comments live
at `gh api repos/<owner>/<repo>/pulls/<n>/comments`, and the reviews list
can look empty of content while findings sit one call away. All four
findings above arrived by that route.

## Scope note

This concerns documents that describe code. A document with no code claims
— a policy record, a decision log — is fully served by the existing passes.
The working model was both, which is why it was exposed.
