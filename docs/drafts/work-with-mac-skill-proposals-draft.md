# Proposals pending approval: the skill for getting Mac work done from ned-box

ned-box-helper proposes these items for the user's approval. They go with the skill text in `docs/drafts/work-with-mac-skill-draft.md`. The user approved the idea in merge-lane-2's agent-session 2c812b81 at about 22:05Z on 2026-10-09: "ned-box agents need to kow what to do when they try to do mac stuff, so they don't ask me", and "sounds like we need a work-with-mac skill".

## 1. The skill's name

Proposed: `get-mac-work-done-from-ned-box`, in `.claude/skills/get-mac-work-done-from-ned-box/SKILL.md`.

Why not `work-with-mac`, the user's phrase: the name does not say which machine the agent is on, and an agent on the Mac also works with the Mac. The proposed name keeps the user's words "Mac" and "work", and adds where the agent is, in the verb-first form of the existing skills `locate-before-saying-a-file-is-missing` and `start-new-agent-seat-on-ned-box`.

Naming search, run on 2026-10-10 at about 03:25Z in `/home/nedlern/agents/ned-box-helper`, after a `git fetch` that succeeded:

- Patterns `work[-_ ]?with[-_ ]?mac`, `mac[-_ ]?work`, `get[-_ ]?mac`, `mac[-_ ]?terminal`, `mac[-_ ]?command[-_ ]?handed`, `command[-_ ]?handed[-_ ]?to[-_ ]?user`, `mac[-_ ]?scripts?[-_ ]?for` and `scripts?[-_ ]?for[-_ ]?the[-_ ]?user`, each with `git grep -i -l -E` in the checkout, `git ls-tree -r --name-only origin/main | grep -i -E` for paths on main, and `git grep -i -l -E ... origin/main` for text on main.
- Only `get[-_ ]?mac` matched anything: `TARGET_MAC` in `scripts/watch-agent-dialog-alerts.py` and its test, and "get" next to "mac" in `docs/issues/45-remote-named-agent-launch-and-reattach.md`. Neither names a skill, a hook or a folder.
- Open pull requests: `gh pr list --repo nedschorus/nedschorus --state open --search` for "mac work", "work-with-mac", "mac script", "mac terminal" and "reminder hook mac" found none, and no open pull request's branch name matches `mac|work[-_]?with|handed|scripts?[-_]?for`.
- The log-store has no folder whose name contains "mac" at its top level.

A fresh subagent was asked what each of the three new names means from the name alone. For `get-mac-work-done-from-ned-box` it answered "a skill with rules for getting Mac tasks done remotely from ned-box", which is right; adding `-without-asking-the-user` made it read the name as "without prompting the user for permission", so the name stays as proposed. For the folder it answered "a folder of Mac scripts for the user to run by hand", which is right. The hook's first proposed name, `mac-command-handed-to-user-reminder-hook.py`, it read as a hook that notifies the user on macOS, so the hook's name was changed to the one in section 3, which it read correctly. None of the three names collides with a name on main or in an open pull request.

## 2. The CLAUDE.md line, and where it goes

A new bullet in `CLAUDE.md`, placed directly after the bullet that begins "The project runs on two machines, each with its own clone":

```
- On ned-box, when work needs the user's Mac, and before you tell the user to run anything on his Mac, use the skill `get-mac-work-done-from-ned-box`: it gives the ways to get the work done without him, and asking him comes last.
```

## 3. The hook

**File:** `scripts/reply-asks-user-to-run-mac-command-agent-reminder-hook.py`, with its tests in `scripts/reply-asks-user-to-run-mac-command-agent-reminder-hook-test.py`. Reminder hooks such as `scripts/absence-claim-locator-reminder-hook.py` are kept in `scripts/`; guards that refuse a tool call are kept in `.claude/hooks/`. The name puts the trigger first, as `absence-claim-locator-reminder-hook.py` does, and says that the reminder goes to the agent, not to the user.

**Event:** Stop, reading the agent's last reply: the text blocks of the last assistant message that has text, since the last message that started the turn, read from the transcript as `absence-claim-locator-reminder-hook.py` reads them. Stop, not UserPromptSubmit: UserPromptSubmit fires only after the user has answered, which is after he has already been asked; Stop fires as the reply ends, so the agent follows up in the same turn. The reply has already been shown when Stop fires, so the reminder tells the agent to correct the reply, not to withhold it. The hook is not wired to SubagentStop: a subagent's reply goes to its parent agent, whose own reply to the user the Stop hook reads.

**Wiring:** one more command in the existing Stop entry of `.claude/settings.json`: `python3 "$CLAUDE_PROJECT_DIR"/scripts/reply-asks-user-to-run-mac-command-agent-reminder-hook.py`. `.claude/settings.json` is guarded, so the user approves that edit too.

**The pattern it matches.** The hook removes block quotes (lines starting with `>`) and text in double quotes, and keeps code, because a command handed to the user is usually written as code. It then matches, ignoring case:

```
MAC_NAMED_THEN_INSTRUCTION = r"\b(?:on|in|from)\s+(?:your|the|his|a)\s+Mac(?:'s)?(?:\s+(?:terminal|iTerm2?|shell))?\s*[,:]?\s*(?:run|type|paste|enter|open)\b"
INSTRUCTION_THEN_MAC_NAMED = r"\b(?:run|type|paste|enter)\b[^.\n]{0,80}?\b(?:on|in|from)\s+(?:your|the|his|a)\s+Mac\b"
SSH_TO_NED_BOX_HANDED_TO_USER = r"\bssh\s+(?:-\S+\s+)*(?:nedlern@)?ned(?:-box)?\s+['\"]"
```

The first matches "On your Mac, run" and "In a Mac terminal, paste". The second matches "Run this on your Mac" and "paste it in a Mac terminal". The third matches a command the user would type on the Mac to run something on ned-box, `ssh nedlern@ned-box '<command>'`, which an agent on ned-box can run itself. The user's own `~/.claude/CLAUDE.md` tells agents to hand him ned-box commands in exactly that form, so the third pattern fires on replies that follow that instruction; the reminder's lines that say to carry on cover the case where he really must run the command. The patterns are not yet measured against real replies; before wiring, the tests run them over replies from the ned-box agent-session transcripts in the log-store, and the precision goes in the pull request.

**It stays silent when any of these holds:**

- the machine's host name is not `ned-box`: the skill is for agents on ned-box;
- a path starting `/Volumes/nedhome/` appears anywhere after the first match in the reply: the reply hands the user a script from the skill's way 4;
- `stop_hook_active` is set: the agent is already continuing because of a Stop hook;
- the agent-session is headless, told apart as `absence-claim-locator-reminder-hook.py` does: `NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER` set, or `CLAUDE_CODE_SESSION_ATTENDED` equal to `0`;
- the agent invoked the skill `get-mac-work-done-from-ned-box` earlier in this agent-session, found by scanning the whole transcript, not only the last turn; or this agent-session was already reminded, which the hook records in a per-session marker file, as `absence-claim-locator-reminder-hook.py` does: the reminder comes once.

When it reminds, it prints `{"decision": "block", "reason": <the text below>}`. On a fault it prints nothing and exits 0, so a fault never stops a turn ending.

**The text it hands the agent:**

```
reply-asks-user-to-run-mac-command reminder: your last reply asks the user to run something on his Mac ({matched}), and you have not used the skill get-mac-work-done-from-ned-box in this agent-session. The user wants agents on ned-box to get Mac work done without him wherever they can, and that skill lists the ways.
Invoke the skill get-mac-work-done-from-ned-box now, and try its ways in order.
If one of its ways gets the work done without the user, do the work, then tell the user he does not need to run what your reply asked.
If the user is still needed, for a password, a browser login or a physical step, carry on, and make sure your reply names the machine and the exact command.
If your reply did not ask the user to run anything, carry on; this reminder comes once per agent-session.
```

`{matched}` is the matched text, cut to 80 characters.

## 4. The shared folder for Mac scripts on ned-box

Proposed: `/home/nedlern/nedschorus-logs/mac-scripts-for-the-user-to-run/`, which the Mac reaches as `/Volumes/nedhome/nedschorus-logs/mac-scripts-for-the-user-to-run/`. It holds the scripts of one command that agents write for the user to run on his Mac, each with the `.out` file of its output beside it. One folder for all agent-seats lets an agent find and reuse a script another agent-seat wrote. The scripts already in `/home/nedlern/nedschorus-logs/seats/merge-lane-2/` stay where they are, since moving them would break the paths quoted in transcripts and minutes. The folder is in the log-store and not in a scratchpad, because ned-box empties `/tmp` at every reboot.

The other option, which needs no new name: each agent-seat keeps its scripts in its own `/home/nedlern/nedschorus-logs/seats/<agent-seat name>/`, named `mac-<...>.sh`, as merge-lane-2 does today. ned-box-helper recommends the shared folder.

When the folder is created, the log-store's `README.md` should list it. That README is rewritten from `STORE_README` in `nc-systems/cold-read/cold-read-record-ship.py`, so the change goes there, in the same pull request as the skill.

## 5. Skill alone, or a skill and a wiki page: a skill alone

Everything here is what an agent needs at the moment it is about to do Mac work or ask the user to, which is what a skill is loaded for; a wiki page would be read only by an agent that already knew to look. The runbook page for the two machines that ned-box-helper's task #32, "After the Mac-agent move: a reboot program and a runbook page for the two machines", will write covers setup, adding, removing and moving agent-seats, and reboots: when it is written, the runbook page links to this skill for getting work done on the Mac from ned-box, and keeps the procedures it owns, so each fact has one canonical location. The traps about reboots and `/tmp` are in the skill because an agent writing a way 4 script needs them then; if the runbook page needs them too, the runbook page links to the skill's Traps section rather than copying them.

## 6. A question for the user: the address in the remount command

The remount command, `open 'smb://nedlern@10.0.1.39/nedhome'`, is taken from `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/mac-ned-box-firmware-update-reboot-and-reopen-seat-windows.sh`. 10.0.1.39 is ned-box's Wi-Fi address; the Mac's ssh now uses the wired address, 10.0.1.106, since `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/mac-ssh-to-ned-box-wired-address-and-connection-reuse.sh` ran at 21:57Z on 2026-10-09. Should the skill keep 10.0.1.39, which is what the Mac mounts today, or should the mount move to 10.0.1.106 as ssh did? ned-box-helper recommends keeping 10.0.1.39 in the skill until the mount itself is moved, since a remount to a different address than the current mount could leave two mounts.

## 7. Two smaller questions for the user

- Should way 5 also allow a command that must run outside the agent-session's sandbox or worktree isolation? The user's `~/.claude/CLAUDE.md` says such a command needs a separate terminal, which is a fourth reason, besides a password, a browser login and a physical step, to hand him a command. ned-box-helper recommends adding it to way 5 as "a command that must run outside the agent-session's sandbox, run in a terminal on ned-box over ssh".
- The project glossary lists some skills by their slash names, such as /cold-read and /handoff, and not others, such as /locate-before-saying-a-file-is-missing. Should `/get-mac-work-done-from-ned-box` get an entry? ned-box-helper recommends no entry, as for the two skills this one is modelled on.
