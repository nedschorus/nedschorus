# Ubuntu fleet — open work inventory and thread map

Snapshot taken 2026-08-13 for [nedschorus#45](https://github.com/nedschorus/nedschorus/issues/45), to divide the box's open work among a small number of named agents. Written because parallel sessions accumulated faster than anyone tracked them: forks were used to park context for later, successors wrote handoffs describing their *present* state rather than their fork point, and several threads ended up overlapping. Operational snapshot, not a standing design — the PR and issue rows go stale as they land; the thread map and the context-file paths stay useful.

## 1. Open pull requests

| PR | Branch | What it carries | Owner stream |
|---|---|---|---|
| [#51](https://github.com/nedschorus/nedschorus/pull/51) | `walk-and-md-review-skill-rules` | walk choice items are proposals; md-review delivers piecemeal under a Monitor | choirmaster |
| [#52](https://github.com/nedschorus/nedschorus/pull/52) | `fast-handoff-findings-applied` | fast-handoff sanity-check findings applied, design doc gutted | choirmaster |
| [#53](https://github.com/nedschorus/nedschorus/pull/53) | `sanity-checker-attack-split-experiment` | three attack prompts, `scripts/md-drift-lint.py`, twelve scored cells | choirmaster |
| [#55](https://github.com/nedschorus/nedschorus/pull/55) | `claude/gatekeeper-audit-account-case-and-rulings-fold` | audit compares account names case-insensitively; #49 review rulings folded into the slice plan | a third stream |
| [#57](https://github.com/nedschorus/nedschorus/pull/57) | `launch-claude-machine-named-launchers` | machine-named launchers + Mac twin, fleet paths reference, supervisor branch sync, session riders | gatekeeper-walk-fork |

All five are open and awaiting the Mac-side review-and-merge seat. They do not conflict: different files, different branches.

## 2. Decisions waiting on the user

1. **The sanity-checker grid seat** — whether the sanity-checker joins the md-review grid as three stance attacks (cut, mechanization, fresh-eyes) across Fable and gpt-5.6-sol at xhigh. Evidence is in `md-review-records/2026-08-12-attack-split-experiment/scorecard.md` and PR #53; the split beat the unsplit baseline. Job `ea663864` has been blocked on this ruling.
2. **Which comes first** — that grid-seat walk, or triage of the novel findings below. This is the question `ea663864` asked and never got answered.
3. **The gatekeeper's remaining road**, all user-gated: the walked-approval evidence format, then build slice 6 (the review-evidence check), then the credential work. Until then the gate stays dormant.

## 3. Un-triaged novel findings (from the attack-split experiment)

Surfaced beyond both ground-truth sets, never presented, each needing verification against current code before any walk — the cells read archived snapshots:

- The gatekeeper spec's "when a test suite exists, the tests run here" never fired, though the suite now exists — so the gate runs no checks today.
- No gate-edits-the-gate guard.
- A writer-stamps-the-pin proposal, to stop agents hand-writing 40-character SHAs.
- The wedged-but-light session: stalls below the recycle threshold with no watchdog.

## 4. Open issues, grouped

Twenty-four open. By theme, for splitting:

- **Fleet and sessions:** #45 (named agents), #50 (worktree file hygiene), #34 (successors must state git context), #37 (turn/steer equivalents), #27 (console insertion, stuck-state detection), #40 (harden the box).
- **Review and skills:** #24 (queue drain), #23 (eval-agent-change), #22 (review-change), #21 (diagnose-failure), #20 (implement-with-evidence), #19 (attack-artifact), #18 (write-test-plan), #17 (design-change), #38 (watch-your-back), #36 (mutual oversight), #26 (dynamic agent-team model).
- **GHI and tooling:** #46 (ghi-info), #41 (run-agent CLI), #42 (reference-integrity checker), #39 (memory instrumentation).
- **Doctrine and research:** #44 (import-tracking doctrine), #35 (usage-vs-expectation), #33 (fast-handoff pickup superseded), #32 (what NC preserves), #31 (review-system requirements), #30 (trigger-first delivery), #29 and #28 (research bundles), #25 (check-in timing).

## 5. Thread map — where each thread's context lives

Transcripts are the durable context. A new session can be pointed at any of these regardless of which agent name it runs under (see § 6).

| Thread | Job | Transcript (context) | State |
|---|---|---|---|
| gatekeeper + launchers (this stream) | `ec9045a3` | `~/.claude/projects/-home-nedlern-Projects-nedschorus--claude-worktrees-gatekeeper-walk-fork-continuation/ec9045a3-6202-4cdc-9fb2-d855d62585cc.jsonl` | live; PR #57 open; handoff at `~/.claude/handoffs/gatekeeper-walk-fork-handoff.md` |
| choirmaster stream, current | `ea663864` | `~/.claude/projects/-home-nedlern-agents-choirmaster/ea663864-8dd4-4734-a0e7-a0c65d5eb1de.jsonl` | live, blocked on the ruling above |
| choirmaster stream, predecessor | `49e0a3cf` | `~/.claude/projects/-home-nedlern-agents-choirmaster/49e0a3cf-4ebc-41d9-9417-3edafe0e2aa8.jsonl` (3.6 MB) | retired; handoff consumed |
| code-review prompt drafting | — | `~/.claude/projects/-home-nedlern-agents-choirmaster/29d66917-9767-47cb-a221-d4876d8014cd.jsonl` (3.6 MB, "Draft code review prompt for reliability improvement") | unclaimed; substantial context, no live session |
| sanity-checker | `d9eda3ec` | `~/.claude/projects/-home-nedlern-agents-choirmaster/d9eda3ec-*.jsonl` | retired; handoff written |
| login session | `3d8bf995` | `~/.claude/projects/-home-nedlern/3d8bf995-*.jsonl` | never had a task; delete |
| tmux seat | `f741668d` | `~/.claude/projects/-home-nedlern-agents-choirmaster/f741668d-*.jsonl` | duplicate of the choirmaster stream; resolve against `ea663864` |

### Complete transcript sweep (2026-08-13)

All 35 transcripts over 30 KB were read for their titles, not just the ones already known. What it added beyond the table above:

**Two unowned threads with real content.**

- `29d66917` (3.67 MB, last written 2026-08-13 20:30) — *"Draft code review prompt for reliability improvement."* Substantial drafting work in `~/agents/choirmaster`, no live session, mentioned in no handoff. Its natural home is whichever seat takes the review-and-skills work.
- A second project entirely: **nedsmessenger**, under `~/.claude/projects/-home-nedlern-agent-nedsmessenger/`, five sessions from 2026-08-03/04 totalling ~4 MB — *"Reorganize GitHub repos and GitHub Apps"* (1.15 MB), *"Create Samba links for Typora file access"* (1.38 MB), *"Review backup alert system improvements"* (1.13 MB), *"Merge PR #37 and resolve branch conflicts with main"*, and a test-message thread. Untouched for ten days. Whether that project is still live is the user's call; it is not nedschorus work and would want its own seat if revived.

**Everything else is accounted for.** The remaining transcripts fall into three groups, none needing an owner: predecessor generations of the two live streams (`5a7d955e`, `d9eda3ec`, `49e0a3cf`, `574972e0`, `1caf1c51`, `ccc79ae5`, plus the gatekeeper worktree's own `b2912831`, `27862506`, `0550ed74`); **md-review and experiment cells** whose findings already live in `md-review-records/` (`3766ca30`, `84a8a260`, `946596c0`, `0f34ff59` from the 2026-08-09 grid; `832f3b95`, `9cd26c95`, `0e711797`, `99a2f1a4` from the sanity-checker draft review; `8d89bd09`, `83e22b1a`, `849436bf`, `9aae839c`, `cd59239a`, `82f21e87` from the 2026-08-12 attack-split experiment); and two box-maintenance sessions from July (`bab1c2b3` security audit, `c75a8d63` upgrade).

Preserved handoffs and dialog extracts, all under `~/.claude/handoffs/`: the choirmaster and gatekeeper-walk-fork handoffs plus their numbered generations, and matching `-dialog-` files carrying each session's conversation tail.

## 6. How to give a new agent someone else's handoff

The supervisor reads `~/.claude/handoffs/<agent>-handoff.md`, where `<agent>` is the name passed to the launcher — so by default an agent only sees its own. Two supported ways around that, both already built:

1. **`--first-prompt-file <path>`** — the launcher passes it through to the supervisor, which reads that file as the new session's first prompt and then reverts to ordinary ignition. This is the intended mechanism for seeding a session from arbitrary context: point it at another thread's handoff, its dialog extract, or a purpose-written brief.
2. **Copy the handoff to the new name** — `cp ~/.claude/handoffs/<old>-handoff.md ~/.claude/handoffs/<new>-handoff.md` before launching `<new>`; its supervisor picks it up as if it were its own.

Either way, a handoff written by a *forked* session describes that session's state when it wrote the handoff, not the fork point. When the fork point is what matters, point the new session at the `-dialog-` extract or the transcript instead, and say in the first prompt which part of the history is the subject.

## 6a. Seats launched 2026-08-13, and how

`gatekeeper` and `sanity-checker` are running on the box, each in `~/agents/<seat>` on its own branch, reading the reviewed versions of their briefs. Both were verified to start correctly: branch confirmed, status line present (which is the tell that project settings loaded, and therefore that the recycle hook and the instruction-file guard loaded too).

They were **not** launched by the documented recipe, because that recipe cannot work yet: it reads `docs/agents/seat-first-prompt.md` from the box's checkout of main, and that file is still in PR #58 along with every md-review correction to the briefs. Launching from main would have booted both seats into the pre-review documents — the ones carrying twenty to thirty findings each.

What was done instead, and what to undo once #58 merges:

1. Each seat's worktree was created from the PR branch rather than main: `git worktree add ~/agents/<seat> -b <seat> seat-launch-first-prompt`. The launcher skips creating a home that is already a checkout, so this simply pre-empts it.
2. The launcher was then run with the prompt file taken from the seat's own checkout: `sh scripts/launch-claude-mac <seat> --no-attach --first-prompt-file /home/nedlern/agents/<seat>/docs/agents/seat-first-prompt.md`. The Mac twin runs locally on the box and is mechanically identical to the Ubuntu launcher minus the SSH hop, which is what makes it usable from a box-side session.

Consequence to expect: each seat's branch carries PR #58's commits, so the supervisor's branch sync will report it as *ahead of main* and change nothing. Once #58 merges, those branches become strictly behind and fast-forward normally. No action is needed unless #58 is changed substantially before merging, in which case the seats should be relaunched from the merged main.

## 7. Proposed split into named agents

Three seats, chosen so no two touch the same files or branches:

- **`gatekeeper`** — the gatekeeper's remaining road (evidence format → slice 6 → credential work), plus PR #55 and PR #57, plus the fleet and session issues (#45, #50, #34). Context: this stream's transcript and handoff.
- **`reviewer`** — the sanity-checker grid-seat decision, the novel-findings triage, PRs #51/#52/#53, and the candidate-skill issues (#17–#23). Context: `ea663864`'s transcript, and `29d66917` for the code-review prompt work.
- **`ghi`** — ghi-info (#46) and its neighbours (#41, #42, #39). Context: the ghi design documents already in the repo.

Each seat gets its own agent home and therefore its own branch, which is what keeps them from colliding. Start with two if three is too many at once; the third can wait.
