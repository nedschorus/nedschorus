<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/issues/queue/45-session-seat-and-isolation-riders.md -->

1. “two live sessions must never share a working directory”

   The proposed guard only checks selected tool calls; it does not prevent two sessions from being started or attached in the same directory. The document also explicitly leaves reads and searches unblocked. Thus the stated invariant can already be violated without the guard firing. This harms any agent that treats the hook as enforcing directory isolation. Confidence: sure.

2. “a background job launched from a session inherits the same cwd”

   This is unqualified, but the referenced fleet document says background jobs may receive isolated task worktrees. As written, it conflates ordinary background jobs with jobs that the harness isolates. That makes the detector’s expected directory relationship ambiguous. Confidence: sure.

3. “call `EnterWorktree` first”

   `EnterWorktree` is not defined as a command, tool, or procedure in this file or `CLAUDE.md`. The later statement that it “relocates” a session does not explain how it is invoked or what happens with an occupied worktree or conflicting branch. The proposed denial message therefore teaches an action a future agent cannot execute from this context. Confidence: sure.

4. “Reads and searches stay unblocked; they never collide.”

   “Never” is too broad. A read or search can overlap a write, deletion, branch switch, or partial file update and observe inconsistent state or fail. Two sessions can also share a directory indefinitely if they only read, contradicting the invariant. Confidence: sure.

5. “another live Claude process”

   “Live” is undefined: the file does not say whether idle, pinned, attached, reaped, or viewer processes count. It also substitutes process identity for session identity even though the surrounding text says viewer processes can masquerade as sessions. A detector cannot classify these cases reliably. Confidence: sure.

6. “A working detector needs the session's own view of its working directory (its transcript records it, and the session itself answers correctly when asked), not the process table.”

   This describes a needed fact but no executable way to obtain it. It does not say how a hook identifies the current session, locates or parses another session’s transcript, asks a running session, handles stale records, or compares path aliases. A future agent cannot build the detector from this description. Confidence: sure.

7. “Resolve this before building the hook”

   “Resolved” has no stopping point or acceptance condition. It could mean a proof, a prototype, a reliable observation, or merely a documented limitation, so an agent cannot determine when this prerequisite is complete. Confidence: sure.

8. “a PreToolUse hook on `Edit|Write`” and “The project already runs this exact pattern”

   The referenced `.claude/settings.json` matcher is `Edit|Write|NotebookEdit`, and the referenced hook documentation also names `NotebookEdit`. The proposed scope omits notebook edits while calling the existing pattern exact. A notebook edit can therefore remain a reachable modification path outside the proposed guard. Confidence: sure.

9. “a PreToolUse hook runs for every session on the machine”

   The referenced launcher documentation says project settings are read from `.claude/` in the working directory, and the launchers can start an agent without project settings if checkout creation fails. Sessions in other projects or bare directories therefore do not necessarily run this hook. The absolute claim can cause agents to assume machine-wide protection that is absent. Confidence: sure.

10. “place every agent in `<agents-root>/<name>`” and “accept no directory argument”

    `<agents-root>` is not the actual configuration name used by either launcher, and the proposed `--directory` behavior is unspecified across the local Mac and remote Ubuntu launcher. The file does not define path interpretation, checkout validation, branch behavior, or how the directory interacts with the name-derived tmux session, handoff files, and lock. The change is not executable from this specification. Confidence: sure.

11. “promote this background thread to a visible tmux seat”

    “Background thread” and “seat” are not defined or mapped to a job, session, agent home, or tmux session. The later use of “background session” does not establish that these are the same object. The intended behavior of the proposed flag is consequently ambiguous. Confidence: sure.

12. “One branch per session removes the class: git already refuses one branch in two worktrees”

    Git restricts branches per worktree, not per session. The document itself describes multiple sessions sharing one working directory; those sessions can still use and push the same branch. The statement therefore does not remove the reported shared-branch failure mode. Confidence: sure.

13. “md-review the fleet paths reference” and “the md-review skill's stated target”

    No `md-review` skill, procedure, or acceptance criteria appears in the provided context. “Not yet reviewed” also supplies no completion condition beyond an undefined operation. A future agent cannot execute or close this item. Confidence: sure.

14. “the same name on both is two unrelated agents rather than a conflict” and “nothing more”

    The referenced launcher scripts use the agent name as the branch name when creating a worktree. The referenced fleet document explicitly says pushed branches cross machines and that two clones pushing the same branch fight over one remote ref. Thus identically named agents can create a cross-machine branch conflict; the suffix is not merely listing legibility. Confidence: sure.

15. “every session grouped by state”

    This is unqualified, while the file also distinguishes live jobs, job directories, session UUIDs, and transcripts that can outlive jobs. If “session” includes an idle-reaped or otherwise unregistered transcript, the agent view cannot show every session. If it means only active jobs, that narrower meaning is unstated. Confidence: unsure — the command may use “session” in a narrower product-specific sense.

16. “No side-by-side view exists in the harness. Simultaneous views mean one terminal (or tmux window) per session.”

    The scope of “harness” is undefined, and tmux itself can display multiple panes in one terminal or window. The second sentence therefore does not follow from the first and is false under an ordinary tmux reading. Confidence: unsure — the claim may intend only the built-in Claude view.

17. “a session showing 23 hours of `etime`”

    `etime` is not identified as a process field, command output, or Claude UI value. A future agent cannot reproduce the observation or know whether it means process elapsed time or some session-specific metric. Confidence: unsure — `etime` may be familiar as a `ps` field, but that is not stated.

18. “the honest staleness check is the modification time of its transcript under `~/.claude/projects/<project>/<session-id>.jsonl`”

    Transcript modification time is not necessarily activity time: buffered writes can lag activity, and harness or system events can update an idle transcript. The path placeholders are also undefined, and the text gives no behavior for a missing, rotated, delayed, or unreadable transcript. This can misclassify session staleness. Confidence: sure.

clean sections: none.
