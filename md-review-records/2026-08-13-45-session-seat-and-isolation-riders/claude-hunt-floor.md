<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/issues/queue/45-session-seat-and-isolation-riders.md -->

Findings, in document order.

**1. Opening paragraph — "one had forked into another's checkout" is not explained by the mechanism this file gives.**
Quote: *"...one had forked into another's checkout."* (line 3), compared with Item 1's explanation: *"a fork inherits the parent's directory along with its conversation... which is what made several jobs look like duplicates"* (line 7).
The mechanism in Item 1 explains how a fork or background job ends up sharing *its own parent's* directory. It does not explain how the parent itself came to be working in a directory that belonged to a *different* session in the first place — that prior, more basic collision is the actual event the opening line describes, and no cause for it is given anywhere in the file. A future reader trying to reconstruct the incident cannot do so from what's here.
Confidence: unsure — this may be intentionally out of scope for a "riders" document that only records proposals, not incident forensics.

**2. Item 1 — the stated invariant is broader than what the guard is designed to enforce.**
Quote: *"The invariant: two live sessions must never share a working directory."* (line 7), against *"Reads and searches stay unblocked; they never collide."* (line 9).
If reads and searches are explicitly allowed to proceed while another session shares the directory, then two live sessions demonstrably *can* share a working directory (while one or both are only reading) without violating anything the proposed mechanism cares about. The actual rule the guard enforces is closer to "must never *write* while another session is in the same directory," not "must never share a working directory." As written, the invariant and its own justification disagree about what state is forbidden.
Confidence: sure.

**3. Item 1 — "The proposal" describes the detection method the same paragraph goes on to falsify.**
Quote: *"a PreToolUse hook on `Edit|Write` that refuses when another live Claude process shares this session's working directory"* (line 9), against *"A working detector needs the session's own view of its working directory... not the process table."* (line 9).
The proposal sentence defines the hook's trigger condition in terms of another *process* sharing the directory — i.e., process-table detection. Later in the same paragraph, process-table detection (the `/proc` scan) is reported tried and found unreliable, and the fix is stated to require a different data source (transcript or session self-report) instead of the process table. It is left unclear whether "The proposal" as stated already presupposes the (not-yet-built) working detector, or whether it still literally describes the falsified `/proc`-based approach — the sentence's own wording ("another live Claude process") points at the latter.
Confidence: sure.

**4. Item 1 / Item 3 — "instruction-class" and "the user's walk" are used across sections but only explained once, indirectly.**
Quote: *"needs an entry in `.claude/settings.json` (instruction-class, so it lands through the user's walk)"* (line 13); reused at *"Instruction-class text, so it lands through the user's walk."* (line 25).
Neither term is defined in this file. Item 1's occurrence sits next to a path reference to `.claude/hooks/instruction-file-guard.py`, and that file's own docstring does use the phrase "the user's walk" and explains the approval mechanism — so a reader who follows that reference from Item 1 can recover the meaning. Item 3 repeats "Instruction-class" and "the user's walk" without repeating that pointer, relying on the reader to have retained Item 1's context under an unrelated heading three sections later.
Confidence: unsure — the meaning is recoverable via Item 1's reference, so this may be an acceptable amount of forward-reliance for a single short document rather than a real gap.

**5. Item 1/3/5 — "choirmaster" is never identified; its nature must be pieced together from three separate mentions.**
Quote: *"...duplicates in `~/agents/choirmaster`"* (line 7); *"`Merge remote-tracking branch 'origin/choirmaster' into choirmaster`"* (line 23); *"Migrating `choirmaster` to a machine-suffixed name"* (line 31).
The file never states what choirmaster is (an agent name, per the directory/branch/seat pattern implied across the three mentions). A reader gets a directory path, then a branch name, then talk of "migrating" it and moving "its" git worktree — from which "agent" can be inferred, but no sentence ever says so. This is exactly the kind of name that is easy to misread in isolation (e.g., mistaking it for a project or a person).
Confidence: unsure — the identity is recoverable by reading all three mentions together, so this may be adequately self-documenting for this file's own scope.

**6. Item 2 — the `--directory` flag's semantics are unspecified.**
Quote: *"A `--directory` flag for the launchers"* (line 15) and *"Roughly ten lines per launcher."* (line 17).
The item doesn't say whether `--directory` overrides the existing `<agents-root>/<name>` convention entirely, supplements it, or how it should interact with the already-existing `--first-prompt-file` flag on both launchers. A reader tasked with implementing this later has a goal ("adopt an existing worktree") but no interface spec to build against.
Confidence: unsure — this is a queue note recording a deferred idea, not a spec, so under-specification may be expected at this stage.

**7. Item 4 — "Not yet reviewed" is contradicted by the current state of the checkout.**
Quote: *"Not yet reviewed."* (line 29), referring to `docs/cross-project/fleet-machine-paths-and-checkouts.md`.
The checkout already contains a populated `md-review-records/2026-08-13-fleet-machine-paths-and-checkouts/` directory with completed hunt/restate passes and a reference-check dated the same day, whose reference list (`launch-claude-mac`, `launch-claude-ubuntu`, `~/agents/choirmaster`, etc.) matches that exact target file. The review this item calls for has already run; the file's claim is stale.
Confidence: sure — verified directly against the files on disk.

**8. Item 5 — "the two machines share no agent state" is stated as an unqualified justification, but Item 3 describes exactly the kind of state that *is* shared across machines: a pushed branch on the common origin remote.**
Quote: *"The two machines share no agent state, so the same name on both is two unrelated agents rather than a conflict — the suffix buys legibility... nothing more."* (line 33), against Item 3's *"Several sessions pushing to one shared agent branch produced the `Merge remote-tracking branch 'origin/choirmaster' into choirmaster` commits"* (line 23).
If an agent's branch name is derived from its agent name (as the `choirmaster` branch in Item 3 suggests, matching the `choirmaster` directory name in Item 1), then two same-named agents on two different machines would push to the identically-named branch on the one origin remote both machines share — which is precisely the collision class Item 3 exists to describe. Item 5's claim that a name collision across machines is "not a conflict... nothing more [than legibility]" does not account for this, and Item 3 in the same file is evidence that shared-branch collisions are a real, already-experienced problem.
Confidence: unsure — Item 3 doesn't state whether its incident involved sessions on one machine or two, so the counterexample depends on a detail the file leaves unspecified; the general claim in Item 5 is still broader than the file's own evidence supports.

clean sections: Title, Session-management facts worth keeping (verified 2026-08-13, Claude Code 2.1.231)

