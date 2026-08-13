<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh attack=mechanization doc=fast-handoff isolation=instruction-pinned document set -->

# Prompts-to-code table

| Site | Disposition | Reason |
|---|---|---|
| Recognize a user’s natural-language request for “handoff,” “restart,” or consultation | Correctly delegated residue | Intent may be ambiguous; code can only receive the resulting bounded mode. |
| Detect the context threshold | Already mechanized | The statusline relay and Stop hook calculate and compare the percentage. |
| Obey the threshold message and complete the handoff before continuing ordinary work | Finding 1 | The trigger is mechanical, but completion still depends on the model obeying “Run the handoff skill now.” |
| Compose the successor’s actual first action | Correctly delegated residue | This requires understanding unfinished work and user intent. |
| Keep `next-step` an instruction rather than a summary | Correctly delegated residue, partly verified | Semantic quality is interpretive; empty input and newline transport are already checked mechanically. |
| Choose the conversation boundary | Already mechanized | The extractor owns the 2500-word floor and nearest-user-turn extension. |
| Invoke `--boundary-quote` manually | Correctly delegated residue | A manual override exists specifically for exceptional semantic boundary judgment. |
| Decide whether to follow the full-transcript pointer | Correctly delegated residue | Only the successor can judge whether missing context matters to its task. |
| Stamp time, calculate the counter, normalize whitespace, and write atomically | Already mechanized | The writer owns these fields and invariants. |
| Stage `next-step` in a file and invoke the exact writer command | Finding 1 | Transport and sequencing are still prompted procedure. |
| Supply `<your name>` | Finding 3 | This is stable configuration, explicitly described as the remaining “unscriptable” input. |
| Supply file commit SHAs and GitHub repository identities | Finding 5 | These are lookup/canonicalization facts mixed into semantic drafting. |
| Decide whether `dont-restart` reflects the user’s request | Correctly delegated residue, already constrained | Natural-language intent is interpretive; the result is already a Boolean flag. |
| Answer `restart? y/n` | Correctly delegated human checkpoint | Consultation is the requested policy, not a remembered maintenance duty. |
| Follow the writer’s liveness report, stop/wait, or continue and notify the user | Finding 1 | This is deterministic branching assigned to the model. |
| Recover after a supervisor dies | Finding 1 | Detection is mechanized, but the design says recycling stops until something relaunches it. |
| Kill, wait, extract, locate JSONL by UUID, and retain files | Already mechanized | These are supervisor/extractor algorithms with tests. |
| Copy task records to the successor UUID | Already mechanized | The file operation is code-owned. |
| Validate that copied tasks are structurally usable and visible | Findings 2 and 4 | A model count and remembered upgrade canaries currently guard undocumented state. |
| Re-run canaries after every Claude Code upgrade | Finding 4 | A version comparison is a computable trigger. |
| Fall back to queues after incompatibility | Finding 4 for fail-closed routing; residue for artifact authoring | Code can block uncertified pre-seeding; deciding and writing task-shaped GHIs requires project semantics unavailable here. |
| Print queue depth and oldest item | Already mechanized | The queue-status line is calculated by script. |
| Decide what to commit, queue, or drain | Correctly delegated residue | Coherent commit boundaries and artifact ownership require judgment; blindly committing a shared worktree would be unsafe. |
| Read the handoff file before acting | Finding 2 | The supervisor already has the contents and can place them in the initial prompt. |
| Interpret the elapsed-time warning | Correctly delegated residue | Code can compute age, but cannot generically decide which external facts became stale. |
| Confirm `N` tasks before working | Finding 2 | Count, schema, copy integrity, and compatibility can be checked mechanically. |
| Take the next step and reconcile conversation with current artifacts | Correctly delegated residue | This is the handoff’s substantive work. |
| Challenge cross-artifact inconsistencies such as “50 completed tasks but 14 files” | Correctly delegated residue | No generic handoff algorithm knows each task’s expected work product. |
| Avoid combining `--allowedTools` with a positional launch prompt | Finding 2, verification | A launcher invariant/test should replace the English “never combine” warning. |
| Wire the Stop hook during the seat move | Finding 3 | This is a one-time but silent-failure-prone remembered setup duty. |
| Start pane sessions with the supervisor as parent and preserve visible output | Finding 3 | The desired topology is known once mode is selected; startup code can enforce it. |
| Write the founding prompt | Correctly delegated residue | The first assignment is semantic. |
| Commit a founding or boss-requested durable snapshot | Correctly delegated residue | Snapshot contents and historical intent require judgment. |
| Execute the founding launch pattern | Finding 3 | A launcher can preserve the ruled positional-prompt behavior mechanically. |
| Tune the threshold and 2500-word floor | Correctly delegated human policy | These are performance/risk choices; code already applies the selected values. |

## Finding 1 — Make retirement an atomic, persisted handoff transaction

**WHAT**

Replace the prompted “run, inspect report, branch, then wait” procedure with a small persisted lifecycle owned by the hook, writer, and supervisor:

`idle → due → published → consumed`

- At threshold, the Stop hook records `due`; it does not forget the obligation after emitting one message.
- While `due`, the hook repeats or gates on the same exact approved handoff request until the writer acknowledges it.
- A shared `ensure_supervisor` routine starts an adopting supervisor when the heartbeat is dead, using the current session identity rather than discovery.
- The writer prepares the handoff, confirms a live watcher, atomically publishes the counter, and then does not return control to the retiring model. The supervisor’s kill completes the successful call.
- If a watcher cannot be established, the writer does not publish a live counter and returns one typed, loud failure. Exception communication may remain with the model.
- Preserve the `dont-restart` human gate unchanged.

**WHY**

The governing objective is “a fleet of interactive agents running with little attention” and recycling “without the human typing into each pane.”

The remaining model-controlled branch is explicit:

> “Do what it reports. When it found a supervisor watching, or started one, stop working and wait … When it reports it could not start one, do not stop: keep working, and tell the user…”

The design itself says these operations are one deterministic decision:

> “a handoff nobody is watching must not stop the agent working”

Yet the known hole says:

> “if it dies, recycling stops until relaunched”

and:

> “the threshold hook stays silent when nothing is watching”

That is a silent loss of the central autonomous behavior. Heartbeat, stale-lock reclamation, session ID, and PID already exist, so recovery does not require discovery or semantic judgment.

**Recorded-ruling collision**

This directly changes the approved allocation:

> “The two-command procedure collapsed into one: the script reports, the agent obeys.”

It also strengthens the ruled “one script that does everything best done by script.” Because it removes the approved “agent obeys” branch, it must be explicitly re-walked rather than treated as a cleanup.

The exact ratified message—

> “Run the handoff skill now.”

—can remain unchanged. What changes is the mechanical pending state and retry policy behind it.

**LOST**

The model loses the flexibility to keep acting after a successful writer invocation, and the implementation gains a small persisted state machine. A failed setup still returns control. Priority 1 pays: successful handoff intent already authorizes retirement, while permitting more model actions introduces race and omission risk without useful flexibility.

**CONSEQUENCES**

The following become false or stale:

- `SKILL.md` steps 2–3, especially “reports whether a supervisor is watching” and the entire “Do what it reports” branch.
- The design’s writer description: “writes the handoff file atomically, then reports whether a supervisor is watching and what that means for the agent.”
- The component description: “writes `next-step` … runs the writer, waits for the supervisor.”
- The walk record’s item 5 description of “one command plus following what it reports.”
- The walk record’s item 6 ruling that “the script reports, the agent obeys.”
- The walk record’s verbatim proposed steps 2–3.
- “the agent starts it when its handoff script finds none watching” must acknowledge that the due hook may also call the shared ensure operation.
- The known-hole text saying recycling stops until a supervisor is manually relaunched and the threshold hook remains silent.
- The Auto-trigger, Writer, and Skill build-status claims require revalidation after this lifecycle change.
- The trigger test “threshold crossing fires the skill exactly once” must become: one pending obligation is created; it persists until one handoff is published; repeated hook execution cannot publish twice.
- Add tests for dead-supervisor recovery, failure before counter publication, a writer call that never returns to a still-live retiring model, and retry after an ignored first trigger.

## Finding 2 — Turn successor ignition into a mechanically verified startup package

**WHAT**

Have the supervisor construct the successor’s first prompt from the actual extracted dialog and `next-step`, rather than instructing the model to read a path. Retain the on-disk files and full-JSONL pointer for recovery.

Before launch, mechanically:

- Parse every copied task record and enforce the observed schema, including string `id` and required `blocks`/`blockedBy` arrays.
- Verify destination count and content hashes against the source manifest.
- Attach a machine-produced result such as `task-preseed: verified; count=N` to the startup package.
- Combine this with the version certification in Finding 4 before treating disk validity as harness compatibility.
- Construct the subprocess argv in one function and assert that a positional prompt can never coexist with `--allowedTools`.

The successor then receives the verbatim dialog, elapsed-time fact, task verification result, and semantic next action directly. Its remaining responsibility is interpretation and action, not file-reading and counting choreography.

**WHY**

The design declares:

> “The conversation is the key context.”

but currently launches with English instructions for:

> “the exact handoff path to read … confirm N tasks visible … then take the next step.”

The live skill similarly promises:

> “Your successor will read the last few thousand words of this conversation before acting on your prompt.”

The supervisor already created those contents and builds the ignition prompt. Asking the model to retrieve known input adds a fallible tool-routing step.

The task check is also based on exact mechanical invariants. The document records:

> “A task record’s `id` is a STRING, and `blocks`/`blockedBy` arrays are present; a record with an integer id is dropped by TaskList while still counting toward the next allocated id.”

That is a parser/schema test, not a judgment call. Likewise:

> “`--allowedTools` on the launch silently prevents the positional prompt from firing — never combine them in a launcher”

should be an argv invariant and regression test, not retained programmer memory.

**Recorded-ruling collision**

The walk approved the sentence that the successor “reads the last few thousand words.” Changing that to “receives” touches approved skill text and requires re-walking. It does not reverse the ruling to carry verbatim conversation or reintroduce distillation.

**LOST**

This removes the successor’s independent, per-session TaskList count announcement and makes the initial positional prompt larger. It also replaces a general “pause and inspect” moment with narrower mechanical checks.

The generic semantic check must therefore remain explicit residue: the successor should still judge whether the conversation, repository, and work products agree. The essay discrepancy cannot be reduced to task-file count. Priorities 1 and 2 pay for removing deterministic startup chores while preserving the real judgment.

The documents do not expose a non-model API for inspecting Claude Code’s internal TaskList view. If version certification is not accepted, the per-session visibility check cannot safely be removed solely on the strength of filesystem validation.

**CONSEQUENCES**

The following require revision:

- “Bounded by what the successor already has, since it reads the conversation tail before acting.”
- Supervisor step 6’s path-reading and task-count instructions.
- `SKILL.md` step 1 and both copies of that text in the walk record: “will read” becomes “will receive.”
- The Ignition Prompt build-status row: “dialog path … task count” becomes embedded dialog plus a verified manifest.
- Component 5: “path, elapsed-time line, task count, next step.”
- The supervisor test “ignition prompt contains path + elapsed-time line + task count.” Replace it with verbatim-dialog inclusion, next-step inclusion, task-manifest verification, recovery-pointer inclusion, and argv incompatibility tests.
- The known-hole bound “the ignition count-check and the per-upgrade canaries.”
- The trial criterion “Each successor reports the expected task count” is historical evidence only, not the new acceptance contract.
- The statement that dialog files contain “the count confirmation” remains historical but ceases to describe required future dialog.
- The explanation that the essay discrepancy is “the behavior the ignition prompt’s count-check exists to produce” becomes false. Preserve the observed discrepancy as evidence for delegated semantic consistency judgment, not for LLM arithmetic.

## Finding 3 — Provide one idempotent installer/launcher for identity, hook wiring, and pane topology

**WHAT**

Create one local setup and launch mechanism that:

- Stores a stable logical agent ID in configuration and exports it to the writer; remove `--agent <your name>` from model-authored commands.
- Idempotently installs and verifies the required Stop-hook settings.
- Takes an explicit bounded mode, `interactive` or `headless`.
- In interactive mode, starts the supervisor as the pane’s parent and launches Claude as its child.
- In headless mode, permits detached output and adoption.
- Before launch, checks that the selected output target and controlling terminal match the mode; refuse a configuration that would relaunch an interactive successor invisibly.
- Uses the ruled positional-prompt invocation internally for the founding boot.

The human selects the name and mode once during provisioning. Code thereafter carries and verifies them.

**WHY**

Two remembered setup duties remain explicit:

> “Only the Stop-hook wiring into NC’s settings remains, and it belongs to the seat move.”

and:

> “Settle this before the seat move rather than after.”

The consequence of forgetting the second is not cosmetic:

> “wrong for a console pane, where the successor would run invisibly.”

The skill also requires the model to substitute:

> `--agent <your name>`

while the walk record admits:

> “One input remains unscriptable until NC has an agent-naming convention: the agent’s own name.”

That is configuration waiting to exist, not irreducible model judgment.

**Recorded-ruling collision**

This preserves the user-requested “self-registration, not discovery” architecture: adoption remains the bootstrap/recovery path and no machine-wide scan is introduced. It also implements, rather than re-litigates, the recommendation that pane supervisors be parents.

The founding ruling that the launcher must pass a positional prompt remains an internal launcher invariant.

**LOST**

Raw, ad hoc `claude` starts become unsupported for guaranteed recycling unless the launcher adopts them in recovery mode. Setup code must carefully merge user settings rather than overwrite them. Priority 1 pays: an invisible successor or unwired Stop hook defeats the system silently.

The exact NC settings schema and the source of the naming convention are not present in the allowed document set, so the specific configuration keys cannot be prescribed here.

**CONSEQUENCES**

Revise:

- The implementation-status claim that only manual Stop-hook wiring remains.
- “Not yet done: wiring the Stop hook … belongs to the seat move.”
- “the agent starts it when its handoff script finds none watching” to distinguish normal parent-supervisor startup from adoption recovery.
- The entire “Open question” paragraph; it becomes a resolved, enforced launch contract.
- The founding boot’s raw command should be described as launcher behavior, while preserving its positional-prompt semantics.
- `SKILL.md` step 2 and the walk-record copy must drop `--agent <your name>`.
- The walk record’s “remains unscriptable” statement becomes false.
- The build table needs an Installer/Launcher component and verification status.
- Add tests for idempotent hook installation, preservation of unrelated settings, stable agent identity, interactive parentage/TTY routing, headless log routing, and refusal of an unsafe mode/output combination.

## Finding 4 — Gate undocumented task pre-seeding by executable version automatically

**WHAT**

At supervisor startup or before the first pre-seed on a new executable version:

1. Read the actual Claude Code executable path and version.
2. Compare it with a cached certification record keyed by version, executable identity, and canary revision.
3. On a miss, run both pre-seed canaries automatically.
4. Record pass/fail atomically.
5. Permit pre-seeding only for a passing certificate; on failure, preserve the old task store and enter a typed fail-closed state.

Code can expose the documented queue fallback, but automatic GHI creation should not be invented from this document set: the referenced artifact rules were not available and were explicitly out of scope for reading.

**WHY**

The document assigns a permanent remembered duty:

> “re-run both canaries after every Claude Code upgrade”

The trigger is exactly a version change, and the risk is concrete:

> “This rides undocumented harness internals”

and:

> “a schema-wrong pre-seed looks half-successful.”

A half-successful task migration is precisely the kind of quiet failure that merits a compatibility gate.

**LOST**

The first startup after an upgrade becomes slower and may fail closed until compatibility is restored. Automatic canaries may incur process or model cost. Priority 1 pays: a short upgrade delay is cheaper than silently dropping tasks across every later recycle.

**CONSEQUENCES**

Revise:

- Supervisor step 4’s imperative to “re-run both canaries.”
- The Supervisor build-status row; a historical green result for v2.1.220 is no longer the operative authorization.
- The supervisor test description “task pre-seed as executable canaries (re-run per upgrade).” Replace it with version-change execution, cached pass, changed-canary invalidation, and fail-closed tests.
- The known-hole text “bounded by … the per-upgrade canaries” should say “bounded by a version-keyed automatic compatibility gate.”
- The v2.1.220 verified facts remain historical evidence, while the current certificate becomes runtime state.
- The queue-backstop sentence must distinguish automatic refusal from the still-semantic act of creating or selecting queue artifacts.

## Finding 5 — Make references structured; let code generate and validate pins

**WHAT**

Keep the open-ended action text, but constrain references to typed tokens or a sidecar schema, for example:

- `[[file:docs/foo.md]]`
- `[[issue:nedschorus/nedschorus#40]]`

The writer should:

- Find the repository containing each file.
- Reject an uncommitted referenced file when no commit SHA can truthfully identify its current contents.
- Resolve and append the repository HEAD SHA mechanically.
- Canonicalize repository names and issue numbers from configured aliases/remotes.
- Render one canonical reference block into the handoff.
- Reject undeclared path/issue-shaped references where mechanically recognizable.
- Verify every declared file exists at the resolved commit.

The model still decides which artifacts are semantically relevant; it no longer computes or transcribes pin facts.

**WHY**

The skill says:

> “If your prompt references a file, include its path and commit SHA. If it references a GitHub issue, include the repository and number.”

The invariant is sound:

> “Every pointer carries a pin”

but commit SHA and repository identity are stable lookup facts. The same design already establishes the governing direction:

> “The agent supplies only `next-step`; the writer fills every field a machine can compute.”

It also documents why raw textual transport is fragile:

> “a shell mangles backticks and quotes inside an inline argument”

and why silent parsing errors matter. Structured references extend that reasoning to pointer facts.

**Recorded-ruling collision**

The two pin cases were explicitly user-approved in walk item 4. This finding preserves the required pins but moves their derivation from the model into the writer. Because it changes approved skill wording and responsibility, it needs re-walking.

**LOST**

Free-form pointer syntax becomes less convenient, and a referenced dirty file may block handoff until committed or deliberately excluded. Cross-repository aliases require configuration. Priority 1 pays: an incorrect SHA quietly directs the successor to the wrong artifact version, while a rejected unresolved reference fails loudly.

**CONSEQUENCES**

Revise:

- The design’s statement that “The agent supplies only `next-step`” to distinguish semantic action text from typed reference declarations.
- The `next-step` field description assigning path/SHA and repository/number construction to the prompt writer.
- `SKILL.md` step 1 and its verbatim walk-record copy.
- Walk item 4’s approved pin instructions.
- The Writer component and its build-status test count; add clean/dirty file, nested repository, missing path, invalid commit, repository alias, and canonical rendering cases.
- The writer may still take a file, but it becomes a structured handoff request rather than arbitrary one-line prose alone.
- The successor-side wording about “resolving what the writer meant” should state that code supplies the immutable identity; the successor interprets only whether later state changes affect the task.

## Delegated residue certification

The following work rightly remains with a model or an explicitly consulted human:

- **Drafting the first action.** Determining what unfinished work matters and expressing a useful next instruction requires semantic understanding of an arbitrary conversation and repository.
- **Selecting relevant artifacts.** Code can pin a declared file or issue, but cannot know which artifacts the next action actually needs.
- **Interpreting natural-language restart intent.** Code should receive a bounded restart policy; classifying an ambiguous user request requires language judgment.
- **The `restart? y/n` decision.** This is the requested human authority checkpoint, not forgotten maintenance.
- **Reading beyond the extracted tail.** The header and pointer can be mechanical, but relevance of older context depends on the active problem.
- **Reconciling stale or inconsistent state.** Elapsed time, counts, hashes, and schemas are computable; deciding what a changed repository or mismatched work product means is domain-specific.
- **Commit, queue, and durable-snapshot content.** Git and queue operations can be scripted after selection, but coherent boundaries, ownership, and historical value require judgment.
- **Founding prompt content.** The initial assignment has no predecessor state from which an algorithm can derive the intended work.
- **Threshold, floor, and launch-mode policy choices.** Humans choose the risk/cost tradeoff once; configuration and enforcement should then be mechanical.

These are the genuine interpretive residue. The sequencing, retries, identities, compatibility gates, task validation, pointer facts, and operational setup around them do not need model variability.