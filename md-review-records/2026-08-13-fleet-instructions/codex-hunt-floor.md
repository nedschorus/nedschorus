<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/fleet-instructions.md -->

1. “you own that model’s implementation.” This can mean the entire seat model, although the model assigns `fleet` only the launcher, supervisor, and isolation machinery. The broader reading gives this seat an undefined remit; the narrower reading leaves the phrase ambiguous. Confidence: unsure — the preceding pile may be intended to narrow it.

2. “awaiting the Mac-side review seat.” The seat model defines the Mac-side agent as the user’s own agent and explicitly says it is not one of the seats. This introduces a nonexistent or conflicting seat identity, making PR ownership unclear. Confidence: sure.

3. “Nothing else should touch those files until it merges.” If PR #57 is closed, superseded, or abandoned without merging, this condition never ends and freezes the files indefinitely. Confidence: sure.

4. “agent home at `~/agents/<name>`.” Both launchers allow `NEDSCHORUS_AGENTS_ROOT` to override that location, so this is not universally true. An agent following it literally may inspect or modify the wrong home. Confidence: sure.

5. “The name typed is the whole configuration — no roster.” The launchers also accept `--no-attach` and `--first-prompt-file`, and environment variables change the machine and agent-root behavior. Identical names can therefore launch materially different configurations. Confidence: sure.

6. “launches each session.” The supervisor’s adoption mode watches an already-running process instead of launching it. The sentence later mentions adoption but does not qualify this claim. Confidence: unsure — “each session” might be intended to exclude adopted sessions.

7. “recycles on every handoff.” A `dont-restart` handoff can stop the supervisor, and failed dialog extraction also prevents relaunch. A handoff therefore does not guarantee a successor. Confidence: sure.

8. “otherwise report and change nothing.” The supervisor fetches before checking whether the tree is clean; a dirty-tree or non-fast-forward case can still update remote-tracking refs and `FETCH_HEAD`. Confidence: sure.

9. “It never merges.” The supervisor executes `git merge --ff-only origin/main` when the clean branch is behind. A fast-forward is still a merge operation. Confidence: sure.

10. “blocks edits to CLAUDE.md and `.claude/` machinery.” The guard only intercepts `Edit`, `Write`, and `NotebookEdit` tool calls. A shell command or other direct file operation can bypass it, so this is broader than the mechanism actually enforces. Confidence: sure.

11. “without the user's walked approval, consumed through a `.walk-approved` marker.” The guard only checks whether the marker is nonempty; it does not verify the user’s words, the requested change, or who wrote it. An agent can create arbitrary nonempty content and pass the guard. Confidence: sure.

12. “rider 1's obvious detection method.” The queue uses the heading `## 1`, not the searchable phrase “rider 1,” and the target gives no rider name. Searching for the introduced name does not locate the referenced item reliably. Confidence: sure.

13. “Solve detection before building that guard.” This requires ongoing work but gives no definition of a solved detector, acceptance condition, or stopping point. An agent can pursue it indefinitely. Confidence: sure.

14. “coordinate with `sanity-checker`, which shepherds it.” “It” could refer to PR #52 or its findings, “shepherds” is unexplained, and no coordination action or channel is specified. The agent cannot execute this instruction unambiguously. Confidence: unsure — the seat model identifies the seat but does not define this coordination procedure.

15. “No side-by-side view exists. Simultaneous views mean one terminal per session.” This lacks the necessary scope: the harness may have no built-in side-by-side view, but tmux panes or windows can show multiple sessions within one terminal. The literal wording is unnecessarily absolute and can mislead the agent about available views. Confidence: sure.

16. “Two live sessions must never share a working directory.” The same document says forks and background jobs inherit the existing directory, and the proposed guard remains unbuilt. A normal fork or background session can therefore create exactly the stated violation. As written, this is either an impossible guarantee or an unenforced requirement. Confidence: sure.

17. “`EnterWorktree` relocates a running session correctly — the gap is the trigger, not the capability.” `EnterWorktree`, “the gap,” and “the trigger” are not defined, and no executable procedure identifies when or how the agent should use it. The core isolation instruction is therefore cryptic. Confidence: unsure — `EnterWorktree` may be a known tool name to the eventual agent.

18. “verify the renamed launchers work from the Mac.” The provided context contains no Mac execution environment, test procedure, or success criterion. A box-side agent cannot complete or know when this verification is complete. Confidence: sure.

clean sections: none
