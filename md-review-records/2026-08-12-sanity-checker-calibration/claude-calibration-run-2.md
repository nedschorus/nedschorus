<!-- provenance: runtime=claude model=claude-fable-5 cell=sanity-checker (draft prompt with run-1 fixes: log-machinery lesson, broken-mechanism rule) run=calibration-2 target=git-gatekeeper-design.md at commit 0890848; same inputs and isolation as run 1 -->

I have read all four documents. Two links from the document set point outside it and were not provided, so I note rather than chase them: `entry-manifest.md`, `git-clean-slate-plan.md`, and — cited normatively by the slice plan — `docs/issues/queue/3-gatekeeper-build-bindings.md` (B1–B6; my B-numbered quotes come only from the spec's and plan's restatements), plus `.claude/hooks/instruction-file-guard.py`, `.claude/skills/handoff/SKILL.md`, `docs/drafts/handoff-skill-draft.md`, the named scripts, and the GitHub issues (#3, #13, #18, #27, #31, #40, #45). Nothing below depends on their contents except where stated.

# Sanity-check report: `git-gatekeeper-design.md`

The design's core — one program, digest dedup, construct-from-declaration, atomic-push arbitration, resubmit-heals-everything — is unusually lean and I certify most of it below. The findings concentrate at the periphery: two stale/duplicated normative homes, two declared fields that code can derive, one dead trigger, and one under-specified boundary (F4, the weightiest finding here — the C2 mechanism as written does not yet deliver the guarantee the document claims for it).

## Findings

### F1 — Delete § Cross-spec consequence and its "Open" echo (rung: Delete)

**WHAT** — Delete the section "## Cross-spec consequence, awaiting the boss" and the Open-list line "(resolved) The fast-handoff S2 interaction — see § Cross-spec consequence", leaving at most a one-line pointer to `fast-handoff-design.md`.

**WHY** — The heading says "awaiting the boss"; the body says "RESOLVED 2026-07-24, then SUPERSEDED 2026-08-02 by the session-recycling revision of [fast-handoff-design.md]". A resolved item sitting under both a false heading and an "Open" list is a dead distinction. Its normative content already has a home: fast-handoff-design rules "Handoffs are operational, machine-local, disposable" and "The founding handoff is written by the founding pair, committed as an ordinary file" — restating it here is a duplicated normative home that will drift.

**LOST** — The in-document trace of how the interaction resolved (recoverable from git history, which the design itself declares sufficient: "git history and the invoking session's ordinary transcript are the *only* records"). Pays into priority 2.

**CONSEQUENCES** — The Open list shrinks by one line; no other sentence in the four documents references § Cross-spec consequence; no test touches it.

### F2 — Declare which document now governs C1–C8 (rung: Delete — duplicated normative home)

**WHAT** — Record the handoff of authority between the spec and the bindings doc: either add `3-gatekeeper-credential-and-hook-bindings.md` to the spec's supersedes list, or state in the spec that the C1–C8 fold is provisional pending the rewalk. Exactly one document should govern.

**WHY** — The bindings doc says "until the spec is updated at that walk, this document governs these points" and "The design rewalk is where each ruling gets confirmed against the whole." The spec's 2026-08-09 revision "folds in … the credential rulings of 2026-08-09 (docs/issues/queue/3-gatekeeper-credential-and-hook-bindings.md, C1–C8 …)" — but its supersedes list still reads "Supersedes remain as before: the promotion-relay design, the entry-manifest append-a-row rule, the retired 'land'/'landing' vocabulary." From these four documents I cannot tell whether the rewalk happened; that ambiguity is the finding. Two live normative homes for the enforcement periphery is exactly the drift class this project hunts.

**LOST** — Nothing; one sentence in each document. Pays into priority 2.

**CONSEQUENCES** — The bindings doc gains a status line (or the spec header gains a "provisional" marker); the spec's citation of the bindings doc stays as provenance. No tests affected.

### F3 — Replace B4d's return-once-then-sweep with keep-until-resubmit (rung: Delete). **Collides with a recorded ruling** — B4d is a walked amendment ("the two pending amendments from the 2026-07-30 bindings walk"); flagging, not re-litigating.

**WHAT** — A refused `--no-wait` request's JSON refusal record persists until the digest is resubmitted (the existing sweep path) rather than "`status` returns it once, then sweeps."

**WHY** — The spec: "a refused `--no-wait` request keeps its workspace holding just the JSON refusal record; `status` returns it once, then sweeps. Named residual (accepted): a caller crashing between sweep and read loses the reason — rare, recoverable by resubmit." The sweep-after-one-read makes `status` non-idempotent — against the design's own ethos, "Resubmitting is always safe. Same request, same answer" — and is the sole source of that named residual. The sweep path for lingering workspaces already exists: "absent means the leftover workspace is swept and the work runs fresh." Reusing it deletes both the special case and the residual with zero new machinery.

**LOST** — Guaranteed cleanup after one read: a refused-and-never-resubmitted `--no-wait` workspace (one small JSON file) lingers until some later sweep. Pays into priorities 1 (idempotent `status`, residual gone) and 2 (one fewer state-machine exception).

**CONSEQUENCES** — Spec § States: the B4d sentence and the "Named residual (accepted)" sentence are rewritten; header line "the refused `--no-wait` workspace retains a JSON refusal record, `status` returns it once then sweeps" is stale; "After either ending the workspace is deleted, with one exception (B4d)" — the exception's lifetime changes. Slice plan: "the refusal record B4d (4)" scope line survives, its behavior differs. No numbered test covers B4d in either document, so no test changes.

### F4 — Complete C2: the sudoers boundary as written does not yet make the guarantee mechanical (rung: Externalize/Verify — the highest-stakes finding here)

**WHAT** — Specify three things the Unix-user boundary needs before it is real: (1) the sudoers rule must point at an **installed copy of `git-gatekeeper.py` unwritable by agent users** — never the repo working-copy path — plus the update path for that copy (itself a gate landing followed by a privileged install step); (2) how the session id survives `sudo` (env_keep for `CLAUDE_CODE_SESSION_ID`, or an explicit pass-through), else origin silently degrades; (3) how the gatekeeper user reads across the boundary it erects — the caller's worktree, and (if F6 lands) the caller's transcript.

**WHY** — C2 claims "That is the step at which 'agents never push' becomes impossible rather than instructed," via "a sudoers rule scoped to exactly it." But the program lives at `scripts/git-gatekeeper.py` in a checkout agents write to; a sudoers rule naming that path lets any agent edit the script and run arbitrary code as the credential-holding user — the boundary would be void at the moment it is installed. Second, sudo's default env_reset strips the environment, and field 7 says origin is "auto-filled from the session environment; recorded as `none` when absent, never blocking" — so post-C2 every commit would silently record `Gatekeeper-origin: none`, a designed-in silence that here hides a regression. Third, field 1 requires reading "from the invoking agent's working copy"; the bindings verified the credential is private ("`~/.config/gh/hosts.yml`, mode 600, owner `nedlern`") but nothing verified the reverse direction — a 700/750 home directory blocks the gatekeeper user from the very worktree bytes the contract depends on. None of the three contradicts C2's ruling; they complete it.

**LOST** — Nothing given up; this adds a small amount of named mechanism (an install location, one sudoers option, a permission grant or the C8 ref shape). Pays into priority 1 — it is the difference between the boundary being mechanical and being decorative.

**CONSEQUENCES** — Spec § The credential and enforcement (C2 bullet) and bindings C2 gain the installed-copy, env_keep, and read-path specifications; C5's "any historical version is directly runnable" stays true (break-glass entry 2 is password-mediated, so pointing it at an arbitrary file remains user-approved); C7's pinning applies to the installed copy. No existing test covers C2 (the 146-case suite runs unprivileged by design), so none break; a live-installation check is worth adding to slice 5's scope.

### F5 — Re-home the audit's dead trigger: "each handoff scrub" no longer exists (rung: Externalize — repair, per the broken-mechanism rule)

**WHAT** — Bind the trailer-absence/branch-protection audit to a trigger that exists — the natural home is the supervisor's recycle cycle, beside its queue-status step — and fix the spec's wording.

**WHY** — The spec: "a standing audit at each handoff scrub scans main for commits missing valid trailers and files a `draft` issue naming them." But fast-handoff-design superseded scrubs: "The superseded machinery — … the scrub modes … — is recoverable at `git show e178e67:…`" and "(full manual scrubs died with the committed tier …)." The audit's named trigger is dead. Per the broken-mechanism rule I checked for dependents before proposing deletion, and they exist: T12 ("a raw push (simulated) is caught by the trailer-absence audit"), B3c's three named outcomes, and slice 5's deliverable row — so repair, not delete. The supervisor's step 5 already runs exactly this shape of duty: "computed by script: the artifact-lifecycle rot-visibility duty riding every recycle at zero agent cost." (Alternative home, noted for triage: run the audit inside each gatekeeper invocation — but the residual it detects matters precisely when the gate is being bypassed, so the recycle cadence is the safer host.)

**LOST** — Nothing; the audit keeps its outcomes and consumer (the draft issue). Pays into priority 1 — a detection duty attached to a retired mechanism fires never. One coupling is added: fast-handoff-design's supervisor step list gains the audit, which is a change to a second walked document.

**CONSEQUENCES** — Spec line "at each handoff scrub" rewritten; slice 5's row unchanged in substance; fast-handoff § The recycle cycle gains a step (its supervisor test list — "kill → extract → launch ordering… queue-status line" — would grow one case); T12 unchanged in what it asserts, changed in when it runs.

### F6 — Derive the `Gatekeeper-agent` model from the origin transcript; keep `--agent` as override (rung: Encode). **Collides with recorded rulings** — B6 (boss-ruled 2026-07-31) and D3; flagging, not re-litigating.

**WHAT** — When origin is present, the program resolves the model mechanically by reading `message.model` from the newest assistant record of the session transcript (ID-keyed lookup, the pattern the handoff extractor already uses); `--agent` becomes an optional override, required only when no transcript exists. B6's "never omitted" is preserved: refuse when neither source yields a value.

**WHY** — D3's premise — "The caller is the only party that knows which model it is" — is contradicted by a verified fact in the companion spec: "Every assistant transcript record carries `message.usage` … and `message.model`; … computable from the transcript alone, in any session | probe 2026-08-06." Field 6 admits the declared value is unreliable: "Cooperative class: the gatekeeper records what it is told and never guesses" — yet the fix ladder consumes this value ("the model is the half the fix ladder needs"), so a wrong declaration poisons escalation decisions. Deriving it is the same move as the design's own division-of-labor rule, C6: "the agent contributes only what it already does by training …; the machinery derives or auto-fills everything else (base, session origin, digest, issue trailer form)" — the agent line belongs in that list. This is the accepted-precedent shape: the same exact fact, delivered by mechanism instead of habit.

**LOST** — Two real cases: work drafted by a subagent on a different model (transcript names the invoking session's model — the override covers it, but only if used), and transcript-less callers (must still declare). Post-C2 the transcript read crosses the user boundary — F4's item (3) must cover it. Pays into priority 1.

**CONSEQUENCES** — Request grammar (`--agent` required → optional); field 6's rationale sentence ("Declared by the caller because the environment names the runtime but not the model"); § The trailer's "literal value, never omitted" (still true, differently sourced); D3 in the slice plan rewritten entirely; `malformed-field`'s example case changes; T2's trailer-exact assertion changes its expected source; slice-plan item 5 ("including B6's `Gatekeeper-agent` line") unchanged in substance.

### F7 — Compute `--base` in the program by default; keep the explicit field as override (rung: Encode). **Collides with the walked core** — field 3 is inside "The 2026-07-24 boss-walked core — request/reply, digest, trailers, concurrency, states, error catalog — is unchanged by all of this"; flagging, not re-litigating.

**WHAT** — When `--base` is omitted, the program computes it as the merge-base of the caller's worktree HEAD and main — one git command in the worktree it already reads — and records the resolved value in the request record per B4c. The explicit field remains for deliberate overrides.

**WHY** — The design already classifies base as machinery-derived, but houses the derivation in the cooperative tier: C6 has the skill compute "`--base` computed as `git merge-base HEAD origin/main` (the branch point GitHub used to compute for free)", and the division-of-labor line lists "base" among what "the machinery derives or auto-fills." A hook-tier derivation reaches only hook-carrying harnesses; every other caller must hand-produce "the full 40-character commit id" — a fact "quickly and easily computed … from the primary source." Moving the one command from skill to program serves every caller, removes a required field from the routine invocation, and shrinks the check-in skill. Field 3's validation survives intact for the override path (`unknown-base` / `base-not-on-main`); the digest still includes the resolved base, so dedup semantics are unchanged.

**LOST** — The routine path no longer forces the caller to assert its starting point (the intentionality argument that protects `--files` does not apply here: a base is a fact about the worktree, not a choice); and the auto-path assumes the caller's directory is a git checkout of this repo — true for every caller the design names. Pays into priorities 1 and 3.

**CONSEQUENCES** — Request grammar and field 3 rewritten; procedure step 3 "start from main *at the declared base*" becomes "at the resolved base"; C6's third bullet moves into the program (the skill line and the bindings C6 bullet go stale); T1's base-refusal cases split into override-path cases; T3 unchanged; slice-plan screening item 1's list unchanged in names; B4c already covers recording the resolved value.

### F8 — Fix the contradiction between field 1's read invariant and the advisory (rung: Verify — a consistency repair; Delete was considered for the advisory and rejected, since a forgotten declaration is the likeliest real caller error and the advisory catches it cheaply and never blocks)

**WHAT** — Restate the invariant so the advisory is inside it: declared paths are the only *content* read from the caller's worktree; the advisory additionally performs one status-level comparison (paths and difference only, no content) — or explicitly scope how the advisory learns "modified files *beyond* the declared ones."

**WHY** — Field 1: "The new content of each path is read from the invoking agent's working copy — the program's *only* read of that worktree." The advisory: "if the agent's worktree contains modified files *beyond* the declared ones, the reply carries a note." Detecting undeclared modifications requires examining the whole worktree, so the "only read" claim is false as written; D1 repeats it ("it reads the caller's worktree exactly once, for the declared paths"). One of the two statements must yield, and T9 pins the advisory's behavior, so the invariant is the one to reword.

**LOST** — Nothing; the invariant becomes true instead of aspirational. Pays into priority 2. (Post-C2 the advisory's scan crosses the user boundary — F4 item (3) covers it.)

**CONSEQUENCES** — Field 1's final clause and D1's sentence rewritten; T9 unchanged; § Constructive guarantees unchanged.

## Hunt: prompts-to-code

Every place the design relies on an agent following English where code could carry the fact:

- **`--base`** — derivable by one git command; currently skill-derived (hook tier only). F7.
- **`--agent` model value** — derivable from the transcript the origin already points at. F6.
- **`--files`** — genuinely intentional (which files constitute the change); C6 correctly reduces the agent's contribution to the trained `git add`. Residue, correctly delegated.
- **`--message`** — "Intent lives with the author; it cannot be auto-filled." Residue, correctly delegated.
- **`--issue`** — a forced explicit answer, the design's own rejected-cut precedent. Correctly a declaration.
- **"Agents use the program, not raw push"** — layered mechanically (C6 hook deny, C2 boundary, slice-5 audit); the English in CLAUDE.md is documentation by explicit ruling, not load-bearing. Correct — contingent on F4 making C2 real.
- **Cancel discipline** ("the workflow simply does not teach cancel as a routine move") and **revert-on-bad-landing** — instruction-tier only, low stakes, failures loud and recoverable through the gate. Acceptable residue.
- **The judgment-written issue comment** on genuinely blocking outcomes — interpretive by design. Residue.

After F6 and F7, no fact reaches the gate by agent recall; only judgment does. That is the target state.

## Hunt: a better way

- **The worktree-byte contract is the design's one load-bearing coupling.** It generates C8 (cross-machine callers), F4's cross-user read gap, and F8's advisory tension — three symptoms, one cause. C8's first candidate shape ("the caller pushes its branch and the request names a ref instead of relying on worktree bytes (a real contract change)") dissolves all three at once, at the cost of a branch push per check-in and the loss of "no branches" for ordinary work. I am not proposing it now — but the design should recognize that C2's read-permission problem, not only a Mac agent, may be what forces this decision, which moves its trigger earlier than "when a Mac-side agent first needs direct check-in."
- **Containment is already the design's shape** — refusals have "no side effects at all," the push is atomic, a bad landing is "a **revert**: an ordinary check-in whose change undoes a previous one, through the same gate," and crash recovery is "resubmit." There is no prevention machinery left to shrink; this is what the containment move looks like done well.
- **The audit's detectable class shrinks after C2+C3 land** — the spec already notes "C3 removes that class by taking owner power out of agent hands entirely"; once C2 makes agent raw-push impossible, trailer-absence scanning detects only owner-deliberate acts and credential compromise. It stays worth keeping as a cheap tripwire, but the spec could name its post-C2 demotion the way it names every other trigger. A question for the walk, not a finding.
- **Slice order, a question only** (the five-slice order was accepted at the 2026-08-08 walk, and cancel-in-v1 is boss-ruled — noted, not contested): slice 4 "serves slow checks, and there are no slow checks yet" (the plan's own words), while slice 5 is what protects the lane once the credential decision turns the gate live. If that decision lands before slice 4 is built, building 5 before 4 gets the audits standing when they first matter.
- **Unknown unknowns found:** the three C2 interaction gaps of F4 (agent-writable program path, sudo env stripping, cross-user reads) — each individually small, together they are the difference between the boundary existing and being believed to exist.

## Leanness certification

I examined the following and certify them minimal against the grounds named:

- **Concurrency** — no queue, no lock; GitHub's atomic push as sole arbiter; retry capped at five with a named refusal; both deferred optimizations carry named triggers ("when checks become slow"; "sustained contention at the retry cap"). Nothing to cut, nothing missing.
- **The digest** — program-computed, metadata-excluded for the right reason ("the digest identifies **the work**"); caller-generated request ids correctly cut ("Never").
- **Crash recovery** — "one rule, not a procedure": two durable effects, resubmit heals, "No journal, no repair mode." This is the containment pattern; I found no second check checking the first anywhere in the state machine.
- **The error catalog and exit codes** — every ending named; the 1/2 split has a real consumer ("so loop counters and the audit never read a gatekeeper bug as a correct refusal"); no guard whose failure cannot occur.
- **The reply contract** — one JSON object, one summary format (B1); no duplicate output channel.
- **Imports** — the derived `imports` view replacing the append-a-row manifest is an already-executed simplification of exactly the kind this review hunts; the single-import-per-check-in constraint ("inexpressible by construction") is constraint done right.
- **The cuts table** — every row carries a why and a grow-back trigger; the review-evidence field correctly waits for its format (slice 6, unscheduled).
- **C4–C7** — token scoping proportionate, issues correctly scoped-not-gated with the move-up-a-rung condition recorded, break-glass rejects the standing ungated agent, C6 explicitly "never the boundary." Lean, modulo F4's completion of C2.
- **`unbuilt-option`** (D2) — the right shape for scoped-out surface: named, exit 1, self-retiring.

One watch-item, below the finding bar: build status now lives in both the spec header ("BUILT through slice 3") and the slice plan's table — consistent today, and the fold-history paragraph in the spec header accretes with each revision. Worth an eye at the next rewalk, not machinery now.
