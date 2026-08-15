<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=defect-hunt tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/fleet-instructions.md -->

1. “you own that model’s implementation.” The referenced seat model covers task grouping, naming, retirement, filing, and every seat’s responsibilities—not merely agent machinery. This can mean either ownership of all operational aspects of the model, overlapping the other seats, or ownership only of the launcher/session subset named earlier; the boundary is not stated. Confidence: sure.

2. “Your pile: **the machinery that runs agents**” assigns ongoing work without a completion criterion. The seat model explicitly says, “Each brief states its own criterion,” but this brief never says when this pile is finished; its first action, riders, and issue list do not establish an endpoint. After the immediate action, an agent can either stop prematurely, wait indefinitely, or invent adjacent work. Confidence: sure.

3. “**PR #57**, branch `launch-claude-machine-named-launchers`, awaiting the Mac-side review seat.” This is factually stale: local `origin/main` contains merge commit `f9964e7`, “Merge pull request #57 from nedschorus/launch-claude-machine-named-launchers.” A cold agent could unnecessarily wait for review or continue honoring the associated file freeze. Confidence: sure.

4. “awaiting the Mac-side review seat.” The seat model defines a seat as “a named, long-lived agent identity: a name, a home directory (`~/agents/<seat>`), its own git branch, and a brief,” then explicitly says the “Mac-side agent … is not one of the seats defined here.” Calling it a review seat therefore supports incompatible readings about whether this is a defined, launchable seat or the user’s separate Mac agent. Confidence: sure.

5. “`scripts/launch-claude` renamed to `launch-claude-ubuntu` plus a new `launch-claude-mac` twin.” The old name is a repository-relative path, while both new names omit `scripts/`; the later launcher definition uses `scripts/launch-claude-{ubuntu,mac}`. A literal reader can look for or execute the wrong paths. Confidence: unsure because ordinary rename shorthand may implicitly retain the directory, but the file uses inconsistent path notation.

6. “the supervisor’s branch sync; the session riders; the fleet work inventory; and these seat briefs.” These are not explicit paths or a determinable file set. In particular, the exact name “fleet work inventory” appears only here, while the apparent artifact is named `docs/issues/queue/45-ubuntu-fleet-open-work-inventory.md`; “these seat briefs” has no enumerated referent. This makes the following restriction’s targets impossible to identify from the brief. Confidence: sure.

7. “**Nothing else should touch those files until it merges.**” “Nothing else,” “touch,” and “those files” each admit incompatible readings: unrelated changes versus every change, reading versus editing, and described concepts versus the PR’s actual file list. It is also an overbroad absolute: an ordinary review-requested correction or merge-conflict resolution may have to modify one of the same files before the PR can merge. Confidence: sure.

8. “agent home at `~/agents/<name>`” presents a configurable default as an invariant. Both launchers honor `NEDSCHORUS_AGENTS_ROOT`, so the home can be elsewhere. An agent following the brief can inspect or manipulate the wrong directory on a configured machine. Confidence: sure.

9. “the handoff supervisor inside.” “Inside” has no referent: it can mean inside the tmux session, agent home, launcher, or checkout. Those readings imply different process and filesystem relationships, which matters when diagnosing or stopping the supervisor. Confidence: sure.

10. “The name typed is the whole configuration” is literally false. The adjacent text says identity comes from `CLAUDE.local.md`, while the launchers also accept environment configuration and options such as `--first-prompt-file` and `--no-attach`. Reusing a name alone therefore does not reproduce the whole configuration. Confidence: sure.

11. “launches each session, recycles on every handoff, exits when its agent stops without one.” The referenced supervisor can adopt a session it did not launch, and a handoff does not always cause recycling: `dont-restart` can stop it, and failed conversation extraction prevents relaunch. These reachable cases contradict “each” and “every” and can make an operator misdiagnose a deliberate or defensive stop as supervisor failure. Confidence: sure.

12. “it **syncs the agent’s branch with main before each launch** — fetch, then fast-forward” does not describe fetch failure. The implementation continues against the on-disk `origin/main` after a failed fetch and can fast-forward to that stale ref, so the resulting branch is not necessarily synchronized with current main. This matters precisely during network or remote failures, when a successor may incorrectly believe it woke on current code. Confidence: sure.

13. “otherwise report and change nothing.” Fetch occurs before the stated conditions and can update remote-tracking refs and `FETCH_HEAD` even when a dirty or divergent working branch is left alone. The phrase is false if “nothing” means repository state and ambiguous if it means only the checked-out branch or working tree. Confidence: sure.

14. “It never merges” supports incompatible Git readings. The implementation invokes `git merge --ff-only`; that never creates a divergent merge commit but is still commonly described as performing a fast-forward merge. An agent auditing whether the supervisor executes merge commands can reach the opposite conclusion from one auditing only merge commits. Confidence: sure.

15. “and never runs on the adoption path” has an ambiguous antecedent. Read grammatically as referring to “The supervisor,” it is false because the supervisor implements adopted sessions; only branch synchronization is skipped during adoption. “Adoption path” is also not introduced in this brief, making the intended narrower reading difficult to recover without inspecting the implementation. Confidence: sure.

16. “changing files under a live agent is the one forbidden act” is an overbroad absolute unless silently scoped to branch synchronization. Ordinary counterexamples in the checkout include pushing to `main`, modifying the legacy reference system, and changing instruction-class files without walked approval. The broad reading erases those prohibitions; the narrow reading lacks an explicit subject. Confidence: sure.

17. “a Stop hook firing at 50% context” omits reachable limits of the mechanism. The referenced hook remains silent when it lacks a session ID, transcript, or measurable assistant record, and it fires only once per session after writing a marker—even if the agent fails to hand off. Thus reaching 50% does not guarantee a reminder or recycle, and the brief leaves that failure state undisclosed. Confidence: sure.

18. “`.claude/hooks/instruction-file-guard.py` blocks edits to CLAUDE.md and `.claude/` machinery without the user’s walked approval” overstates the enforcement boundary. The hook is wired only to `Edit`, `Write`, and `NotebookEdit`; a shell write is an ordinary counterexample. This can create a false belief that the policy is mechanically enforced across all write paths. Confidence: sure.

19. “walked approval, consumed through a `.walk-approved` marker.” The marker mechanism is not bound to a path, proposed change, or approval text: the guard accepts any nonempty marker and consumes it on the next protected editor call. A stale, unrelated, or malformed marker can therefore authorize a different edit, a reachable store case not acknowledged by the brief. Confidence: sure.

20. “Solve detection before building that guard.” “Solve” has no stopping test: the brief does not identify supported session types, acceptable false-positive or false-negative behavior, race handling, or evidence that ends the investigation. An agent can either declare success after another narrow probe or remain blocked indefinitely. Confidence: sure.

21. “## Your queue” followed by “Issues:” supports incompatible readings of the listed material. The first named queue contains five ideas “deliberately not built,” while the issue list supplies neither status nor an instruction saying whether those issues are owned tasks, dependencies, or references. Under a queue heading, a future agent cannot determine what it is authorized or expected to take next. Confidence: sure.

22. “PR #52 … is adjacent — coordinate with `sanity-checker`, which shepherds it.” “Adjacent” does not identify whether the relationship is shared files, sequencing, or subject matter. More importantly, the seat model says seats “cannot” hand work to one another and their only channel is through the user; this brief supplies no executable coordination procedure consistent with that rule. Confidence: sure.

23. “It lists **only the machine it runs on**; the box needs `ssh nedlern@ned-box -t 'claude agents'`.” The origin of the SSH command is missing. From the Mac it reaches the box; from the fleet seat already running on the box, direct `claude agents` is sufficient and the literal instruction causes a self-SSH. Confidence: sure.

24. “**No side-by-side view exists.** Simultaneous views mean one terminal per session.” The absolute first sentence is broader than the qualification that follows. An ordinary counterexample is placing two per-session terminal windows side by side; only a single built-in multi-session view appears to be absent. This can make an agent conclude simultaneous visual monitoring is impossible. Confidence: sure.

25. “check its transcript’s modification time under `~/.claude/projects/`.” The brief does not explain how to map the job shown by `claude agents` or its eight-character job ID to the relevant project directory and session-UUID transcript. With many transcripts under that tree, the procedure can select an unrelated recent file. Confidence: unsure because the interactive agent view may expose the session UUID, but this file does not say that it does.

26. “**Two live sessions must never share a working directory.** Forks inherit the parent’s directory … `EnterWorktree` relocates a running session correctly.” Taken literally, the invariant is impossible during the described transition: a fork must already be running in the inherited directory before a running-session operation can relocate it. The absolute is also broader than the collision it is meant to prevent—two read-only sessions are an ordinary non-colliding case—and “background jobs inherit” omits jobs launched with explicit worktree isolation. Confidence: sure.

27. “If it has, verify the renamed launchers work from the Mac and tell the user.” The seat model places named fleet seats on the Ubuntu box and says Mac commands are run from the user’s Mac; it provides no route by which this agent can execute or observe Mac-local launcher behavior. “Work” also has no test boundary—no indication whether it covers no-name help, creation, attachment, both launchers, or cleanup—so the required verification is neither executable from the seat nor clearly complete. Confidence: sure.

clean sections: none
