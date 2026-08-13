<!-- provenance: runtime=claude model=claude-fable-5 effort=xhigh attack=mechanization doc=gatekeeper isolation=instruction-pinned document set -->

All four documents read. This design is unusually well-mechanized already — the digest, trailers, candidate construction, crash recovery, and cooperative hooks are model examples of the pattern this attack hunts for — so most sites clear. Five findings survive self-refutation, one of which collides with a recorded design point (D3) and is flagged as such, not re-litigated.

---

# Mechanization attack report — git-gatekeeper specification at 0890848

## Prompts-to-code table

Every site where the document set relies on an LLM following English instructions or a human remembering a duty:

| # | Site (quoted or named) | Disposition |
|---|---|---|
| 1 | `--files` — agent chooses what constitutes the change | Residue (scoping is intent); the *relay* is already mechanized (C6: "relayed from the agent's own staging") |
| 2 | `--message` — the what-and-why | Residue; the spec itself certifies it: "Intent lives with the author; it cannot be auto-filled" |
| 3 | `--base` — 40-hex commit id | Already mechanized (C6 skill: "computed as `git merge-base HEAD origin/main`") — the accepted worked-example finding |
| 4 | `--import` triple — what to import, from where | Residue (curation judgment); validation already mechanized (`import-source-missing`, `import-incomplete`, …) |
| 5 | `--issue` — which issue, if any | Residue ("The artifact-lifecycle rule decides upstream"); existence-check candidate **rejected**: it catches only nonexistent numbers, not wrong ones, and buys a network+auth dependency inside "instant and synchronous" screening |
| 6 | `--agent <runtime/model>` — declared by the caller | **Finding F3** |
| 7 | Origin | Already mechanized (auto-filled; B4c resolve-once) |
| 8 | The digest | Already mechanized ("Computed by the program; callers generate nothing") |
| 9 | Candidate construction; unchanged files from main | Already mechanized (constructive guarantee: "an undeclared edit never reaches it") |
| 10 | Trailer writing | Already mechanized ("the program writes the trailers itself") |
| 11 | Duplicate detection | Already mechanized (digest screen at submit) |
| 12 | Advisory — detection of undeclared worktree diffs | Detection mechanized; the response ("confirm intentional") is residue |
| 13 | Concurrency loser handling, retry cap | Already mechanized (program rebuilds; five rounds → `main-moving-too-fast`) |
| 14 | Conflict resolution | Residue, boss-ruled: "the program never guesses" / C6: "the one thing the machinery must never fake" |
| 15 | Crash recovery | Already mechanized ("one rule, not a procedure": resubmit; digest-vs-history decides) |
| 16 | Agent resubmits after crash/lost connection | Cleared — one sentence riding trained retry behavior; the mechanism makes any retry safe |
| 17 | `status` / `cancel` outcomes, abandoned-worker detection | Already mechanized (worker.pid; three named cancel outcomes) |
| 18 | Cancel permission — "no permission machinery … the workflow simply does not teach cancel as a routine move" | Cleared — deliberately cooperative, boss-ruled; not re-litigated |
| 19 | Revert construction ("an ordinary check-in whose change undoes a previous one") | Cleared — `git revert` in the caller's worktree already mechanizes the inverse computation; the gate path stays ordinary by design |
| 20 | Issue-timeline collection via `#<n>` | Already mechanized ("zero machinery"; `git log --grep` derivation) — exemplary |
| 21 | Judgment-written issue comment on a genuinely blocking outcome | Residue ("comments are for genuinely new events" is a semantic bar) |
| 22 | Trailer-absence audit — *detection* | Mechanized (slice-5 contract, T12) |
| 23 | Trailer-absence audit — *trigger*: "at each handoff scrub" | **Finding F1** |
| 24 | Branch-protection audit, three outcomes | Already mechanized (B3c: "never a silent skip into green") |
| 25 | C2 Unix boundary — installation | Cleared — one-time, root-held, deliberately human |
| 26 | C2 Unix boundary — *continued correctness* (credential mode, sudoers scope) | **Finding F5** |
| 27 | C4 token replacement | Cleared — one-time human act, verified by dry run |
| 28 | Credential expiry renewal (C5.3, "the user's alone") | **Finding F4** — the duty stays human; the *reminder* has a computable trigger (a date) |
| 29 | Break-glass approval (C5.2) | Human residue by design — the in-the-moment password IS the security property |
| 30 | "the gatekeeper stays one standard-library-only file" (C5.1 standing invariant) | **Finding F2** |
| 31 | C6 gh-rewrite hook, push-deny hook, check-in skill auto-fill | Already mechanized (the cooperative tier is itself the mechanization of trained habits) |
| 32 | CLAUDE.md workflow lines | Cleared — recorded boss ruling: "documentation, never enforcement"; C2 is the boundary |
| 33 | C7 seam refusal under the privileged user | Already mechanized (named refusal, pinned remote) |
| 34 | Going-live decision, growth-point triggers (tests join checks, impact analysis, merge queue, slice 6) | Human strategic residue; every trigger is named in the text |
| 35 | C8 cross-machine callers | Open by the documents' own account; no finding derivable from this set |
| 36 | Refused `--no-wait` workspace never collected by `status` — lingers | Rejected candidate: negligible litter, no real failure; guard applies |
| 37 | Implementation-status header upkeep in the spec | Cleared — low stakes, loud at review time; document-drift class, not gate design |
| 38 | Slice plan D2 — `unbuilt-option` "removed entry by entry as each slice lands" | Cleared — each slice's own tests catch a stale refusal |

The fast-handoff document's "re-run both canaries after every Claude Code upgrade" is the same duty class as F4 (computable trigger: a version comparison), but it belongs to that design, not this one — noted here, not filed as a finding against the gatekeeper spec.

---

## Findings, deepest first

### F1 — The audit's trigger names superseded machinery; anchor it to the supervisor's recycle cycle

**WHAT.** Replace the trailer-absence/branch-protection audit's trigger — currently the English phrase "at each handoff scrub" — with a mechanical anchor: the audit script runs as a rider in the supervisor's recycle cycle, alongside the existing queue-status step (or, failing that, a cron entry). Slice 5's contract gains the wiring, not just the script.

**WHY.** The spec: "a standing audit at each handoff scrub scans main for commits missing valid trailers and files a `draft` issue naming them." But the fast-handoff design at the same snapshot lists "the scrub modes" among "the superseded machinery … recoverable at `git show e178e67`," and its recycle step 5 says plainly "full manual scrubs died with the committed tier." The audit's trigger therefore points at a mechanism that no longer exists; as written, running the audit is an agent-remembered duty with no anchor at all. The fast-handoff design already demonstrates the correct pattern in the very step that replaced scrubs: "one automated queue-status line — each queue's depth and oldest item, computed by script: the artifact-lifecycle rot-visibility duty riding every recycle at zero agent cost." The audit is the same genre of rot-visibility duty and should ride the same mechanical event. Ruling check: the audit's *existence and detection role* trace to the boss ruling ("CLAUDE.md is documentation, never enforcement…"); only the scheduling is touched here — no collision.

**LOST.** Nothing interpretive; a line of supervisor coupling between two designs that were previously coupled only by this stale phrase. Priority 1 pays: zero remembered steps.

**CONSEQUENCES.** The spec sentence quoted above changes its trigger clause. The fast-handoff design's recycle-cycle list gains the rider (a companion-document edit). The slice plan's slice-5 row ("Enforcement surfaces: trailer-absence audit, branch-protection audit…") gains trigger wiring, and a test alongside T12 asserting the audit fires at recycle. T12 itself (detection) is unchanged.

### F5 — The C2 boundary has no drift detection, while the weaker GitHub-side boundary does

**WHAT.** Extend the slice-5 audit with a local-boundary check, three-outcome style (`boundary-ok` / `boundary-wrong` with the difference named / `boundary-audit-failed`): (a) attempt to read the gatekeeper credential path from the agent side and require permission-denied; (b) parse `sudo -l` and require the agent's grant to name exactly the gatekeeper program.

**WHY.** C2 is, in the design's own words, "where the enforcement actually lives … the step at which 'agents never push' becomes impossible rather than instructed." Yet the design audits only the *GitHub* side for drift — and justifies that audit against deliberate human acts: "a protection change by any owner is a deliberate, visible act," and still "(The audit also covers the sibling residual while it exists: an agent-held owner credential could deliberately edit protection — same cooperative class, same catch…)." The Unix side is *more* drift-prone (a chmod during debugging, a broadened sudoers line — no GitHub audit log equivalent), and its failure is perfectly silent: nothing breaks when the credential becomes agent-readable, because agents are trained not to push. That is exactly the "silent skip into green" that B3c exists to prevent. Both probes run unprivileged from the agent side, so the check costs a stat attempt and a `sudo -l` parse. No ruling collision: C2 (user-ruled) establishes the boundary; B3c establishes the audit pattern; this composes them.

**LOST.** Small audit complexity, and a false alarm if the credential path is deliberately relocated — the `boundary-wrong` outcome names the difference, so the alarm teaches. Priority 1 pays.

**CONSEQUENCES.** § The credential and enforcement gains the check next to the branch-protection audit's three outcomes; the C2 bullet's "unreadable by agent sessions" becomes verified rather than asserted; the slice plan's slice-5 row and test list grow one case. The bindings document's C2 ("This is what makes 'agents never push to main' mechanical rather than instructed") is strengthened, not contradicted. Note honestly: this lands only when C2 itself is installed — "still true until C2 is installed" marks the current gap.

### F2 — The standard-library-only single-file invariant is carried by builder habit; enforce it in the test suite

**WHAT.** Add a test case to the existing suite: parse `scripts/git-gatekeeper.py`'s AST and assert every `import`/`from … import` resolves within `sys.stdlib_module_names`, and that nothing is imported from the repository (single-file property). Roughly ten lines.

**WHY.** C5's break-glass path rests on this: "the program stays **one standard-library-only file** precisely so any historical version is directly runnable," and the bindings adopt it as a "Standing invariant." Today every future editor must *remember* it — and its violation is silent: a third-party import works fine on the dev box where the package is installed, and the recovery property ("`git show <good-sha>:scripts/git-gatekeeper.py > /tmp/gk.py`" being directly runnable) dies unnoticed, discovered only during the emergency it exists for. The suite already holds a precedent of exactly this genre: "B3d's version-floor smoke assertion (Python ≥ 3.12, git ≥ the recorded floor…)." No collision — this enforces the C5 ruling rather than amending it.

**LOST.** The freedom to add a dependency or split files without tripping a test — which is the invariant working. Priorities 1 and 3 both pay.

**CONSEQUENCES.** The C5 bullet gains "enforced by test"; the spec's § Build slice test list and the slice plan's test conventions gain one case. Nothing else becomes false.

### F3 — The `--agent` model half is a fact re-derived by the caller when the transcript records it authoritatively. ⚠ Collides with recorded design point D3 — flagged, not re-litigated

**WHAT.** The check-in skill (C6 tier) auto-fills `--agent`: runtime and version from the environment (`AI_AGENT`), model from the session transcript's newest assistant record — the same tail-read pattern the threshold hook already uses. The declared field remains as the fallback for transcript-less callers, exactly as origin already degrades to `none`. Lesser rung if rejected: the gatekeeper cross-checks or the field at least gains a shape grammar (`<runtime>/<model>`, one slash, non-empty halves) beyond today's "required and non-empty."

**WHY.** This is the brief's named cut class — a fact an LLM is asked to supply that a primary source records. The spec justifies declaration with a premise: "Declared by the caller because the environment names the runtime but not the model," and D3 sharpens it: "The caller is the only party that knows which model it is." That premise is contradicted by a verified probe in this document set — the fast-handoff table records: "Every assistant transcript record carries `message.usage` … and `message.model`; context used is therefore computable from the transcript alone, in any session (probe 2026-08-06)." The model *is* in the environment's records; the transcript path is derivable from the session id the gatekeeper already auto-fills as origin. The stake is the fix ladder: "the fix ladder's escalation needs to know what tier produced an artifact to know whether stronger models remain" — a misdeclared model (agents' self-reports of their own model are not reliable) silently poisons an immutable git record that escalation decisions later read. Semantically nothing changes: today's declaration is also "the model of the agent checking in," just self-reported instead of read from ground truth. C6's division of labor already points this way: "the machinery derives or auto-fills everything else (base, session origin, digest, issue trailer form)" — this moves `--agent` into that list, the exact move the accepted `--base` worked-example made. Skill-tier derivation (not gatekeeper-side) is deliberate: post-C2 the gatekeeper user may not read agent-owned transcript files, and the honest-singleton stance — "the gatekeeper records what it is told and never guesses" — stays literally true.

**Collision, stated plainly:** D3 is a recorded design point, "accepted by not being contested" when the 2026-08-08 walk closed at item 1. This finding contradicts D3's factual premise and must be walked, not slipped in. B6 (boss-ruled 2026-07-31: the trailer exists, never omitted) is untouched.

**LOST.** The notion that the agent's self-report is authoritative; a composition step in the skill (`message.model` gives e.g. `claude-opus-5`; runtime from `AI_AGENT`). Honest caveat: the transcript value names the model *at check-in time*, not every model that touched the change over prior turns — but the declared value has exactly that semantics today, so nothing weakens. Priority 1 pays.

**CONSEQUENCES.** Spec field 6's rationale sentence ("…because the environment names the runtime but not the model…") becomes stale. D3's section in the slice plan becomes stale in whole ("The caller is the only party that knows which model it is"). C6's auto-fill list gains an entry. B6, the trailer format, and T2's exact-trailer assertion are unchanged; the skill's own tests gain a derivation case.

### F4 — Credential expiry is a remembered human duty with a computable trigger (a date)

**WHAT.** Mechanize the *warning*, not the duty: the slice-5 audit (or the gatekeeper's reply `summary` after a successful push) reports days-to-expiry of the token it used, and flags below a threshold through the audit's existing draft-issue channel. The renewal itself remains "org-owner territory; the user's alone by C3" — untouched, so no collision with the C5 ruling.

**WHY.** Fine-grained tokens (C4's chosen form, and the gatekeeper account's) expire on a date — a computable trigger, my brief's named class for remembered duties. Today the first notice is `push-auth-failed` at an arbitrary check-in: named and "safely resubmittable," yes, but it takes the entire check-in lane — every agent's — down until the one human acts, at an unplanned moment. A dated warning converts an outage into scheduled maintenance. I report this at reduced weight because the guard cuts against it — the failure *is* loud and recoverable — and I state plainly what I cannot verify from this document set: that the GitHub API exposes token expiry to the token holder (I believe it is returned as a response header on authenticated calls, but no document here records a probe). If that probe fails, the finding dies.

**LOST.** A few audit lines and a dependency on an unprobed API surface. Priority 1 pays if the probe passes.

**CONSEQUENCES.** C5.3 gains a sentence (the duty unchanged, the trigger mechanized); the audit's outcome list or the reply `summary` grows a line; slice plan slice-5 row. Nothing becomes false.

---

## Delegated residue, certified

These rightly stay with the model (or the human), and no code can carry them:

1. **`--message`** — the spec's own certification stands: "Intent lives with the author; it cannot be auto-filled." Code can observe *what* changed, never *why*.
2. **`--files` selection** — deciding what constitutes one coherent change is scoping intent; any auto-derivation "would gut the intentionality the `unchanged-path` refusal exists to force" (C6, verbatim).
3. **`--issue` assignment** — whether work is a wanted-thing with an issue is semantic classification made "upstream, at the right granularity"; the gate correctly only records the answer.
4. **Conflict resolution** — ruled and correct: re-applying over same-content changes "would require guessing the author's intent, and the program never guesses." No algorithm knows which of two intents should survive.
5. **Advisory response** — only the author knows whether an undeclared worktree diff is a forgotten declaration or legitimate work-in-progress; the design rightly detects mechanically and never blocks.
6. **Blocking-outcome issue comments** — "genuinely new events" is a semantic bar; auto-posting is exactly the mechanical chatter the design bans.
7. **Import curation** — what to import from the legacy repository, and at which commit, is judgment about value; validation of the declared triple is already mechanical.
8. **Deliberately human, not model residue but named for completeness:** break-glass approval (the in-the-moment password is the security property — automating it would delete it), org-owner acts (C3's whole point is that no process holds them), going-live, and the growth-point triggers — strategic decisions whose *triggers* the text already names, which is the mechanization those decisions admit.

**Bottom line for triage:** F1 (stale trigger — the audit currently hangs on machinery the fast-handoff revision retired) and F2 (ten lines protecting the break-glass path) look like clean accepts; F5 extends an audit pattern the design already committed to; F3 is real but collides with D3 and needs the walk; F4 is the weakest and depends on an unverified API probe.
