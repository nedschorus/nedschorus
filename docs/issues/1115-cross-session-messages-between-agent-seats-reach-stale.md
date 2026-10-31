---
issue: "[Save a message that SendMessage queues to an offline Remote Control entry, and deliver it later or have the sender resend it](https://github.com/nedschorus/nedschorus/issues/1115)"
kind: design
status: design pending the user's approval; nothing in § Design is built. The user reviews it in an approval-walk before any of it is built.
---

# Save a message that SendMessage queues to an offline Remote Control entry, and deliver it later or have the sender resend it

Agent-seats message each other with Claude Code's SendMessage tool, by name. A Remote Control entry is one row of the list ListAgents shows for a Claude Code session connected to Remote Control; the row stays, marked offline, when that connection drops or that Claude Code session ends. When SendMessage matches the name to an offline Remote Control entry, it queues the message there and reports success. The message arrives only if that entry reconnects. An entry left behind by an agent-session that has ended never reconnects, so a message queued there is never read; an entry whose agent-session is still running but whose Remote Control connection has dropped does reconnect, and its queued messages then arrive. A sender usually meets such an entry when the recipient agent-seat is between agent-sessions, at a session-handoff, or is stopped. This GHI-MD holds the design of a fix in code: a hook saves every message queued to an offline entry; when the recipient is on ned-box and a handoff-supervisor runs it, the handoff-supervisor gives the saved message to the recipient's next agent-session; otherwise the sender is told to resend the message, and is reminded until a resend carrying it is accepted without the offline notice.

## Decided

- **2026-10-31 07:35 Pacific time, the user approved item 5.1 of merge-lane-2's approval-walk merge-lane-2-open-rulings-2026-10-30** (walk-document `/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-open-rulings-2026-10-30.md`, section "Item 5.1 of 14"; walk-minutes `/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-open-rulings-2026-10-30-minutes.md`, the line "item 5.1 of 14: the user answered approved #approved_obvious #case_against_medium (2026-10-31 07:35)"; both in merge-lane-2's agent-home on ned-box; the walk-minutes record times in Pacific time). What he approved: keep this GHI open, narrowed to a fix in code. A hook on SendMessage spots the reply that says the entry is offline and saves the message. For a recipient on ned-box, the handoff-supervisor gives the saved message to the recipient's next agent-session when it starts that agent-session. For a recipient on the Mac, the sender is told the exact message to resend, and is reminded until a send to that agent-seat goes through. ned-box-helper writes the design here, settling where the message is kept and when it is cleared, and the design comes back to the user before it is built.
- **2026-10-30 20:11 Pacific time, the user disapproved item 5 of the same approval-walk**, which proposed that he archive the offline Remote Control entries on claude.ai by hand (walk-minutes, same file, the line "item 5 of 11: the user answered disapproved (2026-10-30 20:11)"). The by-hand part of this GHI is dropped.
- **2026-10-09, the user asked for the first fix**, that each agent-session be listed under its agent-seat's name ("Itme 4 sounds important. Can you dispatch that to some appropriate agent to fix now?", about 05:20Z in merge-lane-2's agent-session, answering item 4 of the approval-walk merge-lane-2-waiting-on-user-walk-2026-10-07, walk-document `/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-waiting-on-user-walk-2026-10-07.md` in merge-lane-2's agent-home on ned-box). That fix is built: PR [#1118](https://github.com/nedschorus/nedschorus/pull/1118) made `nc-systems/handoff/handoff-supervisor.py` (`launch_agent_session`) start every agent-session with `--name <agent-seat>` and `--remote-control-session-name-prefix <agent-seat>` beside `--remote-control <agent-seat>`.

## The failure this design fixes

SendMessage's reply to a send queued to an offline entry carries `"success": true`, and its text, after the message's summary in quotation marks, ends with "it is offline right now — delivery is queued until that machine reconnects)". Eleven such replies are in merge-lane-2's transcripts on ned-box, in `/home/nedlern/.claude/projects/-home-nedlern-agents-merge-lane-2/`, from 2026-10-06 to 2026-10-31: eight to cold-read-research, two to ned-box-helper, and one to agent-instructions-editor, at 09:03:59Z on 2026-10-31 while that agent-seat's agent-session restarted, in transcript `42c973c1-43a2-403b-b036-8a01bf1587b6.jsonl` (the walk-document says 09:12Z). Nine of the eleven came after PR #1118 merged on 2026-10-09. merge-lane-2 read the last reply and resent the message by hand. An agent that does not read the text of a reply that reports success loses the message, which is why the fix is a hook and not an instruction.

Each of those replies says the recipient is "a Claude session on another machine, over Remote Control", though agent-instructions-editor and ned-box-helper run on ned-box, like the sender. So the reply cannot tell the hook which machine the recipient is on; § The save hook names another test.

Since PR #1118, a sender on the same machine reaches the recipient's running agent-session by the agent-seat's exact name. SendMessage refuses a bare name that matches more than one entry and asks for one entry's short identifier, which ListAgents shows in brackets and calls its ref, such as `[74e8b9]`; such a refusal sends nothing and is not this failure. What is left is a send that SendMessage matches to one offline entry: a bare name that matches only one entry, or a ref that names an offline entry.

## Design

The words used below:

- **offline reply**: a SendMessage reply whose text, after the quoted summary at its start, contains "it is offline right now".
- **accepted send**: a SendMessage reply with `"success": true` that is not an offline reply. An accepted send tells the sender that SendMessage handed the message on; SendMessage reports nothing about whether the recipient read it, so neither does this design.
- **message body**: the `message` field of SendMessage's input.
- **saved file**: one JSON file holding one saved message.

### Where the saved messages are kept

In the handoff directory, `~/.claude/handoffs/`, the directory where the handoff-supervisor already keeps each agent-seat's files, on the machine whose program reads them. There are two kinds of directory:

- **Incoming, on ned-box:** `~/.claude/handoffs/<recipient agent-seat>-incoming-messages-saved-from-offline-remote-control-entries/` holds the saved files for one recipient agent-seat on ned-box. The handoff-supervisor that launches that recipient reads them.
- **Outgoing, on the sender's machine:** `~/.claude/handoffs/<sender agent-seat>-outgoing-messages-to-resend-from-offline-remote-control-entries/` holds the saved files that one sender still has to resend. The sender's reminder hook and the sender's handoff-supervisor read them.

A saved file holds the sender agent-seat's name, the time in UTC, and SendMessage's `to`, `summary` (empty when the send gave none) and message body. It is named `<time as YYYYMMDDTHHMMSSffffffZ>-<first 16 hex digits of the SHA-256 of the sender's name, a newline and the message body>.json`, so names sort oldest first, and the same sender's same message body to the same recipient is found by its hash. It is written under a name starting with `.` in the same directory and then renamed; every reader skips names starting with `.`.

The directory `~/.claude/handoffs/` and the two directory-name endings are defined once, in a shared module, proposed name `nc-systems/handoff/handoff-offline-remote-control-entry-saved-messages-common.py`, which the hooks and the handoff-supervisor import. The handoff-supervisor uses its own handoff directory, its `--handoff-dir`, which defaults to `~/.claude/handoffs/`. A handoff-supervisor started with another `--handoff-dir` is not found by the save hook's test in § The save hook, so its agent-seat's messages go to the sender's outgoing directory and are not lost.

Why the handoff directory: `nc-systems/handoff/handoff-supervisor.py` already reads per-agent-seat files there at every launch, a resume included. Its main loop calls `uncommitted_work_snapshot_text(settings.agent, settings.working_directory, settings.handoff_directory)` just before `launch_agent_session` and adds the text to the initial-agent-instructions; the saved messages are listed the same way. Why not the log-store: these files hold messages waiting for delivery and are deleted after it, and the handoff directory is where the handoff-supervisor's other per-agent-seat files are. `scripts/transcript-mirror-to-log-store.py` copies the handoff directories of both machines, and so these files, into the log-store, and both transcripts hold each message's text, so a deleted file's message stays on record.

Open for the user: the saved messages are kept in the handoff directory, `~/.claude/handoffs/`, of the machine whose program reads them, not in the log-store; recommended, for the reasons just given.

### The save hook

A PostToolUse hook on SendMessage, proposed name `nc-systems/general-tools/claude-code-send-message-tool-offline-recipient-message-save-and-resent-message-clear-hook.py`. It reads SendMessage's input, `to`, `summary` and `message`, and the reply. It does nothing when the input has no message body, such as a send that only asks to be told when the recipient goes idle. In both branches below, the recipient agent-seat's name is `to` without a trailing ref such as ` [86a690]`; when `to` is a ref alone, the recipient's name is unknown, and the message goes to the sender's outgoing directory under the ref.

On an offline reply, the hook:

1. Decides where the message goes. When a handoff-supervisor for the recipient's name is running on ned-box, the message goes to that recipient's incoming directory on ned-box. Any other recipient, whether on the Mac, stopped, retired with retire-seat, or named by a Remote Control entry whose name is longer than the agent-seat's name, is one the sender must resend to, and the message goes to the sender's outgoing directory. The test is `supervisor_liveness(supervisor_state_path(<handoff directory>, <recipient>))`, both functions in `nc-systems/handoff/handoff-supervisor.py`, with ned-box's `~/.claude/handoffs/` as the handoff directory: it finds the recipient's supervisor-state file there, reads the handoff-supervisor's lock file beside it, and checks that the process the lock file names is that agent-seat's handoff-supervisor. On ned-box the hook runs that test itself. On the Mac it runs it on ned-box over ssh, with `run_on_ned_box_or_here` from `nc-systems/handoff/handoff-user-review-of-agent-memory-stores-mark.py`, which `handoff-user-review-of-agent-memory-stores-mark.py` uses rather than the Mac's mount of ned-box because a hung mount has no read timeout; the hook writes a saved file into the incoming directory the same way, passing the JSON on stdin to a command on ned-box that writes it under a name starting with `.` and renames it, with the directory and file names quoted for the shell. When ssh to ned-box fails, the message goes to the sender's outgoing directory.
2. Saves the message. A saved file with the same hash in that directory is replaced, so a resend that gets another offline reply is saved once.
3. Tells the sending agent, in the hook's output. For the incoming directory: the message is saved, and the recipient's next agent-session receives it; if ListAgents shows an entry with the recipient's name that is not offline, resend the message to that entry by its ref as well, because the recipient's running agent-session would otherwise see it only after its next session-handoff. For the outgoing directory: the exact message body to resend, to resend it when ListAgents shows an entry with the recipient's name that is not offline, by that entry's ref, and the saved file's path.

On an accepted send, the hook deletes each saved file in the sender's own outgoing directory whose recipient is the same agent-seat and whose whole message body appears in the message body just sent. The hook's output names each saved file it deleted, so a short saved message cleared by a longer send that happens to contain it is seen by the sender. It does not touch the incoming directories on ned-box: a copy delivered there as well as resent reaches the recipient twice, and § Delivery to a recipient on ned-box marks it so.

Any other reply, such as a refusal of an ambiguous name, changes nothing.

The sender agent-seat's name is the `NEDSCHORUS_HANDOFF_SUPERVISOR_AGENT_NAME` environment variable, which the handoff-supervisor sets for every agent-session it launches, and which a `claude` started from inside that agent-session inherits, so such a `claude` counts as the same sender. Where the variable is unset, the hook uses `session-<session_id>` instead, `session_id` being the Claude Code session id that every hook's input carries; the reminder hook finds that outgoing directory by the same id, so such an agent-session is reminded too, though no successor is.

When the hook cannot save or delete a file, it writes to stderr what failed and, when the failure was a save, the exact message body to resend, and exits with status 2, which makes Claude Code show that stderr to the agent.

Open for the user: an accepted send clears only the saved files whose whole message body it carries, not every saved message to that agent-seat. Item 5.1 says "reminded until a send to that agent-seat goes through", which, read literally, would clear a message not yet resent when a different message to the same agent-seat is accepted first. Recommended: clear only the saved files whose message body the send carries; a message the sender resent in other words, or that no longer needs sending, is cleared by deleting the saved file, whose path the hook's output and every reminder give.

Open for the user: for a recipient whose handoff-supervisor runs on ned-box, the sender is also told to resend the message to the recipient's entry when ListAgents shows one that is not offline, and a recipient may then receive the message twice. Item 5.1 settled only the saving and the delivery to the next agent-session. Recommended: without the resend, a recipient whose agent-session is running, or is starting while the message is saved, sees the message only after its next session-handoff, which can be hours away; a message received twice is marked as a possible repeat.

### Delivery to a recipient on ned-box

At every launch of an agent-session, a resume included, the handoff-supervisor lists the saved files in the agent-seat's incoming directory, oldest first, in the initial-agent-instructions, after the leftover work-snapshots: for each, its sender, its time, its summary and the saved file's path, with the instruction to read each saved file and act on its message, which reached an offline entry of this agent-seat and may also have reached it another way. The initial-agent-instructions name the saved files rather than holding their message bodies, so a long queue does not make the launch command too long.

The handoff-supervisor records in its supervisor-state file the names of the saved files it listed at the launch, and deletes those files, and only those, when the agent-session launched with them writes its session-handoff, at the point where it reads that session-handoff. Until then each launch lists them again, so an agent-session that crashes, a resume after it, or a fresh agent-session after a stop still receives them. A saved file that arrives after a launch is listed at the next one.

When a saved file cannot be read, the handoff-supervisor lists its path with the error and launches the agent-session anyway, so that one bad saved file stops neither the launch nor the other messages.

Open for the user: a saved message for a recipient on ned-box is deleted when the agent-session launched with it writes its session-handoff, not when that agent-session starts, and not after it has acted on the message. Recommended: by then that agent-session has had the whole of its run to read the saved file, and no program can tell when it has read it.

### Reminding a sender of a message to resend

Two places remind the sender, so the reminder outlives the sender's agent-session:

- A UserPromptSubmit hook, proposed name `nc-systems/general-tools/claude-code-send-message-tool-offline-recipient-message-resend-reminder-hook.py`, lists the saved files in the sender's outgoing directory as additional context on every prompt the sending agent-session receives: for each, its recipient, its summary and the saved file's path, with the instruction to resend it when ListAgents shows the recipient's entry as not offline, or to delete the saved file when it no longer needs sending.
- The sender's handoff-supervisor adds the same list to every initial-agent-instructions of the sender agent-seat, so the sender's next agent-session is reminded from its first turn.

The list names saved files rather than holding their message bodies, which keeps each entry to one line. The reminder for a message stops when its saved file is deleted, by the save hook after an accepted send that carries its message body, or by the sender. Each outgoing directory is read only on its own machine.

Open for the user: the reminder is given on every prompt the sending agent-session receives, by a UserPromptSubmit hook, and at every launch of the sender, by its handoff-supervisor. A Stop hook was not chosen: a Stop hook that blocks the end of a turn would keep the agent working at a resend it cannot make while the recipient is offline, and one that wakes the agent later, as GHI [Seat mailboxes across machines and runtimes](https://github.com/nedschorus/nedschorus/issues/749) § 4 proposes with `asyncRewake`, would wake it to the same resend it cannot make. Recommended: UserPromptSubmit and the initial-agent-instructions.

### What the build adds, and its tests

- The save hook, the reminder hook, the shared module, and the hooks' entries in `.claude/settings.json`.
- In `nc-systems/handoff/handoff-supervisor.py`: listing the incoming directory's and the outgoing directory's saved files in the initial-agent-instructions at every launch, and deleting the incoming saved files listed at a launch when that launch's agent-session writes its session-handoff.
- Tests, each causing its failure where it cannot be caused for real:
  - The save hook: it saves on an offline reply, clears on an accepted send, and does nothing on any other reply or a send without a message body; a summary holding the words "it is offline right now" does not make a reply an offline reply; it strips the ref in both branches; it sends the message to the incoming directory only when `supervisor_liveness` finds the recipient's handoff-supervisor running, and to the outgoing directory otherwise and when ssh fails; it replaces a saved file with the same hash; an accepted send clears only the matching saved files to that recipient in the sender's own outgoing directory; it uses `session-<session_id>` when the environment variable is unset; it writes to stderr and exits 2 when a save or a delete fails.
  - The reminder hook: it lists every saved file in the outgoing directory, skips names starting with `.`, and lists nothing when the directory is empty or missing.
  - The handoff-supervisor: it lists both directories' saved files in the initial-agent-instructions of a fresh launch and of a resume; it keeps the incoming saved files across a crash and a resume, and deletes them at that agent-session's session-handoff; a saved file that arrived after the launch is kept; an unreadable saved file is listed with its error and the launch goes ahead.

### Not in this design

- Removing the old offline Remote Control entries. Neither `claude --help` nor `claude remote-control --help` (2.1.295) offers a command to list, archive or delete them, and the user dropped archiving them by hand at item 5.
- A mailbox that delivers across machines without SendMessage. That is GHI [Seat mailboxes across machines and runtimes](https://github.com/nedschorus/nedschorus/issues/749), whose design awaits its own approval-walk. This GHI's fix uses SendMessage and the handoff-supervisor as they are; a built mailbox would replace it.
- Adding the saved messages to the sender's next send by changing that send's input in a PreToolUse hook. That would change what an agent sends without the agent seeing it, and item 5.1 has the sender told and reminded instead.

## Background: how agent-seats came to have several entries under one name

Measured on ned-box on 2026-10-09 (Claude Code 2.1.289 and 2.1.295), before PR #1118:

1. **The local name was not the agent-seat's name.** `nc-systems/handoff/handoff-supervisor.py` started every agent-session with `--remote-control <agent-seat>` and no `--name`, and the local session registry, `~/.claude/sessions/<pid>.json`, recorded a derived name such as `"name": "ned-box-helper-45", "nameSource": "derived"`. `--remote-control <name>` names the Remote Control entry, not the local name. PR #1118 fixed this.
2. **Every new agent-session leaves a Remote Control entry behind.** An agent-session the handoff-supervisor starts fresh is a new Claude Code session with its own Remote Control entry (`bridgeSessionId` in the registry); a resume continues the same Claude Code session. When the agent-session ends at a session-handoff, its entry stays, offline, under the same agent-seat name. On 2026-10-09 ListAgents in merge-lane-2's agent-session listed about 40 offline Remote Control entries under agent-seat names, several per agent-seat: "merge-lane" seven times, "MD-skills" five times.
3. **A Remote Control entry can lose the agent-seat's name** when the user runs `/remote-control` in an agent-session's window: the new Remote Control session gets the default name, host name plus two words. The `--remote-control-session-name-prefix` flag that PR #1118 added keeps the agent-seat's name as its prefix.

A message lost this way before that fix: on 2026-10-07 at 16:00Z merge-lane-backlog on the Mac sent a message to "merge-lane-2"; it went to an offline entry and was never read. Claude Code's cross-session messaging documentation says a message to an offline entry "arrives only after that session's machine reconnects" (https://code.claude.com/docs/en/cross-session-messaging.md).

## Next action

merge-lane-2 puts this design, and each "Open for the user:" line above, to the user in an approval-walk. When he disapproves a line or asks for a change, ned-box-helper revises this GHI-MD and the changed part returns to him before the build. After he approves, the agent-seat he names in that approval-walk, or ned-box-helper when he names none, builds § What the build adds, and its tests, in one pull request that edits this GHI-MD to record the build.

## Deferred-decisions

- What the save hook does when a Claude Code release changes the wording of the offline reply, which would make every offline reply look like an accepted send; to be settled at the build, from the replies the installed Claude Code then gives.
- Whether UserPromptSubmit fires on a turn that a cross-session message or a background task's notice starts; to be measured at the build, and if it does not, the reminder is added to a hook that does fire on such turns.
