# `ghi` — seat instructions

Read [the seat model](../nedschorus-wiki/agent-seat-model.md) first: it defines the words used here — seat, walked approval, handoff.

Your work is **GitHub-issue knowledge and the tooling around it**. "GHI" is this project's shorthand for a GitHub issue. Most of this seat's work shares one doctrine — how the project decides what becomes an issue, what goes in a GHI-MD, and what waits in a queue — and one design document, `docs/issues/46-ghi-info-agent-design.md`. One item, [#39](https://github.com/nedschorus/nedschorus/issues/39), does not: it is memory instrumentation, and it sits here under the seat model's cheapest-context rule rather than under the shared doctrine, because it is hook work of the same shape and too small for a seat of its own. Do not use the doctrine as a test of what belongs to you; use this list.

## Reading order

1. [The seat model](../nedschorus-wiki/agent-seat-model.md) — the vocabulary above.
2. `docs/issues/46-ghi-info-agent-design.md` — the design you are building to.
3. `.claude/skills/ghi-write/SKILL.md` — before your first issue write, and you will write constantly.

## The main build: ghi-info

[nedschorus#46](https://github.com/nedschorus/nedschorus/issues/46). The design landed 2026-08-11 after a cold read; it was extracted from a walk and rewritten to stand on its own, so it reads without the walk that produced it. **Part of it is built.** Three scripts are on main, each with its test file beside it (`scripts/<name>-test.py`):

- `scripts/ghi-mirror-refresh.py` (landed 2026-08-22) regenerates the mirror described below: a delta refresh by default, and a full rebuild with `--full` or when it finds no cache, which also drops any issue GitHub no longer returns.
- `scripts/ghi-info-ask.py` (landed 2026-08-22) asks ghi-info. It refreshes the mirror, resumes ghi-info by its stored session id or starts it fresh, checks every issue in the reply against the mirror, and prints the reply; on any failure it exits 1, and the caller falls back. Run on the Mac, it re-runs itself on the box over SSH.
- `scripts/ghi-issue-body-edit.py` (landed 2026-09-08) replaces an issue's body only if the body still matches the copy the caller read; otherwise it refuses, prints the difference, and writes nothing. It is that conflict check alone, not the write tool.

The rest of #46 is not built: the write tool `scripts/ghi-issue-write.py` and its hook `.claude/hooks/ghi-issue-write-redirect.py`, and everything under the design's § Maintenance and fixers. The write tool is the live work. For those parts, treat the design's descriptions as intent the build must honour, not as behaviour you can invoke today; the requirements ruled since the design landed are in #46's body.

What it is, as designed: a dedicated agent that answers, for an issue write about to happen, which existing issues the author should have read. Its corpus is the issues and nothing else — asked about the wiki or the code it returns a fixed `out-of-scope` reply, and asked whether an old ruling still binds it returns `escalate:` rather than deciding. Both replies pass through to the caller verbatim, and the caller must not swallow them. It lives on the box at `~/agents/ghi-info`, is resumed headlessly for each question, and answers on exit; Mac-side callers reach it over SSH.

Its answers come from a local mirror of issue state, `ghi-mirror/` in the checkout: ghi-info reads mirror files only and never calls GitHub itself. The reason is its purpose — asking must stay cheap and fast. This is not a prohibition on live calls generally; it is a boundary on ghi-info. The *caller's* fallback ladder in `ghi-write` does drop to live `gh` calls when the ask fails, and that is sanctioned.

Answering confidently from a silently stale mirror — one missing (first run), out of date, or holding an issue since closed or edited — is the failure mode that matters here, because the caller cannot see it. The built scripts cover each case: a refresh that finds no cache rebuilds in full; every ask refreshes first, and a resumed ghi-info is told which issues changed; and a reply naming an issue that has since closed, when the caller did not pass `--include-closed`, costs one recheck before it is printed.

One thing to raise with the user rather than decide: whether ghi-info is a seat. The design document calls it one and launches it with the seat launcher, but the seat model says seven seats are defined and does not list it. Both cannot be right, and the answer has consequences — whether it counts against the ceiling on seats running at once, whether it gets a supervisor and handoff files, and whether any operation that walks `~/agents/*` (the retirement step `git worktree remove ~/agents/<seat>` in particular) would destroy it. Do not resolve this by editing either document; report it.

Two rulings to know before touching it:

- **The direction was settled against a gate.** An earlier plan, `docs/drafts/ghi-gatekeeper-plan-draft.md`, proposed one program holding the only path to every issue write. The user rejected it 2026-08-07 at walk item 1, and the file survives marked SUPERSEDED as the record of that direction — read it before proposing anything gate-shaped. His stated reason gives you the test: the problem was never unmediated access, it was that an agent about to write does not know which issues it should have read. So what is rejected is *mediating access* — a program that is the only door and fails closed. What replaced it, and is accepted, is *advisory adjudication that fails open* plus the judgment `ghi-write` carries. The write tool refusing a duplicate is not the rejected shape; a credential that makes writes impossible without it is.
- **Write refusals are soft.** The refusals come from the write tool, `scripts/ghi-issue-write.py` — designed in #46, not yet built; the conflict check in `scripts/ghi-issue-body-edit.py` is to be absorbed into it. A refusal's one job is a deliberate second look. An agent still convinced after reconsidering writes its reasoning into `.ghi-issue-write-reconsidered` at the repository root and resubmits; the marker passes exactly one write and is consumed by it. There is no user-approval branch and no forced escalation, and adjudication failing open means infrastructure trouble never produces a refusal. What the design does not say — and the build must — is what happens on a *second* refusal after the marker is spent, and what the tool does if it finds a marker already present.

The `ghi-write` skill (`.claude/skills/ghi-write/`) is live and governs issue writes: filing, editing a body, commenting, closing, and the `draft` label that carries queue membership. Read the skill for the current list rather than trusting this sentence; other GitHub write operations it does not name — assigning, milestones — are simply outside it. Note that the skill tells callers to ask ghi-info first, through `scripts/ghi-info-ask.py`, and to fall back when that ask fails; the ask script exists, so the fallback covers only an ask that fails. The skill still names the unbuilt write tool: its comment step routes through the tool's comment verb, and until #46 builds the tool, plain `gh issue comment` naming the event kind is the interim path. Its edit step is plain `gh issue edit`; it does not name `scripts/ghi-issue-body-edit.py`.

`ghi-write` is yours to change, but it lives under `.claude/`, which makes it an agent-instructions file: it changes only with the user's walked approval, recorded by quoting his words into `.walk-approved` and enforced by `.claude/hooks/instruction-file-guard.py`. Ownership here means you propose and draft the change; it does not mean you commit one unwalked.

## The companions

- [#41](https://github.com/nedschorus/nedschorus/issues/41) **run-agent** — one command that invokes an agent headlessly, callable from shell or from Python, and able to drive either runtime: Claude or Codex. The ask did not wait for it — `scripts/ghi-info-ask.py` calls `claude -p` directly — but the design launches the one-shot agents of its § Maintenance and fixers through run-agent.
- [#42](https://github.com/nedschorus/nedschorus/issues/42) **reference-integrity checker** — verifying that links resolve and that in-repo paths cited in issue bodies and documents actually exist on main. A pure-code check. The issue is also the standing home for the broader question of what else code can check instead of an LLM — a home, not a survey you must exhaust: "designed or ruled out" means a written scope for the checker itself, and the broader question stays open there afterwards. It serves this project's axis directly — deterministic code over LLM prompts wherever the choice exists, mechanical guarantees over trained habit.
- [#39](https://github.com/nedschorus/nedschorus/issues/39) **memory instrumentation** — echoing memory reads and writes as they pass through the paths a hook can observe; hooks that remind rather than block, with no context injection. Two limits to settle rather than assume, because the issue does not: what the coverage boundary is, since reads the harness surfaces as recalled context, direct filesystem access, and files touched by another session or a plain editor all bypass hooks; and who the reminder is for, since "remind rather than block, with no context injection" means the agent does not receive it, while a headless or unattended run has no human at a console to read it either. Read the issue for the scope actually being asked for, and treat those two as questions for the user.

## The doctrine you work inside

Issues carry state; GHI-MDs (`docs/issues/<n>-<slug>.md`) carry substance; queue documents (`docs/issues/queue/`) hold material whose fate is undecided. Edits revise an issue body in place; a comment is only for the event kinds `ghi-write` names — an instance outcome or a challenge to a ruling — and completion is neither, being a body edit plus a close with its reason. The memory-versus-task rule is in `CLAUDE.md` at the repository root; read it there rather than from a shorter copy here. The routing rules live in `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md` § Project organization.

## Boundaries

The launcher (`scripts/launch-claude-ubuntu`) and the supervisor (`scripts/handoff-supervisor.py`) belong to `fleet`; if run-agent needs changes in them, tell the user rather than editing them yourself. A seat's only channel to another seat is through him — not because the commands would fail, but because routing work is his call. Skill *builds* belong to `skill-builder`; `ghi-write` is the exception noted above, because it is issue machinery rather than a general skill.

## First action

Read the three documents in the reading order above, and #46's body for the write tool's requirements ruled since the design landed. Then report to the user what the write tool's first build-slice should be. Propose; do not start building until he rules.
