# Dispositions — md-review of git-gatekeeper-design.md (2026-08-09)

Target: `docs/cross-project/git-gatekeeper-design.md` (design-as-of 2026-08-09).
Reviews: 4 of 8 cells landed (both Claude hunts, both Claude restates);
all 4 Codex cells failed — **codex not logged in on this box**; absence noted
per the grid's instruction. Finding keys: HG = claude-hunt-good (Opus),
HF = claude-hunt-floor (Sonnet); duplicates merged.

Restate verdict first: both restate cells reconstructed the design faithfully,
including the subtle mechanics (digest exclusions, B4d, the race handling).
The misreadings they did hedge on are the same defects the hunts flagged
(boss/user identity, the advisory vs "only read", "disciplined form"). The
document communicates; its defects are contradictions and stale absolutes,
not incomprehensibility.

Groups ordered most-important-first; each item carries a disposition:
**FIX** (spec edit, no ruling needed), **WALK** (user decides),
**CODE** (program follow-up), **RESIDUAL** (record, accept).

## Group 1 — WALK: real design decisions the review surfaced

1.1 **Digest binds the base, weakening resubmit-after-refresh** (HG17).
After a conflict fix or a crash-plus-refresh, the base changes, so the digest
changes, and the `already-checked-in` screen cannot fire; the caller instead
gets `unchanged-path`/`empty-change`, which reads as a caller mistake.
Recommend: keep base in the digest (correctness of integration depends on
it); teach the ambiguity instead — `empty-change`/`unchanged-path` refusal
text gains one line: "if you refreshed from main after a crash or conflict,
your work may already be on main — check `git log`". WALK.
processed 2026-08-10 → revised: base stays in the digest (ruled); the
refusal-text hint is withdrawn as make-work — the crash window is near
zero, the handoff case is the handoff's defect to fix at its source, and
`unchanged-path` already names the operative fact. Digest-scope sentence
added to the spec. Superseded by a broader ruling the discussion produced:
a refusal-text quality pass over the whole catalog (the user's bar: the
best, most useful, actionable text that can be reliably generated),
recorded in the slice plan. 4.2 withdrawn with this.

1.2 **The sudoers target must not be agent-writable** (HG42). A sudoers rule
naming `scripts/git-gatekeeper.py` inside the checkout runs whatever bytes an
agent last wrote there — reducing C2's "impossible" back to "instructed".
Recommend: C2 gains a binding — the privileged lane invokes a **root-owned
copy outside every checkout** (e.g. `/usr/local/lib/nedschorus-gatekeeper/`),
updated only by a deliberate deploy step through the user; the in-repo file
stays the source of truth and the test target. WALK (amends C2).
processed 2026-08-10 → revised then accepted: root-owned copy outside
every checkout as recommended, but the manual deploy step is rejected — no
interim special case. The copy self-upgrades from main; safe because the
gatekeeper source joins the instruction-file class with slice 6's evidence
check enforcing walked approval, which makes slice 6 a prerequisite of
privileged-lane activation. Captured: C2 amendment in the bindings doc
(with the standing deployed-copies-self-upgrade principle), spec
enforcement bullet, slice plan re-sequenced.

1.3 **Mode-only changes are impossible through the gate** (HG15ii). Content
comparison ignores the executable bit, so `chmod +x` alone refuses as
`unchanged-path`. Recommend: RESIDUAL, recorded in the spec — scripts here
run via `python3 <path>`, so the bit is cosmetic today; grows when first
needed. WALK to confirm.
processed 2026-08-10 → accepted as recommended: residual, build nothing;
recorded in the spec beside the `unchanged-path` refusal definition.

1.4 **Retained refusal workspaces have no expiry** (HG29). A `--no-wait`
caller that dies never triggers the sweep. Recommend: any gatekeeper
invocation opportunistically sweeps refusal records older than 30 days —
one rule, no daemon. WALK (slice-4 scope).
processed 2026-08-10 → accepted as recommended; spec States section
amended beside B4d, slice-4 line added to the slice plan's follow-ups.

1.5 **Single-word subcommands vs the naming rule** (HG20). `imports`,
`status`, `cancel` are 1-part names; CLAUDE.md wants 3–4-part grepable names.
Recommend: keep — subcommands ride under the program's name (the grep target
is `git-gatekeeper.py imports`), and renaming now strands the built suite;
record the exemption reasoning in the spec. WALK.
processed 2026-08-10 → accepted as recommended; exemption note added to
the spec beside the query definitions.
open 2026-08-10 — side point the user raised: CLAUDE.md's grepable-name
rule may deserve a clarification that some single words are legitimately
best (language-keyword-like contexts, qualifiers riding under a multi-part
parent name). Undecided ("we might"); CLAUDE.md is instruction-class, so
any edit takes his walked approval. Raise when convenient.

## Group 2 — FIX: contradictions the folding introduced (stale absolutes)

2.1 "Holds the project's one push-capable credential" vs dormant (HG4/HF1)
— qualify: the job section states the *contract*; add "(dormant until the
credential exists — see Implementation status)".
2.2 "one push-capable credential… never push themselves" vs C4 branch
pushes (HG7) — qualify every guarantee-section absolute with **main**-capable.
2.3 "a refusal has no side effects at all" (HG8/HF9), "the *only* records"
(HG9/HF10), "The workspace is deleted" (HG21) — add the B4d exception and a
transient-workspace sentence where each absolute is stated.
2.4 `status` outcome list omits the B4d refusal-record answer (HG19/HF13);
`cancel`'s "exactly three" omits the abandoned/B4d workspace cases (HG33) —
enumerate both.
2.5 `unbuilt-option` absent from the catalog claiming "every ending named"
(HG2/HF2); `checked-in`, `in-progress`, `abandoned`, `unknown` absent from
Answers (HG35); the C7 refusal unnamed (HG47) — add all to the catalog
(C7's named: `unavailable-when-privileged`).
2.6 Reply schema omits `integrated_over`, `advisory`, and the `imports`
table shape (HG18/HF12) — state optional keys and the imports reply form
(the built program already emits them).
2.7 "of five" vs slice 6 (HG3/HF22) — "five slices plus an unscheduled
sixth (review evidence)".
2.8 `--repo`/`--remote` missing from the request grammar (HG47/HF18) — add,
marked as test seams refused when privileged (C7).
2.9 Build-slice section reads as one task (HG52/HF23) — mark superseded by
the slice plan; keep T1–T12 as the acceptance-test index, add the T↔slice map.
2.10 Cut-table review-evidence row stale (HG49/HF20) — annotate: class
designated 2026-08-04; check waits on the evidence format (slice 6).
2.11 "Cross-spec consequence, awaiting the boss" heading (HG50/HF24) and
resolved items under § Open (HG53/HF25) — retitle; split Open into
Open/Resolved.
2.12 Dedicated-identity trigger now circular, original trigger text
overwritten (HG38/HF14) — restore the original "Grows back when" text
un-struck beside the admission mark.
2.13 `git log --grep "Gatekeeper-issue: #<n>"` prefix-collides #1 with #10+
(HG26) — anchor the pattern (`#<n>$`).
2.14 "between screening and push, no refusal remains" vs
`workspace-io-error`/`network-down` arising there (HG24, HG13) — reword:
no *judgment* refusal remains; infrastructure failures remain and are
resubmittable. Also: "instant and synchronous" screening includes the clone
— say so (the built program clones during screening).
2.15 "the program's *only* read of that worktree" vs the advisory scan
(HG14) — only *content* read is the declared paths; the advisory reads
status (names), never bytes.
2.16 "Stray changes cannot enter" overstated (HG22) — scope to path
granularity: within a declared path, the worktree bytes ARE the declaration.
2.17 Guarantee 2 vacuously true in v1 (HG25) — state plainly: the v1 check
set is construction itself; the guarantee binds checks-that-exist to the
exact pushed bytes.
2.18 Conflict test "same content" vs "different files" (HG28) — the built
program is file-granularity; say "same path(s)" (no silent lost update
exists).
2.19 Loser path re-screens the digest (HG23) — the built program does check
the new tip for the digest and answers `already-checked-in`; spec should say
so.
2.20 `--import none` plus triple, and all-absent (HG12) — both are
`import-incomplete` in the built program; document.
2.21 Caller retry guidance (HG11) — one sentence: infrastructure refusals
warrant bounded, backed-off retries by caller judgment; the gate never
instructs unbounded resubmission.
2.22 Break-glass commits trip the trailer audit (HG46) — by design; say so:
the audit's issue is expected, closed by the user citing the approval.
2.23 "Issues cost nothing… needs no repository permission" (HG39) — fix:
needs an authenticated account, not a repo grant; agent tokens still carry
issues:write for the machinery.
2.24 Guarantee 4 unconditional (HF8); "exactly one of two things" scope
(HF7); "Nothing in this design depends on either" (HF17) — qualify each
(--wait form; check-in requests; no *guarantee* depends).
2.25 `main` vs owner-power tension while NedLern is both pusher and owner
(HF15) — mark "no agent ever holds it" as the C3 target state, true at
amendment application.

Group 2 processed 2026-08-11 → batch approved by the user and applied to
the spec: 2.1–2.8, 2.10–2.21, 2.23–2.25 as triaged (2.7 in its
slice-6-scheduled form; 2.8 as plain test seams per S8; 2.6 without the
imports shape per S5; 2.20 renamed `import-invalid` per S9). 2.9 was
applied earlier during S4; 2.22 died with the trailer audit (S3).

## Group 3 — FIX: references and vocabulary

3.1 B-codes get their pointer: `docs/issues/queue/3-gatekeeper-build-bindings.md`
(HG5/HF3); "promotion-relay design" gets a one-line gloss (HF4).
3.2 boss/user defined once in the preamble: same person, the human owner
(HG36/HF5); pick one term per sentence thereafter.
3.3 Retired "land/landing" used four times (HG34) — replace with check-in
vocabulary; "capability-by-landing" keeps its name (it is #31's term, not
this file's coinage) with a pointer.
3.4 Undefined load-bearing names get pointers at first use: fix ladder,
artifact-lifecycle rule, handoff scrub, subsystem token set (HG37/HF11/HF19).
3.5 One name for the evidence mechanism: "walked-approval evidence"
(HF21). "Cooperative class" defined once, used twice consistently (HF26).
3.6 The two audits get distinct names — trailer-absence audit vs
branch-protection audit — and both keep their outcomes (HG48): the trailer
audit's outcomes are `trailerless-commits-found <list>` / `all-trailered` /
`audit-failed`; the protection audit's are B3c's three. T12 covers the
former.
3.7 XDG under sudo (HG30) — state: the workspace root resolves in the
*gatekeeper user's* environment once C2 lands; give the literal default.
3.8 Digest serialization unstated (HG16) — state the canonical form (the
built program's: NUL-framed field tags between components).
3.9 `--base` merge-base operands (HG44) — `git merge-base HEAD origin/main`
after a fetch, in the caller's checkout.
3.10 Hook wording (HG43/HG45) — "disciplined form" defined by pointer to
the C6 binding; deny message carries a *template* (files and base derived,
message left to the author) — drop "exact invocation".
3.11 `NedLern`/`NedLerner` substring hazard flagged inline (HG40); the
dedicated account recorded by name at amendment application (HG41).
3.12 Frontmatter `status: specification` (HG1) — add "(partially built;
see Implementation status)" to the field or a genre note beside it.
3.13 pid-reuse and cross-machine pid limits (HG32) — RESIDUAL now; slice 4
records start-time beside the pid.

Group 3 processed 2026-08-11 → batch approved by the user and applied to
the spec: 3.1–3.5, 3.7–3.8, 3.10–3.13 (3.10 with its pointer retargeted
to the spec's own C6 bullet after the C-doc's retirement; 3.5 unified on
"walked-approval evidence"). 3.9 was applied during S7; 3.6 died with the
trailer audit (S3). 3.13's slice-4 start-time note added to the spec's
crash-recovery paragraph and covered in the slice plan by the slice-4
scope it already states.

## Group 4 — CODE: program follow-ups (not spec text)

4.1 Concurrent identical submissions share one digest workspace — add a
liveness check before the resubmit sweep (HG31); slice-4 work, noted in the
slice plan.
processed 2026-08-11 → noted in the slice plan's follow-ups section, as
triaged; user confirmed.
4.2 `empty-change`/`unchanged-path` refusal text gains the
"already on main?" hint once 1.1 is ruled.
processed 2026-08-10 → withdrawn with 1.1; superseded by the refusal-text
quality pass recorded in the slice plan.
4.3 C7's `unavailable-when-privileged` refusal lands with the credential
work.
processed 2026-08-10 → withdrawn with S8 (C7 struck to zero).

## Group S — WALK: subtraction findings (added mid-walk 2026-08-10)

From the user-requested subtraction-only hunt (`claude-subtract-fable.md`
in this directory — an off-grid Fable cell, additions forbidden, run to
counter the grid's additive bias). Full WHAT/WHY/LOST/COST per finding in
that file; one ruling each. Rulings here supersede earlier walk rulings
where they collide (S1 vs 1.4's expiry sweep; S2 vs 1.2's self-update and
slice-6 chain) — the earlier marks get updated when these land.

Walk lesson (user, 2026-08-10, at S6): a simplification review needs its
optimization axis stated — "asking to simplify is like asking to optimize
without context: faster, cheaper, more reliable, simpler to write, simpler
to maintain, simpler to use?" This project's axis: simple-to-operate over
simple-to-build; mechanical forcing functions over trained LLM habit;
logging is cheap, log-consuming machinery is the cost. The S-rulings below
apply that axis. (Pending: same lesson to agent memory — blocked by the
instruction-file guard, approval to be asked at walk close.)

S1 Cut slice 4 entirely (async mode, worker, `status`, `cancel`, retained
   records, expiry); defer to "not in v1" with trigger *checks become slow*.
   processed 2026-08-10 → rejected by the user: tests and reviews are
   planned and may be quite slow, so the deferral trigger is expected to
   fire — build the worker machinery while the system is still simple and
   fast. Slice 4 stands as planned; cancel-in-v1 and 1.4's expiry ruling
   stand.
S2 Drop the self-updating root copy; manual `sudo cp` deploy; slice 6 no
   longer gates privileged-lane activation.
   processed 2026-08-10 → rejected by the user: simple-to-operate beats
   simple-to-build — the 1.2 ruling stands (self-updating copy, slice 6
   gates activation). One capture kept from the finding: the fail-safe
   property recorded in the C2 amendment (a stale copy enforces the old
   contract and can never run agent bytes — staleness costs availability,
   never safety).
S3 Delete the trailer-absence audit; keep the branch-protection audit.
   processed 2026-08-10 → accepted by the user, over the presenter's
   keep recommendation. His reasoning: logging is the easy half — the real
   cost is machinery to consume the logs, and this detector has no
   consumer. Applied: spec enforcement section rewritten around the one
   audit, T12 retired, slice-5 row and slice-plan prose updated.
   Consequences for the batches: 2.22 (break-glass trips the trailer
   audit) and 3.6 (distinct names for two audits) are mooted; re-triage
   drops them. T12's row in 3.6 moot likewise.
S4 Retire the C-bindings doc; deduplicate spec↔slice-plan sections.
   processed 2026-08-10 → accepted, all three parts. (a) C-doc deleted
   (git rm; committed version at 0890848; today's two C-doc-only
   sentences — the fail-safe property, the self-update standing
   principle — moved into the spec's C2 bullet first, with the working
   deploy path). Spec's revision note updated to record the retirement.
   (b) narrowed per 2.9: spec's build-slice section retitled "Acceptance
   tests", keeps the T-index, points at the slice plan for sequencing —
   2.9 is thereby applied early. (c) the classification's one home is the
   spec's § Relationship (class tags added there); the slice plan's
   restating table replaced by a pointer plus its unique slice-landing
   notes.
S5 Delete the `imports` subcommand; the trailer plus `git log --grep` is
   the view.
   processed 2026-08-10 → accepted (the trailer record and T11 screening
   are untouched; only the redundant reader goes). Spec: subcommand bullet
   replaced with the git-log view, cut table updated, T10 retired, 1.5's
   naming note trimmed, status line annotated. Slice plan: slice-2 row
   updated; program-deletion follow-up queued for after the walk.
   Consequence: 2.6's imports-reply-shape fix is mooted; re-triage drops
   that clause.
S6 Drop `--issue` and the `Gatekeeper-issue` trailer.
   processed 2026-08-10 → rejected by the user (the presenter's initial
   accept recommendation reversed itself under his question). The field's
   value is not downstream parsing but the mechanically forced, recorded
   answer — a check-in cannot proceed without stating an issue or an
   explicit `none`; dropping it trades a deterministic linkage for a
   probabilistic LLM habit, and absence would become indistinguishable
   from forgetting. Carrying cost is trivial. The 2026-07-24 trailer set
   stands intact. Walk lesson recorded (see S-group headnote): a
   simplification review needs its optimization axis stated — this
   project's axis is operational reliability and simple-to-operate,
   not less code.
S7 Absorb `--base` into the program; field leaves the contract.
   processed 2026-08-10 → accepted: same exact commit id, computed by the
   program (merge-base after fetch, in the caller's checkout) instead of
   relayed by the cooperative tier — reliability moves from the
   probabilistic tier to the mechanical one. `unknown-base` /
   `base-not-on-main` retired; mid-task-refresh blind spot recorded as an
   accepted residual (shared exactly by the previous wrapper design).
   Spec: grammar, field 3, candidate construction, catalog, C6 bullet
   updated — 3.9's merge-base operands statement applied in the process.
   Slice plan: program rework queued post-walk. Mooted: 3.9; 2.8's
   grammar fix loses no scope (--repo/--remote still get added).
S8 C7 shrinks to a remote-pin line, or to zero.
   processed 2026-08-10 → accepted at zero (user chose zero over the
   presenter's pin recommendation): both refusals struck as guards that
   guard nothing; no remote pin — the token's scope, set once by the
   user, is the guard. Spec C7 bullet rewritten to record the reasoning.
   Consequences: 4.3 (the `unavailable-when-privileged` refusal) is
   withdrawn; 2.5 drops its C7-refusal clause; 2.8 still adds
   `--repo`/`--remote` to the grammar but as plain test seams, no
   privileged-mode note.
S9 Collapse the refusal catalog (~19 → ~10); delete dead `empty-change`.
   processed 2026-08-11 → accepted, all three parts: `empty-change`
   deleted as unreachable (a real latent defect the review found),
   `missing-message` folded into `malformed-field`, the four import codes
   merged into `import-invalid`. Spec fields and catalog updated; program
   work queued in the slice plan. Consequences: 2.20's two cases now
   answer `import-invalid` (its documentation clause survives with the
   new name); 1.1's digest-scope sentence updated to drop its
   `empty-change` mention at batch application.

## Walk order

1. Group 1 items (five rulings), one per item — DONE 2026-08-10, all five
   processed above
2. Group S items S1–S9 (nine rulings), one per item — inserted 2026-08-10
   at the user's direction, ahead of the batches so surviving spec text is
   fixed once
3. Groups 2–3 in one batch each (mechanical; approve the batch, spot-check
   any item), re-triaged first to drop fixes mooted by Group S rulings
4. Group 4 noted for the slice plan
5. Codex leg: rerun after `codex login`, or accept the Claude-only review
   open 2026-08-11 — ruled: rerun. Device-auth login completed (the
   2026-08-10 attempt had never finished its browser half — no credential
   existed); all four Codex cells relaunched against the revised spec,
   reports land beside the Claude cells in this directory. The item (and
   the walk) closes when their triage is presented.
   Triage landed 2026-08-11: `codex-dispositions.md` in this directory —
   both restates pass; 5 new WALK items and 23 FIX items survive
   verification; 24 moot against this file's rulings, 3 stale (overtaken
   by 151e046), 30 rejected. The walk continues there: its own Walk order
   section is the plan and carries the marks. Process defect
   recorded: the grid should pre-flight each runtime's availability
   before launching and report absences up front — one-line check in
   `scripts/md-review-grid.py`, ordinary follow-up work.
