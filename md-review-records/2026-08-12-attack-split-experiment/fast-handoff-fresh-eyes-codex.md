<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh attack=fresh-eyes doc=fast-handoff isolation=empty-scratch-directory -->

## 1. Your solution sketch

I would make recycling a property of a stable **session slot**, not something the agent must remember to do. A slot survives many Claude session IDs and owns one workspace, launch configuration, terminal pane or headless service, and an append-only generation history.

### Components

- **Session runner:** A small deterministic wrapper around Claude Code. It owns the child process group, terminal attachment, workspace lease, generation number, and restart state. Headless runners are supervised by systemd; interactive runners remain the foreground program in their existing terminal pane.
- **Boundary hook:** Reads the latest complete assistant record from the current transcript, calculates context pressure, and requests recycling. It never summarizes work or kills anything.
- **Checkpoint builder:** Captures task files, transcript identity, repository state, uncommitted work, and launch metadata into an immutable handoff bundle.
- **Bootstrap compiler:** Produces a bounded, mechanical continuation capsule and the successor’s opening prompt. It selects and copies facts; it does not ask another model to summarize.
- **Health notifier:** A systemd failure action plus a periodic state check. It records failures locally and sends one deduplicated notification through a configured channel such as a GitHub issue.
- **Control CLI:** Provides `status`, `recycle`, `hold`, `resume`, and `recover` operations. Automatic and manual recycling use the same state machine.

There is no central custom daemon. Each long-lived slot already needs a parent process; the runner gives that parent an explicit operational job.

### State and invariants

Each slot has a machine-local directory containing:

- Stable slot ID and generation number.
- Active Claude session ID, model, transcript path, PID, process start time, and boot ID.
- Workspace roots and exact launch arguments.
- State journal and current-state pointer.
- Immutable bundles for prior generations.
- Retry counters, health timestamps, manual hold state, and notification status.

The state machine is:

`RUNNING → PREPARING → PREPARED → STOPPING → STARTING → BOOTSTRAPPING → RUNNING`

Failures enter either `RETRYING` or `FROZEN`; every transition is journaled and atomically committed under a lock.

The mechanical invariants are:

1. Only the active generation may hold the slot’s workspace lease.
2. A successor never starts while the predecessor process group is alive.
3. A predecessor is never intentionally killed until a complete handoff bundle has been fsynced and recorded as `PREPARED`.
4. Session IDs are never reused, so transcripts and harness task files cannot be accidentally blended.
5. Recovery never resets the live worktree automatically. Checkpoints are evidence and restore sources, not authority to discard newer work.
6. Every transition is idempotent; after a runner or machine crash, current state can be reconstructed from the journal, PIDs, bundle hashes, and lease.

If sessions can share a worktree, the lease must be workspace-wide rather than slot-wide. Otherwise safe snapshots and single-writer guarantees are impossible.

### Triggering a recycle

At each synchronous turn boundary, the hook reads the last complete JSONL record for its exact session ID. It ignores a partially written final line and verifies that the record’s session and model match the runner’s state.

Context pressure is computed from the usage fields using a versioned model-capacity table. The hook maintains a high-water mark rather than assuming every reported value is monotonic. Recycling starts at a conservative soft threshold—initially around 60% of verified usable context—with a reserve established by measurement for unusually large tool results and the bootstrap turn. A manual request, model-specific absolute ceiling, or optional maximum-turn policy can also trigger it.

The hook creates one atomic recycle request and then remains blocked. Because the hook is still executing, Claude cannot begin another turn. The runner also stops delivering queued terminal input. This establishes a real boundary rather than relying on the old agent to notice a file or obey an instruction.

### Preparing the handoff

While the old session is quiescent, the checkpoint builder creates an immutable generation bundle containing:

- A copy of the predecessor’s task-file directory.
- Transcript path, size, last complete byte offset, and content hash.
- Model ID, final usage record, timestamps, and recycle reason.
- Exact working directories, environment allowlist, launch arguments, instruction-file hashes, and hook version.
- Per-repository branch, HEAD, status, recent commits, submodule state, and diff statistics.
- A content-addressed WIP checkpoint made without changing the live index or worktree. A temporary Git index records tracked changes, deletions, and non-ignored untracked files under a namespaced handoff ref. Index state is recorded separately if preserving staged versus unstaged intent matters.
- Copies of registered non-Git task artifacts that are required to resume.
- A list of tool calls or external operations that lack a recorded completion result.
- A verbatim continuation capsule containing the active task records, latest user request, recent assistant narrative, and recent tool outcomes. Oversized content is referenced by exact path, byte range, and hash rather than summarized.

Ordinary completed work remains in normal commits and GitHub. The hidden WIP commit is a local recovery point for an interrupted handoff, not a branch the successor must merge or reset to. Ignored files are excluded unless explicitly registered as durable inputs.

The task files are copied to a newly allocated successor session ID through a temporary directory and atomic rename. The old copies remain for audit and recovery.

If preparation fails at the soft threshold, the old session is released and the failure is retried at the next boundary. At a hard safety threshold, it remains frozen at the boundary and an alert is raised; continuing to consume context without a recoverable checkpoint is worse than stopping useful work temporarily.

### Cutting over

Once `PREPARED` is durable, the runner terminates the predecessor’s process group, first gracefully and then forcibly after a short deadline. It validates process identity using PID plus start time and boot ID to avoid PID-reuse mistakes.

The runner verifies that the old group is dead and releases its generation lease. It then launches a fresh Claude session with:

- A new session ID.
- The copied task files already in place.
- The same registered workspace, model policy, permissions, working directory, and tool configuration.
- A generated opening prompt containing the bounded continuation capsule and exact paths to the full bundle and transcript.

The opening prompt tells the successor to reconcile three sources before acting: the task state, the actual worktree, and the predecessor’s final transcript events. It must treat incomplete external operations as uncertain and query their real status before retrying them. If the compact capsule is ambiguous, the full transcript remains available for targeted inspection.

The successor performs the only model-dependent part: understanding the current task, resolving inconsistencies between recorded intent and actual state, and choosing the next useful action. Threshold detection, extraction, checkpointing, process control, task transfer, retrying, and alerting are all deterministic code. I would not introduce a separate summarizer model; it adds another lossy and fallible handoff.

The first completed successor turn causes its boundary hook to acknowledge the new generation. This proves that the new process started, loaded its hooks, wrote a transcript, and completed a request. It does not pretend to prove semantic understanding.

### Failure containment

- **Duplicate hook requests:** Serialized by the slot lock and generation ID; later requests become no-ops.
- **Malformed or partially written transcript:** Ignore the incomplete suffix and retry at the next boundary.
- **Unknown model or usage schema:** Use a conservative configured ceiling and alert. Do not silently guess a larger context capacity.
- **Checkpoint failure or disk full:** Do not kill the old process. Freeze at the hard limit and retain all existing state.
- **Runner crash during preparation:** The old session remains blocked or running; the restarted runner resumes from the journal.
- **Crash after `PREPARED` but before launch:** Systemd restarts the runner, which launches a successor from the existing bundle.
- **Old process refuses to die:** Do not launch a competing writer. Quarantine the slot and alert.
- **Successor launch failure:** Retry from the immutable bundle with bounded backoff. No rollback of the workspace is necessary.
- **Successor crashes during bootstrap:** Preserve its new transcript and any workspace changes, create a crash bundle, and retry with another session ID.
- **Uncertain external side effect:** The successor queries GitHub or the relevant system using stable object IDs before retrying. Exactly-once behavior is not inferred from a missing transcript result.
- **Unexpected machine reboot:** The runner reconciles journal state, validated PIDs, leases, worktree state, and the latest complete bundle before deciding whether to relaunch.
- **User input during an interactive cutover:** The runner buffers ordinary input until bootstrap finishes; control signals remain available. The pane never falls back to an exposed shell.
- **Alert delivery failure:** The alert remains in a local spool and is retried. Repeated identical failures update one incident rather than creating a storm.

## 2. The hard parts

1. **Does transcript usage actually measure remaining context?** Cached-input fields, system prompts, tool definitions, model changes, and output reservation may make the apparent count misleading. Prototype by replaying controlled conversations across every deployed model, comparing each usage field with observed compaction or rejection points. The result determines the formula and safe threshold.

2. **Is the hook a genuine quiescent boundary?** The design depends on the hook being synchronous and on blocking it preventing another model turn. Test interactive input, autonomous headless loops, tool calls, background subprocesses, transcript buffering, Ctrl-C, and runner crashes while the hook is blocked. This is the first concurrency prototype I would build.

3. **Does a fresh model actually continue as well as the old one?** “Not dumber” needs an operational definition. Run paired trials on representative long tasks: continue the old session versus recycle from the mechanical capsule, then score next-action correctness, duplicated work, missed constraints, recovery time, and new-context cost. Vary capsule size and which transcript events are selected.

4. **Can the WIP checkpoint reproduce every repository state the fleet uses?** Temporary-index snapshots interact with Git LFS, filters, submodules, sparse checkouts, worktrees, symlinks, file modes, staged/unstaged distinctions, and large untracked files. Build a fixture matrix, checkpoint it, restore into a separate worktree, and compare content and metadata.

5. **Can cutover survive a crash at every instruction?** Use fault injection after each state transition, fsync, rename, signal, task copy, and launch. On restart, assert that there is never both a live predecessor and successor and that a usable bundle always precedes intentional termination.

6. **What counts as an incomplete external action?** A process can successfully create a PR or issue and die before recording the result. Test each integration for stable request IDs, lookup APIs, and idempotency behavior. Any integration without reconciliation needs an explicit “possibly executed” state exposed to the successor.

7. **Will the interactive wrapper preserve terminal behavior?** Resize events, alternate-screen mode, paste, SSH disconnects, tmux pane death, signal forwarding, and buffered keystrokes are classic 2am failures. Exercise them under a pseudo-terminal test harness and verify that the pane never lands at an unmanaged shell.

8. **How is a dead runner noticed?** A runner cannot report its own total failure. Verify systemd supervision for headless slots and an independent timer for all slots. Stale state, repeated launch failures, frozen handoffs, disk pressure, and unknown usage schemas should create one durable local incident and one deduplicated remote notification.

9. **How much reserve is enough for a single oversized turn?** The hook only runs at boundaries, so one tool-heavy turn may jump far past the threshold. Measure the largest real context increase per turn and either lower the threshold accordingly or introduce tool-output truncation outside this design.

10. **Are all required state locations known?** The problem names transcripts and task files but not caches, plans, attachments, credentials, or harness metadata. Trace filesystem access during representative sessions, kill them, launch under a new ID, and identify every missing dependency.

The most likely unattended failures are disk exhaustion from retained bundles, restart loops caused by a bad launch configuration or hook version, a terminal wrapper losing its child, and an external operation being repeated. All need explicit health states, bounded retries, local forensic records, and a notification path independent of the Claude child.

## 3. Late discoveries

- Token accounting differs across model versions, cached prompts, and tool-use turns; “input tokens” is often not synonymous with live context occupancy.
- Context can grow substantially within one apparent turn, leaving no boundary at which the nominal threshold is observed.
- A turn boundary does not necessarily mean the filesystem is quiescent: compilers, tests, language servers, and agent-started background jobs may still be writing.
- The transcript may be buffered, rotated, truncated after a crash, contain multiple record schemas, or reference attachments whose bytes live elsewhere.
- Task lists are often stale. The real current objective may exist only in an old user message, an issue comment, a plan file, or the predecessor’s unrecorded reasoning.
- A successor can spend so much context reconstructing history that it immediately approaches the next recycle threshold.
- The bootstrap prompt, reloaded instruction files, or tool schemas may themselves become large enough to cause restart storms.
- Relaunch environment drift is easy to miss: working directory, environment variables, SSH agent, credential helpers, umask, resource limits, virtual environment, model flags, proxy settings, and terminal dimensions can all change behavior.
- Hooks or instruction files can change between generations. Reproducibility may require recording their versions while still intentionally loading the newest policy.
- Multiple agents may modify the same repository. A per-session lock then provides false confidence, and one checkpoint can silently capture another agent’s work.
- Git snapshots have sharp edges around ignored-but-important files, generated sources, LFS pointers, submodules, nested repositories, sparse checkout, filters, file modes, and secrets in untracked files.
- Hidden refs and transcripts accumulate until the disk fills. Retention needs reference-aware garbage collection that never deletes the last recovery point for a nonterminal slot.
- Automatically pushing WIP refs can expose secrets or proprietary artifacts; never pushing them means the recovery promise ends at machine failure.
- External systems do not provide exactly-once semantics merely because a tool call has an ID. “Request sent, response absent” is an enduring third state.
- Manual boss actions can race automation: a message may target the old generation, a forced recycle may arrive during preparation, or a hold may be set after termination has begun.
- PID files are unsafe across reuse and reboot unless paired with process start time, boot ID, and expected command identity.
- File locks may disappear or behave differently on networked filesystems and container boundaries.
- Terminal keystroke buffering can replay a command into the wrong program after restart, especially pasted newlines or Ctrl-C.
- The old session may own useful child processes, ports, mounts, or temporary credentials that disappear when its process group is killed.
- A clean Claude exit may mean “task complete,” “authentication expired,” “input closed,” or “crashed after printing success.” Exit code alone is insufficient restart policy.
- Security and privacy arrive late: transcripts and handoff capsules can contain credentials, proprietary text, personal data, and tool outputs with stricter retention requirements than source code.
- Clock jumps break age-based watchdogs and ordering unless monotonic clocks and journal sequence numbers are used.
- GitHub, DNS, or authentication may be unavailable precisely when alerts or remote checkpoints are needed. Local recovery and alert spooling must stand alone.
- “Seamless” means different things for headless throughput and interactive experience. Preserving work is easier than preserving terminal scrollback, pending user input, and the user’s mental model.
- Operators eventually need forensic tools: show why a recycle occurred, reconstruct the chosen capsule, compare generations, and safely materialize a checkpoint without altering the live workspace.

## 4. Assumptions

1. The launch path can place every long-lived Claude process beneath a controllable wrapper and distinct process group. Can the real harness guarantee that for both interactive and headless sessions?
2. Turn-boundary hooks are synchronous and may block without timing out or being detached. What exact lifecycle and timeout semantics do hooks have?
3. Blocking the boundary hook prevents Claude from starting another turn. Is there any concurrent internal loop that bypasses it?
4. The transcript record associated with the latest request can be identified unambiguously while the process is live. How are files named, rotated, and correlated with session IDs?
5. Token-usage semantics and context capacities are known for every permitted model. What happens when the model or record schema changes mid-session?
6. A sufficiently conservative threshold leaves room for the largest normal turn. What does production data say the maximum boundary-to-boundary jump is?
7. Each session has a registered, bounded set of workspace roots. Can an agent make durable changes elsewhere?
8. A workspace has only one writing slot, or all writers participate in a workspace-wide lease. Are shared repositories or worktrees allowed today?
9. Local disk survives a routine session recycle and is within the required durability boundary. Must handoffs also survive loss of the Ubuntu box?
10. Creating local namespaced Git refs and content objects is acceptable. Are repositories bare, read-only, unusually filtered, or subject to policies against hidden WIP commits?
11. Non-ignored untracked files are safe to capture, and ignored files are rebuildable or explicitly registered. Are secrets or required artifacts exceptions?
12. The repository is the durable record for completed work, while the handoff bundle is temporary containment. Is remote push required before killing a predecessor?
13. The harness task-file directory contains all session-scoped task state that must transfer. Is there additional opaque state keyed by session ID?
14. Task files can safely be copied to a new ID while retaining the old copy. Does the harness require moves, ownership metadata, locks, or an index update?
15. A successor can read the predecessor’s transcript and bundle through ordinary tools. Are there sandbox, ownership, or path-access differences between sessions?
16. The successor launches with equivalent model access, credentials, permissions, tools, environment, and working directory. Which of these are inherited implicitly rather than declared?
17. The opening prompt is allowed to reference local files and is reliably delivered as the first turn. Can any startup error or interactive input precede it?
18. Reloading the latest `CLAUDE.md` and hooks is desirable even if policy changed during the predecessor’s work. Should handoff preserve old behavior or adopt new behavior?
19. Functional continuity—not retention of hidden reasoning—is the intended meaning of “not dumber.” What measurable acceptance criterion does the project use?
20. Terminating at a completed boundary will not corrupt the transcript or harness state. Does Claude or the harness perform asynchronous post-turn writes?
21. The runner may terminate the old process externally despite the safety layer blocking self-termination. Are process signals, process groups, and parent-child ownership available?
22. Ordinary interactive input may be briefly buffered during cutover. Is lossless replay preferable, or should input be rejected and visibly requested again?
23. Background processes created by a session may be killed with it unless explicitly registered. Which services, tests, or tunnels are expected to survive?
24. External actions can usually be queried before retry. Which integrations lack stable lookup keys or idempotency support?
25. systemd is available for headless supervision and periodic health checks; interactive panes have a stable enclosing terminal or multiplexer. What actually owns those panes?
26. A deterministic remote notification channel and credentials are available to the Ubuntu box. Is GitHub the intended incident sink, and what happens during an outage?
27. Bounded automatic retries are preferable to infinite restart loops. After how many failures should a slot freeze and request intervention?
28. Retaining transcripts and bundles is permitted if stored mode `0700`. What are the required encryption, redaction, and deletion policies?
29. Normal restart latency of several seconds is acceptable. Are any sessions latency-sensitive or expected to respond continuously?
30. Subagents and cross-machine migration remain excluded, so their state and ownership do not need to participate in this protocol.