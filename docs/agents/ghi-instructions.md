# `ghi` — seat instructions

Your pile: **GitHub-issue knowledge and the tooling around it** — the agent that answers "which issues bear on this file?", the CLI that invokes agents headlessly, and the checker that keeps references honest. They share the issue doctrine and the same design documents. Read [the seat model](agent-seat-model.md) for how seats work.

## The main build: ghi-info

[nedschorus#46](https://github.com/nedschorus/nedschorus/issues/46), designed and awaiting build. **Read `docs/issues/46-ghi-info-agent-design.md` first** — the design landed 2026-08-11 after an md-review, with walk scaffolding deliberately stripped so it stands on its own.

Shape, in brief: a dedicated issue-knowledge agent, seated on the Ubuntu box at `~/agents/ghi-info`, asked which issues to read before a file or an edit, resumed headlessly per question and answering on exit. Mac-side callers reach it over SSH through the launcher. Its answers come from a mirror of issue state — **it never fetches live issue state itself**, a rule stated by its purpose rather than by prohibition.

Two rulings worth knowing before you touch it. First, the direction was **settled against a gate**: an earlier ghi-gatekeeper plan proposed gating issue reads and writes, and the user rejected it — no gate on reads or writes, a knowledge agent instead. That plan survives marked SUPERSEDED as the record of the rejected direction. Second, **write-tool denials are soft**: a refusal's job is a deliberate second look, and a still-convinced agent passes exactly one resubmit by writing its reasoning into a marker file. There is no user-approval branch and no forced escalation.

The `ghi-write` skill (`.claude/skills/ghi-write/`) is live and governs every issue write — filing, editing a body, commenting, or promoting queue material. You will use it constantly; read it before your first issue write.

## The neighbours

- [#41](https://github.com/nedschorus/nedschorus/issues/41) **run-agent** — one CLI to invoke a Claude or Codex agent headlessly from any caller, Python or shell, either runtime. ghi-info needs exactly this to be callable, so the two are natural companions and may share a design.
- [#42](https://github.com/nedschorus/nedschorus/issues/42) **reference-integrity checker** — links resolve and cited revision-paths exist; a pure-code review check, and the designated home for "what else can code check rather than an LLM". Directly serves the project's axis of replacing prompts with deterministic code.
- [#39](https://github.com/nedschorus/nedschorus/issues/39) **memory instrumentation** — echo every memory read and write to the console; remind-tier hooks, no blocking, no context injection.

## The doctrine you are working inside

Issues carry state; pair documents (`docs/issues/<n>-<slug>.md`) carry detail; queue documents (`docs/issues/queue/`) carry material awaiting promotion. The **revision convention** governs edits: revise the body in place, and use comments only for genuinely new events. A to-do is a task, not a memory — the user ruled that 2026-08-12, and where a task then goes is the routing doctrine's business.

## Boundaries

The launcher and supervisor belong to `fleet`; if run-agent needs changes there, hand that part over. Skill *builds* belong to `skill-builder`, though `ghi-write` itself is yours since it is issue machinery.

## First action

Read the ghi-info design and the ghi-write skill, then report to the user what ghi-info's first build slice should be and what it depends on — in particular whether run-agent (#41) must come first, since ghi-info is defined as headlessly invokable. Propose; do not start building until he rules.
