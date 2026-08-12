---
status: integrated design; decisions ruled 2026-08-07 in the plan walk, md-review corrections ruled 2026-08-09; integration walk in progress — items 1–5 processed, item 6 (close-out) open; § Prompts md-review dispositioned 2026-08-11
design-as-of: 2026-08-11
---

# ghi-info — the GHI knowledge agent (design)

## Walk order — integration walk (opened 2026-08-09, new-vp session 3a11d08f; this block is removed when the walk closes)

1. The walked core, confirmed whole — identity, duties, answer form, seat, mirror shape, no-gate posture, three-layer stack
   *processed 2026-08-09 → CONFIRMED in six parts (user); rider ruled: the over-specification correctness rule lands in the skill-authoring checklist's Register section, not CLAUDE.md — applied same day; nothing from this design touches CLAUDE.md.*
2. The GHI write path — hook rewrite, the tool's four-step sequence, comments/close/delete, soft block and override, accepted holes
   *revised 2026-08-11 (user, settled after a soft/hard back-and-forth in the § Prompts md-review walk): denials stay soft with a reconsider-to-pass override — reconsider once against the refusal's stated reason and, still convinced, pass one resubmit via the `.ghi-issue-write-reconsidered` marker; no user approval, no forced escalation — GHI-filing mistakes are not worth the user's attention. The open-perimeter half of the ruling stands. See § The GHI write path, "Soft block, reconsider-to-pass."*
   *processed 2026-08-09 → APPROVED in three parts (user), with the soft-block observation captured: code reviewers reflexively push to harden soft blocks, so the ruling is now recorded in the greppable Accepted-residual form, which the standing reviewer counterpart rule protects — re-flagged only with evidence matching the named reopening trigger, never as an ordinary finding. Side answers ruled along the way: untouched state changes reach the mirror through the normal delta with the recycle rewrite as backstop; mirror fields grow by deliberate one-line script edits, never automatically.*
3. The ask path — wrapper steps, drift notice and recheck, `--include-closed`, throwaway-session concurrency, fallback ladder
   *processed 2026-08-09 → APPROVED in two parts (user), with the drift notice reworded to kill an ambiguity: the closure fact is the script's, established from the just-refreshed mirror — the notice hands the agent the fact and asks only for a judgment redo over mirror files; the agent never calls GitHub to verify state.*
4. The session and currency — lifecycle, recycle triggers, two-cadence refresh, freshness and the Superseded-by marker
   *processed 2026-08-09 → APPROVED (user).*
5. Maintenance and fixers — the sweep, spawned focused fixers, escalation, the model-per-role open question
   *processed 2026-08-11 → APPROVED (user), via a fixer-brief drafting round and a zero-context teaching walk. Rulings: the single fixer brief split into two templates, one per defect kind — the sweep picks the template, each brief covers exactly one job; the sweep pre-runs `scripts/ghi-info-ask.py` and embeds the reading list in the brief — the fixer invokes nothing; "do only the job stated above" replaced "smallest change"; every prompt opens for a zero-context reader; `BODY_WORD_LIMIT` starting value 500 (constants line updated); staleness swept one direction only, issue-ahead, with the lapsed-cite gap recorded as accepted residual (§ Maintenance and fixers); ruled text in an over-length body moves verbatim into the pair document with the body summary citing it — only rewording blocks (Template B); every prompt the design depends on lands verbatim in § Prompts, which passes its own md-review before the design's status closes — four prompts still owed there.*
6. Close-out — where this document lands, the build GHI, and the riders (ghi-write walk resume, correctness-rule review, #26 lifecycle revision)
   *open 2026-08-11 — close-out sequence approved (user): draft the four owed § Prompts entries one at a time → md-review the section → landing decision (recommendation on the table: the design becomes the build GHI's pair document) → file the build GHI → queue the riders. Prompts all final; § Prompts md-review run and dispositioned 2026-08-11 ([md-review-records/2026-08-11-ghi-info-agent-design/dispositions.md](../../md-review-records/2026-08-11-ghi-info-agent-design/dispositions.md)) — its rider of deep whole-doc findings awaits routing at this item's close.*

How agents work with GitHub issues (GHIs) in nedschorus: `ghi-info`, a long-lived knowledge agent over the issue corpus; a script-maintained local mirror; a write path whose hook routes raw writes through the project write tool; and the `ghi-write` skill carrying the judgment none of the machinery can. Throughout, **GHI author** means whichever agent is filing or editing an issue. Decision trail: [ghi-info-agent-plan-draft.md](ghi-info-agent-plan-draft.md) (per-item dispositions, 2026-08-07) and [md-review-records/2026-08-09-ghi-info-agent-design-2/dispositions.md](../../md-review-records/2026-08-09-ghi-info-agent-design-2/dispositions.md); the rejected single-gate direction is preserved at [ghi-gatekeeper-plan-draft.md](ghi-gatekeeper-plan-draft.md).

The organizing idea: instead of building a vector or graph database of the GHIs, we use a modern agent — the corpus fits in its context window (measured 2026-08-07: 45 issues ≈ 109 KB). Mechanical work is script work — fetch, format, measure, filter; `ghi-info` spends model turns only on judgment.

## What ghi-info is

The first build of the domain-knowledge-agent class defined in [26-dynamic-agent-team-model.md](../issues/26-dynamic-agent-team-model.md) ("the GHIs" is that class's first listed domain). Three duties:

1. **Answer asks.** A GHI author, before filing or editing, asks what it should read. The answer is a bare list — "read #13, #24, #31."
2. **Maintain.** Cross-links between issues, and link integrity across the issue–MD boundary in both directions: every GHI→MD reference resolves on main; every pair MD backlinks its correct GHI(s). Link repairs are `ghi-info`'s own writes — its only write class. Detected problems beyond links — a pair MD stale relative to its issue, a body over the length limit — spawn fixers (§ Maintenance and fixers).
3. **Adjudicate writes.** The write tool consults `ghi-info` with the actual draft title and body — plus, for edits, the target issue number, which is excluded from the comparison. The reply is one line: `verdict: too-similar #n` / `related #n,#m` / `unrelated`. A malformed reply is treated as unavailable (fail-open). From the verdict the tool composes the author-facing reply: **too-similar** (duplicate, overlapping, conflicting) — the write is refused with a merge instruction: read #n, then merge this content into it by editing it; **related but compatible** — the write proceeds, and the reply names the GHIs to become familiar with; **unrelated** — plain success.

Out of scope: routing (queue vs GHI vs pair vs bare MD — `ghi-write`'s judgment; terms defined in [nedschorus-founding-plan.md](../cross-project/nedschorus-founding-plan.md) § Project organization); authoring issue or MD substance; anything beyond the issue corpus — asked about the wiki or the code, it returns a fixed `out-of-scope` reply. Whether an old ruling still binds is never `ghi-info`'s to decide. Its reply names the ruling and the doubt (`escalate:`), and the question travels up the chain unswallowed: the caller resolves it if it can, and otherwise it lands as one `draft`-labeled issue — the same escalation surface as a blocked fix — for whoever can attend to it, agent or human.

## The GHI mirror (ghi-mirror)

`<checkout>/ghi-mirror/`, gitignored; regenerated by `scripts/ghi-mirror-refresh.py` on any machine. The authoritative copy lives in `ghi-info`'s checkout on the box. GitHub is the source of truth; the mirror is derived data.

Two files, split by state: `issues-open.md` — every open issue near-raw (number, title, labels, updated time, body, comments); `issues-closed.md` — one line per closed issue: number, title, close reason, closed date. Routine relatedness checks grep the open file; the closed file joins the search for an absence claim (a "no issue covers X" receipt is invalid unless both files were searched) or an explicit precedent hunt.

**Refresh cadence.** Per ask: a delta — one `updated:>` query against the mirror's newest entry re-fetches changed issues, moving entries between files on state change; comments are fetched only for changed issues (one call per issue). At every session recycle the mirror is rewritten whole from a full fetch: anything the delta cannot see — a deletion, a same-second boundary clip — is purged then, so delta blind spots are bounded by the recycle cadence. Mirror writes go temp-then-rename, so concurrent refreshes are safe. Measured 2026-08-07 against the live repo: a full pull of all 45 issues with bodies took 0.82 s; `updated:>` returned exactly the issues touched since a timestamp.

**The second feed:** the refresh fetches origin and reads `git log origin/main` — pair-MD edits touch no issue timestamp, and they enter the corpus when they land on main.

**Currency.** Each entry carries its updated time plus an activity-relative freshness — project events since this issue last moved; activity, not calendar time, is the aging clock. Supersession is the marker literal `Superseded-by: #<n>`, written at change time by the author who knows. The sweep greps the marker and verifies its targets; detecting *unmarked* same-ground pairs is similarity judgment, which belongs to `ghi-info` — the write-time adjudication catches new instances.

## The ghi-info session

**Seat:** the Ubuntu box, `~/agents/ghi-info` (the box convention; see [nedschorus#45](https://github.com/nedschorus/nedschorus/issues/45)); wrapper state — session id, counters — lives there. Mac-side callers reach it over SSH (`scripts/launch-claude`, same issue).

**Lifecycle:** active while taking a turn, otherwise exited — a session id, transcript, and the mirror persist; no process does. No idle state exists for this class.

**Context:** a cold start loads `issues-open.md` whole; closed issues enter a turn only by grep. A resumed session's context drifts — the mirror refreshes every turn, but entries loaded earlier stay in context, and the agent cannot reliably notice on its own; the wrapper notices for it (§ The ask path). Recycle fires on the first of three script-observable triggers: closes since session birth, the stale-match rate, transcript size. Recycling errs eager: an eager recycle costs one cheap reload; a lazy one costs silently wrong answers.

## The ask path (ghi-info-ask)

`scripts/ghi-info-ask.py`, run by any agent — and by `ghi-write` step 1. The write tool's adjudication consult rides this same wrapper (user-ruled 2026-08-11): one stored session, one refresh-and-resume machinery, every request form riding it (reading-list asks, adjudication consults, link-repair requests). In order:

1. Run the mirror refresh (delta).
2. Resume the stored session; cold-start when none exists or a recycle trigger has fired. If another ask holds the session, cold-start a throwaway session instead — nothing waits, nothing shares a transcript.
3. Prompt: the question — plus, on resume, the changed-issue numbers with the instruction to re-read those entries from the mirror before answering. `--include-closed` marks a deliberate closed-history question (precedent, absence): `ghi-info` greps the closed file, and closed pointers are expected.
4. Post-check: every returned pointer is verified against the mirror — plain script work; the fact is established here, never by the agent. An unexpected closed pointer triggers one drift notice back to `ghi-info`, carrying the fact and asking only for a judgment redo: "#31 closed on <date> — the mirror is current; re-read its entry in `issues-closed.md`, including any `Superseded-by:` link, and give a corrected reading list." One recheck per ask; the agent reads only mirror files and never calls GitHub. Whatever remains is delivered with truthful tags ("#31 (closed 2026-08-08)"); note lines are plain sentences. Replies that are not reading lists — `escalate:`, `out-of-scope` — pass through to the caller verbatim; the caller owns the escalation and must not swallow it. Unexpected closed pointers count toward the stale-match trigger; expected ones do not.
5. Print the list.

One overall timeout (inside the hook budget); a killed run is a named failure. Auth is the box's two credentials — its `gh` login and its long-lived Claude token (interactive logins expire unattended). Precedent: nedsmessenger runs this pattern live (`~/Projects/nedsmessenger/adapter/adapter.py`, `ask_claude` — headless `claude -p --resume`, answer off the exit stream; NM runs three watchdogs where version 1 here starts with one timeout).

**A failed ask never blocks a write.** The ladder: ask → grep the local mirror (stale if not regenerated) → `gh` search → proceed under the ordinary rules — the `ghi-write` skill and the artifact-lifecycle rule. Self-correction: a GHI author who finds a relation `ghi-info` missed adds the cross-link while editing; the next refresh carries it into the corpus, and answers reflect it after the next reload — a lag bounded by the recycle triggers.

## The GHI write path (ghi-issue-write)

GHI authors write with `gh` as trained for create, edit, and close; comments are the one taught exception. A PreToolUse hook (`.claude/hooks/ghi-issue-write-redirect.py`, sibling of `.claude/hooks/instruction-file-guard.py`) rewrites body-bearing `gh issue create`/`edit` into `scripts/ghi-issue-write.py` via `updatedInput` (rewrite mechanics and the 600 s configurable command-hook timeout verified 2026-08-07 against https://code.claude.com/docs/en/hooks). The tool's internal `gh` calls are subprocesses below the hook layer; `ghi-info`'s and fixers' writes route through the tool like any author's.

The tool's sequence per write:

1. **Reference check.** In-repo paths cited in the body must resolve on main. A failing reference refuses with both branches: land the MD first, or file without the reference and add it by edit once landed. No GHI is required to cite an MD — the check is reactive to what the body cites.
2. **Similarity adjudication** (§ What ghi-info is; the edit's own issue excluded). Fail-open: `ghi-info` unreachable means the write proceeds without adjudication — the mechanical checks still run.
3. **The write**, via `gh` internally; the tool relays `gh`'s own output verbatim and appends its lines after it.
4. **Length measurement** — no author counts words. Over the limit, the reply instructs: keep a good summary in the body; merge the substance into the linked pair MD, creating or updating it. The author holds the context, so the author does the split; what to link comes from asking `ghi-info`.

Accepted residual: an issue can change between verdict and write.

**Comments:** `gh issue comment` — and `close --comment` — are denied with a teaching reply: a comment cannot be mechanically rewritten into the body edit the revision convention requires ([nedschorus-founding-plan.md](../cross-project/nedschorus-founding-plan.md) § Project organization) — where the content lands, and what it supersedes, only the author knows. The reply teaches both paths: integrate into the body by edit, or resubmit through the tool's comment verb naming an event kind from the fixed catalog (instance outcome, completion, ruling challenge; growth only by explicit ruling; whether "completion" collapses into close-with-reason is deferred to the `ghi-write` walk). One lost turn per attempt, accepted.

**Close** is a state change with a reason (completed / not planned); plain `close` and `reopen` pass the hook untouched and the delta feed carries them. **Non-body edits** (labels, title-only, milestones) pass through — accepted residual: a rename could disguise a duplicate. **Delete** is denied — close instead; the record is append-forward.

**Soft block, reconsider-to-pass.** A refusal's one job is a deliberate second look (user-ruled 2026-08-11, settling a soft/hard back-and-forth: GHI-filing mistakes are not worth the user's attention — a smart agent told to reconsider, and reconsidering, is good enough). Every deny path ends with the same closing line (verbatim in § Prompts): reconsider once against the refusal's stated reason; still convinced, write the reasoning into `.ghi-issue-write-reconsidered` at the repository root and resubmit — the marker passes exactly one write and is consumed by it (the `.claude/hooks/instruction-file-guard.py` mechanics, live on main, carrying the agent's reconsidered reasoning rather than user approval; the reasoning stays visible in the transcript). Infrastructure failure never produces a refusal: adjudication fails open. **Accepted residual (user-ruled 2026-08-07, reaffirmed 2026-08-09; unchanged by the 2026-08-11 revision):** the enumeration holes stay open — `gh api`, MCP tools, creative quoting — under **the cooperative posture**: enforcement targets mistakes, not evasion (the same stance as [git-gatekeeper-design.md](../cross-project/git-gatekeeper-design.md) § The credential and enforcement). Reviewers re-flag the open perimeter only with evidence matching its reopening trigger: the delta showing deliberate evasion, not breakage. Bypassed writes still appear in the delta, where the sweep finds their symptoms.

**Codex** is in scope as the planned companion runtime; until its hook equivalence is verified at build, Codex-side writes ride the accepted-holes class with the skill as their up-front layer.

## Maintenance and fixers

The sweep is script work riding the two feeds: the length check over changed bodies, the `Superseded-by:` marker scan, and the link-integrity scan in both directions (the MD side read from the repo checkout, not the mirror). Findings spawn **one-shot focused fixer agents** (the class in [26-dynamic-agent-team-model.md](../issues/26-dynamic-agent-team-model.md); launched per [nedschorus#41](https://github.com/nedschorus/nedschorus/issues/41)) with tight briefs — one defect each, verbatim in § Prompts. Fixers write through the normal path; their reading list is pre-fetched by the sweep, so the fixer invokes nothing to discover its inputs. **Fixer repairs land on main immediately (user-ruled 2026-08-11, an explicit exception to the review-lane convention):** the fixer commits and pushes its document changes itself — on a push race, re-pull and retry once, else blocked — the same immediacy the issue half of every repair already has through gh. The guardrails are the brief's blocked conditions, and the record is append-forward and revertable; the same ruling covers `ghi-info`'s document-side link repairs. `ghi-info` repairs links only, never substance. Pair staleness is swept in one direction only — issue moved, pair MD not. The reverse (MD landed on main, issue silent since) is deliberately unswept (user-ruled 2026-08-11): MD-ahead is the pair sequence's normal intermediate state, and the body is a summary many MD edits never touch. **Accepted residual:** an author who lands the MD but never completes the cite step goes uncaught by this sweep; the link-integrity scan does not catch it either (a never-added link resolves vacuously). The sweep files a blocked fix's escalation from the fixer's `blocked:` reply — one `draft`-labeled issue naming what blocked it. Which model and runtime serve each role best — `ghi-info`, fixers, adjudication; Claude or Codex; fable, opus, sonnet — is an open question, settled empirically.

## The three-layer stack

1. **`ghi-write`** (skill; in build — walk in progress at [ghi-write-skill-draft.md](ghi-write-skill-draft.md)): fires when a GHI author is about to file or edit; front-loads the right behavior — ask `ghi-info` first, route by state, edit rather than duplicate, write lean, and the pair sequence: write the MD, land it, then cite it.
2. **Hook + tool** — the correctness backstop when the skill does not fire: on the covered write path with `ghi-info` answering, a missed trigger costs efficiency — a late merge catch, one comment retry. The fail-open window and the enumeration holes are the accepted residuals, visible in the delta.
3. **CLAUDE.md** — ambient documentation only ([nedschorus#13](https://github.com/nedschorus/nedschorus/issues/13) is this project's record of a written convention losing to trained habit).

## Division of labor

| Work | Owner | Cost |
|---|---|---|
| Fetch, format, delta-merge, state split | `ghi-mirror-refresh.py` | free |
| Reference and length checks | `ghi-issue-write.py` | free |
| Freshness numbers, marker scan, link-integrity scan | sweep scripts | free |
| Answer post-check and drift notice | `ghi-info-ask.py` | free (a recheck costs `ghi-info` one call) |
| Which issues bear on a question; similarity verdicts | `ghi-info` | a model call |
| Cross-link repairs | `ghi-info` | its one write class |
| Routing, body substance, the lean-split merge | the GHI author (via `ghi-write`) | context already loaded |
| Stale-MD and over-length repairs found by the sweep | spawned focused fixers | one one-shot agent each |

## Prompts

Every prompt this design depends on, verbatim (user-ruled 2026-08-09/11): a prompt that exists only as description is not buildable or reviewable. Each opens for a zero-context reader. This section passes its own md-review before the design's status closes. Angle-bracket `<slots>` are filled by the invoking script, never by the agent receiving the prompt.

**Status: every prompt is final** — the two fixer briefs, the drift notice, the cold-start prompt (four request forms), the resume ask, the adjudication request, the link-repair request (user-ruled 2026-08-11: worded here rather than left to build), the sweep ask, and the write tool replies. The section's required md-review ran 2026-08-11; dispositions in [md-review-records/2026-08-11-ghi-info-agent-design/dispositions.md](../../md-review-records/2026-08-11-ghi-info-agent-design/dispositions.md).

### Fixer brief — pair document behind its issue (approved 2026-08-11)

The sweep fills every slot, including the reading list, which it gets by running `ghi-info-ask.py` itself before spawning — the fixer invokes nothing.

> You are a fixer: a one-shot agent spawned when a maintenance script finds that a pair document in this project's GitHub-issue records has fallen behind its issue. Your entire purpose is to bring the one document below up to date, then exit.
>
> Job: Issue #\<n\> changed on \<date\>; its pair document \<path\> is untouched since \<date\>. Update the document to match the issue's current state.
>
> Read first: issue #\<n\>; its pair document at \<path\>; and these related issues: \<the list ghi-info returned when the sweep asked on your behalf, e.g. #13, #24\>.
>
> Rules:
>
> - You change only the pair document, committed with a message stating what and why and landed on main immediately: push; on a push race, re-pull and retry once — if it still fails, report blocked. You do not write to any issue.
> - Do only the job stated above.
>
> Stop and report blocked instead of editing if:
>
> - the change would alter text marked as ruled ("user-ruled", "boss-ruled", "Accepted residual", a dated ruling), or would choose between two such statements;
> - the issue and document conflict in a way the record does not resolve;
> - you are unsure the change is correct.
>
> Your final message is exactly one of:
>
> - done: \<what changed — files\>
> - done: no change needed — \<why the issue's change required no document update\>
> - blocked: \<what stopped you, quoting the text at issue\>

### Fixer brief — issue body over the length limit (approved 2026-08-11)

Same slot-filling contract as above. The ruled-text handling is the verbatim-move exception (user-ruled 2026-08-11): ruled text may change address, never wording.

> You are a fixer: a one-shot agent spawned when a maintenance script finds an issue body in this project's GitHub-issue records grown past the length limit. Your entire purpose is to shorten the one body below, then exit.
>
> Job: Issue #\<n\>'s body is \<count\> words; the limit is \<limit\>. Keep a good summary in the body; merge the substance into its pair document \<path\>, creating it if it does not exist.
>
> Read first: issue #\<n\>; its pair document at \<path\> (may not exist yet); and these related issues: \<the list ghi-info returned when the sweep asked on your behalf, e.g. #13, #24\>.
>
> Rules:
>
> - Land the document before the body edit: document changes are committed with a message stating what and why and pushed to main immediately (on a push race, re-pull and retry once; if it still fails, report blocked). The body edit then goes through gh as normal — the write tool refuses citations that do not resolve on main, which is why the document lands first.
> - Nothing removed from the body may be lost: it must land in the pair document.
> - Text marked as ruled ("user-ruled", "boss-ruled", "Accepted residual", a dated ruling) moves only word-for-word: carry it into the pair document verbatim, and have the body's summary cite where it went.
> - Do only the job stated above.
>
> Stop and report blocked instead of editing if:
>
> - the change would reword text marked as ruled — moving it verbatim, as the rules allow, is the only permitted handling — or would choose between two such statements;
> - the issue and document conflict in a way the record does not resolve;
> - you are unsure the change is correct.
>
> Your final message is exactly one of:
>
> - done: \<what changed — files, issue numbers\>
> - blocked: \<what stopped you, quoting the text at issue\>

### Drift notice (ghi-info-ask post-check → ghi-info; final, worded 2026-08-09 in § The ask path)

> #\<n\> closed on \<date\> — the mirror is current; re-read its entry in `issues-closed.md`, including any `Superseded-by:` link, and give a corrected reading list.

### Cold-start prompt (ghi-info session birth; approved 2026-08-11)

Delivered as the first prompt of a fresh session — cold start fires when no stored session exists or a recycle trigger has fired (ghi-info-ask step 2). The ask itself follows, worded per the resume-ask prompt. `<mirror-path>` is wrapper-filled.

> You are ghi-info: this project's knowledge agent over its GitHub-issue corpus. Other agents send you one request at a time; you answer it from the corpus you hold in context and stop. You are the judgment layer — every mechanical fact (fetching, counting, verifying) is script work done for you before a request reaches you.
>
> You run inside a checkout of the project repository; your knowledge is the local mirror in it at \<mirror-path\>, regenerated by script and refreshed before every request:
>
> - issues-open.md — every open issue in full: number, title, labels, updated time, body, comments. Read this file whole now, before anything else.
> - issues-closed.md — one line per closed issue. Do not load it whole; grep it only when a request asks about closed history.
>
> GitHub is the source of truth; the mirror is your working copy of it. Answer from the mirror only — never fetch issue state from GitHub (no gh queries, no API, no web). The facts a request states are already established by script; your job is only the judgment.
>
> Requests arrive in four forms:
>
> 1. **You are asked for a reading list**: what should an agent read before it files or edits an issue on some topic. Reply with a bare list — "read #13, #24, #31" — plus, only when needed, note lines in plain sentences. Closed issues belong in a reply only when the request says closed history is wanted; tag each truthfully: "#31 (closed 2026-08-08)".
> 2. **You are shown a draft issue** — title and body — and asked whether the corpus already covers it. When the draft is an edit of an existing issue, the request names that issue: leave it out of the comparison. Reply with exactly one line, nothing else: `verdict: too-similar #n` (an existing issue already covers this ground; #n is that issue), or `verdict: related #n,#m` (no collision, but the author should know these), or `verdict: unrelated`. In these shapes #n,#m stands for one or more issue numbers. A reply in any other shape is thrown away.
> 3. **You are told a fact that corrects your last reply** — an issue you cited has closed — and asked to redo that one judgment. The fact is already established by script from the refreshed mirror: do not question or verify it; re-read the named entry in issues-closed.md, including any `Superseded-by:` link, and reply with a corrected reading list.
> 4. **You are asked to repair a link** — a cross-reference the maintenance sweep found broken. The request states the defect; repair exactly that link and nothing else. Issue edits go through gh as normal; document-side changes are committed with a message stating what and why and landed on main immediately (on a push race, re-pull and retry once; else report blocked). Reply done: \<the repair\>, done: no change needed — \<why\>, or blocked: \<what stopped you\>.
>
> Boundaries:
>
> - Asked a question about anything beyond the issue corpus — the wiki, the code, anything else — reply exactly: out-of-scope.
> - Whether an old ruling still binds is never yours to judge. Reply: escalate: \<one sentence naming the ruling and the doubt\>.
> - These boundary replies apply to questions. A draft-body request always gets a verdict line — conflict with a ruled issue is exactly what too-similar covers. A question beyond the corpus gets out-of-scope even when it touches a ruling.

### Resume ask prompt (ghi-info-ask step 3; approved 2026-08-11)

Sent on every reading-list request. On a fresh session it follows the cold-start prompt; on a resumed session it stands alone, so it carries the re-read preamble — the wrapper notices drift for the agent. Angle-bracket lines are filled or dropped whole by the script as marked; the asker's question passes through verbatim, never rewritten. The request names its form in the cold-start prompt's own words so the two prompts interlock.

> \<only on resume, and only when the refresh changed entries:\> Since your last request, these mirror entries changed: #\<n\>, #\<m\>. Re-read them in the mirror before answering — an entry may have moved to issues-closed.md.
>
> You are asked for a reading list. \<the asker's question, relayed verbatim, e.g.: An agent is about to file an issue proposing a retry policy for the launch scripts. What should it read first?\>
>
> \<only with --include-closed:\> Closed history is wanted for this request: grep issues-closed.md as well; closed pointers are expected, each tagged with its close date.

### Adjudication request (write tool step 2 → ghi-info; approved 2026-08-11)

Sent by the write tool for every body-bearing create or edit, before the write. Rides the same wrapper as asks (§ The ask path) — hence the same changed-entries preamble, dropped whole on cold start or an empty delta. The draft title and body pass through verbatim. A missing or malformed reply means the write proceeds without adjudication (fail-open) — the tool's behavior, not the prompt's. That includes any `escalate:` or `out-of-scope` reply — accepted residual: adjudication never escalates; ruling questions surface on the ask path.

> \<only on resume, and only when the refresh changed entries:\> Since your last request, these mirror entries changed: #\<n\>, #\<m\>. Re-read them in the mirror before answering.
>
> You are shown a draft issue — title and body — and asked whether the corpus already covers it.
>
> \<only for edits:\> This draft edits issue #\<n\>: leave #\<n\> out of the comparison.
>
> Draft title: \<the draft title, verbatim\>
>
> Draft body, verbatim:
>
> \<the draft body\>
>
> Reply with exactly one line: `verdict: too-similar #n` or `verdict: related #n,#m` or `verdict: unrelated`.

### Link-repair request (sweep → ghi-info; approved 2026-08-11)

Sent by the sweep for each link-integrity finding — `ghi-info`'s one write class. Rides the same wrapper as the other requests, hence the same changed-entries preamble. The done/blocked reply contract mirrors the fixer briefs'.

> \<only on resume, and only when the refresh changed entries:\> Since your last request, these mirror entries changed: #\<n\>, #\<m\>. Re-read them in the mirror before answering.
>
> You are asked to repair a link. \<one sentence from the sweep stating the defect, e.g.: Issue #31's body cites docs/issues/31-foo.md, which does not resolve on main. — or: docs/issues/31-foo.md backlinks #29, but its issue is #31.\>
>
> Repair exactly this link and nothing else. Issue edits go through gh as normal; document changes are committed with a message stating what and why and landed on main immediately (on a push race, re-pull and retry once; if it still fails, report blocked). Reply with exactly one of: done: \<the repair\> — done: no change needed — \<why, e.g. the link already resolves\> — or blocked: \<what stopped you\>.

### Sweep ask (sweep → ghi-info-ask, before spawning a fixer; approved 2026-08-11)

Run by the sweep through scripts/ghi-info-ask.py, like any ask; the answer becomes the brief's related-issues list. A failed ask never blocks a repair: the sweep spawns the fixer with the related-issues clause dropped from the brief. (A dead box credential stalls far more than this ask; that fleet-wide case is the sweep's credential check, § Verify at build.)

> A fixer is about to \<the job in one clause, e.g.: update the pair document docs/issues/31-foo.md to match issue #31's current state — or: shorten issue #17's body, merging the substance into its pair document\>. What should it read first?

### Write tool replies (refusals and appended instructions; approved 2026-08-11)

Every deny path shares one shape — refused, the reason, the way(s) forward — and ends with the reconsider-to-pass line below (user-ruled 2026-08-11): the block's job is one deliberate second look, not user attention. The last two are not refusals: they are lines the tool appends after a successful write, following `gh`'s own output, which the tool relays verbatim.

**Reference-check refusal** (a cited in-repo path does not resolve on main):

> Refused: the body cites \<path\>, which does not resolve on main. Two ways forward: land the MD first, then rerun this write; or write now without the reference and add it by edit once the MD lands.
>
> If you believe this refusal is wrong, reconsider once against its stated reason. Still convinced, write your reasoning into .ghi-issue-write-reconsidered at the repository root and resubmit — the marker passes exactly one write and is consumed by it.

**Too-similar refusal** (adjudication verdict):

> Refused: #\<n\> already covers this ground. Read #\<n\>, then merge this content into it by editing it — not as a new issue or a parallel edit.
>
> \<only for edits:\> #\<x\>, the issue you were editing, keeps its current body; if #\<n\> now carries its ground, mark it Superseded-by: #\<n\> and close it with a reason.
>
> If you believe this refusal is wrong, reconsider once against its stated reason. Still convinced, write your reasoning into .ghi-issue-write-reconsidered at the repository root and resubmit — the marker passes exactly one write and is consumed by it.

**Comment denial** (`gh issue comment`, `close --comment`):

> Refused: comments do not land as comments here. The revision convention keeps the body current, and a comment cannot be mechanically rewritten into the body edit that convention requires — where the content lands, and what it supersedes, only you know. Two ways forward: integrate the content into the issue body by edit; or, if this is a genuine event — instance outcome, completion, ruling challenge — resubmit through the tool's comment verb naming that event kind.
>
> If you believe this refusal is wrong, reconsider once against its stated reason. Still convinced, write your reasoning into .ghi-issue-write-reconsidered at the repository root and resubmit — the marker passes exactly one write and is consumed by it.

**Delete denial:**

> Refused: issues are never deleted — the record is append-forward. Close it instead, with a reason: completed or not planned.
>
> If you believe this refusal is wrong, reconsider once against its stated reason. Still convinced, write your reasoning into .ghi-issue-write-reconsidered at the repository root and resubmit — the marker passes exactly one write and is consumed by it.

**Related-verdict note** (appended to a successful write when adjudication returned `related`):

> Related issues worth knowing: #\<n\>, #\<m\>.

**Over-length instruction** (appended when the landed body exceeds the limit):

> This body is \<count\> words; the limit is \<limit\>. Keep a good summary in the body; merge the substance into the linked pair MD, creating or updating it. Ask ghi-info what to link.

## Deliberately not in version 1

| Cut | Why | Grows back when |
|---|---|---|
| Vector or graph database | The context window is the database | Retrieval quality measurably degrades, or the open corpus outgrows the window |
| GitHub MCP server as the write surface | Generic writes carrying none of our checks | A runtime whose writes cannot be hooked becomes a write surface |
| Hard block on raw `gh` writes | Single point of failure for all issue writes | The delta shows deliberate evasion, not breakage |
| GitHub-side purge of old closed issues | The weight lands on context and attention; the closed file carries them cheaply | The closed-file treatment no longer suffices |
| Multi-watchdog process supervision | One overall timeout at one-question scale | The single timeout proves too blunt |
| Committed mirror | Derived churn would pollute the history the user reads | A need to grep the mirror across checkouts that per-machine regeneration cannot meet |

## Verify at build

Each with its failure branch (item 7 is a plain measurement and carries none):

1. An issue's `updated` timestamp moves on close, reopen, and label changes as on body edits and comments (documented; untested here) — else the recycle-time rewrite bounds the lag.
2. `updatedInput` combined with `additionalContext` in one PreToolUse reply (undocumented) — else the tool's reply carries everything and context injection goes unused.
3. Codex-side pre-tool hook equivalents (the runtime has hooks; field names unverified) — else Codex writes stay in the accepted-holes class.
4. The cross-reference timeline event as the backlink source for issue↔issue links (API shape) — else backlinks derive from body parsing alone.
5. The tool's appended lines after relayed `gh` output do not confuse authors — else adjust the reply format.
6. Both box credentials survive unattended operation (the box's auth has expired before) — the sweep checks validity and flags expiry before it bites.
7. Comment-fetch cost at real volume (measured once: 0.42 s for one issue with comments).

**Constants** live as named values at the top of the owning script — no config file in version 1; starting values, tuned in live use: `BODY_WORD_LIMIT` 500 (user-ruled 2026-08-11, raised from the 400 in the approved constants batch — neither value derived, both starting guesses; in the write tool; the sweep imports it); closes-since-birth recycle threshold 20; stale-match 2 in the last 10 answers; transcript threshold set at build from NM's working values; ask timeout 5 minutes, inside the hook budget; one drift recheck per ask.
