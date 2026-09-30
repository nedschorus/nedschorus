---
issue: "[Mutual oversight: agents watch each other's session transcripts, both runtimes — capability record + lean build candidate](https://github.com/nedschorus/nedschorus/issues/36)"
---

# Mutual oversight: agents watch each other's session transcripts, both runtimes — capability record + lean build candidate

Boss-named capability ("mutual oversight" — his replacement for "spying"), boss-directed GHI 2026-07-29, filed by new-vp (nedlern session b6241858). Capability record plus build candidate: **agents watch each other's session transcripts, in both runtime directions**, so one agent can follow another's work in near-real time without the human ferrying content between sessions.

## What is proven today (all evidence verified on disk before filing)

- **Claude watching Codex: works now, no build.** The Claude harness's Monitor tool arms a persistent watcher whose emitted lines wake the idle session (measured: 5/5 no-keystroke wakes, ~3.0–3.8s to first model activity). Codex rollout transcripts grow live at `~/.codex/sessions/<date>/rollout-*.jsonl` with parseable turn boundaries (`event_msg` `task_started`/`task_complete`, `turn_context`, role-bearing `response_item`/`message`). Caveat, honestly held: the rollout schema is internal and not promised stable.
- **Codex reading Claude: proven live.** During the research task the Codex agent read a growing Claude transcript (`~/.claude/projects/<project-dir>/<session-id>.jsonl`) mid-task.
- **Codex being woken: needs a thin build.** Codex CLI 0.145.0 has no Monitor equivalent; MCP resource-change notifications have no official evidence of starting a model turn; Codex notify/hooks are outbound-only. The wake path that DOES exist: App Server `turn/start` (inject into an idle thread) and `turn/steer` (into an active turn).
- **Live usage specimen (2026-07-29):** during a dual-conversation walk, the fleet-side Claude agent followed the boss's Mac-app session by Monitor on its transcript — rulings flowed between two conversations with the human ferrying only nudges. Observer and discussant proved to be distinct, complementary roles (the observer caught record-forking and stale-copy hazards the discussant could not see).

## The build candidate (lean; at or after NC kickoff; boss-gated like everything NC)

A Codex-side monitor: file-change detection (watchexec, established OSS) → saved byte offset → parse only complete appended JSONL records → inject selected record/text via App Server `turn/start`. Filtering, redaction, dedupe, and backpressure are production hardening, not conceptual prerequisites. No build has been attempted anywhere; research was read-only.

## Evidence and references

- Research report (machine-local session artifact, verified 11.9KB): `/Users/el/Projects/nedlern-sonnet/cvp/tasks/sessions/cvp-cross-agent-jsonl-monitor-research-2026-07-29.md` — **re-home this file if this GHI outlives the legacy worktrees**; it is not repository-committed.
- Wake-canary evidence (verified): `/Users/el/Projects/nedlern-sonnet/cvp/tasks/sessions/cvp-monitor-wake-canary-2026-07-28.md`
- Official docs cited by the research: Claude Code Monitor tool — https://code.claude.com/docs/en/tools-reference#monitor-tool ; Codex App Server — https://learn.chatgpt.com/docs/app-server ; watchexec — https://github.com/watchexec/watchexec
- Research: cvp (Codex runtime), 2026-07-29, boss-directed, relayed and verified by new-vp. Related: the session-lifecycle observations on GHI [Runtime-behavior research bundle: instruction compression + deliberate scrub, instruction precedence, output styles, context clearing, names reviewer, memory maintenance](https://github.com/nedschorus/nedschorus/issues/29) (transcript identity and store keying) and the comms-bridge/companion design surfaces this capability may partially subsume.

## Outcome

Closed as not planned on 2026-09-29, by the user's "y" to item 2 of the walk eight-deferrals-with-no-trigger-2026-09-29, shown updated at his request ("repeat 2, updated"). Minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/eight-deferrals-with-no-trigger-2026-09-29-minutes.md`.

Nothing left in this issue needs building:

- **Claude watching Claude already runs.** The Mac merge-lane seat follows the other seats' dialogs on both machines with `scripts/watch-agent-dialogs.py`.
- **No nedschorus seat runs Codex, so there is no Codex session to wake.** In this repository Codex runs only as a one-shot reviewer: `scripts/code-review-codex-cell.py`, the cold-read Codex cell `nc-systems/cold-read/cold-read-codex-cell.py`, and `scripts/sanity-check-attacks.py`. Outside nedschorus, the legacy nedlern checkout runs a Codex App Server adapter on the Mac, `/Users/el/Projects/nedlern/scripts/codex-app-server-adapter.py`; whoever reopens the Codex wake path starts from that adapter.
- **The oversight the user asked for during the walk does not need a transcript watcher.** Spotting a seat's open tasks stranded after the seat is retired or renamed is a check a program runs, and checking whether another seat is already on a piece of work is the asking agent reading every seat's task list itself, with the task viewer `scripts/seat-task-list-read.py`, which reads the task lists of the seats on both machines. Both are proposed to the user as a small task subsystem, recorded under "Side rulings and open questions" in the same walk's minutes and still open with him.
