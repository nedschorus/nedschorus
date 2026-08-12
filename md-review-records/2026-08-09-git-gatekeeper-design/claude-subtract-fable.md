<!-- provenance: runtime=claude model=claude-fable-5 effort=default cell=subtraction-hunt tier=above-good target=/home/nedlern/agents/choirmaster/docs/cross-project/git-gatekeeper-design.md -->
<!-- Off-grid cell, user-requested 2026-08-10 during the review walk: a
     subtraction-only hunt (additions forbidden) over the spec, the C-bindings
     doc, the slice plan, and the built program, to counter the grid's
     observed additive bias. Read alongside dispositions.md; findings here
     postdate the dispositions triage and some contradict rulings made in
     the 2026-08-10 walk (noted inline by the reviewer). -->

Findings, deepest first. Format per finding: WHAT / WHY the guarantees hold / LOST / COST.

---

**1. Cut slice 4 entirely — `--no-wait`, the detached worker, `status`, `cancel` — and with it the whole observable state machine.**

WHAT: Delete the async mode and everything downstream of it: the detached worker, `worker.pid`, the on-disk request record as a durable artifact (B4c stays as an in-process rule), the B4a discoverable-workspace requirement, the B4d retained-refusal-record, the 30-day expiry sweep and its "crashed between sweep and read" residual, the `abandoned` state, all four `status` answers, all three `cancel` outcomes, the cancel-vs-push race analysis, `accepted <digest>` / `in-progress` / `cancelled` / `too-late` / `unknown-request` reply forms, and the `--wait|--no-wait` flag pair itself (one mode needs no flag). Move the whole cluster to the "Deliberately not in version 1" table with the trigger the design already uses elsewhere: *checks become slow*.

WHY: The slice plan concedes the premise itself: "The worker lifecycle serves slow checks, and there are no slow checks yet... waiting is cheap." Every guarantee slice 4 defends is a corollary of one invariant the spec already states: *the atomic push is the only durable effect; history answers every question*. Synchronous-only makes that invariant total — the caller's process is the worker, so "died silently" is visible to the caller directly; crash recovery remains exactly "resubmit" (digest in history → `already-checked-in`; absent → runs fresh); a refused waiting request already "deliberately leaves nothing," which becomes true of *all* requests. `status` exists to answer questions only a detached worker creates; `cancel`'s boss-ruling rests on "the machinery it needs already exists" — false once slice 4 is cut (kill-the-caller's-tool-call is cancel; after the push, revert, exactly as the spec already rules). § States, crashes, cancel shrinks to about three sentences around the one invariant.

LOST: A caller who wants to not block — no such caller exists and the pipeline runs in seconds. Cross-agent visibility into another agent's in-flight request — not a designed use. Two user rulings get contradicted (cancel-in-v1; today's 30-day expiry ruling, which dies with the records it sweeps) — surfacing that is the point of this review.

COST: Negative in code. Lines 799–808 of `scripts/git-gatekeeper.py` (per-digest workspace, `request.json`, `worker.pid`, the clone move) exist *only* to serve future slice 4 and delete; the `status`/`cancel` stub parsers and their `unbuilt-option` refusals delete; tests asserting `unbuilt-option` for these delete; the 146 real cases stay green. T7 keeps its resubmit-after-kill halves, drops the `status abandoned` assertion; T8 deletes. Spec sections shrink substantially.

---

**2. Drop the self-updating root copy, unchaining slice 6 from activation.**

WHAT: In C2-as-amended (spec § credential; C-doc C2 amendment): delete the "copy keeps itself current from main automatically" mechanism. The root-owned copy is updated by a deliberate user act (one `sudo cp` when a gatekeeper change lands — the same in-the-moment-password posture C5 already establishes). Consequently delete the entire prerequisite chain it created: slice 6 stops gating activation, and "approval-evidence format → slice 6 → credential work" collapses back to "credential work."

WHY: Self-update-from-main is safe only if main's gatekeeper source is mechanically gated (review-evidence check), which needs the evidence format, which needs slices 4–5 first — four stages of machinery built to automate deploying *one low-churn file*. Without self-update, the enforcement boundary (C2/C3) holds identically: the sudoers rule still names a root-owned copy outside every checkout, agents still cannot touch it, and a stale copy fails *safe* (it enforces the old contract; it cannot be made to run agent-written bytes). The design's real guarantee — "agents never push becomes impossible rather than instructed" — never depended on freshness, only on ownership.

LOST: The fix-without-deploy loop genuinely returns as a risk: a landed gatekeeper fix is not live until the user copies it, and a forgotten copy means the deployed gate silently runs old code. The "deployed things self-update" standing principle (user-ruled yesterday) is contradicted. Real losses — against them: the gate goes live after slice 5 (or arguably after slice 3 plus the credential work) instead of after an unscheduled format-design plus slice 6. Dormancy is also a cost, currently unpriced.

COST: Zero code (nothing of this is built). Spec: one paragraph in § credential, one in C2, the slice-plan sequencing paragraph.

---

**3. Delete the trailer-absence audit — half of slice 5 — as subsumed by C2 + C3 + the protection audit.**

WHAT: From slice 5 and the spec's § credential closing paragraph: cut the standing scan of main for trailer-less commits and its mechanical `draft`-issue filing, plus T12. Keep the branch-protection settings audit (three named outcomes).

WHY: The audit exists to detect the *procedural* residual — "before C2, agents use the program by instruction only." C1–C3 are now ruled: after they apply, only the gatekeeper account can push main (protection), and only the gatekeeper program can use that credential (Unix-user boundary). The spec itself already argues the sibling case this way: "C3 removes that class by taking owner power out of agent hands entirely." The same sentence applies to raw pushes. Post-C2/C3, a trailer-less commit on main can arise only from (a) break-glass — a user-password-approved deliberate act needing no detection, or (b) a protection failure — which the *protection* audit catches at the config level, one layer earlier and more directly. The trailer scan also sits in tension with the design's own rule that "nothing routes to the boss mechanically" and "no side files": it mechanically files issues about history.

LOST: Detection of a trailer-less commit landing through a protection hole *in the window before the next protection-audit run* — the protection audit catches the hole, not the commits that used it. Also a permanent record that break-glass was exercised (the user already knows; his password was required).

COST: Zero code (unbuilt). Slice 5 shrinks to: protection audit, repo git config, CLAUDE.md lines — small. Combined with findings 1 and 2, the remaining unbuilt scope collapses from "slices 4, 5, evidence-format design, 6, credential work" to "small slice 5, credential work."

---

**4. Retire the C-doc; collapse duplicated sections across the three documents.**

WHAT: (a) Delete/archive `docs/issues/queue/3-gatekeeper-credential-and-hook-bindings.md`. (b) In the spec: replace § "Build slice (choirmaster task 1)" (the T1–T12 list) with a pointer to the slice plan, which already owns the slice↔test mapping. (c) One of the two legacy-disposition tables goes: the slice plan's rewrite-policy table says outright it "restates" the spec's § Relationship to the legacy design — keep one, point from the other.

WHY: The C-doc's own lifecycle clause is "until the spec is updated at that walk, this document governs." The 2026-08-09 spec revision states it folded C1–C8 in; the walk anchor is committed (9f1b841). Two normative texts for the same rulings is a live divergence hazard — the fold already introduced deltas (the spec's C2 paragraph and the C-doc's amendment paragraph are near-duplicates that will drift). The test list and the legacy table are pure duplication; the slice plan already declares "the specification is canonical, not this document," so the direction of each pointer is settled.

LOST: For (a), nothing — provenance survives in git history and the md-review records. For (b)/(c), the spec stops being fully self-contained on those two points; one hop to the slice plan.

COST: Deletions and two pointers. No code.

---

**5. Delete the `imports` subcommand; keep the trailer.**

WHAT: Cut the `imports` command: parser entry, `imports_table`, `parse_import_trailers` (including the malformed-row branch), the per-invocation scratch clone it performs, and T10.

WHY: By the spec's own argument, applied to itself. For issues it says: "The same collection is derivable offline (`git log --grep ...`)" — and rests the issue-timeline feature on exactly that derivability. The import table is the identical situation: `git log origin/main --grep "Gatekeeper-import:"` is the whole query. The entry checkpoint's guarantee ("the record cannot lag") lives entirely in the trailer written at candidate construction; the query adds no guarantee, it formats one. Replace the "Never — the `imports` query is the view" cell with "the trailer is the view; `git log --grep` reads it."

LOST: The parsed-JSON table, oldest-first ordering, and the malformed-trailer flagging (which detects hand-pushed bypasses — a class finding 3's logic says C2/C3 eliminate anyway). A one-line documented git command replaces a subcommand.

COST: Real but bounded — this is built and tested (slice 2). Delete ~60 lines and T10's cases; T11 (import screening) is untouched. The deeper cut — the whole import lane, given that the slice plan verified the legacy checkout does not even exist on this box — I do not recommend: the entry-checkpoint recording is a founding-plan-level policy, the machinery is built and green, and deleting it would re-open a ruled question for zero carrying cost. The query is the part with carrying cost (a full clone per call) and no guarantee attached.

---

**6. Drop `--issue` — the field, its validation, and the `Gatekeeper-issue` trailer.**

WHAT: Remove the required `--issue none|<n>` argument, its `malformed-field` branch, the trailer line, its clause in the digest-exclusion list, and the spec paragraph defending the `#<n>` form.

WHY: The spec's own mechanism does not need the trailer: "any commit reaching the default branch with `#<n>` in its message appears automatically in that issue's timeline" — true of the *message body*, where agents already put issue references by training (this repo's own recent history: every commit ends "(nedschorus#3)"). The gatekeeper "only records the answer" and validates syntax only — it is a pass-through with no consumer; no mechanism reads `Gatekeeper-issue`, and the offline derivation works as well on message-borne `#n`.

LOST: The structured `none` — an explicit machine-readable statement that work has no issue — and grep precision (`Gatekeeper-issue: #3` vs `#3` anywhere in a message). If per-issue tooling ever wants exact linkage, the field grows back with a named trigger, like everything else in the v1 table.

COST: Small: one argument, one screen branch, one trailer line, T2's trailer assertion, a handful of T1 cases. Contradicts the boss-walked 2026-07-24 trailer set — flagged.

---

**7. Absorb `--base` into the program; delete the field from the contract.**

WHAT: The program computes the base itself — `git merge-base HEAD origin/main` in the caller's repo, which it already reads — and `--base`, its 40-hex ceremony, and the `unknown-base` / `base-not-on-main` refusals leave the contract. (Not a drop — a collapse of two mechanisms into one.)

WHY: C6 already rules that base is machinery-derived, not agent judgment: "the agent contributes only what it already does by training... the machinery derives everything else (base, session origin, digest...)" — and the check-in skill computes it by exactly this command. So the design currently has *derivation in the skill* plus *validation of the derived value in the program*: two mechanisms, one fact. Deriving in the program deletes the field, both base refusals (a merge-base with origin/main is on main by construction), the skill's front-loading step, and one hook-tier dependency. Base itself cannot be dropped outright — see refuted candidates — but nothing requires the *caller* to carry it.

LOST: Callers whose repo state doesn't encode their start point (worked across a `git pull` mid-task) — but the skill's derivation fails identically there, so nothing the current design delivers is lost. Test fixtures that pin explicit bases need the caller's HEAD set instead.

COST: Moderate — the largest of these against built code: screening reorders (base resolves after `resolve_repository`), T1's base cases delete, T3/T4/T5 fixtures set HEAD rather than pass `--base`. Report ranked here because it removes contract surface, not code volume.

---

**8. C7 shrinks to one line, or to zero.**

WHAT: Replace C7's "refuse `--repo` and `--remote` under the privileged user" with at most "the privileged copy pins the remote" — and consider deleting even that.

WHY, in two halves. `--remote`: C1's blast-radius ruling already covers it — the gatekeeper credential is a collaborator on this one repository; aimed anywhere else, the push fails auth, and a push to an attacker-controlled remote delivers only the attacker's own declared content. C7's guard restates C1's guarantee as a refusal. `--repo`: the refusal is illusory by the design's own structure — refusing the flag leaves repo = cwd's toplevel, and under the sudo lane cwd is exactly as caller-controlled as the flag was; C7's `--repo` half changes which channel the caller uses, not what the caller controls. A guard that guards nothing is deletable.

LOST: Defense-in-depth on the remote (a pin also protects against C1 being misapplied someday — e.g., the account later granted wider access). Honest: the pin line is cheap; zero is defensible only while C1 holds exactly as ruled.

COST: Zero code (C7 is unbuilt — the seams exist, the refusal doesn't). One spec bullet and C-doc section (moot if finding 4 lands).

---

**9. Refusal-catalog collapses — three concrete ones, plus one dead entry.**

WHAT/WHY:
- `empty-change` is unreachable as specified. Every path in `classify_changes` either refuses (`unknown-path`/`unchanged-path`) or classifies, and the first unchanged path refuses *before* the aggregate "nothing differs" check — so the branch at lines 461–465 is dead code; and the empty-`--files` branch is unreachable via CLI (`nargs="+"` rejects first). Delete the catalog entry; fold the empty-list case into `malformed-field`.
- `missing-message` → `malformed-field`. The catalog already refuses an empty `--agent`, a malformed `--issue`, and a malformed `--base` as `malformed-field`; a lone dedicated code for one field's emptiness is an inconsistency, not a distinction. Facts carry the field name.
- `unknown-base` + `base-not-on-main` → one code (moot entirely if finding 7 lands); `import-incomplete` + `import-source-missing` + `import-dest-undeclared` + `legacy-unreadable` → one `import-invalid`. Nothing machine-branches on error *names* — the design's own loop-counter/audit contract branches on exit codes 0/1/2 — and the three-part teaching form carries every distinction in facts + next_action.

LOST: Grep granularity per code in future analysis of refusal patterns. The teaching text loses nothing.

COST: Small code edits, matching test-assertion edits across T1/T11; catalog list in the spec shrinks from ~19 names toward ~10.

---

**Candidates refuted (checked and rejected — do not cut):**

- **Digest dedup replaced by `unchanged-path`.** Fails: a *verbatim* resubmit after a crash (same base, same bytes) compares against the declared base, not the tip, so without the digest screen it flows into integration, collides with its own landed paths, and refuses `conflict` — the wrong answer, breaking "resubmitting is always safe," the design's cornerstone. Both mechanisms stay; they cover disjoint cases, as today's spec ruling already records.
- **`--base` dropped outright** (defaulting to current tip): destroys conflict detection — a stale worktree copy of a path main has since changed would classify as "modified" against the tip and silently revert the newer change. Base is load-bearing; only its *carrier* is negotiable (finding 7).
- **`--agent` / B6.** The nearest thing to a droppable field: cooperative (unverifiable), no mechanical consumer, and in the common case the model is recoverable via `Gatekeeper-origin` → transcript. But the transcript-less case loses model attribution entirely, the fix-ladder use is concrete, and it was boss-ruled twice with rationale. Cost of keeping: one flag, one line. Not worth contradicting.
- **The advisory.** Small, never blocks, and nothing else catches a forgotten declaration. Keep.
- **Concurrency (slice 3).** Already the subtracted form — no queue, no lock, GitHub's atomic push as sole arbiter, a bounded loop, deferred optimizations with named triggers. Nothing to remove.

**Already lean:** the core contract — request/reply shape, three-part refusals, exit-code triad, trailer-writing during construction, the constructive-guarantee list, the crash-recovery-is-resubmit rule, the growth-point framing, and the "Deliberately not in version 1" table — is genuinely minimal; findings 1–3 are largely about making the *rest* of the design as small as that core, and together they reduce the unbuilt future from five stages to roughly one.

Files: `/home/nedlern/agents/choirmaster/docs/cross-project/git-gatekeeper-design.md`, `/home/nedlern/agents/choirmaster/docs/issues/queue/3-gatekeeper-credential-and-hook-bindings.md`, `/home/nedlern/agents/choirmaster/docs/issues/3-git-gatekeeper-build-slice-plan.md`, `/home/nedlern/agents/choirmaster/scripts/git-gatekeeper.py` (dead branch: lines 461–465; slice-4-only persistence: lines 799–808).
