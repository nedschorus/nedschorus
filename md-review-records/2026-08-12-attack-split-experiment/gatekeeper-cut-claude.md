<!-- provenance: runtime=claude model=claude-fable-5 effort=xhigh attack=cut doc=gatekeeper isolation=instruction-pinned document set -->

Report complete. I read all four documents; findings below, deepest cut first, each with quoted grounds. Two findings collide with recorded rulings and are flagged as such, not silently re-litigated. This is the report; nothing was written or edited.

---

# Cut-attack report: git-gatekeeper specification (revision 2026-08-09, archived at 0890848)

## Finding 1 — Cut the trailer-absence audit; keep the branch-protection audit

**WHAT.** Remove the trailer-absence audit — "a standing audit at each handoff scrub scans main for commits missing valid trailers and files a `draft` issue naming them" — and its test T12. Keep the branch-protection audit with its three named outcomes (`protection-ok` / `protection-wrong` / `audit-failed`), which needs a live trigger (see below). Both are slice 5, contract-only; nothing built is lost.

**WHY.** Three independent grounds, all from the documents' own text.

*Its trigger is dead.* The audit runs "at each handoff scrub." The fast-handoff revision (2026-08-02) superseded "the scrub modes" and records that "full manual scrubs died with the committed tier." No moment named "handoff scrub" exists in the current handoff cycle; the closest survivor is the supervisor's "one automated queue-status line" per recycle. Per my charter, a dead trigger reopens the Delete question: I searched all four documents for dependents of the trailer-absence audit's output and found only T12, the slice-5 row, and the honest-singleton sentence — all inside this cut's own consequence list. Nothing outside the mechanism consumes it.

*Both of its purposes are spent or dying.* The audit existed to (a) detect the cooperative raw-push residual and (b) trigger the mechanical-closure rung — the bindings record "the spec names two triggers for its mechanical-closure rung: the audit ever firing, or the boss admitting it early." The boss admitted it early (C1, 2026-08-09), so purpose (b) is consumed. Purpose (a) dissolves on the chosen roadmap: C2 "is the step at which 'agents never push' becomes impossible rather than instructed," and today "the gate is dormant: no host yet holds a main-capable credential" — so a raw agent push is impossible now (no credential exists to steal) and impossible after C2/C3 (the credential is "owned by a dedicated Unix user, unreadable by agent sessions," and protection "names it alone"). A guard whose failure condition cannot occur at any point on the chosen path guards nothing. The spec itself already made the trailer's presence constructive: "The record cannot be missing — the program writes the trailers itself."

*It carries unstated machinery.* Every commit on main from before the gatekeeper went live lacks trailers, so a scan of main for "commits missing valid trailers" flags the entire founding history unless the audit also carries an epoch boundary or allowlist — complexity the spec never mentions. It also auto-files issues, in tension with the spec's own convention that "mechanical chatter stays in transcripts."

The branch-protection audit is the keeper: `protection-wrong` detects the one real event that could reopen the hole (settings drift, a botched amendment application, GitHub-side change), it is point-in-time and read-only, and B3c's fail-loud outcomes were boss-walked 2026-07-30. If the boss prefers to keep the trailer scan as a belt to that suspender, it minimally needs a live trigger and an epoch bound — repair is the second candidate; deletion is the first.

**LOST.** The one thing only a history scan can catch: a trailer-less commit landed through a *transient* protection hole that was opened and closed between protection audits. Every actor in that chain is the user (only org owners touch protection, and "a protection change by any owner is a deliberate, visible act"). Priority 1 pays: fewer standing detectors, no draft-issue triage stream, no epoch machinery.

**CONSEQUENCES.** Spec: "The raw-push residual is *detected*, not prevented: a standing audit at each handoff scrub scans main for commits missing valid trailers and files a `draft` issue naming them" becomes false as written; the parenthetical "(The audit also covers the sibling residual while it exists…)" goes with it; T12 ("a raw push (simulated) is caught by the trailer-absence audit") is deleted; the header's "Slices 4 … and 5 (the audits, …)" becomes singular. Slice plan (archived context): the slice-5 row "trailer-absence audit, branch-protection audit" and the rationale "The audits are detection, not gating" go stale. **Ruling collision, flagged:** the audit sits inside boss-ruled enforcement text and its dead trigger comes from a boss-walked supersession in a *different* spec; this cut must be walked, never applied silently. Independent of the cut decision, the "at each handoff scrub" trigger is stale for **both** audits and the branch-protection audit needs a new home (the supervisor's per-recycle step is the obvious candidate — a design question for the walk, not mine to settle).

## Finding 2 — Cut B4d: the retained refusal record for refused `--no-wait` requests

**WHAT.** Remove the exception in § States: "a refused `--no-wait` request keeps its workspace holding just the JSON refusal record; `status` returns it once, then sweeps." Every ending sweeps the workspace, no exception; a refused non-waiting request answers `unknown` from `status`, whose next action is already "no trace; submit it — always safe."

**WHY.** The mechanism contradicts three of the spec's own flagship statements. First: "The repository is untouched — a refusal has no side effects at all" — B4d makes one refusal class leave a durable side effect. Second: "**Records:** git history and the invoking session's ordinary transcript are the *only* records. No side files, no separate logs" — the JSON refusal record is a side file surviving past the request's ending. Third, an inventory mismatch: § The reply enumerates `status` outcomes as "`checked-in <commit>`, `in-progress`, `abandoned` …, or `unknown`" — no refusal-return outcome exists in that list, yet B4d promises `status` returns one. Two inventories that differ is cut evidence, and the smaller half is B4d.

The spec's own resubmit invariant makes the record redundant: "Resubmitting is always safe. Same request, same answer; … Refusals teach, retries are free." Form refusals are already "instant and synchronous in both modes," so B4d only ever holds post-acceptance refusals (`conflict`, `main-moving-too-fast`, infrastructure) — and those are state-dependent: a stored `conflict` describes a main that has since moved, so resubmitting yields either a success or a *fresher, truer* refusal than the record. Finally, the mechanism's own accepted residual — "a caller crashing between sweep and read loses the reason — rare, recoverable by resubmit" — concedes that resubmit covers the loss, which is the argument for not building the record at all.

**LOST.** A non-waiting caller learning a post-acceptance refusal reason from `status` alone; without the record it pays one extra pipeline run to rediscover it. Cheap while checks are fast (the spec's version-1 premise); when checks become slow, this ruling can be revisited alongside the other slow-checks machinery. Priorities 1 and 2 pay: one fewer durable state, no return-once-then-sweep protocol, no named residual, and the "no side effects / no side files / two durable effects" claims become unconditionally true.

**CONSEQUENCES.** Header line: "the two pending amendments from the 2026-07-30 bindings walk (the refused `--no-wait` workspace retains a JSON refusal record, `status` returns it once then sweeps; …)" loses its first item. § States: the exception sentence and the "Named residual (accepted)" sentence are deleted; "Durable traces: … a refused waiting request deliberately leaves nothing" extends to every refusal. Slice plan: the out-of-scope item "the refusal record B4d (4)" goes stale. **Ruling collision, flagged:** B4d is a boss-walked amendment (2026-07-30); this cut must be walked.

## Finding 3 — Delete the "Cross-spec consequence, awaiting the boss" section

**WHAT.** Remove the section whose heading says "awaiting the boss" and whose body says "RESOLVED 2026-07-24, then SUPERSEDED 2026-08-02," together with the Open-list bullet "(resolved) The fast-handoff S2 interaction — see § Cross-spec consequence."

**WHY.** A heading contradicted by its own body: nothing here awaits anyone. The resolution's durable home is the fast-handoff spec itself, which records its own supersession history ("This 2026-08-02 revision supersedes the 2026-07-22/24 fast-handoff design"). A resolved item held open in two places in this spec is exactly the duplicated-status drift the design elsewhere avoids ("the `imports` query is the view" replacing the entry manifest is the same instinct).

**LOST.** A pointer from this spec to the recycling reconciliation. If the walk wants the breadcrumb, one sentence in the revision-history paragraph replaces the section. Priority 2 pays.

**CONSEQUENCES.** The Open list drops its last bullet; no other text references the section.

## Finding 4 — One of these is false: the "only read of that worktree" claim, or the advisory

**WHAT.** Field 1 states that reading the declared paths is "the program's *only* read of that worktree." The advisory requires detecting "modified files *beyond* the declared ones," which cannot be done without reading (or at least hashing) undeclared worktree content. Both statements cannot be true. Cut the claim, not the advisory.

**WHY.** The advisory has a consumer (the calling agent, told to "confirm intentional"), answers a real failure mode (a forgotten declaration), is boss-walked, built in slice 1, and tested (T9). The claim is an overclaim that a reader — or a future builder taking it literally — would act on wrongly. The correct scoped statement is that the declared paths are the only worktree content that can *reach the candidate*: "Stray changes cannot enter — the candidate is built *from* the declaration" already says this correctly.

**LOST.** Nothing; the constructive guarantee carries the real invariant.

**CONSEQUENCES.** Field 1's "the program's *only* read of that worktree" is rescoped or deleted. The same overclaim recurs in the slice plan's D1 ("it reads the caller's worktree exactly once, for the declared paths") — stale in that archived context document.

## Questions for the walk (not findings)

- **The bindings queue document's governance clause.** It states "until the spec is updated at that walk, this document governs these points," and this spec revision now folds C1–C8 in. If the live queue document still stands un-retired, C1–C8 have two authoritative homes that will drift. I cannot verify the live repository state — my document set is the four archived files — so this is a question, not a finding.
- **The import happy path cannot execute where the gate runs.** The slice plan records, "verified 2026-08-07 — the legacy checkout does not exist on this box." Slice 2 is built and tested against fixtures, and `legacy-unreadable` names the condition honestly, but every real import will refuse until the checkout exists on the gatekeeper's machine or imports route another way. Roadmap-shaped; the founding plan is outside my document set, so I raise it rather than cut.
- **A stale rationale, not a cut:** the origin field is justified "because our agents are long-lived," while the recycling design deliberately makes sessions short-lived and disposable. The field is auto-filled and near-free, and transcripts do persist machine-locally, so the mechanism stands; only the rationale sentence has aged.

## Leanness certification

I examined and certify as already minimal, each passing the replacement test:

- **Crash recovery** — "No journal, no repair mode. Recovery is: **resubmit**." The digest screen, which must exist anyway, *is* the recovery mechanism. Containment done right; no simpler existing thing could replace it because it already is the reuse.
- **Concurrency** — "No queue and no lock are built"; GitHub's atomic push is the arbiter. The simplest existing thing already delivers the ordering guarantee, and the design uses it.
- **Break-glass (C5)** — git history as the rollback store ("any historical version is directly runnable") plus the one-standard-library-file invariant that keeps it true. This is the containment framing my charter hunts for, already applied.
- **The digest** — content-keyed, program-computed, metadata-excluded; it replaces caller-generated request ids and makes retries free. Nothing simpler exists that still deduplicates.
- **`--issue` and the `#<n>` trailer form** — protected forcing function (the ruled worked example), and the `#<n>` form buys issue-timeline collection "with zero machinery" by reusing GitHub behavior.
- **`unchanged-path`** — a forcing function with a named downstream dependent: C6's push-deny rationale leans on "the intentionality the spec's `unchanged-path` refusal exists to force."
- **The retry cap, the `abandoned`/`unknown` distinction, exit code 2** — each is a few lines guarding a real, reachable condition (`abandoned` falls out of the `worker.pid` file crash-recovery needs; exit 2 has named consumers in "loop counters and the audit").
- **The "Deliberately not in version 1" table** — the design's own cut ledger, most rows correctly marked "Never" grows back.
- **Slice 4 as a whole (`--no-wait`, `status`, `cancel`)** — I examined it as a cut candidate and refuted myself: cancel is boss-ruled into version 1 with its cost stated ("it is three branches"), the five-slice order was user-accepted 2026-08-08 without per-item approval, and building ahead of need is the project's stated preference. The roadmap interlock protects it; only B4d inside it (Finding 2) survived my refutation pass.
