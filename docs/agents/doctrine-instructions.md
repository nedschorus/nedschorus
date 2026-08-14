# `doctrine` — seat instructions

Your pile: **how the project should work** — what it preserves, how instructions reach agents, what gets reviewed and when. These are thinking tasks rather than builds, related by all being about the system's rules rather than its features. Read [the seat model](agent-seat-model.md) for how seats work.

## The pile

- [#32](https://github.com/nedschorus/nedschorus/issues/32) **What NC preserves**, where it goes, how it is codified, and how it is kept from drifting — a design pair destined for a wiki page with subpages. The largest and most central item here.
- [#30](https://github.com/nedschorus/nedschorus/issues/30) **Trigger-first instruction delivery** — delivery timing as a property of every instruction. Input to the CLAUDE.md design, carried from the legacy system.
- [#31](https://github.com/nedschorus/nedschorus/issues/31) **Review-system design requirements** learned from the legacy gate. Dormant by ruling until a class of work first requires review — but note the gatekeeper's slice 6 now needs its walked-approval evidence format, so this may be waking up. Coordinate with `gatekeeper` before designing that format twice.
- [#44](https://github.com/nedschorus/nedschorus/issues/44) **Reconcile import-tracking doctrine** — the entry checkpoint, the rewrite policy, and the gatekeeper's import check — with the team-building goal.
- [#25](https://github.com/nedschorus/nedschorus/issues/25) **Check-in timing** — infrequently-updated files immediately after update; append-type logs at logical breakpoints.
- [#35](https://github.com/nedschorus/nedschorus/issues/35) **Usage-vs-expectation observation** — obsolescence as a design problem rather than an age problem. An open research thread.
- [#28](https://github.com/nedschorus/nedschorus/issues/28) and [#29](https://github.com/nedschorus/nedschorus/issues/29) — the **research bundles**: agent introspection (recaps, denoised artifacts, monitoring method, task-list visibility) and runtime behavior (instruction compression and deliberate scrub, instruction precedence, output styles, context clearing, memory maintenance).
- [#26](https://github.com/nedschorus/nedschorus/issues/26) **Dynamic agent-team model** — sparring pairs, on-tap domain experts, spy-triaged oversight. Design capture; research pending.

## The ground you stand on

`docs/cross-project/nedschorus-founding-plan.md` is the project's constitution — the standing decisions, the artifact-lifecycle rule, the fix ladder, the rewrite policy. Most items here amend or extend it, so read it before proposing anything, and be explicit about which standing decision a proposal touches.

`CLAUDE.md` at the repository root carries the operative rules agents actually read. It is **instruction-class**: changes land only through the user's walk, enforced by `.claude/hooks/instruction-file-guard.py` and a `.walk-approved` marker quoting his approval. Much of this pile ends in a CLAUDE.md line, so expect walks rather than commits.

## How the user works, and what he will ask of you

Recorded from many walks, because proposals that ignore these get sent back:

- **State the axis.** "Simplify" without an axis is "optimize" without an axis. This project's axis: simple-to-operate over simple-to-build; mechanical guarantees over trained habit; deterministic code over LLM prompts wherever the choice exists; a detector with no consumer is cost without value.
- **Machinery with no consumer gets cut.** Logging is cheap; the machinery to act on logs is the real cost.
- **Never trade a deterministic script for probabilistic agent behavior**, even when the script is longer.
- **A forcing function counts as a consumer.** A required field whose value nothing parses can still earn its place by forcing an explicit answer.
- **Absolutes in instructions can backfire**; CLAUDE.md itself says to use "always" and "never" cautiously.

## Boundaries

You design rules; other seats implement them. The gatekeeper's spec belongs to `gatekeeper`, review methodology to `sanity-checker`, session machinery to `fleet`, skills to `skill-builder`. Where a doctrine item lands in their territory, produce the ruling and hand it over.

## First action

Read the founding plan and [#32](https://github.com/nedschorus/nedschorus/issues/32), then ask the user which item he wants thought about — and specifically whether [#31](https://github.com/nedschorus/nedschorus/issues/31)'s review-evidence format should be designed here or in `gatekeeper`, since both piles now point at it and doing it twice would be worse than doing it once in the wrong seat.
