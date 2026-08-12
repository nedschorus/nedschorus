<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=defect-hunt tier=good target=docs/cross-project/git-gatekeeper-design.md -->

1. “`scripts/git-gatekeeper.py` is BUILT through slice 3 of five — plus slice 6 (the review-evidence check), scheduled 2026-08-10...” supports incompatible readings: “plus slice 6” places slice 6 inside what is built, while “scheduled” says it is future work. Later, “Open” says its evidence format is undesigned, and “Deliberately not in version 1” says the check waits on that format. An agent cannot determine whether the check exists or whether the privileged lane may be activated. Confidence: sure.

2. “slice 2's `imports` table subcommand was built, then deleted by ruling 2026-08-10” is factually false against the explicitly referenced implementation. `scripts/git-gatekeeper.py` still defines `imports_table`, registers the `imports` parser, dispatches to it, and documents it in its usage text. This makes the stated implementation boundary unreliable. Confidence: sure.

3. “reaching an unbuilt part is the named refusal `unbuilt-option`, never a crash” is not executable for slice 5, because no slice-5 command or option is named, and is false for ordinary parser failures. The referenced program parses arguments outside its refusal handler, so an unknown command, unknown option, or missing required option exits through `argparse` rather than returning `unbuilt-option`. Confidence: sure.

4. “This revision (2026-08-09) folds in...” conflicts with the frontmatter’s “`design-as-of: 2026-08-11`” and with changes described as documented on 2026-08-11. “This revision” consequently has two plausible dates, obscuring which rulings belong to the current specification. Confidence: sure.

5. “this specification became the rulings' sole normative home” conflicts with the continued normative dependence on “The B-codes cited throughout ... recorded in `docs/issues/queue/3-gatekeeper-build-bindings.md`.” The referenced binding file still defines material absent here, notably `unsafe-path` and its validation. A future agent cannot implement the claimed sole specification without treating the supposedly non-normative binding as normative. Confidence: sure.

6. “One program, `scripts/git-gatekeeper.py`, is the only way any change reaches main” and “Agents ... never push to main themselves” conflict with the later admission that, until C2, agents can use raw `git push`, and with the separately defined break-glass lane. Those are ordinary alternate paths to main, even if policy discourages them. The absolute guarantee is therefore not currently enforced. Confidence: sure.

7. “For each check-in request the program does exactly one of two things: checks the work in, or refuses and teaches the fix” omits program defects, process termination, host failure, and loss of the response. The document itself defines exit code 2 as a third program outcome. An orchestrator relying on the stated exhaustive dichotomy will mishandle that channel. Confidence: sure.

8. “The commit's trailer lines carry the whole machine-readable record” leaves “whole ... record” undefined and is false under the natural reading of the complete request. The trailers do not contain the declared path list, base, message, mode, or resolved request object; the digest cannot reconstruct those values. This affects audit and recovery expectations. Confidence: sure.

9. “The repository is untouched — a refusal has no side effects, with one named exception...” conflicts with the later mandatory fetch in the caller’s checkout and with the rule that every invocation sweeps old refusal records. A refusal reached after the fetch can leave updated remote-tracking/FETCH_HEAD state, and even an unrelated refused invocation can delete expired records. The JSON refusal record is not the only side effect. Confidence: sure.

10. “git history and the invoking session's ordinary transcript are the only durable records. No side files, no separate logs” conflicts with the durable `request.json`, `worker.pid`, retained refusal JSON, and candidate workspace used for crash recovery. These files survive process loss and, for refusals, may remain for 30 days; calling them “transient” does not make them non-durable. The document later calls the workspace one of the pipeline’s “durable effects.” Confidence: sure.

11. “the invocation is a normal tool call, already recorded where tool calls are recorded” does not identify the transcript store, its path or lookup procedure, its retention, or which non-Claude runtimes create it. Since the transcript is declared one of only two durable records, loss or inaccessibility of that store is a reachable case with no stated disposition. Confidence: sure.

12. “Resubmitting is always safe. Same request, same answer; a fixed request digests differently” contains three incompatible claims. The same request can first receive `network-down` and later succeed; fixes to message, issue, agent, origin, or infrastructure do not alter the digest; and a later base changes the digest even when the work itself was not fixed. After subsequent edits to the same main path, a stale resubmit can also reintroduce old bytes rather than deduplicate. Confidence: sure.

13. “Refusals teach, retries are free: the loop self-heals” gives an agent continuing work no stopping point. Permanent authentication failure, disk failure, or network isolation does not self-heal, and the later “caller’s judgment” supplies no retry count or elapsed-time bound. Confidence: sure.

14. “Field by field, with exact validation” is incomplete. The referenced bindings and implementation reject whitespace, non-ASCII, non-printable characters, and `->` as `unsafe-path`, but this field list and the fixed error catalog omit that rule and error name. Implementations built from this specification can accept requests the current program refuses. Confidence: sure.

15. “repository-relative paths, normalized: no absolute paths, no `..`, nothing under `.git/`, no duplicates” does not define normalization or path-type behavior. Reachable cases include `./a` versus `a`, symlinks, symlinks whose targets lie outside the repository, directories, submodules/gitlinks, and file-to-symlink changes. In the referenced implementation, `Path.is_file()` follows symlinks and candidate writes can follow a checked-out symlink, so the omission can change which bytes are read or where writes occur. Confidence: sure.

16. “The new content of each path is read from the invoking agent's working copy” conflicts with the import mechanism, which obtains the destination’s content from the legacy repository and does not require it to exist in the working copy. This changes how added/modified/deleted classification applies to an import destination. Confidence: sure.

17. “every project script runs as `python3 <path>`, nothing depends on the bit” is false in this checkout. `scripts/launch-claude` is a shell script, and numerous scripts are executable and may be invoked directly by hooks or supervisors. A permissions-only change can therefore be operationally meaningful. Confidence: sure.

18. The command synopsis requires `--message "<one-line summary of what and why>"`, while the field definition validates only “Required, non-empty.” A message containing embedded newlines satisfies the latter and the referenced implementation but violates the former. Callers cannot know whether one-line form is syntax or merely advice. Confidence: sure.

19. “the program runs `git merge-base HEAD origin/main`, after a fetch ... so every caller gets the exact right value deterministically” is impossible as stated and contradicted by the immediately accepted mid-task-refresh blind spot. Git history does not record when uncommitted work began, so it cannot infer the historical start state after HEAD changes. The referenced implementation also still requires caller-supplied `--base`, making the described behavior non-existent today. Confidence: sure.

20. The same base mechanism leaves failures unspecified: fetch authentication or network failure, missing `origin/main`, an unborn or unrelated HEAD, shallow history, and `git merge-base` returning no commit. No mapping from those reachable results to the fixed refusal catalog is stated, despite the assertion that the result is always a real main commit. Confidence: sure.

21. “`--import` — `none`, or all three parts” and the synopsis’s `--import none | --import-commit ...` make the three-part form omit `--import`, but “omitting `--import` entirely ... refuse[s] `import-invalid`.” “Omitting” can mean either the valid triple form or supplying no import-related option. Those readings produce opposite behavior. Confidence: sure.

22. “The artifact-lifecycle rule (the founding plan's standing rule for which work gets an issue and when) decides upstream” delegates a required request field to an unnamed plan and undefined process. No explicit path or rule is supplied, and “right granularity” and “trivial work” are not defined. A context-limited caller cannot determine whether to pass `none`. Confidence: sure.

23. “`--agent` — the runtime and model ... required and non-empty” does not validate the promised `<runtime/model>` structure; an arbitrary non-empty value satisfies the stated exact validation. The rationale depends on an undefined “fix ladder” and model “tier,” with no ordering that lets an agent decide whether stronger models remain. Confidence: sure.

24. “the session id points at a readable transcript of intent” defines a pointer/store without naming the environment variable, lookup mechanism, filesystem or service, retention, authorization, or cross-host behavior. A syntactically valid session ID with a deleted, private, or machine-local transcript is an ordinary counterexample. Confidence: sure.

25. “NUL-framed field tags between components, so concatenation can never make two different requests read as one” is false for the referenced serialization because content has no length prefix or escaping. With the same base/import, one request containing path `a` with bytes `x\0path\0b\0content\0y` serializes identically to a request containing path `a` with bytes `x` and path `b` with bytes `y`. The two distinct requests therefore receive the same SHA-256 input and digest. Confidence: sure.

26. “when that work is already checked in, its declared paths now match main and the answer is `unchanged-path`” is not generally true. If the checked-in path was subsequently changed again on main, the old worktree bytes no longer match main; the stale request becomes a fresh modification and may restore obsolete content. This undermines the stated resubmission safety. Confidence: sure.

27. “Every invocation prints exactly one JSON object on stdout” is broader than the implementation can guarantee. `--help`, an unknown command, a missing required argument, Python startup failure, signals, and abrupt process or host termination are ordinary counterexamples; the current argument parser runs outside the JSON-producing exception handler. Confidence: sure.

28. “`status <digest>` answers ... `checked-in`, `in-progress`, `abandoned`, a retained ... refusal record, or `unknown`” leaves reachable store states without an outcome: malformed digest, partial or corrupt workspace, missing/invalid PID, unreadable request or refusal file, permission failure, two simultaneous status collectors, and an incomplete sweep. Since `status` is the only recovery interface for non-waiting callers, those omissions make the mechanism incomplete. Confidence: sure.

29. “the single-word subcommands (`status`, `cancel`) are a deliberate exemption from the project's multi-part naming rule, not a violation” conflicts with CLAUDE.md’s definition: “When creating or inventing names ... and other names likely to be grepped, use explicit, clear and precise multi-part names. Check newly invented names with glob ... or grep ... If these checks return collisions or ambiguity, choose a more explicit name, with 3 or 4 parts, not 1 or 2.” `status` and `cancel` are searchable invented names, and the specification supplies no required collision check. Its further assertion that the names “never appear alone” is false in this document and the parser, where both appear as standalone tokens. Confidence: sure.

30. “`git log origin/main --grep "Gatekeeper-import:"` lists every import” is misleading as a view because every gatekeeper commit contains a `Gatekeeper-import:` trailer, including `Gatekeeper-import: none`. The command consequently lists every ordinary check-in as well as actual imports, and can match unrelated message text. Confidence: sure.

31. “The digest is computed and looked up in history right here ... ‘Instant’ means ... the built program creates the workspace clone during screening” directly conflicts with the state definition “SCREENING (synchronous, in memory, nothing on disk).” A clone necessarily creates files on disk during SCREENING. Crash recovery and refusal-side-effect behavior depend on which statement is authoritative. Confidence: sure.

32. “the non-waiting caller's outcome now sits in history where `status` finds it” is false for refusals, which the document says live only in a retained workspace record. It also fails for `in-progress`, `abandoned`, and `cancelled`, none of which is represented by a successful commit in history. Confidence: sure.

33. “The requester's own working copy is never modified” is uncertain because “working copy” is undefined. The required fetch in that checkout modifies Git repository metadata and remote-tracking state but not checked-out file contents; the claim is true under the narrow “worktree files” reading and false under the common broader “local checkout” reading. Confidence: unsure for that terminology reason.

34. “The record cannot be missing — the program writes the trailers itself” is broader than its construction. Raw authorized pushes remain possible before C2, break-glass is an explicit bypass, and a program defect or malicious gatekeeper revision can create a trailer-less commit. Later sections acknowledge some of these paths. Confidence: sure.

35. “The import record cannot lag” is not enforced because the program cannot tell that manually copied legacy bytes are an import. A caller can copy legacy content into the worktree and honestly or dishonestly pass `--import none`; the gate then writes no import provenance. Confidence: sure.

36. “Duplicates cannot apply — the digest screen runs at submit” is too broad. Semantically identical work against another base receives another digest; the serialization itself has collisions; and simultaneous identical requests can both pass the history screen before either pushes. Later integration may mitigate the last case, but the submit-time screen does not make it impossible. Confidence: sure.

37. “if the agent's worktree contains modified files beyond the declared ones, the reply carries a note” conflicts with the referenced implementation’s `git status --untracked-files=no`. An undeclared newly added file—an ordinary forgotten declaration—is omitted from the advisory even though added paths are accepted check-in content. Confidence: sure.

38. “In v1 the check set is construction itself” and “when the boss gates an artifact class, its review-evidence check runs here (the request format grows its evidence field then, not before)” conflict with the document’s claim that instruction-bearing text was already designated, the implementation-status suggestion that slice 6 exists, and “Open” saying the evidence format remains undesigned. The document supplies no single current definition of the check set or request schema. Confidence: sure.

39. “any commit reaching the default branch with `#<n>` in its message appears automatically in that issue's GitHub timeline” exceeds the gate’s validation. Version 1 checks only that `n` is positive, not that the issue exists, is in this repository, or remains available; a reference to a nonexistent issue has no such timeline. Confidence: sure.

40. “a genuinely blocking outcome earns a judgment-written comment by the requesting agent” requires work but does not define “genuinely blocking,” distinguish it from retryable or terminal refusal, identify the issue to comment on when `--issue none`, or bound repeated comments across retries. Agents can either omit required communication or create repeated chatter while both believe they obeyed it. Confidence: sure.

41. “when checks become slow ... re-validation narrows to checks whose inputs intersect what actually changed ... so trivial head movement ... never invalidates a pending check-in” lacks a measurable “slow” trigger and any definition or store for check inputs and dependencies. The file already admits cross-file semantic interaction, so file intersection alone cannot support “never.” “Ledger marks” and “log commits” are also undefined classes. Confidence: sure.

42. The state expression “`WORKING (candidate built and checked, inside <workspace-root>/<digest>/`” never closes its WORKING parenthesis before “`the worker only reads it, never re-derives) → PUSHING`”; that closing parenthesis belongs to the nested B4c explanation. It is consequently unclear whether the workspace details, C2 condition, and transition to PUSHING are part of WORKING. The phrase “candidate built and checked” also omits the reachable interval after the workspace/PID record is created but before construction finishes. Confidence: sure.

43. “outside every repository, discoverable from the digest alone” is false across users, hosts, or differing `XDG_STATE_HOME` values. The digest does not identify the host, Unix user, state-home override, or whether C2 has moved storage into the gatekeeper user’s home. Confidence: sure.

44. The per-digest workspace mechanism leaves simultaneous identical requests unresolved. Both can pass the history check and target the same `<digest>` directory; no ownership claim, atomic creation rule, liveness check, or collision outcome appears here. The referenced implementation deletes any existing digest workspace before creating its own, so one request can erase another active request’s state. Confidence: sure.

45. “any gatekeeper invocation first sweeps refusal records older than 30 days” does not identify which timestamp controls age, where it is stored, how clock changes are handled, how refusal workspaces are distinguished from active/partial workspaces, or what happens on corrupt records and sweep permission failures. “Any invocation” also makes unrelated calls mutators of this store. Confidence: sure.

46. “a caller crashing between sweep and read loses the reason” supports incompatible orderings. The preceding sentence says `status` returns the record and “then sweeps,” in which case there is no interval between sweep and program read; the loss actually requires deletion before successful delivery to the caller. “Read” could mean filesystem read or caller receipt, and the recovery guarantee differs between them. Confidence: sure.

47. “A crash or lost connection at any moment therefore leaves one of two worlds: the commit is on main, or it is not and a stale workspace remains” is false. A crash before workspace creation can leave no per-digest workspace; a crash during screening can leave an unkeyed `screening-*` clone; and cleanup can remove the workspace before a response is delivered. These states are not recoverable through the stated digest workspace rule. Confidence: sure.

48. “absent means the leftover workspace is swept and the work runs fresh” is unsafe when an identical request is still running in that per-digest workspace. The specification has no liveness check before this sweep, so resubmission can destroy a live twin’s candidate and request record. Confidence: sure.

49. “a died-silently worker is a named, resubmittable state — never a forever-‘in-progress’” is too broad. A worker can remain alive but deadlocked, blocked indefinitely on I/O, stopped, or a zombie that still passes the chosen liveness test. PID plus start time distinguishes reuse but supplies no timeout or progress criterion, leaving a reachable permanent `in-progress` state. Confidence: sure.

50. “`cancel <digest>` — built in version 1” contradicts Implementation status, which says slice 4—including `cancel`—is “contract-only,” and the referenced program returns `unbuilt-option` for it. An agent cannot tell whether cancellation is available. Confidence: sure.

51. “Outcomes, exactly four” names four branches but only three outcome values: `too-late`, `cancelled`, and `unknown-request`; both live-worker and abandoned-workspace branches return `cancelled`. The acceptance index later says “T8 cancel: all three outcomes,” confirming the competing count. Confidence: sure.

52. “The cancel-versus-push race resolves by the push's atomicity: kill the worker, then ask history whether the digest made it” does not resolve a worker-child race. Killing only the recorded worker PID need not kill an already running `git push` child; the history query can return before that child updates main, after which `cancelled` has already been reported. No process-group kill, wait-for-termination, or final synchronization point is defined. Confidence: sure.

53. “The error catalog — every ending named, three-part teaching form” is false and internally incomplete. It omits the binding/implementation’s `unsafe-path`, omits parser termination and signals, and lists successful/informational answers that do not use the three-part refusal form. The current implementation also still emits retired names such as `missing-message`, `empty-change`, `unknown-base`, and several import-specific names. Confidence: sure.

54. “infrastructure refusals warrant bounded, backed-off retries at the caller's judgment” assigns repeated work without stating either bound, delay progression, or terminal condition. Different agents can retry once, indefinitely, or immediately while all following the text. Confidence: sure.

55. “`unbuilt-option` ... resubmit without the option” is not executable for the `status` and `cancel` subcommands. Removing the subcommand does not produce a valid request or answer the caller’s question, and a status-only caller may not possess the original work needed for a new check-in. Confidence: sure.

56. “The autonomy standard, met: no unnamed endings; every refusal teaches; resubmit always safe” is contradicted by parser exits, signals and crash states, unspecified store failures, the unresolved live-twin sweep, and stale-content resubmission. It declares completion of guarantees the document itself does not establish. Confidence: sure.

57. “a protection change by any owner is a deliberate, visible act, never a standing path” is broader than account control can ensure. A compromised owner token, automation using owner credentials, or accidental API action is neither necessarily deliberate nor caught while active; “visible” also has no named log, viewer, or retention mechanism. Confidence: sure.

58. “Issues need no repository grant beyond an authenticated GitHub account” supports incompatible scopes of “issue” work. Creating a public issue or comment may require no repository role, while editing, closing, labeling, assigning, or managing issues does; the immediately following `issues:write` grant suggests the broader scope. Confidence: unsure because the exact issue operations intended by “the machinery” are not named.

59. “Blast radius of a stolen token: commits to this one repository, nothing else” is unsupported by the defined dedicated account. A repository collaborator with write permission can ordinarily manipulate branches and may have other repository capabilities, while the main-capable token’s exact fine-grained permissions are never stated. Token storage, expiry, rotation, revocation, and account recovery are also absent from this credential mechanism. Confidence: sure.

60. “on one machine every process of one Unix user reads the same credential files” is an overbroad literal claim. Processes can be sandboxed, subject to mandatory access controls, lack access to a keyring or agent socket, or encounter credential files with different ownership; sharing a UID generally grants potential filesystem access, not automatic reading. Confidence: sure.

61. “agents invoke the program through a sudoers rule scoped to exactly it” leaves “it” ambiguous between the dedicated user and the program. No sudoers command shape, permitted arguments, environment handling, credential/helper configuration, or protection against alternate interpreters is given. This is the stated security boundary, so the missing scope prevents its implementation or audit. Confidence: sure.

62. “The copy keeps itself current from main automatically (no manual deploy step; a checked-in fix is live on the next call)” defines a privileged self-update mechanism without specifying update order, ref verification, atomic replacement, concurrency, rollback, interrupted-update behavior, or which code performs the update. A root-owned running copy cannot simply become the next main version without one of those unprovided transitions. Confidence: sure.

63. “changes reach main only with walked-approval evidence, enforced by the review-evidence check (slice 6)” conflicts with the missing evidence request field, the “Open” statement that its format is undesigned, and the ambiguous implementation status. It cannot presently justify the self-update safety claim. Confidence: sure.

64. “a stale copy enforces the old contract and can never be made to run agent-written bytes ... a lag in self-update costs availability, never safety” is false. The old contract may contain a security defect, may predate the evidence check, and may self-update to code authored by an agent after gate approval; review evidence does not make the bytes non-agent-written. Staleness of authentication or path validation code can directly affect safety. Confidence: sure.

65. “project-wide: a deployed copy of anything keeps itself current from its source automatically” is an overbroad absolute and conflicts with “Scope ends at main,” which assigns deployment to a later DevOps/CI design. Ordinary counterexamples include schema-coupled services, firmware, or multi-component releases that cannot safely self-update independently. Confidence: sure.

66. “discipline lives at the skill and hook rung” and “a PreToolUse hook rewrites `gh` calls ... through the project's wrapper” name no skill, hook path, settings entry, or wrapper path and do not define “disciplined form.” Slice 5 therefore cannot implement this promised cooperative layer from the document and its explicit references. Confidence: sure.

67. “files prefilled from the agent's own staging” conflicts with the gatekeeper reading declared bytes from the working tree rather than the index. An unstaged edit inside a staged path rides into the candidate even though the template was derived from staging; conversely, an intended unstaged path is omitted. The declaration source and content source can describe different changes. Confidence: sure.

68. “the program stays one standard-library-only file precisely so any historical version is directly runnable” is false. It also depends on an installed compatible Python, Git executable, repository layout, remote behavior, credentials, sudo policy, and historical data formats. A one-file source layout does not make every historical revision directly runnable in the current environment. Confidence: sure.

69. “a check-in the gate wrongly refuses uses a sudoers entry requiring the user's password, approved in the moment” does not state which executable/version is authorized, how the refused content is supplied, which credential is used, how the resulting commit is marked, or when access closes. The break-glass lane is therefore named but not executable or auditable. Confidence: sure.

70. “a foreign remote dies at GitHub's authentication because the credential is scoped to this one repository” is false for the permitted `--remote` seam. Git accepts a local bare-repository path or another credential-free transport, and the referenced program passes the value directly to `git clone` and later pushes to that clone’s origin. Such a remote does not reach GitHub authentication at all. Confidence: sure.

71. “Process-level ordering needs no lock: the atomic push arbitrates” ignores the non-push shared state keyed by digest. Identical requests, status collection, cancel, refusal consumption, and expiry sweeping all race over the same workspace before or after any push. Atomic ref update cannot arbitrate those filesystem operations. Confidence: sure.

72. “The raw-push residual is detected at its source, not prevented: a standing branch-protection audit...” is wrong. The described audit checks protection configuration, not commit provenance; an authorized agent can raw-push while protection remains correct and the audit will return `protection-ok`. The trailer-less-history detector that could detect the resulting commit is explicitly deleted. Confidence: sure.

73. “at each handoff scrub (the cleanup pass every agent session runs when handing off)” is un-executable from this checkout context and conflicts with the explicitly referenced `fast-handoff-design.md`. That design says the old scrub modes were superseded and that full manual scrubs died with the committed tier; CLAUDE.md contains no universal handoff cleanup pass. The audit consequently has no valid invocation cadence. Confidence: sure.

74. “an agent-held owner credential could deliberately edit protection — same catch” is too broad. An agent can change protection, push, then restore the original settings before the next handoff audit; the configuration-only detector sees green and catches nothing. Confidence: sure.

75. “once C2/C3 apply, a trailer-less commit can arise only from break-glass ... or from a protection failure” omits ordinary cases such as a gatekeeper defect or malicious gatekeeper revision that writes a malformed/trailer-less commit, theft of the dedicated pusher token while protection remains correct, and GitHub-side administrative bypasses. The deleted detector therefore has unacknowledged residual inputs. Confidence: sure.

76. “The subsystem token set (the project's planned controlled vocabulary of subsystem names, founding plan) starts empty” introduces an unnamed plan, undefined “subsystem,” and undefined controlled-vocabulary store. “A real subsystem set exists” supplies no observable trigger for the deferred naming-hygiene work. Confidence: sure.

77. “Transcripts + git history already record everything” and “`status` derives from history” conflict with the specification’s own request workspace, PID, in-progress/abandoned state, and retained refusal records. `status` explicitly derives several answers from the workspace, not history. Confidence: sure.

78. “the procedural gap is audit-detected (that audit itself deleted 2026-08-10)” invalidates its own rationale. The surviving protection audit does not detect authorized raw pushes, while the detector that could inspect trailer absence was deleted. The text does not identify another audit that detects the gap. Confidence: sure.

79. “The legacy system's `git-clean-slate-plan.md` (read-only reference, `~/Projects/nedlern/docs/working/proposed/`)” names a path that does not exist in this environment; the referenced build plan explicitly records that `~/Projects/nedlern` is absent. The classifications asserted from that source cannot be verified by the future context this document promises. Confidence: sure.

80. “the rewrite policy (founding plan § Standing decisions), in its four-class vocabulary” does not identify the founding plan by path or define `update-feature`, `remove-feature`, `preserve-feature`, and `consider-feature`. The classification record is therefore not understandable without undocumented project history. Confidence: sure.

81. “The repo's git config is minimal and stated here” is not executable as written. It supplies no literal `user.name` or `user.email`, omits the full `user.useConfigOnly` key/value, does not identify local versus global scope, and gives no application or audit procedure. Confidence: sure.

82. “T1 every form error refuses with its named error and no side effects” contradicts mandatory on-disk screening, the caller-checkout fetch, and opportunistic refusal-record sweeping. It also cannot cover the claimed current implementation because parser errors do not use the named JSON refusal channel and `unsafe-path` is absent from this specification’s catalog. Confidence: sure.

83. “T5 conflict: same-content collision refuses” conflicts with duplicate detection. If “same-content” means the same work, the expected result is `already-checked-in`; if it means different content touching the same path, the phrase is wrong and omits the distinguishing condition. The test cannot be implemented unambiguously. Confidence: sure.

84. “T8 cancel: all three outcomes” contradicts the earlier “Outcomes, exactly four.” The earlier paragraph has four branches but three distinct outcome strings, and T8 does not say whether it covers branches or strings. Confidence: sure.

85. “The walked-approval evidence format ... undesigned; slice 6 waits on it” conflicts with the implementation-status wording that places slice 6 after “BUILT,” and with the credential section’s present-tense claim that the check enforces gatekeeper-source approval. This open item makes privileged-lane readiness indeterminate. Confidence: sure.

86. “class definition, procedure, and guards on `nedschorus#31`” delegates essential normative content to an external issue rather than an explicit repository path. The issue could not be read from this checkout or through the available network, while this section labels the matter “Resolved.” Without it, an agent cannot identify every instruction-bearing artifact, produce evidence, or evaluate the guard. Confidence: sure.

87. “The check itself is slice 6, scheduled 2026-08-10” is stale relative to `design-as-of: 2026-08-11` and does not say whether the scheduled work happened, slipped, or was blocked by the still-undesigned format. Combined with the contradictory status statements, it provides no stopping state for slice 6. Confidence: sure.

clean sections: Cross-spec consequence (resolved)
