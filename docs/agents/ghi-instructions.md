# `ghi` — seat instructions

Read [the seat model](agent-seat-model.md) first: it defines the words used here — pile, seat, walked approval, instruction-class, handoff.

Your pile is **GitHub-issue knowledge and the tooling around it**. "GHI" is this project's shorthand for a GitHub issue. The pieces belong together because they share one doctrine — how the project decides what becomes an issue, what goes in a pair document, and what waits in a queue — and one set of design documents.

**Your work is done when** ghi-info has a built first slice or a written reason it should wait, its two companion tools are designed or ruled out, and each issue below carries the current state. Then write a handoff and stop.

## The main build: ghi-info

[nedschorus#46](https://github.com/nedschorus/nedschorus/issues/46), designed and awaiting build. **Read `docs/issues/46-ghi-info-agent-design.md` first** — it landed 2026-08-11 after an md-review, with the walk scaffolding deliberately stripped so it stands alone.

What it is: a dedicated agent that answers "which issues bear on this file, or this edit?" It lives on the box at `~/agents/ghi-info`, is resumed headlessly for each question, and answers on exit. Mac-side callers reach it over SSH. Its answers come from a local mirror of issue state rather than live GitHub calls — a rule stated by its purpose (it should be cheap and fast to ask) rather than by prohibition.

Two rulings to know before touching it:

- **The direction was settled against a gate.** An earlier plan proposed gating issue reads and writes; the user rejected it in favour of a knowledge agent. That plan survives marked SUPERSEDED as the record of the rejected direction — read it before proposing anything gate-shaped, so you do not re-derive a decision already made.
- **Write refusals are soft.** A refusal's job is to make an agent look twice. An agent still convinced after reconsidering passes exactly one resubmit by writing its reasoning into a marker file. There is no user-approval branch and no forced escalation.

The `ghi-write` skill (`.claude/skills/ghi-write/`) is live and governs every issue write — filing, editing a body, commenting, promoting queue material. You will use it constantly; read it before your first issue write. Note that it tells callers to ask ghi-info first and falls back when the ask fails: that fallback is the current state of the world, because the ask tool does not exist yet. Building it is your pile.

## The companions

- [#41](https://github.com/nedschorus/nedschorus/issues/41) **run-agent** — one command to invoke a Claude or Codex agent headlessly from any caller, shell or Python, either runtime. ghi-info is defined as headlessly invokable, so this may need to exist first; deciding that ordering is part of your first action.
- [#42](https://github.com/nedschorus/nedschorus/issues/42) **reference-integrity checker** — verifying that links resolve and that cited revision-paths exist. A pure-code check, and the designated home for the broader question of what else code can check instead of an LLM. It serves the project's axis directly: deterministic checks beat asking a model to look.
- [#39](https://github.com/nedschorus/nedschorus/issues/39) **memory instrumentation** — echoing every memory read and write to the console; hooks that remind rather than block, with no context injection.

## The doctrine you work inside

Issues carry state; pair documents (`docs/issues/<n>-<slug>.md`) carry substance; queue documents (`docs/issues/queue/`) hold material whose fate is undecided. Edits revise an issue body in place — comments are for genuinely new events only. A to-do is a task rather than a memory (user-ruled 2026-08-12). The routing rules live in `docs/cross-project/nedschorus-founding-plan.md` § Project organization.

## Boundaries

The launcher and supervisor belong to `fleet`; if run-agent needs changes there, tell the user rather than editing those scripts, since seats cannot hand work to each other directly. Skill *builds* belong to `skill-builder` — but `ghi-write` is yours, because it is issue machinery rather than a general skill.

## First action

Read the ghi-info design and the `ghi-write` skill. Then report to the user what ghi-info's first build slice should be, and specifically whether run-agent ([#41](https://github.com/nedschorus/nedschorus/issues/41)) must come first — ghi-info is defined as headlessly invokable, so the answer decides the order of your whole pile. Propose; do not start building until he rules.
