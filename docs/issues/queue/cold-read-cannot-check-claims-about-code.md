# The cold read cannot catch a document's false claims about code

> **Naming:** the instrument this describes was called `md-review` when the
> finding was raised and is now the **cold read**. The narrative below keeps
> the contemporary name so its citations resolve; the blind spot is the
> current instrument's, not a retired one's — see the 2026-08-31 update.

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

## Update, 2026-08-31 — the gap widened rather than closed

**The rename did not fix it.** Counting mentions of code, scripts, or claim
verification in the cold-read prompts on main: `defect-hunt.md` **zero**,
`fast-clarify.md` **zero**, `restate.md` one. The prompt whose whole job is
hunting defects never mentions code. The structural property described above
survived the rename intact.

**The accidental safety net is now closed by rule.** This document's second
option — leave code claims to pull-request review and make the reliance
explicit — rested on the pull-request reviewer reading the diff and the
repository, which is how all four findings arrived. The review-scope rule
adopted 2026-08-31 (`CLAUDE.md`) instructs pull-request reviewers to report
**nothing** about prose outside the operative set, silently. A false claim
*about* code, stated in prose, is prose. So the reviewer that caught these
four is now instructed not to raise them.

That does not make the rule wrong: it was measured against a pull request
that drew four review rounds over five hours, where every blocking finding
was about prose and two were errors the previous round's own fix had created.
But it removes this document's cheaper option, leaving the separate
verification pass as the live candidate.

**The rule also depends on this instrument.** Its own words: operative prose
is "taken as given, because it is reviewed BEFORE the pull request by the
instruments built for prose — the cold-read grid and the user." A documented
blind spot in the cold read is therefore a hole in the rule's premise, which
raises this finding's priority rather than retiring it.

**Still live, demonstrated.** On 2026-08-31 the merge-lane seat filed a
diagnosis that `launch-claude-mac:197` hides a stale-launch failure behind
`2>/dev/null || true`. That is the same misdiagnosis this document records at
the fourth finding above, corrected in PR #101: the real cause is that the
catch-up script returns success on every outcome, so `|| true` is redundant
rather than causal. The seat corrected itself after reading this document —
which was on an unmerged branch, not on main where it would have been found
first.
