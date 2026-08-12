<!-- provenance: runtime=claude model=claude-fable-5 cell=sanity-checker (draft prompt with run-1 fixes plus the replacement test) run=calibration-3 target=git-gatekeeper-design.md at commit 0890848; same inputs and isolation as runs 1-2 -->

The four documents are read. Here is the full report.

---

# Sanity-checker report: `git-gatekeeper-design.md` (revision 2026-08-09)

**Documents read:** the design under review; `3-git-gatekeeper-build-slice-plan.md` (the forward plan); `3-gatekeeper-credential-and-hook-bindings.md` (C1–C8); `fast-handoff-design.md`.

**Linked documents I could not read** (outside the provided set, per the review request — findings that touch them are marked): `docs/issues/queue/3-gatekeeper-build-bindings.md` (B1–B6 — the most material gap; I know B1–B6 only through quotations in the documents I have), `entry-manifest.md`, the legacy `git-clean-slate-plan.md`, `.claude/hooks/instruction-file-guard.py`, `.claude/skills/handoff/SKILL.md`, and the GitHub issues (#3, #13, #18, #27, #31, #40, #45).

---

## Findings (deepest rung first)

### F1 — DELETE (question reopened by a dead trigger): the trailer-absence audit's trigger names a retired mechanism, and the C1–C3 rulings removed most of what it detects

**WHAT.** The standing audit is bound to "each handoff scrub" — a mechanism the superseding fast-handoff design retired. Reopen the Delete question for the trailer-absence audit specifically; if it survives, rebind it (and the branch-protection audit) to a mechanical host — the natural one is the supervisor's per-recycle script step — and restate in the spec what it guards after C2/C3 land.

**WHY.** Three grounds, all quoted:

1. *The trigger is dead.* The spec: "a standing audit at each handoff scrub scans main for commits missing valid trailers." But fast-handoff-design.md (2026-08-02 revision, which "supersedes the 2026-07-22/24 fast-handoff design") lists among "the superseded machinery — ... the scrub modes ..." and states "full manual scrubs died with the committed tier; memory maintenance is the boss's drain per the #32 Q1 ruling." The gatekeeper spec was revised 2026-08-09, a week after the scrub died, and still names it. As it stands, the audit has no moment at which it runs.
2. *Its forcing-function consumer was consumed.* The dedicated-identity row of the cut table names its grow-back trigger as "the boss-admits-it-early trigger," and the bindings doc states the spec "names two triggers for its mechanical-closure rung: the audit ever firing, or the boss admitting it early. The user admitted it early (2026-08-09)." The audit's role as the tripwire that escalates to the dedicated-identity rung is over — that rung is admitted.
3. *Its detection target largely vanishes when C2/C3 apply.* C2: the Unix-user boundary "is the step at which 'agents never push' becomes impossible rather than instructed." The spec's own parenthetical already concedes the sibling half: "C3 removes that class by taking owner power out of agent hands entirely." After C2/C3, a trailer-less commit on main can come only from the gatekeeper Unix user itself or a human with owner power — the "cooperative residual" the slice plan says the audits exist to catch ("They catch the cooperative residual (an agent pushing raw, an owner editing protection)") is exactly the pair those rulings remove.

Per the rules, a dead trigger reopens Delete before repair. What depends on the audit, found by search: T12 ("a raw push (simulated) is caught by the trailer-absence audit"), the B3c three-outcome contract, and slice 5's row in the forward plan. The branch-protection settings check retains a real failure class C3 does not remove — settings drift by a human owner — so it should survive; the trailer-absence scan is the half whose failure condition C2 makes near-impossible.

**Ruling collisions, flagged:** B3c's three named outcomes are a walked amendment ("the two pending amendments from the 2026-07-30 bindings walk"); slice 5 is in the ruled forward plan, and "respect the roadmap" weighs against deletion. I am not silently re-litigating either — I am reporting that the audit section was written for the pre-C2 world (the spec itself says "still true until C2 is installed" about the honest singleton) and was not re-derived when C1–C8 were folded in. The honest counter-argument: the trailer scan is one `git log` command and end-to-end checks are cheap defense-in-depth during the window before C2/C3 are applied (they are "not yet applied" today). That argues for keeping it through the interim with a named retirement trigger ("C2 installed"), not for keeping it standing forever.

**LOST.** If the trailer-absence audit is cut after C2/C3: detection of a trailer-less commit made by the gatekeeper Unix user itself or by a human owner bypassing protection — a new named blind spot, accepted with eyes open (the remedy either way is a revert through the gate). Paid for by priority 1 (no recurring check protecting against an impossible class) and priority 3 (slice 5 shrinks). If instead rebound to the supervisor: nothing lost, and a recurring agent duty becomes code — priority 1.

**CONSEQUENCES.** Stale or false if this lands: the spec sentence "a standing audit at each handoff scrub scans main for commits missing valid trailers and files a `draft` issue naming them, with three named outcomes ... (B3c)"; the parenthetical "(The audit also covers the sibling residual while it exists ...)"; the implementation-status line "5 (the audits, repo git config, CLAUDE.md workflow lines)"; test T12; slice-plan row 5 ("Enforcement surfaces: trailer-absence audit, branch-protection audit ... T12, B3c") and its rationale bullet "The audits are detection, not gating. They catch the cooperative residual (an agent pushing raw, an owner editing protection)." If rebound to the supervisor, fast-handoff-design.md's supervisor step 5 (the queue-status line) gains a duty — a change outside the document under review.

---

### F2 — DELETE (duplicated normative home): C1–C8 now live authoritatively in two places

**WHAT.** Once the design rewalk confirms the fold, explicitly retire the bindings document's governing status (stamp it superseded / drain it from the queue), leaving the spec's § The credential and enforcement as the single normative home for C1–C8.

**WHY.** The bindings doc: "until the spec is updated at that walk, this document governs these points." The spec: "This revision (2026-08-09) folds in: ... the credential rulings of 2026-08-09 (`docs/issues/queue/3-gatekeeper-credential-and-hook-bindings.md`, C1–C8 ...)." Both currently claim authority over the same rulings — the textbook drift-apart pair. The queue placement suggests the project's own mechanism may already drain it; if so, this finding costs one confirming stamp.

**LOST.** The bindings doc's fuller rationale (C4's scope-by-scope reasoning, C5's rejected-alternative argument) stops being normative and becomes historical rationale only — future readers of the spec alone get the ruling without the full why. Paid for by priority 2 (one place to read, no drift).

**CONSEQUENCES.** The bindings doc's provenance note ("until the spec is updated at that walk, this document governs these points") becomes false and needs the superseded stamp; the spec's link to it becomes a historical reference. No tests affected.

---

### F3 — ENCODE: the program should compute `--base` itself; the required caller field can be demoted to an override or removed

**WHAT.** Move the base derivation from the check-in skill into `git-gatekeeper.py`: the program runs the merge-base of the caller's worktree HEAD against main (it already locates and reads that worktree for `--files`). `--base` becomes optional (an override for unusual cases and tests) or is removed; `unknown-base` / `base-not-on-main` become impossible by construction on the ordinary path.

**WHY.** The design already concedes the value is mechanical — C6 (folded into the spec as "the check-in skill front-loads the declaration (... `--base` computed as the merge-base ...)"; bindings text: "`--base` computed as `git merge-base HEAD origin/main` (the branch point GitHub used to compute for free)"). A skill is instructions an agent follows; the design's own doctrine prefers the stronger rung: "Most classic gate failures are made impossible by construction rather than detected," and field 8 already sets the precedent — "Computed by the program; callers generate nothing." A base the caller relays can be stale, mistyped, or truncated; a base the program computes cannot. This matches the project's ruled precedent exactly (the accepted `--base` worked example in my brief); the document under review still carries the pre-ruling form ("**`--base`** — the full 40-character commit id of the main state the work started from"), so either this is that ruling not yet folded in, or it is the same finding re-derived — the triager should check which.

**Ruling collision, flagged:** the request format belongs to "The 2026-07-24 boss-walked core — request/reply, digest, trailers, concurrency, states, error catalog — is unchanged by all of this." Changing the request block touches that walked core.

**LOST.** The caller can no longer declare a base other than its worktree's actual branch point — a deliberate old-base submission becomes inexpressible without the override flag. No realistic use was found: the concurrency section already treats a stale base as ordinary ("being behind is just 'main moved before we started'"), so nothing is gained by declaring one. Paid for by priority 1: one agent-relayed fact becomes mechanism.

**CONSEQUENCES.** Stale if this lands: the request block line "`--base <full-40-hex-commit-id>`"; field 3 in full ("No abbreviations ..., no branch names ..."); the catalog entries `unknown-base` / `base-not-on-main` (they survive only behind the override, or die); C6's bullet "`--base` computed as the merge-base" (the computation moves homes); the digest definition is unaffected (it still hashes the base id, now program-derived); T1's base-error cases narrow to the override path; T3 unaffected; the slice-5 CLAUDE.md workflow lines simplify. In the bindings doc, C6's third bullet becomes stale. In the slice plan, D1 is unaffected but the screening list in slice 1 loses two routine refusals.

---

### F4 — ENCODE: the `--agent` model half is mechanically derivable; the design's stated reason for caller declaration is contradicted by its companion document

**WHAT.** Derive the `Gatekeeper-agent` value mechanically — runtime from the environment (`AI_AGENT`, already verified present), model from the newest assistant record of the session transcript — with caller declaration retained only as the fallback for transcript-less callers. The natural home for the derivation is the caller side (the C6 PreToolUse hook, which is code, runs as the agent, and can read its own transcript), sidestepping the C2 cross-user readability question.

**WHY.** The design's justification for the declared field is: "Declared by the caller because the environment names the runtime but not the model" (field 6), and D3: "The caller is the only party that knows which model it is." But fast-handoff-design.md's verified-facts table (probe 2026-08-06) states: "Every assistant transcript record carries `message.usage` ... and `message.model`; context used is therefore computable from the transcript alone, in any session." The caller is not the only party that knows — the transcript knows, and the design already treats the transcript as reachable ("the session id points at a readable transcript of intent"). This is the cut class "facts used directly instead of derived": the design accepts a cooperative field that "a caller can declare wrongly" (D3) for a fact its own companion verified as mechanical. The trailer and B6 are untouched — this is "the same exact fact, delivered a better way," the shape of the project's accepted worked example.

**Ruling collisions, flagged:** B6 (boss-ruled 2026-07-31) requires the trailer line — unchanged by this finding. D3 stands in the ruled slice plan ("accepted by not being contested"); this finding contradicts D3's factual premise and says so plainly.

**LOST.** The purity of "Cooperative class: the gatekeeper records what it is told and never guesses" narrows — the machinery now asserts a fact rather than relaying one. Residual risk: a session that switched models mid-run records its newest model, not necessarily the authoring one — but the declared field carries the identical risk plus honest error, so this is not a regression. The fallback path (declaration) must still exist for callers with no transcript, so the field does not fully disappear. Paid for by priority 1.

**CONSEQUENCES.** Stale if this lands: field 6 in full (especially "Declared by the caller because the environment names the runtime but not the model"); the request-block line "`--agent <runtime/model>`" (becomes optional); slice-plan D3 in full; C6's division-of-labor sentence "the machinery derives or auto-fills everything else (base, session origin, digest, issue trailer form)" gains the agent value; T2's trailer assertion is unchanged in shape. Note: if the derivation is placed in the gatekeeper rather than the hook, verify first that the gatekeeper Unix user (C2) can read agent transcripts at all — see the A-better-way section.

---

### F5 — Structural consistency: the "only read of that worktree" invariant is contradicted by the advisory, and the false version feeds the C2 permission design

**WHAT.** Reconcile field 1's claim with the advisory: either amend the invariant to admit the advisory's whole-worktree status scan, or scope the advisory so the claim holds. Do not leave both statements normative.

**WHY.** Field 1: "The new content of each path is read from the invoking agent's working copy — the program's *only* read of that worktree." The advisory: "if the agent's worktree contains modified files *beyond* the declared ones, the reply carries a note." Detecting modifications beyond the declared paths requires reading (at minimum, statting and hashing) the worktree beyond the declared paths — the two statements cannot both be true. The slice plan repeats the false half (D1: "it reads the caller's worktree exactly once, for the declared paths") while slice 1 built the advisory (item 7). This is not phrase-polish: the C2 design must decide what read access the gatekeeper Unix user gets to agent home directories, and "N declared files" versus "the whole worktree" are materially different footprints. The advisory itself survives my refutation pass — it is built, T9-tested, cheap, and its consumer is the requesting agent catching the likeliest real failure ("the likeliest cause is a forgotten declaration") — so the fix is the invariant statement, not the mechanism.

**LOST.** The crisp one-read invariant — which was false, so nothing real. Paid for by priority 2.

**CONSEQUENCES.** Field 1's final clause; slice-plan D1's sentence "it reads the caller's worktree exactly once, for the declared paths"; T9 unaffected; the C2 read-footprint analysis (see A better way) must use the corrected version.

---

### F6 — Structural dedup: the error catalog is not the complete home it claims to be

**WHAT.** Fold `unsafe-path` (B2) and the transitional `unbuilt-option` into the spec's error catalog, or have the catalog state its exclusions. One normative home for endings.

**WHY.** The catalog's own banner: "The error catalog — every ending named, three-part teaching form." But two named refusals the built program emits today appear only elsewhere: `unbuilt-option` lives in the implementation-status paragraph ("reaching an unbuilt part is the named refusal `unbuilt-option`, never a crash") and in slice-plan D2; `unsafe-path` lives only in the slice plan ("plus B2's `unsafe-path`") — the spec's field 1 lists path-safety rules ("no absolute paths, no `..`, nothing under `.git/`") but names no refusal for violating them. A reader holding only the canonical spec — which the plan insists wins ("Where this plan and the specification appear to disagree, the specification wins and this plan is wrong") — has an incomplete ending list. (Caveat: B2's definition is in the build-bindings document I could not read; I know it only from the plan's quotation.)

**LOST.** The catalog gains one transitional entry (`unbuilt-option`) that must be removed after slice 5 — a small scheduled maintenance edit, which D2 already plans ("removed entry by entry as each slice lands, and is gone after slice 5"). Paid for by priority 2.

**CONSEQUENCES.** The catalog's *Form (instant)* line gains `unsafe-path`; a transitional line gains `unbuilt-option`; field 1's refusal list gains the unsafe-path name; T1's case list in the spec's Build-slice section is already satisfied by the built suite; nothing else moves.

---

## Hunt 1 — Prompts-to-code

Every place the design relies on an agent following English instructions, and the verdict:

1. **`--base` relayed by the check-in skill** — replaceable by program code. Finding F3.
2. **`--agent` declared by the caller** — replaceable by hook/program code reading environment plus transcript. Finding F4.
3. **The audit riding "each handoff scrub"** — an agent-performed duty whose vehicle no longer exists; replaceable by supervisor code. Finding F1.
4. **`--files` and `--message`** — genuinely interpretive, and ruled so: "auto-deriving the whole declaration would gut the intentionality the spec's `unchanged-path` refusal exists to force" (C6) and "Intent lives with the author; it cannot be auto-filled" (field 2). Correctly delegated; no finding.
5. **`--issue`** — the forcing function is the feature, per the project's own rejected worked example. No finding.
6. **The judgment-written issue comment on blocking outcomes** ("a genuinely blocking outcome earns a judgment-written comment by the requesting agent") — deliberately interpretive, cheap, with mechanical chatter already excluded. Correctly delegated.
7. **Cancel discipline** ("the workflow simply does not teach cancel as a routine move") — trained-habit reliance, but the stakes are bounded by cancel's own safety (three outcomes, all recoverable). Acceptable residue.

Everything else on the check-in path is already code: digest, screening, candidate construction, trailer writing, retry loop, crash recovery. The design is unusually good on this axis.

## Hunt 2 — A better way / unknown unknowns

**The C2 boundary is bidirectional, and the design only states one direction.** C2 makes the credential unreadable by agents; nothing in any of the four documents states how the gatekeeper Unix user reads the *caller's* worktree — yet field 1 requires exactly that ("read from the invoking agent's working copy"), and the advisory requires scanning the whole worktree (F5). On a default setup, `nedlern`'s home is not readable by another Unix user; C2 itself verified tight modes there ("`~/.config/gh/hosts.yml`, mode 600, owner `nedlern`"). The same question applies to environment passthrough: origin is "auto-filled from the session environment," but `sudo` strips the environment unless sudoers whitelists `CLAUDE_CODE_SESSION_ID`. Neither binding is designed anywhere I could read. This is not a proposal to add machinery — it is a missing decision that C2's installation will hit on day one.

**One shape dissolves three problems at once.** C8's first candidate — "the caller pushes its branch first and the gatekeeper reads content from the branch ref (a real contract change — the request names a ref instead of relying on worktree bytes)" — would simultaneously solve C8 (cross-machine callers), the C2 worktree-read direction above, and F5's advisory-footprint question (the declaration is exactly the ref's diff; no worktree scan exists). C4 already opens branch pushes ("branch pushes stay open — the #45 'push-less' ruling covers main only; verified by dry run"). The design defers C8 until "a Mac-side agent first needs direct check-in" — reasonable in isolation, but the C2 read problem arrives with C2's installation, much sooner. Recommend the C8 decision inherit that added weight rather than waiting for the Mac trigger. This is a question for the walk, not a deletion — the worktree-bytes contract is boss-walked core.

**No other unknown-unknown found.** The problem framing — one program, one credential, one door, atomic push as the only arbiter, resubmit as the only recovery — is the right shape; I looked for a simpler substrate (plain protected-branch PRs, GitHub merge queue, CI-hosted gate) and each was already considered and rejected in the text with reasons that hold ("An App or CI job relocates the gate into CI, which this design scopes out").

## Leanness certification

I examined each mechanism against the replacement test (name the simplest existing thing that could deliver the same result) and certify the following lean:

- **The digest** (field 8): git's own commit hash cannot serve (it hashes metadata the design deliberately excludes — "the digest identifies **the work**"); a content digest computed by the program, callers generating nothing, is minimal. The exclusion list is deliberate and correct for dedup-on-resubmit.
- **Concurrency**: "a push either wins cleanly or is rejected whole ... No queue and no lock are built" — the atomic push *is* the simplest existing arbiter; the five-round cap and `main-moving-too-fast` are named bounds, and the semantic-interaction gap is explicitly accepted ("the accepted gap, recorded"), which is exactly how an unsolvable remainder should be handled. The deferred optimizations carry named triggers.
- **Crash recovery**: "The whole pipeline has exactly two durable effects ... Recovery is: **resubmit**. No journal, no repair mode." Nothing simpler exists; certified.
- **The reply contract** (B1): one JSON object, exit trichotomy 0/1/2 — the 2-versus-1 distinction has a named consumer ("so loop counters and the audit never read a gatekeeper bug as a correct refusal"); certified.
- **Records**: "git history and the invoking session's ordinary transcript are the *only* records" — the cut table already deleted the separate audit log and the entry-manifest row; `imports` derives its table from trailers. Certified; `Gatekeeper-origin` is auto-filled and near-free, and its pointer decaying with transcript retention is an acceptable, already-implied residual.
- **Break-glass (C5)**: the standard-library-only single-file invariant making every historical version directly runnable is the cheapest possible recovery mechanism; the rejected standing ungated agent was rightly rejected. Certified.
- **The cut table itself** and the slice decomposition (slices 1–3 built, 146 cases, credential-free against throwaway repositories): a working leanness ledger. Slice 4 (worker lifecycle) is in the ruled forward plan and per the roadmap rule is not a valid deletion, though the triager should note its rationale ("The worker lifecycle serves slow checks, and there are no slow checks yet") shares its trigger with a mechanism the cut table defers — I raise that as an observation, not a finding, because the project's build-early preference and the explicit roadmap both cover it.
- **B4c/B4d workspace mechanics**: resolve-once request records and the refused-`--no-wait` retention with its named residual ("a caller crashing between sweep and read loses the reason — rare, recoverable by resubmit") are walked amendments with honest residuals; certified.
- **C7 seam refusal**: the minimal answer to a real privilege surface; certified.

The rest of the document — request fields not named in F3/F4, the procedure's seven steps, the trailer block, the states — is already lean.
