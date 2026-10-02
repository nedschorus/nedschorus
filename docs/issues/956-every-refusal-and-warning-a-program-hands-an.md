---
issue: "[Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956)"
---

# Every refusal and warning a program hands an agent says why and what to do instead

When a program in this repository stops or warns an agent, the program's message is the agent's only account of what the program stopped and why. A message that leaves out the reason or the next step leaves the agent to guess, and a cooperative agent's guess can be the wrong action. This document shows each such message as the agent sees it and proposes the exact words to replace it. None of the proposed wording is built.

This document covers the first of six parts, the hooks registered in `.claude/settings.json`; "Later parts" lists the other five. Each later part is drafted as a document of its own, in the same shape, and walked the same way; this GHI tracks all six. The next action is an approval-walk of the proposed words, one message to an item, for every message whatever directory its program sits in. Then the messages of this part, and the test cases that assert their text, change in one pull request. That pull request is cut from main after PR [CLAUDE.md: text a program hands an agent says what was stopped and why, and cites no ruling](https://github.com/nedschorus/nedschorus/pull/909) has merged, because the rule below is the one that pull request lands.

## What a reader needs first

**Hooks.** The agent harness, Claude Code, runs small programs called hooks at fixed moments: before a tool call, after a tool call, when a session starts, and when an agent's turn ends. `.claude/settings.json` registers twelve hooks in this repository. A hook that refuses a tool call is called a guard here. The project glossary's hard-block, soft-block and user-block name three kinds of refusal by whose words clear them; each section below names the kind where one applies.

**How a hook's text reaches the agent.** Three channels:

- The hook exits with code 2 and prints to stderr. The harness cancels the tool call, or keeps the turn open, and shows the agent the stderr text.
- The hook prints JSON whose `permissionDecision` is `deny`. The harness cancels the tool call and shows the agent the `permissionDecisionReason`.
- The hook prints JSON with `additionalContext`. Nothing is cancelled; the text is added to what the agent reads next.

**The four questions.** A message is complete when the message answers all four:

1. What was refused or found, naming the file or the command.
2. Why: the rule being enforced, or what goes wrong if the agent goes ahead.
3. What to do instead, as an instruction.
4. Under which condition each instruction applies, when the message gives more than one.

**The project's rule for this text**, from `CLAUDE.md` as PR [CLAUDE.md: text a program hands an agent says what was stopped and why, and cites no ruling](https://github.com/nedschorus/nedschorus/pull/909) leaves it: "When you write the text a program hands an agent at the moment it must act, a hook's refusal or an error message, say what was stopped and why, then put each instruction on its own line with the condition it applies under. Give the reason wherever the reason helps the agent act well. Keep quotations of the user, rulings, dates and citations out of the text."

**Where the list comes from.** The audit put the four questions to 139 messages; its report is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/MD-skills/refusal-and-warning-message-audit-2026-10-01.md`. Every hook message below was read again from main at the commit [Merge pull request #881 from nedschorus/search-file-argument-read-as-option-guard](https://github.com/nedschorus/nedschorus/commit/dad220d463d1d1d8f650e9c6669c43926834794f), and the line numbers are main's at that commit. The guard that pull request added, `scripts/search-file-argument-read-as-option-guard-hook.py`, answers all four questions and cites nothing, so it has no row.

## The messages in this part

Thirteen messages from the registered hooks, each with at least one gap or one citation in its text. In the What, Why, Instead and Conditions columns, "no" marks a question the message leaves unanswered, and "one instruction" means the message gives one instruction and so needs no conditions. The last column names what the text cites, which the rule keeps out of it.

| # | Program | When it appears | What | Why | Instead | Conditions | Citation in the text |
|---|---|---|---|---|---|---|---|
| 1 | `ghi-issue-write-redirect.py` | closing or reopening an issue with `--comment` | yes | no | yes | yes | none |
| 2 | `ghi-issue-write-redirect.py` | deleting an issue | yes | no | yes | no | none |
| 3 | `session-location-write-guard.py` | write from a detached HEAD | yes | yes | yes | no | none |
| 4 | `backup-and-snapshot-write-guard.py` | write to backup state | yes | yes | yes | yes | date |
| 5 | `synthetic-keystroke-guard-hook.py` | AppleScript typing | yes | yes | yes | one instruction | date, issue number |
| 6 | `synthetic-keystroke-guard-hook.py` | tmux session with someone attached | yes | yes | no | yes | issue numbers |
| 7 | `synthetic-keystroke-guard-hook.py` | tmux session that could not be checked | yes | yes | yes | no | issue number |
| 8 | `synthetic-keystroke-guard-hook.py` | tmux target holding a variable | yes | yes | yes | no | issue number |
| 9 | `synthetic-keystroke-guard-hook.py` | tmux command naming no target | yes | yes | no | no | issue numbers |
| 10 | `handoff-context-threshold-hook.py` | context share reaches the reincarnation threshold at a turn's end | no | no | yes | one instruction | none |
| 11 | `checkout-freshness-catch-up.py` | branch not brought up to date | yes | yes | yes | no | none |
| 12 | `obsolete-file-edit-warning-hook.py` | edit of a file main has changed, on a detached HEAD or with no branch state reported | yes | no | no | no | none |
| 13 | `file-name-collision-warning-hook.py` | second file under a tracked file's name | yes | no | yes | no | none |

## The messages, one at a time

### 1. Closing or reopening an issue with a comment

**When an agent sees this.** An agent finishes the work of a GHI and runs `gh issue close 224 --comment "done in the layout pull request"`. The guard refuses the command, because agents here do not write issue comments: what an issue says lives in the issue's GHI-MD.

**What the agent is told today** (`.claude/hooks/ghi-issue-write-redirect.py:168`; the program fills `{subcommand}` with `close` or `reopen`, shown here for `close`):

```
Run gh issue close again without --comment.
Record the reason in the issue's GHI-MD, docs/issues/<number>-*.md, with: python3 scripts/ghi-issue-write.py edit <path>
If the issue has no GHI-MD, stop and tell the user.
```

**What the agent cannot tell from the text.** Why the comment is refused. The first line reads as a correction of the command's form, so the agent may drop the outcome it meant to record and skip line two. The text also has the agent close the issue first and record the outcome after, where the /ghi-write skill closes an issue only after the edit recording the outcome has merged and its rerun has finished. And `docs/issues/<number>-*.md` can match several files: an issue's GHI-MD and its supporting files share the number.

**Proposed text**, one text for each subcommand, since the skill orders closing and says nothing about reopening. For `close`:

```
Do not comment on this project's issues: what an issue says lives in its GHI-MD, and a comment would sit outside it.
Record the outcome in the issue's GHI-MD, the first file the issue's body links to, then open the edit's pull request with: python3 scripts/ghi-issue-write.py edit <path>
Close the issue after that edit's pull request has merged and its rerun has finished, without --comment: gh issue close <number> --reason completed, or --reason "not planned", or --duplicate-of <the other issue's number>.
If the issue has no GHI-MD, stop and tell the user.
```

For `reopen`:

```
Do not comment on this project's issues: what an issue says lives in its GHI-MD, and a comment would sit outside it.
Run gh issue reopen again without --comment.
Record why the issue is reopening in the issue's GHI-MD, the first file the issue's body links to, then open the edit's pull request with: python3 scripts/ghi-issue-write.py edit <path>
If the issue has no GHI-MD, stop and tell the user.
```

**What changes.** `STATE_CHANGE_COMMENT_REFUSAL` becomes two constants, one per subcommand. `.claude/hooks/ghi-issue-write-redirect-test.py` compares each refusal against its constant, and also requires every refusal line to start with one of its listed opening words and to contain neither "ruled" nor "2026"; every line above starts with "Do not", "Record", "Close", "Run" or "If", all already listed. The file is under `.claude/`, so the exact text must be approved-by-walk: the instruction-file guard refuses the edit until the user's approval words are quoted into its marker.

### 2. Deleting an issue

**When an agent sees this.** An agent files a GHI by mistake and runs `gh issue delete 912 --yes`.

**What the agent is told today** (`.claude/hooks/ghi-issue-write-redirect.py:200`):

```
Do not delete this project's issues.
Close the issue instead: gh issue close <number> --reason completed, or --reason "not planned".
```

**What the agent cannot tell from the text.** Why deleting is refused. Which close reason fits: an issue filed by mistake is neither completed nor, in plain words, "not planned", and the close reason for a duplicate is not offered. And that the /ghi-write skill has an agent record an issue's outcome in the issue's GHI-MD, and wait for that edit to merge, before closing the issue.

**Proposed text.**

```
Do not delete this project's issues: a deleted issue cannot be restored.
Record the outcome in the issue's GHI-MD, the first file the issue's body links to, then open the edit's pull request with: python3 scripts/ghi-issue-write.py edit <path>
Close the issue after that edit's pull request has merged and its rerun has finished, with the line below that fits.
If this issue covers the same work as another issue: gh issue close <number> --duplicate-of <the other issue's number>
If the issue's work is done: gh issue close <number> --reason completed
If the issue will not be done, or was filed by mistake and duplicates no other issue: gh issue close <number> --reason "not planned"
If the issue has no GHI-MD, stop and tell the user.
```

**What changes.** `DELETE_REFUSAL`; `.claude/hooks/ghi-issue-write-redirect-test.py` compares against the constant, and every line starts with a listed opening word. The record line, the wait and the duplicate line are new; the /ghi-write skill already says to record the outcome before closing and names the duplicate close reason, and `gh issue close --duplicate-of` sets that close reason. Under `.claude/`: the exact text must be approved-by-walk.

### 3. Writing from a detached HEAD

**When an agent sees this.** A subagent checks out a pull request's head commit directly, with `git checkout --detach 6880db6d`, and then edits `nc-systems/handoff/handoff-supervisor.py`. The guard refuses the edit. The guard is a user-block: only the user's approval, quoted into its marker, lets one write through.

**What the agent is told today** (`.claude/hooks/session-location-write-guard.py:76`):

```
Refusing to write {path}: this session's checkout is on a detached HEAD — no branch points at its commits, so anything committed here is unreachable by name and will be lost with the worktree. Get onto a branch first (git switch -c <a-branch-name>), or move to your own seat worktree, then resubmit. If the user has approved writing from this exact state, quote his approval words into {marker} at the checkout root and resubmit — the marker is consumed by the one call it approves. Create the marker with a shell command (printf/echo): writing it with the Write tool would be refused by this same guard.
```

**What the agent cannot tell from the text.** When to make a branch and when to move. On 2026-10-01 both fix-round subagents of the MD-skills seat working on PR [The instruction-file guard protects the files the user reviews, by where they sit](https://github.com/nedschorus/nedschorus/pull/852) met this refusal in a worktree detached at that pull request's pushed head. Both made a branch, which the text allows, and both then left the branch unrebased although other hooks called it never pushed, so as not to rewrite the head under review. Open question 4 says why those hooks are wrong about such a branch. "Lost with the worktree" also overstates: a commit on a detached HEAD can still be put on a branch, until nothing names the commit any more.

**Proposed text.**

```
Refusing to write {path}: this checkout is on a detached HEAD. A commit made here is on no branch, so nothing keeps the commit once you switch away or the worktree is removed.
If this checkout was made for the work you are doing, make a branch here (git switch -c <a-branch-name>), then try the write again.
If this checkout belongs to another session, do the work in your own checkout instead.
If the user has approved writing from this exact state, quote his approval words into {marker} at the checkout root with a shell command (printf or echo), then try the write again; the marker is used up by the one call it approves, and the Write tool cannot create the marker, because this guard refuses that Write.
```

**What changes.** `DETACHED_DENY_MESSAGE`; the test case "the detached refusal teaches the branch fix" in `.claude/hooks/session-location-write-guard-test.py` looks for `git switch -c` and still passes. The proposed text assumes the fix of open question 4 has merged, so a branch made here at a pull request's pushed head is not rebased by any hook. A rebase stopped on a conflict also leaves HEAD detached, and this guard then refuses the edit that would resolve the conflict; open question 7. Under `.claude/`: the exact text must be approved-by-walk.

### 4. Writing to backup state

**When an agent sees this.** An agent tries to edit `/etc/timeshift/timeshift.json` on ned-box. The guard is a hard-block: nobody's words clear it.

**What the agent is told today** (`.claude/hooks/backup-and-snapshot-write-guard.py:50`):

```
Refusing to modify {path}: it is backup state (Timeshift snapshots or configuration on ned-box, or Time Machine state on the Mac), and backup state is never an agent's to write — there is no approval lane for this, in this or any conversation (user-ruled 2026-08-17). If you are trying to RECOVER a file, nothing here is in your way: snapshots are ordinary readable directories, so copy the file out of the snapshot tree instead of writing anything. If backup configuration genuinely needs changing, that is the user's to do at his own keyboard — tell him what needs changing and why, and stop.
```

**What the agent cannot tell from the text.** What to do when the backup cannot be read: a Time Machine backup can be a disk image, not an ordinary directory, and a snapshot may not be mounted. The text also carries a ruling's date, and puts three instructions in one paragraph.

**Proposed text.**

```
Refusing to modify {path}: it is backup state (Timeshift snapshots or configuration on ned-box, or Time Machine state on the Mac). Backup state is never an agent's to write, because backups are how damage done by any agent is undone, and there is no override for this in this or any conversation.
If you are trying to recover a file, copy the file out of the snapshot or backup without writing to it; scripts/find-deleted-path-across-backups.py finds the copies.
If you cannot read the snapshot or backup, tell the user and stop.
If backup configuration needs changing, tell the user what needs changing and why, and stop: the change is the user's to make at his own keyboard.
```

**What changes.** `DENY_MESSAGE`. `.claude/hooks/backup-and-snapshot-write-guard-test.py` looks for four phrases: "never an agent's to write", "copy the file out" and "his own keyboard" are kept; its test case "the refusal offers no approval lane" changes to look for "no override". Under `.claude/`: the exact text must be approved-by-walk.

### 5. AppleScript typing into a window

**When an agent sees this.** An agent wants to show the user a log and runs `osascript -e 'tell application "iTerm" to tell current session of current window to write text "tail -f run.log"'`. The guard refuses, because typed keystrokes mix with whatever the user is typing in that window.

**What the agent is told today** (`scripts/synthetic-keystroke-guard-hook.py:129`):

```
Blocked: AppleScript synthetic typing — iTerm `write text`, System Events `keystroke`/`key code` — sends keystrokes that race the user's real typing and splice (this exact failure corrupted a command on 2026-08-17; rule on nedschorus#27). To open a terminal window running a command for the user, run: scripts/open-iterm-window-running-command <command...> — it passes the command as the new session's own process, no keystrokes involved.
```

**What the agent cannot tell from the text.** What to do when the keystrokes were meant for some application other than a terminal: System Events can type into any of them. The parenthesis carries a date, an incident and an issue number.

**Proposed text.**

```
Blocked: AppleScript synthetic typing (iTerm `write text`, System Events `keystroke` or `key code`) sends keystrokes that race the user's real typing and interleave with it.
If you want a terminal window running a command for the user, run: scripts/open-iterm-window-running-command <command...> (it starts the command as the new window's own process, with no keystrokes).
If you meant to type into another application, stop and tell the user what you wanted typed.
```

**What changes.** `SYNTHETIC_TYPING_REASON`. `scripts/synthetic-keystroke-guard-hook-test.py` looks only for the name `scripts/open-iterm-window-running-command`, which is kept.

### 6. Typing into a tmux session someone is attached to

**When an agent sees this.** An agent runs `tmux send-keys -t merge-lane-2 "status" Enter` to nudge another agent-seat while the user has that seat's terminal open.

**What the agent is told today** (`scripts/synthetic-keystroke-guard-hook.py:138`):

```
Blocked: tmux session '{target}' has an attached client, so send-keys/paste-buffer would splice into whoever is typing there (nedschorus#27; evidence on #37). Injection is permitted only into detached sessions. To show the user something, open them a window with scripts/open-iterm-window-running-command; for agent-to-agent messaging the durable path is the nedschorus#37 inbox design.
```

**What the agent cannot tell from the text.** How to reach the other agent, which is what the agent in the example wanted. The last clause points at "the nedschorus#37 inbox design"; GHI [Claude turn/start and turn/steer equivalents: inject a message into an idle session, steer an active turn](https://github.com/nedschorus/nedschorus/issues/37) is closed as completed, and a design is not a command. Today the agent-seats message each other with Claude Code's SendMessage tool, which delivers a message into another agent's session without typing into its terminal, across the two machines: the MD-skills seat on the Mac reaches merge-lane-2 on ned-box that way. No standing instruction in the repository names the tool yet; open question 1. The window opener also runs on the Mac only.

**Proposed text**, with the messaging lines as open question 1 recommends:

```
Blocked: tmux session '{target}' has an attached client, so send-keys or paste-buffer would interleave with the typing of whoever is attached. Sending keystrokes is permitted only into detached sessions.
If the keystrokes carry a message for another agent-seat, send the message with the SendMessage tool instead; the ListAgents tool lists the seats' addresses.
If SendMessage cannot reach the seat, tell the user.
If the purpose is to show the user something: on the Mac, open a window with scripts/open-iterm-window-running-command <command...>; on ned-box, tell the user the command to run.
Otherwise, do not send the keystrokes: tell the user what you were trying to do.
```

**What changes.** `ATTACHED_REASON`; the test case at line 258 of `scripts/synthetic-keystroke-guard-hook-test.py` looks for `#37` in the text and changes with it.

### 7. A tmux session the guard could not check

**When an agent sees this.** The same `tmux send-keys`, aimed at a session on ned-box, when the guard's own probe over ssh times out.

**What the agent is told today** (`scripts/synthetic-keystroke-guard-hook.py:147`):

```
Blocked: could not verify that tmux target '{target}' has no attached client ({error}). Verify yourself with: {probe} — 0 means detached — then re-run this command with CLAUDE_VERIFIED_DETACHED=1 prefixed. Never inject keystrokes at a session someone may be typing in (nedschorus#27).
```

**What the agent cannot tell from the text.** What to do when the probe does not print 0, or fails. And `{probe}` is not always one command: when the guarded command names no tmux socket and the target has a per-seat tmux server, `probe_recipe()` fills `{probe}` with a first probe, a parenthesis, and a second probe for the seat's own server. The text then speaks of one output where there can be two. The override, `CLAUDE_VERIFIED_DETACHED=1`, is the agent's own probe, set through an environment variable; none of the glossary's three kinds names it.

**Proposed text.**

```
Blocked: could not verify that tmux target '{target}' has no attached client ({error}). Keystrokes sent into a session someone is typing in interleave with that typing.
Verify with this probe: {probe}
If that probe prints "no server running", probe the seat's own tmux server: {per_seat_probe}
If a probe prints 0, the session is detached: run this command at once with CLAUDE_VERIFIED_DETACHED=1 prefixed.
If no probe prints 0, or the probes fail, do not send the keystrokes.
If the keystrokes carry a message for another agent-seat, send the message with the SendMessage tool instead.
If the purpose is to show the user something: on the Mac, open a window with scripts/open-iterm-window-running-command <command...>; on ned-box, tell the user the command to run.
Otherwise, tell the user what you were trying to do.
```

**What changes.** `UNVERIFIED_REASON`, and `probe_recipe()` returns its two probes separately so each gets its own line; the third line appears only when there is a per-seat probe. `scripts/synthetic-keystroke-guard-hook-test.py` pins "could not verify", "session_attached" and "CLAUDE_VERIFIED_DETACHED=1" in this text; all three are kept.

### 8. A tmux target that still holds a variable

**When an agent sees this.** An agent runs `tmux send-keys -t "$SEAT" "status" Enter`. The guard reads the command before the shell fills in `$SEAT`, so the guard sees the variable and not a session's name.

**What the agent is told today** (`scripts/synthetic-keystroke-guard-hook.py:155`):

```
Blocked: tmux target '{target}' contains an unexpanded variable or substitution placeholder, so this guard cannot verify the real target is detached — probing the literal text would misjudge it. Inline the literal session name, or verify detachment yourself with: {probe} — 0 means detached — then re-run with CLAUDE_VERIFIED_DETACHED=1 prefixed (rule: nedschorus#27).
```

**What the agent cannot tell from the text.** Which of the two instructions applies. And the second instruction does not work in two ordinary cases. When the guarded command runs over ssh, `{probe}` puts the remote tmux command inside single quotes, so the variable is expanded on the far machine, where it is usually unset, and the probe reads the wrong session. When the target is xargs' or parallel's `{}`, which the guard also refuses with this message, no variable is set anywhere, and the command can name several sessions. An agent that sets `CLAUDE_VERIFIED_DETACHED=1` on such a probe's answer sends keystrokes the guard was written to stop.

**Proposed text.**

```
Blocked: tmux target '{target}' holds an unexpanded variable (a shell variable or command substitution) or an xargs or parallel replacement string ({}), so this guard cannot check that the real session is detached.
If the target is a shell variable or command substitution, find the session's name where it is set (echo it), write the name into the command in place of the variable, and run the command again.
If the target is xargs' or parallel's {}, list the sessions first, then send to each by name, one command per session.
```

**What changes.** `UNRESOLVED_TARGET_REASON`; the literal `{}` is written `{{}}` in the format string. Test case F8a in `scripts/synthetic-keystroke-guard-hook-test.py` looks for "unexpanded variable", which is kept, and for "CLAUDE_VERIFIED_DETACHED=1", which this text drops; F8a changes with it.

### 9. A tmux command that names no target

**When an agent sees this.** An agent runs `tmux send-keys "status" Enter` with no `-t`.

**What the agent is told today** (`scripts/synthetic-keystroke-guard-hook.py:164`):

```
Blocked: this send-keys/paste-buffer names no -t target, so the keystrokes would land in tmux's current session — possibly the very one the user is attached to — and cannot be verified detached. Name the session with -t, or use scripts/open-iterm-window-running-command / the nedschorus#37 inbox instead (rule: nedschorus#27).
```

**What the agent cannot tell from the text.** Which instruction fits which purpose, and what "the nedschorus#37 inbox" is.

**Proposed text**, with the messaging lines as open question 1 recommends:

```
Blocked: this send-keys or paste-buffer names no -t target, so the keystrokes would go to tmux's current session, which may be the session the user is typing in.
If the keystrokes are meant for a detached session, name that session with -t and run the command again.
If the keystrokes carry a message for another agent-seat, send the message with the SendMessage tool instead; the ListAgents tool lists the seats' addresses.
If the purpose is to show the user something: on the Mac, open a window with scripts/open-iterm-window-running-command <command...>; on ned-box, tell the user the command to run.
Otherwise, do not send the keystrokes: tell the user what you were trying to do.
```

**What changes.** `NO_TARGET_REASON`. Two test cases in `scripts/synthetic-keystroke-guard-hook-test.py`, at lines 290 and 347, look for "no -t target", which is kept.

### 10. The handoff instruction

**When an agent sees this.** An agent-session has used the share of its context window set as the reincarnation threshold, half by default. At the end of a turn the hook keeps the turn open and prints one line. The /handoff skill then writes the session-handoff, and the handoff-supervisor starts a fresh agent-session.

**What the agent is told today** (`scripts/handoff-context-threshold-hook.py:240`):

```
Run the handoff skill now.
```

**What the agent cannot tell from the text.** What happened and why. The line names no cause, so an agent in the middle of a task cannot tell that the line comes from the reincarnation threshold and not from the user or from the task.

**Proposed text.**

```
This session has used {used_percentage:.0f}% of its context window, which has reached the reincarnation threshold. Run the /handoff skill now.
```

The comment above the constant forbids restating the skill's procedure in the message. The added sentence states the cause and none of the procedure.

**What changes.** `HANDOFF_INSTRUCTION` becomes a template filled with the share the hook has already computed. Twelve test cases in `scripts/handoff-context-threshold-hook-test.py` hold the old line, ten that expect the line and two that expect its absence; the test case "hook names the handoff skill" looks for "handoff skill", which "/handoff skill" keeps.

### 11. A branch the hook could not bring up to date

**When an agent sees this.** The agent's branch has no copy on GitHub and main has moved. At the end of a turn the hook tries to rebase the branch and cannot, for example because one tracked file has uncommitted changes. The hook reports the state, gives this instruction, and, as with every note the hook gives, appends a line saying the note is not for the user.

**What the agent is told today** (`scripts/checkout-freshness-catch-up.py:126`, after a heading such as "checkout-freshness: my-branch is 12 behind origin/main (1 own commit(s); head unpushed). Not updated: 1 uncommitted tracked change(s)."):

```
This branch has never been pushed, so nobody else has it. Bring it up to date now: commit or set aside any uncommitted work, run `git rebase origin/main`, then rerun the test suites for what you touched. If the rebase stops on a conflict, `git rebase --abort` puts everything back; then resolve it by hand or stay behind, which costs nothing at merge.
Do not report this to the user: he does not need to hear that main moved, or what other agents merged, unless it changes the work you are doing with him.
```

**What the agent cannot tell from the text.** When to resolve and when to stay behind; open question 2. And "nobody else has it" is false today for a branch cut at a pull request's pushed head, which this hook cannot yet tell from a new branch; open question 4, whose fix makes the sentence true.

**Proposed text.**

```
This branch has never been pushed, so nobody else has it. Bring the branch up to date now: commit or set aside any uncommitted work, run `git rebase origin/main`, then rerun the test suites for what you touched.
If the rebase stops on a conflict that you can resolve now, resolve the conflict and run `git rebase --continue`.
If the rebase stops on a conflict that you cannot resolve now, run `git rebase --abort`, which puts everything back, and finish what you are doing first; this note comes back at each turn's end until the branch is up to date.
Before you push this branch for the first time, run `git fetch origin`, rebase onto origin/main again, rerun the test suites, and push; if a conflict there cannot be resolved, stop and tell the user which files conflict, because a conflict you cannot resolve changes the work you are doing with him.
```

**What changes.** `REBASE_ADVICE`. One test case in `scripts/checkout-freshness-catch-up-test.py` looks for "`git rebase --abort` puts everything back", which the proposed text rewords; that test case changes. The first sentence is true once the fix of open question 4 has merged: a branch whose commits are already on GitHub is then no longer called never pushed. Resolving the conflict with the Edit tool meets message 3's refusal while the rebase is stopped; open question 7.

### 12. An edit to a file main has changed, on a detached HEAD or with no branch state reported

**When an agent sees this.** An agent edits `scripts/recover-crashed-seats.py`, and main has changed that file since this checkout's merge base with origin/main. When the checkout is on a branch, the warning ends with an instruction. When git did not answer, or the checkout is on a detached HEAD, the instruction is dropped. A detached HEAD is rare here: `session-location-write-guard.py` refuses a write from a detached HEAD (message 3), so this warning reaches a detached checkout normally only after the user has approved that write.

**What the agent is told today** (`scripts/obsolete-file-edit-warning-hook.py:274`):

```
obsolete-file-edit-warning: you just changed scripts/recover-crashed-seats.py, which 3 commit(s) on origin/main have changed since this branch's merge base and this checkout does not have.
```

**What the agent cannot tell from the text.** Why the finding matters and what to do about it. On a detached HEAD, "this branch" also names a branch that is not there.

**Proposed text.** The first line, for every state of the checkout (when git could not count the commits, the line says "which origin/main has changed since …" as today):

```
obsolete-file-edit-warning: you just changed {path}, which {count} commit(s) on origin/main have changed since this checkout's merge base with origin/main and this checkout does not have, so your edit is built on an old copy of the file.
```

Then, on a detached HEAD:

```
If git status says a rebase is in progress, finish the rebase first, and skip the lines below until it is done.
This checkout is on a detached HEAD: make a branch (git switch -c <a-branch-name>) before you commit, because a commit on a detached HEAD is on no branch.
Compare your edit with main's copy: git diff origin/main -- {path}
If main's changes touch the lines you edited, bring the branch up to date with origin/main before you commit, then check your edit again.
```

Or, when git did not report the branch state:

```
git did not report this checkout's branch state: run git status to see it.
Compare your edit with main's copy: git diff origin/main -- {path}
If main's changes touch the lines you edited, bring the branch up to date with origin/main before you commit, then check your edit again.
If git status fails too, stop and tell the user before you commit.
```

**What changes.** `head_advice` returns lines for the two states it now returns nothing for, and `obsolete_file_warning_line` gains "this checkout's merge base with origin/main" and the "so your edit…" clause for every variant, including the one with no count. `NEVER_PUSHED_ADVICE` keeps "This branch has never been pushed, so nobody else has it", which the fix of open question 4 makes true. `scripts/obsolete-file-edit-warning-hook-test.py` needs a test case for each state.

### 13. A second file under a tracked file's name

**When an agent sees this.** In this repository a basename, the last part of a file's path, belongs to one tracked file, so that the file can be cited by its name; `SKILL.md`, `README.md` and `.gitkeep` are the exceptions, fixed by the tools that read them. On 2026-10-01 the handoff-supervisor on the branch of PR [The instruction-file guard protects the files the user reviews, by where they sit](https://github.com/nedschorus/nedschorus/pull/852) told the subagent that refreshes a system's overview to write `docs/nedschorus-wiki/queue/nedschorus-handoff-system-overview.md`, a draft of the tracked page of the same name.

**What the agent is told today** (`scripts/file-name-collision-warning-hook.py:173`):

```
file-name-collision-warning: you wrote docs/nedschorus-wiki/queue/nedschorus-handoff-system-overview.md; the name nedschorus-handoff-system-overview.md is already docs/nedschorus-wiki/nedschorus-handoff-system-overview.md.
If you are moving the file, delete docs/nedschorus-wiki/nedschorus-handoff-system-overview.md in this change.
If both files are meant to exist, rename the one you just wrote by CLAUDE.md's naming rule, and update what you have already written to point at the new name.
```

**What the agent cannot tell from the text.** The rule, which the first line leaves to inference. And today's text covers two conditions where there are three: the subagent was neither moving the page nor keeping both files for good. Line two deletes the live page; line three renames the draft, and the step that expects the draft at its first path then finds nothing. Reviewers caught this before an agent acted on it, and that pull request now names its draft `nedschorus-<system>-system-overview-draft.md`. Any other agent that drafts a new version of a tracked file still meets today's text.

**Proposed text.**

```
file-name-collision-warning: you wrote {path}; the name {name} is already {already}. A basename, other than SKILL.md, README.md and .gitkeep, belongs to one tracked file, so the file can be cited by its basename.
If you are moving the file, delete {moved_from} in this change.
If the file you wrote is a draft of a new version of {draft_of}, rename the file you wrote so its name ends -draft before the extension, or at the end of a name that has none; tell whoever expects the old path the new one; and leave {draft_of} as it is.
If both files are meant to exist and the file you wrote is not a draft, rename the file you wrote by CLAUDE.md's naming rule, and update what you have already written to point at the new name.
If you wrote the file by mistake, delete the file you wrote.
```

**What changes.** `collision_warning_line`. `{already}` and `{moved_from}` are the values the code builds today: every matching path, and the one matching path or "the file you moved from". `{draft_of}` is new: the one matching path, or "one of those files" when several match. The `-draft` ending is that pull request's convention for overview drafts; the file-naming page is where it would become general. A `-draft` name that is taken too draws this same warning again. The test case "the warning arrives as three lines, one instruction to a line" in `scripts/file-name-collision-warning-hook-test.py` becomes five lines.

## Messages an open pull request adds

PR [The instruction-file guard protects the files the user reviews, by where they sit](https://github.com/nedschorus/nedschorus/pull/852), at its head commit [An overview's draft takes a name of its own, its reminder goes out once a day, and the guard's test pins the hyphen of the two exempt endings](https://github.com/nedschorus/nedschorus/pull/852/commits/229c7c95b6dbac390d8ee7dde76bac6e0b975733), adds a program an agent runs, `nc-systems/handoff/daily-overview-refresh-reminder-mark.py`, which is on that pull request's branch and not yet on main, and adds or rewords five lines on the handoff-supervisor's console. The texts below were read from that head. None has had a /cold-read.

The program writes a daily-overview-refresh-reminder-mark: the dated file in the log-store, one per system per day, recording that an agent-seat has shown the user that day's refreshed draft of the system's overview page, so that other agent-seats do not show it again. An agent-seat runs the program after the agent-seat has shown the user the difference between the overview page and the refreshed draft. The mark is written only after that, so an agent-seat that reincarnates in between gets the same reminder.

**Read by the agent that runs `daily-overview-refresh-reminder-mark.py`** (lines 150, 163 and 167 of the program):

```
daily-overview-refresh-reminder-mark: pass the name of the system's directory under nc-systems/, such as handoff, in place of 'docs/nedschorus-wiki/nedschorus-handoff-system-overview.md'.
```

```
daily-overview-refresh-reminder-mark: the mark for handoff was not written (ssh: connect to host ned-box port 22: No route to host) — tell the user this message, and run this command again once the cause is fixed.
```

```
daily-overview-refresh-reminder-mark: the reminder for handoff is recorded for 2026-10-01 in nedlern@ned-box:/home/nedlern/nedschorus-logs/daily-overview-refresh-reminder-marks/2026-10-01-handoff.txt
```

The first message does not say that nothing was written. The second says the mark "was not written" when a timeout can follow a write that succeeded; does not say what an unwritten mark costs; and sets no limit on the retry, although the mark's file name carries the Pacific date of the run, so a retry after midnight marks a day on which the user saw nothing. The third is a confirmation and needs no change. Proposed:

```
daily-overview-refresh-reminder-mark: no daily-overview-refresh-reminder-mark was written, because {value} is not a system's name.
Run this again with the name of the system's directory under nc-systems/, such as handoff.
```

```
daily-overview-refresh-reminder-mark: the mark for {system} could not be confirmed as written, so the next agent-seat to reincarnate today may show the user the same overview refresh again: {error}
Tell the user what the error above says.
When the user says the cause is fixed, run this command again, the same day in Pacific time; after midnight Pacific, do not run it, because the mark is dated by the day the command runs; the next agent-seat to show the refresh writes the new day's mark.
```

**Read by whoever watches the handoff-supervisor's console**, not by the agent-seat's agent (`nc-systems/handoff/handoff-supervisor.py`, lines 1736 to 1783 at that head). They are here as the background to open question 5. The first rewords a line on main; the other four are new:

```
handoff-supervisor: overview check could not ask GitHub which open pull requests change an overview, so no line is withheld for a pull request: {error}
handoff-supervisor: overview check for {system} withheld its line: the open pull request "{title}" ({url}) already changes {overview path}
handoff-supervisor: overview check could not read the day's reminder marks in {marks directory}, so no line is withheld for a reminder already given: {error}
handoff-supervisor: overview check for {system} gives its line: the day's reminder mark {mark} does not hold the time it was written, but {text}
handoff-supervisor: overview check for {system} withheld its line: the user was shown this overview's refresh today, at {time}, as {mark} records
```

Each console report says what happened and why, and each is a report, not an instruction, so no rewording is proposed.

## Related issues

`scripts/ghi-info-ask.py "Is there an open issue about the wording of the messages that hooks, guards and checks hand an agent when they refuse or warn: that each message must say what was refused, why, and what to do instead?"` answered that no open issue states this rule. It named two near neighbours: GHI [main-gatekeeper — the single check-in gate (design: nc-systems/main-gatekeeper/main-gatekeeper-design.md)](https://github.com/nedschorus/nedschorus/issues/3), which rules on the structure of a reply and not its wording, and GHI [A project style guide: words to avoid, a mechanical checker, and a check on unbacked promises](https://github.com/nedschorus/nedschorus/issues/14), the closest home for a phrasing rule.

The defect behind open question 4 is filed as its own GHI: GHI [The checkout-freshness hook treats a new branch cut at a pull request's pushed head as never pushed, and rebases it](https://github.com/nedschorus/nedschorus/issues/913).

## Open questions for the user

1. Messages 6 and 9 send an agent that wants to reach another agent-seat to "the nedschorus#37 inbox", and that GHI is closed: should the two messages name the SendMessage tool, which the agent-seats use today? Recommendation: yes, as proposed; the alternative is to leave the line out, so the agent must find SendMessage unprompted.
2. Message 11 says staying behind main "costs nothing at merge", yet a conflict left unresolved now is a conflict at merge: should that instruction stay? Recommendation: no; the proposed text has the agent fetch and rebase again before the first push.
3. Message 2 gains a line for a duplicate issue, and message 13 gains a line for a draft of an existing file: are both wanted? Recommendation: yes to both.
4. A branch made at a pull request's pushed head, as message 3 instructs, has no copy on GitHub under its own name, so `checkout-freshness-catch-up.py` and `obsolete-file-edit-warning-hook.py` treat the branch as never pushed. The obsolete-file warning then instructs a rebase, and at a main session's turn end the freshness hook rebases the branch itself when the tree is clean, moving a frozen head. Wording cannot fix this; the GHI named under Related issues tracks the fix, which the user asked to have built at once (direction 1 of that GHI: a branch whose commits are already on a branch on GitHub counts as pushed). The messages pull request is cut after that fix merges, and messages 3, 11 and 12 assume it.
5. When the handoff-supervisor cannot read the daily-overview-refresh-reminder-marks because ned-box cannot be reached, the report goes to the console only, so the agent cannot tell the user, as `CLAUDE.md` asks. Recommendation: a change of its own to the handoff-system, after PR [The instruction-file guard protects the files the user reviews, by where they sit](https://github.com/nedschorus/nedschorus/pull/852) merges.
6. Do the two reworded messages of `daily-overview-refresh-reminder-mark.py` go into the open pull request that adds the program, or follow it? Recommendation: follow it, in the pull request that changes the hook messages. That pull request can touch the program only once that pull request has merged, and drafts the two messages against the program as merged.
7. While a rebase or merge is stopped on a conflict, the checkout's HEAD is detached, so `session-location-write-guard.py` refuses the Edit or Write that would resolve the conflict, and message 3 then tells the agent to make a branch in the middle of the rebase. Recommendation: the guard recognises a rebase or merge in progress (`rebase-merge`, `rebase-apply`, `MERGE_HEAD`, `CHERRY_PICK_HEAD` or `REVERT_HEAD` in the worktree's git directory) and lets the write through, in the pull request that changes this guard's message; messages 11 and 12 assume it.

## Later parts

The audit found gaps in four more groups, and left out of its scope three programs that can refuse an agent. Each of these five parts is drafted the same way once this part is reviewed:

- the git hooks that run at commit and push (`scripts/git-client-side-hooks/` and `scripts/git-client-side-hooks-pre-push-conflict-check.py`), 8 of 11 messages with a gap;
- `scripts/merge-gate.sh`, 20 of 27; only the merge-lane runs this program, so this document recommends that the merge-lane's agent-seat draft that part;
- the test suites that enforce a repository-wide rule, 20 of 38, each named in the audit;
- three programs run by hand, `scripts/dangling-path-citation-check.py`, `scripts/stale-code-citation-check.py` and `scripts/md-drift-lint.py`, 19 of 21;
- the three the audit did not read: the create-GHI and edit-GHI refusals of `scripts/ghi-issue-write.py`, `nc-systems/main-gatekeeper/main-gatekeeper.py`, and the lock and directory refusals of `scripts/run-all-test-suites.py`.
