<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=docs/cross-project/git-gatekeeper-design.md -->

## YAML frontmatter

1. The document’s status is “specification,” with only part of the specified system implemented; the Implementation status passage gives the details.

## git-gatekeeper (specification)

1. Branch protection and the account arrangement are already active as of July 21, 2026, while an account-layout amendment decided on August 9 remains unapplied.
2. The document says `scripts/git-gatekeeper.py` has been built through the first three of five planned slices, plus slice 6’s review-evidence check, which was scheduled for August 10 as a prerequisite for activating the privileged path; the synchronous check-in flow, entry checkpoint, and concurrent-check-in handling operate now, while an `imports` table command built in slice 2 was later deleted in favor of reading trailers with `git log --grep`, and the remaining behavior has been exercised by 140 tests in disposable repositories, down from 146 after tests for `--base` and `imports` queries were removed and assertions concerning “fact fragments” were added, although that last expression is not defined here beyond naming something the tests assert.
3. Slices 4, covering worker lifecycle features such as `--no-wait`, `status`, and `cancel`, and 5, covering the branch-protection audit, repository Git configuration, and workflow instructions in CLAUDE.md, exist only as contractual specifications; asking for an unimplemented part must produce the named refusal `unbuilt-option`, not crash the program.
4. The gate is inactive because no machine currently has the main-capable credential that the design requires.
5. The August 9 revision incorporates two amendments left pending by the July 30 “bindings walk”—an apparently formal review or decision process whose mechanics are not defined here—under which a refused `--no-wait` request keeps a JSON refusal record and `status` returns that record once before deleting it, and the branch-protection audit has three specifically named outcomes; it also incorporates the `Gatekeeper-agent` trailer and eight credential decisions labeled C1 through C8, whose separate amendment document was retired once this specification became their sole authoritative statement, while their decision history remains available in Git history and `md-review-records/`.
6. The core design reviewed with the boss on July 24—requests, replies, digests, trailers, concurrency, states, and errors—was not changed by those amendments.
7. The same earlier designs remain superseded: the two-stage promotion-relay design that sent changes through a relay branch before main was replaced by this single gate, the rule requiring a row to be appended to an entry manifest was replaced, and the terms “land” and “landing” were retired in favor of “check in.”
8. Labels B1, B3c, B4a through B4d, and B6 refer to rulings from the July 30 bindings walk recorded in `docs/issues/queue/3-gatekeeper-build-bindings.md`.
9. “The boss” and “the user” both mean the project’s human owner throughout this document.
10. The document specifies how a change is put onto the `main` branch in the `nedschorus` project.
11. Its scope stops once a change reaches `main`: deployment from `main` to production is a separate CI or DevOps problem to be designed after the project has its first long-running process, and although `main` happens to function as production until then, this design does not establish that relationship.
12. Normal changes do not use branches or pull requests.

## The job and the guarantee

1. The only authorized route by which a change may reach `main` is the program `scripts/git-gatekeeper.py`.
2. Under the contract, that program holds the project’s sole credential capable of pushing to `main`, although the credential does not yet exist and the gate therefore remains inactive.
3. Every agent invokes the program itself and never pushes directly to `main`, while its scoped credentials may still push branches other than `main`.
4. The design intentionally has one program, one main-capable credential, and one route into `main`.
5. No agent acts as a gatekeeper, doorman, or relay for another agent’s check-in, and choirmaster differs only by being the most frequent caller.
6. For every check-in request, the program either checks in the work or refuses it and explains how to correct the request.
7. The `status` and `cancel` subcommands are informational operations that answer questions rather than checking in work.
8. A successful check-in carries four guarantees.
9. The change exists on `main` and has been pushed to GitHub.
10. The checks were run against exactly the content that was ultimately pushed.
11. The commit trailers contain the complete machine-readable record defined by this design.
12. The requester receives a success result and commit identifier immediately when waiting, or receives the same result later through `status` when using non-waiting mode.
13. Every refusal contains the fixed catalog’s named error, concrete facts identifying such things as the affected file, failed check, or mismatch, and a precise next action phrased so an agent can perform it, resembling the structured error style expected from a well-made MCP tool.
14. A refusal does not modify the repository, except that a refused `--no-wait` request temporarily leaves a JSON refusal record in its private workspace until that record is read or expires.
15. The only durable records are Git history and the normal transcript of the session that invoked the program.
16. The gatekeeper creates no sidecar record files or separate logs because its ordinary tool invocation is already captured wherever tool calls are recorded.
17. The temporary refusal record for a `--no-wait` request is not considered durable because it survives only until collection or cleanup.
18. Repeating a submission is always intended to be safe.
19. An identical request receives the same answer, a corrected request produces a different digest and is processed as new work, and a request for work that has already passed through the gate receives `already-checked-in <commit>`.
20. If an agent crashes or loses its connection, it should not try to infer the previous outcome; it submits the request again and lets the program determine what happened.
21. Because refusals explain corrections and retries are safe and cost nothing logically, the request-and-retry loop is intended to recover by itself, which the document identifies as necessary for nearly perfect autonomous operation.

## The request and the reply

1. Every field is subject to the exact validation described below, and this entire form-validation stage completes immediately and synchronously in both waiting and non-waiting modes, with every refusal naming both the error and its correction.
2. `--files` must contain at least one unique, repository-relative, normalized path, with no absolute paths, parent-directory traversal using `..`, or paths beneath `.git/`.
3. For each declared path, the program reads the new bytes from the calling agent’s working copy, and this is its only byte-level content read from that worktree; the advisory check reads only changed path names reported by Git status.
4. The program classifies each path as added if it is absent at the base but present in the worktree, modified if its bytes differ, or deleted if it is present at the base but absent from the worktree.
5. A path that exists neither at the base nor in the worktree produces `unknown-path`, while a declared path identical to its base version produces `unchanged-path`, and an empty or structurally malformed file list produces `malformed-field`.
6. A separate `empty-change` error was removed as unreachable because the first unchanged declared path would already cause `unchanged-path` before an aggregate empty-change test could execute.
7. The current comparison deliberately ignores executable-mode changes, so changing only the executable bit without changing file bytes is treated as `unchanged-path`.
8. The document considers this harmless for now because every project script is invoked as `python3 <path>` and nothing depends on its executable bit, while a change that modifies both bytes and mode carries the mode change with it.
9. File-mode awareness is to be added only when an actual need for it arises.
10. `--message` supplies the human-readable explanation of what changed and why, and its value becomes the commit-message body above the trailers.
11. The message is mandatory and nonempty, with absence or emptiness reported as `malformed-field` and the facts identifying the message field; a separate `missing-message` error was removed for consistency with other empty fields.
12. The author must supply the intent expressed by the message because the program cannot safely generate it.
13. “The base” means the exact commit on `main` from which the submitted work began.
14. Rather than accepting a caller-provided `--base`, the program fetches and then runs `git merge-base HEAD origin/main` in the same checkout from which it reads the declared content, which is intended to calculate the fork point deterministically without a relay or dependence on the cooperative hook layer.
15. The computed base is necessarily an actual commit on `main`.
16. One accepted weakness is that a caller that refreshed from `main` partway through its task may present a fork point newer than the true starting point and thereby weaken conflict detection, and the document says the previous design had the same weakness because its wrapper inferred the base from the same repository state.
17. `--import` must be either the explicit value `none` or a complete triple consisting of a legacy commit identifier, a source path that exists in the legacy repository at that exact commit, and a destination path included in `--files`.
18. An incomplete triple, absent source, undeclared destination, or unreadable legacy checkout produces the single error `import-invalid`, whose facts and next-action fields must explain the particular defect; four former error names were merged because nothing branches programmatically on refusal names and the teaching text preserves the distinctions.
19. The request format cannot represent two imports because a second import must be submitted as a separate check-in.
20. The caller must explicitly choose an import policy, so combining `--import none` with any import-triple component or omitting `--import` entirely produces `import-invalid`.
21. `--issue` accepts either `none` or a positive integer.
22. Version 1 checks only the field’s syntax.
23. The project’s upstream artifact-lifecycle rule, rather than the gatekeeper, determines which bodies of work should have issues and when, at whatever granularity that rule considers appropriate.
24. The gatekeeper merely records the upstream decision about the issue.
25. `none` is valid for trivial work because the design does not require every invocation to have an issue, and issues represent desired work rather than serving as invocation logs.
26. `--agent` is a required, nonempty identifier for the runtime and model that produced the change, such as `claude-code/opus-5`, with absence or emptiness reported as `malformed-field`.
27. The caller supplies this value because the environment identifies the runtime but not necessarily the model, and the model is needed by the “fix ladder”—the project’s escalation sequence of retrying, trying a stronger model, and then involving the boss—so Git history can show what last produced the work.
28. The agent identifier belongs to the cooperative trust class: the program records the caller’s declaration without verifying or inferring it.
29. The origin is filled from the session environment automatically, and if no origin is available the program records `none` without refusing the request.
30. Origin is useful because agents have long-lived sessions and a session identifier can point to a readable transcript explaining the work’s intent.
31. The digest is a SHA-256 hash over the base commit, the sorted declared-path list, every declared path’s new bytes with deletions represented by a marker, and the import triple.
32. The message, issue, waiting mode, origin, agent identity, and time are intentionally excluded because the digest identifies the submitted work itself, allowing the same work with different metadata to deduplicate.
33. The implemented serialization places NUL-delimited field tags between components so distinct requests cannot become indistinguishable merely because their concatenated values happen to form the same byte sequence.
34. The program computes the digest and callers do not generate any part of it.
35. Deduplication is limited to byte-for-byte resubmission of the same work against the same base.
36. Rebuilding a request after updating from `main` produces a new digest, and if the work was already checked in, its declared paths then match `main` and the program responds `unchanged-path`.
37. The document accepts this result because it expects the relevant situations—such as an inaccurate handoff to a successor session or independently duplicated work—to be uncommon, and the refusal already states the fact that matters operationally.
38. Every invocation writes exactly one JSON object to standard output with the fields `{outcome, error?, facts?, next_action?, commit?, digest?, integrated_over?, advisory?, summary}`, where `summary` is the sole human-readable response line rather than a separate response format.
39. Optional fields are included only when applicable, with `integrated_over` currently emitted after a losing race is integrated successfully and `advisory` currently emitted when undeclared worktree differences exist.
40. Exit status 0 means success or an informational answer, status 1 means an expected catalog refusal showing the gatekeeper is functioning, and status 2 means a program defect, allowing automation and audits to distinguish a bug from a valid refusal.
41. A successful waiting request returns `checked-in <commit-id>` with exit status 0, and if it lost a race but integrated successfully, the JSON also contains `integrated_over: <n>`.
42. A valid non-waiting request immediately returns `accepted <digest>`, and its `next_action` directs the caller to retrieve the eventual result with `status <digest>`.
43. Every refusal uses the three-part teaching response and exits with status 1.
44. `status <digest>` derives an answer from Git history and the gatekeeper workspace and may return `checked-in <commit>`, `in-progress`, `abandoned` for a workspace whose worker has died, one retained three-part refusal exactly once before deleting it, or `unknown` with the instruction that submitting is safe because no trace was found.
45. The behavior of `cancel <digest>` is defined in the later section on states, crashes, cancellation, and errors.
46. The one-word subcommands `status` and `cancel` are explicitly exempted from the project rule that names normally contain multiple parts.
47. Because a subcommand is always invoked beneath the program name, the searchable name remains `git-gatekeeper` for every invocation.
48. The naming rule is meant to prevent searches from failing to find a thing, which cannot happen here, so renaming the already-tested commands would break alignment with the test suite without improving searchability.
49. The import history is read directly from commit trailers, and `git log origin/main --grep "Gatekeeper-import:"` lists what was imported, its legacy commit and source, its destination, and when the import occurred.
50. A slice-2 `imports` subcommand that formatted those records as a table was deleted because the trailer already constitutes the record, the Git command already provides a view, and making a temporary clone for every query added no guarantee.
51. The import trailer replaces the retired requirement to add an entry-manifest row, while `entry-manifest.md` remains only as a historical artifact from the project’s founding period.

## The procedure

1. The first step is for an agent to call the program with its request and choice of waiting or non-waiting mode.
2. The second step performs immediate screening synchronously in either mode.
3. That screening validates the form according to the earlier rules.
4. It also computes the digest and searches history immediately, returning `already-checked-in <commit>` without doing further work if the digest is already present.
5. A non-waiting caller receives `accepted <digest>` at that point, after which the remaining processing is identical to waiting mode.
6. “Instant” means the caller waits synchronously for only a few seconds, not that the operation performs no I/O, because the current program creates the workspace clone during screening.
7. The third step builds a candidate in a private directory named `<workspace-root>/<digest>/`, never in the agent’s worktree, by starting with `main` at the computed base and applying exactly the declared changes.
8. Files not declared by the request are taken from `main`, not from potentially stale versions in the agent’s checkout.
9. If the request declares an import, the program copies the source from the specified legacy commit during candidate construction and retains its source information for the trailer.
10. The fourth step runs the checks defined under Constructive guarantees against the exact candidate bytes that would be placed on `main`.
11. The fifth step creates a commit containing the message followed by the required trailer lines.
12. The sixth step attempts to push the commit.
13. If `main` has not changed since the base, that push succeeds normally.
14. If `main` has changed, the program follows the concurrent-check-in procedure.
15. The seventh step returns the result directly to a waiting caller, while the result of a non-waiting request becomes discoverable in history through `status`.
16. The workspace is then deleted, except that a refused non-waiting request temporarily retains only its refusal record until `status` reads it or it expires.
17. The gatekeeper never changes the requester’s own working copy, leaving the agent free to update it from `main` whenever convenient.

## Constructive guarantees, the advisory, and the growth point

1. The design prevents most traditional gate failures through the way it constructs candidates rather than by detecting those failures afterward.
2. Undeclared changes cannot enter the candidate at path granularity because the candidate is assembled from the declared paths, but every byte present in a declared file is treated as part of that declaration, so an unintended edit inside a declared file is included and the guarantee does not distinguish individual edits within a file.
3. The machine-readable record cannot be omitted because the program itself writes the trailers.
4. The import record cannot fall behind the imported content because both are produced during construction of the same commit.
5. Duplicate submissions cannot be applied twice because the digest is checked when the request is submitted.
6. If Git reports modified worktree files beyond those declared, the response includes an advisory such as “worktree also differs at `x`, `y`; confirm intentional,” because an omitted declaration is considered the most likely explanation.
7. Because unrelated work in the same checkout may be legitimate, this advisory never causes a refusal.
8. After screening and before pushing in version 1, no refusal requiring human or agent judgment remains; only deterministic construction and recording occur there, although failures such as `workspace-io-error` and `network-down` can still occur and may safely be resubmitted.
9. Version 1 treats construction itself as the entire check set, so the guarantee that checks run against the pushed bytes currently means the candidate-construction operation is bound to those exact bytes, and the check set acquires more substantive content as actual checks are added.
10. The document calls this an intended extension point rather than a missing guarantee: a future test suite will run at this point, and when the boss requires review evidence for an artifact class, its evidence check will also run here, with the request format gaining an evidence field only then.

## The trailer

1. The five trailer lines represent what the document characterizes as four facts plus one pointer, with no additional machine-readable record.
2. `Gatekeeper-agent`, added by ruling B6, records the literal runtime-and-model identifier and can never be omitted, because the escalation ladder needs to know which model tier produced an artifact and whether a stronger tier remains available.
3. `Gatekeeper-digest` is the key used to detect duplicate work and make retries safe, rather than a statement of the work’s provenance or history.
4. `Gatekeeper-issue` deliberately formats an issue as `#<n>` because GitHub automatically places default-branch commits containing that form in the referenced issue’s timeline, allowing an issue to collect its related check-ins without additional software.
5. The same grouping can be reproduced offline with the anchored search `git log --grep "Gatekeeper-issue: #<n>$"`, whose end anchor prevents an issue such as `#1` from also matching `#10`.
6. Refusals and other program replies are never posted automatically to issues because routine machine output belongs in transcripts, while a genuinely blocking result may receive a manually judged comment from the requesting agent under the project convention that comments represent genuinely new events.

## Concurrent check-ins

1. The concurrency design relies on GitHub accepting a push in full or rejecting it in full, with no partial or interleaved push result.
2. GitHub decides which request wins a race, and exactly one request wins each race.
3. The program uses neither a queue nor a lock, so independent check-ins run concurrently by default.
4. The winning request completes the normal procedure without needing to know that a race occurred.
5. For a losing request, the program—not the agent—fetches the new `main` and first searches the new tip for the request’s digest; if the winning request was another submission of the same work, it returns `already-checked-in <commit>` without rebuilding, which is the implemented behavior.
6. If the digest is not found, the program rebuilds the candidate by applying the declared changes to the new `main`.
7. If reapplication is clean, ordinarily because different paths changed, the program reruns every check against the rebuilt candidate in version 1, retries the push, and reports that it integrated over a stated number of newer commits.
8. If new `main` changed any path also changed by the request, the current file-granularity implementation treats that as a real conflict rather than risking a lost update within the file, refuses with `conflict`, identifies the affected files and intervening commits, and instructs the caller to update from `main`, adjust the work, and resubmit it under a new digest.
9. A request created from a checkout already behind `main` uses the same mechanism because it is equivalent to `main` having moved before processing began.
10. The retry loop stops after five rounds with `main-moving-too-fast` instead of spinning forever, while the explicitly accepted limitation is that changes to different files may interact semantically without detection until tests capable of detecting that interaction become part of the checks.
11. When checks become materially slow, revalidation is intended to use impact analysis and rerun only checks whose inputs overlap the changes between bases, so unrelated head movement such as ledger or log commits does not invalidate pending work; if contention later becomes high enough, the next optimization would be a merge queue that validates batches against their predicted combined result.

## States, crashes, cancel, and errors

1. A request moves from SCREENING, which is synchronous, memory-only, and leaves nothing on disk, to WORKING in `<workspace-root>/<digest>/`, concretely under `$XDG_STATE_HOME/nedschorus-gatekeeper/<digest>/` or the default `~/.local/state/...`, and after the dedicated Unix-user boundary is installed this resolves under that user’s home at `/home/nedschorus-gatekeeper/.local/state/nedschorus-gatekeeper/<digest>/`; this directory is outside every repository, can be found from the digest alone, and contains the candidate clone, `worker.pid`, and a resolved request record whose environment-derived values—including origin—were fixed during screening so the worker only reads them, after which the request enters PUSHING for an atomic, retry-limited push and ends as CHECKED-IN or REFUSED.
2. After either terminal state, the workspace is deleted, except that a refused `--no-wait` request retains only its JSON refusal record until `status` returns it once and then deletes it.
3. Every gatekeeper invocation opportunistically deletes refusal records older than 30 days, using no daemon, and a caller whose record has expired recovers by resubmitting just as it would after losing any other refusal reason.
4. One accepted edge case is that a caller that crashes after the old record is swept but before reading it loses the explanation, which remains recoverable by resubmission.
5. A successful request leaves its commit on `main` as its durable trace, while a refused waiting request intentionally leaves no durable trace.
6. Crash recovery is defined as one rule rather than a separate repair procedure.
7. The pipeline has only two durable effects: creation of its workspace and an atomic push.
8. Therefore, after any crash or lost connection, either the commit is already on `main`, or the commit is absent and a stale workspace remains.
9. Recovery consists of resubmitting the request.
10. On resubmission, the program searches history for the digest and returns `already-checked-in <commit>` if found; otherwise it removes the leftover workspace and runs the work again from the beginning.
11. The design has no journal and no special repair mode.
12. Using the recorded process identifier, `status` distinguishes a currently WORKING request from `abandoned`, meaning its workspace exists but its worker has died, so a silently dead worker does not remain reported as perpetually in progress and can be safely resubmitted.
13. The design accepts that a recycled process identifier might appear to identify a live worker and that a process-id check has no meaning across machines, so slice 4 records and verifies the worker’s start time as well as its identifier.
14. `cancel <digest>` belongs to version 1 because the boss ruled that cancellation becomes necessary when checks become slow and requires only machinery the design already needs.
15. Any agent may cancel because the cooperative model includes no permission system, but the workflow does not present cancellation as a routine action, and the original author receives no special authority because that author may no longer be present.
16. Cancellation has exactly four defined outcomes: a digest already in history returns `too-late — already-checked-in <commit>` and a bad committed change must instead be undone by an ordinary gatekeeper check-in called a revert; a live worker is killed, its workspace deleted, and `cancelled` returned; a workspace with no live worker, including either an abandoned run or retained refusal record, is deleted and `cancelled` returned; and an absent digest and workspace produce `unknown-request`.
17. A cancellation racing with a push kills the worker and then checks history to determine whether the atomic push had already committed the digest.
18. Cancellation applies only before check-in completes; afterward, the correction mechanism is a revert.
19. Every terminal error belongs to a fixed catalog and uses the three-part teaching response.
20. Immediate form errors are `malformed-field` for a named missing, empty, or malformed field, `unknown-path`, `unchanged-path`, and `import-invalid` for any specifically identified import defect; the former `missing-message` and unreachable `empty-change` errors were folded into `malformed-field`, four import errors were merged, and the caller-base errors `unknown-base` and `base-not-on-main` disappeared when the program began computing the base itself.
21. Integration errors are `conflict` and `main-moving-too-fast`.
22. Infrastructure errors are `push-auth-failed`, `network-down`, and `workspace-io-error`, all of which may safely be retried, although the caller must use judgment to make retries bounded and back them off because the gatekeeper never recommends infinite resubmission.
23. `unbuilt-option` means the caller reached a slice-4 or slice-5 interface that has been specified but not implemented, and the prescribed response is to omit that option or retry after the relevant slice ships.
24. The non-error answers are `checked-in <commit>`, `already-checked-in <commit>`, `accepted <digest>`, `in-progress`, `abandoned`, `unknown`, `cancelled`, `too-late`, and `unknown-request`.
25. The claimed autonomy standard is that every ending has a name, every refusal explains the correction, resubmission is always safe, and the mechanism never automatically escalates to the boss, whom agents involve only through judgment.

## The credential and enforcement

1. The project owner approved the dedicated-identity layer earlier than the original trigger required, but the document first describes the arrangement it replaces because that older arrangement remains active until the amendment is implemented.
2. Since July 21, 2026, live branch protection has restricted pushes to `main` to the `NedLern` machine credential, enabled enforcement for administrators, and prohibited force-pushes and branch deletion.
3. The organization has two owners, `NedLern` and `NedLerner`, with the latter assigned settings and emergency authority but no pushing role, so either can recover the organization if the other is lost; because the first name is a proper prefix of the second, searches must match complete names rather than substrings, and any owner’s modification of protection is treated as an intentional and visible act rather than an ordinary route into `main`.
4. The boss does not commit directly, so work originating with the boss is drafted through an agent and submitted through the same gate.
5. Because the repository is public, issue operations require no repository-specific grant beyond an authenticated GitHub account, although agent tokens still include `issues:write` for issue-related automation.
6. Under the approved C1/C3 amendment, the pushing role moves to a dedicated GitHub account that is a non-admin, non-owner collaborator with write access only to this repository, and branch protection will name only that account; the account’s literal name is to be inserted into the document when the amendment is applied.
7. This account-based arrangement was chosen instead of a GitHub App or CI job because an App or CI implementation would move the gate into CI, which lies outside this design’s scope, whereas a normal account allows the gate to remain a local program.
8. If the dedicated token is stolen, the intended maximum damage is unauthorized commits to this single repository.
9. Organization-owner authority remains with the human user, and the C3 target state is that no agent ever possesses it once the amendment is applied; until then, `NedLern` remains both owner and pusher as the explicitly recorded live-state exception.
10. The Unix-user boundary is where process-level enforcement resides because GitHub distinguishes accounts rather than local processes and every process running as the same Unix user can ordinarily read that user’s credential files.
11. Consequently, the main-capable credential is owned by a dedicated Unix user whose files agent sessions cannot read, and agents reach the gatekeeper only through a sudoers rule limited to that program.
12. Installing this boundary turns the rule that agents do not push into a technical impossibility rather than merely an instruction, while also making the gatekeeper an invocable service available to every agent on the machine.
13. The sudoers entry refers to a root-owned copy of the program outside all checkouts because pointing it into an agent-writable checkout would give elevated execution to whichever program bytes an agent most recently wrote there.
14. The privileged copy updates itself automatically from `main`, without a remembered manual deployment step, and this is considered safe because changes to the gatekeeper source belong to the class of instruction-bearing files that may reach `main` only with walked-approval evidence enforced by slice 6.
15. The privileged path must therefore remain inactive until slice 6 exists.
16. The designated installed path is `/usr/local/lib/nedschorus-gatekeeper/git-gatekeeper.py`.
17. An outdated deployed copy is considered fail-safe because it continues enforcing the older contract and cannot be redirected to agent-written bytes; the ownership boundary, rather than immediate freshness, provides security, so failed self-updating may prevent service but is not supposed to weaken enforcement.
18. The project-wide rule inferred from this arrangement is that deployed copies update themselves automatically from their authoritative source instead of depending on someone to remember a deployment step.
19. Every agent host has a fine-grained token limited to this repository, with content read/write access for non-`main` branch pushes and issue-write access, but never a classic token covering all repositories or the `workflow` scope associated with the referenced “capability-by-landing” class in issue 31.
20. Issue modifications are scoped by credentials but do not pass through a single-writer gate, because no issue-writing invariant analogous to the single writer for `main` exists, leaving issue discipline to skills and hooks.
21. The cooperative tier, which supplements but cannot replace the Unix-user boundary, uses a PreToolUse hook to transparently route `gh` calls through the project wrapper with the same arguments, while denying `git push` operations aimed at this repository and returning a check-in-command template whose file list comes from the agent’s staging area but whose message is deliberately left for the author; it does not generate a fully executable command because a raw push lacks the gatekeeper declaration and deriving all declaration fields automatically would undermine the intentional declaration that `unchanged-path` is meant to enforce.
22. The check-in skill presents the declaration before execution by taking `--files` from the agent’s staging area and passing the authored message unchanged, while the program computes the base itself, so agents need supply only information they are already trained to provide.
23. The last cooperative layer is that refusals explain how to correct the request.
24. Break-glass recovery provides a credential that can be unlocked for a specific event rather than leaving an agent permanently ungated: historical versions of the gatekeeper remain directly executable because it is intentionally one standard-library-only file, a work item wrongly refused by the normal gate may use a sudoers entry requiring the user’s password and immediate approval, and expired credentials or incorrect protection settings can be handled only by the human organization owner.
25. The testing options `--repo` and `--remote` do not need special privileged-mode restrictions because they accept disposable repositories and behave the same for all operating-system users.
26. The earlier proposed restrictions provided no actual protection because a foreign remote cannot authenticate with a token scoped to only this repository, while denying `--repo` would merely let the caller choose the same target through its working directory.
27. A hard-coded remote restriction was considered as protection against possible future credential misconfiguration but rejected because the token scope, configured once by the user, is intended to provide that defense.
28. Until C2 is installed, branch protection honestly guarantees only that the permitted GitHub account may push, not that a particular local process does so, meaning any process using that account on any machine can push.
29. No local lock is required to order processes because atomic pushes decide races.
30. Before C2, the remaining procedural requirement is simply that agents call the gatekeeper rather than invoking raw `git push`.
31. CLAUDE.md provides documentation and cannot enforce this design because the Python program does not read it and different machines may have different CLAUDE.md copies.
32. Harness hooks likewise configure only harnesses that choose to read them, which is why C6 is a convenience layer and C2 supplies the actual security boundary.
33. None of the design’s stated guarantees depends on CLAUDE.md or hooks, although those conveniences and their reduction in token usage do depend on them.
34. Before the stronger boundary exists, a raw-push risk is detected where its configuration originates rather than prevented: every session’s handoff scrub—the cleanup performed when handing work to another session—audits live branch-protection settings and returns exactly `protection-ok`, `protection-wrong` with the differing settings named, or `audit-failed` for a missing or unauthenticated `gh` client or API error, making inability to audit an explicit failure rather than silently treating it as success.
35. While agents still possess an owner credential, the same audit also detects the related possibility that an agent deliberately altered branch protection, and C3 removes that entire possibility by taking owner authority away from agents.
36. A second proposed detector that scanned `main` for commits without trailers and filed draft issues was removed because, after C2 and C3, such a commit could come only from a password-approved break-glass event or a protection failure already detected at the configuration level, and a detector whose findings are consumed by no subsequent mechanism was judged to create record-keeping cost without useful effect.

## Deliberately not in version 1

1. The review-evidence field and check were initially omitted because no artifact class required such approval at the project’s founding, but instruction-bearing text became the first designated class on August 4, and the feature returns in slice 6 after the walked-approval evidence format exists as a prerequisite for activating the privileged path.
2. A naming-hygiene check was omitted because the planned controlled vocabulary of subsystem names began empty and would therefore have produced only noise, and it returns once a real subsystem-name set exists.
3. Requiring an entry-manifest row was removed because it duplicates the trailer and forces any two concurrent imports to conflict on one shared file, and it will never return because trailers are the records and `git log --grep "Gatekeeper-import:"` is the view.
4. A separate audit log was omitted because transcripts and Git history already retain the required information, and it will never return because `status` derives its result from history.
5. Caller-created request identifiers were omitted because the automatically calculated content digest already gives retry-safe identification, so they are not expected to return.
6. Impact-based or footprint-scoped revalidation was omitted because all current checks are fast enough that rerunning everything costs less than implementing selective analysis, and it returns when a real test suite makes checks slow.
7. A merge queue was omitted because current request volume does not justify it, and it returns only if contention repeatedly reaches the retry limit.
8. The dedicated gatekeeper identity was originally deferred because there were only two agents on one machine and the procedural exposure was supposed to be audit-detected, although that detector was itself removed on August 10; the original trigger was either an audit finding or an early decision by the boss, and the second trigger occurred on August 9, so the identity is now admitted as specified in the credential section.

## Cross-spec consequence (resolved)

1. A conclusion reached on July 24 was superseded on August 2 by the revised `fast-handoff-design.md`: recycled handoffs now remain on their machine and are never checked in, while the single founding handoff is committed as an ordinary file.
2. The principle that information is written to disk before use still applies inside the supervisor’s cycle.

## Relationship to the legacy design

1. The legacy read-only document `git-clean-slate-plan.md` designed a many-writer solution to the same general problem.
2. This section is the single classification record required by the founding plan’s rewrite policy, using that policy’s four categories.
3. This design retains and re-derives only two legacy ideas under `update-feature`: expressing workflow rules as CLAUDE.md documentation and reducing branch protection to a lock controlled by one credential.
4. It classifies the three GitHub Apps, credential helper, per-agent branches, ordinary-work pull-request pipeline, and parking states as `remove-feature`, meaning they are intentionally not imported because this project has only one writer.
5. It classifies minimal repository Git configuration as `preserve-feature`, retaining the contract while choosing fresh values: `user.name` and `user.email` identify the machine account, and `useConfigOnly` prevents an identity from global Git configuration from leaking into repository commits.
6. There are no `consider-feature` items, so nothing is placed into `legacy-feature-queue/`.

## Acceptance tests

1. The build sequence and the mapping between tests and implementation slices are controlled by `docs/issues/3-git-gatekeeper-build-slice-plan.md`, whose five-slice plan supersedes this section’s original assumption that the implementation would be one task.
2. This section now serves only as an index of contract-level acceptance tests.
3. T1 requires every form error to produce its designated refusal and no side effects.
4. T2 requires the successful path to demonstrate all four guarantees and an exact trailer.
5. T3 requires an identical submission to return `already-checked-in`, modified content to create a new digest, and changes only to excluded metadata to leave the digest unchanged.
6. T4 injects a delay into concurrent submissions and requires one clean winner while the loser integrates over newer commits and also succeeds.
7. T5 requires a collision described as “same-content” to produce `conflict` with the affected files, intervening commits, and required next action; the phrase “same-content collision” is not further explained here and should not be silently equated with any more specific conflict scenario.
8. T6 requires persistent movement of `main` to end with `main-moving-too-fast` at the retry limit rather than loop forever.
9. T7 kills a worker during WORKING and requires `status` to report `abandoned` followed by successful cleanup and completion on resubmission, then separately kills a worker after its push and requires resubmission to return `already-checked-in`.
10. T8 says cancellation tests cover “all three outcomes,” without identifying in this sentence which three of the four outcomes specified earlier are meant, and separately requires cancellation after a push to return `too-late`.
11. T9 requires undeclared worktree differences to appear as a non-blocking advisory.
12. T10 was retired because the `imports` subcommand it tested was deleted, while trailer exactness remains covered by T2 and import screening by T11.
13. T11 requires every category of import defect to be refused correctly.
14. T12 was retired because the trailer-absence audit it tested was removed, while slice 5’s remaining audit acceptance is the B3c requirement for the branch-protection audit’s three named outcomes.

## Open

1. Cross-machine callers remain unresolved because the gatekeeper reads declared bytes from the caller’s worktree and therefore assumes a shared filesystem, so an Ubuntu-hosted gatekeeper cannot directly read a Mac agent’s checkout.
2. The unchosen alternatives are to have the caller push a branch and name its ref in the request, which changes the contract; route Mac-originated work through the Ubuntu side; or run a second credentialed gatekeeper host, which weakens C2’s single-place property.
3. The design postpones this choice until a Mac-side agent first requires direct check-in.
4. The concrete, machine-checkable form of “walked-approval evidence” has not been designed, so slice 6 cannot proceed until that format is decided.

## Resolved

1. The first artifact class requiring walked-approval evidence was designated as instruction-bearing text, including CLAUDE.md files, skills and their prompt templates, injected system prompts, and the wiki, with the precise class, procedure, and safeguards specified in `nedschorus` issue 31.
2. The corresponding enforcement check belongs to slice 6 and was scheduled for August 10 as a prerequisite for activating the privileged path.
3. The interaction with fast-handoff S2 is resolved by the Cross-spec consequence section.
