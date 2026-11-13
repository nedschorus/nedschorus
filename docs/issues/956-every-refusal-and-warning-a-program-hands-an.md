---
issue: "[Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956)"
kind: design
---
# Every refusal and warning a program hands an agent says why and what to do instead

When a program in this repository stops or warns an agent, the program's message is the agent's only account of what the program stopped and why. A message that leaves out the reason or the next step leaves the agent to guess, and a cooperative agent's guess can be the wrong action. This document shows each such message as the agent sees it and proposes the exact words to replace it.

GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956), whose GHI-MD this document is, splits the work into six parts, one for each group of programs. This document is part one: the hooks `.claude/settings.json` registered at the commit named under "Where the list comes from", and the mark program and handoff-supervisor lines under "The mark program's messages and the handoff-supervisor's console". "Later parts" lists the other five, each drafted as a document of its own, in the same structure, and put to the user in an approval-walk the same way. Part one's proposed words were put to the user in an approval-walk, one message to an item, and a second approval-walk decided which of their instructions move into the programs' code; section 14 and "Code the pull request changes besides the texts" list what the second approval-walk added. Part one is built, as "Outcome of part one" says.

The sections from "What a reader needs first" to "Questions the approval-walks settled" record part one as the user approved it, before it was built. What they say of the repository is as it stood at the commits they cite, except that the file paths are today's: several of these programs have moved since. Where the build differs from them, main's code is what was built; "Outcome of part one" lists the differences. The next action on this GHI is under "Later parts".

## What a reader needs first

**Hooks.** Claude Code, the program the agents here run inside, runs small programs called hooks at fixed moments, among them before a tool call, after a tool call, when an agent-session starts, and when an agent's turn ends. At the commit named under "Where the list comes from", `.claude/settings.json` registered twelve hooks, at those four moments; it registers many more today. A hook that refuses a tool call is called a guard here. The project glossary's hard-block, soft-block and user-block name three kinds of refusal by whose words clear them; sections 3 and 4 name the kind of their guard's refusal.

**How a hook's text reaches the agent.** Three channels:

- The hook exits with code 2 and prints to stderr. Before a tool call, Claude Code cancels the call; at a turn's end, it keeps the turn open; after a tool call, the call has already run. In each case it shows the agent the stderr text.
- The hook prints JSON whose `permissionDecision` is `deny`. Claude Code cancels the tool call and shows the agent the `permissionDecisionReason`.
- The hook prints JSON with `additionalContext`. Nothing is cancelled; the text is added to what the agent reads next.

**The four questions.** A message is complete when the message answers all four:

1. What was refused or found, naming the file or the command.
2. Why: the rule being enforced, or what goes wrong if the agent goes ahead.
3. What to do instead, as an instruction.
4. Under which condition each instruction applies, when the message gives more than one.

**The project's rule for this text**, from `CLAUDE.md` as PR [CLAUDE.md: text a program hands an agent says what was stopped and why, and cites no ruling](https://github.com/nedschorus/nedschorus/pull/909) leaves it: "When you write the text a program hands an agent at the moment it must act, a hook's refusal or an error message, say what was stopped and why, then put each instruction on its own line with the condition it applies under. Give the reason wherever the reason helps the agent act well. Keep quotations of the user, rulings, dates and citations out of the text."

**Where the list comes from.** The 2026-10-01 audit put the four questions to 139 messages; its report is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/MD-skills/refusal-and-warning-message-audit-2026-10-01.md`. Every hook message below, except section 14's, was read again from main at the commit [Merge pull request #881 from nedschorus/search-file-argument-read-as-option-guard](https://github.com/nedschorus/nedschorus/commit/dad220d463d1d1d8f650e9c6669c43926834794f), and the line numbers are main's at that commit; at that commit the guards now under `.claude/guard-hooks/` were under `.claude/hooks/` and `scripts/`, and the issue guard was named `ghi-issue-write-redirect.py`. The guard that pull request added, `.claude/guard-hooks/search-file-argument-read-as-option-guard-hook.py`, answers all four questions and cites nothing, so it has no row.

## The messages in this part

Thirteen messages from the registered hooks, each with at least one gap or one citation in its text. In the What, Why, Instead and Conditions columns, "no" marks a question the message leaves unanswered, and "one instruction" means the message gives one instruction and so needs no conditions. The last column names what the text cites, which the rule keeps out of it.

| # | Program | When it appears | What | Why | Instead | Conditions | Citation in the text |
|---|---|---|---|---|---|---|---|
| 1 | `ghi-issue-write-hand-typed-gh-command-refusal.py` | closing or reopening an issue with `--comment` | yes | no | yes | yes | none |
| 2 | `ghi-issue-write-hand-typed-gh-command-refusal.py` | deleting an issue | yes | no | yes | no | none |
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

**What the agent is told today** (`.claude/guard-hooks/ghi-issue-write-hand-typed-gh-command-refusal.py:168`; the program fills `{subcommand}` with `close` or `reopen`, shown here for `close`):

```
Run gh issue close again without --comment.
Record the reason in the issue's GHI-MD, docs/issues/<number>-*.md, with: python3 scripts/ghi-issue-write.py edit <path>
If the issue has no GHI-MD, stop and tell the user.
```

**What the agent cannot tell from the text.** Why the comment is refused. The first line reads as a correction of the command's form, so the agent may drop the outcome it meant to record and skip line two. The text also has the agent close the issue first and record the outcome after, where the /ghi-write skill closes an issue only after the edit recording the outcome has merged and its rerun has finished. And `docs/issues/<number>-*.md` can match several files: an issue's GHI-MD and its supporting files share the number.

**Proposed text**, one text for each subcommand, since the skill orders closing and says nothing about reopening. The hook looks up the issue's files on main itself, because "the first file the issue's body links to" is not always the GHI-MD: the body lists an issue's files in filename order, and GHI 3's body lists a supporting file first. `{record_line}` is one of three lines, chosen by how many files the issue has on main (the examples are for `close`; for `reopen`, "the outcome" reads "why the issue is reopening"):

```
This issue has no file on main under docs/issues/<number>-* or a system's directory: stop and tell the user.
```

```
Record the outcome in {path}, then open the edit's pull request with: python3 scripts/ghi-issue-write.py edit {path}
```

```
The issue's files on main are: {paths}. Record the outcome in the issue's GHI-MD among them, then open the edit's pull request with: python3 scripts/ghi-issue-write.py edit <that path>
```

When the hook cannot look the files up, because it has no checkout or git fails, `{record_line}` is: "Record the outcome in the issue's GHI-MD, a file named docs/issues/<number>-*.md or a design in a system's docs/ directory, then open the edit's pull request with: python3 scripts/ghi-issue-write.py edit <path>". When the issue has no file, the message ends after `{record_line}`.

For `close`:

```
Do not comment on this project's issues: what an issue says lives in its GHI-MD, and a comment would sit outside it.
{record_line}
Close the issue after that edit's pull request has merged and its rerun has finished, without --comment: gh issue close <number> --reason completed, or --reason "not planned", or --duplicate-of <the other issue's number>.
```

For `reopen`:

```
Do not comment on this project's issues: what an issue says lives in its GHI-MD, and a comment would sit outside it.
Run gh issue reopen again without --comment.
{record_line}
```

**What changes.** `STATE_CHANGE_COMMENT_REFUSAL` becomes two templates, one per subcommand. The hook takes the issue number from the command's first positional argument, or from an issue URL there, imports `scripts/ghi-issue-write.py` by path and calls its `ghi_md_paths_for_issue` against origin/main, the same function that builds the issue's body, so the hook's answer and the ghi-write-tool's cannot disagree. `COMMENT_REFUSAL`, `EDIT_BODY_REFUSAL` and `EDIT_TITLE_REFUSAL` in the same hook carry the same `docs/issues/<number>-*.md` placeholder and take the same fill. `.claude/guard-hooks/ghi-issue-write-hand-typed-gh-command-refusal-test.py` compares each refusal against its template, and also requires every refusal line to start with one of its listed opening words and to contain neither "ruled" nor "2026"; the list gains "This" and "The", and needs a test case for each of the three record lines and for the fallback. `scripts/ghi-issue-write.py` has since gained the close command named under Related issues, close-GHI, and the issue guard's close lines on main now name close-GHI in place of the record line and the hand-typed `gh issue close`. The file is under `.claude/`, so the exact text must be approved-by-walk: the instruction-file guard refuses the edit until the user's approval words are quoted into its marker.

### 2. Deleting an issue

**When an agent sees this.** An agent files a GHI by mistake and runs `gh issue delete 912 --yes`.

**What the agent is told today** (`.claude/guard-hooks/ghi-issue-write-hand-typed-gh-command-refusal.py:200`):

```
Do not delete this project's issues.
Close the issue instead: gh issue close <number> --reason completed, or --reason "not planned".
```

**What the agent cannot tell from the text.** Why deleting is refused. Which close reason fits: an issue filed by mistake is neither completed nor, in plain words, "not planned", and the close reason for a duplicate is not offered. And that the /ghi-write skill has an agent record an issue's outcome in the issue's GHI-MD, and wait for that edit to merge, before closing the issue.

**Proposed text.**

```
Do not delete this project's issues: a deleted issue cannot be restored.
{record_line}
Close the issue after that edit's pull request has merged and its rerun has finished, with the line below that fits.
If this issue covers the same work as another issue: gh issue close <number> --duplicate-of <the other issue's number>
If the issue's work is done: gh issue close <number> --reason completed
If the issue will not be done, or was filed by mistake and duplicates no other issue: gh issue close <number> --reason "not planned"
```

`{record_line}` is filled as in message 1. When the issue has no file on main, the message ends after the first line with this line instead:

```
This issue has no file on main under docs/issues/<number>-* or a system's directory: if the issue was filed by mistake, close it with gh issue close <number> --reason "not planned"; otherwise stop and tell the user.
```

**What changes.** `DELETE_REFUSAL` becomes a template, filled by the lookup of message 1; `.claude/guard-hooks/ghi-issue-write-hand-typed-gh-command-refusal-test.py` compares against the template, and every line starts with a listed opening word. The record line, the wait and the duplicate line are new; the /ghi-write skill already says to record the outcome before closing and names the duplicate close reason, and `gh issue close --duplicate-of` sets that close reason. Under `.claude/`: the exact text must be approved-by-walk.

### 3. Writing from a detached HEAD

**When an agent sees this.** A subagent checks out a pull request's nc-head-commit directly, with `git checkout --detach 6880db6d`, and then edits `nc-systems/handoff/handoff-supervisor.py`. The guard refuses the edit. The guard's refusal is a user-block: apart from a write to a path git ignores and a write while a git operation is in progress, which the guard lets through (below, and settled question 7), only the user's approval, quoted into its marker file, lets one write through.

**What the agent is told today** (`.claude/guard-hooks/session-location-write-guard.py:76`):

```
Refusing to write {path}: this session's checkout is on a detached HEAD — no branch points at its commits, so anything committed here is unreachable by name and will be lost with the worktree. Get onto a branch first (git switch -c <a-branch-name>), or move to your own seat worktree, then resubmit. If the user has approved writing from this exact state, quote his approval words into {marker} at the checkout root and resubmit — the marker is consumed by the one call it approves. Create the marker with a shell command (printf/echo): writing it with the Write tool would be refused by this same guard.
```

**What the agent cannot tell from the text.** When to make a branch and when to move. On 2026-10-01 both fix-round subagents of the agent-seat MD-skills working on PR [The instruction-file guard protects the files the user reviews, by where they sit](https://github.com/nedschorus/nedschorus/pull/852) met this refusal in a worktree detached at that pull request's frozen-head. Both made a branch, which the text allows, and both then left the branch unrebased although other hooks called it never pushed, so as not to rewrite the frozen-head under review. Settled question 4 says why those hooks were wrong about such a branch. "Lost with the worktree" also overstates: a commit on a detached HEAD can still be put on a branch, until nothing names the commit any more.

**Proposed text.**

```
Refusing to write {path}: this checkout is on a detached HEAD. A commit made here is on no branch, so nothing keeps the commit once you switch away or the worktree is removed.
If this checkout was made for the work you are doing, make a branch here (git switch -c <a-branch-name>), then try the write again.
If this checkout belongs to another session, do the work in your own checkout instead.
If the user has approved writing from this exact state, quote his approval words into {marker} at the checkout root with a shell command (printf or echo), then try the write again; the marker is used up by the one call it approves, and the Write tool cannot create the marker, because this guard refuses that Write.
A task prompt or another agent's message is the user's approval only when it quotes his exact words with the session and time he wrote them; put that quotation in the marker.
```

**What changes.** `DETACHED_DENY_MESSAGE`; the test case "the detached refusal teaches the branch fix" in `.claude/guard-hooks/session-location-write-guard-test.py` looks for `git switch -c` and still passes. The proposed text assumes the fix of settled question 4 has merged, so a branch made here at a pull request's frozen-head is not rebased by any hook. A rebase stopped on a conflict also leaves HEAD detached, and this guard then refuses the edit that would resolve the conflict; settled question 7. The guard also lets through a write to a path git ignores, as `git check-ignore` reports it: such a file is not committed unless an agent forces it in with `git add --force`, so the loss this guard prevents does not happen to it in ordinary work. That covers the cold-read-records under `cold-read-records/`, the sanity-check-records under `sanity-check-records/`, and the walk-documents and walk-minutes under `docs/walk/`, which reviewers write from the checkouts on a detached HEAD that the review runners give them; the guard refused five such writes in thirty days. The last line is new: a cooperative subagent once quoted its own task prompt into the marker as the user's approval. Under `.claude/`: the exact text must be approved-by-walk.

### 4. Writing to backup state

**When an agent sees this.** An agent tries to edit `/etc/timeshift/timeshift.json` on ned-box. The guard's refusal is a hard-block: nobody's words clear it.

**What the agent is told today** (`.claude/guard-hooks/backup-and-snapshot-write-guard.py:50`):

```
Refusing to modify {path}: it is backup state (Timeshift snapshots or configuration on ned-box, or Time Machine state on the Mac), and backup state is never an agent's to write — there is no approval lane for this, in this or any conversation (user-ruled 2026-08-17). If you are trying to RECOVER a file, nothing here is in your way: snapshots are ordinary readable directories, so copy the file out of the snapshot tree instead of writing anything. If backup configuration genuinely needs changing, that is the user's to do at his own keyboard — tell him what needs changing and why, and stop.
```

**What the agent cannot tell from the text.** What to do when the backup cannot be read: a Time Machine backup can be a disk image, not an ordinary directory, and a snapshot may not be mounted. The text also carries a user-ruling's date, and puts three instructions in one paragraph.

**Proposed text.**

```
Refusing to modify {path}: it is backup state (Timeshift snapshots or configuration on ned-box, or Time Machine state on the Mac). Backup state is never an agent's to write, because backups are how damage done by any agent is undone, and there is no override for this in this or any conversation.
If you are trying to recover a file, copy the file out of the snapshot or backup without writing to it; scripts/find-deleted-path-across-backups.py finds the copies.
If you cannot read the snapshot or backup, tell the user and stop.
If backup configuration needs changing, tell the user what needs changing and why, and stop: the change is the user's to make at his own keyboard.
```

**What changes.** `DENY_MESSAGE`. `.claude/guard-hooks/backup-and-snapshot-write-guard-test.py` looks for phrases of the refusal: "never an agent's to write", "copy the file out" and "his own keyboard" are kept; its test case "the refusal offers no approval lane" changes to look for "no override". Under `.claude/`: the exact text must be approved-by-walk.

### 5. AppleScript typing into a window

**When an agent sees this.** An agent wants to show the user a log and runs `osascript -e 'tell application "iTerm" to tell current session of current window to write text "tail -f run.log"'`. The guard refuses, because typed keystrokes mix with whatever the user is typing in that window.

**What the agent is told today** (`.claude/guard-hooks/synthetic-keystroke-guard-hook.py:129`):

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

**What changes.** `SYNTHETIC_TYPING_REASON`. `.claude/guard-hooks/synthetic-keystroke-guard-hook-test.py` looks only for the name `scripts/open-iterm-window-running-command`, which is kept.

### 6. Typing into a tmux session someone is attached to

**When an agent sees this.** An agent runs `tmux send-keys -t merge-lane-2 "status" Enter` to nudge another agent-seat while the user has that agent-seat's terminal open.

**What the agent is told today** (`.claude/guard-hooks/synthetic-keystroke-guard-hook.py:138`):

```
Blocked: tmux session '{target}' has an attached client, so send-keys/paste-buffer would splice into whoever is typing there (nedschorus#27; evidence on #37). Injection is permitted only into detached sessions. To show the user something, open them a window with scripts/open-iterm-window-running-command; for agent-to-agent messaging the durable path is the nedschorus#37 inbox design.
```

**What the agent cannot tell from the text.** How to reach the other agent, which is what the agent in the example wanted. The last clause points at "the nedschorus#37 inbox design"; GHI [Claude turn/start and turn/steer equivalents: inject a message into an idle session, steer an active turn](https://github.com/nedschorus/nedschorus/issues/37) is closed as completed, and a design is not a command. Today the agent-seats message each other with Claude Code's SendMessage tool, which delivers a message into another agent's session without typing into its terminal, across the two machines: the MD-skills seat on the Mac reaches merge-lane-2 on ned-box that way. No standing instruction in the repository names the tool yet; settled question 1. The window opener also runs on the Mac only.

**Proposed text**, with the messaging lines as settled question 1 recommends:

```
Blocked: tmux session '{target}' has an attached client, so send-keys or paste-buffer would interleave with the typing of whoever is attached. Sending keystrokes is permitted only into detached sessions.
If the keystrokes carry a message for another agent-seat, send the message with the SendMessage tool instead; the ListAgents tool lists the seats' addresses.
If SendMessage cannot reach the seat, tell the user.
{show_line}
Otherwise, do not send the keystrokes: tell the user what you were trying to do.
```

`{show_line}` is chosen by the guard from the platform it runs on, so the agent need not know which machine it is on. On the Mac: "If the purpose is to show the user something, open a window with scripts/open-iterm-window-running-command <command...>". Elsewhere: "If the purpose is to show the user something, tell the user the command to run; the window opener runs only on the Mac." Once PR [ned-box opens a window on the Mac through one forced command](https://github.com/nedschorus/nedschorus/pull/982) is merged and installed, the ned-box line can name `scripts/open-mac-window-from-ned-box.py` instead, in a change of its own.

**What changes.** `ATTACHED_REASON`, and one test case per platform for `{show_line}`; the test case at line 258 of `.claude/guard-hooks/synthetic-keystroke-guard-hook-test.py` looks for `#37` in the text and changes with it.

### 7. A tmux session the guard could not check

**When an agent sees this.** The same `tmux send-keys`, aimed at a session on ned-box, when the guard's own probe over ssh times out.

**What the agent is told today** (`.claude/guard-hooks/synthetic-keystroke-guard-hook.py:147`):

```
Blocked: could not verify that tmux target '{target}' has no attached client ({error}). Verify yourself with: {probe} — 0 means detached — then re-run this command with CLAUDE_VERIFIED_DETACHED=1 prefixed. Never inject keystrokes at a session someone may be typing in (nedschorus#27).
```

**What the agent cannot tell from the text.** What to do when the probe does not print 0, or fails. Nor how to read the probe's answer: the guard's own parser of the probe's answer knows four forms of answer the agent does not, among them an empty reply that looks like 0 but, in the code's own words, is "NOT a count of 0 attached clients". And `{probe}` is not always one command: when the guarded command names no tmux socket and the target has a per-seat tmux server, `probe_recipe()` fills `{probe}` with a first probe, a parenthesis, and a second probe for the seat's own server. The text then speaks of one output where there can be two. The override, `CLAUDE_VERIFIED_DETACHED=1`, is the agent's word that its own probe found the session detached, given through an environment variable, which the guard takes without checking; none of the glossary's three kinds names it.

**Proposed text.**

```
Blocked: could not verify that tmux target '{target}' has no attached client ({error}). Keystrokes sent into a session someone is typing in interleave with that typing.
Check the target with: {check_command}
If it prints detached, run this command again at once with CLAUDE_VERIFIED_DETACHED=1 prefixed.
If it prints anything else, do not send the keystrokes.
If the keystrokes carry a message for another agent-seat, send the message with the SendMessage tool instead.
{show_line}
Otherwise, tell the user what you were trying to do.
```

`{show_line}` is filled as in message 6.

**What changes.** `UNVERIFIED_REASON`. The guard gains a command-line mode, `.claude/guard-hooks/synthetic-keystroke-guard-hook.py --is-target-detached <target>` with the ssh host, carried options and server flags the hook used, which runs the guard's own `query_session_attached` with a longer time limit than the hook can afford and prints one word, `detached` or `attached`, or `could not verify` with the error, exiting 0, 1 or 2; the hook fills `{check_command}` with that command, so the agent never reads raw tmux output. `.claude/guard-hooks/synthetic-keystroke-guard-hook-test.py` looks for "could not verify" and "CLAUDE_VERIFIED_DETACHED=1" in this text, both kept; the test case that looks for "session_attached" changes to look for the check mode, and the mode needs test cases for each of its answers.

### 8. A tmux target that still holds a variable

**When an agent sees this.** An agent runs `tmux send-keys -t "$SEAT" "status" Enter`. The guard reads the command before the shell fills in `$SEAT`, so the guard sees the variable and not a session's name.

**What the agent is told today** (`.claude/guard-hooks/synthetic-keystroke-guard-hook.py:155`):

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

**What changes.** `UNRESOLVED_TARGET_REASON`; the literal `{}` is written `{{}}` in the format string. Test case F8a in `.claude/guard-hooks/synthetic-keystroke-guard-hook-test.py` looks for "unexpanded variable", which is kept, and for "CLAUDE_VERIFIED_DETACHED=1", which this text drops; F8a changes with it.

### 9. A tmux command that names no target

**When an agent sees this.** An agent runs `tmux send-keys "status" Enter` with no `-t`.

**What the agent is told today** (`.claude/guard-hooks/synthetic-keystroke-guard-hook.py:164`):

```
Blocked: this send-keys/paste-buffer names no -t target, so the keystrokes would land in tmux's current session — possibly the very one the user is attached to — and cannot be verified detached. Name the session with -t, or use scripts/open-iterm-window-running-command / the nedschorus#37 inbox instead (rule: nedschorus#27).
```

**What the agent cannot tell from the text.** Which instruction fits which purpose, and what "the nedschorus#37 inbox" is.

**Proposed text**, with the messaging lines as settled question 1 recommends:

```
Blocked: this send-keys or paste-buffer names no -t target, so the keystrokes would go to tmux's current session, which may be the session the user is typing in.
If the keystrokes are meant for a detached session, name that session with -t and run the command again.
If the keystrokes carry a message for another agent-seat, send the message with the SendMessage tool instead; the ListAgents tool lists the seats' addresses.
{show_line}
Otherwise, do not send the keystrokes: tell the user what you were trying to do.
```

`{show_line}` is filled as in message 6.

**What changes.** `NO_TARGET_REASON`. Two test cases in `.claude/guard-hooks/synthetic-keystroke-guard-hook-test.py`, at lines 290 and 347, look for "no -t target", which is kept.

### 10. The handoff instruction

**When an agent sees this.** An agent-session has used the share of its context window set as the reincarnation threshold, half by default at the commit this document read, and a third by default today. At the end of a turn the hook keeps the turn open and prints one line. The /handoff skill then writes the session-handoff, and the handoff-supervisor starts a fresh agent-session.

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

**What the agent is told today** (`scripts/checkout-freshness-catch-up.py:126`, after a first line such as "checkout-freshness: my-branch is 12 behind origin/main (1 own commit(s); head unpushed). Not updated: 1 uncommitted tracked change(s)."):

```
This branch has never been pushed, so nobody else has it. Bring it up to date now: commit or set aside any uncommitted work, run `git rebase origin/main`, then rerun the test suites for what you touched. If the rebase stops on a conflict, `git rebase --abort` puts everything back; then resolve it by hand or stay behind, which costs nothing at merge.
Do not report this to the user: he does not need to hear that main moved, or what other agents merged, unless it changes the work you are doing with him.
```

**What the agent cannot tell from the text.** When to resolve and when to stay behind; settled question 2. And "nobody else has it" was false, until the fix of settled question 4 merged, for a branch cut at a pull request's frozen-head, which this hook could not then tell from a new branch; that fix makes the sentence true.

**Proposed text.**

```
This branch has never been pushed, so nobody else has it. Bring the branch up to date now: commit or set aside any uncommitted work, run `git rebase origin/main`, then run `python3 scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main`.
If the rebase stops on a conflict that you can resolve now, resolve the conflict and run `git rebase --continue`.
If the rebase stops on a conflict that you cannot resolve now, run `git rebase --abort`, which puts everything back, and finish what you are doing first; this note comes back at each turn's end until the branch is up to date.
A push that conflicts with origin/main is refused by the pre-push check, which names the conflicting commit; if you cannot resolve that conflict, stop and tell the user which files conflict.
```

The last line replaces a line the first approval-walk approved, which had the agent fetch, rebase and test by hand before the first push. Those steps are already done for the agent: this hook rebases an unpushed branch at each turn's end once the tree is clean; the pre-push hook installed on both machines runs `scripts/branch-conflict-check.py`, which fetches origin and refuses a conflicting push; and merge-lane-2, an agent-seat, runs the selected nc-test-suites on the frozen-head merged onto main before merging. The test command is the one `CLAUDE.md` named for a push when part one was built, because the test runner selects the nc-test-suites the change can affect.

**What changes.** `REBASE_ADVICE`. `AFTER_REBASE_ADVICE` in the same hook, "Rerun the test suites for what you touched: your work now sits on newer code.", and `NEVER_PUSHED_ADVICE` in `scripts/obsolete-file-edit-warning-hook.py`, which ends "then rerun the tests for what you touched.", name the same command in place of that phrase. One test case in `scripts/checkout-freshness-catch-up-test.py` looks for "`git rebase --abort` puts everything back", which the proposed text rewords; that test case changes. The first sentence is true once the fix of settled question 4 has merged: a branch whose commits are already on GitHub is then no longer called never pushed. Resolving the conflict with the Edit tool meets message 3's refusal while the rebase is stopped; settled question 7.

### 12. An edit to a file main has changed, on a detached HEAD or with no branch state reported

**When an agent sees this.** An agent edits `scripts/recover-crashed-seats.py`, and main has changed that file since this checkout's merge base with origin/main. When the checkout is on a branch, the warning ends with an instruction. When git did not answer, or the checkout is on a detached HEAD, the instruction is dropped. A detached HEAD is rare here: `session-location-write-guard.py` refuses a write from a detached HEAD (message 3), so this warning reaches a detached checkout normally only after the user has approved that write, or while a rebase stopped on a conflict, during which that guard lets the write through (settled question 7).

**What the agent is told today** (`scripts/obsolete-file-edit-warning-hook.py:274`):

```
obsolete-file-edit-warning: you just changed scripts/recover-crashed-seats.py, which 3 commit(s) on origin/main have changed since this branch's merge base and this checkout does not have.
```

**What the agent cannot tell from the text.** Why the finding matters and what to do about it. On a detached HEAD, "this branch" also names a branch that is not there.

**Proposed text.** The first line, for every HEAD state of the checkout (when git could not count the commits, the line says "which origin/main has changed since …" as today):

```
obsolete-file-edit-warning: you just changed {path}, which {count} commit(s) on origin/main have changed since this checkout's merge base with origin/main and this checkout does not have, so your edit is built on an old copy of the file.
```

The hook works out for itself the facts the agent would otherwise have to find. On a branch, the instruction the warning gives today stays as it is, apart from the test command message 11 names. Then, on a detached HEAD while a rebase, merge, cherry-pick or revert is in progress, one line and nothing else:

```
A git operation is in progress ({marker}): finish it before anything else.
```

On a detached HEAD otherwise:

```
This checkout is on a detached HEAD: make a branch (git switch -c <a-branch-name>) before you commit, because a commit on a detached HEAD is on no branch.
{overlap_line}
```

`{overlap_line}` is the hook's verdict on whether main's changes to the file overlap the agent's edit, one of:

```
main's changes to {path} do not overlap this checkout's copy; a rebase merges them cleanly.
```

```
main's changes to {path} overlap this checkout's copy: after you make the branch and commit your edit, run git rebase origin/main, which will stop on this file, and resolve the conflict there.
```

```
main no longer has a file at {path}: find out whether main moved or deleted it (git log origin/main -- {path}) before you commit.
```

When the verdict cannot be worked out for another reason, the line is left out, as the count is left out today. A no-overlap verdict is textual: the first line still says main changed the file, because changes that do not overlap can still disagree.

Or, when git did not report the branch state, after the first line:

```
git could not report this checkout's branch state ({text}): stop and tell the user before you commit.
```

A two-way `git diff origin/main -- {path}` could not answer the overlap question, because the agent's own edit is part of that diff; a three-way merge of the file answers it directly.

**What changes.** `head_advice` returns lines for the two states it now returns nothing for, and keeps the failure text `head_state` returns, which it discards today, for the line about a HEAD state git could not report. The in-progress check reads `GIT_IN_PROGRESS_MARKERS`, already defined in `scripts/checkout-freshness-catch-up.py`, which this hook imports, against the git directory the hook already resolves; the location guard's change of settled question 7 reads the same list. The overlap verdict takes `git merge-base HEAD origin/main`, writes the merge-base and origin/main copies of the file to temporary files, and runs `git merge-file -p` with the working copy as the current side: exit 0 is no overlap, a positive exit is an overlap, and a failed read of origin/main's copy is a file main no longer has. `obsolete_file_warning_line` gains "this checkout's merge base with origin/main" and the "so your edit…" clause for every variant, including the one with no count. `NEVER_PUSHED_ADVICE` keeps "This branch has never been pushed, so nobody else has it", which the fix of settled question 4 makes true. `scripts/obsolete-file-edit-warning-hook-test.py` needs a test case for each state: in progress, overlap, no overlap, a file main no longer has, and unknown.

### 13. A second file under a tracked file's name

**When an agent sees this.** In this repository a basename, the last part of a file's path, belongs to one tracked file, so that the file can be cited by its name; `SKILL.md`, `README.md` and `.gitkeep` are the exceptions, fixed by the tools that read them. On 2026-10-01 the handoff-supervisor on the branch of PR [The instruction-file guard protects the files the user reviews, by where they sit](https://github.com/nedschorus/nedschorus/pull/852) told the subagent that refreshes a system's nc-architecture-overview to write `docs/nedschorus-wiki/queue/nedschorus-handoff-system-overview.md`, a draft of the tracked page of the same name. These pages have since been renamed `nedschorus-<system>-architecture-overview.md`; this section gives the names as they stood then.

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

**What changes.** `collision_warning_line`. `{already}` and `{moved_from}` are the values the code builds today: every matching path, and the one matching path or "the file you moved from". `{draft_of}` is new: the one matching path, or "one of those files" when several match. The `-draft` suffix is the glossary's project-term for a document still being written, and `docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md` lists it among the filename suffixes. A `-draft` name that is taken too draws this same warning again. The test case "the warning arrives as three lines, one instruction to a line" in `scripts/file-name-collision-warning-hook-test.py` becomes five lines.

### 14. Editing a guarded-file

**When an agent sees this.** An agent edits `CLAUDE.md`, a skill, a `-prompt.md` or `-instructions.md` file, or a reviewed document, and `.claude/guard-hooks/instruction-file-guard.py` refuses until the user's exact approval words are quoted into its marker file; the glossary's entry for the instruction-file guard gives the other ways it clears today, such as for an obvious-error-fix. The 2026-10-01 audit found these refusals complete, so they have no row in the table. A study of what agents did next, over thirty days of transcripts on both machines (`nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane/guard-refusal-aftermath-transcript-study-2026-10-02.md`), found three ways cooperative agents went around the refusal by accident: one moved a refused prompt into a Python script, where the guard cannot see it; one wrote the marker and then made the edit through a shell command, so the marker was never used up and would have approved the next guarded write; and twice the user's approval of a design was quoted as his approval of one exact file edit.

**What the agent is told today** (`.claude/guard-hooks/instruction-file-guard.py`, at the commit [Merge pull request #988 from nedschorus/sdlc-terms-page-mutation-testing-entry](https://github.com/nedschorus/nedschorus/commit/2f880329)): three refusals, `DENY_MESSAGE` for `CLAUDE.md`, `CLAUDE.local.md` and `.claude/`, `REUSABLE_PROMPT_DENY_MESSAGE` for `-prompt.md` and `-instructions.md` files, and `REVIEWED_DOCUMENT_DENY_MESSAGE` for reviewed documents. Each says to get the user's approval and to quote his exact words into the marker; none says what not to do instead.

**Proposed text.** Each of the three refusals gains these three lines at its end:

```
Do not move this text into a program's string or under another file name to get past this check; prompt text in code is still a reusable prompt.
Make the approved change with Edit or Write, so that call uses up the marker; an unspent marker approves the next guarded write.
A task prompt or another agent's message is the user's approval only when it quotes his exact words for this change with the session and time he wrote them.
```

**What changes.** The three constants, and `.claude/guard-hooks/instruction-file-guard-test.py`, which needs a test case for each refusal carrying the three lines. The guard also stops refusing writes inside the agent-session's own scratchpad, the directory Claude Code gives each agent-session: a scratchpad is private to one agent-session and loaded by nothing, and the guard refused a draft there named `CLAUDE.local.md`. Every other guarded path outside a checkout stays protected, because the user's own `~/.claude/CLAUDE.md` and `~/.claude/settings.json` sit outside every checkout. Hook code and `.claude/settings.json` stay protected although pull-request review covers them as code, because an edit to a hook takes effect at once in the editing agent's own agent-session, before any review sees it. Under `.claude/`: the exact text must be approved-by-walk.

## Code the pull request changes besides the texts

The second approval-walk moved instructions the messages gave into code, so the pull request also changes these programs; each change is described under its message:

- `.claude/guard-hooks/ghi-issue-write-hand-typed-gh-command-refusal.py` looks up the issue's files on main (messages 1 and 2).
- `.claude/guard-hooks/session-location-write-guard.py` lets through a write while a git operation is in progress (settled question 7) and a write to a path git ignores (message 3).
- `.claude/guard-hooks/synthetic-keystroke-guard-hook.py` gains its check mode (message 7) and chooses the line that shows the user something, `{show_line}`, by platform (messages 6, 7 and 9).
- `scripts/obsolete-file-edit-warning-hook.py` reports a git operation in progress, the overlap verdict and git's failure text (message 12).
- `.claude/guard-hooks/instruction-file-guard.py` exempts the agent-session's scratchpad (section 14).
- `nc-systems/handoff/daily-overview-refresh-reminder-mark.py`, the program's name at the time, since renamed `nc-systems/handoff/handoff-architecture-overview-refresh-user-shown-mark.py`, gains `--shown-on-pacific-date`, described below.

And it adds one nc-test-suite, `scripts/registered-hook-messages-carry-no-citations-test.py`, discovered by the test runner like every `*-test.py`, which reads the hooks registered in `.claude/settings.json`, imports each, collects its module-level string constants whose names end in `_REASON`, `_MESSAGE`, `_REFUSAL`, `_ADVICE`, `_NOTICE`, `_INSTRUCTION`, `_TEMPLATE` or `_LINE`, and fails on a date, the word "ruled", an issue or pull request number in the spellings `nedschorus#27`, `#37`, `PR 931` and `GHI 913`, or a GitHub pull or issue link. It also fails when a registered hook declares no such constant, so a hook whose every message is built inline cannot escape the check, and it holds an explicit list of exemptions, empty at first, for a message that needs one of those forms as data. The suite reads only registered hooks' message constants: tried on main, it flagged the six messages of this table that carry a citation and nothing else among 50 constants, while across all 152 programs and tests about 16 of its 26 hits were dates or issue numbers that are data, not citations.

## The mark program's messages and the handoff-supervisor's console

PR [The instruction-file guard protects the files the user reviews, by where they sit](https://github.com/nedschorus/nedschorus/pull/852), now merged, added a program an agent runs, `nc-systems/handoff/daily-overview-refresh-reminder-mark.py`, the program's name at the time, since renamed `nc-systems/handoff/handoff-architecture-overview-refresh-user-shown-mark.py`, and added or reworded five lines on the handoff-supervisor's console. This section records part one, which PR [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/pull/1007) shipped before the rename, so the program's name, its test's name and its texts below are given as they stood then; none of them is a command to run today.

The program writes a daily reminder mark: the dated file in the log-store, one per system per day, recording that an agent-seat has shown the user that day's refreshed draft of the system's nc-architecture-overview, so that other agent-seats do not show it again. An agent-seat runs the program after the agent-seat has shown the user the difference between the nc-architecture-overview and the refreshed draft. The mark is written only after that, so that if a reincarnate-seat happens in between, the agent-seat's next agent-session gets the same reminder.

**Read by the agent that runs `nc-systems/handoff/handoff-architecture-overview-refresh-user-shown-mark.py`**, as the program printed them when it was named `daily-overview-refresh-reminder-mark.py`:

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
When the user says the cause is fixed, run: nc-systems/handoff/daily-overview-refresh-reminder-mark.py {system} --shown-on-pacific-date {date}
```

The program gains `--shown-on-pacific-date YYYY-MM-DD`, defaulting to today's Pacific date, and the failure message fills `{date}` with the day the user was shown the refresh, so a retry made the same Pacific day marks that day, and a retry made after that day writes nothing. A run whose date has passed writes nothing and exits 0 with:

```
daily-overview-refresh-reminder-mark: no mark was written, because {date} has passed; the next agent-seat to show the refresh writes the new day's mark.
```

A date after today is a mistake in the command, refused with:

```
daily-overview-refresh-reminder-mark: no mark was written, because {date} is after today's Pacific date.
Run this again without --shown-on-pacific-date, or with the date the user was shown the refresh.
```

`nc-systems/handoff/tests/daily-overview-refresh-reminder-mark-test.py` needs a test case for each date case.

**Read by whoever watches the handoff-supervisor's console**, not by the agent-seat's agent (`nc-systems/handoff/handoff-supervisor.py`). They are here as the background to settled question 5:

```
handoff-supervisor: overview check could not ask GitHub which open pull requests change an overview, so no line is withheld for a pull request: {error}
handoff-supervisor: overview check for {system} withheld its line: the open pull request "{title}" ({url}) already changes {overview path}
handoff-supervisor: overview check could not read the day's reminder marks in {marks directory}, so no line is withheld for a reminder already given: {error}
handoff-supervisor: overview check for {system} gives its line: the day's reminder mark {mark} does not hold the time it was written, but {text}
handoff-supervisor: overview check for {system} withheld its line: the user was shown this overview's refresh today, at {time}, as {mark} records
```

Each console report says what happened and why, and each is a report, not an instruction, so no rewording is proposed.

## Related issues

`scripts/ghi-guide-agent-ask.py "Is there an open issue about the wording of the messages that hooks, guards and checks hand an agent when they refuse or warn: that each message must say what was refused, why, and what to do instead?"` answered that no open issue states this rule. It named two near neighbours: GHI [main-gatekeeper — the single check-in gate (design: nc-systems/main-gatekeeper/main-gatekeeper-design.md)](https://github.com/nedschorus/nedschorus/issues/3), which rules on the structure of a reply and not its wording, and GHI [A project style guide: words to avoid, a mechanical checker, and a check on unbacked promises](https://github.com/nedschorus/nedschorus/issues/14), the closest home for a phrasing rule.

The defect behind settled question 4 is filed as its own GHI: GHI [The checkout-freshness hook treats a new branch cut at a pull request's pushed head as never pushed, and rebases it](https://github.com/nedschorus/nedschorus/issues/913), fixed by PR [The checkout-freshness hook treats a branch whose commits are already on GitHub as pushed, and leaves it alone](https://github.com/nedschorus/nedschorus/pull/931).

Follow-ups the second approval-walk accepted, each its own change after this pull request:

- a close command in `scripts/ghi-issue-write.py` that opens the outcome edit's pull request and, run again after that pull request merges, finishes the rerun and closes the issue; the issue guard then points a hand-typed `gh issue close` at it, and messages 1 and 2 shrink to one line; built since as close-GHI, which the issue guard's close lines name;
- the issue guard refuses a command that only quotes the words `gh issue comment` inside data, which is a defect; the fix belongs to agent-seat cold-read-research's planned replacement of the Bash guards' hand-written shell parser, which carries that command as a required test case;
- a check that catches a guarded-file changed without the user's approval by any means, a shell command included: carried by GHI [Catch a guarded file changed without the user's approval, ask him, and keep every version](https://github.com/nedschorus/nedschorus/issues/1268), which asks the user instead of reverting;
- the handoff-supervisor's report that it could not read the reminder marks reaches the initial-agent-instructions of the agent-seat's next agent-session (settled question 5).

## Questions the approval-walks settled

The first approval-walk put each of these to the user. Where a question gives a recommendation, the user's answer is as the recommendation says, except as noted; questions 4 to 6 say how each was settled.

1. Messages 6 and 9 send an agent that wants to reach another agent-seat to "the nedschorus#37 inbox", and that GHI is closed: should the two messages name the SendMessage tool, which the agent-seats use today? Recommendation: yes, as proposed; the alternative is to leave the line out, so the agent must find SendMessage unprompted.
2. Message 11 says staying behind main "costs nothing at merge", yet a conflict left unresolved now is a conflict at merge: should that instruction stay? Recommendation: no; the proposed text has the agent fetch and rebase again before the first push. The second approval-walk later replaced that line with the pre-push check, as message 11 says.
3. Message 2 gains a line for a duplicate issue, and message 13 gains a line for a draft of an existing file: are both wanted? Recommendation: yes to both.
4. A branch made at a pull request's frozen-head, as message 3 instructs, has no copy on GitHub under its own name, so `checkout-freshness-catch-up.py` and `obsolete-file-edit-warning-hook.py` treated the branch as never pushed. The obsolete-file warning then instructed a rebase, and at the end of an agent-session's turn, though not a subagent's, the freshness hook rebased the branch itself when the tree was clean, moving a frozen-head. Wording cannot fix this; the GHI named under Related issues tracked the fix, which the user asked to have built at once, and which has merged (direction 1 of that GHI: a branch whose commits are already on a branch on GitHub counts as pushed). Messages 3, 11 and 12 assume it.
5. When the handoff-supervisor cannot read the daily reminder marks because ned-box cannot be reached, the report goes to the console only, so the agent cannot tell the user, as `CLAUDE.md` asks. Answered: a change of its own to the handoff-system, listed under Related issues.
6. Do the two reworded messages of the mark program, `nc-systems/handoff/handoff-architecture-overview-refresh-user-shown-mark.py` today, go into the pull request that added the program, or follow it? Settled when that pull request merged: they go into the pull request that changes the hook messages, drafted against the program as merged.
7. While a rebase is stopped on a conflict, the checkout's HEAD is detached, so `session-location-write-guard.py` refuses the Edit or Write that would resolve the conflict, and message 3 then tells the agent to make a branch in the middle of the rebase. A merge, cherry-pick or revert stopped on a conflict leaves HEAD on its branch, so the guard does not refuse there. Recommendation: the guard recognises a rebase or merge in progress (`rebase-merge`, `rebase-apply`, `MERGE_HEAD`, `CHERRY_PICK_HEAD` or `REVERT_HEAD` in the worktree's git directory, the list `GIT_IN_PROGRESS_MARKERS` in `scripts/checkout-freshness-catch-up.py` already holds) and lets the write through, in the pull request that changes this guard's message; messages 11 and 12 assume it.

## Outcome of part one

Part one shipped as PR [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/pull/1007), merged to main on 2026-10-04 as commit [f9496284](https://github.com/nedschorus/nedschorus/commit/f9496284). PR 1007 built this document's proposed texts, which merge-lane-2's review checked against this document word for word, and the code changes this document lists, except the three sibling refusals of message 1, `COMMENT_REFUSAL`, `EDIT_BODY_REFUSAL` and `EDIT_TITLE_REFUSAL`, for which this document gives no text; PR [The issue guard's comment, body and title refusals name the issue's file and the rerun](https://github.com/nedschorus/nedschorus/pull/1031) gave them their words. Its review took three rounds, whose fixes changed code, tests and four program texts; those four texts had a cold-read-fast-read, recorded in the directory `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/pr-1007-fix-commit-program-texts-2026-10-03/`. Where the build differs from this document, main's code is what was built, among the differences:

- the keystroke guard has a refusal of its own, `NESTED_SSH_REASON`, for a target reached through more than one ssh hop, which the guard cannot check through;
- the obsolete-file warning reports a copy on origin/main that git cannot read, `MAIN_COPY_UNREADABLE_LINE`, rather than calling the file one main no longer has, and counts only a `git merge-file` exit up to 127 as an overlap;
- `REBASE_ADVICE` ends by saying that a conflict the agent cannot resolve may be told to the user, despite the line after it that says not to report the note;
- the location guard and the obsolete-file warning do not count `BISECT_LOG` as a git operation in progress;
- the instruction-file guard's scratchpad exemption leaves out a checkout made inside the scratchpad;
- the citation nc-test-suite also reads constants with plural names and tuples of strings.

Messages on main have changed further since; main's code, not this document, gives their current text.

## Later parts

The 2026-10-01 audit found gaps in four more groups, and left out of its scope three programs that can refuse an agent. Each of these five parts is drafted the same way as part one, as a document of its own:

- part two, the git hooks that run at commit and push (`scripts/git-client-side-hooks/` and `scripts/git-client-side-hooks-pre-push-conflict-check.py`), 8 of 11 messages with a gap: drafted as `docs/issues/956-part-two-the-git-hooks-messages.md`, which says where it stands;
- part three, `scripts/merge-gate.sh`, 20 of 27: drafted as `docs/issues/956-part-three-the-merge-gate-messages.md`, which says where it stands;
- the nc-test-suites that enforce a repository-wide rule, 20 of 38, each named in the 2026-10-01 audit's report;
- three programs run by hand, `scripts/dangling-path-citation-check.py`, `scripts/stale-code-citation-check.py` and `scripts/md-drift-lint.py`, 19 of 21;
- the three the 2026-10-01 audit did not read: the create-GHI and edit-GHI refusals of `scripts/ghi-issue-write.py`, `nc-systems/main-gatekeeper/main-gatekeeper.py`, and the lock and directory refusals of `scripts/run-all-test-suites.py`.

The next action on this GHI is drafting the last three parts; the documents of parts two and three give their own next actions.

## Decided after part one

- GHI 956 no longer plans to rewrite every message the 2026-10-11 audit found failing. That audit, a different one from the 2026-10-01 audit this document is built on, gave each program message to two agents that saw the message and nothing else, neither `CLAUDE.md` nor a skill, and recorded each message on which those agents went wrong; its brief, its report `synthesis.md` and its records are in `nedlern@ned-box:/home/nedlern/nedschorus-logs/analysis/hook-messages-instructions-that-fail-when-followed-audit-2026-10-11/`. An agent-session in this project loads `CLAUDE.md`, and a study of real transcripts in the same directory, `follow-test-against-real-transcripts.md`, sampled 20 of the failing messages and found 39 real deliveries of them, with 0 failures. The user decided this on 2026-11-13, at 22:40Z by the walk-minutes, approving item 13, "GHI 956 drops its plan to rewrite every message the 2026-10-11 audit failed", of the approval-walk `approval-binding-design-ghi-1268-approval-walk-2026-11-09`: "And approve if item 13 is don't rewrite every message the audit failed. Yeah, we're not going to do that. So I think that's a approve." The walk-minutes are `nedlern@ned-box:/home/nedlern/agents/fleet-restart-at-login/docs/walk/approval-binding-design-ghi-1268-approval-walk-2026-11-09-minutes.md`, and the item's text is the section "Item 13 of 46" of the walk-document `nedlern@ned-box:/home/nedlern/agents/fleet-restart-at-login/docs/walk/approval-binding-design-ghi-1268-approval-walk-2026-11-09.md`. The approved change deleted one sentence of agent-seat reboot-test's provisional addition below, "Then the 105 messages an audit found failing are rewritten, the ones agents meet most often first, each with its fast read.", and put nothing in its place; it says nothing about the later parts above, which come from the 2026-10-01 audit.

## Provisional additions (not yet vetted by the user)

- MD-skills, 2026-10-14: Add the message `nc-systems/handoff/handoff-user-review-of-agent-memory-stores-mark.py` prints when its mark may not have been written to this document's mark program's messages, beside the daily reminder mark messages (MD-skills task #144).
- MD-skills, 2026-10-14: Issue guard wording, one small pull request: the shared line for an issue with no file on main prints a literal `<number>` though the guard knows the number; the rerun and record lines do not say that edit-GHI opens a pull request; the body refusal's "--title alone afterwards" does not say after what (MD-skills task #157, from the review notes on PR [The issue guard's comment, body and title refusals name the issue's file and the rerun](https://github.com/nedschorus/nedschorus/pull/1031)).
- Agent-seat agent-instructions-editor, 2026-10-14: add the list of the kinds of obvious-error, which `CLAUDE.md` lets an agent fix in a guarded-file without asking the user, to the refusals of `.claude/guard-hooks/instruction-file-guard.py` (section 14), so that an agent meets the list at the moment the guard stops it.
- reboot-test, 2026-10-14: a reminder hook that names the wiki page on how to write a tool-message-to-agent, and the command for that message's cold-read-fast-read, whenever an agent edits a message in a Python program, is built on branch `python-edit-changed-agent-facing-message-check-reminder-hook-topic-branch`, pushed with no pull request yet; it waits for that page to merge in PR [Wiki: How to write an agent-facing-message](https://github.com/nedschorus/nedschorus/pull/1363). PR 1363 has since merged, on 2026-10-14, and on 2026-11-13 `git ls-remote --heads origin` found no branch of that name.
- fleet-restart-at-login, 2026-11-12: Audit: hand each program message's instruction to fresh agents, follow it in the situation it is shown in, and record where following it fails (task #194).
- fleet-restart-at-login, 2026-11-12: Rewrite the audit's top-ranked messages once reboot-test's parser pull requests merge: OBS-3, OBS-8 and OBS-9 first, then GK-34, GK-39 and GK-31 (task #199).

## Deferred-decisions

- The possible defects in part one's messages as main carries them that the cold-read-full-run of 2026-11-13 found, each listed with its message under "Deferred" in `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/956-every-refusal-and-warning-a-program-hands-an-2026-11-13-3/cold-read-triage.md`, to be settled when that message is next changed.
