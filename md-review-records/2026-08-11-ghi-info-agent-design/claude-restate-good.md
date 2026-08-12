<!-- provenance: runtime=claude model=claude-opus-5 effort=high cell=restate tier=good target=/Users/el/Projects/nedschorus/.claude/worktrees/linters-tool-usage-f8b0a0/docs/drafts/ghi-info-agent-design.md -->

## Frontmatter

1. **`status:`** — This document is at the stage where the separate pieces of the design have been merged into a single coherent whole ("integrated design"); the substantive choices it records were decided by the user on 2026-08-07 during a step-by-step review session over the earlier plan document (a "plan walk"); further corrections that came out of running the project's `md-review` procedure on this document were decided by the user on 2026-08-09; and the document is now waiting for the user to conduct one more step-by-step review session, this time over the integrated document itself.
2. **`design-as-of:`** — skipped (a date).

## Title line

1. The document's subject is a thing named `ghi-info`, described as the agent that holds knowledge about GHIs (GitHub issues), and the document itself is the design document for that agent — as opposed to a plan, a spec, or the built artifact.

## Walk order — integration walk (opened 2026-08-09, new-vp session 3a11d08f; this block is removed when the walk closes)

1. **Heading.** This section lists the sequence in which the document's parts will be presented to the user for the integration review session; that session was started on 2026-08-09 by an agent session identified as `new-vp session 3a11d08f`; and the whole section is scaffolding — when the review session finishes, this section gets deleted from the document rather than kept as a record.
2. **Item 1, title.** The first thing reviewed was the central body of material that had already been presented in the earlier plan review, checked this time as a single unit rather than piecewise; the listed contents of that unit are: what `ghi-info` is, the three jobs it does, the shape of the answers it gives, where it physically runs, how the local copy of the issues is structured, the stance of not putting a mandatory checkpoint in front of writes, and the three-tier arrangement of skill/hook-plus-tool/CLAUDE.md.
3. **Item 1, annotation (a).** This item was reviewed on 2026-08-09 and the user confirmed it, doing so across six separate exchanges or chunks.
4. **Item 1, annotation (b).** A secondary decision attached to that confirmation ("rider") was also made: a rule about the failure mode of specifying things in too much detail belongs in the checklist used when authoring skills, specifically in that checklist's section named "Register", and it does not belong in the project's CLAUDE.md file; that placement was carried out on the same day, 2026-08-09.
5. **Item 1, annotation (c).** Nothing in this design document results in any change to CLAUDE.md.
6. **Item 2, title.** The second thing reviewed was the mechanism by which issues get written, comprising: the hook that rewrites a raw command into a call to the project's write tool, the four steps the write tool performs, the handling of comments/closing/deleting, the fact that the block is soft plus its override mechanism, and the gaps in coverage that are knowingly left open.
7. **Item 2, annotation (a).** Reviewed on 2026-08-09; the user approved it across three exchanges; and during that review an observation about the soft block was written down: reviewers of code habitually and automatically argue that a soft block should be made into a hard one, so to protect against that, the decision has been written in the specific textual pattern used for "Accepted residual" notes — a pattern chosen because it can be found with grep — and there is an existing standing rule (my reading: a project rule that pairs each accepted-residual note with a matching instruction to reviewers) that shields such notes, meaning a reviewer may only raise the issue again if they have evidence that matches the specific reopening condition stated in the note, and may never raise it as a routine review comment.
8. **Item 2, annotation (b).** Additional questions that came up during that review were also decided: (i) changes to an issue's state that don't go through the write tool still get into the local mirror via the ordinary incremental refresh, with the full rewrite at session recycle as a second line of defense; and (ii) new fields in the mirror only appear when someone deliberately edits one line of the refresh script to add them — the script never starts emitting new fields on its own.
9. **Item 3, title.** The third thing reviewed was the path by which an agent asks `ghi-info` a question, comprising: the steps performed by the wrapper script, the notice sent when the agent's answer is out of date plus the one re-ask, the `--include-closed` option, how simultaneous asks are handled by spinning up disposable sessions, and the ordered list of fallbacks when the ask fails.
10. **Item 3, annotation (a).** Reviewed on 2026-08-09 and approved by the user across two exchanges.
11. **Item 3, annotation (b).** As part of that approval, the wording of the drift notice was changed to remove an ambiguity: the statement that an issue is closed is a fact the script owns, derived from the mirror that was just refreshed, so the notice's job is to hand that fact to the agent and ask it only to redo its judgment using the mirror files; the agent is not being asked to check with GitHub, and never contacts GitHub to confirm state.
12. **Item 4, title.** The fourth thing reviewed was how a `ghi-info` session lives and how its knowledge is kept current: the session's lifecycle, the conditions that cause a session to be thrown away and restarted, the two different rates at which the mirror is refreshed, the notion of how fresh an issue is, and the `Superseded-by` marker.
13. **Item 4, annotation.** Reviewed on 2026-08-09 and approved by the user.
14. **Item 5, title.** The fifth thing reviewed was upkeep: the periodic scanning script, the single-purpose repair agents it launches, what happens when a repair can't be done, and the still-undecided question of which model to use for which role.
15. **Item 5, annotation (a).** Reviewed on 2026-08-11 and approved by the user, by way of a session spent drafting the briefs given to fixer agents plus a session in which the material was explained to (or as if to) a reader with no prior context.
16. **Item 5, annotation (b).** Decision: the one fixer brief that had existed was divided into two separate templates, one for each type of problem; the sweep script chooses which template to use; and any one brief instructs the fixer on exactly one task.
17. **Item 5, annotation (c).** Decision: the sweep runs `scripts/ghi-info-ask.py` in advance and pastes the resulting list of issues to read directly into the brief, so the fixer agent itself never calls any tool to get that list.
18. **Item 5, annotation (d).** Decision: the instruction wording "do only the job stated above" replaces the previous wording "smallest change".
19. **Item 5, annotation (e).** Decision: every prompt in this design must be written so that an agent with no background knowledge can act on it.
20. **Item 5, annotation (f).** Decision: the constant `BODY_WORD_LIMIT` starts at 500, and the line of the document listing constants was updated accordingly.
21. **Item 5, annotation (g).** Decision: the check for a pair document lagging its issue is performed in only one direction — the case where the issue is newer than the document — and the resulting uncovered case (a citation that was supposed to be added but never was) is written down as a knowingly accepted gap in the § Maintenance and fixers section.
22. **Item 5, annotation (h).** Decision: when an issue body is too long, any text that has been ruled on is transferred word-for-word into the pair document, with the shortened body summary pointing at where it now lives; what is forbidden is rewording it — and this rule applies to the second fixer template (Template B).
23. **Item 5, annotation (i).** Decision: every prompt that this design relies on must appear in full, exactly as it will be used, in the section titled "Prompts"; that section is itself subject to a separate `md-review` pass, which must happen before this document's `status` can be marked done; and at the time this note was written, four prompts were still missing from that section.
24. **Item 6, title.** The sixth item is wrapping up: deciding where this document will finally live, the GitHub issue that will track building the thing, and the follow-up items carried forward — resuming the review of the `ghi-write` skill, reviewing the correctness rule, and revising issue #26's lifecycle content.
25. **Item 6, annotation (a).** This item was still open as of 2026-08-11, and the user approved the following order for finishing: write the four missing § Prompts entries one at a time, then run `md-review` on that section, then decide where the document lands — with a recommendation already proposed, that this document become the pair document of the GitHub issue tracking the build — then create that build issue, then add the follow-up items to the queue.
26. **Item 6, annotation (b).** The prompt-writing step is currently underway, and the per-prompt status is tracked by labelling each prompt in § Prompts as either still owed or final, rather than by any separate tracker.

## (untitled preamble, lines 23–25)

1. **Line 23, sentence 1.** This document describes the whole arrangement by which agents in the nedschorus project deal with GitHub issues, and that arrangement has four parts: `ghi-info`, an agent that persists over time and holds knowledge of the entire body of issues; a local copy of the issues kept up to date by scripts; a write mechanism in which a hook intercepts direct issue-writing commands and redirects them through the project's own write tool; and a skill named `ghi-write` that carries the decisions requiring judgment, which no script or hook can make.
2. **Line 23, sentence 2.** For the rest of this document, whenever the term "GHI author" appears, it means whatever agent happens to be creating or modifying an issue at that moment (not a person, and not a specific named agent).
3. **Line 23, sentence 3.** The record of how these decisions were reached is in two places — `ghi-info-agent-plan-draft.md`, which holds the item-by-item decisions from 2026-08-07, and the dispositions file from the 2026-08-09 md-review of this design — and the alternative approach that was considered and rejected, in which a single mandatory checkpoint would guard everything, is kept for reference in `ghi-gatekeeper-plan-draft.md`.
4. **Line 25, sentence 1.** The core concept: rather than constructing a specialized search index over the issues (either an embedding-based one or a graph one), the approach is to hand the issues to a current-generation language model agent, which works because the whole body of issues is small enough to fit in that model's context window — measured on the day of writing at 45 issues totalling about 109 kilobytes.
5. **Line 25, sentence 2.** Anything that a script can do — retrieving data, formatting it, counting things, selecting subsets — is done by scripts, so that the (paid, slow) model turns of `ghi-info` are used exclusively for decisions that require judgment.

## What ghi-info is

1. `ghi-info` is the first concrete instance of a category of agent — an agent that knows one subject area — which was defined in the document `26-dynamic-agent-team-model.md`, and in that document's enumeration of subject areas, "the GHIs" is the first one named.
2. It has three responsibilities (introduced by "Three duties:").
3. **Duty 1 heading and body, sentence 1.** Answering questions: an agent that is about to create or modify an issue asks `ghi-info` which existing issues it ought to read first.
4. **Duty 1, sentence 2.** The response is nothing but a list of issue numbers, with the illustrative example "read #13, #24, #31" — no explanation or prose around it.
5. **Duty 2 heading and body, sentence 1.** Upkeep: `ghi-info` looks after two things — the references issues make to one another, and whether references crossing between issues and Markdown documents work in both directions, meaning both that every link from an issue to a repository Markdown file points at a file that actually exists on the main branch, and that every Markdown document paired with an issue contains a back-reference to the right issue or issues.
6. **Duty 2, sentence 2.** Fixing broken links is the one and only category of change `ghi-info` itself makes to anything.
7. **Duty 2, sentence 3.** Other kinds of problem it notices — a paired Markdown document that hasn't been updated since its issue changed, or an issue body longer than the allowed word count — are not fixed by `ghi-info`; instead a separate repair agent is created for each, as described in the § Maintenance and fixers section.
8. **Duty 3 heading and body, sentence 1.** Deciding on writes: when the write tool is about to write an issue, it sends `ghi-info` the full text of the proposed body, and additionally — when the write is a modification of an existing issue — the number of the issue being modified, so that `ghi-info` can exclude that issue when looking for overlaps (otherwise an edit would always look identical to itself).
9. **Duty 3, sentence 2.** `ghi-info` answers with a single line in one of three literal forms: `verdict: too-similar #n`, `verdict: related #n,#m`, or `verdict: unrelated`.
10. **Duty 3, sentence 3.** If the reply does not conform to that shape, the tool behaves exactly as if `ghi-info` had not responded at all, and "fail-open" means the write is allowed to proceed rather than being blocked.
11. **Duty 3, sentence 4.** The tool turns that verdict into a message for the authoring agent, in three cases: (i) for **too-similar** — which covers an existing issue being a duplicate, partially overlapping, or contradicting the draft — the write is rejected and the author is told to read issue #n and then fold this content into #n by editing #n; (ii) for **related but compatible**, the write goes ahead and the message additionally lists the issues the author ought to acquaint itself with; (iii) for **unrelated**, the author just gets an ordinary success message with nothing added.
12. **Out-of-scope sentence, clause 1.** Things `ghi-info` does not do: deciding what form a piece of information should take — a queue note, a GitHub issue, an issue-plus-document pair, or a standalone Markdown file — because that decision belongs to the `ghi-write` skill's judgment, and the definitions of those four categories are in the founding plan document's "Project organization" section.
13. **Out-of-scope, clause 2.** It also does not write the actual content of issues or Markdown documents.
14. **Out-of-scope, clause 3.** It also does not deal with anything outside the body of issues: if asked about the project wiki or the source code, it responds with a single fixed reply, the literal string `out-of-scope`.
15. **Out-of-scope, last sentence.** The question of whether a decision made in the past is still in force is never answered by `ghi-info`; it is invariably referred up to the user.

## The GHI mirror (ghi-mirror)

1. The mirror is a directory called `ghi-mirror` at the top of a checkout, excluded from git tracking, and it can be recreated from scratch on any machine by running `scripts/ghi-mirror-refresh.py`.
2. The copy that matters — the one treated as the working one — is the one inside the checkout that `ghi-info` uses on the Ubuntu machine.
3. GitHub holds the real data; the mirror is a generated artifact, so any disagreement is resolved in GitHub's favor and losing the mirror costs nothing but regeneration time.
4. The mirror contains two files, divided according to whether an issue is open or closed: `issues-open.md` holds each open issue with almost no processing applied — its number, its title, its labels, when it was last changed, its body text, and its comments — while `issues-closed.md` holds a single line per closed issue containing its number, its title, why it was closed, and the date it was closed.
5. Ordinary checks for whether some issue is related to something search only the open-issues file; the closed-issues file is searched additionally in two situations — when someone wants to assert that nothing in the corpus covers a topic (and such an assertion is not considered supported unless both files were searched), or when someone is deliberately looking for a prior case.
6. **Refresh cadence, sentence 1.** On each ask, only the changes are pulled in: a single GitHub query using `updated:>` with the timestamp of the most recently updated entry in the mirror, which re-downloads the issues that changed; entries are moved from one file to the other if an issue opened or closed; and comments are downloaded only for the issues that changed, at the cost of one API call per such issue.
7. **Sentence 2.** Whenever a `ghi-info` session is discarded and restarted, the mirror is not updated incrementally but rebuilt completely from a full download, so the things an incremental update structurally cannot detect — an issue that was deleted, or an issue missed because its change landed in the same second as the timestamp boundary — get cleaned up at that moment, which means the maximum time such an error can persist is one recycle interval.
8. **Sentence 3.** The mirror files are written to a temporary file and then renamed into place, so if two refreshes run at the same time neither can leave a half-written file behind.
9. **Sentence 4.** Measurements taken on 2026-08-07 against the actual repository: downloading all 45 issues including their bodies took 0.82 seconds, and the `updated:>` query returned precisely the set of issues modified after the given timestamp — no more, no fewer.
10. **The second feed.** The refresh script also does a `git fetch` from origin and reads the commit log of `origin/main`, because editing a Markdown document paired with an issue does not change that issue's "last updated" time, and such documents count as part of the knowledge corpus from the moment their changes are merged into main.
11. **Currency, sentence 1.** Every mirror entry records both when the issue was last modified and a measure of how stale it is expressed relative to project activity — that is, how much has happened in the project since this issue last changed — because the intended measure of aging is how much work has gone by, not how many days have gone by.
12. **Sentence 2.** When one issue replaces another, that is recorded by putting the exact text `Superseded-by: #<n>` into the issue, and it is written at the time the change happens by whichever author knows about the replacement — not inferred later.
13. **Sentence 3.** The sweep script searches for that marker text and checks that the issue it points to exists (my reading of "verifies its targets"); finding pairs of issues covering the same ground where nobody wrote such a marker is a matter of judging similarity, which is `ghi-info`'s job rather than a script's, and the adjudication that happens at write time is what catches newly created same-ground pairs — with the implication left as-is that pre-existing unmarked pairs are not systematically hunted down.

## The ghi-info session

1. **Seat.** `ghi-info` runs on the Ubuntu machine, in the directory `~/agents/ghi-info`, following the standard layout for agents on that machine documented in nedschorus issue #45; and the state the wrapper script keeps — the identifier of the stored session, plus the counters used for recycle decisions — is stored in that same place.
2. Callers running on the Mac invoke it remotely over SSH using `scripts/launch-claude`, which is documented in that same issue #45.
3. **Lifecycle, sentence 1.** A `ghi-info` process exists only while it is actually answering something; the rest of the time no process is running, and what survives between turns is only a session identifier, the recorded transcript, and the mirror files.
4. **Sentence 2.** There is no notion of a session sitting idle and ready for this category of agent — it is either working or gone.
5. **Context, sentence 1.** When a session starts fresh it reads the whole `issues-open.md` file into context, whereas closed issues only enter a turn's context if something greps them in during that turn.
6. **Sentence 2.** In a session that is resumed rather than started fresh, what the agent believes gradually diverges from reality: the mirror files are re-refreshed before every turn, but issue text that was read into context on an earlier turn stays in context in its old form, and the agent has no dependable way to detect this on its own — so the wrapper script detects it on the agent's behalf, as described in § The ask path.
7. **Sentence 3.** A session is discarded and a fresh one started as soon as any one of three conditions is met, each of which a script can check without model help: how many issues have closed since this session began, the rate at which its answers have turned out to reference stale state, and how large the transcript has grown.
8. **Sentence 4.** The thresholds are deliberately set so that sessions are recycled sooner rather than later, because recycling too early only costs one inexpensive reload of the corpus, whereas recycling too late produces answers that are wrong without anyone noticing.

## The ask path (ghi-info-ask)

1. The entry point is the script `scripts/ghi-info-ask.py`, which any agent may run, and which the `ghi-write` skill runs as the first thing it does.
2. The consultation that the write tool performs to get a similarity verdict goes through this same script rather than a separate one — a decision the user made on 2026-08-11 — meaning there is a single stored session, a single implementation of "refresh the mirror and resume the session", and the only difference between the two use cases is which of two request formats is sent.
3. The steps follow in the stated order.
4. **Step 1.** Perform an incremental mirror refresh.
5. **Step 2, sentence 1.** Resume the previously stored session; if there is no stored session, or if one of the recycle conditions has been met, start a fresh session instead.
6. **Step 2, sentence 2.** If a different ask is already using the stored session at that moment, do not queue behind it — instead start a brand-new session that will be discarded afterwards, so that no caller ever waits and no two callers write into the same transcript.
7. **Step 3, sentence 1.** Send the prompt, consisting of the question being asked, and — only in the case of a resumed session — the numbers of the issues that the refresh just changed, together with an instruction to re-read those issues' entries from the mirror files before formulating an answer.
8. **Step 3, sentence 2.** Passing `--include-closed` signals that the caller intentionally wants closed history considered — for finding precedent, or for establishing that nothing covers a topic — with two consequences: `ghi-info` searches the closed-issues file, and closed issue numbers appearing in the answer are treated as intended rather than as errors.
9. **Step 4, sentence 1.** After the answer comes back, every issue number in it is checked against the mirror; this is done entirely by the script, and the resulting determination of an issue's state is always the script's, never something the agent asserts.
10. **Step 4, sentence 2.** If the answer contains a closed issue that was not expected (i.e. `--include-closed` was not given), the script sends exactly one "drift notice" back to `ghi-info`, which supplies the established fact and requests only that the agent redo its judgment; the notice's text is the quoted sentence: "#31 closed on \<date\> — the mirror is current; re-read its entry in `issues-closed.md`, including any `Superseded-by:` link, and give a corrected reading list."
11. **Step 4, sentence 3.** At most one such re-ask happens per ask, and in performing it the agent consults only the mirror files and does not contact GitHub.
12. **Step 4, sentence 4.** Whatever issue numbers survive this process are given to the caller with accurate annotations attached — the example being "#31 (closed 2026-08-08)" — and any explanatory notes accompanying the list are written as ordinary prose sentences rather than in some structured format.
13. **Step 4, sentence 5.** A closed issue that was not expected increments the counter feeding the stale-match recycle condition; a closed issue that was expected (because `--include-closed` was passed) does not.
14. **Step 5.** Output the list of issue numbers.
15. **Timeout sentence.** There is a single timeout covering the whole operation, chosen to fit within the time the hook system allows; and if the run is terminated by that timeout, it is reported as a specific, named kind of failure rather than as an empty or ambiguous result.
16. **Auth sentence.** Authentication relies on the two credentials stored on the Ubuntu machine — the `gh` CLI login belonging to that machine and a long-lived Claude API token — the token being long-lived because credentials obtained through an interactive login flow would expire while nobody is present to renew them.
17. **Precedent sentence.** This overall pattern is already running in production in the nedsmessenger project, specifically in `~/Projects/nedsmessenger/adapter/adapter.py` in the function `ask_claude`, which runs `claude -p --resume` non-interactively and takes the answer from the process's output stream; nedsmessenger uses three separate watchdog mechanisms, whereas the first version of this design starts with just the one timeout.
18. **Fallback ladder, sentence 1 (bolded).** If asking `ghi-info` fails, that failure never causes a write to be prevented.
19. **Sentence 2.** The ordered fallbacks are: first try the ask; if that fails, grep the local mirror files directly (accepting that they may be out of date if the refresh didn't run); if that fails, use `gh` to search GitHub; and if that fails, just go ahead under the ordinary governing rules, namely the `ghi-write` skill and the project's artifact-lifecycle rule.
20. **Sentence 3.** The self-correcting behavior: if an issue author notices a relationship that `ghi-info` failed to report, the author adds the cross-reference as part of the edit it was already making; the next mirror refresh brings that cross-reference into the corpus; and `ghi-info`'s answers start reflecting it once the corpus is next loaded into a session — so the delay before the correction takes effect is at most one recycle interval.

## The GHI write path (ghi-issue-write)

1. Agents that author issues use the `gh` command line the way they have been trained to for creating, editing, and closing issues; commenting is the single case where they are explicitly taught to do something different from their default behavior.
2. **Sentence 2.** A hook of type PreToolUse, implemented at `.claude/hooks/ghi-issue-write-redirect.py` and placed alongside the existing `.claude/hooks/instruction-file-guard.py`, transforms any `gh issue create` or `gh issue edit` command that carries a body into an invocation of `scripts/ghi-issue-write.py`, doing so via the hook system's `updatedInput` field; and both that rewriting mechanism and the fact that command-type hooks have a 600-second timeout that can be configured were checked against the official hooks documentation on 2026-08-07.
3. **Sentence 3.** When the write tool itself runs `gh`, those runs are child processes started beneath the level at which the hook operates, so they are not themselves intercepted and rewritten; and writes made by `ghi-info` and by fixer agents go through the write tool exactly like any other author's writes, with no exemption.
4. **Sequence introduction.** The tool performs these steps for each write.
5. **Step 1, sentence 1.** Reference check: any path to a file inside this repository that the issue body mentions must actually exist on the main branch.
6. **Step 1, sentence 2.** If a cited path does not exist, the write is rejected and the rejection message states both available options: merge the Markdown file to main first, or file the issue now leaving the reference out and add it later with an edit once the file has landed.
7. **Step 1, sentence 3.** There is no requirement that an issue cite a Markdown document at all; the check only responds to what the body happens to cite, and cites nothing itself.
8. **Step 2.** Similarity adjudication, as described in § What ghi-info is, with the issue being edited excluded from consideration; and it fails open — if `ghi-info` can't be reached, the write goes ahead with no similarity check, while the script-based checks (reference and length) still run.
9. **Step 3.** The actual write, performed by the tool calling `gh` internally; the tool passes through `gh`'s own output word for word and then adds its own lines afterward, below it.
10. **Step 4, sentence 1.** Measuring the body's length — with the explicit point that no authoring agent is ever asked to count words itself.
11. **Step 4, sentence 2.** If the body exceeds the limit, the reply tells the author to leave a good summary in the issue body and move the detailed content into the Markdown document paired with that issue, creating that document if it doesn't exist yet or updating it if it does.
12. **Step 4, sentence 3.** The author performs this split rather than a script or fixer, because the author is the one who already has the relevant material in mind; and to find out which documents to link to, the author asks `ghi-info`.
13. **Accepted residual line.** A knowingly accepted imperfection: between the moment `ghi-info` gives its verdict and the moment the write actually happens, the issue in question could be changed by someone else, making the verdict out of date.
14. **Comments, sentence 1.** The commands `gh issue comment` and `gh issue close --comment` are both refused, and the refusal message is written to teach rather than merely block: the reason is that no script can automatically convert a comment into the edit to the issue body that the project's revision convention (defined in the founding plan's "Project organization" section) calls for, because deciding where in the body the content belongs and which existing text it replaces requires knowledge only the author has.
15. **Sentence 2.** The refusal names both legitimate routes: fold the content into the body by editing the issue, or submit it again using the write tool's own comment operation while declaring which kind of event it records, chosen from a closed list containing "instance outcome", "completion", and "ruling challenge" — with the list only expandable by an explicit user decision, and with the separate question of whether "completion" is redundant with closing an issue with a completion reason postponed to the `ghi-write` review session.
16. **Sentence 3.** Each time an agent attempts a comment and is refused, one agent turn is wasted, and that cost is accepted.
17. **Close sentence.** Closing an issue is treated as a change of state that carries a reason, either "completed" or "not planned"; the plain `gh issue close` and `gh issue reopen` commands are not intercepted by the hook at all, and the incremental refresh picks up the resulting changes.
18. **Non-body edits sentence.** Edits that change only labels, only the title, or only milestones are allowed straight through, with the knowingly accepted consequence that renaming an issue could make it stop looking like a duplicate of another one.
19. **Delete sentence.** Deleting an issue is refused, with closing offered instead, on the principle that the record is only ever added to and never rewritten backwards; and the delete refusal includes the same override mechanism that every other refusal includes.
20. **Soft block, sentence 1.** Every path that refuses something offers the same escape hatch: a single-use override that is recorded in an audit log, following the pattern already implemented and running on main in `.claude/hooks/instruction-file-guard.py`.
21. **Sentence 2 (bolded lead-in and body).** A knowingly accepted imperfection, decided by the user on 2026-08-07 and reaffirmed on 2026-08-09: the block is soft rather than absolute, and the ways around it that come from only enumerating specific commands are deliberately left unclosed — `gh api`, MCP-provided tools, and writing the command in an unusual form — because of the stance called "the cooperative posture", meaning the enforcement exists to catch honest errors and is not trying to stop an agent that is deliberately circumventing it; and that stance is the same one taken in the git-gatekeeper design document's section "The credential and enforcement".
22. **Sentence 3.** Reviewers are permitted to raise this decision again only if they have evidence matching the specific condition stated for reopening it, which is: the audit log of overrides showing that overrides are being used to avoid the tool rather than to get past a genuine malfunction.
23. **Sentence 4.** Writes that bypass the tool are nonetheless visible in the incremental refresh, and the maintenance sweep detects the resulting problems (over-length bodies, broken links) even though it did not intercept the write.
24. **Codex sentence.** Codex is included as the other runtime intended to be used alongside Claude; until it has been verified during the build that Codex offers an equivalent hook mechanism, writes performed from Codex fall into the same category as the other knowingly accepted gaps, with the `ghi-write` skill serving as the only layer standing in front of them.

## Maintenance and fixers

1. The sweep is performed by scripts and draws on both sources of change (the issue delta and the git log of main); it does three things: checks the length of bodies that have changed, searches for `Superseded-by:` markers, and checks link integrity in both directions — where for the Markdown side it reads the actual files in the repository checkout rather than anything in the mirror.
2. **Sentence 2.** Each problem the sweep finds causes a single-purpose, single-use repair agent to be created — the category of agent defined in `26-dynamic-agent-team-model.md`, started using the mechanism described in nedschorus issue #41 — and each is given a narrowly scoped instruction, the example given being "issue #31 moved on \<date\>; its pair MD has not: update the MD."
3. **Sentence 3.** These fixer agents write through the same write path as everyone else and query `ghi-info` the same way any issue-authoring agent does.
4. **Sentence 4.** `ghi-info` itself only ever fixes links; it never changes the content of an issue or document.
5. **Sentence 5.** The check for a document/issue pair being out of sync only looks for one of the two possible mismatches: the issue changed and the paired document did not.
6. **Sentence 6.** The opposite mismatch — the document has been merged to main while the issue has not changed since — is intentionally not checked for, a decision made by the user on 2026-08-11, for two reasons: having the document ahead of the issue is the ordinary halfway state of the prescribed sequence (write the document, land it, then cite it from the issue), and the issue body is only a summary, so many document edits legitimately have no effect on it.
7. **Sentence 7 (bolded lead-in and body).** Knowingly accepted imperfection: if an author lands the Markdown document but then never performs the step of adding the citation to the issue, this sweep does not detect it — and neither does the link-integrity check, because a link that was never written cannot be found broken (nothing exists to fail to resolve).
8. **Sentence 8.** If a fixer cannot complete its repair, it reports that upward by filing exactly one issue labelled `draft` that states what prevented it.
9. **Sentence 9.** Which language model and which runtime is best suited to each of the roles — `ghi-info` itself, the fixers, and the adjudication call; Claude versus Codex; and among Claude's models fable versus opus versus sonnet — is not decided here and will be determined by trying them out.

## The three-layer stack

1. **Layer 1.** The `ghi-write` skill — a skill, currently being built, whose review is underway over the document `ghi-write-skill-draft.md` — activates when an issue-authoring agent is on the point of creating or editing an issue, and puts the correct behaviors in front of the agent before it acts: query `ghi-info` first; choose the destination according to the situation; modify an existing issue instead of creating a near-duplicate; keep what you write short; and follow the document-issue sequence of writing the Markdown, merging it, and only then referencing it from the issue.
2. **Layer 2, sentence 1.** The hook together with the write tool serves as the safety net for correctness in the case where the skill does not activate.
3. **Layer 2, sentence 2 (same sentence, second half).** Given that the write in question is one the hook covers and that `ghi-info` is responding, a failure of the skill to activate costs only efficiency rather than correctness — the duplicate gets caught later at merge time instead of before writing, and one attempt to comment has to be retried.
4. **Layer 2, sentence 3.** The window during which fail-open lets an unadjudicated write through, and the command forms the hook does not enumerate, are the knowingly accepted imperfections of this layer, and both leave traces that show up in the incremental refresh.
5. **Layer 3.** CLAUDE.md serves only as background documentation that agents may or may not act on, and nedschorus issue #13 is cited as this project's own documented case of a convention that was written down but lost out to what the model had been trained to do.

## Division of labor

*(The table's three columns are the piece of work, who or what performs it, and what it costs; each row restated as one proposition.)*

1. Retrieving issues, formatting them, merging in incremental changes, and separating open from closed is done by `ghi-mirror-refresh.py`, and costs nothing (my reading: no model calls, hence no tokens or money).
2. Checking that cited paths resolve and measuring body length is done by `ghi-issue-write.py`, at no cost.
3. Computing the freshness figures, scanning for `Superseded-by:` markers, and scanning link integrity is done by the sweep scripts, at no cost.
4. Verifying the issue numbers in an answer and issuing the drift notice is done by `ghi-info-ask.py` at no cost, with the qualification that if a recheck is actually triggered it consumes one model call from `ghi-info`.
5. Judging which issues are relevant to a given question, and judging whether a draft is too similar to an existing issue, is done by `ghi-info`, and each such judgment costs one model call.
6. Fixing cross-references is done by `ghi-info`, and this constitutes the single category of writing it performs.
7. Choosing where content should go, writing the actual substance of an issue body, and performing the split of an over-long body into summary-plus-document is done by the agent authoring the issue, guided by the `ghi-write` skill, and costs nothing extra because that agent already has the material in its context.
8. Repairing documents that lag their issues and bodies that exceed the length limit, in the cases the sweep discovers, is done by purpose-created fixer agents, at a cost of one single-use agent per repair.

## Prompts

1. **Sentence 1.** Every prompt that this design relies on is written out here in its exact final wording, per user decisions on 2026-08-09 and 2026-08-11, on the reasoning that a prompt described only in summary form cannot be implemented from the document and cannot be reviewed.
2. **Sentence 2.** Each of these prompts is written to be actionable by an agent that has no prior knowledge of the project.
3. **Sentence 3.** This section must go through its own `md-review` pass before this document's `status` field can be changed to indicate completion.
4. **Sentence 4.** Wherever text in angle brackets appears inside a prompt, it is a placeholder that the script sending the prompt substitutes real text into; the agent receiving the prompt never sees an unfilled placeholder and is never expected to fill one in itself.
5. **Status paragraph, sentence 1 (bolded lead-in).** All the prompts listed here are now in their final form, and the complete list is: the two fixer briefs, the drift notice, the cold-start prompt with its four kinds of request, the resume-time ask prompt, the adjudication request, the link-repair request — this last one having been written out here on 2026-08-11 by the user's decision rather than being left to be invented during implementation — and the messages the write tool emits.
6. **Sentence 2.** The section has not yet had its `md-review`, which must happen before the document's `status` can be closed.

## Fixer brief — pair document behind its issue (approved 2026-08-11)

1. **Preamble.** The sweep script supplies the text for every angle-bracket placeholder in this brief, including the list of issues to read, which it obtains by running `ghi-info-ask.py` itself before it creates the fixer — so the fixer agent never calls any tool to obtain it.
2. **Prompt ¶1, sentence 1.** The agent is told its role: it is a fixer, meaning a single-use agent brought into existence because an automated maintenance check discovered that a Markdown document paired with a GitHub issue in this project has fallen out of date relative to that issue.
3. **¶1, sentence 2.** The agent is told the entirety of its purpose is to bring the one named document up to date and then finish — it should not look for other work.
4. **¶2, sentence 1 ("Job").** The concrete task: issue number \<n\> was changed on \<date\>, while its paired document at path \<path\> has not been modified since \<date\> (a second, earlier date).
5. **¶2, sentence 2.** The instruction: revise the document so that it reflects what the issue now says.
6. **¶3 ("Read first").** Before doing anything, read three things: the issue itself, the paired document at \<path\>, and the additional related issues listed — that list being what `ghi-info` returned when the sweep asked it on the fixer's behalf, illustrated as "#13, #24".
7. **Rules, item 1, sentence 1.** The only file the agent may modify is the paired document, and the change must be committed on the agent's own branch with a commit message that says both what was changed and why.
8. **Rules, item 1, sentence 2.** The agent must not make any change to any GitHub issue.
9. **Rules, item 2.** The agent is to do exactly the task described above and nothing more.
10. **Blocked condition, lead-in.** In the following situations the agent must not make an edit at all; instead it must halt and report that it is blocked.
11. **Blocked condition 1.** If making the change would modify text that is marked as having been decided — with the markers listed as the strings "user-ruled", "boss-ruled", "Accepted residual", or a decision with a date attached — or if making the change would require picking one of two such decided statements over the other.
12. **Blocked condition 2.** If the issue and the document say things that contradict each other, and nothing in the written record settles which is right.
13. **Blocked condition 3.** If the agent is not confident the change it would make is the correct one.
14. **Final-message rule, lead-in.** The agent's last output must be exactly one of the two forms below and nothing else.
15. **Form 1.** The literal word `done:` followed by a description of what was changed, specifically which files.
16. **Form 2.** The literal word `blocked:` followed by a description of what prevented completion, which must include a direct quotation of the text that caused the problem.

## Fixer brief — issue body over the length limit (approved 2026-08-11)

1. **Preamble, sentence 1.** The same arrangement applies as for the previous brief: the sweep fills in all the placeholders itself.
2. **Preamble, sentence 2.** The way this brief handles decided text is the exception introduced by the user's 2026-08-11 decision permitting a verbatim move: text that has been ruled on may be relocated to a different place, but its wording may never be altered.
3. **Prompt ¶1, sentence 1.** The agent is told it is a fixer — a single-use agent created because an automated maintenance check found that one issue body in this project has become longer than the permitted limit.
4. **¶1, sentence 2.** Its entire purpose is to shorten that one body and then finish.
5. **¶2, sentence 1 ("Job").** The specifics: issue #\<n\>'s body currently contains \<count\> words, against a limit of \<limit\>.
6. **¶2, sentence 2.** The instruction: leave behind a summary in the body that is genuinely good (not a stub), and move the detailed content into that issue's paired document at \<path\>, creating that document if it does not yet exist.
7. **¶3 ("Read first").** Read first: the issue; its paired document at \<path\>, with the explicit warning that this file may not exist yet; and the related issues listed, which is the list `ghi-info` returned when the sweep asked on the fixer's behalf.
8. **Rules, item 1, sentence 1.** Changing the issue body is done through `gh` in the usual way (with the implication that the hook will redirect it through the write tool as it does for anyone).
9. **Rules, item 1, sentence 2.** Changes to the document are committed on the agent's own branch with a commit message stating what changed and why.
10. **Rules, item 2.** Nothing taken out of the issue body may simply disappear: every removed piece must end up in the paired document.
11. **Rules, item 3.** Text carrying one of the decided-text markers ("user-ruled", "boss-ruled", "Accepted residual", or a dated decision) may only be relocated exactly as written — copy it into the paired document letter for letter, and make the summary that remains in the body point to where it has gone.
12. **Rules, item 4.** Do only the task described above.
13. **Blocked condition, lead-in.** In the following situations, halt and report blocked rather than editing.
14. **Blocked condition 1.** If the change would involve rewording decided text — and the parenthetical makes explicit that moving such text unchanged, which rule 3 permits, is the only thing the agent is allowed to do with it — or if it would require choosing between two such decided statements.
15. **Blocked condition 2.** If the issue and the document contradict each other in a way the record does not settle.
16. **Blocked condition 3.** If the agent is not sure the change is right.
17. **Final-message rule, lead-in.** The final output must be exactly one of two forms.
18. **Form 1.** The literal `done:` followed by what changed, listing both the files touched and the issue numbers touched.
19. **Form 2.** The literal `blocked:` followed by what stopped the agent, quoting the problematic text.

## Drift notice (ghi-info-ask post-check → ghi-info; final, worded 2026-08-09 in § The ask path)

1. **Heading gloss.** This is the message the ask script's verification step sends back to `ghi-info`; it is in final form, and its wording was settled on 2026-08-09 where it appears in § The ask path.
2. **Prompt.** The message tells `ghi-info` that issue #\<n\> was closed on \<date\>; asserts that the mirror is up to date (so the agent should not doubt the fact or try to confirm it); instructs it to re-read that issue's entry in `issues-closed.md` and, while doing so, to also look at any `Superseded-by:` link that entry contains; and asks it to produce a revised reading list.

## Cold-start prompt (ghi-info session birth; approved 2026-08-11)

1. **Preamble, sentence 1.** This text is sent as the very first message of a newly created session; a new session is created either when no stored session exists or when a recycle condition has been met, which is step 2 of the ask script.
2. **Preamble, sentence 2.** The actual question follows this prompt as a separate message, worded according to the resume-ask prompt given below.
3. **Preamble, sentence 3.** The `<mirror-path>` placeholder is filled in by the wrapper script.
4. **Prompt ¶1, sentence 1.** The agent is told its identity: it is `ghi-info`, the agent that holds knowledge of this project's collection of GitHub issues.
5. **¶1, sentence 2.** It is told the interaction model: other agents send it one request at a time, it answers each from the corpus already in its context, and then it stops — it does not carry on working after answering.
6. **¶1, sentence 3.** It is told its role in the division of labor: it supplies judgment, and every factual/mechanical operation — retrieving data, counting, checking — has already been carried out by scripts before the request arrives.
7. **¶2 (lead-in to the file list).** Its knowledge consists of the mirror stored at \<mirror-path\>, which is produced by a script and brought up to date before every single request it receives.
8. **File bullet 1, sentence 1.** `issues-open.md` contains every open issue completely, comprising number, title, labels, last-updated time, body, and comments.
9. **File bullet 1, sentence 2.** The agent is instructed to read that entire file immediately, before doing anything else at all.
10. **File bullet 2, sentence 1.** `issues-closed.md` contains one line for each closed issue.
11. **File bullet 2, sentence 2.** The agent must not read that file in its entirety; it should only search within it, and only when a request specifically concerns closed history.
12. **¶3, sentence 1.** GitHub holds the real data, and the mirror is the only window the agent has onto it.
13. **¶3, sentence 2.** The agent must never contact GitHub by any route — not through the `gh` command, not through the API, not through the web.
14. **¶4.** There are exactly four kinds of request the agent will receive.
15. **Request form 1, sentence 1.** In the first kind the agent is asked for a reading list — the question being what an agent ought to read before it creates or modifies an issue about a particular subject.
16. **Form 1, sentence 2.** The answer should be nothing but a list of issue numbers, illustrated as "read #13, #24, #31", and only where genuinely necessary may ordinary-prose note lines be added.
17. **Form 1, sentence 3.** Closed issues may appear in the answer only when the request has said that closed history is wanted; and where a closed issue does appear, it must be labelled accurately, in the form "#31 (closed 2026-08-08)".
18. **Request form 2, sentence 1.** In the second kind the agent is given the text of a proposed issue body and asked whether the existing corpus already covers that material.
19. **Form 2, sentence 2.** If the draft is a modification of an existing issue, the request will say which issue that is, and the agent must exclude that issue when looking for overlap.
20. **Form 2, sentence 3.** The answer must be exactly one line with nothing accompanying it, in one of three literal forms: `verdict: too-similar #n`, meaning an existing issue already covers this material and #n identifies it; `verdict: related #n,#m`, meaning there is no conflict but the author ought to be aware of those issues; or `verdict: unrelated`.
21. **Form 2, sentence 4.** Any reply that does not have one of those exact shapes is discarded (with the consequence, stated elsewhere, that the write proceeds unadjudicated).
22. **Request form 3, sentence 1.** In the third kind the agent is given a fact that corrects something in its previous answer — namely that an issue it recommended has since been closed — and is asked to redo just that one judgment.
23. **Form 3, sentence 2.** The fact has already been established by a script working from the freshly updated mirror, so the agent must not challenge it or try to check it; instead it should re-read the named entry in `issues-closed.md`, including any `Superseded-by:` link found there, and respond with a corrected reading list.
24. **Request form 4, sentence 1.** In the fourth kind the agent is asked to fix a link — a cross-reference that the maintenance sweep has determined is broken.
25. **Form 4, sentence 2.** The request itself describes what is wrong; the agent is to fix precisely that one link and change nothing else.
26. **Form 4, sentence 3.** Changes to an issue are made through `gh` in the normal way; changes on the document side are committed to the agent's own branch with a commit message stating what was changed and why.
27. **Form 4, sentence 4.** The reply is either the literal `done:` followed by a description of the repair, or the literal `blocked:` followed by a description of what prevented it.
28. **Boundaries, item 1.** If asked about anything that is not part of the issue corpus — the wiki, the source code, or any other subject — the agent must reply with precisely the string `out-of-scope` and nothing else.
29. **Boundaries, item 2, sentence 1.** The agent is never the one to decide whether a decision made in the past is still binding.
30. **Boundaries, item 2, sentence 2.** In that situation it must reply with the literal `escalate:` followed by a single sentence identifying which decision is at issue and what the uncertainty about it is.

## Resume ask prompt (ghi-info-ask step 3; approved 2026-08-11)

1. **Preamble, sentence 1.** This prompt is sent for every request asking for a reading list.
2. **Preamble, sentence 2.** When the session is new, this prompt comes immediately after the cold-start prompt; when the session is being resumed, this prompt is the only thing sent, which is why it contains the instruction to re-read changed entries — because it is the wrapper script, not the agent, that has detected that the agent's context has gone stale.
3. **Preamble, sentence 3.** The lines enclosed in angle brackets are either filled in or removed in their entirety by the script according to the conditions marked on them; and the question supplied by the asking agent is passed through exactly as written, never rephrased by the script.
4. **Preamble, sentence 4.** The prompt describes what kind of request this is using the same phrasing that the cold-start prompt uses for that request form, so that the two prompts refer to the same thing in the same words and reinforce one another.
5. **Prompt line 1.** A conditional line included only when the session is a resumed one and only when the just-run refresh actually changed something: it lists the numbers of the mirror entries that changed and instructs the agent to re-read those entries before answering, warning explicitly that an entry may have been relocated into `issues-closed.md` (that is, the issue may have closed).
6. **Prompt line 2, sentence 1.** The literal statement that this is a request for a reading list.
7. **Prompt line 2, sentence 2 (the slot).** Followed by the asking agent's question copied verbatim, with an illustrative example: an agent is about to file an issue proposing a policy for retrying in the launch scripts, and wants to know what it should read first.
8. **Prompt line 3.** A conditional line included only when the `--include-closed` option was used: it states that closed history is wanted for this request, instructs the agent to search `issues-closed.md` as well, and tells it that closed issue numbers in the reply are expected rather than mistakes, each to be labelled with the date it closed.

## Adjudication request (write tool step 2 → ghi-info; approved 2026-08-11)

1. **Preamble, sentence 1.** This prompt is sent by the write tool before performing any create or edit that carries a body.
2. **Preamble, sentence 2.** It goes through the same wrapper script as reading-list asks, described in § The ask path, which is why it carries the same conditional line about changed entries — a line that is omitted entirely when the session is fresh or when the refresh found no changes.
3. **Preamble, sentence 3.** The draft body is inserted exactly as the author wrote it, with no modification.
4. **Preamble, sentence 4.** If no reply comes back, or the reply doesn't have the required shape, the write goes ahead without an adjudication — and this is behavior implemented in the tool rather than something the prompt itself says.
5. **Prompt line 1.** The conditional changed-entries line: sent only on a resumed session and only when the refresh changed something, listing the changed issue numbers and instructing the agent to re-read them in the mirror before answering.
6. **Prompt line 2.** The statement that this request is of the "shown a draft body, asked whether the corpus covers it" kind.
7. **Prompt line 3.** A conditional line present only when the write is an edit: it names the issue being edited and instructs the agent to exclude that issue from the comparison.
8. **Prompt line 4.** A label announcing that what follows is the draft body reproduced exactly.
9. **Prompt line 5.** The slot into which the draft body itself is inserted.
10. **Prompt line 6.** The instruction that the answer be exactly one line, in one of the three literal forms `verdict: too-similar #n`, `verdict: related #n,#m`, or `verdict: unrelated`.

## Link-repair request (sweep → ghi-info; approved 2026-08-11)

1. **Preamble, sentence 1.** The sweep sends this prompt once for each broken-link finding, and this is the single category of writing that `ghi-info` itself performs.
2. **Preamble, sentence 2.** It travels through the same wrapper as the other request types, which is why it too begins with the conditional changed-entries line.
3. **Preamble, sentence 3.** The rule about how the reply must be shaped — either `done:` or `blocked:` — is copied from the fixer briefs, so all three use the same reply contract.
4. **Prompt line 1.** The conditional changed-entries line, included only on a resumed session and only when entries actually changed, listing them and requiring a re-read before answering.
5. **Prompt line 2, sentence 1.** The statement that this request is of the link-repair kind.
6. **Prompt line 2, sentence 2 (the slot).** Followed by one sentence written by the sweep describing what specifically is broken, with two illustrative cases: the body of issue #31 cites the path `docs/issues/31-foo.md`, which does not exist on the main branch; or the document `docs/issues/31-foo.md` contains a back-reference to issue #29 when the issue it is actually paired with is #31.
7. **Prompt line 3, sentence 1.** The instruction to fix that one link only and change nothing else.
8. **Prompt line 3, sentence 2.** Changes to issues are made through `gh` in the ordinary way; changes to documents are committed on the agent's own branch with a message stating what and why.
9. **Prompt line 3, sentence 3.** The reply must be exactly one of the two forms: the literal `done:` followed by a description of the repair made, or the literal `blocked:` followed by a description of what prevented it.

## Write tool replies (refusals and appended instructions; approved 2026-08-11)

1. **Preamble, sentence 1.** All the refusal messages follow one common structure — state that the action was refused, state why, and state the available way or ways to proceed — and each ends with the single-use, audit-logged override, following the pattern of `instruction-file-guard.py` which is already running on main; here that override line is shown as a placeholder rather than spelled out.
2. **Preamble, sentence 2.** The last two entries in this subsection are not refusals at all: they are additional lines the tool prints after a write has succeeded, positioned after the `gh` command's own output, which the tool reproduces unchanged.
3. **Reference-check refusal, heading gloss.** This message is used when the body cites a path inside the repository that does not exist on main.
4. **Reference-check refusal, sentence 1.** The message states that the write was refused because the body cites \<path\>, which does not resolve on the main branch.
5. **Reference-check refusal, sentence 2.** It then offers two options: merge the Markdown file first and then run this write again, or file the issue now with the reference omitted and add the reference by editing the issue once the file has landed.
6. **Reference-check refusal, closing line.** Then the placeholder for the audited one-use override line, following the instruction-file-guard pattern.
7. **Too-similar refusal, heading gloss.** This message is used when the adjudication came back with the `too-similar` verdict.
8. **Too-similar refusal, sentence 1.** It states the write was refused because issue #\<n\> already covers this subject matter.
9. **Too-similar refusal, sentence 2.** It instructs the author to read #\<n\> and then incorporate this content into #\<n\> by editing it, and explicitly forbids creating a new issue instead.
10. **Too-similar refusal, closing line.** The placeholder for the audited one-use override line.
11. **Comment denial, heading gloss.** This message is used when an agent runs `gh issue comment` or `gh issue close --comment`.
12. **Comment denial, sentence 1.** It states the action was refused, with the summary reason that in this project comments do not end up as comments.
13. **Comment denial, sentence 2.** It explains why: the project's revision convention requires the issue body to always be current, and no automatic process can turn a comment into the body edit that convention requires, because only the author knows where in the body the content belongs and which existing text it replaces.
14. **Comment denial, sentence 3.** It gives two ways forward: fold the content into the issue body by editing the issue; or, if what is being recorded is genuinely one of the recognized event types — an instance outcome, a completion, or a challenge to a ruling — submit it again through the write tool's comment operation while stating which of those event types it is.
15. **Comment denial, closing line.** The placeholder for the audited one-use override line.
16. **Delete denial, sentence 1.** It states the action was refused because issues are never deleted in this project, on the principle that the record only ever grows forward.
17. **Delete denial, sentence 2.** It directs the author to close the issue instead, supplying one of the two permitted reasons: completed, or not planned.
18. **Delete denial, closing line.** The placeholder for the audited one-use override line.
19. **Related-verdict note, heading gloss.** This line is added after a write that succeeded, in the case where adjudication returned the `related` verdict.
20. **Related-verdict note, text.** It tells the author which issues are worth being aware of, listing their numbers.
21. **Over-length instruction, heading gloss.** This is added when the body that was actually written turns out to exceed the word limit.
22. **Over-length instruction, sentence 1.** It reports the body's word count and the applicable limit.
23. **Over-length instruction, sentence 2.** It instructs the author to leave a good summary in the body and move the detailed content into the paired Markdown document, creating that document if it does not exist or updating it if it does.
24. **Over-length instruction, sentence 3.** It tells the author to ask `ghi-info` which documents or issues to link to.

## Deliberately not in version 1

*(Table columns: the thing left out, the reason for leaving it out, and the condition under which it would be reconsidered; one item per row.)*

1. A vector database or graph database is left out because the model's context window serves the purpose a database would serve; it would be reconsidered if the quality of what gets retrieved is observed to get worse, or if the set of open issues grows too large to fit in the context window.
2. Using GitHub's MCP server as the way writes are performed is left out because writes made that way would be generic and would not go through any of this project's checks; it would be reconsidered if some runtime that is being used has writes that cannot be intercepted by a hook and therefore becomes a route by which writes happen.
3. Making the block on raw `gh` writes absolute is left out because it would create a single component whose failure would stop all issue writing; it would be reconsidered if the override audit log shows that overrides are being used to evade the tool rather than to work around something broken.
4. Removing old closed issues from GitHub itself is left out because the burden closed issues impose falls on context and attention rather than on GitHub, and the one-line-per-issue closed file carries them at very little cost; it would be reconsidered if that closed-file treatment stops being adequate.
5. Running several independent watchdog processes to supervise the agent is left out because a single overall timeout is sufficient at the scale of one question at a time; it would be reconsidered if that single timeout turns out to be too coarse an instrument.
6. Committing the mirror files into git is left out because the constant churn of regenerated content would clutter the history the user actually reads; it would be reconsidered if there arises a need to search the mirror across multiple checkouts that regenerating it separately on each machine cannot satisfy.

## Verify at build

1. **Lead-in.** Each of the following is something to confirm during implementation, and each is stated together with what will be done if the confirmation fails.
2. **Item 1.** Confirm that an issue's `updated` timestamp changes when the issue is closed, when it is reopened, and when its labels change, just as it does when the body is edited or a comment is added — this is what the documentation says but it was not tested while writing this design; if it turns out not to be true, the consequence is bounded because the full rewrite of the mirror at recycle time limits how long such a change can go unnoticed.
3. **Item 2.** Confirm that a single PreToolUse hook response can carry both an `updatedInput` field and an `additionalContext` field at the same time, which the documentation does not state; if it cannot, then everything the author needs to be told will be carried in the write tool's own reply, and the mechanism for injecting extra context will simply not be used.
4. **Item 3.** Confirm that Codex has hooks equivalent to pre-tool hooks — Codex is known to have some hook mechanism, but the specific field names have not been checked; if the equivalence doesn't hold, writes made from Codex remain in the category of knowingly accepted gaps.
5. **Item 4.** Confirm that GitHub's cross-reference timeline event can be used as the way to find issue-to-issue back-references, which is a question about the shape of the API's data; if it cannot be used, back-references will have to be derived solely by parsing issue bodies for references.
6. **Item 5.** Confirm that the lines the write tool prints after passing through `gh`'s own output are not confusing to the authoring agents reading them; if they are confusing, change how those replies are formatted.
7. **Item 6.** Confirm that both of the credentials on the Ubuntu machine keep working when nobody is attending to the machine — noted as a real past problem, since that machine's authentication has expired before; the mitigation stated here is that the sweep will test whether the credentials are still valid and raise a warning about an impending expiry before it causes a failure.
8. **Item 7.** Confirm what fetching comments costs at realistic volumes — the only measurement so far being a single one, 0.42 seconds for one issue that had comments. (No "else" branch is stated for this item.)
9. **Constants, sentence 1, clause 1.** The numeric settings are kept as named constants at the top of whichever script owns them, and version 1 has no configuration file at all.
10. **Constants, clause 2.** All the values listed are initial guesses meant to be adjusted based on how the system behaves in real use.
11. **Constants, value 1.** `BODY_WORD_LIMIT` is 500 — a value the user decided on 2026-08-11, increasing it from the 400 that had been in the previously approved set of constants, with the explicit note that neither number was calculated from anything and both are starting guesses; the constant is defined in the write tool, and the sweep script imports it from there rather than defining its own copy.
12. **Constants, value 2.** The recycle trigger based on issues closing since the session started fires at 20.
13. **Constants, value 3.** The stale-match trigger fires when 2 of the last 10 answers contained a stale match.
14. **Constants, value 4.** The transcript-size threshold is not fixed here; it will be chosen at build time based on the values that are working in the nedsmessenger project.
15. **Constants, value 5.** The timeout on an ask is 5 minutes, a figure chosen to fit within the time budget the hook system allows.
16. **Constants, value 6.** Exactly one drift recheck is permitted per ask.

