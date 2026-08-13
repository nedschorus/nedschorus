<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh attack=mechanization doc=gatekeeper isolation=instruction-pinned document set -->

## Prompts-to-code table

This inventory covers every gatekeeper-related model or human duty described across the four supplied files; unrelated handoff-only duties are context, not review subjects.

| Site | Disposition |
|---|---|
| Agents must use the gate rather than raw `git push` | **Finding 1.** C2 mechanizes this, but installation remains a multi-step human duty and is not applied. |
| Agent chooses which changes belong together | **Correctly delegated residue.** Intent has no mechanical source of truth. |
| Skill relays `--files`; gate reads live worktree bytes | **Finding 2.** Derive the declaration and immutable bytes from the staged index. |
| Agent writes the what-and-why message | **Correctly delegated residue.** |
| Agent obeys the message’s “one-line” contract | **Finding 7.** Mechanically validate it. |
| Skill computes and passes `--base` | **Finding 5.** Compute it inside the gatekeeper. |
| Agent declares whether work is an import and selects its source/destination | **Correctly delegated residue; already bounded and mechanically verified.** |
| Agent associates the work with an issue or `none` | **Correctly delegated residue; already constrained to two forms.** |
| Agent declares `runtime/model` | **Finding 6.** Use available runtime/transcript facts instead. |
| Origin, digest, trailer formatting, JSON replies, import table | **Already mechanized.** |
| Caller chooses `--wait`/`--no-wait`, later `status`, or `cancel` | **Correctly bounded operational choice; state transitions are already mechanical.** |
| Agent executes a refusal’s next action | **Mostly residue.** Syntax and retry instructions are generated mechanically; conflict correction requires intent. |
| Agent refreshes its worktree “at its convenience” | **No correctness duty:** candidate reconstruction and integration already isolate the gate from that choice. |
| Agent must “confirm intentional” undeclared worktree changes | **Correctly delegated residue.** Code can list differences but cannot know intended scope. |
| Human must connect a test suite or new policy check when it appears | **Finding 4.** The trigger and routing can be encoded. |
| Agent judges whether a refusal deserves an issue comment | **Correctly delegated residue.** “Genuinely blocking” is semantic. |
| Concurrent integration, retry cap, deduplication, crash-state classification | **Already mechanized.** |
| Agent resolves a real content conflict | **Correctly delegated residue.** |
| Agent resubmits after a crash or infrastructure refusal | **Cleared:** rare, loud, safe, and part of the accepted no-journal recovery ruling; a daemon would not earn its complexity here. |
| Agent decides whether to cancel or revert | **Correctly delegated residue; already constrained to explicit state-dependent commands.** |
| Agents decide when to consult the boss | **Correctly delegated residue.** |
| Owner installs the account, Unix-user boundary, tokens, sudoers, protection, and git config | **Finding 1.** |
| `gh` rewriting, raw-push denial, privileged test-seam refusal | **Already mechanized once installed.** |
| User approves break-glass access and owner-only recovery | **Correctly delegated residue and intentional security checkpoint.** |
| Audit must run “at each handoff scrub” | **Finding 3.** That trigger was removed by the supplied handoff revision. |
| Slow-check impact analysis and merge-queue growth | **Partly Finding 4:** measure and signal slow checks mechanically; the optimization itself remains deliberately deferred. Retry-cap pressure is already loud. |
| Naming hygiene grows back when a token set exists | **Correctly deferred:** creating that policy set is an explicit design event, not a quiet recurring duty. |
| Review-evidence format and approval semantics | **Correctly delegated residue until the authority defines the evidence format; enforcement must then be code.** |
| Cross-machine architecture choice | **Correctly deferred residue.** The first unsupported caller fails loudly and the alternatives change security topology. |
| Hand-written slice test planning | **Correctly delegated residue and explicitly ruled.** Test design needs interpretation; execution and assertions are mechanical. |

## Findings

### 1. Encode deployment as an idempotent provisioning transaction

**WHAT**

Add a deterministic provisioning/check command, separate from the one-file gatekeeper:

- A root-authorized host phase creates the dedicated Unix user, installs the canonical program and permissions, writes and validates the exact sudoers rule, installs the push credential, and sets `user.name`, `user.email`, and `useConfigOnly`.
- An org-owner-authorized GitHub phase configures the selected collaborator, branch restriction, enforce-admins, force-push/deletion settings, and agent-token permissions, then reads them back.
- Owner credentials/passwords are supplied ephemerally and never stored.
- The command emits a machine-readable readiness result and refuses to call the gate live until every invariant passes.

Account creation or token issuance may still require GitHub interaction, but the provisioner should name the missing prerequisite rather than leave a checklist to memory.

**WHY**

The reviewed spec says the layout is “**not yet applied**,” the gate is “**dormant**,” and “**applying it needs an org owner**.” The binding adds several coupled requirements:

> “the main-capable credential is owned by a dedicated Unix user”

> “agents invoke the gatekeeper through a sudoers rule scoped to exactly that program”

> “Branch protection’s push restriction on `main` moves … to the gatekeeper account alone”

> “Replace with a fine-grained token scoped to `nedschorus/nedschorus`”

A partial or mistaken installation can leave a superficially working gate without the boundary on which “only one way to main” depends. Those settings are deterministic desired state; only authorization needs a human.

This preserves the C1–C4 rulings rather than reopening the chosen account layout.

**LOST**

Ad hoc installation flexibility and a shorter build. The owner still performs the privileged approval, but no longer chooses or remembers individual settings. Priority 1—simpler and safer operation—pays for the installer and fixtures.

**CONSEQUENCES**

- The implementation-status paragraph must replace “dormant” and “not yet applied” with provisioner state or its last verified result.
- The credential section’s C1–C4, C7, git-config, and “until C2 is installed” prose becomes generated/verified configuration rather than an installation recipe.
- The build plan’s slice 5 must include provisioning, not only “repo git config,” audits, and documentation.
- Build-plan open item 1 and “go live when the credential question is settled” become stale; the account form is already ruled, and the remaining action becomes running the provisioner.
- C5’s password-gated break-glass sudoers entry should be rendered and verified by the same mechanism.
- No existing T1–T12 assertion becomes false, but none proves this boundary. Add fixture tests for rendered permissions/sudoers/configuration, mocked API readback, partial-install refusal, and idempotent rerun.

### 2. Make the Git index snapshot the declaration

**WHAT**

Remove normal `--files` transcription. At screening, derive the path set, file modes, deletions, and exact blob bytes from the caller’s staged index relative to the resolved base. Snapshot those values once into the request record and compute the digest from that snapshot. The model’s deliberate act remains staging the intended changes.

The advisory should compare unstaged work against the captured index, not compare a hand-written path list against a mutable worktree.

**WHY**

The specification currently says:

> “The new content of each path is read from the invoking agent’s working copy”

while C6 says:

> “`--files` relayed from the agent’s own staging”

and:

> “the agent contributes only … choose the files”

Relaying names from staging but reading bytes from the live worktree leaves two avoidable gaps: the skill can mistranscribe the staged set, and a file can differ from its staged version when the gate reads it. Staging already contains the intentional selection and immutable blobs; asking a model to restate it adds no judgment.

This collides with accepted D1’s “reads the caller’s worktree exactly once, for the declared paths” and changes C6’s ruled transport. It does **not** overturn C6’s ruling that file selection is intentional or its rejection of deriving the whole declaration from `git push`; message, issue, import intent, and staging remain deliberate.

**LOST**

Direct check-in of unstaged files and hand-written subsets. Callers must maintain a meaningful index. That is already the C6 workflow, and priority 1 pays for eliminating transcription and live-worktree races.

**CONSEQUENCES**

- Remove `--files` from the normal request syntax and rewrite field 1.
- `import-dest-undeclared` must mean “destination absent from the staged snapshot.”
- Digest field 8 must name indexed blobs/modes rather than worktree bytes.
- Candidate construction must consume the captured snapshot.
- `unknown-path` largely disappears from normal calls; `unchanged-path` and `empty-change` operate on the derived index delta.
- The stray-change guarantee and advisory text must distinguish staged from unstaged changes.
- C6’s “`--files` relayed” instruction disappears; the skill only stages and supplies interpretive fields.
- Accepted build-plan D1 and its “read exactly once” test assumptions become stale.
- C8 still requires a shared filesystem unless the snapshot is later serialized; this finding does not silently choose a cross-machine transport.
- Revise T1, T2, T3, T9, and T11 for staged additions, modifications, deletions, partial staging, post-staging worktree edits, and import destinations.

### 3. Attach the audits to a real mechanical trigger

**WHAT**

Invoke the audit command exactly once from the handoff supervisor’s recycle cycle, include its named outcome in the successor’s ignition/status material, and integration-test the invocation. Provision whatever narrowly scoped read capability the branch-protection query needs; it need not be push-capable.

If the audit process cannot start or authenticate, the supervisor must surface `audit-failed`, not silently omit the step.

**WHY**

The gatekeeper spec promises:

> “a standing audit at each handoff scrub”

But the supplied handoff revision says:

> “the superseded machinery — … the scrub modes … is recoverable”

and:

> “full manual scrubs died”

Its seven-step supervisor cycle contains queue status but no gatekeeper audit. Therefore the named trigger no longer exists; building the audit command alone will not make it run.

There is also an unresolved capability detail in the supplied set: C3 says the current agent “**cannot even read protection settings**,” while C4 grants contents/issues permissions only. The documents do not establish whether the dedicated write collaborator can read protection settings. I did not chase that fact outside the supplied set; the design must name a read-capable mechanism or accept deterministic `audit-failed`.

This preserves the ruled “audits are detection, not gating” boundary. It does collide with the boss-walked handoff cycle by adding a step, so that cross-spec change requires an explicit walk.

**LOST**

A looser coupling between recycling and repository monitoring, plus some recycle latency and credential plumbing. Priority 1 pays because an audit that is never invoked provides no detection.

**CONSEQUENCES**

- Replace “at each handoff scrub” with the exact supervisor invocation.
- Add the audit to the handoff supervisor’s numbered cycle and ignition/status output.
- The handoff implementation-status and “every component … built” claims become stale until this integration lands.
- The handoff supervisor tests must assert exactly-once audit execution and all three outcomes.
- Build-plan slice 5 must include trigger wiring and credential/readability validation.
- T12 remains useful but incomplete; it must also prove that an ordinary recycle invokes the trailer scan. B3c must exercise `protection-ok`, `protection-wrong`, and `audit-failed` through the real trigger.
- C3/C4 must identify the audit’s read authority. A read-only observer credential does not reopen C1’s rejected App/CI pusher design or create another main writer.
- The “git history and transcript only” record rule remains true if the result is carried into the successor transcript; a timer with an independent log would require revisiting it.

### 4. Install a fixed, auto-discovered check runner now

**WHAT**

Have the gatekeeper mechanically discover and execute the repository’s established self-running test convention—currently `scripts/*-test.py`—against the candidate, with fixed argv execution, timeout, output bounds, and named `check-failed`/`check-timeout` outcomes. Any test-like file must be discovered or explicitly excluded in code with a reason.

Measure total check duration and emit a deterministic `checks-slow` advisory at a configured threshold. That mechanizes the trigger for later impact analysis without implementing the boss-deferred optimization.

**WHY**

Success claims:

> “The checks ran against exactly the content that was pushed.”

Yet version 1 says:

> “when a test suite exists, the tests run here”

The supplied build plan already identifies:

> “`scripts/git-gatekeeper-test.py` … standard library only, self-running”

and the reviewed status says the implementation has a “**146-case suite**.” Thus the existence trigger is no longer safely represented by “when”; code must either run the suite or explicitly classify why it is not a gate check.

The approval-evidence format referenced by the open section is unavailable in the supplied set, so this finding does not invent that semantic policy. Once defined, its checker should enter the same mechanical execution path.

**LOST**

Check-in latency, new refusal modes, and test-discovery maintenance. Priority 1 pays because the exact-content check guarantee otherwise depends on someone remembering to connect a suite. Full reruns preserve the boss-ruled deferral of impact analysis.

**CONSEQUENCES**

- “No refusal remains” between screening and push becomes false.
- Add `check-failed` and `check-timeout` to the error catalog and teaching templates.
- Procedure step 4 and success guarantee 2 become concrete rather than prospective.
- Concurrent clean reapplication must run the discovered checks again, as the current text promises.
- The build plan’s “there are no slow checks yet” may become stale after measuring the 146-case suite; that measurement determines whether slice 4 should move earlier.
- T2 must prove the runner saw the candidate’s literal bytes. T4 must prove rerun after integration. Add timeout, malformed output, discovery, exclusion, and failure-side-effect cases.
- The deferred impact-analysis row should name the mechanical duration threshold, while retaining its boss-ruled “not yet.”
- Keep discovery inside the standard-library gatekeeper so C5’s one-file historical recovery remains valid.

### 5. Compute the base inside the gatekeeper

**WHAT**

Remove normal `--base`. During screening, run the already-selected computation—`git merge-base HEAD origin/main`—inside the program and store its full resolved commit in the request record. Retain an unprivileged test-only override if fixtures need it; privileged canonical operation must derive it.

**WHY**

The request asks the caller for:

> “the full 40-character commit id of the main state the work started from”

but C6 already says:

> “`--base` computed as `git merge-base HEAD origin/main`”

This is a direct fact lookup with one known command. Passing the result through a skill and model adds stale-value and transcription possibilities without adding intent.

This changes the C6 user ruling that the **skill** computes the value, and accepted D1/D4 assume a “declared base.” The value and semantics remain unchanged, but the recorded location ruling is a genuine collision and must be walked.

**LOST**

The ability to intentionally supply an older arbitrary base in a normal privileged call. Priority 1 pays because the gate’s concurrency and digest semantics need the actual branch point, not caller flexibility.

**CONSEQUENCES**

- Remove `--base` and rewrite field 3.
- `unknown-base` and `base-not-on-main` disappear from normal caller-form errors; internal derivation failures need named outcomes.
- Digest construction still includes the resolved base.
- Replace “declared base” throughout candidate construction and concurrency with “resolved base.”
- C6’s skill instructions and the raw-push explanation no longer list `--base`.
- Accepted build-plan D1 and D4 must say resolved rather than declared base.
- Update T1’s base-error cases; T2–T6 must assert the mechanically resolved base. Test fixtures may use the unprivileged seam governed by C7.

### 6. Resolve model identity from primary runtime data

**WHAT**

For supported runtimes, resolve `runtime/model` mechanically at screening:

- Runtime from the session environment.
- Claude model from the current session’s ID-keyed transcript record.
- Reject a caller-supplied value that disagrees with an authoritative detected value.
- For unsupported or transcript-less callers, constrain the fallback to configured runtime/model values rather than accepting any non-empty string.

**WHY**

The spec says:

> “Declared by the caller because the environment names the runtime but not the model”

and D3 says:

> “The caller is the only party that knows which model it is.”

The supplied handoff facts instead establish:

> “Every assistant transcript record carries … `message.model`”

The gate already records the session ID as origin, and the handoff design already specifies ID-keyed transcript lookup. Therefore at least for the documented Claude runtime, this is a primary-source fact rather than model judgment. A typo currently passes because `--agent` is only required and non-empty, silently degrading the fix ladder that the trailer exists to support.

This directly contradicts accepted, uncontested D3. The later supplied transcript fact is grounds to reopen it, but the collision must be walked explicitly.

**LOST**

A uniform caller-declaration interface and unrestricted model labels. Runtime adapters and transcript-format canaries require maintenance. Priority 1 pays because accurate provenance is more useful than silently accepted free text.

**CONSEQUENCES**

- Make `--agent` automatic for supported sessions and a constrained fallback elsewhere.
- Rewrite field 6 and the trailer explanation from “literal value declared by caller” to “resolved provenance.”
- Extend B4c’s resolve-once request record to retain the evidence source.
- Update C6’s division of labor to include agent identity among mechanically derived fields.
- Replace build-plan D3.
- T2’s exact trailer test must fixture runtime metadata. T3 must retain the rule that agent metadata does not affect the digest. Add detected/declaration mismatch, absent transcript, malformed transcript, and unsupported-runtime cases.
- Preserve the break-glass path’s explicit fallback because an old or transcript-less recovery invocation may have no adapter.

### 7. Enforce the one-line message and trailer namespace

**WHAT**

Reject commit messages containing CR/LF or any line that could enter the reserved `Gatekeeper-*:` trailer namespace. Use a named form refusal such as `malformed-message`; accepted text is still passed verbatim.

**WHY**

The CLI promises:

> “`--message "<one-line summary of what and why>"`”

but its stated validation is only:

> “Required, non-empty (`missing-message`).”

The same message is placed “above the trailers,” while success guarantees that:

> “The commit’s trailer lines carry the whole machine-readable record.”

Without code enforcement, a model can accidentally submit multiple lines or trailer-shaped text, making trailer parsing, audits, and provenance ambiguous. This is exactly the kind of formatting invariant where model variability adds nothing.

It does not overturn C6’s “message passed through verbatim”: valid messages remain unchanged.

**LOST**

Multiline commit bodies and trailer-like author text, neither of which the declared contract permits. Priority 2—simpler to understand—pays, while priority 1 gains unambiguous machine records.

**CONSEQUENCES**

- Field 2 must specify the exact accepted character/line contract.
- Add `malformed-message` to the form-error catalog and teaching templates.
- C6 should say “validated then passed verbatim.”
- T1 needs newline, carriage-return, and reserved-trailer cases with no side effects.
- T2’s exact trailer assertion must prove exactly one program-generated instance of every reserved trailer.
- Digest behavior remains unchanged because message metadata is still excluded.

## Delegated residue

- **Selecting and staging the intended change:** no code can infer which edits the author means to publish together.
- **Writing the what-and-why:** the purpose of a change is semantic author intent, not a repository fact.
- **Choosing import provenance, issue association, and whether an event is genuinely blocking:** these depend on project meaning rather than syntax; code should only constrain and verify the selected representation.
- **Resolving real conflicts and interpreting undeclared extra work:** determining whether two edits preserve intent requires understanding the change.
- **Choosing wait/cancel/revert and escalation timing:** these are bounded operational or risk judgments whose correct answer depends on current human goals.
- **Defining approval evidence, artifact classes, check applicability, and future cross-machine topology:** these are policy and architecture decisions. Once decided, their routing and enforcement belong in code.
- **Break-glass and owner recovery approval:** this is deliberately retained human authority, not forgotten labor; automating the approval would destroy the security boundary it protects.

These are certified as genuine interpretive or authority-bearing residue. Everything else identified above has a stable mechanical source, transition, trigger, or invariant and should not remain an English-trained habit.