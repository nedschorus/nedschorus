# How to change an agent's trained default by pairing a refusing hook with a correction

Agents arrive trained to do some things one way, such as writing a new version of a file somewhere else and then copying it over the original. When the project needs them to act differently, a sentence in `CLAUDE.md` or a skill rarely changes the habit: the agent read the sentence long before the moment it applies, and by then the trained default wins. What does change the habit is a pair: block the obvious case with code, and correct the less obvious cases with text the agent meets at the moment it acts.

## Why the pair works

- **The block arrives at the moment.** A block is a hook that refuses the act as the agent takes it. Its refusal is the one text the agent is sure to read at the one moment the rule matters, so the refusal carries the correction: what was stopped, why, and what to do instead. [How to write an agent-facing-message](nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md) says how to word it.
- **The block is blind to some routes.** A hook sees only the routes its code reads; the same act done another way passes. So the second half of the pair is a correction placed where the agent will be when it takes each route the block cannot see: a line in the step of the skill it is following, or a hook that notices the result after the act and tells the agent how to undo it, which the glossary calls detect-inform-correct. Where an unseen route does something that cannot be undone, the correction must reach the agent before the act, in the skill step.
- **A block that is wrong is soon ignored.** Block only what the hook can tell is wrong nearly every time. Where the act is sometimes right, make the block a soft-block, which the agent clears by writing its reason into the marker file the refusal names; the glossary defines hard-block, soft-block and user-block.

The [enforcement ladder](nedschorus-enforcement-ladder.md) orders every way of making an agent follow a rule; this page is about pairing its block rung with a rung below it, either detecting the act afterwards or text the agent meets at the moment, so that what the block cannot see is still corrected.

## A worked example: copying over a GHI-MD

**The default.** An agent writes a new version of a GHI-MD, the Markdown file that holds a GitHub issue's text, in a separate file, works on that version for days, then copies it over the GHI-MD. Main changed the GHI-MD meanwhile, and the copy undoes those changes without anyone noticing.

**The block.** A PreToolUse hook refuses a whole-file replacement of an existing GHI-MD under `docs/issues/`, made with `cp`, `mv`, `tee`, a `>` redirection or the Write tool. It is a soft-block, because a deliberate rewrite of the whole file is sometimes right. Its refusal says, with the hook filling in the GHI-MD's path and the path of the marker file:

> Refused: this command replaces the whole GHI-MD <path>, which can undo changes merged into it on main after your copy was written.
> Change the GHI-MD with the Edit tool instead, one passage at a time, so main's other changes stay.
> If you mean to replace the whole file, write your reason into <marker path> and run the command again.

**The correction.** The hook cannot see the same mistake made with the Edit tool: pasting in, passage by passage, text written days earlier. So the /ghi-write skill, which every agent follows to change a GHI-MD, says at its "Edit:" step:

> When your new text was drafted in another file, carry over only your own changes, passage by passage, because main may have changed the GHI-MD since.

Neither half works alone. The sentence alone loses to the habit, as a sentence in a skill usually does; the hook alone teaches the agent to use the Edit tool, and so moves the mistake to the one route the hook cannot see.

## When to show a rule

- **Not too early.** A rule read at the start of an agent-session fades as the context fills, which is why `CLAUDE.md` is the weakest place for one.
- **Not too late.** A rule shown after the act may find the act impossible to undo, or other work already built on it. Show it before the act or as it happens, and after the act only when the act can still be undone.
- **Not too often.** A reminder that fires on every edit is soon ignored, the time it matters included, and every firing costs context. Show a reminder once, when the agent first reaches the moment it applies to, and again only after the agent-session's transcript has grown by about 50,000 tokens, so that a pass of twenty edits sees it once. A hook can tell how far the transcript has grown from the size of the transcript file, whose path every Claude Code hook is given, by keeping the size at its last firing in a small file of its own. A refusal is the exception: it fires every time the wrong act is tried, because each firing stops a real act.

## Pairs the project already uses

Most blocks here are the first half of a pair only: a refusal that carries its own correction for the route the hook sees. Add the second half when an agent is found taking a route the hook cannot see.

- `.claude/hooks/ghi-issue-write-hand-typed-gh-command-refusal.py` refuses a `gh issue` write typed by hand and gives the `scripts/ghi-issue-write.py` command to run instead.
- `scripts/hand-typed-codex-exec-command-refusal-hook.py` refuses a hand-typed `codex exec` and sends the agent to `scripts/run-codex-task-from-brief.py`.
- `scripts/search-file-argument-read-as-option-guard-hook.py` refuses a search whose glob expands to a file name read as an option, and, where it can, gives the command back with `--` put in.
- `nc-systems/general-tools/claude-code-tmux-kill-server-and-kill-session-missing-server-selection-refusal-hook.py` refuses a tmux kill that names no server, and gives the command that names one.
- `scripts/force-push-with-open-pull-request-guard-hook.py` refuses a force push that would replace a pull request's pushed commits under review, and says when and how to push.
- `scripts/synthetic-keystroke-guard-hook.py` refuses keystrokes sent into a terminal, sends the agent to the SendMessage tool, and lets it rerun the command with `CLAUDE_VERIFIED_DETACHED=1` once it has checked the target terminal is detached.

A block paired with a detector after the act:

- `.claude/hooks/instruction-file-guard.py` refuses an Edit or Write of a guarded-file without the user's approval. It cannot see shell writes, so `.claude/hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py` notices, after every tool call, a guarded-file changed without approval, keeps every version, and tells the agent to ask the user.
