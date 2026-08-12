<!-- provenance: runtime=claude model=claude-fable-5 cell=sanity-checker (draft prompt, post-md-review revision) run=calibration-1 target=git-gatekeeper-design.md at commit 0890848 (pre-S-walk revision); context: build-slice plan, credential bindings C1-C8, fast-handoff design, all at 0890848; reviewer had no access to the S1-S9 rulings; the prompt's two worked examples teach S7 (--base) and S6 (--issue) -->

I have read all four documents in full (the previous run's context was lost, so I re-read them). Here is the complete report.

# Sanity-checker report: `git-gatekeeper-design.md` (revision 2026-08-09)

**Documents read:** the specification under review; `3-git-gatekeeper-build-slice-plan.md`; `3-gatekeeper-credential-and-hook-bindings.md` (C1–C8); `fast-handoff-design.md`.

**Linked documents I could not read** (findings that touch them rest only on quoted text in the four provided files): `docs/issues/queue/3-gatekeeper-build-bindings.md` (B1–B6 — I know these bindings only through quotation in the spec and slice plan), `entry-manifest.md`, the legacy `git-clean-slate-plan.md`, `.claude/hooks/instruction-file-guard.py`, `.claude/skills/handoff/SKILL.md`, `docs/drafts/handoff-skill-draft.md`, the founding plan, the superseded fast-handoff at `e178e67`, and GitHub issues #3, #13, #18, #27, #31, #40, #45.

**Rulings register consulted:** the spec's revision note (2026-07-24 walked core; B1–B6 2026-07-30; B6 2026-07-31; C1–C8 2026-08-09), the slice plan's "How this plan was ruled" and walk-order block, and the bindings doc's provenance note. Two findings below collide with recorded rulings and are flagged as such.

---

## Findings (deepest first)

### F1 — Delete the read-once-then-sweep semantics of the refused `--no-wait` record (Delete) — **collides with ruled amendment B4d; flagged, not re-litigated**

**WHAT.** Replace "`status` returns it once, then sweeps" with: the refusal record persists and `status` answers it idempotently; it is swept when the same digest is resubmitted (the sweep the crash-recovery rule already performs) or by an age bound (e.g., older than N days, checked during any screening).

**WHY.** The design's own headline principle is "**Resubmitting is always safe.** Same request, same answer". Read-once makes `status` the one non-idempotent query in the system: the second `status <digest>` answers `unknown` where the first answered a refusal. The spec itself must then carry an accepted wart: "Named residual (accepted): a caller crashing between sweep and read loses the reason — rare, recoverable by resubmit" — but "recoverable by resubmit" here means re-running the whole pipeline just to re-learn a refusal reason. Idempotent records delete both the residual sentence and the wart; the sweep-on-resubmit path already exists ("absent means the leftover workspace is swept and the work runs fresh").

**Flag:** this contradicts the recorded amendment from the 2026-07-30 bindings walk, folded in this revision: "the refused `--no-wait` workspace retains a JSON refusal record, `status` returns it once then sweeps". I flag the collision plainly; the ruling's virtue is that read-once is self-cleaning with zero policy.

**LOST.** The self-cleaning property: a refused no-wait request that is never resubmitted leaves its small JSON record until the age sweep fires, and the age bound is a new (trivial, testable) policy constant. Paid for by priority 1: `status` becomes reliable under retries and racing readers, and a named residual disappears.

**CONSEQUENCES.** Stale if landed: the § States sentence "a refused `--no-wait` request keeps its workspace holding just the JSON refusal record; `status` returns it once, then sweeps"; the residual sentence following it; the revision-note clause "(the refused `--no-wait` workspace retains a JSON refusal record, `status` returns it once then sweeps)". Slice plan: the out-of-scope entry "the refusal record B4d (4)" survives but its slice-4 behavior changes; no numbered spec test (T1–T12) names the read-once sweep, so no test text goes stale, but slice 4's eventual tests must test the new semantics. B4d itself (in the unread bindings doc) would need amending at the walk.

### F2 — Retire the credential-bindings doc's normative standing once the rewalk confirms the fold (Delete: duplicated normative homes)

**WHAT.** At the rewalk that confirms C1–C8, add `docs/issues/queue/3-gatekeeper-credential-and-hook-bindings.md` to the spec's supersedes list and mark that doc provenance-only, so the credential rules have exactly one normative home.

**WHY.** The bindings doc says "until the spec is updated at that walk, this document governs these points" — correct today. But the spec's 2026-08-09 revision already "folds in … the credential rulings of 2026-08-09 … C1–C8", restating C1–C7 in full in § The credential and enforcement, while its supersedes list says only "Supersedes remain as before" — not naming the bindings doc. Neither document says who retires the queue doc after the walk. Two authoritative statements of the same rules (e.g., C7's refusal behavior appears normatively in both) is the project's named cut class: "the same rule stated authoritatively in two places, which will drift apart."

**LOST.** Nothing — the queue doc remains as provenance record; only its standing authority ends. Priority 2 pays (one place to read; no drift).

**CONSEQUENCES.** The spec's revision-note supersedes sentence changes; the bindings doc's header ("until the spec is updated at that walk, this document governs these points") is superseded. No tests touched.

### F3 — Delete the two resolved items still occupying live sections (Delete: dead sections)

**WHAT.** Delete "## Cross-spec consequence, awaiting the boss" (its content is one line of history: "RESOLVED 2026-07-24, then SUPERSEDED 2026-08-02…"), folding that line into the revision note's supersedes list; and delete the Open-section item "(resolved) The fast-handoff S2 interaction — see § Cross-spec consequence", which points at the section being deleted.

**WHY.** A section headed "awaiting the boss" whose body opens "RESOLVED" misinforms a reader scanning headings, and a "(resolved)" entry under "## Open" is a dead distinction — the section list and the Open list are the document's navigation, and both currently carry entries whose answer is "nothing here is live." This is structural (delete/merge), not phrasing.

**LOST.** One click of provenance convenience — the resolution history moves from its own section to the revision note. Priority 2 pays.

**CONSEQUENCES.** The Open section's internal cross-reference "see § Cross-spec consequence" disappears with the item. No other sentence in the spec references that section; no tests touched.

### F4 — Compute `--base` in the program; retire it as a required caller field (Encode)

**WHAT.** Drop `--base <full-40-hex-commit-id>` from the required request. The program derives it with one git command in the caller's worktree (the merge-base of the caller's HEAD with main — exactly the formula C6 already assigns to the skill), resolves it once at screening into the request record like every other environment-derived field (B4c), and puts the derived id into the digest as today. `unknown-base` / `base-not-on-main` retire from the catalog (or survive only behind a test seam if an override is kept for the throwaway-repo suite).

**WHY.** The design's own ruled division of labor already classifies base as machinery-derived, not agent-contributed: "the agent contributes only what it already does by training — choose the files, write the what-and-why; the machinery derives or auto-fills everything else (**base**, session origin, digest, issue trailer form)" (C6). But the spec currently locates that machinery in the cooperative tier — "the check-in skill front-loads the declaration (… `--base` computed as the merge-base …)" — and C6 is by the design's own words "a convenience tier … never the boundary". So any caller not routed through the skill (a raw invocation, a Mac-side caller someday, a human at a shell) re-inherits a 40-hex-copying step and two refusals that exist only to catch its mistakes. Unlike `--files` and `--message`, base carries no intent — the spec's intentionality argument ("auto-deriving all of it would gut the intentionality the `unchanged-path` refusal exists to force") is about the declaration of *what changed*, and C6 itself exempts base from it. Moving the one git command from skill text into the program makes the derivation reach every caller, mechanically. The digest is unaffected in kind: "Computed by the program; callers generate nothing" — this extends that sentence's spirit to base. This matches the project's already-validated pattern (the accepted worked example in this reviewer's brief is this exact move).

**Flag:** the request format belongs to "The 2026-07-24 boss-walked core — request/reply, digest, trailers, concurrency, states, error catalog — is unchanged by all of this", so this amends a walked contract; C6 (ruled 2026-08-09) and that core currently point different directions on where base derivation lives. The walk must reconcile them; I flag, not rewrite.

**LOST.** The caller can no longer pin an unusual base (work deliberately started from an older main state than its worktree reflects) without an override seam; and this modifies built, 146-case-tested slice-1 behavior. Paid for by priority 1: one fewer remembered step for every non-skill caller, two refusals whose failure condition becomes unreachable on the common path.

**CONSEQUENCES.** Stale in the spec if landed: the synopsis line `--base <full-40-hex-commit-id>`; all of field 3 ("the full 40-character commit id … No abbreviations … no branch names … `unknown-base` / `base-not-on-main`"); the catalog entries `unknown-base`, `base-not-on-main` under *Form (instant)*; the C6 bullet "`--base` computed as the merge-base". Still true, unchanged: field 8's digest definition ("SHA-256 over: base id + …"), the Concurrent-check-ins sentence "A request submitted from a behind-main worktree is the same mechanism". In documents read: slice plan slice-1 scope item 1 lists `unknown-base`, `base-not-on-main` among built refusals; slice-plan D1's "at the declared base" phrasing; bindings C6's merge-base bullet. Tests: T1 ("every form error refuses with its named error") loses two cases or moves them behind the seam; T3's digest properties are unaffected.

### F5 — Re-home the audits' trigger and split the conflated audit sentence (Externalize)

**WHAT.** Two defects, one rewrite of the audit passage in § The credential and enforcement. (a) The trigger "at each handoff scrub" names machinery the superseding handoff design retired; re-home the trigger to a live mechanical moment — the natural one is the supervisor's scripted per-recycle step, which the handoff design describes as exactly this duty class ("the artifact-lifecycle rot-visibility duty riding every recycle at zero agent cost"). (b) The passage describes two audits as one: the sentence's subject is the trailer scan, but its outcomes belong to the protection audit — split into two named checks, each with its own outcomes (the trailer audit's endings — nothing-found / commits-found-and-issue-filed / audit-failed — are currently never named, against the design's own "no unnamed endings" standard).

**WHY.** (a) The spec: "a standing audit at each handoff scrub scans main for commits missing valid trailers". The fast-handoff spec (which "supersedes the 2026-07-22/24 fast-handoff design") retired scrubs: its superseded-machinery list includes "the scrub modes", and its cycle says "full manual scrubs died with the committed tier". The audit's trigger point therefore no longer exists anywhere; slice 5 would build a detector with no invocation moment. (b) The same sentence continues "…files a `draft` issue naming them, with **three named outcomes** — `protection-ok` / `protection-wrong` (differing settings named) / `audit-failed`" — but `protection-ok`/`protection-wrong` are answers about branch-protection settings, not about trailer-missing commits; the revision note itself attributes them to "the branch-protection audit's three named outcomes", and slice 5 lists "trailer-absence audit, branch-protection audit" as two things.

**LOST.** Coupling: the supervisor (a built, tested component of another spec) gains a duty, so its suite grows and the two specs share a seam. Paid for by priority 1: the audits actually run, unattended, with no remembered human or agent step — the alternative (an agent remembers to run them) is the "operator cost is not builder cost" anti-pattern.

**CONSEQUENCES.** Stale if landed: the quoted audit sentence in § The credential and enforcement (including its B3c citation, which needs restating against the new trigger) and the trailing parenthesis "(The audit also covers the sibling residual…)", which must attach to the correct audit after the split; the revision-note clause "the branch-protection audit's three named outcomes". In documents read: fast-handoff step 5 ("Prints one automated queue-status line") gains a companion duty and its Supervisor test list grows; slice plan slice-5 row and its rationale bullet ("The audits are detection, not gating") stay true but the build target changes shape. Tests: T12 ("a raw push (simulated) is caught by the trailer-absence audit") is unchanged in substance; its harness must invoke the audit at the new trigger.

### F6 — Close the error catalog's completeness gap (Verify: the catalog is the normative home)

**WHAT.** Add to the catalog: `unsafe-path` (built, slice 1); a name for the C7 privileged-seam refusal (it is asserted named but never named anywhere — pick the name at the walk, checked per the project's naming rule); and a transitional line for `unbuilt-option` pointing at its definition (spec header / slice-plan D2), marked "gone after slice 5".

**WHY.** The catalog claims completeness: "**The error catalog** — every ending named". Three reachable endings are absent. (1) Field 1 forbids "no absolute paths, no `..`, nothing under `.git/`" but names no refusal for them; the slice plan shows it exists and is built: "plus B2's `unsafe-path`". (2) C7: the spec says "Run as the credential-holding user, they are refused" and the bindings say "(named refusal; the remote is pinned to the canonical repository)" — the name is stated to exist and given nowhere. (3) The header makes `unbuilt-option` a live, reachable ending today ("reaching an unbuilt part is the named refusal `unbuilt-option`, never a crash") yet the catalog omits it.

**LOST.** Nothing but three lines of catalog. Priority 2 pays (the catalog can be trusted as the one complete list, which is its whole job).

**CONSEQUENCES.** The *Form (instant)* list gains `unsafe-path`; a new *Infrastructure*-or-privilege entry appears for C7; T1's "every form error refuses with its named error" becomes verifiable against the catalog alone (today `unsafe-path` passes T1 per the slice plan while failing the spec's list). No other sentence goes stale.

### F7 — Reconcile the advisory with the "only read of that worktree" invariant (Verify: internal contradiction)

**WHAT.** Amend the field-1 invariant to admit the advisory's scan — e.g., the declared paths are the program's only *content* read of the worktree, plus one modification scan performed solely to emit the advisory — or, if the invariant is the truer commitment, delete the advisory. Recommend amending the invariant: the advisory is built (slice 1 item 7, T9) and catches the likeliest real failure ("the likeliest cause is a forgotten declaration").

**WHY.** Field 1: "The new content of each path is read from the invoking agent's working copy — the program's *only* read of that worktree." The advisory: "if the agent's worktree contains modified files *beyond* the declared ones, the reply carries a note" — which cannot be computed without examining the worktree beyond the declared paths. Both statements are normative and one is false. The invariant is not decoration — it is the spec's claim about how much of the caller's environment the program touches, which matters more once C2 has the program running as a different Unix user.

**LOST.** The invariant weakens from "only read" to "only content read, plus a scan" — a genuinely smaller promise. Priority 2 pays: a true small promise beats a false absolute one.

**CONSEQUENCES.** Stale if landed: the field-1 sentence quoted above. In documents read: slice-plan D1 repeats it ("reads the caller's worktree exactly once, for the declared paths") and goes stale the same way. Unchanged: the advisory bullet, T9 ("undeclared worktree changes noted, never blocking").

---

## Hunt: prompts-to-code

Every place the design rests on an LLM following English instructions where code could carry it, with disposition:

1. **`--base`** — currently derived by skill text at the cooperative tier; move into the program (F4). The one genuine prompts-to-code finding.
2. **`--files` relayed from the agent's staging (C6)** — examined and left. The intentional act is `git add`; the relay is mechanical either way, and moving the staged-set read into the program would cross the C2 Unix-user boundary to read the caller's index while weakening the explicit declaration the walked design prizes ("auto-deriving the whole declaration would gut the intentionality the spec's `unchanged-path` refusal exists to force"). If the walk ever revisits it, "`--files` defaults to the caller's staged set" is the shape — a question, not a finding.
3. **The audits** — already scripts; F5 only fixes where they fire, keeping them at "zero agent cost" instead of agent memory.
4. **CLAUDE.md workflow lines (slice 5)** — already ruled documentation-only ("CLAUDE.md is documentation, never enforcement"); enforcement already lives in code (C2) and hooks. Nothing to move.
5. **Correctly delegated interpretive residue (rung 6), left with the model explicitly:** the `--message` what-and-why ("Intent lives with the author; it cannot be auto-filled"), the `--agent` model half (D3: the environment names the runtime but not the model), the judgment-written issue comment on genuinely blocking outcomes, `conflict` resolution ("the program never guesses"), and revert authorship. Each is already marked as judgment in the text.

## Hunt: a better way / unknown unknowns

1. **The C2 sudo seam is undesigned, and one of its failure modes is a silent skip into green.** Once agents invoke the gatekeeper "through a sudoers rule scoped to exactly it", two facts the spec assumes stop being free: (a) **Origin auto-fill** — "auto-filled from the session environment; recorded as `none` when absent, never blocking". `sudo` strips the environment by default, so `CLAUDE_CODE_SESSION_ID` never reaches the program and *every* commit records `Gatekeeper-origin: none` — permanently, quietly, with "never blocking" guaranteeing no one notices. That is precisely the pattern B3c exists to forbid elsewhere ("never a silent skip into green"). (b) **Cross-user reads** — the gatekeeper user must read the agent user's worktree (field 1, the advisory, and F4's merge-base all read it); nothing in the spec or C2 names the permission arrangement. Recommendation for the walk: give C2 an explicit invocation contract — which environment values cross the sudo boundary and how (sudoers `env_keep`, or the wrapper passing them as resolved arguments per B4c) — and how the worktree is readable across users, each with a test. This is the review's one "missing something important."
2. **The worker-lifecycle asymmetry — a question, not a deletion (it collides with recorded rulings).** The cut table drops footprint-scoped re-validation and the merge queue because "Checks are fast; full re-run is cheaper than the machinery", and the slice plan concedes "The worker lifecycle serves slow checks, and there are no slow checks yet … waiting is cheap." The same trigger ("checks become slow") would defer all of slice 4 — `--no-wait`, the detached worker, `worker.pid`, abandoned detection, B4d, and cancel's race analysis — the largest deferrable block in the design. But `--wait | --no-wait` sits in the 2026-07-24 boss-walked core, and cancel-in-v1 is boss-ruled with cost weighed ("it is three branches"). Flagged for the walk only: if the rulings stand, slice 4 builds as planned; the asymmetry deserves one conscious look.
3. **Operational, not design:** the import path's precondition is absent on the build box — "verified 2026-08-07 — the legacy checkout does not exist on this box" — so the first real `--import` will hit `legacy-unreadable` until a checkout is restored. Worth a line wherever slice-2 go-live is tracked.
4. **The overall shape is right.** Declaration-built candidate + GitHub's atomic push as the only arbiter + resubmit-as-recovery is the containment pattern this review is told to hunt for, already at the center: no journal, no repair mode, no lock, and the bad-landing remedy is a revert through the same gate. The considered alternatives (PR pipeline, GitHub Apps, per-agent branches, merge queue) are examined and rejected in the text with reasons. C8 is correctly parked as a named unsolved remainder rather than half-solved.

## Leanness certification

Examined and certified minimal, with the grounds checked:

- **The two-outcome contract, three-part refusal form, and exit-code split (0/1/2)** — each element has a named consumer (agents' next action; loop counters and the audit distinguishing defect from refusal). Nothing removable.
- **The digest (field 8)** — every inclusion and exclusion argued in the text; single purpose ("the duplicate-detection key, not provenance"); caller generates nothing. Lean.
- **Concurrency** — no lock, no queue, capped retry with a named ending, the accepted semantic gap recorded, and both deferred optimizations carry named triggers. Nothing to cut; nothing missing.
- **Crash recovery** — "two durable effects … Recovery is: resubmit. No journal, no repair mode." Exemplary; there is no machinery here to delete because none was built.
- **The trailer block** — five lines; each consumer checked: origin → transcript pointer, agent → fix-ladder tier, digest → dedup screen, import → the `imports` derived view, issue → the zero-machinery GitHub timeline collection. No detector without a consumer.
- **Forcing functions, correctly kept:** `--issue` (an explicit answer mechanically forced — the project's own rejected-deletion precedent) and `unchanged-path` (the honesty check C6's whole rewrite-vs-deny split leans on). Not cuts.
- **`--agent` as a declared field (D3)** — the environment genuinely lacks the model half ("`AI_AGENT=claude-code_2-1-220_agent`… not the model"); I considered constraining its shape (require `runtime/model` form) and rejected it under the guard: cooperative class, cheap failure, no recurring cost.
- **The credential ladder (C1–C7)** — each tier does one distinct job, the boundary is correctly placed at C2 with hooks explicitly demoted ("convenience and coverage, never the boundary"), and break-glass C5 is a containment design (single standard-library file so any historical version runs; unlockable, not held). Lean, modulo the C2 seam gap in the hunt above.
- **The cut table** — every cut carries a grow-back trigger or an explicit "Never" with the replacing mechanism named. This section is the design auditing itself, and it holds up.
- **The slice decomposition and D1–D4** — each boundary argued from one criterion (shortest path to main), the alternative slice-1 boundary considered and recorded as the fallback. Lean.

The rest of the specification is already lean; the seven findings above are the complete set that survived self-refutation.
