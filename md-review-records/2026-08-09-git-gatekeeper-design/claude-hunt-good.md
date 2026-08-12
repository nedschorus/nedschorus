<!-- provenance: runtime=claude model=claude-opus-5 effort=high cell=defect-hunt tier=good target=/home/nedlern/agents/choirmaster/docs/cross-project/git-gatekeeper-design.md -->

I read the design file in full and the checkout's `CLAUDE.md`, and confirmed that every path it cites by name exists (`docs/issues/3-git-gatekeeper-build-slice-plan.md`, `docs/issues/queue/3-gatekeeper-credential-and-hook-bindings.md`, `fast-handoff-design.md`, `entry-manifest.md`, `scripts/git-gatekeeper.py`). Findings below are in document order; line numbers are from the file as read.

---

**1. Frontmatter `status: specification` (line 2), with title "# git-gatekeeper (specification)" (line 6)**
> `status: specification`

The body immediately says branch protection and the account layout "are LIVE" and that the program "is BUILT through slice 3 of five" with a running 146-case suite. A machine-readable `status` field is the thing a future agent or a doc-index script filters on; reading `specification` it will treat live, load-bearing infrastructure as an unimplemented proposal — for instance skipping it when asking "what is currently enforcing pushes to main?". The file never says whether `status` describes the document's genre or the system's implementation state, so both readings are available and they disagree. Confidence: sure the two disagree; unsure which reading was intended.

**2. Line 8 — `unbuilt-option` is not in the catalog that claims to be complete**
> "reaching an unbuilt part is the named refusal `unbuilt-option`, never a crash"

The error catalog at line 123 is introduced as "**The error catalog** — every ending named", and line 130 asserts "no unnamed endings", but `unbuilt-option` appears nowhere in the four catalog groups (Form / Integration / Infrastructure / Answers). Its exit code is therefore also undetermined: line 59 assigns 1 to "catalog refusal" and 2 to "program defect", and `unbuilt-option` is by construction not in the catalog. Harm: an agent scripting against exit codes, or the audit that must "never read a gatekeeper bug as a correct refusal", cannot classify the single most likely outcome of calling `--no-wait`, `status`, or `cancel` today, since slices 4 and 5 are unbuilt. Confidence: sure.

**3. Line 8 vs line 175 — "five" slices vs a slice 6**
> "is BUILT through slice 3 of five" … "Slices 4 … and 5 … remain contract-only"

against

> "The check itself is built with the gatekeeper (slice 6 of the build order, unscheduled until the approval-evidence format exists)"

The build order cannot have exactly five slices and also a slice 6. A reader planning remaining work gets a different answer depending on which sentence they read, and "of five" makes slice 6 look like a typo when it may be a real, deliberately unscheduled slice. Confidence: sure it is a contradiction; unsure which number is stale.

**4. Line 8 vs lines 136 and 143 — is a main-capable credential held anywhere or not?**
> "The gate is **dormant**: no host yet holds a main-capable credential for it"

against

> "pushes to `main` restricted to the machine credential (`NedLern`) alone" (136) and "anything running as that account, on any machine, can push. … What remains procedural before C2 is only that agents *use the program* rather than raw `git push`." (143)

Line 143's whole point — the raw-push residual that C2 and the standing audit exist to close — presupposes that some host does hold a credential able to push main. If genuinely no host holds one, there is no residual to be procedural about, the audit at line 144 has nothing to catch, and the currently-live commits on main were produced by something the design does not account for. Harm: an agent deciding whether it may attempt a check-in today, or whether the audit is meaningful today, gets opposite answers from the header and the credential section. Confidence: sure the two statements cannot both be true as written.

**5. Line 10 — the "B" ruling codes and the walk they come from are unresolvable from this file**
> "the two pending amendments from the 2026-07-30 bindings walk" … and, downstream, "(B1)", "(B4a)", "(B4c)", "(B4d)", "(B3c)", "(B6)"

The parallel "C" codes are given a home in the same sentence (`docs/issues/queue/3-gatekeeper-credential-and-hook-bindings.md`, C1–C8); the B codes are given none, here or anywhere in the file. Six later design decisions are annotated only by these codes, so a future agent that wants to know what B4d actually ruled — or whether a proposed change would violate it — has no way to look it up from this document, and no way to know a lookup is even possible. (A sibling file `docs/issues/queue/3-gatekeeper-build-bindings.md` exists in the checkout, which makes the omission a missing pointer rather than a dead one, but this file never names it.) Same defect for "Supersedes remain as before: the promotion-relay design" — "as before" refers to a prior revision the reader does not have, and "the promotion-relay design" is named with no path and no description. Confidence: sure.

**6. Line 16 — "the only way any change reaches main" is contradicted by the file's own credential section**
> "One program, `scripts/git-gatekeeper.py`, is the only way any change reaches main."

Line 141 provides break-glass: "a landing the gate wrongly refuses uses a sudoers entry requiring the user's password, approved in the moment" — a second way. Line 136 notes an org owner can change protection, and line 144 says the raw-push residual is "*detected*, not prevented", i.e. raw pushes are possible and expected to occur. An absolute stated in the guarantee section and then repeatedly qualified 120 lines later will be relied on where it is stated: an agent reasoning "every commit on main has trailers, because the program is the only way in" will write tooling that breaks on the first break-glass or pre-gate commit. Confidence: sure.

**7. Line 16 — "one push-capable credential" and agents that "never push themselves" vs C4**
> "It holds the project's one push-capable credential. Agents — all of them, equally — invoke the program directly and never push themselves."

Line 139 says "each agent host holds a fine-grained token for this repository only — contents read/write (branch pushes are open; the push-less ruling covers main alone)". Contents write *is* push capability, and branch pushes are explicitly open, so there are many push-capable credentials and agents do push. The qualifier that makes line 16 true — *main*-capable — is missing exactly where the guarantee is stated. Harm: the sentence is the one a reader quotes when deciding whether some new agent may be given a token at all, and it forbids something the design elsewhere permits. Confidence: sure.

**8. Line 27 — "no side effects at all" vs the retained refusal workspace**
> "The repository is untouched — a refusal has no side effects at all."

Line 117 (B4d) states the opposite for one refusal class: "a refused `--no-wait` request keeps its workspace holding just the JSON refusal record; `status` returns it once, then sweeps." That is a durable on-disk side effect of a refusal. It also matters operationally: a caller that reads line 27 will not know it must call `status` to release state, and will not expect a directory to exist under the state root after a refusal. Confidence: sure.

**9. Line 29 — "the *only* records … No side files, no separate logs"**
> "**Records:** git history and the invoking session's ordinary transcript are the *only* records. No side files, no separate logs"

Three things in this file are records that are neither: the "resolved request record" written into the workspace at screening (line 117, B4c), the JSON refusal record retained after a refused `--no-wait` (line 117, B4d), and the `draft` issue the standing audit files naming trailer-less commits (line 144). Harm: this sentence is the rule a future agent will cite to reject any proposal that writes state, and to conclude that nothing needs sweeping, backup, or privacy consideration outside git. Confidence: sure. (The workspace files are transient by design, but the sentence as written admits no transient category.)

**10. Line 31 — "Resubmitting is always safe. Same request, same answer"**
> "**Resubmitting is always safe.** Same request, same answer; … work that already went through answers `already-checked-in <commit>`."

Ordinary counterexample the file itself creates: line 121 names revert as "the remedy for a bad landed change" — an ordinary check-in that undoes a previous one. After a revert, the original work's digest is still in main's history, so resubmitting that work answers `already-checked-in <commit>` with exit 0 while the change is *not* on main. The caller is told, in the success vocabulary, that a guarantee ("1. The change is on main") holds when it does not. This is reachable by design, not by misuse: revert-then-redo-properly is a normal loop. Confidence: sure the case is reachable; unsure whether the author considers `already-checked-in` acceptable there, but the file does not say.

**11. Line 31 — the self-healing retry loop has no termination condition**
> "Refusals teach, retries are free: the loop self-heals, which is what near-perfect autonomous operation requires."

Combined with line 127 ("`push-auth-failed`, `network-down`, `workspace-io-error` — all safely resubmittable"), an autonomous agent is instructed to resubmit on these outcomes and is given no attempt bound, no backoff, and no escalation point — while line 130 forecloses the obvious escape by asserting "nothing routes to the boss mechanically". The internal retry loop is bounded (line 112, five rounds), which makes the absence of a bound on the *caller's* loop look deliberate when it is probably just unstated. Harm: an expired token or a down network turns an agent into an unbounded resubmit loop against a gate that keeps answering "safely resubmittable". Confidence: sure the stopping point is absent.

**12. Line 40 / item 4 (line 51) — `--import none` and the three-part form can both be supplied**
> `--import none | --import-commit <id> --import-source <path> --import-dest <path>`

`none` is a value of a flag (`--import`) while the positive case uses three *different* flags. The validation rule given covers only "One or two parts of three: `import-incomplete`". Nothing states what happens when a caller passes `--import none` *and* `--import-commit …` (contradictory), or when it passes none of the four (is absent import equivalent to `--import none`, or is it `malformed-field`?). Both are reachable from ordinary argument-templating mistakes, and both currently fall outside every named error, against line 123's "every ending named". Confidence: sure the cases are unaddressed.

**13. Line 46 / step 2 (line 71) — "instant and synchronous" validation that requires repository and probably network access**
> "all form validation is instant and synchronous in both modes"

Four of the eleven Form errors are not form checks: `unknown-base` and `base-not-on-main` require main's history; `import-source-missing` and `legacy-unreadable` require reading the legacy repository at a specific commit; and step 2 adds "The digest is computed and looked up in history right here". The file never says where "history" comes from at screening time — a local clone, a fetch from GitHub, or the workspace clone that does not exist yet — nor what the answer is when that access fails during screening. `network-down` is catalogued as Infrastructure, which line 91 implies happens after screening. Harm: an implementer must invent the fetch policy, and a stale local view would let `base-not-on-main` or a missed `already-checked-in` fire wrongly. Confidence: sure the mechanism is unstated; unsure whether "instant" was meant as "no worker involved" rather than "no I/O".

**14. Item 1 (line 48) vs the advisory (line 89) — "the program's *only* read of that worktree"**
> "The new content of each path is read from the invoking agent's working copy — the program's *only* read of that worktree."

The advisory requires exactly the read this sentence forbids: "if the agent's worktree contains modified files *beyond* the declared ones" can only be determined by scanning the whole worktree and diffing it against base. Harm: an implementer obeying line 48 literally cannot build the advisory, and a reader auditing privacy/blast-radius ("the gate reads only what I declare") is misinformed — undeclared files in the caller's worktree are read, or at least stat'd and hashed. Confidence: sure.

**15. Item 1 (line 48) — change inference is content-only, and several stated validation rules have no named error**
> "no absolute paths, no `..`, nothing under `.git/`, no duplicates, list non-empty" and "**modified** (differs)"

Two gaps. (i) Five prohibitions are stated with no error names attached; only `unknown-path`, `unchanged-path`, and `empty-change` are given, so a duplicate path or a `..` segment has no named ending, against line 123. (ii) Change is inferred purely from presence and byte difference, so a mode-only change (making a script executable) is "identical to base" and is refused as `unchanged-path` — meaning the executable bit can never be changed through the gate that is "the only way any change reaches main", and the file has a `scripts/` directory. Symlinks and paths that escape the repo via a symlinked parent are likewise not addressed by a rule that only textually forbids `..` and absolute paths. Confidence: sure on (i); sure the mode case is unaddressed, unsure whether it is considered out of scope.

**16. Item 8 (line 55) — the digest definition is not reproducible**
> "SHA-256 over: base id + sorted path list + each path's new bytes (deletions as a marker) + the import triple"

No field separators or length framing are specified, so the concatenation is ambiguous (two different path lists can serialize identically); "sorted" does not say by what ordering (bytewise vs locale); and "deletions as a marker" does not say what the marker is. This value is not internal: it is the duplicate-detection key, it is published in the `Gatekeeper-digest` trailer, it names the workspace directory, and it is the argument to `status` and `cancel`. Harm: any reimplementation, or any tool that wants to verify a trailer, computes a different digest, and `already-checked-in` silently stops working. Confidence: sure.

**17. Item 8 (line 55) — the digest binds the base, which defeats dedup on exactly the path the file recommends**
> "the digest identifies **the work**, so identical work resubmitted under different metadata still deduplicates"

The base id is an input to the digest and is not classified as metadata. So the recommended recovery action in the conflict refusal — "update from main, adjust, resubmit" (line 110) — necessarily changes `--base` and therefore the digest, and so does any resubmit by an agent that refreshed from main after a crash (line 31's scenario). In those cases the `already-checked-in` screen cannot fire, and the caller falls through to whatever the rebuilt candidate produces (probably `unchanged-path`, an error that reads as a caller mistake rather than "your earlier submission actually succeeded"). Harm: the safety property "resubmit and the program sorts it out" is weakest precisely in the crash-and-refresh case it was written for. Confidence: sure the digest changes; unsure whether the resulting refusal was thought through and considered acceptable.

**18. Line 59 — "exactly one JSON object" whose key set cannot carry three documented outputs**
> "Every invocation prints exactly one JSON object on stdout: `{outcome, error?, facts?, next_action?, commit?, digest?, summary}`"

Three later outputs have nowhere to go in that object: `integrated_over: <n>` (line 61) is an extra key; the advisory note "worktree also differs at `x`, `y`; confirm intentional" (line 89) is a distinct channel from `error`/`next_action` and has no key; and `imports` (line 66) "prints the import table" — a table of many rows, not one `{outcome, …, summary}` object. Additionally, exit code 2 is defined as "program defect", and the file does not say whether a defect severe enough to abort still emits the one JSON object, so a caller cannot rely on parsing stdout before checking the exit code. Harm: a caller written to the stated schema breaks on the first integrated check-in, the first advisory, and every `imports` call. Confidence: sure.

**19. Line 64 — the `status` outcome list is closed but omits a documented fifth answer, and one listed answer overlaps it**
> "`status <digest>` answers from what already exists (history plus the program's workspace): `checked-in <commit>`, `in-progress`, `abandoned` (workspace present, worker dead — resubmit safely), or `unknown`"

Line 117 adds a fifth: for a refused `--no-wait` request, "`status` returns it once, then sweeps" — the retained JSON refusal record. Worse, that workspace matches the stated definition of `abandoned` exactly (workspace present, worker dead), so an implementation reading only line 64 will report `abandoned — resubmit safely` for work that was in fact refused with a teachable reason, sending the agent into a resubmit that will be refused identically. Harm: the one case where retrying is guaranteed useless is the case the list mislabels as "resubmit safely". Confidence: sure.

**20. Line 66 and the subcommand set — single-word command names against the checkout's naming rule**
> "`imports` — prints the import table derived from history"

`CLAUDE.md` line 7 requires that invented names "likely to be grepped" be "explicit, clear and precise multi-part names … 3 or 4 parts, not 1 or 2". `imports`, `status`, and `cancel` are one part each. `imports` in particular is unsearchable in a Python codebase — the token appears in every discussion of import statements, and this project's gate already has an unrelated `--import`/`--import-commit`/`--import-source`/`--import-dest` family plus a `Gatekeeper-import` trailer, so a grep for the query, the flag, and the trailer cannot be separated. `--import` is also a strict prefix of the other three flags, which makes flag-level searching and argument-parser prefix matching ambiguous. Harm falls on the future agent trying to find every site that implements or calls the query. Confidence: sure about the searchability property; unsure whether the author considers subcommand names exempt from the rule.

**21. Step 7 (line 76) — "The workspace is deleted", stated without the exception**
> "The workspace is deleted."

Line 117 carves out B4d: a refused `--no-wait` workspace survives until `status` reads it. The procedure is the section a reader consults for "what is on disk after my call", and it states an unconditional deletion. Confidence: sure it is inconsistent; the exception exists elsewhere, so this is a stale absolute rather than a missing mechanism.

**22. Line 84 — "Stray changes cannot enter" holds only at file granularity**
> "**Stray changes cannot enter** — the candidate is built *from* the declaration; an undeclared edit never reaches it."

The declaration is a list of paths, and the whole current bytes of each declared path are taken from the worktree. So any unintended edit *inside* a declared file — a debug print, a half-finished neighbouring function, an editor artifact — enters the candidate and reaches main with no signal at all; the advisory at line 89 only notices undeclared *files*. The claim is made in a section titled "made impossible by construction", which invites a reader to stop checking. Confidence: sure the claim is broader than the mechanism.

**23. Line 87 — "Duplicates cannot apply — the digest screen runs at submit"**
> "**Duplicates cannot apply** — the digest screen runs at submit."

"At submit" is the whole defence, and the loser path (line 110) never re-runs it: on losing the race the program fetches, rebuilds, re-checks, and pushes again, without re-asking whether the digest is now in history. Two reachable consequences. (i) Two agents submit identical work concurrently — both pass the submit screen, one wins, the loser rebuilds, finds the new main already contains its content, and by line 110's own definition ("the new main touched the same content this request changes") is refused with `conflict` rather than answered `already-checked-in`. (ii) A push that actually succeeded but whose acknowledgement was lost (the file's own crash scenario) drives the same path to the same wrong answer. Harm: a `conflict` refusal tells the agent to "update from main, adjust, resubmit" for work that is already checked in. Confidence: sure the loser path omits the re-screen as written; unsure whether the built slice 3 does the same.

**24. Line 91 — "between screening and push, no refusal remains"**
> "In version 1, between screening and push, **no refusal remains** — this stage is deterministic construction and recording."

`workspace-io-error` (line 127) arises precisely there: candidate clone, file writes, commit. So does `legacy-unreadable` if the legacy copy happens during candidate construction, which step 3 says it does ("A declared import happens here"), even though the catalog files it under Form/instant. Harm: the sentence is used to justify the claim that the stage needs no teaching-form outcomes, and an implementer may leave those failures as unhandled exceptions (exit 2, "program defect") when they are ordinary, resubmittable infrastructure failures. Confidence: sure.

**25. Step 4 (line 74/91) — "the checks" are never defined, and the pointer goes to a section that defines none**
> "4. **Run the checks** (§ Constructive guarantees) against the candidate"

§ Constructive guarantees lists four things made impossible plus one advisory; it contains no check. Line 91 says the check stage is "the growth point" and that tests run there "when a test suite exists". So in version 1 the set of checks is empty and step 4 is a no-op — which the file never states — and success guarantee 2, "The checks ran against exactly the content that was pushed" (line 21), is vacuously true today while reading as a substantive assurance. Harm: an agent or reviewer relying on guarantee 2 believes content reaching main was validated by something. Confidence: sure the referenced section defines no checks; sure the v1 set is empty by implication, though the file never says it outright.

**26. Line 103 — the offline collection command matches the wrong issues**
> "`git log --grep \"Gatekeeper-issue: #<n>\"`"

`--grep` takes a regular expression and is unanchored, so the command for issue #1 also matches `Gatekeeper-issue: #10`, `#11`, `#12`, and every other issue whose number starts with 1. Taken literally, the stated derivation is wrong for any issue number that is a prefix of another in use, which in a repository already numbering past #45 is the common case, not the corner case. Harm: an agent auditing "all check-ins for issue #3" gets #30, #32, #35 mixed in and may act on them. Confidence: sure.

**27. Line 103 and line 130 — "never auto-posted to issues" / "nothing routes to the boss mechanically"**
> "Refusals and other responses are **never** auto-posted to issues — mechanical chatter stays in transcripts" … "nothing routes to the boss mechanically — he is consulted by agents' judgment, never by the machinery."

Line 144 has a standing audit that mechanically "files a `draft` issue naming them" — an automated program outcome posted to issues without any agent's judgment, which is exactly the class both absolutes exclude. Whether "responses" was meant narrowly (replies to a check-in request) is not stated, so both readings stand. The second absolute is also in tension with line 175's designated gated class, whose check-ins "require walked-approval evidence" — a machinery-level requirement that cannot be satisfied without the boss. Harm: the rules read as bright lines and will be cited to reject a future automated-notification proposal that is no different from the audit already specified. Confidence: sure about the audit contradicting the second absolute; unsure whether the author reads the audit's issue as a "response".

**28. Line 110 — "the same content" vs "different files": the conflict test is defined two ways**
> "**Clean re-application** (the usual case — different files) … **Real conflict** (the new main touched the same content this request changes)"

The parenthetical implies file granularity; "the same content" implies something finer (same lines/hunks). The distinction is not cosmetic: the candidate is built by writing the declared file's *whole new bytes*, not by applying a diff. So if a request declares `foo.md` and the new main also changed `foo.md` elsewhere in the file, a fine-grained reading says "no overlap, re-apply cleanly" — and re-applying silently discards the other agent's change, a lost update that both the checks and the digest would consider fine. A file-granularity reading is the only one the construction method supports, but the text permits the other. Harm: silent data loss on main under exactly the concurrency the design encourages ("check-ins run in parallel by default"). Confidence: sure the wording supports both readings.

**29. Line 117 — the retained refusal workspace has no expiry**
> "a refused `--no-wait` request keeps its workspace holding just the JSON refusal record; `status` returns it once, then sweeps"

The only sweep triggers named anywhere are a `status` read (here), a resubmit of the same digest (line 119), and a `cancel` on a live worker (line 121). If the `--no-wait` caller dies, is recycled, or simply never calls `status` — all ordinary for the long-lived agents this design is built around — that workspace persists indefinitely, and nothing else will ever name that digest. No TTL, no startup sweep, no size bound is stated or discarded. Harm: unbounded growth under `$XDG_STATE_HOME` from the failure mode the design explicitly expects (agents that crash and never reconstruct what happened). Confidence: sure it is unaddressed.

**30. Line 117 vs line 138 — whose `$XDG_STATE_HOME`?**
> "`$XDG_STATE_HOME/nedschorus-gatekeeper/<digest>/`, default `~/.local/state/...` (B4a): outside every repository, discoverable from the digest alone"

Under C2 the program runs as a dedicated Unix user via sudo, so `$XDG_STATE_HOME`/`~` resolve in that user's environment, not the caller's — and sudo's environment handling for `XDG_STATE_HOME` specifically (passed through, reset, or unset) determines the answer. "Discoverable from the digest alone" is then false for an agent trying to inspect state directly, since it also needs to know which user's home and whether the variable survived the sudo boundary. Separately, the default path is written with an ellipsis (`~/.local/state/...`) rather than the literal value, so the one concrete fallback the reader needs is elided. Harm: an agent debugging a stuck check-in looks in the wrong home directory and concludes no workspace exists. Confidence: sure the sudo interaction is unstated; unsure how much of it the author considers obvious.

**31. Line 119 — the resubmit rule sweeps workspaces without checking whether the worker is alive**
> "The program checks the digest against history — found means `already-checked-in <commit>`; absent means the leftover workspace is swept and the work runs fresh."

The condition given is only "absent from history"; liveness is not part of it. But an in-flight request is by definition absent from history and has a workspace with a live worker — so obeyed literally, any resubmit during WORKING deletes a running worker's candidate clone out from under it. The file has the discriminator (line 119's own next sentence: `status` "distinguishes WORKING from **abandoned** … via the recorded process id") but does not apply it in the recovery rule. This is not an exotic case: the design tells agents to resubmit whenever they are unsure, and `--no-wait` plus a nervous caller reaches it directly. It also contradicts "Resubmitting is always safe" (line 31). Confidence: sure the rule as stated omits the liveness check.

**32. Line 119 — "never a forever-'in-progress'" rests on a bare recorded pid**
> "so a died-silently worker is a named, resubmittable state — never a forever-\"in-progress\"."

A recorded pid alone cannot distinguish "worker still running" from "worker died and the OS reused its pid" — the second reports `in-progress` forever, which is precisely what the absolute denies. Nothing is stated about a start-time check, a held lock/flock, or any other liveness evidence, and nothing is stated about a worker on a different machine (line 143 explicitly contemplates the credential account being used "on any machine"), where a local pid means nothing at all. Harm: the one state the design promises cannot wedge is the one that wedges, and the remedy (`cancel`) is documented as not routine. Confidence: sure the pid mechanism admits the counterexample; unsure how likely reuse is in practice on this host.

**33. Line 121 — "Outcomes, exactly three" leaves two reachable cases uncovered**
> "Outcomes, exactly three: digest already in history → `too-late …`; live worker found → kill it, sweep the workspace, `cancelled`; nothing found → `unknown-request`."

Two states this file itself defines fit none of the three: (i) `abandoned` — workspace present, worker dead, digest not in history: not "in history", not a "live worker", and not "nothing found"; (ii) the B4d refused-`--no-wait` workspace holding a refusal record, which is the same shape. In both, the workspace is found, so `unknown-request` is a lie and no sweep is specified, leaving the directory behind after an explicit cancel. Harm: `cancel` — the intended cleanup path — is the one command that cannot clean up the states most likely to need cleaning. Confidence: sure.

**34. Line 121 (and 139, 141, 161) — vocabulary the file's own supersede note retires**
> "the remedy for a bad landed change is a **revert**"

Line 10 states: "Supersedes remain as before: … the retired \"land\"/\"landing\" vocabulary." The file then uses it four times: "a bad landed change" (121), "capability-by-landing class" (139), "a landing the gate wrongly refuses" (141), "lands as an ordinary file" (161). A reader cannot tell whether the retirement is still in force, whether these are grandfathered terms of art, or whether "landing" now means something distinct from "check-in". Harm: the next author reintroduces the vocabulary in good faith, and grep-based enforcement of the retirement flags the spec that declares it. Confidence: sure.

**35. Line 128 — the "Answers, not errors" list is incomplete against "every ending named"**
> "*Answers, not errors:* `already-checked-in <commit>`, `accepted <digest>`, `cancelled`, `too-late`, `unknown-request`."

Missing: `checked-in <commit-id>` — the success outcome, named at line 61 and nowhere in the catalog — and `in-progress`, `abandoned`, and `unknown`, all three named as `status` answers at line 64. Line 123 introduces the catalog as "every ending named" and line 130 asserts "no unnamed endings", so a reader building an exhaustive outcome handler from the catalog will omit the single most common outcome of a successful check-in. Confidence: sure.

**36. Throughout — "the boss" and "the user" are used as authorities without being defined or equated**
> "boss-ruled 2026-07-24" (12) … "user-ruled 2026-08-09" (134) … "Owner power stays with the user; no agent ever holds it" (137) … "requiring the user's password" (141) … "nothing routes to the boss mechanically — he is consulted by agents' judgment" (130)

Neither term is defined in this file or in `CLAUDE.md`, and the file uses both, sometimes in adjacent sentences (line 134's "user-ruled" for a decision the line-157 table attributes to "the boss-admits-it-early trigger"). A future agent cannot tell whether these are one person or two roles — which matters concretely at line 141, where break-glass requires "the user's password", and at line 136's "The boss never commits directly". If they are the same person, one of the two names should not exist; if they are different, the file assigns overlapping authority with no boundary. Confidence: sure they are never equated; unsure whether the distinction is intentional.

**37. Throughout — machinery referred to by name but never defined or located**
> "the **fix ladder**" (53, 103); "The **artifact-lifecycle rule** decides *upstream*" (52); "each **handoff scrub**" (144); "**walked-approval evidence**" (175); "capability-by-landing class" (139); "loop counters" (59); "the 2026-07-30 bindings walk" / "the 2026-07-24 boss-walked core" (10)

Each of these carries load: the fix ladder is the stated justification for the `Gatekeeper-agent` trailer; the artifact-lifecycle rule is what makes `--issue none` legitimate; the handoff scrub is the trigger that makes the standing audit "standing" — without it there is no stated schedule for the audit at all; walked-approval evidence is the gate condition for the first gated artifact class. None is defined here, none carries a pointer, and none is a standard SDLC term a reader could look up. Harm: an agent asked to implement slice 5 cannot determine when the audit runs; an agent asked to decide `--issue` cannot find the rule that decides it. Confidence: sure.

**38. Line 134 with line 157 — the "trigger" for admitting the dedicated identity is a circular reference**
> "the dedicated-identity rung was **admitted early** (user-ruled 2026-08-09, exercising the trigger named below)"

"Named below" points to § The credential and enforcement, which does not name a trigger; the only mention is in the table at line 157, "**Admitted 2026-08-09** (the boss-admits-it-early trigger) — § The credential and enforcement", which points back to the section. The two references cite each other and the trigger condition itself is stated nowhere — and the table row's original "Grows back when" text has been overwritten by the admission notice, so whatever condition was recorded there is gone. Harm: the next cut in that table cannot be admitted early by the same route, because nobody can say what the route is. Confidence: sure.

**39. Line 136 — "opening and commenting needs no repository permission"**
> "Issues cost nothing: the repository is public, so opening and commenting needs no repository permission."

Taken literally this is false: GitHub requires an authenticated account to open or comment on an issue in a public repository, issues can be disabled repository-wide, and interaction limits or a user block will refuse the write. It also contradicts line 139, which provisions "issues write" on every agent token — a scope that would be unnecessary if no permission were needed. Harm: an agent reasoning "issues need no permission" will not diagnose an issue-write failure as a credential problem, and a token could be provisioned without the scope on the strength of this sentence. Confidence: sure about the contradiction with line 139; sure that authentication is required.

**40. Line 136 — `NedLern` and `NedLerner` are distinguished only by a trailing "er", and one is a substring of the other**
> "The org has two owners (`NedLern`; `NedLerner`, settings and emergency power, no push)"

These two identities have opposite capabilities — one is the push credential, the other explicitly has "no push" — and no textual search can separate them: every grep, log scan, or audit rule matching `NedLern` also matches `NedLerner`. A misread or a substring match in tooling swaps the account that may push main with the account that may change branch protection. `CLAUDE.md` line 7 anticipates exactly this ("If these checks return collisions or ambiguity, choose a more explicit name"). Confidence: sure the collision is real; unsure whether the file can do anything about it, since these appear to be pre-existing GitHub account names rather than names this file invents — but the file introduces them into the design's vocabulary without flagging the hazard.

**41. Line 137 — the dedicated GitHub account has no name**
> "the pusher role moves to a **dedicated GitHub account** — a collaborator with write on this one repository, not admin, never an org owner — and protection's push restriction names it alone."

The amendment is stated as ruled and pending application, and applying it requires naming the account in the branch-protection restriction — but the account name is not given, nor is it said whether the account exists yet or must be created. Whoever applies the amendment (the file says an org owner must) cannot execute it from this document, and no later reader can verify that the live protection setting matches the design, which is exactly what the `protection-ok`/`protection-wrong` audit at line 144 is supposed to do. Confidence: sure the name is absent; unsure whether it is recorded in the C1–C8 issue the file cites.

**42. Line 138 — the sudoers boundary is claimed to make agent pushes "impossible", but the invoked program lives in an agent-writable checkout**
> "agents invoke the program through a sudoers rule scoped to exactly it. That is the step at which \"agents never push\" becomes impossible rather than instructed"

The program is `scripts/git-gatekeeper.py`, a repository-relative path — a file inside the working copies agents edit, and a file agents can change through the gate itself (nothing excludes it from `--files`). A sudoers rule naming that path runs whatever bytes are at it as the credential-holding user. The file states nothing about which copy is invoked, who owns it, whether it is immutable to agent sessions, or whether the sudoers entry pins a path outside agent-writable space. Until that is settled, the boundary is as strong as the file permissions on a script the agents are expected to develop — which reduces "impossible" back to "instructed". This also interacts with C7 (line 142), whose `--repo`/`--remote` refusals are enforced by that same mutable program. Confidence: sure the ownership/immutability of the invoked copy is unstated; unsure whether the deployed arrangement already separates them.

**43. Line 140 — "rewrites `gh` calls seamlessly into their disciplined form"**
> "a PreToolUse hook rewrites `gh` calls seamlessly into their disciplined form"

"Their disciplined form" is never defined, and neither is the set of `gh` calls affected. An agent asked to build or audit this hook has no specification: which subcommands are rewritten, what the rewrite is, and what happens to a call whose disciplined form does not exist. "Seamlessly" also means the caller is not told its command was changed, so a rewrite that guesses wrong is silent — in a design whose stated principle is that "the program never guesses". Confidence: sure it is un-executable as written.

**44. Line 140 — "`--base` computed as the merge-base"**
> "the check-in skill front-loads the declaration (`--files` from the agent's own staging, `--base` computed as the merge-base, message passed through verbatim)"

A merge-base is computed between two commits, and neither is named. Line 12 says "Ordinary changes use no branches", so in the ordinary case there is no second branch to take a merge-base with; the plausible intent (the local view of `origin/main`, or the last fetched main) is a different operation with different failure modes when the local copy is stale — and `--base` is the field whose staleness the whole concurrency section exists to handle. Harm: an implementer of the skill picks one reading, and a wrong choice produces `unknown-base`/`base-not-on-main` refusals, or a base far behind main that maximizes conflict. Confidence: sure the operands are unstated.

**45. Line 140 — "deny-with-exact-invocation" vs the same sentence's argument that the invocation cannot be derived**
> "a `git push` toward this repository's remote gets deny-with-exact-invocation instead — a push carries none of the declaration, and auto-deriving all of it would gut the intentionality"

If a push "carries none of the declaration" and auto-deriving it is rejected on principle, the hook cannot print an *exact* invocation: `--message` in particular is the field the file insists cannot be auto-filled ("Intent lives with the author; it cannot be auto-filled", line 49), and `--issue` and `--agent` are likewise caller-declared. The two halves of one sentence promise and forbid the same derivation. Harm: an implementer either builds a hook that fabricates a message — the precise outcome the sentence rejects — or builds one that prints a template, which is not what "exact invocation" says. Confidence: sure.

**46. Line 141 — break-glass commits will trip the audit designed to catch raw pushes, and no exemption is stated**
> "a landing the gate wrongly refuses uses a sudoers entry requiring the user's password, approved in the moment"

Such a commit is written outside the program, so it carries no `Gatekeeper-*` trailers — and line 144's standing audit "scans main for commits missing valid trailers and files a `draft` issue naming them". Nothing says how a sanctioned break-glass commit is distinguished from the unsanctioned raw push the audit exists to detect, nor whether the audit's issue is expected and should be closed, nor whether break-glass should leave a marker. Harm: either the audit generates false alarms that train agents to dismiss it, or a real raw push is dismissed as break-glass. Confidence: sure the interaction is unaddressed.

**47. Line 142 — `--repo` and `--remote` are absent from the interface definition and their refusal is unnamed**
> "`--repo` and `--remote` exist so tests can hand the program throwaway repositories. Run as the credential-holding user, they are refused"

Neither flag appears in the usage block at lines 36–44, which is presented as the request contract, and the refusal has no entry in the error catalog that claims to name every ending. Also unstated: what "run as the credential-holding user" is determined from (effective uid? an environment marker?), and what happens to the seams under the sudo path, where every real invocation runs as that user — the sentence "tests run unprivileged and keep the seams" asserts the test posture without saying what enforces it. Harm: an agent reading the usage block does not know the flags exist; one reading this line does not know what error to expect. Confidence: sure.

**48. Line 144 — the audit's "three named outcomes" do not cover the function the same sentence gives it**
> "a standing audit at each handoff scrub scans main for commits missing valid trailers and files a `draft` issue naming them, with **three named outcomes** — `protection-ok` / `protection-wrong` (differing settings named) / `audit-failed` (gh missing, unauthenticated, API error)"

The stated function is a trailer scan; the three outcomes are all about branch-protection *settings*. There is no named outcome for "trailer-less commits found" or "none found" — the very result the scan produces — and `protection-ok` would be reported for a main full of untrailered commits. Either two separate audits have been collapsed into one sentence, or the outcomes belong to a different audit than the one described. Line 8 and line 169 both say "the audits", plural, while this sentence says "a standing audit", singular, which reinforces the confusion. T12 (line 171) then tests "a raw push (simulated) is caught by the trailer-absence audit" — a fourth outcome name in a fourth vocabulary. Harm: slice 5 cannot be implemented or tested from this description. Confidence: sure.

**49. Line 150 — the cut table's stated reason for deferring the review-evidence check is contradicted by § Open**
> "| Review-evidence field + check | No artifact class is gated | The boss gates a class |"

Line 175 says the first class was designated on 2026-08-04: "instruction-bearing text (CLAUDE.md files, skills with their prompt templates, injected system prompts, the wiki), whose check-ins require walked-approval evidence". So the "Why" column is false as of this 2026-08-09 revision and the "Grows back when" trigger has already fired. Line 91 carries the same stale conditional ("when the boss gates an artifact class, its review-evidence check runs here"). Harm: a reader consulting the cut table to decide whether the evidence field is needed concludes it is not, when the deciding event has occurred and only the format is missing. Note this file is itself instruction-adjacent committed text, so the question of whether the class applies to it is live. Confidence: sure the table is stale relative to line 175.

**50. Line 159 — the section heading contradicts its own body**
> "## Cross-spec consequence, awaiting the boss"

The body begins "RESOLVED 2026-07-24, then SUPERSEDED 2026-08-02". Nothing in the section awaits anyone. Headings are what a reader scans and what a table of contents shows, so this one advertises an open dependency on the boss that does not exist — and line 177 separately lists this same item under § Open as "(resolved)". Confidence: sure.

**51. Line 165 — "stated here" states no values**
> "The repo's git config is minimal and stated here, not imported: `user.name`/`user.email` for the machine identity, `useConfigOnly` so no global identity leaks in."

The sentence claims to state the config and then names only the keys. The actual machine identity (`user.name`, `user.email`) is not given, and `useConfigOnly` is written bare rather than as `user.useConfigOnly`. Slice 5 is defined as including "repo git config" (line 8) and the build slice section leads with "The git config above" (line 169) — so an agent building slice 5 is told to apply a configuration whose values the document does not contain, and no other source is pointed to. Confidence: sure.

**52. Line 167/169 — "Build slice (choirmaster task 1)" describes the whole build, not a slice**
> "## Build slice (choirmaster task 1)" … "The git config above + `git-gatekeeper.py` with `check-in`, `status`, `cancel`, `imports` + the CLAUDE.md workflow lines + tests"

Singular "Build slice" and "task 1" describe what line 8 splits into five (or six) slices governed by a separate build-order document. A reader who lands on this section takes the T1–T12 list as the definition of done for one task, when line 8 says three of those slices are unbuilt and the ordering lives elsewhere. The section also gives no way to map T1–T12 onto the slices, so "which tests should pass now" is unanswerable — relevant since line 8 reports a 146-case suite whose relationship to T1–T12 is not stated either. Confidence: sure the section's scope conflicts with line 8's.

**53. Line 175 — a resolved item under "## Open", with a criterion that has already passed**
> "Which artifact classes, if any, are gated on review evidence from day one — the first class is now designated (boss-ruled 2026-08-04)"

The item is filed under Open but reports its own resolution, as does line 177 ("(resolved) The fast-handoff S2 interaction"). Two of the three Open items are closed, so a reader scanning for outstanding work must read each in full to discover that only C8 (cross-machine callers) is genuinely open. "From day one" is also undefined and, on any reading (the 2026-07-21 protection date or the founding), already in the past, so the question as phrased can no longer be answered. Confidence: sure.

---

clean sections: (none) — every section, including the YAML frontmatter and the untitled preamble, carries at least one finding above.

