<!-- provenance: runtime=codex model=gpt-5.6-terra effort=xhigh cell=restate tier=floor target=docs/cross-project/git-gatekeeper-design.md -->

# git-gatekeeper (specification)

1. Branch protection and the account arrangement are already active as of 2026-07-21; an amendment to that arrangement was decided on 2026-08-09 but has not yet been applied, as described later in “The credential and enforcement.”
2. `scripts/git-gatekeeper.py` has been implemented through three of the five planned build slices, plus the sixth slice that checks review evidence; the latter was scheduled for 2026-08-10 because it must exist before the privileged lane can be activated.
3. The implemented behavior includes synchronous check-in, the initial validation/checkpoint stage, and integration of concurrent check-ins.
4. Slice 2 once included an `imports` table subcommand, but that command was subsequently removed by a 2026-08-10 ruling; import information is instead viewed through the commit trailer and `git log --grep`.
5. The implemented behavior has been tested using 140 cases in disposable repositories.
6. The test suite previously had 146 cases, but the 2026-08-11 application of a ruling removed tests for `--base` and the `imports` query and added assertions about individual fact fragments.
7. Slices 4 and 5 exist only as specified contracts, not as working code: slice 4 would add the worker-lifecycle features `--no-wait`, `status`, and `cancel`, while slice 5 would add the branch-protection audit, repository Git configuration, and CLAUDE.md workflow instructions.
8. If a caller reaches an option belonging to an unimplemented part, the program must deliberately return `unbuilt-option` rather than crash.
9. The gate currently does not actively control main because no host yet has a credential that can write to main on its behalf.
10. The 2026-08-09 revision incorporates the two outstanding changes from the 2026-07-30 bindings review: a refused `--no-wait` request leaves a JSON refusal record in its workspace, which `status` returns once and then removes; and the branch-protection audit has three explicitly named result types.
11. That revision also incorporates the `Gatekeeper-agent` trailer required by ruling B6 on 2026-07-31.
12. It also incorporates credential decisions C1 through C8 from 2026-08-09, including early admission of a dedicated identity, a Unix-user isolation boundary, limited agent tokens, break-glass access, and a cooperative hook layer.
13. The separate credential-and-hook delta document was retired on 2026-08-10 because this specification is now the only normative source for those rulings; its history remains available in Git and in `md-review-records/`.
14. The core design reviewed by the boss on 2026-07-24—request and reply behavior, digests, trailers, concurrency, states, and the error catalog—was not changed by these later additions.
15. The specification still supersedes the older promotion-relay design, which used a relay branch as a second stage before changes reached main; this design replaces that structure with one gate.
16. It also supersedes the rule requiring an entry manifest to receive an appended row.
17. It replaces the retired words “land” and “landing” with “check-in” terminology.
18. References such as B1, B3c, B4a–B4d, and B6 refer to rulings from the 2026-07-30 bindings review, recorded in `docs/issues/queue/3-gatekeeper-build-bindings.md`.
19. In this document, “the boss” and “the user” both mean the project’s human owner.
20. The document describes the mechanism by which a change reaches `main` in nedschorus.
21. The design explicitly stops at getting a change onto `main`; deploying `main` to production is outside its scope.
22. Deployment will be a separate DevOps or CI design concern when the project first has a long-running process.
23. Until then, `main` happens to serve as production, but that is not a consequence guaranteed or created by this design.
24. Normal changes are made without branches or pull requests.

## The job and the guarantee

1. `scripts/git-gatekeeper.py` is intended to be the sole program through which any change can reach `main`.
2. That program is intended to possess the project’s only credential authorized to write to `main`.
3. This section defines that intended contract, but the credential is inactive until it actually exists, as noted in the implementation-status text.
4. Every agent has the same relationship to the gatekeeper: each invokes it directly and none pushes to `main` itself.
5. Agent tokens may still push branches, because C4 permits branch pushes.
6. The intended arrangement is one program, using one main-writing credential, providing the only route into `main`.
7. No agent is meant to act as another agent’s doorman or relay in its check-in process.
8. Choirmaster is only the agent that most often asks for check-ins, not a privileged intermediary.
9. For a check-in request, the program has exactly two substantive outcomes: it either puts the submitted work into `main`, or rejects it while explaining how to correct the problem.
10. Informational commands such as `status` and `cancel` answer questions or perform their stated operation rather than themselves checking work in.
11. A successful check-in guarantees that the change is present on `main` and has been pushed to GitHub.
12. It guarantees that the checks were run on exactly the same content that was ultimately pushed.
13. It guarantees that the commit trailers contain the entire machine-readable record.
14. It guarantees that the requester receives confirmation of success and the commit identifier, either directly when waiting or later through `status` when using the non-waiting form.
15. Every refusal must contain three things rather than merely an error code: a fixed-catalog error name, concrete facts about the particular failure, and a precise next step written so an agent can perform it.
16. On refusal, the repository normally remains unchanged.
17. The sole named exception is that a refused non-waiting request leaves a JSON refusal record in its workspace until that record is read or expires.
18. The only lasting records are Git history and the ordinary transcript of the session that invoked the program.
19. The design intentionally creates no extra durable files or separate logs, because invocation is an ordinary tool call whose record already belongs in the place where tool calls are recorded.
20. The B4d refusal record is not treated as a durable record because it is temporary and disappears after collection or sweeping.
21. Repeating the same request is intended to be safe in every case.
22. An unchanged repeat receives the same result, while a corrected request has a different digest and is processed anew.
23. If the work has already been successfully checked in, the program responds `already-checked-in <commit>`.
24. An agent that crashes or loses its connection should submit the request again rather than attempt to infer or reconstruct the previous outcome.
25. The program is intended to distinguish the relevant cases after that resubmission.
26. The intended operational loop is that refusals explain the correction and retries cost nothing harmful, allowing the workflow to recover from ordinary autonomous-operation failures.

## The request and the reply

1. All request-form validation is immediate and synchronous whether the caller waits or does not wait, and every validation failure identifies both its catalog error and its remedy.
2. `--files` accepts a nonempty list of normalized repository-relative paths.
3. Such paths may not be absolute, may not contain `..`, may not refer to anything under `.git/`, and may not repeat.
4. For each declared path, the program reads the new content from the invoking agent’s working copy.
5. That is the program’s only read of file content from that worktree.
6. The advisory scan may read changed-file names from Git status, but it never reads worktree file bytes.
7. For each declared path, the program categorizes the change as added when it does not exist at the base but exists in the worktree, modified when its worktree content differs from the base, or deleted when it exists at the base but not in the worktree.
8. A path found neither at the base nor in the worktree is refused as `unknown-path`, meaning the likely issue is a typo.
9. A declared path whose content is identical to the base is refused as `unchanged-path`, because a declaration must truthfully identify an actual change.
10. An empty or malformed files list is refused as `malformed-field`.
11. The former `empty-change` error was removed on 2026-08-10 because it could never be reached: the first individually unchanged declared path would already produce `unchanged-path` before an aggregate “nothing changed” test could occur.
12. The accepted 2026-08-10 limitation is that file comparison considers bytes only and ignores executable-bit changes.
13. Therefore a permissions-only change, such as `chmod +x` with no byte change, is rejected as `unchanged-path`.
14. The document calls this limitation cosmetic because project scripts are executed with `python3 <path>`, so the executable bit currently has no effect.
15. When a change modifies file bytes as well as the mode, the committed result carries the mode change along with the byte change.
16. The design intentionally postpones mode-aware behavior until a real project need appears.
17. `--message` is the human-readable explanation of what changed and why.
18. Its value becomes the commit-message body before the trailers.
19. It is required and cannot be empty; a missing or empty value is `malformed-field`, with facts identifying the message field.
20. The distinct `missing-message` error was folded into `malformed-field` on 2026-08-10 so empty fields are handled consistently.
21. The author, rather than the program, must supply the intent expressed by the message.
22. The program may not automatically invent or fill in that intent.
23. The base is the exact `main` commit from which the submitted work began.
24. The program computes the base instead of accepting it from the caller, following a 2026-08-10 ruling that replaced the caller-supplied `--base` argument and its two handoff-related refusal cases.
25. After fetching, the program runs `git merge-base HEAD origin/main` in the caller’s checkout.
26. It uses that same checkout because it already needs that checkout’s declared file content.
27. This is meant to give every caller a deterministic and correct base, without a relay stage that could distort the value and without relying on the cooperative layer being installed.
28. By how it is computed, the resulting base is a real commit that belongs to `main`.
29. A caller that refreshes from `main` in the middle of its work, for example by running `git pull`, may present a fork point that is newer than the point where its work really started.
30. That weakens conflict detection for that request.
31. The design accepts this blind spot because the prior design had the same issue: its wrapper derived the base from the same repository state.
32. `--import` must explicitly be either `none` or a complete set consisting of a legacy commit ID, a source path, and a destination path.
33. For an import, the source must exist in the legacy repository at the stated legacy commit.
34. The import destination must also be listed in `--files`.
35. Any import problem—an incomplete triple, nonexistent source, undeclared destination, or unreadable legacy checkout—uses the single `import-invalid` error.
36. Although all such failures share that one error name, its facts and next-action text must say which specific import problem occurred.
37. Four previously separate import errors were merged on 2026-08-10 because no machine behavior depends on distinguishing their names and the explanatory text can preserve each distinction.
38. A request cannot describe two imports, because a second import must instead be a second check-in.
39. The caller must make an explicit import choice.
40. Combining `--import none` with any part of an import triple is `import-invalid`.
41. Omitting `--import` completely is also `import-invalid`.
42. The document says the built program already behaves this way and that this was documented on 2026-08-11.
43. `--issue` must be either `none` or a positive integer.
44. Version 1 checks only that this value has valid syntax.
45. The artifact-lifecycle rule, described as a standing rule in the founding plan, determines before gatekeeper invocation whether work deserves an issue and at what granularity.
46. The gatekeeper merely records that upstream decision.
47. `none` is a truthful value for trivial work, because an issue is not required for every invocation.
48. The stated reason is that issues are containers for desired work, not execution logs.
49. `--agent` is a required, nonempty runtime/model identifier, such as `claude-code/opus-5`.
50. A missing or empty agent value is `malformed-field`.
51. The caller supplies this value because the environment identifies the runtime but does not identify the model.
52. The model matters because the fix ladder—the founding plan’s escalation path for failed work, from retry to a stronger model to the boss—needs to know which model last authored the work.
53. Recording the agent value makes the answer to “who last wrote this?” available with one `git log` query.
54. The agent value is cooperative information: the program records what the caller says and does not verify or infer it.
55. Origin is filled automatically from the session environment.
56. If no origin is available, the program records `none` and does not reject the request.
57. A caller lacking a transcript is considered honestly transcript-less rather than erroneous.
58. Origin is useful because the project’s agents are long-lived and a session ID can point to a readable transcript describing intent.
59. The digest is a SHA-256 value over the base ID, the sorted path list, every path’s new bytes with a special marker for deletions, and the import triple.
60. Message, issue, waiting mode, origin, agent, and time are deliberately excluded from the digest.
61. The intended meaning is that the digest identifies the work itself, so otherwise identical work submitted with different metadata still deduplicates.
62. The built program serializes the digest inputs with NUL-framed field tags between components, ensuring that concatenating different inputs cannot accidentally make two distinct requests appear identical.
63. The program computes the digest; callers do not generate it.
64. The 2026-08-10 scope ruling limits deduplication to byte-for-byte resubmissions of the same work against the same base.
65. Work rebuilt after refreshing from `main` gets a new digest.
66. If that rebuilt work was already checked in, the paths it declares now match `main`, so the answer becomes `unchanged-path`.
67. The design accepts this outcome because the cases that reach it are expected to be rare, such as an imperfect successor-session handoff or duplicated work.
68. The refusal text is considered sufficient because it already identifies the immediate operative fact: the declared content does not differ from the base.

### The reply

1. Every invocation writes exactly one JSON object to standard output.
2. That object has the common shape `{outcome, error?, facts?, next_action?, commit?, digest?, integrated_over?, advisory?, summary}`.
3. `summary` is the human-readable line, so there is one reply format rather than separate machine and human formats, as required by B1.
4. Optional fields appear only when applicable.
5. `integrated_over` appears when a check-in initially loses a race but successfully applies over the newer work.
6. `advisory` appears when the worktree has differences beyond what the request declared.
7. Both `integrated_over` and `advisory` are already emitted by the built program.
8. Exit status 0 means either success or an informational answer.
9. Exit status 1 means a catalog refusal in a correctly functioning gatekeeper.
10. Exit status 2 means the gatekeeper itself has a defect.
11. The separation between exit statuses 1 and 2 prevents retry counters and audits from mistaking a gatekeeper bug for a valid refusal.
12. A waiting caller whose request succeeds receives `checked-in <commit-id>` and exit status 0.
13. If that success required cleanly reapplying after losing a race, the reply also includes `integrated_over: <n>`.
14. Once a non-waiting caller has passed form validation, it immediately receives `accepted <digest>`.
15. That caller later retrieves the result with `status <digest>`.
16. The reply’s `next_action` must explicitly direct that caller to do so.
17. Every refusal uses the three-part teaching response and exit status 1.
18. `status <digest>` derives its answer from existing Git history and the program workspace.
19. It can report `checked-in <commit>`, `in-progress`, `abandoned` when a workspace exists but its worker is dead, a retained B4d refusal record, or `unknown`.
20. A retained refusal record is returned once in the complete three-part refusal form and then removed.
21. `unknown` means there is no trace of the request and tells the caller to submit it, which the design says is always safe.
22. The behavior of `cancel <digest>` is defined later in “States, crashes, cancel, and errors.”
23. The single-word subcommands `status` and `cancel` are intentionally exempt from the project’s multi-part naming rule, by a 2026-08-10 ruling.
24. The document treats that exemption as deliberate rather than as a breach of the naming rule.
25. A subcommand is never used without the enclosing program name, so every such command appears under the searchable name `git-gatekeeper`.
26. Therefore the naming rule’s intended failure case—a search failing to find the relevant thing—does not arise.
27. Renaming the built commands would leave the existing test suite using old names without producing any search benefit.
28. Import records are read directly from history using `git log origin/main --grep "Gatekeeper-import:"`.
29. That command lists each import’s imported content, legacy commit, destination, and time.
30. The slice-2 `imports` subcommand once formatted those records into a table, but a 2026-08-10 ruling removed it.
31. The stated reason is that the trailer itself is the record, the Git command is the view over it, and a scratch clone for each call added no guarantee.
32. The trailer replaces the retired entry-manifest-row mechanism.
33. `entry-manifest.md` remains only as a historical founding-era record.

## The procedure

1. The agent submits a request to the program and chooses whether to wait.
2. In both modes, instant screening performs the form validation already described.
3. During that screening, the program computes the digest and searches Git history for it.
4. If the digest is already in history, the program immediately returns `already-checked-in <commit>` and performs no further work.
5. A non-waiting caller receives `accepted <digest>` at this stage.
6. All later processing is meant to be identical regardless of whether the caller waits.
7. “Instant” means synchronous and expected to take seconds, not that it performs no I/O.
8. The built program creates the workspace clone during screening.
9. The candidate is built in the program’s private `<workspace-root>/<digest>/` workspace and never in the agent’s worktree.
10. Candidate construction starts from `main` at the computed base and applies exactly the declared changes.
11. Any file not declared by the request comes from `main`, not from possibly stale copies in the agent’s worktree.
12. An import is performed during candidate construction by copying the source from the legacy repository at the specified legacy commit.
13. The program records the import source for the eventual trailer at that time.
14. The program runs the constructive-guarantee checks against the candidate, namely the literal bytes that would become `main`.
15. It makes the commit with the supplied message followed by the trailer lines.
16. On the normal path, `main` has not changed since the computed base and the push succeeds.
17. If `main` changed, the concurrent-check-in procedure applies.
18. A waiting caller receives its result directly.
19. A non-waiting caller’s result is then represented in history so that `status` can retrieve it.
20. Normally, the workspace is deleted after the result.
21. The B4d exception is a refused non-waiting request: its workspace remains only with the refusal record until `status` retrieves the record or the record expires.
22. The requester’s own working copy is never changed by the gatekeeper.
23. The agent may refresh that working copy from `main` whenever it chooses.

## Constructive guarantees, the advisory, and the growth point

1. The design aims to prevent most traditional gate failures by how it constructs the candidate, rather than by detecting those failures after the fact.
2. Undeclared changed paths cannot reach the candidate, because the candidate is assembled from the path declaration.
3. A stray edit inside a declared path does reach the candidate, because the declared file’s worktree bytes are themselves the declaration.
4. Thus the stray-change guarantee operates at file-path granularity, not at the granularity of individual edits within a file.
5. The machine-readable record cannot be absent because the program, rather than the requester, writes the trailers.
6. The import record cannot become out of date because it is written while the candidate is constructed into the same commit.
7. Duplicate work cannot be applied because digest lookup happens at submission.
8. If the worktree has modified files outside the declaration, the program emits an advisory such as “worktree also differs at `x`, `y`; confirm intentional.”
9. The advisory exists because a likely explanation is that the requester forgot to declare those files.
10. It never blocks a request because unrelated work in progress within the same worktree can be legitimate.
11. In version 1, after screening and before pushing, no remaining rejection is based on judgment.
12. That stage is intended to be deterministic construction and recording.
13. Infrastructure failures such as `workspace-io-error` and `network-down` can still occur there, but the document says they can safely be retried by resubmitting.
14. In version 1, the available check set is construction itself.
15. Therefore the second success guarantee currently means that the construction work was bound to exactly the bytes pushed.
16. That guarantee gains substantive test content as actual checks are added.
17. The design calls this an intentional growth point rather than a missing safeguard.
18. When a test suite exists, its tests are to run at this point in the procedure.
19. When the boss requires a class of artifact to have review evidence, that evidence check is to run here as well.
20. The request format should gain an evidence field only when such a requirement exists, rather than earlier.

## The trailer

1. The trailers contain four factual values and one pointer, with no additional information.
2. The `Gatekeeper-agent` trailer, required by B6 and ruled by the boss on 2026-07-31, always records the literal runtime/model value that produced the change.
3. That agent trailer may never be omitted.
4. Its purpose is to let the fix ladder know which capability tier produced an artifact, so it can tell whether stronger models are still available for escalation.
5. The digest trailer is the key used for duplicate detection, not a provenance record.
6. It is the mechanism that makes retrying a submission safe.
7. The issue trailer deliberately writes an issue as `#<n>`.
8. A commit that reaches the default branch with `#<n>` in its message automatically appears in that issue’s GitHub timeline.
9. Consequently, the document claims an issue gathers all of its check-ins without special additional machinery.
10. The same collection can be reconstructed offline with `git log --grep "Gatekeeper-issue: #<n>$"`.
11. The end anchor in that search is intended to ensure that a search for `#1` does not also match `#10`.
12. Refusals and other non-success responses are never automatically posted to issues.
13. Mechanical routine output belongs in session transcripts instead.
14. A genuinely blocking event may receive a deliberately written comment from the requesting agent.
15. The stated revision convention is that comments should represent genuinely new events.

## Concurrent check-ins

1. The design relies on GitHub’s property that a push either succeeds completely or is completely rejected.
2. It assumes GitHub never partially applies or interleaves two competing pushes.
3. GitHub is therefore the component that decides which competing request wins.
4. Exactly one request wins a given race.
5. The design deliberately has neither a queue nor a lock.
6. Check-ins are intended to run in parallel by default, by boss ruling.
7. The winner completes the normal procedure without needing to know that competition occurred.
8. The program, rather than the losing agent, handles a losing request.
9. It fetches the new `main` and first looks at its new tip for the losing request’s digest.
10. If the winner was actually a concurrent submission of the same work, the losing request answers `already-checked-in <commit>` and does not rebuild.
11. Otherwise, the program rebuilds the candidate by applying the declared changes over the new `main`.
12. A clean reapplication—normally one whose changes concern different paths—causes the program to rerun checks on the rebuilt candidate and push again.
13. In version 1, it reruns every check on that rebuilt candidate, because checks are currently cheap.
14. A cleanly integrated reply reports that it integrated over `N` newer commits.
15. A real conflict means that newer `main` changed one or more of the same paths that the request changes.
16. The built program detects that overlap at whole-file granularity.
17. The design says this prevents a silent lost update within a path.
18. Because resolving such an overlap would require guessing the author’s intended combined content, the program must not make that guess.
19. It instead refuses as `conflict`.
20. That refusal identifies the conflicting files and intervening commits and tells the caller to update from `main`, adjust the work, and resubmit.
21. The adjusted request has a new digest, which the design considers correct.
22. A request whose worktree was already behind `main` uses the same process, because it is equivalent to `main` having moved before candidate construction began.
23. The retry loop may run at most five rounds.
24. If it reaches that limit, the program refuses with `main-moving-too-fast` rather than retrying indefinitely.
25. The design explicitly accepts the remaining gap that changes in different files can still interact semantically without being detected until tests become part of the checks.
26. When checks become slow because a real test suite exists, the planned optimization is to rerun only checks whose inputs overlap the changes between the relevant bases.
27. The purpose is that harmless head movement, such as ledger marks or log commits, does not invalidate a pending check-in unnecessarily.
28. A merge queue, which would validate several queued requests against their projected combined result, is a later possible step if workload volume requires it.

## States, crashes, cancel, and errors

1. The lifecycle begins in `SCREENING`, which is synchronous, held in memory, and leaves nothing on disk.
2. It then enters `WORKING`, in which the candidate is built and checked inside `<workspace-root>/<digest>/`.
3. Concretely, before C2 the workspace root is `$XDG_STATE_HOME/nedschorus-gatekeeper/<digest>/`, defaulting to a `~/.local/state/...` location.
4. Once C2 is installed, that path is resolved in the gatekeeper Unix user’s environment, with the literal default `/home/nedschorus-gatekeeper/.local/state/nedschorus-gatekeeper/<digest>/`.
5. The workspace is outside every repository and can be located from the digest alone.
6. It contains the candidate clone, `worker.pid`, and a resolved request record.
7. Under B4c, every environment-derived value—especially origin—is resolved during screening and written into that record.
8. The worker reads the resolved record but never recomputes those environment-derived values.
9. The next state is `PUSHING`, which is the atomic push attempt and is subject to the retry cap.
10. The terminal state is either `CHECKED-IN` or `REFUSED`.
11. After either terminal state, the workspace is deleted.
12. The exception required by B4d is a refused `--no-wait` request, whose workspace retains only the JSON refusal record until `status` returns it once and removes it.
13. On every gatekeeper invocation, the program opportunistically removes refusal records older than 30 days.
14. No daemon is required for this expiry process.
15. A caller whose record has expired simply resubmits, which is intended to recover in the same way as other lost refusal reasons.
16. The design accepts the residual case where a caller crashes after the record is swept but before reading it, thereby losing the reason.
17. It calls that situation rare and recoverable through resubmission.
18. A successful request’s durable trace is its commit on `main`.
19. A refused waiting request deliberately leaves no durable trace.
20. Crash recovery is intended to follow one rule rather than a special recovery procedure.
21. The entire pipeline has only two durable effects: the workspace directory and the atomic push.
22. Therefore, after a crash or lost connection, either the commit is on `main`, or it is absent and a stale workspace remains.
23. Recovery is always to resubmit.
24. If history contains the digest, resubmission returns `already-checked-in <commit>`.
25. If history lacks the digest, the program removes the leftover workspace and processes the work as new.
26. The design has no journal and no repair mode.
27. `status` distinguishes an active `WORKING` request from `abandoned` by checking the recorded process ID.
28. `abandoned` means a workspace exists but the worker process is dead.
29. This makes a silently died worker an explicitly named and resubmittable state instead of one that remains permanently reported as in progress.
30. The accepted limitation is that an operating system may recycle a process ID, making an unrelated process look like the original worker, and that a process-ID test has no meaning across machines.
31. Slice 4 is to store the worker’s start time alongside its process ID so `status` can check both values.
32. `cancel <digest>` is described as part of version 1 because the boss ruled that slow checks create the need, the required lifecycle machinery already exists, and the feature is small.
33. Any agent may cancel a request.
34. There is no permission system for cancellation because the design assumes cooperation.
35. The workflow does not teach cancellation as an ordinary routine action.
36. The author gets no special cancellation authority, because the author may no longer be present and authorship is not treated as a source of special judgment.
37. If the digest is already in history, cancellation returns `too-late — already-checked-in <commit>`.
38. If a checked-in change is bad, the remedy is a revert: an ordinary new check-in that undoes the earlier commit through the same gate.
39. If a live worker exists, cancellation kills it, deletes its workspace, and returns `cancelled`.
40. If a workspace exists without a live worker—whether from an abandoned run or a retained B4d refusal record—cancellation deletes it and returns `cancelled`.
41. If neither history nor workspace contains the request, cancellation returns `unknown-request`.
42. A cancel-versus-push race is settled by the push’s atomicity: after killing the worker, the program checks history to see whether the digest reached `main`.
43. The design says cancellation only makes sense before a check-in completes.
44. After a check-in has completed, the appropriate operation is a revert.
45. Every possible ending is intended to have a catalog name and a three-part teaching response where it is a refusal.
46. The instant form-error group consists of `malformed-field` for any missing, empty, or malformed field identified in facts; `unknown-path`; `unchanged-path`; and `import-invalid` for any specifically identified import problem.
47. On 2026-08-10, `missing-message` and unreachable `empty-change` were absorbed into `malformed-field`; four import errors were merged; and `unknown-base` and `base-not-on-main` were retired because callers no longer submit a base to validate.
48. Integration errors are `conflict` and `main-moving-too-fast`.
49. Infrastructure errors are `push-auth-failed`, `network-down`, and `workspace-io-error`, and each is intended to be safe to resubmit.
50. Callers may make bounded, backed-off retries for infrastructure refusals when their own judgment warrants it.
51. The gatekeeper itself must not direct callers to retry forever.
52. `unbuilt-option` means that a request reached an option in the not-yet-implemented slice-4 or slice-5 surface.
53. Its prescribed options are to resubmit without that option or wait until the relevant slice ships.
54. `checked-in <commit>`, `already-checked-in <commit>`, `accepted <digest>`, `in-progress`, `abandoned`, `unknown`, `cancelled`, `too-late`, and `unknown-request` are answers rather than errors.
55. The stated autonomy standard is that no outcome is unnamed, every refusal explains a corrective action, resubmission is always safe, and machinery never mechanically escalates matters to the boss.
56. Agents consult the boss through their own judgment rather than through an automated route.

## The credential and enforcement

1. The dedicated-identity option was admitted earlier than originally planned by a user ruling on 2026-08-09, because the trigger described later had been exercised.
2. The older arrangement is described first because it remains the live arrangement until the amendment is actually applied.
3. Since 2026-07-21, branch protection has restricted pushes to `main` to the machine credential `NedLern`.
4. Administrators are subject to that protection, and force-pushes and deletion are blocked.
5. The organization has two owners: `NedLern`, and `NedLerner`, which has settings and emergency authority but no push role.
6. Because `NedLern` is a literal prefix of `NedLerner`, substring searching can confuse the two names, so searches must match whole or anchored names.
7. Either owner can recover the organization if the other account is lost.
8. A protection change by either owner is intended to be a visible, deliberate recovery act rather than an ordinary standing route into `main`.
9. The boss does not commit directly.
10. A change originating with the boss is drafted with an agent and checked in through the same process as every other change.
11. Because the repository is public, issue activity needs no repository grant beyond an authenticated GitHub account.
12. Agent tokens nevertheless include `issues:write` because the machinery uses that capability, as stated by C4.
13. The 2026-08-09 C1/C3 amendment requires an organization owner to apply it.
14. Under that amendment, the pusher role moves to a dedicated GitHub account.
15. That account is a write collaborator on this repository only, is not an administrator, and is never an organization owner.
16. Branch protection will then list only that dedicated account as allowed to push.
17. The account name is to be recorded literally in this document once the amendment has been applied.
18. This option was chosen over the App or CI form previously outlined here because an App or CI job would relocate the gate into CI, which this design excludes.
19. A plain GitHub account keeps the gatekeeper as a local program.
20. A stolen token for that account could commit only to this repository and nothing else.
21. Owner authority remains with the user.
22. C3’s target state is that no agent ever holds owner authority.
23. That target becomes true when the amendment is applied.
24. Until then, `NedLern` is both the pusher and an owner, which is the documented exception in the current live state.
25. The Unix-user boundary in C2 is where enforcement is intended actually to occur.
26. GitHub can restrict which accounts may act, but not which local processes act.
27. On one machine, every process owned by the same Unix user can read the same credential files.
28. Therefore the main-writing credential is to belong to a dedicated Unix user whose credential files agent sessions cannot read.
29. Agents invoke the program through a sudoers rule limited exactly to that program.
30. This is the point at which “agents never push” becomes technically impossible rather than merely instructed behavior.
31. It also makes the gatekeeper an actual invocable service for any agent on that machine.
32. The sudoers rule must point to a root-owned program copy outside all checkouts.
33. A sudoers rule that pointed into a checkout would grant privileges to whichever program bytes an agent most recently wrote there.
34. The deployed copy updates itself automatically from `main`.
35. Thus a check-in containing a gatekeeper fix becomes active on the next invocation without a manual deployment step.
36. This automatic update is considered safe because gatekeeper source belongs to the instruction-file artifact class.
37. Changes to that class may reach `main` only with walked-approval evidence, enforced by the slice-6 review-evidence check.
38. Therefore the privileged lane cannot be activated until slice 6 exists.
39. The intended deployed location is `/usr/local/lib/nedschorus-gatekeeper/git-gatekeeper.py`.
40. A stale deployed copy fails safely because it still enforces an earlier contract and cannot be turned into agent-written code.
41. The security property comes from ownership, not from immediate freshness.
42. A lag in self-updating therefore reduces availability but not safety.
43. The stated project-wide principle is that deployed copies automatically keep themselves current from their sources instead of depending on somebody remembering a deployment step.
44. Under C4, every agent host has a fine-grained token limited to this repository.
45. That token has repository contents read/write permission, including branch pushes, because the no-push rule is specifically about `main`.
46. It also has issue-write permission.
47. It is never an all-repository classic token and never has the `workflow` scope.
48. The document links the absence of workflow scope to capability-by-landing-class and nedschorus issue 31.
49. Issue work is limited in scope but not gated.
50. The reason is that issues have no equivalent invariant requiring one writer to `main`.
51. Consequently, issue discipline belongs to the skill and hook layer rather than the gatekeeper.
52. C6 is a cooperative layer above the Unix-user boundary and must never be mistaken for a replacement for that boundary.
53. A `PreToolUse` hook rewrites `gh` calls transparently into their disciplined form, meaning the equivalent operation routed through the project wrapper with the same arguments.
54. A `git push` directed at this repository’s remote is denied and replaced with a template for a check-in invocation.
55. That template prepopulates files from the agent’s own staging area.
56. It leaves the message for the author to provide.
57. It is deliberately not an exact ready-to-run command.
58. A raw push does not contain the complete declaration required by a check-in.
59. Automatically deriving every missing part would defeat the intentionality that `unchanged-path` is meant to require.
60. The check-in skill places the declaration up front by taking `--files` from the agent’s staging and passing the author’s message through unchanged.
61. It does not need to prepare a base because the program computes the base.
62. Thus the agent need only provide information it is already trained to provide.
63. Refusals are the final teaching layer.
64. C5 break-glass is an unlockable credential, not an always-available ungated credential for agents.
65. Gate defects are recoverable from the gate’s own history because the program intentionally remains one file that uses only the Python standard library.
66. Therefore any historical version can be run directly.
67. If the gate wrongly refuses a check-in, the user can authorize a sudoers entry by entering the user’s password at that moment.
68. Credential expiration and branch-protection misconfiguration are reserved to the organization owner, meaning the user alone.
69. The test seams do not require a privileged-mode guard, because C7 was reduced to zero by the user on 2026-08-10.
70. `--repo` and `--remote` allow tests to supply disposable repositories, and their behavior is intended to be identical for every Unix user.
71. The earlier planned refusals did not protect anything.
72. A remote belonging elsewhere would fail GitHub authentication because the credential is limited to this repository under C1.
73. Refusing `--repo` would merely shift caller control to the current working directory rather than removing caller control.
74. The design considered but rejected a hard-coded remote as defense in depth against future credential misconfiguration.
75. It treats the token scope, configured once by the user, as the relevant guard.
76. Until C2 is installed, the design’s honest statement about singleton access is that branch protection limits an account, not individual processes.
77. Anything running as the permitted account on any machine can push.
78. The design does not need a process-ordering lock because the atomic push resolves ordering.
79. Before C2, the remaining procedural requirement is only that agents use the program instead of issuing raw `git push`.
80. CLAUDE.md is documentation rather than enforcement, because a Python script does not read it and machines may have different copies.
81. Harness hooks likewise only configure a harness, and only cooperating harnesses read them.
82. That is why C6 is a convenience layer and C2 is the actual isolation boundary.
83. No guarantee in this design may depend on CLAUDE.md or harness hooks.
84. They still provide convenience and save tokens.
85. The remaining raw-push risk is detected at its origin rather than prevented.
86. At each handoff scrub—the cleanup pass every agent session performs when handing off—a branch-protection audit checks the live protection settings against this design.
87. That audit has exactly three named outcomes: `protection-ok`, `protection-wrong` with differing settings identified, and `audit-failed` for missing or unauthenticated `gh` or an API error.
88. An audit failure must visibly report its own failure and may not be silently skipped and treated as passing.
89. This is the B3c requirement.
90. While it remains relevant, the audit also detects the sibling risk that an agent possessing an owner credential could intentionally change protection settings.
91. C3 removes that risk by ensuring agents have no owner authority.
92. The former design also included a second detector that scanned `main` for commits without trailers and created draft issues.
93. That detector was removed on 2026-08-10 during the subtraction review.
94. Once C2 and C3 are applied, a trailer-less commit can arise only from user-approved, password-authorized break-glass or from protection failure.
95. The branch-protection audit addresses the latter at the configuration level.
96. A detector whose findings do not feed any consuming process is considered logging cost without value.

## Deliberately not in version 1

1. The review-evidence request field and check were omitted initially because no artifact class was gated at founding.
2. The first gated class was designated on 2026-08-04 as instruction-bearing text, referenced as nedschorus issue 31.
3. This feature is to return in slice 6 after the walked-approval evidence format is defined, and slice 6 was scheduled for 2026-08-10 before privileged-lane activation.
4. The naming-hygiene check was omitted because the planned controlled vocabulary of subsystem names is empty at founding and would produce only noise.
5. It returns once a real subsystem-name set exists.
6. The entry-manifest append-a-row mechanism was omitted because it duplicates the trailer and a shared append-only file would force any two parallel imports to conflict.
7. It is never meant to return: the trailer is the import record and `git log --grep "Gatekeeper-import:"` is the intended view.
8. A separate audit log was omitted because ordinary transcripts and Git history already record the relevant events.
9. It is never meant to return because `status` derives its information from history.
10. Caller-created request IDs were omitted because the content digest is created automatically and makes retries safe.
11. They are never meant to return.
12. Footprint-scoped revalidation was omitted because checks are fast and rerunning everything is cheaper than implementing the analysis machinery.
13. It returns when checks become slow due to a test suite.
14. A merge queue was omitted because present volume is far below the level that would need one.
15. It returns if contention is sustained up to the retry cap.
16. A dedicated gatekeeper identity was initially omitted because there were two agents on one machine and the procedural gap was intended to be detected by an audit, although that audit itself was deleted on 2026-08-10.
17. The original trigger was either that the audit fired or that the boss chose to admit the identity early.
18. The second trigger occurred: the identity was admitted on 2026-08-09, as described in “The credential and enforcement.”

## Cross-spec consequence (resolved)

1. The relationship described here was resolved on 2026-07-24 and then superseded on 2026-08-02 by the session-recycling revision of `fast-handoff-design.md`.
2. Recycling handoffs are local to a machine and are never checked in.
3. The one committed handoff—the founding handoff—reaches the repository as an ordinary file.
4. The principle that files are written to disk first still applies within the supervisor’s cycle.

## Relationship to the legacy design

1. The read-only legacy `git-clean-slate-plan.md`, located at `~/Projects/nedlern/docs/working/proposed/`, designed this problem for a many-writer system.
2. This section is the authoritative classification record for the rewrite policy described in the founding plan’s “Standing decisions,” using that policy’s four-class vocabulary.
3. The new design retains only two ideas from the legacy design, but says they were independently re-derived as `update-feature` decisions.
4. Those retained ideas are workflow rules written as CLAUDE.md documentation and protection-as-lock reduced to a single credential.
5. The design does not import the legacy system’s multi-writer machinery, classified as `remove-feature`, because this project has one writer.
6. Specifically, it does not import the three GitHub Apps, credential helper, per-agent branches, ordinary-work pull-request pipeline, or parking states.
7. The repository Git configuration is minimal, is specified here rather than imported, and is classified as `preserve-feature` because the contract is retained while its values are re-derived.
8. That configuration sets `user.name` and `user.email` for the machine identity and sets `useConfigOnly` so a global identity cannot leak in.
9. There are no `consider-feature` entries, so nothing is sent to `legacy-feature-queue/`.

## Acceptance tests

1. Build order belongs to `docs/issues/3-git-gatekeeper-build-slice-plan.md`, which defines five slices and maps tests to slices.
2. The original one-task framing in this section was superseded by that plan through a 2026-08-10 ruling.
3. T1 requires every form error to refuse with its designated error and leave no side effects.
4. T2 requires the happy path to prove all four success guarantees and exact trailers.
5. T3 requires an identical resubmission to answer `already-checked-in`, changed content to receive a new digest, and metadata-only changes not to change the digest.
6. T4 requires concurrent submissions with an injected delay to show a clean winner and a loser that successfully integrates over newer commits.
7. T5 requires a same-content collision to refuse while naming files, commits, and a next action.
8. T6 requires sustained movement of `main` to end in `main-moving-too-fast` rather than endless retrying.
9. T7 requires a worker killed during `WORKING` to make `status` report `abandoned`, after which resubmission removes the stale workspace and succeeds.
10. T7 also requires a worker killed after pushing to make resubmission answer `already-checked-in`.
11. T8 requires all three cancellation outcomes and requires cancellation after a push to answer `too-late`.
12. T9 requires undeclared worktree changes to be reported as an advisory without blocking the request.
13. T10 was retired on 2026-08-10 because its subject, the `imports` subcommand, was deleted.
14. The exactness formerly tested by T10 is instead covered by T2’s trailer assertion and T11’s screening.
15. T11 requires each class of import error to refuse correctly.
16. T12 was retired on 2026-08-10 because its subject, the trailer-absence audit, was removed from the design.
17. The slice-5 audit acceptance condition is instead B3c’s three branch-protection-audit outcomes.

## Open

1. C8, cross-machine callers, remains undecided.
2. The gatekeeper currently reads declared file content from the caller’s worktree, so it requires a shared filesystem.
3. That means agents on the Mac side cannot have their worktree content read from the Ubuntu box.
4. No candidate solution has been chosen.
5. One possible shape is for the caller to push a branch and name a ref in the request instead of relying on worktree bytes; the document identifies this as a real change to the contract.
6. Another possible shape is to route Mac-side agent work through Ubuntu.
7. A third possible shape is a second host with credentials, but that would weaken C2’s single-place property.
8. The decision is deferred until a Mac-side agent first needs direct check-in.
9. The format of walked-approval evidence—what constitutes a checkable artifact showing that approval was walked—has not been designed.
10. Slice 6 waits for that format.

## Resolved

1. The first artifact class requiring walked-approval evidence was decided by the boss on 2026-08-04.
2. That class is instruction-bearing text: CLAUDE.md files, skills and their prompt templates, injected system prompts, and the wiki.
3. Check-ins for that class require walked-approval evidence.
4. The class definition, procedure, and protections are specified in nedschorus issue 31.
5. The enforcing check is slice 6, scheduled for 2026-08-10 before privileged-lane activation.
6. The fast-handoff S2 interaction is resolved by the “Cross-spec consequence (resolved)” section.
