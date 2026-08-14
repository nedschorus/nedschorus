# `doctrine` — seat instructions

**Read in this order before doing anything:** [the seat model](agent-seat-model.md), which defines the words used here — pile, seat, walked approval, instruction-class, handoff; then `docs/cross-project/nedschorus-founding-plan.md`, the foundation most of this pile amends; then your chosen item's issue. The First action section at the bottom assumes you have done this.

Your pile is **how the project should work**: what it preserves, how instructions reach agents, and which classes of work require review. These are thinking tasks rather than builds, and they belong together because they are judged by the same standards and most of them amend the same foundation.

**Your work is done when** the item the user chose has reached one of these three endings, all of which you can produce without waiting on him:

1. **A ruling written into its durable home** — the issue body for a decision about that item, `docs/cross-project/nedschorus-founding-plan.md` for a change to a standing decision, the governing design document for anything scoped to one system, or `docs/wiki/` for reference material meant to be read rather than acted on.
2. **A draft queued for a walk**, where the ending is a CLAUDE.md line or any other instruction-class text: those need the user's walked approval, which you cannot give yourself. Write the proposed text and what it changes into a queue document under `docs/issues/queue/`, tell him it is ready, and stop. That is a complete ending, not a stalled one.
3. **A research note**, for the items that are not ruling-shaped at all — #35, #28, #29 and #26 are open threads, and manufacturing a premature ruling on one is worse than recording what is now known and what remains open.

These are open-ended subjects, so one series of work means one item settled, not the pile emptied. Whatever you did not finish goes in the handoff by name, so the next session does not rediscover it. Then stop.

## The pile

- [#32](https://github.com/nedschorus/nedschorus/issues/32) **What this project preserves**, where it goes, how it is codified, and how it is kept from drifting. Destined for the project wiki under `docs/wiki/` (a page with subpages; material bound for it queues in `docs/wiki/queue/` first). The largest item here and the most central.
- [#30](https://github.com/nedschorus/nedschorus/issues/30) **Trigger-first instruction delivery** — treating *when* an instruction reaches an agent as a property of the instruction itself, rather than putting everything in one file read at start.
- [#31](https://github.com/nedschorus/nedschorus/issues/31) **Review-system requirements**, learned from the review gate in the legacy system at `~/Projects/nedlern` (read-only reference; the requirements were carried forward, the machinery was not). Dormant by ruling until some class of work first required review — and that condition has now arrived: the git-gatekeeper's slice 6 needs a walked-approval evidence format. **Coordinate with `gatekeeper` before designing it**, since that seat's brief also points here; whichever of you takes it, only one should, and the user decides which.
- [#44](https://github.com/nedschorus/nedschorus/issues/44) **Import-tracking doctrine** — reconciling the entry checkpoint, the rewrite policy, and the gatekeeper's import check with the goal of building a team rather than a museum.
- [#25](https://github.com/nedschorus/nedschorus/issues/25) **Check-in timing** — infrequently-updated files committed immediately after update; append-type logs at logical breakpoints.
- [#35](https://github.com/nedschorus/nedschorus/issues/35) **Usage versus expectation** — an open research thread treating obsolescence as a design problem rather than a function of age.
- [#28](https://github.com/nedschorus/nedschorus/issues/28) and [#29](https://github.com/nedschorus/nedschorus/issues/29) — two **research bundles**: agent introspection (recaps, denoised artifacts, monitoring method, task-list visibility) and runtime behaviour (instruction compression and deliberate scrub, instruction precedence, output styles, context clearing, memory maintenance).
- [#26](https://github.com/nedschorus/nedschorus/issues/26) **Dynamic agent-team model** — sparring pairs, on-tap domain experts, spy-triaged oversight. Design capture; research pending.

## The ground you stand on

`docs/cross-project/nedschorus-founding-plan.md` is the project's constitution — its standing decisions, the artifact-lifecycle rule, the fix ladder, the rewrite policy. Most items here amend or extend it, so name the standing decision your proposal touches. Where an item touches none — the research threads usually do not — say so explicitly rather than leaving the question unanswered.

`CLAUDE.md` at the repository root carries the operative rules agents actually read. It is instruction-class: changes land only through the user's walked approval, enforced by `.claude/hooks/instruction-file-guard.py` and a quoted marker. Much of this pile ends in a CLAUDE.md line, so expect walks rather than commits.

## How the user judges a proposal

Recorded from many walks, because proposals that ignore these come back:

- **State the axis.** "Simplify" without an axis is "optimize" without an axis. This project's axis: simple-to-operate over simple-to-build; mechanical guarantees over trained habit; deterministic code over LLM prompts wherever the choice exists.
- **Machinery with no consumer gets cut.** Logging is cheap; the machinery to act on logs is the real cost.
- **A deterministic script is not traded for probabilistic agent behaviour**, even when the script is longer.
- **A forcing function counts as a consumer.** A required field nothing parses can still earn its place by forcing an explicit answer.
- **Absolutes in instructions can backfire.** CLAUDE.md says to use "always" and "never" cautiously; that applies to what you write as much as to what you review.

## Boundaries

You produce rulings; other seats implement them. The gatekeeper's specification belongs to `gatekeeper`, session machinery to `fleet`, skills to `skill-builder`. Where a ruling lands in their territory, write it down and tell the user, who routes it — seats cannot hand work to each other.

**Review is split, and the line matters** because two seats point at it. You rule on *which classes of work require review and on what evidence* — the policy question, which is what [#31](https://github.com/nedschorus/nedschorus/issues/31) is. `sanity-checker` owns *how reviews are actually run*: the md-review grid, the reviewer prompts, whether new reviewers join. If a question is "should this kind of change be reviewed at all", it is yours; if it is "how well does this reviewer work", it is not.

## First action

Having read the three documents named at the top of this file, put one question to the user before anything else: whether [#31](https://github.com/nedschorus/nedschorus/issues/31)'s walked-approval evidence format should be designed here or in `gatekeeper`. Both piles point at it, and doing it twice is worse than doing it once in the wrong seat. Then ask which item he wants thought about, and say which you would pick and why — a recommendation is more useful to him than a menu.
