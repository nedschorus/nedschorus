# Problem statement: recycling agent sessions before context fills

<!-- fresh-eyes attack input, written 2026-08-12 for the attack-split validation experiment: the problem and goals behind the fast-handoff design, stated without revealing any of that design's decisions. Environment facts an independent designer could learn by probing are included; design choices are not. -->

## The situation

A fleet of AI agent sessions (Claude Code CLI) runs on an Ubuntu box with little human attention — some interactive in terminal panes, some headless. Each session has a finite context window that fills as it works; a session deep into its window gets slower and worse. The work is mostly sequential: old turns are mostly disposable, and the durable output (commits, issue updates, files) is already outside the session in git and on GitHub. The human (the boss) drives from a Mac, is often away, and does not want to type into panes to keep the fleet healthy.

## The problem

Design how a session gets replaced by a fresh one before its context gets heavy — with the successor continuing the work seamlessly — with near-zero routine human intervention, for headless and interactive sessions alike.

## Environment facts (verifiable by probing; you may rely on them)

- Every session writes a JSONL transcript as it runs; each assistant record carries the model id and that request's token usage. Transcripts are readable while the session runs and after it dies.
- The harness keeps a per-session task list in per-session files on disk; a session can be launched with a chosen session id, and it reads whatever task files already sit under that id.
- A fresh session starts with an empty window; instruction files (CLAUDE.md and hooks) reload from disk at launch.
- A session cannot terminate itself: it has no exit command, and sending itself a kill signal is blocked by a safety layer.
- A launch command can pass an opening prompt that fires as the session's first turn.
- The harness can run a configured hook command at every turn boundary; a status line runs only for interactive sessions, never headless ones.
- The rejected easy answers, ruled out before this design: built-in context compaction (summarizes uniformly when value is non-uniform, and slow) and resuming the old session (restores exactly the context being shed).

## The goals

- **No human typing** to keep sessions fresh — the fleet recycles itself; the boss can always trigger or intervene manually.
- **The successor is not dumber than the predecessor:** it continues the current task where it stands, knowing what it was doing and what comes next.
- **Nothing durable is lost** — anything of lasting value must already be, or get put, somewhere durable.
- **Minimal standing infrastructure:** deterministic scripts preferred over daemons and over prompted-agent intermediaries; machine-local operational state is acceptable, but git is the durable record.
- **Failures are contained, not elaborately prevented:** a botched replacement should be a recoverable glitch, not a disaster.

## Out of scope

Moving sessions between machines (ruled a project, not a handoff). Subagents (they are short-lived by construction).
