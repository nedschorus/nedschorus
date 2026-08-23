# The PR→main process: a state machine (design of record)

**Status: DRAFT.** First draft, assembled 2026-08-23 by the merge-lane seat.
Nothing is settled by this document. It compiles rulings the user already
made rather than proposing new ones: elements carry the ruling and date they
came from, locked texts are quoted rather than paraphrased, and questions
the sources leave open are listed as open in section 8 with an owner.

## 1.1 What this is

nedschorus moves code to `main` through pull requests. Between "an agent
opened a PR" and "it is on main" sits a process that was, until this cycle,
improvised per merge: who reviews, what a finding means, who fixes it, what
proves the fix, what stops a merge. Improvisation was measured to fail in
repeatable ways — a PR that grew from 372 to 1,933 lines across two fix
rounds (PR #118), findings merged over because nobody re-read a channel
(#95, #125), a hand-written merge gate that printed a warning instead of
stopping (#141).

The user's framing, adopted here as the document's spine: **this is a state
machine.** A pull request occupies one state at a time. Each state has a
meaning (what is true while a PR sits in it, and what must be true to leave
it), an artifact that witnesses it, and a transition fired by a named event.
Findings carry tags, and the tags fire the routing mechanically. Work that
outlives the PR leaves through named side-channels — GitHub issues, queue
notes, knowledge records — rather than being folded into the PR that found
it.

This document compiles that machine from the review-process walk's rulings.
Where it articulates something the sources imply rather than state, it says
so in place.

## 1.2 Provenance: the review-process walk

The design comes from a study and a walk, both machine-local at the time of
writing:

- The study — `review-fix-cycle-analysis/` in the merge-lane seat's
  worktree. Three phases, about eighteen agents, commissioned after PR #118;
  findings F1–F6 and recommendations R1–R9 in
  `phase-3-synthesis.md`.
- The walk — the user going through those findings and recommendations one
  item at a time, 2026-08-21 through 2026-08-23, ruling as he went. The walk
  order and dispositions are recorded in `phase-3-synthesis.md` (16 items)
  and, for the tag scheme, in the sub-walk inside
  `phase-4-research-triage-synthesis.md` (6 items).
- Experiments run during the walk — `phase-5-fixoff-results.md` (specimen
  one: PR #131 round 1, three fixer arms) and
  `phase-6-118-specimen-results.md` (specimen two: #118's original
  commission, with-spec arms against pre-registered no-spec baselines).

Those paths are machine-local to the merge-lane seat today. The walk's item
16 covers the cleanup queue and this material's durable home; until item 16
is processed, a reader off this machine cannot open them.

**What was read to compile this document** (this document obeys the claims
rules it describes): `phase-3-synthesis.md`, `phase-4-research-triage-synthesis.md`,
`phase-5-fixoff-results.md`, and `phase-6-118-specimen-results.md` in full;
`CLAUDE.local.md` (the merge seat's local rules) in full; and, for the
frozen commission template's exact wording, lines 85–204 of
`phase-6-118-specimen-codex-arm.md`. The other phase reports (phase-0
through phase-2, the per-PR findings reports, the grading reports) were not
read for this draft — where a number from them appears here, it is quoted
through `phase-3-synthesis.md`, whose figures were independently
re-verified (`phase-3-verify-synthesis.md`, per its own note).

## 1.3 README lineage

The user ruled on 2026-08-23 (`phase-4-research-triage-synthesis.md`,
"Part-2 ruling and the state-machine frame") that the item-15 PR-mechanism
document is to be written as this state machine, "titled/shaped as the
PR-Main README."

The README comes **later**, after the mechanisms in section 7 are built and
tested. This design may become its skeleton. The knowledge-placement ladder
(section 6) puts a README per major system at rung 2, paired with a thin
skill whose description is the at-need trigger — that is how the PR-Main
README is meant to land, on the `ghi-write` model.

The same ruling records: **a second pass over this whole cluster is
expected; nothing is final-final until it.**

---

# 2. The state machine

## 2.1 States

The user's spine names six: opened → reviewed-with-tagged-findings → fix
rounds → verified → gated → merged. This draft separates UNDER REVIEW from
OPENED, and splits the fix round into commissioned/landed, because their
exit criteria differ. That separation is a drafting articulation, not a
ruling; the second pass may collapse them.

### S1 OPENED

**Meaning.** A branch off `main` carrying one topic has a pull request
against `main`.

**Entry conditions**, from the project's standing lane rules
(`CLAUDE.md`, "How a change reaches main", user-ruled 2026-08-17):
work commits on the seat's own branch; PRs are small and atomic — one
topic's commits cherry-picked onto a fresh branch from `main`; an existing
PR is never extended with a second topic. Agents never push to `main`.

For the merge-lane seat specifically (`CLAUDE.local.md`): the PR is opened
as `nedlern` (plain `gh pr create`, no token exported), because a PR opened
under the merge credential cannot afterwards be approved by it — GitHub
refuses an approving review from a PR's own author, which deadlocked #117
and #118 on 2026-08-20.

**Witness.** The pull request itself.

**Fires the exit.** A reviewer is commissioned.

### S2 UNDER REVIEW

**Meaning.** Reviewers hold the PR. No merge decision is available yet.

**Who reviews** (RULED 2026-08-22, walk item 12): a **Claude + Codex
reviewer pair on every substantive PR** — the `chatgpt-codex-connector` bot
is welcome but **never gated on**. Measured basis (F1, and the direct-answer
section of `phase-3-synthesis.md`): accuracy ties between the runtimes
(codex bot 11-for-11 real; graded Claude findings real), but coverage barely
overlaps — on the same two commits the Claude verifiers returned 16 and 13
findings where Codex returned 1 and 1, each catching real defects the other
missed. "Both, as a pair, is the measured answer; the pair paid for itself
every time it ran."

**Reviewer lifetime** (measured 2026-08-23,
`phase-4-research-triage-synthesis.md`): one reviewer agent reused across
three PRs and seven verification rounds died of context exhaustion at
write-up ("prompt too long", unresumable). Standing rule for the reviewer
procedure: **fresh reviewer per PR**; resume the same reviewer only within
one PR's fix rounds, because fixture continuity within a PR is valuable
(verification re-runs the exact failing cases); budget its final round
before its context runs out.

**The bot cannot be waited on deterministically.** Codex's GitHub
integration creates no check run and no commit status even on PRs it does
review (verified on the head commits of #99, #100, #101, #102:
`check_runs=0`, combined status `pending` with zero contexts). A required
status check from it **cannot be built** — `CLAUDE.local.md` records this as
a recommendation not to repeat. And it skips silently: of eight PRs opened
2026-08-19 it reviewed five and skipped three, two of them alive 9 and 17
minutes with no trace of any kind. So an empty inline channel has two
indistinguishable meanings — reviewed-and-found-nothing, or never ran. That
indistinguishability is itself the knowledge record (section 6.3).

**Fires the exit.** A review is posted to a GitHub channel.

### S3 REVIEWED (findings tagged and routed)

**Meaning.** A review exists on a channel any seat can read, its findings
carry tags, and each finding has a route.

**Exit criteria — what a review must carry:**

1. **It lands on a GitHub channel** (R8). #118's two rounds and both Codex
   reviews were invisible to GitHub; #117's off-channel round needed the
   timeline API to detect. This is also the precondition for point-don't-paste
   (section 3.4): a fixer can only read the review at its source if the
   source is readable.
2. **It names the head SHA it covers** (staleness rule part 1, settled
   2026-08-23) — already universal practice, now load-bearing, because the
   merge gate compares the latest approval's `commit_id` against current
   head.
3. **Every seat-authored finding carries the tag line** (section 2.2).
4. **The review body carries its ran-vs-read account** (section 3.3). Zero
   findings never means zero record: the review body stays mandatory
   (RULED 2026-08-23, sub-walk item 1).
5. **Named shapes only** (RULED 2026-08-23, sub-walk item 1): a
   seat-authored PR comment must be a tagged finding, a question, an author
   fix-report, or a merge/closing note. Anything else — praise, summaries —
   is refused by the write-time hook (section 7.3). Evidence note carried
   with the ruling: the three measured missed-comment incidents (#95, #98,
   #125) were all inline-channel-at-merge-time and are cured by the timing
   and gate rules, not by this rule, which targets noise.

**Two review channels, fetched separately** (`CLAUDE.local.md`, recorded
because it went wrong on #95):

    gh pr view <n> --json reviews                    # review-level: APPROVED / CHANGES_REQUESTED / COMMENTED
    gh api repos/<owner>/<repo>/pulls/<n>/comments   # INLINE comments on specific lines

A review can show as a bare `COMMENTED` with every substantive point living
only in the inline set.

**Fires the exit.** The routing table (2.3) is applied to every finding.
If any route is `fix-now`, the PR moves to S4. If none is, it moves toward
S7 GATED. (That second branch is derived from the routing table's blocking
semantics — "merge blocks on it" applies to fix-now findings only — rather
than stated as a transition in the sources.)

### S4 FIX ROUND n — COMMISSIONED

**Meaning.** A fixer holds the PR with an open commission.

**Who fixes** (RULED 2026-08-23, walk item 13, five parts): **resume the
author by default**; fresh Claude and fresh Codex are approved substitutes
under the standing rules. Basis: the fix-off (specimen one, PR #131 round 1)
measured all three arms at 8/8 on assigned findings, and the user's
anchoring worry did not materialize — the author defended nothing and its
single round was no worse than either fresh arm.

**What the commission carries:**

- **Three inputs — spec, code, findings** (R7a; section 3.5).
- **The review by pointer, never restated** (R1 point-don't-paste;
  section 3.4).
- **The claims specification** verbatim (section 3.1).
- **The depth rule** verbatim, with the depth *not* pre-picked
  (section 3.2).
- **The widened-matcher rule** (section 3.2).
- **For a Codex fixer, the rider** (section 4.2).
- **On rungs 2 and 3, an appended EVIDENCE section** and nothing else —
  the template is frozen; rounds differ only in what fixers *know*, never in
  what they are *told to do* (section 5).

**Fires the exit.** The fixer pushes responding commits and reports.

### S5 FIX ROUND n — LANDED

**Meaning.** Commits answering the findings are on the branch; nothing yet
proves they work.

**Fires the exit.** Verification runs (S6) — or, on failure, the escalation
ladder advances (section 5).

### S6 VERIFIED

**Meaning.** The original reviewer's own recipes have been re-run against
the fixed code, and the findings' failing conditions are gone.

**This is the load-bearing state.** Both specimens converged on it:

> **the binding constraint is fix-round verification, not fixer choice.**
> The reviewer-rerun verification caught this class on the author's round;
> the identical instrument caught it on both fresh arms. No fixer
> configuration removes the need; any of the three is workable WITH it.
> (`phase-5-fixoff-results.md`)

The finding behind that sentence: all three fixers — in-context author,
fresh Claude, fresh Codex — broke or re-broke the *same* unassigned class,
each via its own fix, each differently, and all three left the same
pre-existing P1 alone. Fixer identity changed the *style* of the introduced
defect, not its existence or location. Specimen two agreed: "every
introduced defect and every survivor was caught only by the grading
instrument, in both specimens, across all five arms."

**Ruled 2026-08-23** (walk item 13, part 3): reviewer-recipe verification of
every fix round is **non-negotiable**.

**Fires the exit.** No fix-now finding remains open; an approving review is
recorded.

### S7 GATED

**Meaning.** The PR is merge-eligible on content and is now being checked
mechanically for freshness and completeness.

**What the gate checks** (compiled from the staleness rule, the two
gate-regression specimens, and `CLAUDE.local.md`):

1. **Approval freshness** — the latest approval's `commit_id` equals current
   head; refuse otherwise. One API field against another.
2. **Channel digest unchanged** — a hash of `id`+`updated_at` across all
   three channels, taken at read time and re-taken at merge time. Any change
   between read and merge forces a re-read. **Not** comment counts, and
   **not** `commit_id`: #141 demonstrated that GitHub remaps an old inline
   comment's `commit_id` to the new head, so `commit_id` is not evidence of
   comment newness — `created_at` is.
3. **Age since last push** — do not merge a PR younger than about three
   minutes, measured from its most recent push, since an update restarts the
   bot reviewer. The rule is timing, not diligence: #98's inline channel was
   read and came back genuinely empty; Codex posted three more findings 62
   seconds before the merge, one a P1 causing silent data loss.
4. **A posted review exists**, with the body discipline of section 3.3, and
   it says whether an independent reviewer was used or whether the seat
   reviewed alone. GitHub's `required_pull_request_reviews` (live
   2026-08-20, 1 approving review, admins included) checks that a review
   exists, not that it says anything.
5. **The tag validator passes** on seat-authored findings — malformed tags
   silently misroute work, so the gate bounces them to the reviewer
   (section 7.2).

**The gate must abort, not narrate.** Two specimens of the same regression:
a script that printed the inline count and proceeded on `&&` merged #125
over two P2s (2026-08-22); a hand-written variant on #141 gated the head SHA
but only *printed* the comment count (2026-08-23), harmless by luck. The
recorded conclusion: **a fresh hand-written gate per merge WILL regress** —
the committed `pr-state` gate is the fix (section 7.1). Batch merges: check
one PR, merge that PR, only then check the next — never pre-compose a chain.

**Fires the exit.** All gate checks pass; the merge call runs as
`ned-review-merge`.

### S8 MERGED

**Meaning.** The change is on `main`.

**Consequences that fire here:** a GHI opened for a `loses-work-or-data`
finding closes on the merge of its fix PR; the corresponding plate task
leaves by "finished" (section 6.4).

## 2.2 The tags

Per finding, the **reviewer** supplies four cheap tags beside the condition
and location it already writes. The values and their order below are
verbatim from `phase-4-research-triage-synthesis.md`; the formatting (tag
names bolded, values in code style) is this document's:

- **consequence if it fires:** `loses-work-or-data` | `wrong-behavior-in-operation`
  | `misleads-readers` (false prose/docs) | `polish`
- **introduced-by:** `this-change` | `this-fix-round` | `pre-existing` | `external`
- **evidence:** `reproduced` | `reasoned`
- **how-to-find:** the search that finds every instance

### `evidence` and `how-to-find` — renamed and re-shaped (user-ruled 2026-08-23)

The two tags above were `basis: reproduced | judged` and `scope: isolated |
pattern` until the user walked them. Both names were abstract nouns that did
not say what they held, and one of them held the wrong thing.

**`evidence: reproduced | reasoned`.** The vaguer half was the value, not the
name. `reproduced` says what the reviewer did; `judged` named a verdict rather
than a method, which is why the scheme needed a standing note explaining that
judged is not weak. `reasoned` is symmetric with `reproduced` — both say what
the reviewer did — and the note largely stops being necessary. Candidates
considered and set aside: `Verification-Method`, which promises to name *which*
method when the tag is binary, and `Evaluation-Basis`, which stacks two
abstract nouns and still does not say what is evaluated.

**`how-to-find`, replacing `scope`.** `pattern` told the fixer that other
sites existed without saying where, so the fixer re-ran the search the reviewer
had already run. The field now carries the search itself, which makes
`isolated | pattern` derivable and removes a vocabulary item rather than adding
one. `location` and `sites` were both considered and rejected for the same
reason: every finding already cites its own `path:line`, so a field named for
locations promises locations and delivers a method.

What it holds, in four shapes and one rule:

- one command → the command
- several commands → all of them
- a command plus a judgement → the command **and** what was discarded, so the
  fixer applies the same filter instead of trusting a list
- no command possible → a **prompt**, which in this fleet is as runnable as a
  shell command, and which survives rewording where a grep does not: the
  five-tool defect of 2026-08-23 shared no string at all, so no grep would ever
  have found it

**One invariant across every shape: it is the search the reviewer actually
ran**, not one composed for someone else. Without that the field acquires the
defect it exists to prevent, in a new costume — a plausible-looking grep or
prompt that was never executed reads exactly like a real one.

**The field is mandatory, including for a single-instance finding.** That case
is what justifies it: `how-to-find: grep -rn "X" scripts/ — returns only this
site` records that the reviewer looked and found one. A missing field records
that nobody searched. Today those two are indistinguishable, which is why
`isolated` was never trustworthy — it could mean "one place" or "I did not
check."

### Counts in durable text — two kinds, opposite treatment (user-ruled 2026-08-23)

The user observed that reviews kept being stopped by bad counts and that most
of the counts looked meaningless. Four separate counts in this project's
durable text went stale or proved wrong within hours on 2026-08-23: a
32-of-32 that now reads 35; a 73-of-98 that measures 77-of-102; a commit
message claiming "21/21, 20/20 before" that measures 37/37 after its own
rebase; and a "3,712 characters to 1,029" that became 1,173 when a fix round
added 144 characters back — its pull request body edited nineteen seconds
after the push that invalidated it.

**Bookkeeping counts** — test-case totals, commit counts, character counts.
Nobody decides anything from them. They are a proxy for *work happened*, the
cheapest thing that resembles evidence, and they rot on contact. Cut them and
name what was added instead.

**Measurement counts** — "73 of 98 sessions carry the memory block", "32 of 32
merges carry an approving review". Here the number *is* the finding. These
stay, but pinned: the command that produced it and the moment it was taken.
That stamp is what kept the 32-of-32 claim honest when it became 35.

**The test that separates them:** would anyone decide differently if the number
were different? If no, it is bookkeeping — cut it.

Commissioning texts are implicated in producing these, since they ask for
evidence and a count is the easiest thing that resembles evidence. That belongs
to walk item 15's pass over the commission templates.

### When a tag is wrong, and when readers disagree (user-ruled 2026-08-23)

Four failure modes were walked. Two already have a mechanical answer and are
recorded in §7.2 and §7.3: a **malformed** tag line is refused by the
write-time hook, and a **missing** one is caught by the pre-merge gate, which
the hook cannot do because a comment with no tag line is indistinguishable
from an ordinary comment. The other two need judgement and are ruled here.

**A tag that is well-formed and wrong.** No validator can catch this by
construction — `consequence: polish` on a finding that actually loses data
parses perfectly. What makes it worse than an ordinary mis-set field is that
**tags are routing decisions, so a wrong tag has already misrouted by the time
anyone notices**. A finding tagged `polish` is merged over; correcting the tag
afterwards does not unmerge it.

RULED: **the merge seat checks the tags rather than accepting them.** It is
the last reader before the routing takes effect, so it is the only point at
which a wrong tag is still recoverable, and it is the same posture the seat
already takes toward every other claim in a pull request.

**Disagreement between readers.** One case was already ruled and stands: a
finding the fixer cannot reproduce goes back to the reviewer as a question,
not a fix. RULED for the unresolved case — reviewer versus merge seat: **the
merge seat decides, because it owns the merge, and the disagreement is
recorded on the pull request rather than silently overridden.** Both shapes
occurred on 2026-08-23 and are on the record: a fixer declining to fix and
giving three reasons the merge seat agreed with, and a finding raised against
text the merge seat itself had written and committed, which it accepted and
recorded.

**Provenance worth keeping for the second pass:** the user approved both of
these while saying plainly that he had no strong view of them — "nasty
problems, I have no great insight so approved." They are therefore the two
rulings in this cluster most worth re-examining when better specimens exist,
and they should not be cited as settled doctrine with the same weight as
rulings he argued for.

**Why four and not more:** each is answerable in seconds by a reviewer who
just proved the finding; none requires estimating someone else's work.
Remedy size sits with the fixer — effort estimation by reviewers appears in
no review-time scheme the research found.

**consequence** — processed 2026-08-23, sub-walk item 2, accepted as
presented: four values, worse-wins boundary rule.

**introduced-by = external** — added by the user 2026-08-23. Verbatim
definition and constraints:

> the wrong behavior originates outside this repository's code, prompts, and
> configuration — tmux semantics, harness behavior, the codex sandbox, bot
> skips. Never routes fix-now by itself: it routes to a workaround decision
> — coping needed by this PR becomes its own this-change finding beside it —
> and always leaves a durable record. Guard: our code mishandling an
> external quirk is still ours, tagged normally; external is only for
> behavior with no code of ours implicated.

Measured basis: reviewers made this distinction in prose all night —
"environmental, not a regression" — and it prevented false blocking.

**REQUIRED BODY of an external finding** (user, 2026-08-23) — the tag is a
causal claim and obeys the claims rules:

> (1) WHERE, the externality named as specifically as evidence allows,
> version pinned when known; (2) WHY THERE — basis=reproduced means
> demonstrated IN ISOLATION with our code out of the loop, anything less is
> basis=judged and stated as inference; (3) DEPTH — one of: root cause
> confirmed / proximate only, searched deeper and stopped at X / did not
> search deeper.

**The fifth, conditional tag position** (user-ruled 2026-08-23). When
`introduced-by = pre-existing`, a fifth tag value is **REQUIRED** — the
validator enforces presence and vocabulary (the write-time hook refuses
otherwise; "a required statement without a mechanical check is just a
hope"):

- `triggers-existing-problem` — this PR's changes make the pre-existing
  defect reachable, likely, or worse. Specimen: #134's box route to the
  dormant ubuntu quoting defect. **The TRIGGERING blocks this PR; the
  underlying defect stays queue-routed.**
- `non-triggering` — neither worsens nor newly exposes it; pure queue
  routing, the PR merges.

The pair was renamed by the user from `existing-problem-unchanged` on
2026-08-23, so that it reads as `triggers-existing-problem | non-triggering`
with the second self-defining against the first. "Arming" was rejected as
opaque. Both terms were grep-checked clean at ruling time.

**Remedy depth is the fixer's, not the reviewer's.** The fixer chooses
site / mechanism / recommend-redesign per the locked menu (section 3.2) —
"chosen by the party with the code open." Commissions never pre-pick it.
`phase-4-research-triage-synthesis.md` calls this "this scheme's fifth
axis," which collides with "the fifth, conditional tag position" above; see
section 8 for the naming question.

**Original to this fleet:** nothing in the fifteen-plus schemes the two
researchers surveyed classifies the reviewer's *claim*. The
`basis: reproduced | judged` field is an original contribution — "keep it."

**What the tag scheme replaced:** the single serious/non-serious line
proposed as R4's operational rule. The user identified during walk item 9
that remedy-size, consequence-severity, detectability, scope, and
already-solved-elsewhere are independent axes no scalar bridges; dual
research (Codex + Claude, independent) into how leading organizations triage
PR-review findings was commissioned, and the multi-axis scheme is its
result. What that literature settles, both researchers independently:
severity is an INPUT, not the decision; the best modern schemes are
OUTCOME-valued (SSVC classifies straight into Defer / Scheduled /
Out-of-cycle / Immediate — the classification IS the routing); review-time
schemes and tracker schemes carry nearly disjoint axes with no documented
handoff, which is the gap this lane lives in; and Google's documented
practice routes by PROVENANCE — problems the change introduced are fixed
pre-submit, surrounding pre-existing problems become filed bugs.

## 2.3 Tag-fired routing

Routing is outcome-valued and mechanical from the tags. Table verbatim from
`phase-4-research-triage-synthesis.md`:

| tags | route |
|---|---|
| this-change or this-fix-round, consequence >= wrong-behavior | fix-now (this round; merge blocks on it) |
| this-change, misleads-readers | fix-now (prose fixes are cheap; claims rules apply) |
| pre-existing, consequence >= wrong-behavior | its own queue item -> user decides (deliberate #98->#102, never a rider) |
| polish, any provenance | recorded in the review; next touch of the file |
| basis=judged and the fixer cannot reproduce | back to reviewer as a question, not a fix |
| spec-vs-code divergence, any | question routed to the user (R7a) |
| scope=pattern | the finding names it; the fixer's mechanism-vs-site choice answers it |

**Blocking semantics unchanged:** `CHANGES_REQUESTED` stands while any
fix-now is open — GitHub-native, no new machinery.

**Superseding row** (user-ruled 2026-08-23, "Routing revision: confirmed
bugs become agent-filed GHIs"): the `pre-existing → queue item` row is
superseded for the confirmed-bug class — `basis=reproduced` AND
`consequence >= wrong-behavior-in-operation` now routes to an agent-filed
GitHub issue. See section 6.1.

**Riding on top of the table**, for the merge seat, in force now
(`CLAUDE.local.md`, 2026-08-23): a pre-existing or external finding never
blocks the PR that surfaced it; what can block is this PR *triggering* it.

---

# 3. The locked texts

These are quoted verbatim because they are meant to be used verbatim. Each
carries the date it locked and the party who ruled it.

## 3.1 Fixer claims specification — LOCKED (user-ruled 2026-08-22)

From `phase-3-synthesis.md`, under R9. It goes verbatim into the standing
fixer procedure and every fix commission. It was iterated with the user
during the results walk; a zero-context reader (a fresh Sonnet agent, per
the walk-me-through rule landed in PR #124) vetted the draft and its
stumbles were fixed or ruled on before locking.

> **What to write re your change** (commit message and PR body alike):
> 1. What changed: the defect's failing condition, and the change that
>    removes it. A sentence or two per defect.
> 2. Why it mattered: the consequence — only where it isn't obvious from the
>    condition.
> 3. What you ran: the exact test or check you used to verify the fix, and
>    its output or results, or the test file plus the command that runs it.
>    A check you did not run is not written.
>
> **Do not write** — as these may cause confusion, tail chasing or other
> unwanted byproducts:
> - Universal statements ("every probe…", "X can never happen"). Instead
>   simply name the test you used.
> - Coverage claims ("verified on…", "checked all…") beyond the exact
>   commands or inputs and their results.
> - References to files or behavior whose latest version you did not
>   carefully examine this session.
> - Narrative justification — why the approach is good. The diff argues for
>   itself.
>
> If a statement you believe matters can not be fully verified, write it as
> a question in the PR instead of a claim in the commit. If you accidentally
> find design problems or defects outside the scope and changes of this PR,
> file each as a small zero-context note in the ask-the-user queue
> (`docs/issues/queue/`), landed as its own small PR — do not fold it into
> this one.

**Division of the two ending sentences** (user-ruled): related but not fully
verifiable → question in the PR; unrelated accidental discovery → queue note
in its own small PR. GitHub issues stay post-sign-off; the queue directories
are the ask-the-user path, and the built-in session task list was considered
and rejected (session-scoped, dies at recycle, invisible to other seats).

**Dated supersession, not yet written into the locked text (2026-08-23).**
The routing revision (section 6.1) supersedes the queue-note route for one
class: a finding that is `basis=reproduced` and `consequence >=
wrong-behavior-in-operation` is now eligible for an agent-filed GHI. The
locked text above still says "file each as a small zero-context note in the
ask-the-user queue," and the item-3 disposition still records "no GHI filing
by fixers." How the locked text is amended to carry the exception — and
whether the fixer or only the reviewer files — is OPEN (section 8).

**Measured basis for having a specification at all.** The broad ask was the
cheap failure (user, 2026-08-21: "we asked too broadly, too ambiguously").
"Write no claim you have not run" cut the false-claim rate about fourfold in
#118's round 2. Codex under the identical broad ask wrote 117 words to
Claude's 732, so the specification treats a Claude-specific disposition. A
narrow ask alone was not sufficient — the "brief comments only where not
obvious" ask still returned 41 claims.

**Measured effect once it existed** (specimen two, `phase-6-118-specimen-results.md`):
on the exact commission that produced the historical spiral, with-spec
Claude went from 4 false statements to 0 and from 1 introduced defect to 0,
and added fail-first tests. The same document's caution: the claims spec
"worked but is not armor" — fresh Claude still shipped 2 false comment
statements under it in specimen one, and fresh Codex under the same spec
shipped zero false claims but hid two structural trades.

## 3.2 The depth menu, and the widened-matcher rule — the frozen template's text

The commission template is frozen (R9 text; revising it is a user decision
with a zero-context read). This is the depth rule as it was actually fed to
the specimen-two arms, from `phase-6-118-specimen-codex-arm.md` §3, where
the fix-depth rule is recorded as verbatim template text:

> **How deep to fix**
>
> For each finding — or cluster sharing one cause — choose the fix's depth
> yourself, and say which you chose and why, one sentence each, in the PR
> body: Smallest correct change — removes the finding's failing condition at
> its site; the default for typos, oversights, isolated defects. Generalize
> the mechanism — when several findings are instances of one cause inside
> the footprint, fix the cause once, where it lives. Recommend redesign —
> when the right fix would rewrite beyond the footprint or replace the
> design of the thing being fixed: make the case in the PR; recommending
> does not suspend the fixes. The footprint: the files the findings name,
> plus the code their cause actually lives in. A commission names findings
> and must not pre-pick the depth.
>
> When a fix widens a matcher or filter, enumerate what else now matches,
> and test one legitimate representative.

**Where the depth rule came from.** R2 originally said "a fix commission
asks for the smallest correct change; restructuring is recommended, not
executed" (refined per user direction 2026-08-21), on the basis that the
structural instruction — the supervisor's own "fix the root cause once,
structurally, not site by site" — was the largest line-count event in the
studied range (#92–#118), producing a 1,618-line round and a guard its own
verifier proved decorative. At walk item 9 (2026-08-22) it was reshaped into
the menu above: three depths, **the fixer chooses**, commissions never
pre-pick, footprint defined, pre-pick asymmetry encoded; a zero-context read
was done.

**Where the widened-matcher rule came from** (`phase-5-fixoff-results.md`,
analyzed 2026-08-22, user-prompted). All three fix-off arms broke the same
unassigned class because the commission pointed them at the trap: the
finding's framing was one-sided ("the filter recognizes too few empty
shapes; widen it"), and the missing invariant existed in no input — not the
spec, not the finding, not the code. Each fixer faithfully widened the net;
each net swept a legitimate population, in that fixer's style. The rule was
adopted into the standing fixer procedure draft as the process fix.

**Measured engagement:** in specimen two the Codex arm engaged the
widened-matcher rule unprompted — it carved out and tested the post-reboot
case, the fix-off's trap class, pre-empted by the new rule.

**Naming divergence, unresolved:** the same three depths are written
`smallest / generalize / recommend-redesign` in `phase-3-synthesis.md` item
9 and `site / mechanism / recommend-redesign` in
`phase-4-research-triage-synthesis.md`; the fix-off (specimen one)
commission rendered the rule as a single sentence with slightly different
wording than the template above. See section 8.

## 3.3 Reviewer and approver claims discipline — RULED 2026-08-22

Walk item 10, verbatim disposition from `phase-3-synthesis.md`:

> R3 claim hygiene — fixer half locked at item 3; extension to reviewers and
> approvers RULED 2026-08-22: review bodies and approval notes carry ran
> (exact, timestamped where it decays) / read / taken-attributed, and
> nothing else asserted; lands in the standing reviewer procedure and this
> seat's merge discipline at item 15, each with a zero-context read.

That sentence is the whole of the ruled text today. **The full wording is
not yet written** — it lands at walk item 15, sub-steps (2) the reviewer
procedure and (6) this seat's merge-review discipline amendment, each with a
zero-context read before the user sees it.

**The rule this extends** (R3, strengthened per user direction 2026-08-21 to
grounded AND verifiable): "A claim is written only with its verification
attached: the command and observed output, or a test — and a test counts
only if something runs it (#118's 65 tests are wired to nothing). No
universals, no coverage claims, no unopened cross-references." Basis is F3:
every false statement in the corpus lacked an attached verification
procedure; claims that carried one graded real.

**Why approvers and not only writers** (F3): the same failure appears at
every station — writer, approver, supervisor, archaeologist. The #109
approval claimed an item-by-item confirmation that never happened; the #98
approval said "all three channels checked … all empty" 59 seconds after the
findings landed; #113's merge note said a point was "carried to issue #45"
when nothing was carried.

**Already in force at the merge seat** (`CLAUDE.local.md`): the review body
says what was checked and what was verified against the repository rather
than taken from the PR's own description, and states plainly whether an
independent reviewer was used or whether the seat reviewed alone — "a
degraded review that does not announce its degradation is worse than a
missing one." When a PR carries no Codex review, the approving review says
the seat reviewed alone.

## 3.4 Point, don't paste — R1, ACCEPTED as ruled 2026-08-22

R1 verbatim from `phase-3-synthesis.md`:

> R1. **Point, don't paste** (strengthened during the walk, user terminology
> adopted: author writes the PR, fixer works the fix round). The fixer reads
> the review at its source; a commission names the review ("fix the findings
> in the review on PR #N, smallest correct changes") and never restates it.
> Requires R8 (every review lands on a readable channel) — the #118
> middleman existed because the Claude verifier's findings lived only in its
> private return to the supervisor. Distinct from the rejected
> review-reviewer gate: no layer judges the review; one layer (the
> supervisor's retelling) is removed. Measured harm prevented: F5.

Walk item 8's disposition, verbatim:

> R1 verbatim forwarding → upgraded to point-don't-paste. — processed
> 2026-08-22 → ACCEPTED as ruled: commissions name the review and scope,
> never restate findings; fixer reads the source; binds all commissioning
> seats; lands verbatim in the standing procedures (item 15).

**The measured harm (F5), because the rule reads as bureaucracy without
it.** A verbatim comparison of what reviewers wrote against what the
supervisor forwarded to writers: every claim carried; nearly every
mitigating qualifier dropped ("low blast radius", "indicated, not
demonstrated", "the live seat is not destroyed"). One item the reviewer
filed as "intentional and defensible" arrived promoted to a numbered
"footgun" finding. Four findings became five defects. The largest additions
to any commission were the supervisor's own.

**Note on R1's example text:** the parenthetical example commission above
ends "smallest correct changes," which pre-picks a depth — the practice item
9 forbade later the same day. The example wording is stale against the depth
menu; which text wins where they touch is OPEN (section 8).

## 3.5 Three-input commissions — R7a

R7a verbatim from `phase-3-synthesis.md` (added during the walk, the user's
hypothesis, data-confirmed):

> **The fixer's inputs are three: spec, code, findings.** Every fix
> commission carries the requirement's pointer (the issue) alongside the PR
> and the review; reviewers receive the same pointer with a standing duty to
> raise code-vs-spec divergence as a question routed to the user. Basis:
> neither #118 commission carried issue #116, and the fresh fixers' claim
> explosion is largely improvised specification — docstring contracts and
> exit-code tables written by agents who were never shown what correct
> meant; Codex handled the same gap by silent assumption (zero declared
> limits). A reviewer without the spec can only verify internal consistency.

**How the frozen template renders it** — the three inputs appear as three
named sections of the commission (`phase-6-118-specimen-codex-arm.md` §3,
specimen values elided here):

> **Your three inputs**
>
> **(1) The spec.** The issue this branch implements, copied to a local file
> — read it in full: `<path>` … it is the only statement of what these
> scripts are for.
>
> **(2) The code**, as it stands at `<sha>`: `<paths>`
>
> **(3) The findings.** A review of that code raised `<n>` defects.
> Verbatim: `<the findings, unaltered>`

**Measured support** (`phase-5-fixoff-results.md`, held lightly at one
specimen): "R7a (spec as third input) is supported: neither fresh arm
produced a #118-style improvised-spec explosion; both stayed scoped."
Specimen two strengthened it: with-spec Claude took the historical
commission to 0 false statements and 0 introduced defects. Confound stated
in the source: with-spec arms also carried the new process texts, so deltas
attribute to spec+process jointly.

**The template is frozen; only EVIDENCE varies** (ladder refinement, user +
merge seat 2026-08-22): "Rounds differ only in the appended EVIDENCE section
— failure shapes per arm, divergence map, RCA. Change what fixers know,
never what they're told to do."

---

# 4. The roles

## 4.1 Author

Writes the PR. (Terminology adopted from the user during walk item 6,
2026-08-22: **author** writes the PR, **fixer** works the fix round.)

The author's claims obey the same specification as the fixer's — R3 binds
"writers and reviewers alike," and the locked text in 3.1 governs "commit
message and PR body alike."

The author is also the default fixer for its own PR (4.2).

## 4.2 Fixer

Works a fix round. Default: **resume the author** (RULED 2026-08-23).
Approved substitutes under the standing rules: fresh Claude, fresh Codex.

**What the fixer owns that nobody else does:** the depth choice
(section 3.2), stated with its one-sentence reason in the PR body.

**Standing duties carried in the commission:** the claims specification; the
widened-matcher rule; question-vs-claim routing for unverifiable statements;
out-of-scope discoveries routed out of the PR (section 6.2, as revised by
6.1).

**The Codex-fixer rider** (R6 rider, extended 2026-08-22 by specimen two).
Original form from `phase-5-fixoff-results.md`: "the commission must demand
that any mechanism replacement be stated in the PR body ("what did you
rebuild and what does it cost") — the silent-trade failure is its
signature." Extended form from `phase-6-118-specimen-results.md`: "state
every mechanism replacement, carve-out, and gating condition with what it
excludes." Ruled into item 13 on 2026-08-23 as "the extended Codex rider
(mechanism replacements, carve-outs, gating conditions all stated with what
they exclude)."

Why the rider exists rather than a general preference for one runtime: the
two runtimes fail differently. **Claude misstates affirmatively (universals
it didn't run); Codex misstates by omission (limits it doesn't declare)**
(F6). Codex introduced the worst defect in both specimens — the
silent-redesign P1 in specimen one, the carve-out regression that falsifies
its own docstring in specimen two — and in both cases the defect existed
because a trade was never stated for review.

## 4.3 Reviewer

Fresh per PR; resumed only within one PR's fix rounds (2.2 lifetime note).
A Claude + Codex pair on every substantive PR; the bot welcome, never gated
on.

**Duties:** name the failing condition per finding; supply the four tags
(plus the conditional fifth); post to a GitHub channel naming the head SHA;
carry the ran / read / taken-attributed account in the body; raise
code-vs-spec divergence as a question routed to the user (R7a); write no
finding the claims rules would forbid as a claim.

**Delivery format** is covered by the `pull-request-review-write` skill —
one finding per comment, each naming the condition under which the wrong
thing happens. `phase-3-synthesis.md` records it as "the first piece" of R9,
with a probe marker still to strip.

**The standing reviewer procedure is unwritten** — item 15 sub-step 2. Three
inputs are registered for it, none yet merged into a text:

- **This project's own review rules** — condition-naming, ran-vs-read.
- **Codex CLI's built-in review procedure.** Codex CLI is open source, so
  its review prompt can be read from source and used as the foundation
  (user, 2026-08-21): "take what earned its measured 11-for-11 record and
  merge it with this project's own review rules."
- **A Gemini-authored code-review skill text, supplied by the user**
  (registered 2026-08-22, `phase-5-fixoff-results.md`): its
  verify-then-discard step and empty-response-over-noise rule "align with
  measured results"; it "lacks name-the-failing-condition, ran-vs-read
  disclosure, and the claims rules." Recorded as a **usable skeleton** for
  the reviewer procedure, not as the procedure.

Measured support for having explicit format rules at all: the explicit
format rules handed to the #118 reviewer throttled it correctly — in its own
words, "it worked against me."

**Reviewer volume is the throttle, and it is partly ours** (F4). On the same
two commits the Claude verifiers returned 16 and 13 findings to Codex's 1
and 1 — but the Claude verifiers had been handed escalating ranked questions
by the supervisor, questions the first pair was never asked, while Codex ran
the same fixed procedure both times. "One finding becomes one commission
becomes one fix's worth of new claims; reviewer volume, however honest, is
the accelerator." This is why the triage tags route rather than merely rank:
not every real finding is a fix-now.

**Do not build the review-reviewer gate** (R5, accepted at walk item 2,
2026-08-21). Basis F1: across roughly 39 graded findings on ten PRs, one was
false, and the reviewer that filed it retracted it four minutes later,
unprompted. The proposed gate would check about 40 claims to catch one error
the process already self-caught.

## 4.4 Verifier

Re-runs the original reviewer's recipes against the fixed code. Non-negotiable
in every fixer configuration (RULED 2026-08-23).

Within a PR this is the same reviewer agent resumed — that is the stated
reason fixture continuity is worth the context cost. **Fresh verification
stays** (R7): "it caught everything that mattered."

## 4.5 Merge seat / review manager

Two hats on one seat today.

**As merge seat** (`CLAUDE.local.md`, in force now): posts the review to the
PR before merging; acts as `ned-review-merge` for review, approve, merge and
`audit`, while PRs are opened as `nedlern`; never approves its own work by
switching identity — a PR this seat authored is reviewed and approved by a
different seat or by the user; runs the gate of section 2 S7.

**As review manager** — the role as practiced during the walk
(`phase-5-fixoff-results.md`, registered as an item-15 input 2026-08-22):

> route findings by pointer, commission with scope only, gate merges on
> channel reads, never restate.

A review-manager prompt is needed if multi-reviewer/multi-fixer becomes
standard; it is item 15 sub-step (3), unwritten.

**Divergence-locates-the-hard-spot** (item-15 input, 2026-08-22): multiple
arms failing one location in different styles is a detectable signature; a
manager agent can flag the collision zone without knowing which arm is
right.

**The manager is the amplifier risk.** F5 is a finding about this role, not
about reviewers or fixers. Point-don't-paste (3.4) exists to bind it, and
the ladder's rule that commissions carry evidence but never strategy
(section 5) is the same constraint on the same seat.

## 4.6 The round-3 analyst, and the lenses

Both are instruments of the escalation ladder's third rung, not standing
roles on every PR.

**The analyst** (item 15 sub-step 4, unwritten prompt): given all arms'
diffs and failures, produces the divergence map and the **recursive** root
cause. The user's observation behind the recursion: a first RCA is one level
down; recursion reaches commission-level causes.

Its standing question set (ladder refinement, 2026-08-22): for each failure
— cause in the CODE, the DESIGN/COMMISSION, or the TESTS-AS-EVIDENCE? Then
recursively: why did that cause exist? — iterated until the answer names
something outside the artifact or bottoms out. Measured basis: all three
legs have specimens (a UTF-8 crash; the invariant-in-no-input trap; the
vacuous probe, unwired tests, and fixtures that encoded the defect).
"Tonight's chain ran four levels; only the deepest fixed the process."

**Guard:** the RCA obeys the claims discipline — grounded, ran-vs-judged
marked. "A speculative root cause asserted as fact to three arms is the
supervisor-amplifier reborn."

**The lenses** (user proposal 2026-08-22; item 15 sub-step 5, charters
unwritten). Parallel naive reviewers specialized by failure leg, since PR
reviewers default to code:

- a **DESIGN lens** — given the spec + diff: does the change serve the
  requirement; is the load-bearing invariant stated anywhere; what does a
  widened matcher now include;
- a **TEST lens** — do the new tests fail on the broken base; does anything
  run them; is any proof vacuous. Half mechanical, so built as a script plus
  a narrow agent, per the script-for-the-mechanical doctrine.

**Placement (user, 2026-08-22): reserved for ROUND 3**, not standing on
every PR — by the time two rounds have failed, the surviving cause is
disproportionately design- or test-leg, which is what the lenses hunt. They
join the recursive-RCA analyst as round 3's diagnosis battery. Volume guard:
narrow charters plus triage routing. Measured basis: every test-leg catch in
the corpus came from ad-hoc commissioned questions, and the design-leg trap
was invisible to code review by construction.

---

# 5. The escalation ladder

The user's design, refined 2026-08-22 (`phase-5-fixoff-results.md`); ruled
into item 13 on 2026-08-23 as "the escalation ladder as designed, refining
per natural specimen." It is the control flow of the S4/S5/S6 loop.

- **Round 1:** resume the original author (`oa`). Cheapest; the fix-off
  measured no quality cost. Verified per the reviewer's recipes, as every
  round is.
- **Round 2 (r1 failed):** `oa` with r1 context, plus fresh Claude `c0` and
  fresh Codex `x0` **in parallel**. The manager's commission carries a
  first-pass RCA of r1's failure **as EVIDENCE** (where it failed, how) —
  never strategy or depth mandates (the #118 lesson; item 9's rule binds
  every rung).
- **Round 3 (r2 failed):** the RCA becomes its own step first — a fresh
  analyst gets all arms' diffs and failures and produces the divergence map
  and the recursive root cause. The manager then either
  **(a)** takes a stop/redesign recommendation to the user — *the exit sits
  BEFORE round 3, because a mis-specified commission is not fixed by more
  arms* — or **(b)** commissions round 3: `oa` + one fresh arm per runtime,
  all carrying the evidence pack; a **third runtime** (e.g. Gemini) replaces
  same-runtime duplicates, per the project's own decorrelation doctrine
  (blind spots correlate within a runtime; the fix-off confirmed style
  varies while location correlates).
- **Round 3 failed:** the manager walks the problem with the user.

**Cost note.** Arms parallelize (tokens, not wall-clock), but every arm must
be verified — arm count multiplies the expensive non-negotiable step, so
marginal budget goes to the analyst, not clones.

**Round-2 pairing stands** after specimen two: the arms' failure styles stay
decorrelated.

**Status.** The ladder's shape is recorded as "open pending more specimens";
item 13's 2026-08-23 ruling adopted it "as designed, refining per natural
specimen." Repetition is owed: specimen one is one specimen, and the
tournament's judge layer never ran — grading alone separated the arms. The
specimen plan after #131 and #118: **#110** (the uncaught fix-introduced
defect), then **#101** (abandoned).

**Experiment hygiene, for anyone running another specimen** (these belong in
the standing replay/experiment procedure, R9's docs, and are recorded as
owed):

- `codex exec` workspace-write on macOS does **not** block child outbound
  network — a replay can read answers straight past a scrubbed clone; the
  working mitigation is the dead-proxy `shell_environment_policy`.
  **Scope, ruled by the user 2026-08-23:** this is a REPLAY-ONLY concern and
  must not be generalized into ordinary review cells. A replay re-runs a task
  whose solution and review findings are published on the pull request, so an
  unblocked network lets the agent fetch the answer and the experiment
  measures nothing. An ordinary review cell is reading new code, has no
  answer to fetch, and was ruled able to check facts online (2026-08-18) —
  blocking its network would remove a capability the user granted, to defend
  against nothing. So the dead proxy becomes a documented, version-pinned
  recipe inside this experiment procedure rather than a launcher every cell
  runs through. **Version pins at ruling time:** codex-cli 0.147.0, macOS
  26.5 build 25F71, gh 2.97.0.
- **Codex memory contamination — RULED 2026-08-23, and the remedy is not
  what this bullet used to say.** Codex reads its own store under
  `~/.codex/` before doing anything else, and every Codex process on a
  machine shares it. This bullet previously said to point it at an empty
  `CODEX_HOME`. That is heavier than needed and rests on two claims that are
  wrong: a different `CODEX_HOME` loses far more than memories and the
  global `AGENTS.md` (sessions, history, logs, skills, plugins, hooks,
  rules, trust state), and `auth.json` is NOT universally required, because
  keychain and API-key paths exist and may not be namespaced by
  `CODEX_HOME` at all. Both corrections came from asking Codex directly, at
  the user's instruction.

  **The supported remedy is a per-invocation flag:** `--disable memories`
  (equivalently `-c features.memories=false`). It suppresses reading
  existing memories AND the generation pipeline for that process, changes
  nothing on disk, and leaves the user's own interactive Codex untouched.
  Verified on this Mac before commissioning: `codex features list` reports
  `memories … true`; `codex --disable memories features list` reports
  `false`. For a run that should also leave no saved session to be mined
  later, `--ephemeral` is the documented addition.

  **The reading contamination is real and worse than first described**;
  **the writing contamination is NOT established and this document said it
  was.** Corrected 2026-08-23 by the independent reviewer of the pull
  request that carries the fix.

  Reading, measured: the shared store holds a task group named "NedsChorus
  NC toolchain / constrained adversarial review", with "Reusable knowledge"
  and "Failures and how to do differently" sections — Codex's own
  conclusions from previously reviewing this project. That is not merely
  present but demonstrably injected: the reviewer recovered the actual
  `role: developer` message headed `## Memory`, 37,535 characters, from
  `code-review-codex-cell.py`'s own review run on pull request #102, and
  found the block in **73 of 98** `codex exec` sessions across 2026-08-17
  to 08-23 — 61 of them under `--sandbox read-only`. Structural note for
  anyone repeating the measurement: `codex exec review` writes TWO session
  files, a parent wrapper without the block and a child reviewer thread
  with it, so a naive per-file scan undercounts.

  Writing, retracted: this document previously said "31 session files
  landed in `~/.codex/` … with the memory database updated the next day, so
  this project's automated cells have been feeding the user's personal
  memory." The 31 files are real and all 31 are nedschorus-seat sessions.
  The inference is not supported. Of the **129 sessions the memory pipeline
  has ever ingested**, not one has `originator: codex_exec` — the mode all
  three launchers use — and all 129 come from `~/Projects/nedlern-sonnet/*`
  or temp directories, **zero from `~/agents/*`**. Ingestion has been idle
  since 2026-08-15; the job that ran on 08-23 was
  `memory_consolidate_global`, re-processing existing material rather than
  taking in a cell session. Whether the flag prevents LATER ingestion of an
  already-persisted cell session is unmeasured: the persisted file is the
  pipeline's input, and no per-session feature-flag record appears in
  sampled `session_meta`. `--ephemeral` is the flag that removes the input.

  The case for the change rests on the reading half, which is measured. The
  writing half is a possibility, not an observation, and saying otherwise
  was this seat's error.

  **Scope:** this applies to every review cell, not only to replays. The
  flag is being added at all three call sites
  (`sanity-check-attacks.py`, `code-review-codex-cell.py`,
  `md-review-codex-cell.py`) on branch `codex-cells-disable-memories`.

  **Purging the existing store is separate and is the user's**, deliberately
  not done by any seat. Codex's own guidance, worth keeping because it
  contradicts the obvious approach: the supported purge is the interactive
  `/memories → Reset all memories`; `codex debug clear-memories` exists but
  its own help labels it *Internal*; the SQLite database is the
  authoritative layer and repopulates from saved sessions, so deleting
  either side alone is not a reliable purge; and `~/.codex/memories/`
  contains much more than its markdown files — a `.git`, scripts, temporary
  artifacts, rollout summaries — with the reset's deletion whitelist
  undocumented. Back it up first.
- **Dead-proxy scope caveat** (user-raised 2026-08-23): the codex arms were
  instructed never to touch GitHub and obeyed — post-run command audits
  clean, all runs. The dead proxy guards **validity, not obedience**: a
  diligent agent's innocent context-fetch would silently invalidate an arm,
  and contamination control cannot rest on the subject's cooperation. Scope
  line: the dead proxy blackholes ALL child HTTP, so use it only for
  isolation-critical experiments whose commission needs no child network; a
  run needing legitimate child network needs an allowlisting proxy or a
  different design. Meta-rule (user): things outside the plan get extra care
  or the user's eyes, usually both.

---

# 6. The side-channels

Work that outlives the PR leaves through a named door. The reason is F2's
second half: every fix is also a bet — each #118 round introduced exactly
one new defect; #98's post-merge fix introduced the race that became #102's
round-2 finding; #110's round-1 fix introduced a traceback no reviewer
caught. Folding an unrelated discovery into an open PR buys a new defect
risk on a change nobody commissioned.

## 6.1 Agent-filed GitHub issues (user-ruled 2026-08-23)

**Supersedes the queue-note route for the confirmed-bug class.** The user's
design, adopted after the merge seat wrongly defended the old sign-off rule
against its own author: the post-sign-off gate existed to stop SPECULATIVE
agent issues; a reproduced finding is categorically different.

- **Eligible for agent filing:** `basis=reproduced` AND `consequence >=
  wrong-behavior-in-operation`. Filed through the `ghi-write` skill; marker
  label; **the issue body's first section is the reproduction**, so any
  reader can re-run the proof.
- **Not eligible (unchanged):** `basis=judged`, design concerns, questions —
  queue notes / sign-off, because there the judgment IS the reserved
  decision.
- **`loses-work-or-data` additionally** gets the immediate fix-PR
  commission; the GHI tracks, the PR fixes, the issue closes on merge;
  visibility is fleet-wide meanwhile. The merge seat's local rule adds the
  operational shape: opening a PR needs no sign-off, the #98→#102
  52-minute turnaround is the standard, plus one `say` line and a plate
  task.
- **The marker is a MANDATORY PAIR** (extended by the user 2026-08-23) so it
  can be mechanized safely: every issue carries exactly one of two labels
  (the user's candidates: `auton-issue` | `manual-issue`), and existing GHIs
  are backfilled with the manual mate so the exactly-one invariant holds
  from day one. Final names settle in the amendment PR with a grep-check.
- **Consequence, owed:** the `ghi-write` skill needs the ruled exception
  written into it — its own PR through the instruction-file lane.
  Commissioned to the mac-ubuntu-bridge seat, which owns the GHI tooling
  (issue #46).

### Fix-now takes precedence over filing, when the fix is small (user-ruled 2026-08-23, later the same day)

Ruled while walking the parked cleanup queue, on a finding that met the
agent-filing gate exactly (reproduced, wrong-behavior-in-operation). The
user declined the issue and commissioned the fix instead, in his words:

> "I prefer making small fixes now instead of creating ghis, remembering to
> look at the ghis, hoping the context wasn't lost, ..."

The reason is a read-path failure, not a dislike of issues: an issue defers
the work to a moment when someone must remember to look, and by then the
context that made the finding actionable may be gone. A small fix made now
carries its own context and needs no retrieval.

So the order of preference for a reproduced finding that reaches
wrong-behavior-in-operation is: **fix it now** if the fix is small; file the
agent-filed issue when it is not. Filing remains right for work too large to
do on the spot, and the eligibility gate above still governs what may be
filed WITHOUT sign-off when filing is the answer.

OPEN, and the user's to settle: where "small" ends. No boundary was stated,
and the two routes are not equivalent in cost — a fix consumes a review
cycle and a merge, an issue consumes a queue slot and a future reader.

## 6.2 Queue notes

`docs/issues/queue/` is the ask-the-user path. It takes unrelated accidental
discoveries, judged findings, design concerns and questions — each a small
zero-context note, landed as its own small PR, never folded into the PR that
found it (locked text, 3.1).

Considered and rejected as the destination: the built-in session task list —
session-scoped, dies at recycle, invisible to other seats.

## 6.3 Knowledge records, and where they live

**The placement ladder** (user + merge seat, 2026-08-23), built from the
user's proven read-path principle — the read path is what fails, not the
store:

1. **Forced files** (seat rules, `CLAUDE.md`, `AGENTS.md`) — always-needed
   rules; the path is small, keep it so.
2. **README per major system + a thin skill** whose description is the
   at-need trigger ("use BEFORE touching X") pointing at it — the harness's
   trigger matching IS the zero-context retrieval mechanism. `ghi-write` is
   the live model; **the PR-Main README lands this way.**
3. **A knowledge agent only where which-knowledge-applies is itself a
   judgment** (the GHI agent's razor).
4. **Memory stays user-gated as ruled.**

**Staleness defense:** records live INSIDE the review machinery — the claims
rules apply to docs, and reviews pass over them (the #135 index catch is the
model) — with version pins and, where possible, a regression test that
doubles as the drift detector.

**A record that exists because it is a non-obvious negative:** Codex's
silent skip is indistinguishable from ran-and-found-nothing. The integration
publishes no check run, no status, no error in either case, verified on
reviewed and unreviewed PRs alike. That indistinguishability is the
knowledge record. Related factual note: the local Codex CLI leaves full
event jsonl (audited 2026-08-23); the cloud bot leaves nothing local — the
undecidability is structural.

**Active knowledge injection** (user proposal 2026-08-23, **parked** for
post-handoff design): beyond the passive ladder, a supervisor watching the
fleet's filtered jsonl stream (`watch-agent-dialogs.py` is already this
monitor) with a cheap-fast classifier triggering on keywords and shapes —
"agent approaching X without knowing Y" — and injecting **a pointer** to the
knowledge home by cross-session message. Constraints carried with the
proposal: pointers never retellings (the amplifier lesson, doubly for pushed
knowledge); injections rare and load-bearing (the `say` discipline applied
to machine-to-machine attention); the injector reads the same READMEs — it
is a retrieval layer, never a second store.

## 6.4 External findings, and the plate

**External handling** (merge seat duties, in force 2026-08-23):
workaround-not-yet-built → agent-filed GHI, where the isolation demo is the
reproduced bar; coping this PR needs → a sibling blocking finding;
knowledge-only → a record in the behavior's durable home, never a
transcript; always version-pinned; a workaround's regression test is the
drift detector.

**The plate** — the persistent task list, PR #141's rig, accepted 2026-08-23
as the mechanism for tracking open items across a session boundary. One
native task per open item (GHIs filed, PRs commissioned, questions routed to
the user); statuses leave only by finished or obsolete; the handoff records
expected task ids, because a silently rebound store looks like success.
User-blocking items surface ONE AT A TIME at natural pauses; `say` only for
act-now items; no external channels.

## 6.5 Session recycling, and the subagents it kills (user-ruled 2026-08-23)

**How a recycle happens.** A seat's session recycles when its context runs
low. `scripts/handoff-context-threshold-hook.py`, wired as a Stop hook, fires
once at a turn boundary and tells the session to run its handoff skill; the
session writes a handoff file; `scripts/handoff-supervisor.py` sees the file,
kills the session, and launches a successor with an ignition prompt. Nothing
kills the session until that file appears, so the moment of the recycle is
the agent's own to choose, and deferring it is structurally possible.

**Subagents spawned by that session die with it.** On 2026-08-23 this seat
commissioned a subagent to fix the review findings on pull request #150. The
session recycled and the subagent died. Its work was NOT lost — its git
worktree and branch survived on disk at exactly the reviewed head — but its
*ownership* was: nothing in the handoff said the pull request had a fixer.
The successor found the orphan only because the retiring agent happened to
mention it in a sentence of prose, which is the faculty most degraded at
recycle time.

**RULED: kill and restart uniformly; do not defer the recycle.** The
alternative considered and rejected was a conditional rule — let a subagent
that is mid-work finish, kill one whose only product is a report to a parent
that no longer exists. It was rejected because it demands a classification at
the exact moment the agent is least able to classify. A uniform rule executes
reliably under those conditions; a conditional one fails precisely when it is
needed, which is the same failure shape as the hand-written merge gates that
regressed twice in August. A killed subagent's partial work is also legible
rather than lost: its edits are individual file writes, so `git status` in its
worktree shows exactly which landed.

**RULED: the handoff records the roster, so the successor restarts them
quickly.** The record is of every subagent the session SPAWNED — not only
those still running. The motivating orphan was not running when its session
died: it had finished its round and sat idle, resumable, owning unfinished
work, so a roster filtered to "currently running" would exclude the exact
case the feature exists for. Whether a subagent is worth restarting is a
semantic judgement; the writer records what a machine can know and the
successor judges. Being built on branch
`handoff-records-spawned-subagent-roster`: the writer
(`scripts/handoff-write-and-check-supervisor.py`) records the field, and
`build_ignition_prompt()` in the supervisor surfaces it, following the
`queue_status` line in that same function as its precedent.

**Practice, this seat's refinement rather than a ruling:** commission prompts
tell the subagent to commit each unit of work locally as it completes, and to
push once at the end of the round. The two halves answer different threats.
The commit is what survives a kill, because the worktree is on disk. The push
is for the pull request's readers — and pushing per commit restarts the
automated reviewer's latency clock, making it re-read a moving target several
times for no gain.

**RULED, on the pace of fixes (2026-08-23).** Asked whether to keep opening
fix pull requests at the rate this walk was generating them, or to let the
queue drain first, the user ruled fix-as-we-find: fix problems as they are
found, so that neither he nor the seat has to re-derive a problem's context
later.

---

---

# 7. Mechanisms to be built

**None of these exists yet.** All three are named in the sources as build
items; the user deferred their detail — commands, data shapes, hook wiring,
gate integration — to walk item 15's entry 7 (2026-08-23, after the tags
locked). This section names them, cites what motivates each, and stops where
the user stopped. Designing the CLI here would pre-empt the entry the user
reserved.

## 7.1 The `pr-state` tool (the committed merge gate)

**What it is** (`phase-4-research-triage-synthesis.md`, "The PR-knowledge
door"): the validator, digest, SHA check, and verbatim-delta commands as one
tool that commissions and gates require.

**Why a tool and not an agent — the design's sharpest line.** The proposal
began as "the GHI pattern applied to PRs: one door all seats go through, so
channel discipline is correct by construction instead of remembered." The
user corrected the analogy on 2026-08-23: the GHI agent never summarizes —
it *routes*, telling the caller which issue to read — and it exists because
that relevance-routing is a judgment. The PR door contains no equivalent
judgment anywhere: comments attach to their PR, findings map to fixes in the
fixer's PR body, and routing is mechanical from tags. **So it is a PURE
MECHANISM. No agent at this door.** The only judgment that could ever
justify one — cross-PR relevance ("this is the class #134 fixed") — belongs
to the gatekeeper if ever wanted. A cloud variant was noted and not taken.

**The hard line the door does not cross**, drawn by F5 and the
point-don't-paste ruling: **the door serves BYTES, never retellings.** It
mediates writes (tag validation, named-shapes refusal, serialization) and
freshness (head SHA, channel digest, verbatim delta since digest X), never
comprehension; readers get the reviewer's own words unaltered.

**Motivating specimens (two of the same regression):** #125, merged
2026-08-22 over two P2s by a script that printed the inline count and
proceeded on `&&`; #141, merged 2026-08-23 by a hand-written variant that
gated the head SHA but only printed the comment count. The recorded
conclusion: improvised per-merge gates regress; the committed gate is the
fix.

**A third specimen, and it widens the class beyond the merge gate**
(git-infra seat, 2026-08-23, self-reported and then corrected by that seat
against its own transcript, which the merge seat read rather than relaying).
The command, verbatim from the transcript, the tail of a longer `&&` chain:

    git -C "$PRWT" cherry-pick HEAD@{0} 2>&1 | tail -2 && \
    git -C "$PRWT" push 2>&1 | tail -1 && \
    git worktree remove "$PRWT" && echo cleaned

`HEAD@{0}` resolved in the freshly added worktree `$PRWT`, whose reflog holds
the branch tip rather than the commit just made in the seat's own worktree.
So the cherry-pick had nothing to apply and failed. The chain then ran to
completion: the push answered `Everything up-to-date`, the worktree was
removed, and `cleaned` printed. Every visible sign said success and the
correction had not been made.

**The mechanism is the pipe, not the truncation.** A pipeline's exit status
is its LAST command's, and `tail` always succeeds, so the failed cherry-pick
could not stop the `&&` chain. `2>&1 | tail -2` did not hide the evidence —
`nothing to commit, working tree clean` was sitting in the visible output.
It replaced the failure signal with a success one.

**And it was caught by eye**, by the seat reading those two lines in the
result. That is the honest and less flattering account, corrected by that
seat when this entry first credited its `origin/` read-back with the catch:
the read-back was the redo's verification, adopted afterwards. Eyes are
exactly what this class defeats, so a specimen caught by eye is a near-miss,
not a working control.

Nothing shipped wrong, but the shape matches #125 and #141 while the
operation differs — a push, not a merge — so the rule is not about the merge
door: **a check whose output cannot distinguish "it worked" from "I looked at
nothing" is not a check.** `Everything up-to-date` is that sentence exactly;
so is an inline-comment count printed beside a merge.

Three countermeasures, in the order they bite:

1. **Never pipe a command whose failure is supposed to stop a chain.** Piping
   through `tail`, `head`, `grep` or `wc` replaces its exit status with the
   filter's. Use `set -o pipefail`, test `PIPESTATUS`, or run the command
   unpiped and filter afterwards. This is the one that would have prevented
   this specimen.
2. **Verify by reading back the state the operation was supposed to produce,
   from the authority** — here `origin/` — not from the tool's report of its
   own success. This is the redo's method and the durable habit.
3. **Truncating a verification step's output is a hazard in its own right,**
   because the tell-tale line is usually the one cut. It did not bite here —
   the line survived inside `tail -2` — but it remains a way to blind a check
   even where the exit status is handled correctly.

**What it must gate on:** the channel **digest** (`id`+`updated_at` across
all three channels) — never counts, never `commit_id`. #141 demonstrated
that GitHub remaps an old comment's `commit_id` to a new head, so
`commit_id` is not evidence of comment newness; `created_at` is.

**Name check:** `pr-state` was to be grep-checked at build. What was run on
2026-08-23: `grep -rn "pr-state" --include="*.md" --include="*.py"` over the
repository, plus a listing of `scripts/`. Result: three hits, all inside
`review-fix-cycle-analysis/` (`phase-3-synthesis.md` item 15, and two in
`phase-4-research-triage-synthesis.md`); no file in `scripts/` carries the
name. The name itself is two parts, which the project's
naming rule treats as thin — whether it becomes a longer explicit name is a
build-time decision.

## 7.2 `scripts/review-finding-tags-check.py` (the tag validator)

**What it does** (user's addition, sub-walk item 1, accepted 2026-08-23):
parses the tag line per finding and reports **valid / invalid-value /
wrong arity-or-order / missing**. It also enforces the conditional fifth
tag's presence and vocabulary when `introduced-by = pre-existing`.

**Placements:** blocking in the merge seat's pre-merge gate — malformed tags
silently misroute work, so it bounces to the reviewer; and as a self-check
in the reviewer procedure before posting.

**Scope:** seat-authored findings only. **Bot comments are exempt by author,
never by silence** — the exemption is a check on who wrote the comment, not
an inference from a missing tag line.

**Doctrine:** script-for-the-mechanical.

**Name check:** the same run on 2026-08-23
(`grep -rn "review-finding-tags-check" --include="*.md" --include="*.py"`
plus the `scripts/` listing) returned one hit,
`phase-4-research-triage-synthesis.md`; no file in `scripts/` carries the
name. The source marks the name "to be grep-checked" at build; this is that
check against today's tree, not a reservation of the name.

## 7.3 The write-time `PreToolUse` hook

**What it does** (user extension, sub-walk item 1, 2026-08-23): runs the
validator at WRITE time on `gh pr review` / `gh pr comment` Bash calls —
malformed tag lines refused before posting, with edits covered by the same
route. It also enforces the named-shapes rule: a seat-authored PR comment
must be a tagged finding, a question, an author fix-report, or a
merge/closing note; anything else is refused.

**What it cannot do:** see a MISSING tag line — a comment with no tag line
is indistinguishable from an ordinary comment. That case stays the merge
gate's catch.

**The three layers, stated as the design's own division of labor:**

| layer | catches |
|---|---|
| write-time hook | malformed tag lines, unnamed comment shapes |
| pre-merge gate | missing tag lines |
| written procedure | documentation — what the tags mean and how to set them |

**One build item:** script plus hook registration, at the implementation
step.

## 7.4 Not to be built

**A required status check from the Codex reviewer.** It cannot be built: the
integration publishes no check run and no commit status even on PRs it
reviews. `CLAUDE.local.md` records the recommendation as made 2026-08-19 and
retracted, with an instruction not to repeat it.

**The review-reviewer gate** (R5). Basis F1; see 4.3.

---

# 8. Open questions

Each is open in the sources; none is resolved here.

| # | Question | Owner | Where it is open |
|---|---|---|---|
| 1 | Tag names — plain words for the four tags and their values | **The user** ("his call") | `phase-4`, "Open for the user's shaping" |
| 2 | Whether `misleads-readers` should ever block a merge on its own | **The user** | same |
| 3 | Whether `pre-existing` + `loses-work-or-data` should fix-now instead of queue — the #98 P1 was merged over then fixed in 52 minutes; either answer is defensible, and Google's rule says file-and-fix-separately | **The user** | same |
| 4 | The GHI label pair's final names (`auton-issue` \| `manual-issue` are the user's candidates) | Settled **in the amendment PR with a grep-check**; built by the **mac-ubuntu-bridge seat** (owns GHI tooling, #46) | `phase-4`, routing revision |
| 5 | Sub-walk items 3–6. Resolved as bookkeeping 2026-08-23 and re-recorded in the anchor: item 3 (`introduced-by`) was presented twice, called confusing, and re-walked as the four-part C-and-D answer walk, all four parts ruled — but no separate accept of the tag itself is on the record; item 4 (`basis`) was PRESENTED and awaits the user's word; items 5 (`scope`) and 6 (failure modes) are unpresented. What remains open is the user's word on 4, the walking of 5 and 6, and the missing accept on 3 | **The user** (walk item) | `phase-4`, sub-walk order |
| 6 | Walk item 14 (R8, reviews land on GitHub channels) — the recommendation exists; the walk line carries no disposition | **The user** (walk item) | `phase-3`, walk order |
| 7 | Walk item 15 — the standing commission procedures, seven sub-steps, each needing exact wording and a zero-context read: (1) fixer commission template; (2) reviewer procedure; (3) review-manager prompt; (4) round-3 analyst prompt; (5) design and test lens charters; (6) this seat's merge-review discipline amendment; (7) the `pr-state` mechanism in detail | **The user** (wants the exact wording of each text gone over) | `phase-3`, walk order |
| 8 | Walk item 16 — the cleanup queue and this study's durable home; until it is processed the sources cited throughout are machine-local | **The user** (walk item) | `phase-3`, walk order |
| 9 | Walk item 11 (R4 severity throttling) — superseded in substance by the tag scheme, which "replaces the single serious/non-serious line," but items 9 and 11 were only "likely" to merge and no disposition records the merge | **The user** (walk item) | `phase-3` item 11; `phase-4` header |
| 10 | How the LOCKED fixer claims specification is amended to carry the agent-filed-GHI exception, and whether fixers file or only reviewers do — the locked text and the item-3 disposition both still say queue-note-only | **The user** (the text is locked by his ruling; item 15 / the second pass) | §3.1 supersession note |
| 11 | Which depth-menu wording is canonical: `smallest / generalize / recommend-redesign` (`phase-3` item 9) vs `site / mechanism / recommend-redesign` (`phase-4`) vs the frozen template's full text; and R1's stale example commission, which pre-picks "smallest correct changes" against item 9's no-pre-pick rule | **The user** (both texts are his rulings; item 15 wording pass) | §3.2, §3.4 |
| 12 | "Fifth" is overloaded: `phase-4` calls the fixer's depth choice "this scheme's fifth axis" and, later, calls `triggers-existing-problem \| non-triggering` "the fifth, conditional tag position" | **The user** (naming) / item 15 wording pass | §2.2 |
| 13 | `dismiss_stale_reviews` in branch protection — RECOMMENDED ON; GitHub natively dismisses approvals on new pushes. Queued as a one-flag ask | **The user's credential** — protection changes are not seat work | `phase-4`, staleness rule part 2 |
| 14 | Linking a Codex account to `ned-review-merge` so this seat can trigger `@codex review` and wait for the answer; today the request is refused for that account and the user must type it from his own | **The user** | `CLAUDE.local.md` |
| 15 | The escalation ladder's refinement — adopted "as designed, refining per natural specimen," with repetition owed (one and two specimens; the tournament's judge layer never ran). Next specimens planned: #110, then #101 | **The user**, on specimen results | `phase-5`; `phase-3` item 13 |
| 16 | **The second pass over this whole cluster**, which the user expects; nothing in the cluster is final-final until it | **The user** | `phase-4`, Part-2 ruling |
| 17 | The **namespace-prefix question** — LOCATED 2026-08-23, contrary to this row's original text. It is in the body of PR #141 under "Open questions for the reviewer", routed to the user by the merge seat as review finding F3: a seat's persistent task list is bound by composing `<seat>-tasks`, and the question is whether the composed id should carry a per-system prefix (`nedschorus-<name>-tasks`) to keep this project's stores apart from the legacy system's on this one Mac, or whether name discipline is enough. The earlier greps missed it because they covered `review-fix-cycle-analysis/`, `docs/`, `CLAUDE.md` and `CLAUDE.local.md` — not pull-request bodies | **The user** | PR #141 body, Open questions |
| 18 | **Reachability of a durable record.** Three records on 2026-08-23 were stated as existing without stating who could read them: a ruling that survived only in a session transcript; the walk anchors in `review-fix-cycle-analysis/`, excluded from git and present on one Mac only; and a ruling committed at `148b6e2` on `origin/doctrine-queue-drain`, which a reader of `main` cannot reach. Three mechanisms, one shape. The proposed rule: a document that points at another record states not only where it is but who can reach it, and a pointer to something not on `main` says so | **The user** | this section; raised by the git-infra seat 2026-08-23 during PR #151 |

---

# 9. Provenance appendix

Which section rests on which ruling, finding, or locked text. Dates are the
dates the sources carry.

| Section | Rests on | Date |
|---|---|---|
| 1 header, README lineage | Part-2 ruling and the state-machine frame (`phase-4`); knowledge-placement ladder rung 2 | 2026-08-23 |
| 2.1 S1 OPENED | `CLAUDE.md` lane rules (interim lane, atomic PRs); `CLAUDE.local.md` author-account rule (#117/#118 deadlock) | 2026-08-17; 2026-08-20 |
| 2.1 S2 UNDER REVIEW — the reviewer pair | Walk item 12, RULED three parts | 2026-08-22 |
| 2.1 S2 — reviewer lifetime | Reviewer-lifetime note, measured (three PRs, seven rounds, context exhaustion) | 2026-08-23 |
| 2.1 S2 — no status check, silent skip | `CLAUDE.local.md`, verified on head commits of #99/#100/#101/#102; eight-PR census | 2026-08-19 |
| 2.1 S3 REVIEWED | R8 (`phase-3`); staleness rule part 1; sub-walk item 1 rulings (validator placements, named shapes, mandatory review body) | 2026-08-21; 2026-08-23 |
| 2.1 S3 — two channels | `CLAUDE.local.md`, recorded from #95 | 2026-08-19 |
| 2.1 S4 — who fixes | Walk item 13 RULED, five parts; fix-off specimen one | 2026-08-23; 2026-08-22 |
| 2.1 S6 VERIFIED | `phase-5-fixoff-results.md` ("the binding constraint is fix-round verification"); `phase-6-118-specimen-results.md` point 3; item 13 part 3 | 2026-08-22; 2026-08-23 |
| 2.1 S7 GATED | Staleness rule (three parts); gate-regression specimens #125 and #141; `CLAUDE.local.md` three-minute rule and review-posting rule; `required_pull_request_reviews` live | 2026-08-19 → 2026-08-23 |
| 2.2 the four tags | `phase-4` proposed fleet scheme, from dual research (15 + 10 schemes) | 2026-08-22 |
| 2.2 consequence accepted | Sub-walk item 2 processed, accepted as presented | 2026-08-23 |
| 2.2 external value + required body | User addition and user ruling | 2026-08-23 |
| 2.2 fifth conditional tag | User-ruled; pair renamed by the user; grep-checked at ruling | 2026-08-23 |
| 2.3 routing table | `phase-4`, verbatim; blocking semantics unchanged | 2026-08-22 |
| 2.3 superseding row | Routing revision, user-ruled | 2026-08-23 |
| 2.3 merge-seat riders | `CLAUDE.local.md`, "Findings that outlive a PR" | 2026-08-23 |
| 3.1 fixer claims spec | LOCKED verbatim after user edits, a zero-context read, and three user rulings (walk item 3) | 2026-08-22 |
| 3.1 supersession note | Routing revision vs the locked text — the conflict is carried, not resolved | 2026-08-23 |
| 3.2 depth menu | Walk item 9 reshaping (from R2, refined 2026-08-21); frozen template text as fed to specimen two | 2026-08-21; 2026-08-22 |
| 3.2 widened-matcher rule | Root-cause analysis of the fix-off's shared introduced defect, user-prompted | 2026-08-22 |
| 3.3 reviewer/approver claims | Walk item 10 RULED; full wording lands at item 15 | 2026-08-22 |
| 3.4 point-don't-paste | R1 as strengthened during the walk; walk item 8 ACCEPTED as ruled; F5 as basis | 2026-08-22 |
| 3.5 three inputs | R7a (user's hypothesis, data-confirmed); frozen template rendering; specimen one and two support | 2026-08-21 → 2026-08-22 |
| 4.2 Codex rider | R6 rider (`phase-5`), extended by specimen two, ruled into item 13 | 2026-08-22; 2026-08-23 |
| 4.3 no review-reviewer gate | R5, walk item 2 accepted; F1 | 2026-08-21 |
| 4.3 reviewer-procedure inputs | R9 (Codex's open-source review prompt, user direction); the Gemini skeleton registered as an item-15 input | 2026-08-21; 2026-08-22 |
| 4.5 review manager | Item-15 input, the role as practiced | 2026-08-22 |
| 4.6 analyst and lenses | Ladder round 3 (`phase-5`); lens proposal and its ROUND 3 placement | 2026-08-22 |
| 5 escalation ladder | User's design, refined; ruled into item 13 "as designed" | 2026-08-22; 2026-08-23 |
| 5 experiment hygiene | Cleanup-queue entry 6 (dead proxy); the CODEX_HOME contamination channel; the dead-proxy scope caveat | 2026-08-22; 2026-08-23 |
| 6.1 agent-filed GHIs | Routing revision, user-ruled, plus the mandatory-pair extension; merge-seat duties | 2026-08-23 |
| 6.2 queue notes | Locked text's ending sentences and the item-3 rulings | 2026-08-22 |
| 6.3 placement ladder | User + merge seat | 2026-08-23 |
| 6.3 active injection | User proposal, parked for post-handoff design | 2026-08-23 |
| 6.4 external handling, the plate | `CLAUDE.local.md` duties; Part-2 ruling (plate = the persistent task list, #141's rig) | 2026-08-23 |
| 7.1 pr-state tool | The PR-knowledge door, as corrected by the user to a pure mechanism; gate-regression specimen two | 2026-08-23 |
| 7.2 tag validator | Sub-walk item 1, user's addition | 2026-08-23 |
| 7.3 write-time hook | Sub-walk item 1, user extension, plus the named-shapes ruling | 2026-08-23 |
| 7.4 not to be built | `CLAUDE.local.md` (no status check exists); R5 | 2026-08-19; 2026-08-21 |
| 8 open questions | As cited per row | — |

**On the study's own reliability**, since this design rests on it: the
synthesis carries a verification note recording that its numbers were
checked against the phase reports by an independent verifier after drafting
— 83 checked, 66 confirmed exactly including every headline figure; 9 wrong
and 8 unsupported statements corrected in place on 2026-08-21; and, per that
note, none of the corrections changed a finding or a recommendation. That
note was read; the phase reports behind it were not re-checked for this
draft. The synthesis also states its own measurement caveat:
claim counts came from different graders with declared per-grader softness,
so the orderings are the robust result and the exact integers are soft.
