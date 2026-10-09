---
issue: "[Cross-session messages between agent-seats reach stale offline Remote Control entries instead of the live agent-session](https://github.com/nedschorus/nedschorus/issues/1115)"
---

# Cross-session messages between agent-seats reach stale offline Remote Control entries instead of the live agent-session

Agent-seats message each other with Claude Code's cross-session messaging, by name. A message addressed to an agent-seat's name often goes to an old, offline Remote Control entry of that agent-seat instead of its live agent-session, and is never read; and a live agent-session is often not listed under its agent-seat's name at all. The user asked for this to be fixed now: "Itme 4 sounds important. Can you dispatch that to some appropriate agent to fix now?" (2026-10-09 about 05:20Z, in merge-lane-2's agent-session, answering item 4 of the approval-walk merge-lane-2-waiting-on-user-walk-2026-10-07, whose approval was to file this GHI so that each live agent-session is listed under its agent-seat's name and old entries are removed; walk-document `docs/walk/merge-lane-2-waiting-on-user-walk-2026-10-07.md` in merge-lane-2's checkout `/home/nedlern/agents/merge-lane-2` on ned-box).

## Reproduction

ListAgents prints each entry as its name, a short code in brackets that Claude Code calls its ref and that tells same-named entries apart, its kind, and whether it is live or offline.

ned-box's view, from merge-lane-2's agent-session at about 2026-10-09T05:16Z: ListAgents listed 49 peer sessions, about 40 of them Remote Control entries marked offline under agent-seat names, several per agent-seat: "merge-lane-2" twice (refs 62fe18 and 122bc8), "merge-lane" seven times, "MD-skills" five times, "cold-read-research" five times. The live ned-box agent-sessions appear under suffixed names: merge-lane-2's live agent-session was "merge-lane-2-83" (in earlier agent-sessions "merge-lane-2-d0" and "merge-lane-2-e3"), and the others "ned-box-helper-45" and "fleet-restart-at-login-37". Live Mac agent-sessions appear under titles taken from their conversations: "Research reproducibility", "a - Y, 3 -y" (merge-lane-backlog), "Better messages display preference".

The Mac's view, from the Mac agent-session "Research reproducibility" (cold-read-research), read-only, 2026-10-09:
- merge-lane-2 [79b0f9] Remote Control idle; merge-lane-2 [62fe18] offline; merge-lane-2 [122bc8] offline.
- fleet-restart-at-login: [b4d2fe], [5a1904], [2220e0] and [386f19], all offline; no live row.
- No row at all for ned-box-helper, agent-instructions-editor or cold-read-improvement. On 2026-10-06 the same agent-session saw ned-box-helper [47b20b], cold-read-improvement [fb822b] and agent-instructions-editor [ced0f3], all Remote Control idle.
- Rows titled by host name and two words: ned-box-sunny-kahn [8e0a2a] idle; ned-box-linear-cerf [d5bdf6] idle; ned-box-unified-tide [0831d6], ned-box-twinkly-hinton [1a436b] and ned-box-refactored-grove [640078], offline.
- Errors when sending: a bare name gave "3 agents are named 'merge-lane-2'"; a ref went stale between two messages ("No agent named 'merge-lane-2 [0f6ffa]' is reachable"); bridge addresses went stale with HTTP 409.

A message lost this way: on 2026-10-07 at 16:00Z merge-lane-backlog on the Mac sent a message to "merge-lane-2"; it went to an offline entry and was never read. Claude Code's cross-session messaging documentation says a message to an offline entry "arrives only after that session's machine reconnects" (https://code.claude.com/docs/en/cross-session-messaging.md), and an old entry's agent-session never reconnects.

## Cause, measured on ned-box on 2026-10-09 (Claude Code 2.1.289 and 2.1.295)

1. **The local name is not the agent-seat's name.** `nc-systems/handoff/handoff-supervisor.py` (`launch_agent_session`) starts every agent-session with `--remote-control <agent-seat>` and no `--name`. The local session registry, `~/.claude/sessions/<pid>.json`, records each live ned-box agent-session's name as derived, not chosen: `"name": "ned-box-helper-45", "nameSource": "derived"`, and the same for every agent-seat on ned-box (`merge-lane-2-83`, `fleet-restart-at-login-37`, `cold-read-improvement-5f`, `agent-instructions-editor-78`). A derived name is the working directory's name plus a short code, and it changes with every agent-session. `--remote-control <name>` names the Remote Control entry, not the local name.
2. **`--name` fixes the local name.** A throwaway session started on ned-box with `claude --name nbh-name-probe-session` was registered as `"name": "nbh-name-probe-session", "nameSource": "user"`, and ListAgents listed it under exactly that name. A second session started with the same `--name` while the first ran kept the same name too; the documented rename of a colliding live name did not happen at start.
3. **Every agent-session leaves a Remote Control entry behind.** Each agent-session is a new Claude Code session with its own Remote Control entry (`bridgeSessionId` in the registry). When the agent-session ends at a session-handoff, its entry stays, offline, under the same agent-seat name. So an agent-seat that has handed off several times has several entries with its name, and a bare name is ambiguous. Neither `claude --help` nor `claude remote-control --help` (2.1.295) offers a command to list, archive or delete Remote Control entries, and the documentation names none.
4. **A Remote Control entry can lose the agent-seat's name.** This agent-session (ned-box-helper, session 74f883f6) started with `--remote-control ned-box-helper`; after the user ran the `/remote-control` command in its window on 2026-10-07, its Remote Control session changed from `session_01RDyv9mvqxbm7Ptk9nC3dZi` to `session_01V2heJES18FbkmTwNcG8mvn`, and the Mac no longer lists a row named ned-box-helper. A Remote Control session started without a name gets the default name, host name plus two words (`--remote-control-session-name-prefix`, "default: hostname"), which fits the live `ned-box-sunny-kahn` and `ned-box-linear-cerf` rows. Which live agent-session each of those two rows is could not be measured from ned-box.
5. **One live agent-seat has no Remote Control entry at all.** agent-instructions-editor's registry entry has no `bridgeSessionId`, although it was started with `--remote-control agent-instructions-editor`, so the Mac cannot reach it. Why its Remote Control connection is missing was not measured.

## What can be fixed on our side, and what cannot

- Fixable in code: start every agent-session, new or resumed, with `--name <agent-seat>` as well as `--remote-control <agent-seat>`, so local senders on the same machine reach it by the agent-seat's exact name; and with `--remote-control-session-name-prefix <agent-seat>`, so a Remote Control session renamed by default keeps the agent-seat's name as its prefix. The handoff-supervisor ends the old agent-session before it starts the next, so two live agent-sessions never share the name.
- Not fixable in code: the stale offline entries. Nothing in the CLI removes them. They can be archived by hand in the claude.ai web interface, which needs the user.
- Not fixable in code: a sender on the Mac choosing among duplicate names. Until the stale entries are gone, a sender picks the row that has the agent-seat's name and is not offline, by its ref from a ListAgents run just before sending. When no such row exists, the sender tells the user which agent-seat it cannot reach.

## Next action

Merge the launch change in `nc-systems/handoff/handoff-supervisor.py`, with its case in `nc-systems/handoff/tests/handoff-supervisor-session-launch-and-seat-lock-test.py`, then put the clean-up of the stale entries to the user as steps in the claude.ai web interface.
