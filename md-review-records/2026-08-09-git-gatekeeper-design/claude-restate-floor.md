<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=restate tier=floor target=/home/nedlern/agents/choirmaster/docs/cross-project/git-gatekeeper-design.md -->

# Frontmatter

No prose fields — `status` and `design-as-of` are data (a status label and a date). Nothing to restate.

# Title and preamble

1. There is exactly one program, the script `scripts/git-gatekeeper.py`, and it is the sole means by which any change reaches the main branch — no other path exists.
2. This program is the only holder of the project's single credential that has permission to push to the repository.
3. All AI agents working on the project, without distinction or hierarchy among them, call this program directly to make changes, and none of them ever pushes to the repository itself.
4. This is a summary phrase emphasizing the arrangement's singularity: one program, one credential, one point of entry through which all changes must pass.
5. No agent acts as an intermediary or forwarding point for another agent's check-in requests — even though "choirmaster" happens to be the agent that submits requests most often, that frequency grants it no special intermediary role.
6. For every request submitted to it, the program's response is always exactly one of two outcomes: it accepts and incorporates the work, or it declines and, in declining, explains how to fix the problem.
7. When the operation succeeds, four specific facts are guaranteed to hold.
8. The submitted change now exists as part of the main branch, and that branch has been pushed to the GitHub-hosted repository.
9. The validation checks that were run were executed against precisely the same content that ended up being pushed — no discrepancy between what was checked and what was committed.
10. The commit that was created includes trailer lines containing the complete record of the operation in a machine-readable form, with further detail given in "The trailer" section.
11. The requesting agent receives a response indicating success, along with the identifier of the commit that was created.
12. When the request is refused, the response always has three parts — likened to how a well-built MCP tool should respond, never just a bare, unexplained error code: (a) a specific named error drawn from a fixed, predefined list; (b) concrete factual details about the refusal (e.g., which file, which check, what mismatch); and (c) precise next-step instructions written specifically to be followed by an AI agent.
13. When a request is refused, the repository remains completely unmodified — a refusal causes no side effects of any kind.
14. The only places where a record of what happened exists are the git commit history and the ordinary transcript/log of the agent session that made the request.
15. There are no extra files or separate logging systems created solely to record this activity — invoking the program is treated as an ordinary tool call, and such calls are already recorded wherever tool calls are normally recorded.
16. It is always safe to submit the same request again.
17. Submitting the exact same request again produces the exact same response as before; but a request that has been corrected/changed produces a different digest and is processed as a brand-new request.
18. Work that has already successfully completed the check-in process will, if resubmitted, simply return `already-checked-in` with the existing commit id, rather than being redone.
19. An agent that crashed or lost its network connection is never expected to determine what state the operation was left in — it simply submits the request again, and the program itself figures out the correct outcome.
20. Because refusals always teach how to fix the problem, and because resubmitting costs nothing and is always safe, the system corrects itself over repeated attempts — and this self-correcting property is described as necessary for achieving near-perfect autonomous operation.
21. This describes the subject of the document: the process by which a code change ends up incorporated into the main branch within the "nedschorus" project.
22. This design's responsibility stops once a change reaches the main branch — a decision made by "the boss" on 2026-07-24; taking code from main and deploying it to a production environment is a separate concern belonging to DevOps/CI design, to be addressed later, once the project first has a long-running process; until then, main happening to also serve as "production" is coincidental, not something this design causes or manages.
23. For ordinary/typical changes, the workflow involves no separate git branches and no pull requests — changes are integrated by some other mechanism, not the branch-and-PR workflow.

# The job and the guarantee

(Command usage/help syntax omitted — not prose.)

1. Field-by-field validation is described next; all form validation happens instantly and synchronously in both operating modes, and every refusal at this stage names both the specific error and how to fix it.
2. The `--files` argument is a list of repository-relative paths, subject to normalization rules: no absolute paths, no `..` parent-directory references, nothing inside `.git/`, no duplicate entries, and the list must not be empty.
3. For each declared path, the program reads its new content from the calling agent's own working directory — and this is the only point in the entire process where the program reads anything from that working directory.
4. For each declared path, the program determines the type of change by comparing the base commit to the working copy: "added" (absent at base, present now), "modified" (differs), or "deleted" (present at base, absent now).
5. Three refusals apply here: `unknown-path` when a declared path exists in neither the base nor the working copy (likely a typo); `unchanged-path` when a declared path's content is actually identical to the base (declarations must honestly reflect real changes); `empty-change` when nothing differs at all.
6. The `--message` argument is the human-readable explanation of what the change is and why, and it becomes the commit message body, placed above the trailer lines.
7. This field is required and must not be empty; if missing or empty, the refusal `missing-message` applies.
8. The reasoning behind a change can only come from its author — the program cannot generate it automatically.
9. The `--base` argument must be the full, unabbreviated 40-character commit hash identifying the state of main that the work started from.
10. Abbreviated ids are disallowed because they can become ambiguous as history grows; branch names are disallowed because they are mutable references that move over time.
11. The base commit must actually exist and must be part of main's history; if not, the refusals are `unknown-base` (doesn't exist) or `base-not-on-main` (exists but isn't on main).
12. The `--import` argument is either `none`, or it must supply all three required parts together: a legacy commit id, a source path, and a destination path.
13. The source path must exist in the legacy repository at that exact commit, or the refusal is `import-source-missing`; if the legacy checkout can't be read at all, the refusal is `legacy-unreadable`.
14. The destination path must also appear among the paths listed in `--files`, or the refusal is `import-dest-undeclared`.
15. Supplying only one or two of the three required import parts results in the refusal `import-incomplete`.
16. It is structurally impossible to specify a second import within one request — a second import must be a separate, second check-in.
17. The `--issue` argument accepts either `none` or a positive whole number.
18. In this first version, the program checks only that the value is syntactically valid — it does not verify anything further, such as whether the issue actually exists.
19. A separate, upstream process called the "artifact-lifecycle rule" is responsible for deciding, at the appropriate level of detail, which work needs an issue reference; the gatekeeper merely records whatever answer that process has already produced.
20. Supplying `none` is a legitimate answer for trivial work — no check-in is ever required to have an issue, since issues represent wanted work, not a log of every action.
21. The `--agent` argument identifies the software runtime and AI model that produced the change (e.g., `claude-code/opus-5`); it is required and must not be empty, or the refusal `malformed-field` applies.
22. The caller must supply this value because, while the environment automatically knows the runtime, it does not automatically know the model — and the model is the piece of information an escalation process (called the "fix ladder," apparently for escalating to progressively more capable models when fixing refused work) needs, so that "who last produced this" becomes discoverable with one `git log` lookup.
23. This field belongs to a "cooperative" category of information: the gatekeeper records whatever value it's told and never attempts to independently verify or infer it.
24. The "Origin" field is filled in automatically by the program from the calling agent's session environment, not supplied explicitly by the caller.
25. If this information is unavailable, it is simply recorded as `none`, and this never blocks the request — a caller lacking a transcript is treated as legitimate, not erroneous.
26. This field is useful because the project's agents run in long-lived sessions: the session id points to a transcript that can be read to understand the intent behind the change.
27. The digest is a SHA-256 hash computed over a specific set of inputs: the base commit id, the sorted list of file paths, the actual new byte content of each path (with deletions represented by a marker), and the three-part import information.
28. Certain fields are deliberately excluded from this hash: the message, issue reference, mode, origin, agent, and time — because the digest's purpose is to identify the substance of the work itself, so identical work resubmitted with different surrounding metadata is still recognized as a duplicate.
29. The digest is computed by the program itself, not generated or supplied by the calling agent.
30. Every invocation outputs exactly one JSON object to standard output, with fields `outcome`, an optional `error`, optional `facts`, an optional `next_action`, an optional `commit`, an optional `digest`, and a `summary` (a human-readable one-line description); this single format (referenced as ruling B1) is used for all cases, not different formats for success versus failure.
31. The process exit code conveys three categories: 0 for success or other informational answers; 1 for a catalog refusal (the gatekeeper functioning as designed); and 2 for a defect/bug in the program itself — kept distinct so that automated retry counters or audits never mistake a program bug for a legitimate refusal.
32. If the caller used waiting mode and the request succeeded, the response is `checked-in` with the commit id at exit 0; if the request initially lost a race but was cleanly reapplied afterward, the reply additionally includes `integrated_over: <n>`, the number of newer commits it was reapplied over.
33. If the caller used non-waiting mode, once the request's form passes validation it immediately gets `accepted` with the digest; the actual final outcome must be retrieved later via `status <digest>`, and the immediate reply's `next_action` field says exactly that.
34. Any refusal, regardless of cause, takes the three-part explanatory form described earlier and results in exit code 1.
35. The `status` command, given a digest, answers using only information that already exists (git history plus the program's workspace): `checked-in` with the commit id; `in-progress`; `abandoned` (the workspace still exists but the worker process died — safe to resubmit); or `unknown` (no trace found — always safe to submit).
36. The `cancel <digest>` command is described in detail in the later "States, crashes, cancel, and errors" section.
37. The `imports` command prints a table of imports, derived by scanning main's history for every `Gatekeeper-import` trailer, showing what was imported, from which legacy commit, to where, and when.
38. This dynamically-generated view replaces the previous, now-discontinued rule requiring a manually appended row in an "entry-manifest" file; that file still exists but only as a historical record from the project's founding, no longer actively maintained.

# The procedure

1. Step 1, "Submit": the agent calls the program with the request details and its chosen mode.
2. Step 2, "Instant screening," happens synchronously in either mode and consists of the form validation described earlier.
3. At this same point, the digest is computed and checked against history: if already present, the process stops here and answers `already-checked-in` with the existing commit id, without doing further work.
4. A non-waiting caller receives `accepted` (with the digest) at this point; everything that follows runs identically regardless of which mode was chosen.
5. Step 3, "Build the candidate": the program constructs the candidate in its own private workspace directory (never in the agent's working directory), starting from main exactly at the declared base commit and applying exactly the declared changes.
6. Any files not part of the declared changes are taken from main's actual current content, never from the agent's own (possibly outdated) copies.
7. If an import was declared, it happens at this step: the content is copied from the legacy repository at the declared commit, and the source is recorded for later inclusion in the trailer.
8. Step 4, "Run the checks" (detailed in "Constructive guarantees"): checks are run against this candidate — the exact bytes that would become the new main.
9. Step 5, "Commit": a commit is created consisting of the message followed by the trailer lines.
10. Step 6, "Push": in the normal case, main hasn't moved since the base, so the push succeeds without complication; if main has moved, handling is described in "Concurrent check-ins."
11. Step 7, "Answer": a waiting caller now gets its response line; a non-waiting caller's outcome is now recorded in history where `status` can find it; the temporary workspace is deleted.
12. The requesting agent's own working copy is never modified by this process; it is up to the agent to refresh from main whenever it chooses.

# Constructive guarantees, the advisory, and the growth point

1. Most of the classic ways a change-control gate can fail are made impossible by how the system is built, rather than merely detected afterward.
2. Stray/unintended changes cannot enter, because the candidate is built strictly from the declaration — anything undeclared never reaches it.
3. The record cannot be missing, because the program writes the trailer lines itself.
4. The import record cannot lag behind, because it's written during candidate construction, landing in the same commit.
5. Duplicates cannot be applied, because the digest check runs at submission time.
6. There is exactly one advisory notice (explicitly not a refusal): if the agent's working directory has modified files beyond the declared ones, the reply includes a note ("worktree also differs at x, y; confirm intentional"), because the likely cause is a forgotten declaration.
7. Unrelated work-in-progress in the same working directory is considered legitimate, so this advisory never blocks the request.
8. In this first version, between the screening step and the push, no refusal can occur — this stretch consists only of deterministic construction and recording.
9. This absence of checks at that stage is intentional, a deliberate place for future growth rather than a gap: when a test suite exists, tests will run here; when the boss decides to gate some artifact class on review evidence, that check will run here too — and only then will the request format be expanded with an evidence field, not before.

# The trailer

(Trailer format block omitted — not prose.)

1. The trailer consists of exactly four factual items plus one pointer, and nothing more.
2. The agent trailer line (decision B6, ruled by the boss on 2026-07-31) records, exactly and literally, the runtime and model that produced the change, and it is never omitted; this is needed because the escalation process called the "fix ladder" needs to know which capability tier produced a given artifact, to know whether stronger models remain available.
3. The digest trailer line functions as the key for detecting duplicates, not as a record of authorship — it's what makes resubmission safe.
4. The issue value is deliberately written as `#<n>` because GitHub automatically shows any commit reaching the default branch with `#<n>` in its message on that issue's timeline — so an issue automatically accumulates all its check-ins without any custom tooling.
5. This same collection can also be obtained offline, without GitHub, via the given `git log --grep` command.
6. Refusals and other responses are never automatically posted as issue comments — routine/mechanical activity stays in transcripts; a genuinely blocking outcome instead earns a deliberately written comment from the requesting agent, per the convention that comments are reserved for genuinely new events.

# Concurrent check-ins

1. The whole mechanism for handling simultaneous check-ins rests on one guaranteed property of GitHub: a push either succeeds completely and cleanly, or is rejected entirely — never partially, never with content mixed together.
2. GitHub itself is the arbiter; when requests race, exactly one of them wins.
3. No request queue or locking mechanism is built; by default, check-ins are processed in parallel (a decision made by the boss).
4. The winning request simply completes the normal procedure, without ever being aware that a race occurred.
5. The losing request is handled by the program itself, not by the agent: the program fetches the new state of main and rebuilds its candidate by reapplying the declared changes on top of it.
6. In the usual "clean re-application" case, where the new commits touched different files, the program re-runs all checks against the rebuilt candidate (this version re-runs everything, since doing so is cheap while checks are fast) and pushes again; the reply notes it was "integrated over N newer commits."
7. In a genuine conflict, where the new commits touched the same content this request changes, the program cannot safely reapply automatically (doing so would require guessing intent, which it never does) — it refuses with `conflict`, naming the files, the intervening commits, and the next action: update from main, adjust, and resubmit (the adjusted work will digest freshly and correctly).
8. A request submitted from a working directory already behind main is handled by this same mechanism — being behind is treated simply as "main moved before the request even started."
9. There are two named limits: the retry loop is capped at five rounds, after which the request is refused with `main-moving-too-fast` rather than retrying indefinitely; and there is a deliberately accepted, documented gap — changes to different files that nonetheless interact semantically will currently pass through undetected until a real test suite becomes part of the checks.
10. There is a deferred optimization with a named trigger: once checks become slow (once a real test suite exists), re-validation will be narrowed to only the checks whose inputs are actually affected by what changed between bases (an approach called impact analysis), so that trivial movements of main's tip (like ledger updates or log-only commits) never force unnecessary re-validation — a decision made by the boss.
11. One step beyond that optimization would be a "merge queue" (batch-validating several queued requests against their combined projected result), to be implemented only if check-in volume ever grows enough to require it.

# States, crashes, cancel, and errors

1. The request passes through a defined sequence of states: SCREENING (synchronous, entirely in memory, nothing written to disk) → WORKING (the candidate is built and checked inside a specific workspace directory, located outside any repository and discoverable purely from the digest, holding the candidate clone, a worker-process-id file, and a resolved request record) → PUSHING (an atomic, retry-capped attempt) → ending in either CHECKED-IN or REFUSED.
2. Per decision B4c, every field derived from the calling environment (with "origin" as the primary example) is resolved once during screening into that record; the worker process later only reads this already-resolved record and never recalculates these values itself.
3. Once the process reaches either final state, its workspace is deleted, with one exception (decision B4d): if a non-waiting request is refused, its workspace is kept, holding only the JSON refusal record; the `status` command returns that record exactly once, then deletes the workspace.
4. There is one acknowledged, accepted edge case: if a caller crashes in the narrow window between the workspace being swept and the caller reading the result, it loses the refusal reason — this is described as rare and recoverable simply by resubmitting.
5. Regarding what durable traces remain: a checked-in request's lasting trace is its commit on main; a refused waiting request deliberately leaves no trace at all.
6. Crash recovery consists of one simple rule, not a multi-step procedure.
7. Across the entire pipeline, only two effects actually persist: the workspace directory and the atomic push.
8. Because of this, a crash or lost connection at any point leaves one of exactly two possible states: either the commit is on main, or it isn't and a stale workspace remains.
9. The way to recover from either situation is simply to resubmit.
10. Upon resubmission, the program checks whether the digest is already in history: if found, it answers `already-checked-in` with the commit id; if not found, any leftover stale workspace is cleaned up and the work is processed fresh.
11. There is no separate journal or dedicated repair mode.
12. The `status` command distinguishes an actively-working request (WORKING) from an abandoned one (workspace present but the worker process dead) by checking the recorded process id, so a worker that silently died is recognized as a specific, resubmittable state rather than appearing stuck showing "in-progress" forever.
13. The `cancel <digest>` command is already implemented in this first version — a decision by the boss, justified because the need for it arrives once checks become slow, the underlying machinery it needs already exists, and its implementation is only three logical branches.
14. Any agent may cancel any request — there is no permission system restricting this, relying instead on a cooperative model; the agents' training/workflow deliberately does not present cancel as a routine action, and being the original author of a request grants no special authority over the decision to cancel it (the author may no longer even be active).
15. There are exactly three possible outcomes for cancel: if the digest is already in history, the answer is `too-late — already-checked-in <commit>` (the correct remedy for a bad landed change is instead a revert — an ordinary check-in whose content undoes a previous one, through the same gate); if a live worker is found, it's killed, its workspace is swept, and the answer is `cancelled`; if neither is found, the answer is `unknown-request`.
16. A race between cancel and push is resolved by the push's atomicity: the worker is killed, then history is checked to determine whether the digest actually made it onto main.
17. Cancel is only meaningful before a check-in completes (a decision by the boss); afterward, the correct action is a revert instead.
18. Every possible ending is named, and refusals take the three-part teaching form.
19. This lists the "Form" category of errors — those detected instantly during initial screening validation.
20. This lists the "Integration" category of errors — those related to reconciling concurrent changes.
21. This lists the "Infrastructure" category of errors — related to authentication, network, or workspace I/O problems — and states that all of them are safe to resubmit.
22. This lists response values explicitly categorized as legitimate answers rather than actual errors.
23. The design claims to meet a stated standard for autonomous operation: every ending is named; every refusal teaches; resubmitting is always safe; and nothing in the system automatically escalates to the boss — any such escalation happens only through an agent's own judgment, never triggered mechanically by the code.

# The credential and enforcement

1. The step involving a dedicated identity (a separate account for this purpose) was adopted earlier than originally planned — a decision by the user on 2026-08-09, invoking a trigger condition named later in this section; the arrangement it replaces is documented first because that older arrangement remains the actual current state until this amendment is actually applied.
2. Branch protection has been active since 2026-07-21, restricting pushes to main to only the account `NedLern` (described as "the machine credential"), with the "enforce admins" setting on (administrators are not exempt), and with force-push and branch deletion both blocked.
3. The organization has two owner-level accounts, `NedLern` and `NedLerner` (the latter holding settings-management and emergency-recovery power but no push access), so that either account can recover the organization if the other is lost; any change to protection settings by either owner is described as a deliberate, visible action, never a standing/routine occurrence.
4. The boss never commits directly; any change originating from the boss is drafted together with an agent and goes through the same check-in process as any other change.
5. There is no cost to using GitHub Issues here: because the repository is public, opening issues or posting comments requires no special repository permission.
6. A decision made on 2026-08-09 (references C1/C3, requiring an org owner to actually apply it) moves the pushing role to a newly dedicated GitHub account — one with write-collaborator access to only this repository, not admin, never an org owner — and branch protection's push restriction will name only this account.
7. This dedicated-account approach was chosen over an alternative (a GitHub App or CI job) sketched earlier in this section, because that alternative would move the gatekeeping logic into CI, which this design explicitly excludes from its scope; a plain account instead keeps the gatekeeper a locally-run program.
8. If this dedicated account's token were stolen, the maximum possible damage would be limited to commits on this one repository, nothing beyond it.
9. Organization-owner-level authority remains solely with the human user; no agent is ever given that level of access.
10. This section, referenced as C2, is described as where the actual technical enforcement resides: GitHub's access restrictions apply at the account level, not the process level, and on a single machine, every process run by the same Unix user can read the same stored credential files.
11. Because of this, the credential capable of pushing to main is owned by a dedicated Unix user account, unreadable by agent sessions, and agents instead invoke the program through a `sudo` rule scoped precisely to that program.
12. This is the point at which "agents never push" becomes technically impossible rather than merely an instructed policy; it also means the gatekeeper functions as a callable service that any agent on that machine can invoke.
13. A decision referenced as C4 narrows agents' access tokens: each machine running an agent holds a fine-grained token limited to this one repository — with read/write access to file contents (pushing to non-main branches is open; only main is restricted by the no-direct-push rule) and write access to issues — never a classic all-repository token, and never the `workflow` permission scope (categorized under a broader concept called "capability-by-landing class," documented in issue #31).
14. Work involving issues is restricted only by limited permission scope, not funneled through a gatekeeping mechanism, because no strict rule equivalent to "only one writer to main" applies there — so good behavior around issues instead relies on the agent's trained skills and automated hook interception, not an enforced gate.
15. A further layer, referenced as C6 and called the "cooperative tier," sits above the hard technical boundary and is explicitly never meant to substitute for it: a "PreToolUse" hook automatically rewrites `gh` command calls into a more disciplined form, and an attempted raw `git push` toward this repository is instead denied, with the denial message including the exact correct command to use — because a raw push carries none of the required declared information, and automatically inferring that information on the agent's behalf would undermine the deliberate intentionality that the `unchanged-path` refusal exists to enforce.
16. A "check-in skill" prepares the declaration ahead of time — deriving `--files` from the agent's own staged files, computing `--base` as the git merge-base, and passing the message through unmodified — so the agent only needs to contribute what it would naturally already do through its training.
17. As the final layer, refusals from the gatekeeper itself serve a teaching/corrective function.
18. An emergency-access mechanism, referenced as C5 and called "break-glass," describes an unlockable credential meant only for emergencies, never a standing way for an agent to bypass the gate: if the gatekeeper program itself has a defect, recovery relies on its own git history, since the program is deliberately kept as one file using only Python's standard library, specifically so any past version can be run directly; if the gate wrongly refuses a change that should land, recovery uses a `sudoers` entry requiring the user's password, approved in the moment; credential expiration and protection misconfiguration are handled solely by the organization owner — the human user alone.
19. A rule referenced as C7 states that the `--repo` and `--remote` options exist so tests can point the program at disposable test repositories.
20. When invoked by the account holding the real push credential, these override options are refused and the program is instead pinned to the actual canonical repository; tests must therefore run under a non-privileged account to make use of these testing seams.
21. An honest acknowledgment, ruled by the boss and true only until C2 is installed, states that branch protection restricts the account, not the process — meaning anything running under that account, on any machine, can currently push.
22. No locking mechanism is needed to order concurrent pushes, because the atomicity of pushes already resolves any such conflicts.
23. Until C2 is installed, the only thing preventing agents from pushing directly is procedural expectation — that agents use the program instead of a raw `git push` — not yet a technical impossibility.
24. It is a decision by the boss that CLAUDE.md files serve purely as documentation, never as enforcement — his stated reasoning being that a Python script doesn't read them, and different machines may hold different copies.
25. The same limitation applies to harness hooks: they only configure a particular agent-running harness, and only harnesses that choose to respect them are actually affected — which is why the cooperative tier (C6) is only a convenience, while the Unix-user boundary (C2) is the real enforcement boundary.
26. This design's actual guarantees do not depend on either CLAUDE.md or harness hooks being respected.
27. The residual risk of a raw, bypassing push is detected rather than prevented: a recurring audit run at each handoff scrub scans main for commits lacking valid trailers and files a draft issue naming them, with exactly three possible outcomes — `protection-ok`, `protection-wrong` (with the differing settings named), or `audit-failed` (e.g., `gh` missing, unauthenticated, or an API error) — and this audit is designed (per reference B3c) to fail loudly as its own distinct outcome rather than silently appearing to pass when something went wrong.
28. This audit currently also covers a related, temporary risk: an agent holding owner-level credentials could deliberately alter protection settings — the same cooperative-trust category, caught by the same mechanism; this risk category will be eliminated entirely once C3 (moving away from owner-level agent access) is implemented.

# Deliberately not in version 1

1. A review-evidence field and check were cut because no artifact class currently requires gating; this would return once the boss decides to gate some specific class.
2. A naming-hygiene check was cut because the set of recognized subsystem names is currently empty, making such a check pure noise at this early stage; it would return once a real set of subsystems exists.
3. The rule requiring an appended row in an entry-manifest file was cut because it duplicates the trailer, and because a single shared append-target file would make any two parallel imports always conflict; this will never return, since the `imports` query now serves as that view.
4. A separate audit log was cut because transcripts plus git history already record everything needed; this will never return, since `status` derives what it needs from history.
5. Caller-generated request ids were cut because the automatically computed content digest already serves that purpose safely for retries; this will never return.
6. Narrowing re-validation to only affected checks ("footprint-scoped") was cut because checks currently run fast, making a full re-run cheaper than building that machinery; this returns once checks become slow, such as when a real test suite exists.
7. A merge queue was cut because current volume is nowhere near requiring one; it would return if there were sustained, ongoing contention regularly hitting the retry cap.
8. A dedicated gatekeeper identity, shown struck through, had originally been cut on the reasoning that with only two agents sharing one machine, the resulting procedural gap could be caught by audit instead of prevented; that reasoning is now superseded, since the feature was actually adopted on 2026-08-09, earlier than planned, via what's called the "boss-admits-it-early trigger," detailed in "The credential and enforcement."

# Cross-spec consequence, awaiting the boss

1. This particular open question was originally resolved on 2026-07-24, then superseded on 2026-08-02 by a revision (concerning "session recycling") to the separate document fast-handoff-design.md: under that revision, handoffs occurring as part of session recycling stay local to the machine and are never checked in through the gatekeeper, with the sole exception being the original founding handoff, which was committed as an ordinary file.
2. The principle that files should be written to disk before other steps happen continues to apply, now specifically within the context of the supervisor's recurring cycle.

# Relationship to the legacy design

1. A prior document from an older, legacy system, `git-clean-slate-plan.md` (treated as a read-only reference at the stated path), addressed an earlier version of this same problem, but designed for a scenario with many different writers/pushers.
2. This design retains only two ideas from that legacy design, though independently reworked rather than copied directly: expressing workflow rules as CLAUDE.md documentation, and using branch protection as a lock, simplified down to a single credential.
3. Several legacy-design elements were never adopted here: three separate GitHub App integrations, a credential-helper mechanism, giving each agent its own branch, the pull-request pipeline for ordinary changes, and a set of "parking states."
4. The repository's git configuration is kept minimal and is defined directly in this document rather than carried over from the legacy system: `user.name`/`user.email` set the machine's identity, and `useConfigOnly` prevents any broader/global git identity on the machine from inadvertently applying to this repository.

# Build slice (choirmaster task 1)

1. This describes a planned unit of work, "choirmaster task 1," combining: the git configuration described above; the `git-gatekeeper.py` program supporting the `check-in`, `status`, `cancel`, and `imports` commands; the corresponding CLAUDE.md workflow lines; and an accompanying test suite.
2. T1 verifies that every form-validation error results in a refusal with the correct named error and no side effects.
3. T2 verifies the normal successful path: that all four success guarantees actually hold, and that the resulting trailer is exactly correct.
4. T3 verifies digest behavior: identical resubmission answers `already-checked-in`; changed content produces a fresh digest; metadata-only changes leave the digest unchanged.
5. T4 verifies concurrent submissions using an artificially injected delay: the winning request completes cleanly, and the losing request successfully integrates over the newer commits and still succeeds.
6. T5 verifies that a same-content collision is refused with the conflicting files, the intervening commits, and the next action included.
7. T6 verifies that sustained, continuous movement of main during retries eventually ends in `main-moving-too-fast` rather than retrying indefinitely.
8. T7 verifies crash recovery in two scenarios: killing the worker mid-WORKING makes `status` report `abandoned`, and resubmitting cleans up and completes the work; killing the worker after the push means resubmitting answers `already-checked-in`.
9. T8 verifies all three possible cancel outcomes, specifically confirming that canceling after the push already happened answers `too-late`.
10. T9 verifies that undeclared working-directory changes are noted in the advisory but never block the request.
11. T10 verifies that the `imports` command correctly derives the expected table from the trailer lines in history.
12. T11 verifies that each distinct class of import-related error results in the correct refusal.
13. T12 verifies that a simulated raw, direct push (bypassing the gatekeeper) is caught by the audit that checks for commits missing valid trailers.

# Open

1. This item, still open, concerns which artifact classes, if any, should require gated review evidence from the very start; the first such class has now been designated by the boss on 2026-08-04: instruction-bearing text (CLAUDE.md files, skills and their prompt templates, injected system prompts, the wiki), whose check-ins will require evidence that the change was reviewed step-by-step and approved; the precise class definition, procedure, and safeguards are documented in issue #31.
2. The actual validation check for this requirement will itself be built as part of the gatekeeper, corresponding to slice 6 of the build order, which remains unscheduled until the format for representing approval evidence has been defined.
3. This item, referenced as C8, concerns callers on different machines than the gatekeeper: since the gatekeeper reads declared content directly from the caller's own working directory, this requires a shared filesystem, and as things stand, agents running on a Mac cannot have their files read by the gatekeeper running on the Ubuntu machine.
4. Several possible solutions to this problem have been considered but none chosen: having the caller push its branch and having the request reference that branch/commit instead of relying on shared working-directory bytes (a substantial change to the request format); routing Mac-based agents' work through the Ubuntu side instead; or setting up a second machine holding a valid credential (though this would weaken the single-location property established by C2); the choice will be made once a Mac-based agent first actually needs to perform a direct check-in.
5. This item, marked resolved, concerns an interaction with something called "the fast-handoff S2," whose resolution is documented in the "Cross-spec consequence, awaiting the boss" section.

