---
status: specification
design-as-of: 2026-08-09
---

# git-gatekeeper (specification)

**Implementation status:** branch protection and the account layout are LIVE (applied 2026-07-21; layout amendment ruled 2026-08-09, § The credential and enforcement, not yet applied). `scripts/git-gatekeeper.py` is BUILT through slice 3 of five (2026-08-08/09, per the build order in `docs/issues/3-git-gatekeeper-build-slice-plan.md`): the synchronous check-in, the entry checkpoint with the `imports` query, and concurrent-check-in integration are running behavior, exercised by a 146-case suite against throwaway repositories. Slices 4 (worker lifecycle: `--no-wait`, `status`, `cancel`) and 5 (the audits, repo git config, CLAUDE.md workflow lines) remain contract-only; reaching an unbuilt part is the named refusal `unbuilt-option`, never a crash. The gate is **dormant**: no host yet holds a main-capable credential for it (§ The credential and enforcement).

This revision (2026-08-09) folds in: the two pending amendments from the 2026-07-30 bindings walk (the refused `--no-wait` workspace retains a JSON refusal record, `status` returns it once then sweeps; the branch-protection audit's three named outcomes); the `Gatekeeper-agent` trailer (B6, boss-ruled 2026-07-31); and the credential rulings of 2026-08-09 (`docs/issues/queue/3-gatekeeper-credential-and-hook-bindings.md`, C1–C8 — the dedicated identity admitted early, the Unix-user boundary, scoped agent tokens, break-glass, the cooperative hook tier). The 2026-07-24 boss-walked core — request/reply, digest, trailers, concurrency, states, error catalog — is unchanged by all of this. Supersedes remain as before: the promotion-relay design, the entry-manifest append-a-row rule, the retired "land"/"landing" vocabulary.

How a change reaches main in nedschorus. **Scope ends at main** (boss-ruled 2026-07-24): deploying main to production is a separate DevOps/CI concern, designed when the first long-running process exists — until then main is production coincidentally, not by this design's doing. Ordinary changes use no branches and no pull requests.

## The job and the guarantee

One program, `scripts/git-gatekeeper.py`, is the only way any change reaches main. It holds the project's one push-capable credential. Agents — all of them, equally — invoke the program directly and never push themselves. One program, one credential, one door. No agent has a doorman or relay role in another agent's check-in path; choirmaster is simply the most frequent requester.

For each request the program does exactly one of two things: **checks the work in**, or **refuses and teaches the fix**.

On success, four things are guaranteed true:

1. The change is on main, pushed to GitHub.
2. The checks ran against exactly the content that was pushed.
3. The commit's trailer lines carry the whole machine-readable record (see § The trailer).
4. The requester has the answer: success plus the commit id.

On refusal, the reply always has three parts, like a well-built MCP tool — never a bare error code: the **named error** from the fixed catalog, the **specific facts** (which file, which check, which mismatch), and the **exact next action, written for an agent to execute**. The repository is untouched — a refusal has no side effects at all.

**Records:** git history and the invoking session's ordinary transcript are the *only* records. No side files, no separate logs — the invocation is a normal tool call, already recorded where tool calls are recorded.

**Resubmitting is always safe.** Same request, same answer; a fixed request digests differently and processes fresh; work that already went through answers `already-checked-in <commit>`. An agent that crashed or lost its connection never reconstructs what happened — it submits again and the program sorts it out. Refusals teach, retries are free: the loop self-heals, which is what near-perfect autonomous operation requires.

## The request and the reply

```
git-gatekeeper.py check-in
    --files <path> [<path> ...]
    --message "<one-line summary of what and why>"
    --base <full-40-hex-commit-id>
    --import none | --import-commit <id> --import-source <path> --import-dest <path>
    --issue none | <issue-number>
    --agent <runtime/model>
    [--wait | --no-wait]          (default: --wait)
```

Field by field, with exact validation (all form validation is instant and synchronous in both modes; every refusal names its error and the fix):

1. **`--files`** — repository-relative paths, normalized: no absolute paths, no `..`, nothing under `.git/`, no duplicates, list non-empty. The new content of each path is read from the invoking agent's working copy — the program's *only* read of that worktree. Per path the change is inferred: **added** (absent at base, present in worktree), **modified** (differs), **deleted** (present at base, absent in worktree). Refusals: `unknown-path` (in neither place — a typo), `unchanged-path` (declared but identical to base — declarations must be honest), `empty-change` (nothing differs at all).
2. **`--message`** — the human-readable what-and-why; becomes the commit message body above the trailers. Required, non-empty (`missing-message`). Intent lives with the author; it cannot be auto-filled.
3. **`--base`** — the full 40-character commit id of the main state the work started from. No abbreviations (short ids can turn ambiguous as history grows), no branch names (they move). Must exist and be on main's history (`unknown-base` / `base-not-on-main`).
4. **`--import`** — `none`, or all three parts: the legacy commit id, the source path (must exist in the legacy repository at exactly that commit — `import-source-missing`; legacy checkout unreadable — `legacy-unreadable`), and the destination (must appear in `--files` — `import-dest-undeclared`). One or two parts of three: `import-incomplete`. A second import is inexpressible by construction — it is a second check-in.
5. **`--issue`** — `none` or a positive integer. Version 1 validates syntax only. The artifact-lifecycle rule decides *upstream*, at the right granularity, which work has an issue; the gatekeeper only records the answer. `none` is honest for trivial work — an issue is never mandated per invocation (issues hold wanted things, not logs).
6. **`--agent`** — the runtime and model that produced the change (for example `claude-code/opus-5`), required and non-empty (`malformed-field`). Declared by the caller because the environment names the runtime but not the model, and the model is the half the fix ladder needs ("who last wrote this" becomes one `git log` away). Cooperative class: the gatekeeper records what it is told and never guesses.
7. **Origin** — auto-filled from the session environment; recorded as `none` when absent, never blocking (a transcript-less caller is honest, not an error). Meaningful because our agents are long-lived: the session id points at a readable transcript of intent.
8. **The digest** — SHA-256 over: base id + sorted path list + each path's new bytes (deletions as a marker) + the import triple. Deliberately excluded: message, issue, mode, origin, agent, time — the digest identifies **the work**, so identical work resubmitted under different metadata still deduplicates. Computed by the program; callers generate nothing.

**The reply.**

Every invocation prints exactly one JSON object on stdout: `{outcome, error?, facts?, next_action?, commit?, digest?, summary}`, where `summary` is the human-readable line — one format, not two (B1). Exit codes: **0** success and informational answers; **1** catalog refusal (the gatekeeper working); **2** program defect — distinct so loop counters and the audit never read a gatekeeper bug as a correct refusal.

- Waiting caller, success: `checked-in <commit-id>`, exit 0; when the race was lost and re-application was clean, the reply also carries `integrated_over: <n>`.
- Non-waiting caller: instant `accepted <digest>` once form is valid; the outcome is collected later with `status <digest>` (`next_action` says exactly that).
- Any refusal: the three-part teaching form, exit 1.
- `status <digest>` answers from what already exists (history plus the program's workspace): `checked-in <commit>`, `in-progress`, `abandoned` (workspace present, worker dead — resubmit safely), or `unknown` ("no trace; submit it" — always safe).
- `cancel <digest>` — see § States, crashes, cancel, and errors.
- `imports` — prints the import table derived from history (every `Gatekeeper-import` trailer on main): what was imported, from which legacy commit, to where, when. This derived view replaces the retired entry-manifest row rule; `entry-manifest.md` remains as the founding-era historical record only.

## The procedure

1. **Submit.** The agent invokes the program with the request and its mode choice.
2. **Instant screening — synchronous in both modes.** Form validation (above). The digest is computed and looked up in history right here: already present answers `already-checked-in <commit>` with no work done. A non-waiting caller gets `accepted <digest>` now; everything after runs identically either way.
3. **Build the candidate.** In the program's own private workspace (`<workspace-root>/<digest>/`) — never the agent's worktree — start from main *at the declared base* and apply exactly the declared changes. Unchanged files come from main, never from the agent's possibly-stale copies. A declared import happens here: copy from the legacy repository at the declared legacy commit; record the source for the trailer.
4. **Run the checks** (§ Constructive guarantees) against the candidate — the literal bytes that would become main.
5. **Commit.** The message, then the trailer lines.
6. **Push.** Happy path: main has not moved since the base; the push succeeds. Main moved: § Concurrent check-ins.
7. **Answer.** The waiting caller gets its line; the non-waiting caller's outcome now sits in history where `status` finds it. The workspace is deleted.

The requester's own working copy is never modified; the agent refreshes from main at its convenience.

## Constructive guarantees, the advisory, and the growth point

Most classic gate failures are made impossible by construction rather than detected:

- **Stray changes cannot enter** — the candidate is built *from* the declaration; an undeclared edit never reaches it.
- **The record cannot be missing** — the program writes the trailers itself.
- **The import record cannot lag** — written during candidate construction, same commit.
- **Duplicates cannot apply** — the digest screen runs at submit.

**One advisory (not a refusal):** if the agent's worktree contains modified files *beyond* the declared ones, the reply carries a note — "worktree also differs at `x`, `y`; confirm intentional" — because the likeliest cause is a forgotten declaration. Unrelated work-in-progress in the same worktree is legitimate, so this never blocks.

In version 1, between screening and push, **no refusal remains** — this stage is deterministic construction and recording. That is the growth point, not a hole: when a test suite exists, the tests run here; when the boss gates an artifact class, its review-evidence check runs here (the request format grows its evidence field then, not before).

## The trailer

```
Gatekeeper-origin: <session-id> | none
Gatekeeper-agent: <runtime/model>
Gatekeeper-digest: <sha256-of-the-work>
Gatekeeper-import: none | <legacy-commit> <source-path> -> <destination-path>
Gatekeeper-issue: none | #<issue-number>
```

Four facts and a pointer; nothing else. The agent line (B6, boss-ruled 2026-07-31) names the runtime and model that produced the change, literal value, never omitted — the fix ladder's escalation needs to know what tier produced an artifact to know whether stronger models remain. The digest line is the **duplicate-detection key**, not provenance — it is what makes resubmission safe. The issue value is written in `#<n>` form deliberately: any commit reaching the default branch with `#<n>` in its message appears automatically in that issue's GitHub timeline, so **an issue collects all its check-ins with zero machinery**. The same collection is derivable offline (`git log --grep "Gatekeeper-issue: #<n>"`). Refusals and other responses are **never** auto-posted to issues — mechanical chatter stays in transcripts; a genuinely blocking outcome earns a judgment-written comment by the requesting agent (revision convention: comments are for genuinely new events).

## Concurrent check-ins

Everything rests on one property GitHub provides: **a push either wins cleanly or is rejected whole** — never partial, never interleaved. GitHub is the arbiter; exactly one request wins any race. No queue and no lock are built; check-ins run in parallel by default (boss ruling).

- **The winner** completes the procedure, unaware of the race.
- **The loser** — handled by the program, not the agent: fetch the new main; rebuild the candidate by re-applying the declared changes onto it. **Clean re-application** (the usual case — different files): re-run the checks against the rebuilt candidate (version 1 re-runs everything; cheap while checks are fast) and push again; the reply notes "integrated over N newer commits." **Real conflict** (the new main touched the same content this request changes): re-applying would require guessing the author's intent, and the program never guesses — refuse with `conflict`, naming the files, the intervening commits, and the next action: update from main, adjust, resubmit (the adjusted work digests fresh, correctly).
- A request submitted from a behind-main worktree is the same mechanism — being behind is just "main moved before we started."
- **Bounds, both named:** the retry loop is capped at five rounds, then `main-moving-too-fast` (refuse rather than spin). And the accepted gap, recorded: changes in *different* files that interact *semantically* pass silently until tests join the checks.
- **Deferred optimization, trigger named:** when checks become slow (a real test suite), re-validation narrows to checks whose inputs intersect what actually changed between bases (impact analysis), so trivial head movement — ledger marks, log commits — never invalidates a pending check-in (boss ruling). A merge queue (batch-validating several queued requests against the projected combined result) is the rung above that, if volume ever demands it.

## States, crashes, cancel, and errors

**States:** SCREENING (synchronous, in memory, nothing on disk) → WORKING (candidate built and checked, inside `<workspace-root>/<digest>/` — concretely `$XDG_STATE_HOME/nedschorus-gatekeeper/<digest>/`, default `~/.local/state/...` (B4a): outside every repository, discoverable from the digest alone, holding the candidate clone, `worker.pid`, and the resolved request record (B4c: every environment-derived field, origin foremost, is resolved at screening into that record; the worker only reads it, never re-derives) → PUSHING (atomic attempt, retry-capped) → **CHECKED-IN** or **REFUSED**. After either ending the workspace is deleted, with one exception (B4d): a refused `--no-wait` request keeps its workspace holding just the JSON refusal record; `status` returns it once, then sweeps. Named residual (accepted): a caller crashing between sweep and read loses the reason — rare, recoverable by resubmit. Durable traces: a checked-in request is its commit on main; a refused waiting request deliberately leaves nothing.

**Crash recovery — one rule, not a procedure.** The whole pipeline has exactly two durable effects: the workspace directory, and the atomic push. A crash or lost connection at any moment therefore leaves one of two worlds: the commit is on main, or it is not and a stale workspace remains. Recovery is: **resubmit**. The program checks the digest against history — found means `already-checked-in <commit>`; absent means the leftover workspace is swept and the work runs fresh. No journal, no repair mode. `status` distinguishes WORKING from **abandoned** (workspace present, worker process dead) via the recorded process id, so a died-silently worker is a named, resubmittable state — never a forever-"in-progress".

**`cancel <digest>`** — built in version 1 (boss ruling: the need arrives with slow checks, the machinery it needs already exists, and it is three branches). Any agent may cancel; there is no permission machinery — cooperative model; the workflow simply does not teach cancel as a routine move (and the author may be gone; authorship grants no special judgment). Outcomes, exactly three: digest already in history → `too-late — already-checked-in <commit>` (the remedy for a bad landed change is a **revert**: an ordinary check-in whose change undoes a previous one, through the same gate); live worker found → kill it, sweep the workspace, `cancelled`; nothing found → `unknown-request`. The cancel-versus-push race resolves by the push's atomicity: kill the worker, then ask history whether the digest made it. Cancel only makes sense before the check-in completes (boss ruling); after, revert.

**The error catalog** — every ending named, three-part teaching form:

- *Form (instant):* `malformed-field`, `missing-message`, `unknown-path`, `unchanged-path`, `empty-change`, `unknown-base`, `base-not-on-main`, `import-incomplete`, `import-source-missing`, `import-dest-undeclared`, `legacy-unreadable`.
- *Integration:* `conflict`, `main-moving-too-fast`.
- *Infrastructure:* `push-auth-failed`, `network-down`, `workspace-io-error` — all safely resubmittable.
- *Answers, not errors:* `already-checked-in <commit>`, `accepted <digest>`, `cancelled`, `too-late`, `unknown-request`.

**The autonomy standard, met:** no unnamed endings; every refusal teaches; resubmit always safe; nothing routes to the boss mechanically — he is consulted by agents' judgment, never by the machinery.

## The credential and enforcement

The dedicated-identity rung was **admitted early** (user-ruled 2026-08-09, exercising the trigger named below); the layout it replaces is recorded first because it is still the live state until the amendment is applied.

- **Branch protection, LIVE since 2026-07-21:** pushes to `main` restricted to the machine credential (`NedLern`) alone; enforce-admins on; force-push and deletion blocked. The org has two owners (`NedLern`; `NedLerner`, settings and emergency power, no push), so either account can recover the org if the other is lost; a protection change by any owner is a deliberate, visible act, never a standing path. The boss never commits directly; a boss-originated change is drafted with an agent and checked in like any other. Issues cost nothing: the repository is public, so opening and commenting needs no repository permission.
- **The layout amendment (ruled 2026-08-09, C1/C3 — applying it needs an org owner):** the pusher role moves to a **dedicated GitHub account** — a collaborator with write on this one repository, not admin, never an org owner — and protection's push restriction names it alone. Chosen over the App/CI form this section previously sketched: an App or CI job relocates the gate into CI, which this design scopes out; a plain account keeps the gate a local program. Blast radius of a stolen token: commits to this one repository, nothing else. Owner power stays with the user; no agent ever holds it.
- **The Unix-user boundary (C2) — where the enforcement actually lives:** GitHub restricts accounts, not processes, and on one machine every process of one Unix user reads the same credential files. So the main-capable credential is owned by a **dedicated Unix user**, unreadable by agent sessions, and agents invoke the program through a sudoers rule scoped to exactly it. That is the step at which "agents never push" becomes impossible rather than instructed; it also makes the gatekeeper literally an invocable service any agent on the box can call.
- **Agent credentials are scoped (C4):** each agent host holds a fine-grained token for this repository only — contents read/write (branch pushes are open; the push-less ruling covers main alone), issues write — never a classic all-repository token, and never the `workflow` scope (capability-by-landing class, nedschorus#31). Issue work is **scoped, not gated**: no invariant like "one writer to main" exists there, so discipline lives at the skill and hook rung, not at a gate.
- **The cooperative tier (C6), above the boundary and never a substitute for it:** a PreToolUse hook rewrites `gh` calls seamlessly into their disciplined form; a `git push` toward this repository's remote gets deny-with-exact-invocation instead — a push carries none of the declaration, and auto-deriving all of it would gut the intentionality the `unchanged-path` refusal exists to force. The check-in skill front-loads the declaration (`--files` from the agent's own staging, `--base` computed as the merge-base, message passed through verbatim), so the agent contributes only what it already does by training. Refusals teach, as the final tier.
- **Break-glass (C5) — an unlockable credential, never a standing ungated agent:** gate defects are recovered from the gate's own history — the program stays **one standard-library-only file** precisely so any historical version is directly runnable; a landing the gate wrongly refuses uses a sudoers entry requiring the user's password, approved in the moment; credential expiry and protection misconfiguration are org-owner territory, the user's alone.
- **Privileged invocations refuse the test seams (C7):** `--repo` and `--remote` exist so tests can hand the program throwaway repositories. Run as the credential-holding user, they are refused and the remote is pinned to the canonical repository; tests run unprivileged and keep the seams.
- **The honest singleton statement (boss ruling), still true until C2 is installed:** branch protection restricts the *account*, not processes — anything running as that account, on any machine, can push. Process-level ordering needs no lock: the atomic push arbitrates. What remains procedural before C2 is only that agents *use the program* rather than raw `git push`.
- **CLAUDE.md is documentation, never enforcement (boss ruling; his rationale verbatim: a python script does not read it, and different machines may carry different copies).** The same is true of harness hooks: they configure a harness, and only cooperating harnesses read them — which is why C6 is a convenience tier and C2 is the boundary. Nothing in this design depends on either. The raw-push residual is *detected*, not prevented: a standing audit at each handoff scrub scans main for commits missing valid trailers and files a `draft` issue naming them, with **three named outcomes** — `protection-ok` / `protection-wrong` (differing settings named) / `audit-failed` (gh missing, unauthenticated, API error) — failing loudly as its own outcome, never a silent skip into green (B3c). (The audit also covers the sibling residual while it exists: an agent-held owner credential could deliberately edit protection — same cooperative class, same catch; C3 removes that class by taking owner power out of agent hands entirely.)

## Deliberately not in version 1

| Cut | Why | Grows back when |
|---|---|---|
| Review-evidence field + check | No artifact class is gated | The boss gates a class |
| Naming-hygiene check | The subsystem token set starts empty — pure noise at founding | A real subsystem set exists |
| Entry-manifest append-a-row | Duplicates the trailer; a shared append file makes any two parallel imports always conflict | Never — the `imports` query is the view |
| Separate audit log | Transcripts + git history already record everything | Never — `status` derives from history |
| Caller-generated request ids | The content digest is automatic and retry-safe | Never |
| Footprint-scoped re-validation | Checks are fast; full re-run is cheaper than the machinery | Checks become slow (test suite) |
| Merge queue | Volume nowhere near needing it | Sustained contention at the retry cap |
| ~~Dedicated gatekeeper identity~~ | ~~Two agents, one machine; the procedural gap is audit-detected~~ | **Admitted 2026-08-09** (the boss-admits-it-early trigger) — § The credential and enforcement |

## Cross-spec consequence, awaiting the boss

RESOLVED 2026-07-24, then SUPERSEDED 2026-08-02 by the session-recycling revision of [fast-handoff-design.md](fast-handoff-design.md): recycling handoffs are machine-local and never checked in; the one committed handoff (the founding one) lands as an ordinary file. The files-written-to-disk-first principle survives inside the supervisor's cycle.

## Relationship to the legacy design

The legacy system's `git-clean-slate-plan.md` (read-only reference, `~/Projects/nedlern/docs/working/proposed/`) designed the many-writer version of this problem. This design keeps only two of its ideas, re-derived: workflow rules expressed as CLAUDE.md documentation, and protection-as-lock reduced to one credential. Never imported: the three GitHub Apps, the credential helper, per-agent branches, the PR pipeline for ordinary work, the parking states. The repo's git config is minimal and stated here, not imported: `user.name`/`user.email` for the machine identity, `useConfigOnly` so no global identity leaks in.

## Build slice (choirmaster task 1)

The git config above + `git-gatekeeper.py` with `check-in`, `status`, `cancel`, `imports` + the CLAUDE.md workflow lines + tests:

T1 every form error refuses with its named error and no side effects · T2 happy path: the four success guarantees verified, trailer exact · T3 digest: identical resubmit answers `already-checked-in`; changed content digests fresh; metadata-only changes do not change the digest · T4 concurrent submissions (injected delay): winner clean, loser integrates over newer commits and succeeds · T5 conflict: same-content collision refuses with files + commits + next action · T6 retry cap: sustained head movement ends in `main-moving-too-fast`, never a spin · T7 crash recovery: worker killed mid-WORKING → `status` reports abandoned, resubmit sweeps and completes; killed after push → resubmit answers `already-checked-in` · T8 cancel: all three outcomes; cancel-after-push answers `too-late` · T9 advisory: undeclared worktree changes noted, never blocking · T10 `imports` derives the exact table from trailers · T11 each import error class refuses correctly · T12 a raw push (simulated) is caught by the trailer-absence audit.

## Open

- Which artifact classes, if any, are gated on review evidence from day one — the first class is now designated (boss-ruled 2026-08-04): instruction-bearing text (CLAUDE.md files, skills with their prompt templates, injected system prompts, the wiki), whose check-ins require walked-approval evidence; class definition, procedure, and guards on [nedschorus#31](https://github.com/nedschorus/nedschorus/issues/31). The check itself is built with the gatekeeper (slice 6 of the build order, unscheduled until the approval-evidence format exists).
- **Cross-machine callers (C8):** the gatekeeper reads declared content from the caller's worktree, which requires a shared filesystem; Mac-side agents cannot be read from the Ubuntu box. Candidate shapes, none chosen: the caller pushes its branch and the request names a ref instead of relying on worktree bytes (a real contract change); Mac agents route work through the Ubuntu side; or a second credentialed host (weakens the single-place property of C2). Decide when a Mac-side agent first needs direct check-in.
- (resolved) The fast-handoff S2 interaction — see § Cross-spec consequence.
