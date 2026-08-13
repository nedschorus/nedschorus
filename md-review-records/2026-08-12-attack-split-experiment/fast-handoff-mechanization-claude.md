<!-- provenance: runtime=claude model=claude-fable-5 effort=xhigh attack=mechanization doc=fast-handoff isolation=instruction-pinned document set -->

I've read all three documents. This design is itself the product of aggressive mechanization rulings (the writer taking over every computable field, the mechanical word-floor boundary, the exact-match trigger message), so most sites are already on the right side of the line. I ran every remaining model-mediated step and human duty through the four rungs; four findings survived self-refutation, and several plausible candidates died on the document's own reasoning, which I record in the table.

Two notes on limits before the report: my document set is the three files only. Where a finding depends on the internals of `handoff-supervisor.py`, `handoff-write-and-check-supervisor.py`, the threshold hook, or the canary scripts — none of which I may read — I say so at the point of dependence rather than asserting.

---

# Mechanization attack report — fast-handoff design (pre-gut snapshot)

## Prompts-to-code table

Every place the document set relies on an LLM following English instructions or a human remembering a duty:

| # | Site | Reliance | Disposition |
|---|---|---|---|
| 1 | Skill step 1: compose `next-step` | LLM writes successor's first-action prompt | **Correctly delegated residue** (certified below) |
| 2 | Skill step 1: "instruction to act on, not a summary" | LLM holds the form discipline | Residue — no lint can classify instruction-vs-summary; walk item 7's positive recipe is the right tool |
| 3 | Skill step 1: file references "include its path and commit SHA" | LLM derives/recalls a SHA per reference, every handoff | **FINDING 3** |
| 4 | Skill step 1: issue references "include the repository and number" | LLM supplies the repository | **FINDING 3** (same stamp) |
| 5 | Skill step 2: `--agent <your name>` | LLM re-derives its name from CLAUDE.local.md prose each generation | Cleared with collision flag — walk item 6 records this as ruled deferred ("unscriptable until NC has an agent-naming convention"). Refuted as a finding besides: name drift self-heals through adoption (a misnamed successor's writer finds no supervisor under that name and starts an adopting one; the orphaned supervisor exits on the clean-stop branch), so the failure is fragmentation, not breakage. Not re-litigated. |
| 6 | Skill step 2: add `--dont-restart` "only when the user asked to be consulted" | LLM reads user intent | Residue |
| 7 | Skill step 3: obey the report (stop-and-wait vs keep-working) | LLM follows a script-computed branch | Cleared — the branch is computed by code; the kill is the mechanical guarantee. Agent compliance only avoids wasted final-turn work; non-compliance fails loudly (the kill lands regardless). |
| 8 | Skill step 3: "tell the user that the handoff is written but nothing is watching" | LLM relays a script report | Cleared — the script already prints the fact; the chat channel is only reachable by the model |
| 9 | Skill description: act "when a system message says the recycle threshold is reached" | LLM invokes the skill on an observable message | Residue — skill invocation is model-side by harness design; walk item 2 already converted the trigger from self-assessment to an observable event |
| 10 | Design, known holes: threshold hook "stays silent when nothing is watching" | Dead-supervisor recovery left to a human noticing | **FINDING 1** |
| 11 | Design, step 4: "**re-run both canaries after every Claude Code upgrade**" | Standing remembered human duty | **FINDING 2** |
| 12 | Design, verified-facts table pinned to v2.1.220 | Implicit human duty to re-verify on upgrade | **FINDING 2** (noted extension) |
| 13 | Design, step 6: ignition count-check, "confirm N tasks visible" | LLM verifies the pre-seed | Residue — only the session can see TaskList's view of the seeded records, and the trial showed the check's value is interpretive ("50 tasks read completed while `essays/` held 14 files"). A supervisor-side schema validation was my candidate and I refuted it: the pre-seed is a byte-copy of files the harness itself wrote, so it cannot *introduce* schema drift; the only real drift channel is an upgrade, which is Finding 2's territory. |
| 14 | Design, step 5: queue-status line's reader | A human watching the right console or log | **FINDING 4** |
| 15 | Design, step 6: successor reads the dialog before acting | LLM instructed via ignition prompt | Cleared — my inlining candidate (put the extract in the launch prompt so consumption is structural) is refuted by the design's own rule: the writer takes next-step "as a FILE, not an argument — a shell mangles backticks and quotes inside an inline argument"; inlining 2500+ words of verbatim dialog into argv reintroduces that hazard at scale. Four trial generations complied with the read instruction; the file also serves recovery. |
| 16 | Design, step 6: elapsed-time line's moral ("the longer the gap, the more will have changed") | LLM judges staleness | Residue — the line's arithmetic is already mechanical; how much the world moved in N days is not computable from N |
| 17 | Extract header: "reading further from the transcript an informed choice" | LLM chooses whether to read deeper | Residue — mechanical info enabling a judgment call |
| 18 | Design: "Settle this before the seat move" (successor output channel) | One-time human design decision | Cleared — not recurring; the trigger is a project event, not computable |
| 19 | Design: founding boot, `claude "$(cat <path>)"` | One-time human command | Cleared — by design, exactly once |
| 20 | Design: "a boss-called durable snapshot is an ordinary commit on request" | Human-triggered | Cleared — deliberate checkpoint |
| 21 | Design: `dont-restart` y/n prompt | Human answers | Cleared — the consultation is the point of the flag |
| 22 | Design, principles: "fed continuously by commit-as-you-go" | Standing agent habit relied on as the long-term-record bound | Out of scope — the habit and its rulings (boss-ruled 2026-08-02, git as record) live outside my document set, which I cannot read. Noted, not pursued. |
| 23 | Design: "memory maintenance is the boss's drain per the #32 Q1 ruling" | Human duty | Cleared — recorded ruling, flagged, not re-litigated; the issue is outside my set |
| 24 | Writer mechanics: timestamp, counter derivation, whitespace collapse, atomic write, empty-next-step refusal, file-not-argument | — | Already mechanized (the 2026-08-06 ruling's exemplar) |
| 25 | Extractor boundary: 2500-word floor, clean-turn extension, left-behind header | — | Already mechanized (agent boundary judgment removed by ruling) |
| 26 | Trigger message "Run the handoff skill now", exact-match tested | — | Already mechanized (the test even guards against procedure text creeping back) |
| 27 | Supervisor liveness `--check`, consumed by skill and hook | — | Already mechanized |
| 28 | Retention, lock file with stale reclaim, pre-seed copy, ignition assembly, queue-line computation | — | Already mechanized |
| 29 | Auto-trigger mechanism | — | Already mechanized, but the document describes it two ways: the "Auto-trigger" section says the Stop hook reads the statusline relay file, while "Auto-trigger — read cost" says it reads the transcript tail for the newest assistant record — and the fact table proves a relay-only trigger "cannot fire" headless, yet the headless trial auto-triggered three times. The built thing evidently works; the description of it is internally inconsistent. That is documentation drift, not an un-mechanized prompt — another attack's territory; I flag it only because Finding 1 touches this hook. |

---

## Findings, deepest first

### Finding 1 — the threshold hook's stay-silent rule defeats the self-healing the writer already provides

**Collision flag, stated plainly:** this finding contradicts a closed hole — "Closed 2026-08-06 (user-asked): … the threshold hook stays silent when nothing is watching, so it cannot ask for a handoff nobody will act on." It also touches the recorded open question ("Settle this before the seat move"). I am not re-litigating silently; I am reporting that two same-day rulings compose into a gap neither contemplated.

**WHAT.** Remove (or invert) the hook's suppression: when the threshold crosses and `--check` reports no supervisor, the hook still fires the trigger message, because the skill's own step 2 now handles the no-supervisor case mechanically — the writer starts an adopting supervisor. For the interactive-pane case, where an auto-started detached supervisor would launch an invisible successor, fold the decision into the recorded open question rather than deciding here; the mechanization is unambiguous for headless and detached agents.

**WHY.** The silence rule's stated justification is now false by the document's own text. The rule: the hook "cannot ask for a handoff nobody will act on." But the same revision records: "**the agent starts it** when its handoff script finds none watching (user-asked 2026-08-06)," and the skill's step 3: "When it found a supervisor watching, **or started one**, stop working and wait." A handoff request with nothing watching *is* acted on — the writer starts the supervisor. The composition of the two rulings leaves exactly one path dead: a supervisor dies mid-session, the hook goes silent at threshold, the skill never fires, the writer's self-registration never runs, and the known-holes sentence "if it dies, recycling stops until relaunched" resolves to *relaunched by a human who happened to notice a session silently running past its threshold forever*. That is a remembered human duty ("notice the dead supervisor") whose trigger is fully computable — threshold crossed AND `--check` exits 1 — and whose remedy is already built. Priority 1: "more autonomous, fewer or no user interventions; mechanical guarantees over trained agent habit."

**LOST.** The silence rule may be silently carrying a second purpose the document never states: keeping a watched console pane from having its session killed and its successor launched invisibly under a detached supervisor. If so, firing the hook unconditionally trades a human-visible pane for an invisible successor — which is why the pane case must ride the open question, not this finding. I cannot read the hook or writer scripts to confirm which purposes the silence actually serves; the document states only the "nobody will act on it" rationale, which is the one this finding refutes.

**CONSEQUENCES.** The known-holes bullet "the threshold hook stays silent when nothing is watching, so it cannot ask for a handoff nobody will act on" becomes false as written. In the same bullet, "if it dies, recycling stops until relaunched" becomes "until the next threshold crossing." The Tests line "threshold crossing fires the skill exactly once" gains the no-supervisor branch (fires, and exactly once, when nothing is watching). The 14-case trigger suite changes. The open-question paragraph gains a dependency: its settlement now also decides the hook's pane behavior.

### Finding 2 — the per-upgrade canary duty has a computable trigger; encode it

**WHAT.** The supervisor records the Claude Code version under which the pre-seed canaries last passed (in the state file it already maintains); at startup — or at latest before each pre-seed — it compares the current `claude --version` and, on mismatch, runs the two canaries automatically, or refuses pre-seed with a loud instruction naming them if auto-run in place is judged unsafe. Either variant deletes the standing duty; which one is a tuning choice for triage.

**WHY.** The document states the duty twice, once in bold: "**re-run both canaries after every Claude Code upgrade**" (step 4) and "task pre-seed as executable canaries (re-run per upgrade)" (Tests). It also states why the duty exists: "Pre-seed rides undocumented harness state," and the canary record shows the failure is silent — "a record with an integer id is dropped by TaskList while still counting toward the next allocated id — so a schema-wrong pre-seed looks half-successful." A silent failure class guarded by a human remembering to act at an event no mechanism watches is precisely the pattern my brief names: "a mechanization candidate whenever its trigger is computable — a version comparison." The trigger is one string comparison; the canaries are already described as executable. Operator cost is not builder cost: this duty otherwise rides every upgrade, forever. Priority 1: "zero remembered human steps." Extension, noted not pressed: the whole verified-facts table is pinned to "Claude Code v2.1.220"; the same version gate can at least *announce* that the table's facts are now unverified, which no mechanism currently does.

**LOST.** The deliberate human attention at upgrade time, and a new failure mode: if a canary itself flakes, supervisor startup blocks or noisily degrades on a non-event. The refuse-vs-warn choice tunes that. Auto-running also writes task-store side effects at supervisor start. Priority 1 pays for all of it.

**CONSEQUENCES.** Step 4's bolded sentence becomes a mechanism description. The Tests line "(re-run per upgrade)" becomes "(version-gated, run automatically on upgrade)". The known-holes bullet "bounded by the ignition count-check and the per-upgrade canaries" updates. The supervisor suite (24 offline cases) gains version-gate cases; the state file grows a field, and the state-file sentences in the counter and liveness discussions gain a sibling. **Dependency I cannot verify:** the finding assumes "executable canaries" means invocable on demand outside the test suite; the canary scripts are outside my document set.

### Finding 3 — the pin is a field a machine can compute; the writer should stamp it

**Collision flag, stated plainly:** the pin sentences are user-authored, walked, and approved text (walk item 4: "REVISED then approved (user-authored text) … Pinning is now two observable cases"). This finding amends that walked text. I read it as completing, not contradicting, the same walk's item 5 ruling — but that judgment belongs to triage and the user, not to me.

**WHAT.** The writer stamps into the handoff file, mechanically: the worktree's repository identity (origin `owner/repo`) and `git rev-parse HEAD` at write time, plus a dirty flag. The default pin for every file and issue reference in `next-step` is then "this repo, at this commit, as of this handoff" without the agent writing anything. The skill's pin duty narrows to the genuinely non-default cases: a file meant at a non-HEAD revision, an issue in another repository. (A weaker alternative — a writer-side lint flagging `#N` without a repo or paths without a nearby SHA — died in refutation: regexing prose for "references" false-positives constantly, and the stamp makes it unnecessary.)

**WHY.** The design's own ruling, quoted: "**The agent supplies only `next-step`; the writer fills every field a machine can compute (user-ruled 2026-08-06).**" The pin bullet, quoted: "**Every pointer carries a pin** — a file reference gives its path and commit SHA … so the successor resolves what the writer meant rather than whatever the artifact says by read time." For any file at HEAD — the overwhelming case under "commit-as-you-go" — that SHA *is* a field a machine can compute, currently re-derived by the model per reference, per handoff, forever. This is the brief's named cut class ("facts used directly instead of re-derived") and the exact fact class of the project's accepted worked example, where agents hand-passing a 40-character commit id to the check-in gate was replaced by one git command. The current rule is also a hallucination channel the stamp closes: an agent recalling or typing a 40-character SHA can produce a wrong one, and a wrong pin is strictly worse than none — the successor then "resolves what the writer meant" to the wrong revision, confidently.

**LOST.** Per-pointer self-containedness: a bare path in `next-step` now needs the stamp consulted to know its revision, one indirection (priority 2 taxed slightly; priority 1 pays). Interpretive slack the current rule also lacks: neither version distinguishes "the file as it was" from "go look at the current state" — the residue duty for non-default pins keeps that with the model, where it belongs.

**CONSEQUENCES.** Skill step 1's last two sentences ("If your prompt references a file, include its path and commit SHA. If it references a GitHub issue, include the repository and number.") revise — walked text, hence the flag. The design's `next-step` bullet revises, and "The fields" gains the stamp field(s). The writer description (component 2a) and its 27-case suite gain stamp cases. Walk item 4's disposition becomes historical record (the draft file already declares itself history, so no edit needed there). **Dependency I cannot verify:** that the supervisor's `key: value` parser tolerates additional keys; the supervisor script is outside my set. The ruling sentence "the writer fills every field a machine can compute" is not falsified but strengthened.

### Finding 4 — the queue-status line has no guaranteed reader; give it one

**Overlap flag:** this feeds the recorded open question ("Settle this before the seat move rather than after"); it is input to that settlement, not a rival ruling.

**WHAT.** The supervisor appends its computed queue-status line to the ignition prompt (or the extract header), making the successor agent the line's structural reader; the console print can remain.

**WHY.** The line exists as a duty discharge: "the artifact-lifecycle rot-visibility duty riding every recycle at zero agent cost." But visibility requires a viewer, and the document itself establishes that in the adoption path there isn't one: "A supervisor the agent starts is detached, with its output going to `<agent>-supervisor.log`," a file no one is stated to read. In that path the mechanized duty discharges into a void — the human duty ("look at the queue line") was never removed, only relocated to a log. Routing the line into the ignition prompt gives it a reader under *both* candidate settlements of the open question, at the cost of one line of successor context. Priority 1: the duty becomes structurally fulfilled instead of contingent on a human watching the right console.

**LOST.** Ignition-prompt minimality — the template is currently exactly "path, elapsed-time line, task count, next step." One line of successor context per recycle. Nothing else.

**CONSEQUENCES.** Step 5's sentence gains a delivery clause; step 6's ignition contents and component 5's template list gain the line; the supervisor test "ignition prompt contains path + elapsed-time line + task count" gains a fourth clause; the open-question paragraph gains a partial answer.

---

## Delegated residue — certified

What remains with the model after these findings, and why no code can carry each piece:

- **Composing `next-step`.** The skill's own description carves this out as "the one piece": the successor's correct first action depends on what the unfinished work *means*, which exists nowhere but in the session's understanding. No mechanism has access to intent. This is the system's designed interpretive core, and the design has already stripped everything computable from around it.
- **Holding the instruction-not-summary form.** Classifying prose as instruction versus summary is semantic; a lint would misfire both ways. Walk item 7's positive recipe ("what the output IS") is the correct non-code tool.
- **Non-default pins** (if Finding 3 lands). Whether a reference means HEAD-now, a historical revision, or read-time state is authorial intent — the stamp covers the default; only the model knows when it means something else.
- **Reading `--dont-restart` intent.** "The user asked to be consulted" is a fact about conversation meaning, not about any file or state code can inspect.
- **Acting on the trigger message.** Hooks can inject the message mechanically — and do, exact-match tested — but executing a skill whose payload is composition is model-side by harness construction.
- **The ignition count-check and the challenge-inconsistent-state behavior.** The harness's view of the seeded tasks is observable only from inside the session (TaskList), and the trial showed the check's real value is interpretive: relating "50 tasks read completed" to "`essays/` held 14 files" is semantic reconciliation no comparison of integers performs. The arithmetic is trivial; the vantage and the judgment are not mechanizable.
- **Judging staleness from the elapsed-time line, and choosing whether to read past the extract boundary.** The numbers are computed mechanically; what they imply about a changed world is not computable from them.

One closing observation for triage: this document is unusually far along the mechanization axis already — three of my strongest candidates (extractor boundary, writer fields, trigger wording) turned out to be *this revision's own prior rulings*, and two more candidates (pre-seed schema validation, extract inlining) were refuted by the document's own recorded reasoning. The four survivors are all seams *between* rulings — places where two mechanizations landed the same day and their composition, not either one alone, leaves a duty with a human or a fact with the model.
