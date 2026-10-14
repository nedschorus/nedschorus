# The handoff-system: architecture overview

This document has proposed improvements or changes: read every file in this folder whose name starts with `nedschorus-handoff-architecture-overview-proposed-improvements-or-changes-`.

## Purpose

The handoff-system keeps an agent-seat working across many agent-sessions. When an agent-session's context window runs low, it has the agent write a session-handoff and replaces the agent-session with a fresh one that continues from the session-handoff and the conversation-tail; when an agent-session or its machine dies, it can bring the agent-seat back, resuming the dead agent-session where it can. In go an agent-seat's name, the next step its agent writes with whether to ask the user before relaunching, and Claude Code's transcripts; out comes a supervised agent-session in the agent-seat's tmux pane, with initial-agent-instructions saying where to pick up.

## Architectural pattern

A supervisor and the process it launches: on each machine, one handoff-supervisor per agent-seat runs as the command of the agent-seat's tmux pane, launches `claude` as its child process, waits for a session-handoff or the child's exit, and starts the next agent-session, fresh or resumed from the transcript. Hooks inside the agent-session ask for the session-handoff and keep work-snapshots, and reach the handoff-supervisor only through files on the machine; launchers start the handoff-supervisor, and `recover-crashed-seats.py` and `resupervise-seat.py` start it again when it is gone. The rulings behind the system, and their reasons, are in `nc-systems/handoff/handoff-design.md`; the code is what the system does.

```
person on the Mac ──> launch-claude-mac / launch-claude-ubuntu ──> tmux pane ──> handoff-supervisor.py
login or boot ──> restart-live-seats-at-login.py ──> recover-crashed-seats.py ──> launcher or tmux pane
handoff-supervisor.py ──launches, kills, resumes──> claude (agent-session)
threshold hook ──asks──> agent ──/handoff──> handoff-write-and-check-supervisor.py ──> <seat>-handoff.md
handoff-supervisor.py ──reads <seat>-handoff.md, kills claude, runs handoff-extract-conversation.py, launches──> successor
```

## Components

**`nc-systems/handoff/handoff-supervisor.py`**, the handoff-supervisor. It holds the agent-seat's lock for its whole life, heartbeats into its state file, and launches `claude` named after the agent-seat, both in the pane and on Claude Code's Remote Control, where agents on the other machine address the agent-seat by that name. Before each launch it tries to update `claude`, and, in a step it reports as the branch sync, fast-forwards the agent-seat's working directory to main when the branch is strictly behind main and no uncommitted tracked change or git operation in progress stops it, launching either way. At a session-handoff it kills the agent-session, asks the user first if the session-handoff says to, runs the extractor (`handoff-extract-conversation.py`), removes worktrees `scripts/clean-worktrees.py` judges removable, and launches the successor with initial-agent-instructions naming the conversation-tail, the next step, the branch sync's result, the subagents still working when the session-handoff was written, and, on the Mac from noon Pacific when one is due, the day's memory review, an approval-walk on the notes agents saved in Claude Code's memory; if the extraction fails, it stops and leaves the session-handoff waiting. For the agent-seat agent-instructions-editor alone, the initial-agent-instructions also carry an overview refresh reminder for each system whose non-Markdown code under `nc-systems/<system>/` has moved past the commit its overview's last line names, unless an open pull request already changes that overview. Every launch also lists the agent-seat's lost work-snapshots, those whose `claude` process has ended and whose worktree no longer holds their changes. When the agent-session dies without a session-handoff, it resumes that agent-session after a signal or an error exit when it has a terminal, again only if the last resume added to the transcript, and otherwise records the exit and stops. With no session-handoff waiting and no recorded exit, its first launch resumes the agent-seat's last transcript worth resuming, as `scripts/seat-transcript-worth-resuming.py` defines it, or else starts fresh; with a recorded exit, it starts fresh; in either case it resumes a transcript it is given, and starts fresh when told its first prompt wins over a crashed transcript.

**`nc-systems/handoff/handoff-write-and-check-supervisor.py`**, the writer script. Apart from the next step and whether the user wants to be asked before a relaunch, the writer computes every field of the session-handoff; it writes `<seat>-handoff.md` under the name the handoff-supervisor watches, refuses, unless told to claim the name, a name that would leave a session-handoff unread, prints the main-gatekeeper's audit of branch protection, which never stops the session-handoff being written, and reports whether a handoff-supervisor is watching.

- `scripts/launch-claude-mac`: run on the Mac, creates a Mac agent-seat's agent-home and seat-branch when missing, and starts the agent-seat on its own tmux server with the handoff-supervisor from the launcher's own checkout as the pane's command, or attaches to it.
- `scripts/launch-claude-ubuntu`: run on the Mac, does the same for a ned-box agent-seat over ssh, with the handoff-supervisor from ned-box's clone at `~/Projects/nedschorus`.
- `scripts/handoff-context-threshold-hook.py`, the threshold hook, a `Stop` hook: at a set share of the context window, tells the agent to run the /handoff skill, once until the next compaction, deferring up to a higher share while a subagent or a recent background task still runs.
- `.claude/skills/handoff/SKILL.md`: the /handoff skill; the agent writes the next step to a file and runs the writer script on it.
- `docs/agents/seat-session-appended-system-prompt.md`: below its `---` line, the text the handoff-supervisor appends to every agent-session's system prompt.
- `scripts/post-compaction-session-continues-hook.py`, the post-compaction hook, a `SessionStart` hook: after a compaction, gives the agent-session the tail of its own dialog and tells it to continue, and deletes the threshold hook's marker file so that hook can ask again.
- `scripts/uncommitted-work-snapshot-hook.py`, a `PostToolUse` hook: after each Edit, Write, NotebookEdit and Bash call, keeps a work-snapshot, owned by the calling `claude` process, of the worktree the call worked in and, after a Bash call, of any worktree that process already has one of, and deletes it once nothing there is uncommitted; it never changes a worktree.
- `nc-systems/handoff/uncommitted-work-snapshots.py`: the work-snapshot module that hook, the handoff-supervisor and `scripts/clean-worktrees.py` share; design in `nc-systems/handoff/uncommitted-work-snapshots-across-crashes-design.md`.
- `scripts/handoff-extract-conversation.py`, the extractor: writes the conversation-tail from the outgoing agent-session's transcript, and the whole filtered dialog beside it when the tail leaves turns out.
- `nc-systems/handoff/handoff-census-user-record-shapes.py`, the census: counts the kinds of user record in the top-level transcripts, to find injected text the extractor should drop.
- `scripts/seat-transcript-worth-resuming.py`: the one definition, for the handoff-supervisor and `recover-crashed-seats.py`, of a transcript worth resuming.
- `scripts/agent-binary-update-under-lock.py`: updates `claude` for a launcher or the handoff-supervisor, skipping the update when another holds `agent-binary-update.lock`.
- `scripts/checkout-freshness-catch-up.py`, a `Stop` hook outside this system: the branch sync uses its checks for uncommitted tracked changes and a git operation in progress.
- `scripts/architecture-overview-path-template-and-checked-against-commit-reader.py`: gives an architecture overview's path and reads the commit its last line names, for the handoff-supervisor's overview refresh reminder.
- `nc-systems/handoff/daily-memory-review-mark.py`: marks the day's memory review started or done, and holds the readers the handoff-supervisor's memory review check uses.
- `nc-systems/handoff/daily-overview-refresh-reminder-mark.py`: marks that the user was shown a system's overview refresh, so the handoff-supervisor withholds that system's overview refresh reminder for the rest of the Pacific day.
- `scripts/clean-worktrees.py`: removes worktrees under `.claude/worktrees/` whose branch has nothing main lacks and that no process uses, uncommitted files included, and merged branches, and deletes lost work-snapshots once they have been listed for long enough.
- `scripts/resupervise-seat.py`: puts an agent-seat running without a handoff-supervisor back under one from a waiting session-handoff, killing the unsupervised agent-session's tmux session.
- `scripts/recover-crashed-seats.py`: brings back an agent-seat whose handoff-supervisor is gone, resuming its last transcript worth resuming, or starting fresh from its newest conversation-tail when there is none, or, when a session-handoff waits, leaving it to a new handoff-supervisor; it restarts an agent-seat whose exit was recorded only when the person running it says yes, so a run without a terminal leaves such an agent-seat down.
- `scripts/restart-live-seats-at-login.py`, the login restart: hands `recover-crashed-seats.py` each agent-seat whose heartbeat places it at the machine's stop; on the Mac it also opens a window running `launch-claude-ubuntu` onto each ned-box agent-seat that has a live tmux session.
- `scripts/install-restart-live-seats-at-login-launch-agent.py` and `scripts/install-restart-live-seats-at-login-systemd-unit.py`: install what runs the login restart on the Mac and on ned-box.
- `nc-systems/handoff/agent-seat-state-records-reader.py`, the records reader: the rules for reading an agent-seat's records from its files, for the login restart, `recover-crashed-seats.py` and `scripts/seat-task-list-read.py`; it re-exports the handoff-supervisor's readers, which own the file names.

## Invariants

- No program but the handoff-supervisor starts or resumes an agent-seat's agent-session; the launchers, `recover-crashed-seats.py` and `resupervise-seat.py` start a handoff-supervisor, and the writer script starts nothing, because an agent cannot end its own agent-session. A person who runs `claude` by hand gets an unsupervised agent-session, which `resupervise-seat.py` repairs.
- When a session-handoff arrives or its agent-session dies, a handoff-supervisor starts the next agent-session only when it has a terminal, since the child inherits its stdio; without one it stops, leaving a handed-off agent-session running, which is why it runs as the tmux pane's command.
- At most one handoff-supervisor per agent-seat name runs on a machine, because each holds that name's lock in the handoff directory; nothing stops the name running on the other machine too, although its Remote Control name then answers on both.
- A handoff-supervisor is alive when the process its lock file names runs `handoff-supervisor.py` for that agent-seat; the heartbeat decides only which agent-seats the login restart brings back.
- Every path that starts a handoff-supervisor sets `CLAUDE_CODE_TASK_LIST_ID`, and the handoff-supervisor refuses to start without it, so every agent-session of an agent-seat on one machine opens the same task list.
- Apart from the next step and the question whether to ask before a relaunch, the writer script computes the session-handoff, and the extractor cuts the conversation-tail by a minimum word count, so the outgoing agent's judgment shapes neither the other fields nor the tail.
- A handoff-supervisor that outlives its agent-session records the exit before stopping, so `recover-crashed-seats.py` can tell a stop from a crash.
- Session-handoffs and work-snapshots stay off every branch; the Mac's session-handoffs are also copied to the log-store on ned-box by `scripts/transcript-mirror-to-log-store.py`.
- The handoff-supervisor of a ned-box agent-seat, or of one `recover-crashed-seats.py` brings back, runs from the clone's main worktree at `~/Projects/nedschorus`, never a linked worktree, because it runs the extractor from its own checkout and a linked worktree can be removed under it; a Mac agent-seat's runs from whichever checkout its launcher was run from.

## Shared state

Unless named otherwise, files are in `~/.claude/handoffs/` on the agent-seat's machine.

- `<seat>-handoff.md`, the session-handoff: written by the writer script; read by the writer script, `handoff-supervisor.py` and `resupervise-seat.py` directly, and by `recover-crashed-seats.py` through the records reader. A session-handoff is waiting while its restart counter is above the one the state file records as consumed.
- `<seat>-handoff-NNNN.md`: copies of consumed session-handoffs, kept by `handoff-supervisor.py`, which keeps the two newest generations of these and of the dialog files.
- `<seat>-supervisor.lock`: held with flock by `handoff-supervisor.py`, which writes its process ID there; read for liveness by the writer script, `resupervise-seat.py` and `recover-crashed-seats.py`.
- `<seat>-supervisor-state.json`, holding the heartbeat, the exit record and the consumed restart counter: written only by `handoff-supervisor.py`; read by the writer script, `resupervise-seat.py`, `recover-crashed-seats.py` and `restart-live-seats-at-login.py`.
- `<seat>-dialog-NNNN.md`, the conversation-tail, and `<seat>-dialog-NNNN-complete.md`, the whole filtered dialog: written by `handoff-extract-conversation.py`; read by the successor, and by `recover-crashed-seats.py` when no transcript is worth resuming.
- The prompt files `recover-crashed-seats.py` writes, such as `<seat>-recovery-ignition-prompt.md`: read by the handoff-supervisor it starts, as that agent-session's first prompt.
- `<session>-handoff-asked` and `<session>-handoff-deferred`, keyed by Claude Code session ID: written by `handoff-context-threshold-hook.py`; the first is deleted by `post-compaction-session-continues-hook.py`.
- `<seat>-work-snapshots-first-listed.json`, recording when each lost work-snapshot was first listed: written through `uncommitted-work-snapshots.py` when the handoff-supervisor lists one; read through the same module by `clean-worktrees.py`, which deletes a lost work-snapshot some days after its first listing.
- `refs/work-snapshots/` in the machine's clone: written by `uncommitted-work-snapshot-hook.py`, listed by `handoff-supervisor.py`, deleted by that hook or by `clean-worktrees.py` through `uncommitted-work-snapshots.py`, or by the agent following the restore steps it is given.
- Transcripts under `~/.claude/projects/`: written by Claude Code; read by the extractor, the threshold hook, the post-compaction hook, the writer script, the census and `seat-transcript-worth-resuming.py`.
- `daily-memory-review-marks/` and `daily-overview-refresh-reminder-marks/` in the log-store on ned-box: written by `daily-memory-review-mark.py` and `daily-overview-refresh-reminder-mark.py`, over ssh from the Mac; read by `handoff-supervisor.py`, the memory review marks only on the Mac, over ssh, and the overview refresh reminder marks only for the agent-seat agent-instructions-editor, on either machine.
- `agent-binary-update.lock` under `~/.local/state/claude/`: taken through `agent-binary-update-under-lock.py` by the launchers and the handoff-supervisor.
- `CLAUDE_CODE_TASK_LIST_ID` and `GIT_AUTHOR_NAME`: set by `launch-claude-mac`, `launch-claude-ubuntu`, and `recover-crashed-seats.py` when it starts a ned-box handoff-supervisor itself; the first is required by `handoff-supervisor.py`, the second names the agent-seat in `uncommitted-work-snapshots.py`.
- `NEDSCHORUS_HANDOFF_SUPERVISOR_AGENT_NAME`, `NEDSCHORUS_HANDOFF_SUPERVISOR_WORKING_DIRECTORY` and `NEDSCHORUS_HANDOFF_SUPERVISOR_SESSION_ID`: set by `handoff-supervisor.py` for its agent-session; read by `handoff-write-and-check-supervisor.py`.
- `LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS`: set by `recover-crashed-seats.py` and `resupervise-seat.py`; passed on to the handoff-supervisor by `launch-claude-mac` and `launch-claude-ubuntu`.
- `NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER`: set by `scripts/ghi-info-ask.py` for its own agent-sessions; silences `handoff-context-threshold-hook.py`.

## Entry points

- The launchers: a person on the Mac; also `resupervise-seat.py`, `recover-crashed-seats.py` on the Mac, and, for `launch-claude-ubuntu`, the login restart on the Mac.
- `handoff-supervisor.py`: a launcher, as the tmux pane's command; on ned-box, also `recover-crashed-seats.py` directly.
- The threshold hook, the post-compaction hook and `uncommitted-work-snapshot-hook.py`: the Claude Code `Stop`, `SessionStart` (after a compaction) and `PostToolUse` events.
- The /handoff skill and the writer script: the agent, when the threshold hook asks or the user requests a session-handoff.
- The two mark programs: an agent-session, as its initial-agent-instructions say.
- `restart-live-seats-at-login.py`: a LaunchAgent at login on the Mac and a systemd user unit at boot on ned-box.
- `recover-crashed-seats.py`: a person, or `restart-live-seats-at-login.py`.
- `clean-worktrees.py`: the `daily-clean-worktrees` job in `nc-systems/general-tools/scheduled-jobs-on-each-machine.json` and the handoff-supervisor at each session-handoff; the launchers run it only to report.
- `resupervise-seat.py`, the census and the install scripts: a person. The `list` command of `uncommitted-work-snapshots.py`: a person, or an agent its initial-agent-instructions send there.

## Planned work

- GHI [Queue drain procedure — the review process that empties the wiki queue, the pair queue, nc-queue, docs/drafts and the draft-label issue queue](https://github.com/nedschorus/nedschorus/issues/24)
- GHI [Console text-insertion + stuck/waiting-state detection (operator tooling; captured from the comms backlog)](https://github.com/nedschorus/nedschorus/issues/27)
- GHI [Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires](https://github.com/nedschorus/nedschorus/issues/45)
- GHI [Fleet survives a machine restart without losing seat context: detect, hand off on notice, relaunch at boot, resume from transcript](https://github.com/nedschorus/nedschorus/issues/116)
- GHI [Rationalize the repository layout: group components by owning system under nc-systems/, and a hook dispatcher](https://github.com/nedschorus/nedschorus/issues/224)
- GHI [Before a seat is retired, report what still cites the paths the retirement removes](https://github.com/nedschorus/nedschorus/issues/226)
- GHI [recover-crashed-seats.py: the six changes ruled 2026-09-02 — exit record, process-identity liveness, parking marker, verified restart, by-hand resume, window](https://github.com/nedschorus/nedschorus/issues/242)
- GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670)
- GHI [Handoffs become one pending file per session, archived only after a successor is up](https://github.com/nedschorus/nedschorus/issues/754)
- GHI [A crash-recovered ned-box seat runs without its own GitHub token, and the Mac launcher warns of a missing token when it only attaches](https://github.com/nedschorus/nedschorus/issues/759)
- GHI [Relaunch stopped agent-seats with open tasks daily](https://github.com/nedschorus/nedschorus/issues/936)
- GHI [A small service on ned-box keeps one record of every agent-seat on both machines](https://github.com/nedschorus/nedschorus/issues/972)
- GHI [Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036)
- GHI [Check every prerequisite of the fleet's programs before an agent-session starts](https://github.com/nedschorus/nedschorus/issues/1055)
- GHI [Daily maintenance in one daily step, starting with a daily check of every wiki page](https://github.com/nedschorus/nedschorus/issues/1058)
- GHI [Agent-seat retirement as a program: the agent-seat marks itself retired, the handoff-supervisor confirms with the user and retires it, and the launchers refuse a retired name](https://github.com/nedschorus/nedschorus/issues/1125)
- GHI [Moving an agent-seat to the other machine in one handoff that stops it on the old machine and starts it on the new one without restart prompts](https://github.com/nedschorus/nedschorus/issues/1129)
- GHI [Wake idle agent-seats that have unfinished work, after a usage limit resets and after a change request goes unanswered](https://github.com/nedschorus/nedschorus/issues/1152)

**Checked against:** commit [a3ecd6891054d9005d07a10221e9db8b0fcb5374](https://github.com/nedschorus/nedschorus/commit/a3ecd6891054d9005d07a10221e9db8b0fcb5374)
