<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=defect-hunt tier=floor target=/home/nedlern/agents/choirmaster/docs/cross-project/git-gatekeeper-design.md -->

I read the full file, including the YAML frontmatter, plus the two checkout instruction files already in context. Findings below are numbered in document order; each states the defect and why it matters, without proposing a fix.

**1. L8 vs L16 — contradiction over whether the gate currently holds a credential**
Quote A (L8): *"The gate is **dormant**: no host yet holds a main-capable credential for it (§ The credential and enforcement)."*
Quote B (L16): *"It holds the project's one push-capable credential."*
L16 states as a present-tense guarantee that the program holds the push credential; L8 states no host holds a main-capable credential yet. A reader following only L16 (in "The job and the guarantee," which is presented as the durable contract) would believe the credential is live now. Sure this is at minimum a supports-incompatible-readings problem; unsure whether the intended resolution is "L16 describes the eventual/designed state" since nothing marks L16 as aspirational.

**2. L8 vs L123–130 — `unbuilt-option` refusal is never listed in the error catalog**
Quote A (L8): *"reaching an unbuilt part is the named refusal `unbuilt-option`, never a crash."*
Quote B (L123): *"**The error catalog** — every ending named, three-part teaching form:"* followed by the Form/Integration/Infrastructure/Answers lists (L125–128), none of which contain `unbuilt-option`.
The catalog claims completeness ("every ending named") but omits a refusal the document itself names and relies on. Sure.

**3. L10 — the B-code decisions (B1, B3c, B4a, B4c, B4d, B6) have no path to their source**
Quote: *"the two pending amendments from the 2026-07-30 bindings walk ... the `Gatekeeper-agent` trailer (B6, boss-ruled 2026-07-31)"*
Unlike the C1–C8 credential rulings, which are pinned to `docs/issues/queue/3-gatekeeper-credential-and-hook-bindings.md`, no file path is ever given anywhere in the document for "the 2026-07-30 bindings walk" that the B-codes (B1 at L59, B3c at L144, B4a/B4c/B4d at L117, B6 at L10/L103) trace back to. A future agent cannot verify or look up what a "B4c" ruling actually says beyond the paraphrase given inline. Sure.

**4. L10 — "the promotion-relay design" is never explained and no path is given**
Quote: *"Supersedes remain as before: the promotion-relay design, the entry-manifest append-a-row rule, the retired \"land\"/\"landing\" vocabulary."*
The entry-manifest rule and the retired vocabulary are both explained elsewhere in the file (L66, L152); "the promotion-relay design" is not explained anywhere in this file, nor is a path given to a document that defines it. Sure this term is unresolvable from this file alone.

**5. "boss" is used pervasively but never defined, and is inconsistent with "the user"**
Quotes: *"Scope ends at main (boss-ruled 2026-07-24)"* (L12); *"the dedicated-identity rung was **admitted early** (user-ruled 2026-08-09..."* (L134); *"credential expiry and protection misconfiguration are org-owner territory, the user's alone"* (L141); *"CLAUDE.md is documentation, never enforcement (boss ruling; his rationale verbatim..."* (L144).
"Boss" recurs as the authority behind nearly every design ruling, but this file never states who or what the boss is, nor does the checkout's CLAUDE.md/CLAUDE.local.md define the term. Compounding this, one ruling on the same subject matter and same date is attributed to "user-ruled" (L134) rather than "boss-ruled," while every other authority-bearing ruling in the file says "boss." A future agent cannot tell whether "boss" and "user" name the same person/role, and if they differ, what each is authorized to decide. Sure the term is undefined in the available context; unsure whether "boss" and "user" are meant to be identical.

**6. L12 — "the PR pipeline for ordinary work" implies an undefined non-ordinary-work category**
Quote: *"Ordinary changes use no branches and no pull requests."* (L12) vs. *"Never imported: ... the PR pipeline for ordinary work"* (L165).
The qualifier "for ordinary work" implies some work is *not* ordinary and might use a different pipeline, but the file never defines what counts as non-ordinary work or what process (if any) governs it, and never states that all work in this project is ordinary. Unsure whether this is a real gap or just loose wording carried over from paraphrasing the legacy design — flagging because the phrase, read literally, opens a case this file doesn't close.

**7. L17 — "exactly one of two things" is contradicted by the reply/exit-code taxonomy**
Quote: *"For each request the program does exactly one of two things: **checks the work in**, or **refuses and teaches the fix**."*
Later the file establishes a third category: *"Exit codes: **0** success and informational answers; ..."* (L59), and subcommands like `status`, `cancel`, and `imports` return outcomes (`in-progress`, `abandoned`, the import table, `cancelled`, `unknown-request`) that are neither "checks the work in" nor "refuses." Read literally and generally ("each request"), the claim is false; it only holds if silently narrowed to check-in requests specifically, which the sentence doesn't say. Sure this is literally false as stated; unsure whether narrowing to "check-in requests only" was the intended scope.

**8. L25 — guarantee 4 is not immediately true for non-waiting callers**
Quote: *"4. The requester has the answer: success plus the commit id."*
For a `--no-wait` caller, the immediate reply is `accepted <digest>` (L62), not "success plus the commit id" — that requires a separate `status <digest>` call later. As stated among "four things guaranteed true" on success, this reads as unconditional. Unsure — the surrounding text elsewhere makes the two-mode behavior clear, so this may just be an imprecise summary rather than a genuine contradiction.

**9. L27 — "a refusal has no side effects at all" is contradicted by the B4d exception**
Quote: *"The repository is untouched — a refusal has no side effects at all."*
Later: *"a refused `--no-wait` request keeps its workspace holding just the JSON refusal record; `status` returns it once, then sweeps"* (L117; also L10). That retained workspace and JSON record is a disk-level side effect of a refusal. The first clause ("the repository is untouched") is true; the second, broader clause ("no side effects at all") is directly falsified by the documented B4d behavior. Sure.

**10. L29 — "the *only* records" is contradicted by the workspace mechanism**
Quote: *"**Records:** git history and the invoking session's ordinary transcript are the *only* records. No side files, no separate logs..."*
But: *"`status <digest>` answers from what already exists (history **plus the program's workspace**)"* (L64), and the WORKING state description (L117) explicitly stores `worker.pid` and "the resolved request record" on disk, used to distinguish `in-progress` from `abandoned` and to serve the retained refusal record. These are side files functioning as logs/records that neither git history nor a transcript contains. Sure.

**11. L53 / L103 — "the fix ladder" is referenced twice but never defined**
Quotes: *"the model is the half the fix ladder needs"* (L53); *"the fix ladder's escalation needs to know what tier produced an artifact to know whether stronger models remain"* (L103).
No definition of "the fix ladder" appears in this file, and no path is given to where it might be defined. A future agent cannot determine what this mechanism is, how it "escalates," or what "tier" means in this context. Sure.

**12. L59 vs L61/L110 — the reply schema omits a field the text says the reply carries**
Quote A (L59): *"Every invocation prints exactly one JSON object on stdout: `{outcome, error?, facts?, next_action?, commit?, digest?, summary}`"*
Quote B (L61): *"...the reply also carries `integrated_over: <n>`."*
Quote C (L110): *"the reply notes \"integrated over N newer commits.\""*
The schema at L59 is presented as the complete field set ("exactly one JSON object... {...}"), but `integrated_over` is not among the listed fields, despite two other places in the document stating the reply carries this information. Sure this is inconsistent as written.

**13. L64 — the `status` outcome list omits the refusal-record case**
Quote: *"`status <digest>` answers from what already exists (history plus the program's workspace): `checked-in <commit>`, `in-progress`, `abandoned` (workspace present, worker dead — resubmit safely), or `unknown` (\"no trace; submit it\" — always safe)."*
This is presented as the enumerated set of things `status` can answer, but B4d (L10, L117) establishes that `status` can also return a retained JSON refusal record for a refused `--no-wait` request — a fifth case not in this list. Sure.

**14. L134 — "the trigger named below" only tautologically names itself**
Quote: *"The dedicated-identity rung was **admitted early** (user-ruled 2026-08-09, exercising the trigger named below)..."*
The only place this trigger is actually named is L157: *"**Admitted 2026-08-09** (the boss-admits-it-early trigger)"* — which labels the trigger as "the boss admits it early," i.e., restates that a ruling happened rather than stating what condition causes early admission in general. A future agent looking for the actual rule governing when a "Deliberately not in version 1" item can be pulled forward finds only a name, not a criterion. Unsure whether this is intentional shorthand for "any standing override by boss/user ruling" (which would make it not need further definition) or a genuine missing rule.

**15. L136–137 — tension between the live pusher account being an org owner and "no agent ever holds" owner power**
Quote A (L136): *"pushes to `main` restricted to the machine credential (`NedLern`) alone ... The org has two owners (`NedLern`; `NedLerner`, settings and emergency power, no push)"* — i.e., `NedLern`, the account used as the push credential, is currently one of the two org owners.
Quote B (L137): *"Owner power stays with the user; no agent ever holds it."*
Under the still-live layout (L136), the account that agents/hosts will eventually be given as the push credential is itself an org owner, which is a stronger grant than "push access" and appears to conflict with "no agent ever holds [owner power]" once that credential is actually deployed to a host. Unsure whether L137's sentence is meant to describe only the post-amendment target state (in which case it's not yet a live contradiction) or a standing invariant — the text doesn't mark it as forward-looking.

**16. L139 — "capability-by-landing class" is unexplained**
Quote: *"never a classic all-repository token, and never the `workflow` scope (capability-by-landing class, nedschorus#31)"*
This coins a classification term ("capability-by-landing class") with no definition in the file, only an issue-number tag. Unsure — the tag `nedschorus#31` gives a locatable pointer (and is elaborated with a full URL at L175), so this is milder than the "fix ladder" or "subsystem token set" cases, but the term itself remains opaque without leaving this file's stated context.

**17. L140/L144 — "Nothing in this design depends on either" is contradicted by C6 and the Build slice**
Quote: *"The same is true of harness hooks: they configure a harness, and only cooperating harnesses read them — which is why C6 is a convenience tier and C2 is the boundary. Nothing in this design depends on either."* (L144)
But C6 itself (L140) is defined as *"a PreToolUse hook rewrites `gh` calls seamlessly into their disciplined form; a `git push` toward this repository's remote gets deny-with-exact-invocation instead"* — i.e., a harness hook is a load-bearing part of the cooperative tier this design describes. And the Build slice (L169) lists *"the CLAUDE.md workflow lines"* as required deliverable content. Taken literally, "nothing in this design depends on either" is false, since the design explicitly specifies and builds a hook-based tier and CLAUDE.md content. Sure the literal sentence is false; the likely intended narrower meaning ("the *enforcement guarantee* doesn't depend on them") is plausible but isn't what's written.

**18. L142 — `--repo` and `--remote` flags are undocumented in the CLI usage block**
Quote: *"**Privileged invocations refuse the test seams (C7):** `--repo` and `--remote` exist so tests can hand the program throwaway repositories."*
The canonical request-format synopsis (L36–44) lists only `--files`, `--message`, `--base`, `--import`/`--import-commit`/`--import-source`/`--import-dest`, `--issue`, `--agent`, and `--wait`/`--no-wait`. `--repo` and `--remote` are never mentioned there, so a reader relying on that synopsis as the interface spec would not know these flags exist. Sure this is a gap between the stated interface and flags referenced elsewhere in the same document.

**19. L151 — "the subsystem token set" is undefined**
Quote: *"Naming-hygiene check | The subsystem token set starts empty — pure noise at founding | A real subsystem set exists"*
No definition of "subsystem token set" appears anywhere else in the file, and no path is given. A future agent cannot determine what this check would validate or what a "subsystem token" is. Sure.

**20. L150 vs L175 — the review-evidence table row's justification is stale**
Quote A (L150): *"Review-evidence field + check | No artifact class is gated | The boss gates a class"*
Quote B (L175): *"the first class is now designated (boss-ruled 2026-08-04): instruction-bearing text ... whose check-ins require walked-approval evidence"*
The table's "why" column asserts "No artifact class is gated" as the reason this feature is cut, and names "The boss gates a class" as the trigger for it to grow back. The Open section states that trigger has already fired (a class was designated on 2026-08-04, before this revision's 2026-08-09 date) — so the row's stated justification is no longer true, yet the row is not struck through or annotated the way the "Dedicated gatekeeper identity" row (L157) was when its own trigger fired. Sure the "why" text is stale relative to L175; unsure whether the row should have been struck or is deliberately left as-is because the field/check itself isn't built yet.

**21. L150/L175 — three different names for the same evidence mechanism**
Quotes: *"Review-evidence field + check"* (L150); *"whose check-ins require walked-approval evidence"* (L175); *"unscheduled until the approval-evidence format exists"* (L175, same paragraph as the previous quote).
Within one document (and even within the same sentence-pair at L175), the mechanism is called "review-evidence field," "walked-approval evidence," and "approval-evidence format." A future agent grepping for one term would miss the others. Sure these are three distinct strings referring to what appears to be one concept, with no note that they're synonyms.

**22. L175 vs L8 — "slice 6" contradicts the stated total of five slices**
Quote A (L8): *"`scripts/git-gatekeeper.py` is BUILT through slice 3 of five ... Slices 4 ... and 5 ... remain contract-only"*
Quote B (L175): *"The check itself is built with the gatekeeper (slice 6 of the build order, unscheduled until the approval-evidence format exists)."*
L8 states the build order has five total slices; L175 references a sixth slice of the same build order. These directly contradict each other on how many slices exist. Sure.

**23. L167–171 — "Build slice (choirmaster task 1)" conflicts with the five-slice implementation-status framing**
Quote: *"## Build slice (choirmaster task 1) — The git config above + `git-gatekeeper.py` with `check-in`, `status`, `cancel`, `imports` + the CLAUDE.md workflow lines + tests: T1 ... T12 ..."*
This section bundles check-in, status, cancel, imports, the repo git config, and the CLAUDE.md workflow lines — plus a trailer-absence-audit test (T12) — into one task. But the Implementation status paragraph (L8) frames the same functionality as spread across five distinct slices, with worker lifecycle (slice 4) and audits/git config/CLAUDE.md lines (slice 5) explicitly "not yet applied"/"contract-only." Nothing in the document states whether this "Build slice (choirmaster task 1)" section is superseded by the later five-slice plan (`docs/issues/3-git-gatekeeper-build-slice-plan.md`) or is a separate, still-active unit of work that duplicates or conflicts with it. Sure there is an unreconciled conflict between the two framings; unsure which one governs.

**24. L159 — section header "awaiting the boss" contradicts its own resolved/superseded body**
Quote: *"## Cross-spec consequence, awaiting the boss" ... "RESOLVED 2026-07-24, then SUPERSEDED 2026-08-02 by the session-recycling revision..."*
The header states something is still awaiting a decision; the body states the matter was resolved and then superseded — i.e., fully closed, not pending. Sure.

**25. L173/177 — an item marked "(resolved)" is listed under the "Open" heading**
Quote: *"## Open" ... "(resolved) The fast-handoff S2 interaction — see § Cross-spec consequence."*
An entry explicitly labeled resolved appears under a section whose heading means unresolved/pending items. This is either miscategorized or the heading's scope is broader than "open" suggests, but neither reading is stated. Sure this is inconsistent as written.

**26. "Cooperative class" is used for two different things without a unifying definition**
Quote A (L53): *"Cooperative class: the gatekeeper records what it is told and never guesses."* — describing a trust property of the `--agent` field.
Quote B (L144): *"an agent-held owner credential could deliberately edit protection — same cooperative class, same catch"* — describing a category of un-enforced residual risk.
Both uses invoke "cooperative class" as if it's a defined recurring category, but the file never states it as a general term with a single definition — the two uses describe different things (an honesty property of one CLI field, versus a class of audit-only residual risks). Unsure whether this is a deliberate recurring motif the author expects readers to recognize, or an accidental reuse of similar phrasing for unrelated ideas.

---

clean sections: The procedure; Constructive guarantees, the advisory, and the growth point; Relationship to the legacy design.

