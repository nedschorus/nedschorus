<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/issues/queue/45-session-seat-and-isolation-riders.md -->

# Title

1. The document's title is "Session seat and isolation riders."

## Opening paragraph (unlabeled, lines 3)

1. This item is on a waiting list ("queued") for a GitHub issue numbered 45 in the "nedschorus" repository, an issue whose subject is described elsewhere as being about "named agents, launch and reattach."
2. This material came up during a conversation that took place on August 13, 2026, at a point where the participants were trying to work out why it was difficult to distinguish several sessions running on the machine from one another, and where it was discovered that one session had created a fork (a copied/derived session) that ended up operating inside the file checkout (working directory) belonging to a different session.
3. Every item listed below was talked about during that conversation and consciously left unfinished — implying a deliberate choice not to act on any of them yet — and none of them is currently being worked on ("in flight" meaning actively in progress).

## 1. A guard that enforces one live session per directory

1. This is a header naming the first proposed item: some kind of protective mechanism ("guard") whose job is to make sure that no more than one active/running ("live") session is ever operating out of the same directory at once.

**The invariant:** (subsection label, meaning "the rule/property that must always hold true")

1. The rule that must always be true is that two sessions which are both currently running must never be using the same working directory at the same time.
2. Forks (sessions spawned as derivatives of a parent session) are identified as the most common way this rule gets broken, because when a session is forked, the new (child) session inherits both the parent's working directory and its conversation history — and separately, when a background job is launched from within a session, that new background job also inherits the same current working directory as the session that launched it; this inheritance behavior is what caused several background jobs to appear to be duplicates of each other inside a location called `~/agents/choirmaster`.

**The proposal:** (subsection label, meaning "what is being suggested as a solution")

1. The suggestion is a "PreToolUse hook" (a piece of code that runs automatically before a tool is used) that intercepts the `Edit` and `Write` tools specifically, and that refuses to let the action proceed if it detects that some other currently-running Claude session is already using the same working directory as the session attempting the edit/write.
2. When it refuses, the hook should also teach/instruct the user or session on how to fix the situation — specifically by telling them "another session is live here; call `EnterWorktree` first," meaning they should invoke a tool/function named `EnterWorktree` before proceeding.
3. Actions that merely read files or search (as opposed to editing or writing) are not blocked by this guard, because such actions never cause the kind of conflict the guard is meant to prevent.
4. The hardest unresolved part of this proposal is figuring out how to reliably detect when a directory is already in use by another live session, and the most obvious way of doing that detection turns out not to work.
5. The first idea for detection was to scan the `/proc` filesystem (a Linux mechanism exposing information about running processes) and compare the working directory (`cwd`) reported by each Claude-related process; this was actually tried on August 13, 2026, and was found to be unreliable.
6. The specific way it failed: when a background session is "attached" to (meaning a person connects an interactive view to a session that was already running in the background), the process's reported working directory is the directory that was current when the person typed the `claude attach` command — not the directory that the background session is actually doing its work in; the consequence of this is twofold — actual duplicate-directory situations go undetected ("hide"), and separate windows that are merely viewing/attached to a session get mistakenly counted as if they were independent sessions themselves ("viewer windows masquerade as sessions").
7. A detection method that would actually work needs to rely on the session's own internal record of what directory it considers itself to be working in — meaning either reading it from the session's transcript (log file), where this information is recorded, or by directly asking the running session itself, which is stated to answer this question correctly — rather than relying on information drawn from the operating system's process table.
8. Before anyone builds the hook described above, this detection-method problem needs to be solved first, because a guard that gives wrong detections would be worse than having no guard at all — the reasoning given is that it would teach the wrong lesson (mislead the user/session about what's actually happening) at exactly the moment (i.e., right when the user is trying to understand and fix a real problem) when getting it right matters most.

**Why this shape:** (subsection label, meaning "the reasoning behind choosing this particular design/approach")

1. A tool called `EnterWorktree` is already capable of correctly moving a currently-running session to a different, isolated working location (a "worktree," a Git concept for an additional working directory tied to the same repository), so the ability to fix the problem already exists — the missing piece is not capability but rather what triggers/prompts that fix to be used.
2. An alternative design was considered — showing a warning at "SessionStart" (i.e., when a new session begins) — but this alternative was judged to be a weaker solution than the PreToolUse hook design, because a SessionStart warning merely advises or suggests, whereas the PreToolUse form actively blocks/prevents the action from happening.
3. This exact design pattern (a PreToolUse hook that blocks) is not a new idea for this project — it is already implemented and running for a different purpose in a file located at `.claude/hooks/instruction-file-guard.py`.

**Cost/caveat:** (subsection label, meaning "downsides or things to be careful about")

1. Implementing this requires adding a new entry into a configuration file located at `.claude/settings.json`, and because this falls into a category the author calls "instruction-class" (implying rules/instructions rather than code), it needs to go through a review process the author calls "the user's walk" (some kind of approval or review procedure carried out by the user).
2. A PreToolUse hook, once installed, runs for every session running anywhere on the machine, which means that if there is a bug or flaw ("defect") in the hook's logic, that flaw would affect/be experienced by every session on the machine, not just one.

## 2. A `--directory` flag for the launchers

1. This is a header naming the second proposed item: adding a command-line flag named `--directory` to the scripts that launch new agent sessions.

1. Two specific scripts, `scripts/launch-claude-ubuntu` and `scripts/launch-claude-mac`, currently place every new agent into a subdirectory named after the agent under some root directory referred to as `<agents-root>` (i.e., `<agents-root>/<name>`), following a fixed convention, and these scripts do not currently accept any argument letting the caller specify a different directory — the consequence is that a launched session cannot be made to operate inside a worktree (an existing separate working directory) that already exists, i.e. it cannot "adopt" one.
2. Because of that limitation, the action of taking a background thread/session and turning it into a directly-visible, interactive session running in a terminal multiplexer window ("tmux seat") is harder to accomplish than it should be.
3. Implementing the proposed flag is estimated to require roughly ten lines of code change in each of the two launcher scripts.

1. This proposed item's importance/necessity is reduced, but not entirely removed, by a fact that was discovered on the same day (August 13, 2026): the command `claude attach <job-id>` already has the ability to open a background session so that it becomes visible/interactive within a terminal, meaning that creating a dedicated visible "seat" is not the only way to gain visibility into a background session — attaching is another existing way.

## 3. A CLAUDE.md rule: background jobs push their own branch

1. This is a header naming the third proposed item: a rule to be written into a file called CLAUDE.md, stating that each background job should push (upload, in the Git sense) its own separate branch rather than sharing one.

1. A situation arose where several sessions were all pushing changes to one shared branch used by agents, and this produced Git merge commits with the message "Merge remote-tracking branch 'origin/choirmaster' into choirmaster" showing up in that branch's history, and it also produced a "non-fast-forward rejection" (a Git error that occurs when your local branch is behind the remote branch you're pushing to), which in turn forced someone to perform a rebase (a Git operation to reapply commits) in the middle of doing an unrelated task, costing time/effort.
2. Adopting a rule of "one branch per session" would eliminate this entire category/class of problem, and this is justified by the fact that Git already has a built-in restriction preventing the same branch from being checked out in two different worktrees at once — so, given that existing Git restriction, the only additional thing the team needs to enforce through discipline/convention is making sure everyone is clear on which branch a given session is supposed to push to.

1. This rule falls into the "instruction-class" category (as mentioned in item 1), and therefore it also needs to go through the review process the author calls "the user's walk."

## 4. md-review the fleet paths reference

1. This is a header naming the fourth proposed item: running a process/skill called "md-review" (reviewing a Markdown document) on a specific reference document about the fleet's file paths.

1. A specific document, located at `docs/cross-project/fleet-machine-paths-and-checkouts.md`, was written on August 13, 2026, and is considered to be a document of lasting/ongoing value — which is exactly the kind of document the "md-review" skill is described (in its own stated purpose) as being meant for.
2. This document has not yet been put through that review process.

## 5. Migrating `choirmaster` to a machine-suffixed name

1. This is a header naming the fifth proposed item: renaming something called `choirmaster` (apparently an agent) so that its name includes a suffix identifying which machine it runs on.

1. This idea was thought about and then deliberately postponed/put off rather than acted on now.
2. The reasoning given: because the two machines involved do not share any agent state between them, having the identical name (`choirmaster`) exist independently on both machines does not actually create any conflict — it simply represents two separate, unrelated agents that happen to share a name; therefore, the only benefit that adding a machine-specific suffix to the name would provide is making it easier to tell the two apart ("legibility") in a listing/view that shows agents from both machines together — and that is the entire benefit, nothing more.
3. Performing the rename/migration for the currently-running ("live") agent seat would require three things: moving its Git worktree using the `git worktree move` command, renaming the files associated with its handoff process, and restarting it — and doing all of this to a session that is actively working is disruptive, especially in exchange for a benefit that is merely cosmetic (appearance-only, not functional).
4. This decision should be reconsidered only if viewing agents across multiple machines together in one combined listing becomes something that happens routinely/regularly, rather than as an occasional or one-off need.

## Session-management facts worth keeping (verified 2026-08-13, Claude Code 2.1.231)

1. This is a header introducing a list of factual findings about how to manage sessions, confirmed to be accurate as of August 13, 2026, using version 2.1.231 of "Claude Code" (the software).

1. This introductory sentence states that the items in the list that follows are not proposals for changes ("riders") but are instead facts that were difficult/costly to learn ("hard-won") and that could easily be forgotten if not written down ("easy to lose").

1. The first fact: identifiers called "job ids" are different from identifiers called "session ids" — specifically, the command `claude attach <id>` expects to be given the 8-character-long job id (which corresponds to directory names found under the path `~/.claude/jobs/`) rather than the session's UUID (a longer, standard unique identifier format); attempting to attach using a session id instead of a job id results in a failure with the error message "No job matching."
2. The second fact: a command `claude agents` opens up a view/interface called the "agent view," within which every session is shown grouped according to its current state; within that view, pressing the Space key lets you look at ("peek") a session without actually attaching to it (i.e., without connecting to it interactively); pressing Ctrl+R lets you rename a session; pressing Ctrl+T lets you "pin" a session, which protects it from being automatically cleaned up ("reaped") after roughly one hour of inactivity ("idle reap"); and pressing Ctrl+X lets you stop a session; additionally, pressing Ctrl+S changes the grouping so that sessions are grouped by their working directory instead, and this particular grouping is useful because it makes it visually apparent when multiple sessions are sharing the same directory (the hazard described in item 1).
3. The third fact: this `claude agents` command must be run on the specific machine whose sessions you're trying to see — running it while logged into/working on the Mac will show you only the Mac's background jobs, whereas to see the jobs running on the machine referred to as "the box," you need to run the command by first connecting to it remotely, specifically using `ssh nedlern@ned-box -t 'claude agents'`.
4. The fourth fact: there is no feature within this software ("the harness") that lets you view multiple sessions side-by-side at the same time; consequently, if you want to look at more than one session simultaneously, you need to dedicate one separate terminal (or one separate tmux window, a subdivision within a terminal multiplexer) to each individual session.
5. The fifth fact: the amount of time a process has been running ("process uptime," measured as `etime`, elapsed time) is not the same thing as, and should not be used as a stand-in for, how long that session has actually been idle/inactive — specifically, a session whose process shows 23 hours of elapsed running time could nevertheless have been actively doing work as recently as one minute ago; therefore the only trustworthy/honest way to check whether a session is actually stale (unused for a long time) is to look at the last-modified timestamp of its transcript file, which is located at a path following the pattern `~/.claude/projects/<project>/<session-id>.jsonl`.

