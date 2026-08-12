<!-- Triage of the Codex leg's four cells (rerun 2026-08-11 against the
     post-walk revision of the spec). Produced by a Fable-class triage agent
     reading the four codex-*.md reports, the current spec, the current
     program (post-151e046), and dispositions.md's ruled record; verified by
     choirmaster with spot-checks (FIX-1, FIX-2 confirmed against the file
     and compute_digest respectively). Walk pending: the WALK items and the
     FIX batch below await the user's rulings — marks land here. -->

# Codex-leg triage — md-review of git-gatekeeper-design.md (2026-08-11)

Finding keys: **G#** = codex-hunt-good (sol, 87 findings), **F#** = codex-hunt-floor (terra, 28 findings). Verified against the current spec, the current program (post-151e046), the bindings doc, the slice plan, and fast-handoff-design.md.

## 1. Restate verdicts

**codex-restate-good (sol): succeeded.** A faithful, near-complete reconstruction, including the subtle mechanics (digest exclusions and framing, B4d lifecycle, the loser-path digest re-screen, the computed base, the catalog collapse, C1–C8). It misread slice 6 as *built* (its item 2) and explicitly hedged on T5's "same-content collision" and T8's "all three outcomes" — all three spots correlate with hunt findings (G1/F1, G83/F26, G51/F27), confirming those as real document defects (FIX-1, FIX-7, FIX-8 below).

**codex-restate-floor (terra): succeeded.** Accurate sentence-level restatement with nothing invented; it even captures the C7-struck-to-zero and S3-deletion reasoning correctly. Its one misread is the same slice-6-as-implemented reading (item 2) — the two cells' *shared* misread marks FIX-1 as the document's worst comprehension defect. Unlike sol, it transmitted the T5/T8 contradictions and the "only content read" overstatement without flagging them — faithful, but hedging less.

## 2. WALK — genuine design questions for the owner

- **WALK-1. Symlink and path-type semantics at the gate** (G15, F6). The `--files` validation ("no absolute paths, no `..`, nothing under `.git/`") says nothing about symlinks. Verified in the program: `Path.is_file()` follows links, so a declared symlink-to-file passes as regular and its **target's** bytes — possibly outside the repository — are read as the declared content; candidate writes into the clone could likewise follow a base-checkout symlink. The gate is the security boundary; ruling needed: refuse symlinks (the program already refuses other non-regular files as `malformed-field`) or define their semantics.
  processed 2026-08-11 → accepted as recommended: refuse outright as
  `malformed-field`; semantics grow in when a real need arrives. Spec
  field-1 sentence added; program change queued in the slice plan's
  follow-ups (applies with the fix batch).
- **WALK-2. CLI endings outside the JSON contract** (G27, F10, G3, part of G53). "Every invocation prints exactly one JSON object on stdout" is false for argparse-level failures: no subcommand, unknown flag, `check-in` without `--files` → usage text, exit 2 (the *program-defect* code). And slice-5's surface has no registered subcommand, so reaching it gives an argparse error, not the promised `unbuilt-option`. Ruling: wrap the parser so form-level CLI errors become `malformed-field` JSON, or scope the every-invocation claim.
  processed 2026-08-11 → accepted, option 1 (wrap the parser): the JSON
  contract holds at every layer, exit 2 stays a true defect signal. Spec
  exit-code paragraph amended; program change queued in the slice plan.
- **WALK-3. Advisory misses untracked files** (G37). Verified: the program uses `git status --untracked-files=no`, so a forgotten **added** file — the advisory's likeliest target — is never flagged, though added paths are accepted check-in content. Ruling: include untracked files (noise risk) or record the residual.
  processed 2026-08-11 → accepted, include untracked: the advisory's
  likeliest target is a forgotten new file, gitignore bounds the noise,
  and the advisory has a live consumer (the calling agent, same turn).
  Spec advisory paragraph amended; program change queued.
- **WALK-4. Cancel-versus-push child race** (G52, F18). Killing `worker.pid` does not kill an already-spawned `git push` child; the history query can return before the child's push lands, so `cancelled` can be reported and the commit arrive afterward. Fix shape is mechanical (process-group kill + wait before querying) — slice-4 scope, like the ruled 4.1.
  processed 2026-08-11 → accepted as recommended: spec cancel paragraph
  amended (group kill, wait, then query); slice-4 build note queued
  beside 4.1 in the slice plan.
- **WALK-5. The protection audit's trigger anchor is stale** (G73, F23-part). The audit runs "at each handoff scrub (the cleanup pass every agent session runs when handing off)" — but fast-handoff-design.md (2026-08-02 revision) records that scrub modes were superseded and "full manual scrubs died with the committed tier." The audit needs a live cadence anchor (the recycle cycle?) — owner names it; slice-5 scope.
  processed 2026-08-12 → accepted, anchor named: each session recycle,
  riding the fast-handoff supervisor's cycle — no new machinery, runs
  several times a day. Spec audit sentence amended; slice 5 builds it
  there.

**Environment note** (from G79, otherwise rejected): `~/Projects/nedlern` does not exist on this box, though CLAUDE.md and the program's `--legacy-repo` default point at it. Imports would refuse `import-invalid` (named, safe) until a legacy checkout exists here. Worth the owner's awareness, not a spec defect.

## 3. FIX — defects in the current text, most important first

FIX batch processed 2026-08-12 → approved by the user as one batch and
applied: all 23 corrections landed in the spec (29 replacement spots),
FIX-2's program half landed as the digest length-prefix reframing with a
crafted-collision regression test, and the three ruled program changes
(WALK-1 symlinks, WALK-2 parser contract, WALK-3 untracked advisory)
applied alongside. Suite 150 cases green. Remaining from this triage: the
environment note (walk item 26).

- **FIX-1. Slice-6 status misparses as "built"** (G1/F1; G38, G85, G87, F28; both restates misread it). Quote: *"is BUILT through slice 3 of five — plus slice 6 (the review-evidence check), scheduled 2026-08-10 as a prerequisite of activating the privileged lane —"*. "Plus slice 6" grammatically attaches to BUILT; both restate cells read slice 6 as existing, while § Open says its evidence format is undesigned. Also "scheduled 2026-08-10" is ambiguous (ruled on that date vs. due that date) and now past. Correction: *"BUILT through slice 3 of five (a sixth slice, the review-evidence check, was added by ruling 2026-08-10 as a prerequisite of activating the privileged lane; not yet built — its evidence format is undesigned, § Open)"*.
- **FIX-2. The digest-framing claim is false** (G25). Quote: *"NUL-framed field tags between components, so concatenation can never make two different requests read as one."* Verified in `compute_digest`: content bytes carry no length prefix, so a single file whose bytes contain `x\0path\0b\0content\0y` serializes identically to two files `a`→`x`, `b`→`y` — two different requests, one digest, wrong dedupe. A broken mechanical guarantee. Correction: length-prefix content in the program (queue in slice plan) and restate the canonical form; interim spec fix: drop "can never".
- **FIX-3. "The raw-push residual is detected at its source" is now false** (G72/F23, G78, G75/F24). Quote: *"The raw-push residual is \*detected at its source\*, not prevented: a standing branch-protection audit…"*; cut-table row 8: *"the procedural gap is audit-detected (that audit itself deleted 2026-08-10)"* — self-invalidating. The protection audit checks **configuration**; a pre-C2 authorized raw push leaves configuration green, and S3 deleted the only detector that saw commits. Correction: reword — the audit detects protection drift; the pre-C2 raw-push gap is accepted undetected (S3's no-consumer reasoning), closed by C2; while rewriting, widen *"can arise only from break-glass … or a protection failure"* with "or a gatekeeper defect" (G75/F24). Fix the cut-table parenthetical to say the *trailer* audit was deleted, not the gap's detection story.
- **FIX-4. SCREENING state contradicts the procedure** (G31, F13). Quote: *"SCREENING (synchronous, in memory, nothing on disk)"* vs. the walk-applied 2.14 sentence *"the built program creates the workspace clone during screening."* Correction: *"SCREENING (synchronous; only a scratch clone on disk, nothing keyed by digest)"*.
- **FIX-5. Import destination's content source, and the missing `--legacy-repo`** (G16, F8). Quote: *"The new content of each path is read from the invoking agent's working copy — the program's only \*content\* read of that worktree"*. Verified: the program **exempts** the import destination — its bytes come from the legacy repository at the declared commit ("the caller need not — and should not — stage a hand-made copy"). Also the grammar lacks `[--legacy-repo <dir>]` (built, default `~/Projects/nedlern`), which the `import-invalid` "unreadable legacy checkout" refusal presupposes. Correction: one exception clause in field 1 or 4; add `--legacy-repo` to the grammar.
- **FIX-6. The import view lists every commit** (G30; F12 folded). Quote: *"`git log origin/main --grep \"Gatekeeper-import:\"` lists every import"*. Every gatekeeper commit carries `Gatekeeper-import: none`, so this lists every check-in. (The suite's own test greps a narrower pattern.) Correction: `--grep "Gatekeeper-import: .*->"` (the arrow appears only in real imports), here and in cut-table row 3; optionally "after a fetch".
- **FIX-7. T5 says "same-content", contract says same-path** (G83, F26; restate-good hedged). Quote: *"T5 conflict: same-content collision refuses"*. 2.18's ruled wording ("same path(s)") was applied in the concurrency section but T5 was missed; same content would answer `already-checked-in`/`unchanged-path`. Correction: "same-path collision".
- **FIX-8. T8 "all three outcomes" vs. "Outcomes, exactly four"** (G51, G84, F27; restate-good hedged). The walk's 2.4 fix changed cancel to four outcomes but left T8 at three. Correction: *"T8 cancel: all four branches (two return `cancelled`); cancel-after-push answers `too-late`"*.
- **FIX-9. "cancel — built in version 1" vs. contract-only slice 4** (G50, F17). Quote: *"**`cancel <digest>`** — built in version 1 (boss ruling: …)"*; Implementation status says slice 4 "remain[s] contract-only" and the program returns `unbuilt-option`. Correction: *"in version 1's contract (boss ruling …; slice 4, unbuilt today — Implementation status)"*.
- **FIX-10. "Can never be made to run agent-written bytes"** (G64, F21). Quote: *"a stale copy enforces the old contract and can never be made to run agent-written bytes"*. The gatekeeper's source *is* agent-written (walked-approved) and self-updates — literal contradiction. Correction: *"…never run bytes an agent planted in place directly — only walked-approved content from main"*.
- **FIX-11. C7's recorded reasoning has a factual hole** (G70, F22). Quote: *"a foreign remote dies at GitHub's authentication because the credential is scoped to this one repository"*. A local-path remote needs no authentication at all. The S8 ruling (no guard) stands; correction to the reasoning: *"…and a non-GitHub remote — a local path — was never the protected asset"*.
- **FIX-12. Refusal side-effect absolutes vs. the S7 fetch and the sweep** (G9, F3, G33, G82; G12/F4's "Same request, same answer" folds in). Quote: *"The repository is untouched — a refusal has no side effects, with one named exception"*. The base-computation fetch (added by S7) updates the caller's remote-tracking refs; any invocation's expiry sweep deletes aged records; and a push-accepted-ack-lost `network-down` leaves the commit **on** main (resubmit self-heals to `already-checked-in`). Correction: scope the absolute to worktree files and main, name the fetch-metadata touch and the ack-lost corner; qualify "Same request, same answer" for infrastructure weather; T1's "no side effects" inherits the scoped meaning.
- **FIX-13. "Every project script runs as `python3 <path>`" is false** (G17). `scripts/launch-claude` is `#!/bin/sh` — its exec bit is operative. The 1.3 residual ruling stands; correct only its supporting fact ("the scripts the gate carries today are interpreter-invoked or already carry their bit").
- **FIX-14. Revision-note date stale** (G4). Quote: *"This revision (2026-08-09) folds in…"* vs. frontmatter `design-as-of: 2026-08-11` and 08-10/08-11 rulings folded into the same paragraph. Correction: *"This revision (2026-08-09, amended through 2026-08-11)"*.
- **FIX-15. Unclosed WORKING parenthesis** (G42, F13/F14). The paren opened at *"WORKING (candidate built and checked"* never closes — the close before "→ PUSHING" belongs to B4c. Correction: close it; while there, "candidate **being** built and checked".
- **FIX-16. Path-character validation unstated** (G14; G5's and G53's unsafe-path clauses fold in). The program (and the bindings doc's ruling) refuses whitespace, `->`, non-printable, non-ASCII path bytes — now as `malformed-field` — but the field-1 "exact validation" omits the rule entirely. Correction: one clause in field 1.
- **FIX-17. "Omitting `--import` entirely" is ambiguous** (G21). Since the valid triple form also omits the `--import` flag, the sentence permits opposite readings. Correction: *"omitting the import choice entirely — neither `--import none` nor the triple —"*.
- **FIX-18. Digest-scope sentence overreaches** (G26, part of G12). Quote: *"when that work is already checked in, its declared paths now match main and the answer is `unchanged-path`"* — untrue when main has since moved those paths. Correction: *"…match main (unless main has since moved them) and the answer is `unchanged-path`"*.
- **FIX-19. Fetch-failure disposition unstated** (G20, F7). Verified: the program ignores fetch failure (`check=False`) and refuses `malformed-field` when merge-base fails. A failed fetch degrades to a stale base — safely, since the behind-main mechanism handles it — but the spec's "exact right value deterministically" doesn't say so. Correction: one clause in field 3.
- **FIX-20. "Between sweep and read" is garbled** (G46). Correction: *"between the program's sweep and the caller's receipt of the reply"*.
- **FIX-21. Crash-recovery's third world** (G47). Quote: *"leaves one of two worlds"* — verified: a crash mid-screening leaves an unkeyed `screening-*` scratch clone that digest-keyed recovery never sweeps. Harmless litter, but the two-worlds claim is load-bearing. Correction: name it; fold `screening-*` cleanup into the 1.4 opportunistic sweep (program follow-up).
- **FIX-22. Cut-table "status derives from history"** (G77, F25). The reply section says history **plus the workspace**. Correction: *"derives from history plus the transient workspace"*.
- **FIX-23. Founding plan never pathed** (G80-part). Cited ~5 times with no path; 3.4-style pointer at first use: `docs/cross-project/nedschorus-founding-plan.md`.

## 4. MOOT / STALE / REJECT summary

**MOOT (24):** G6 (2.1/2.2), G7+F2 (2.24), G10 (2.3), G13, G54 (2.21), G12-part (1.1), G19-part (S7), G22+F9, G23-part, G76 (3.4), G29 (1.5), G36 (1.1/4.1), G44, G48, G71, F15, F16 (4.1), G45 (1.4), G58 (2.23), G62+F20 (1.2/S2), G65 (S2), G66 (3.10), F19 (3.11).

**STALE (3, all overtaken by commit 151e046):** G2 (`imports_table` "still defined" — deleted), G19-part ("implementation still requires `--base`" — computed now), G53-part ("still emits `missing-message`, `empty-change`, `unknown-base`, import-specific names" — all collapsed/retired in the program).

**REJECT (30):** G8 (trailer = the design's defined record; the commit carries content/message), G11, G24 (origin/transcript explicitly best-effort cooperative), G18 (synopsis placeholder is guidance), G23-part (stated validation *is* non-empty), G28 (store-corruption enumeration below spec altitude), G32 (step-7 happy-path context; status contract names both sources), G34, G35 (constructive guarantees scoped to declared, gate-processed work), G39 (v1 syntax-only is stated), G40 (deliberately judgment-based), G41 (deferral prose, not contract), G43 ("digest alone" within the operative environment the same sentence defines), G49 (cancel is the hung-worker remedy; timeout = machinery without consumer), G55 ("after the slice ships" arm covers it), G56 (derivative aggregate), G57, G59, G60, G61, G74 (threat/implementation altitude; C3 closes the class), G63 (activation explicitly waits on slice 6), G67 (template is an author-completed prefill), G68, G69 (deliberate manual lane), G79 (environment, not spec — noted above), G81 (values pend the account naming), G86 (issues are the project's record medium), G5 (its "sole normative home" contradiction misreads the antecedent — the C-doc, not the B-doc; its unsafe-path substance survives in FIX-16), F5 (under the seam, the caller checkout's origin *is* the test remote), F11 (atomic-consume detail below spec altitude).

## Walk order

WALK COMPLETE 2026-08-12: all items processed (marks above at each item).
The environment note was acknowledged by the user 2026-08-12 — no action;
the fix on the day an import is first needed here is one git clone. This
closed the whole git-gatekeeper review walk (26 items across dispositions.md
and this file, 2026-08-10 through 2026-08-12).

1. WALK-1 through WALK-5, one ruling each — done
2. FIX-1 through FIX-23 as one batch — done, applied with the ruled
   program changes (suite 150 green)
3. The environment note — acknowledged
