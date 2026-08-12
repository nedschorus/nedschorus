<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=restate tier=floor target=/Users/el/Projects/nedschorus/.claude/worktrees/linters-tool-usage-f8b0a0/docs/drafts/ghi-info-agent-design.md -->

and draws on the two data feeds described earlier (GitHub issues and the git-log/pair-MD feed). It performs three checks: a length check over any changed bodies, a scan for `Superseded-by:` markers, and a link-integrity scan in both directions — noting that the markdown side of this check is read directly from the repository checkout on disk, not from the mirror.
2. When the sweep finds a problem, it spawns a "one-shot focused fixer agent" — a disposable agent created to handle exactly one task and then finish — belonging to the general agent class defined in the "26-dynamic-agent-team-model.md" document, launched per the pattern described in issue #41. Each fixer is given a narrowly-scoped brief, for example: "issue #31 moved on <date>; its pair MD has not: update the MD."
3. These fixer agents don't get special/privileged write access — they write through the same normal path as any GHI author, and they consult ghi-info the same way any author would.
4. ghi-info's own direct write capability is limited strictly to repairing links — it never writes/fixes the actual substantive content of an issue or document.
5. The check for whether a pair (an issue and its paired MD) has drifted out of sync runs in only one direction: checking for cases where the issue has changed but its paired MD has not been correspondingly updated.
6. The opposite situation — the MD having landed on main while the issue has been untouched since — is deliberately not checked, per the user's 2026-08-11 ruling: having the MD "ahead" of its issue is treated as the normal, expected intermediate state of the pair sequence, and since the issue body is only meant to be a summary, many MD edits simply wouldn't need reflecting back into it at all.
7. This is another knowingly-accepted gap: if an author lands the MD but never completes the step of citing it back from the issue, this omission goes uncaught by the sweep; nor does the separate link-integrity scan catch it, because a link that was never added in the first place has nothing to check — it trivially ("vacuously") "resolves" with nothing to flag as broken.
8. If a fixer agent gets stuck and can't complete its assigned fix, this is escalated by filing a single new issue, labeled `draft`, that names specifically what blocked it.
9. There remains an open, currently-undecided question about which specific model and runtime best serve each role in this system — ghi-info itself, the fixer agents, and the adjudication function — considering options like Claude versus Codex as runtime, and among Claude models, options like "fable," "opus," or "sonnet"; this is left to be resolved empirically (through real-world use), not decided in advance.

# The three-layer stack

1. The first layer is the `ghi-write` skill — currently being built, with its own walkthrough underway in a separate document, "ghi-write-skill-draft.md." It activates whenever a GHI author is about to file or edit an issue, and its purpose is to proactively instill the correct behavior beforehand: ask ghi-info first, route the content appropriately based on its state, prefer editing an existing issue over creating a duplicate, keep the writing lean, and follow the "pair sequence" — write the MD first, get it landed on main, and only then cite it from the issue.
2. The second layer is the hook-and-tool combination, serving as a "correctness backstop" for cases where the `ghi-write` skill, for whatever reason, doesn't fire; as long as the write goes through the covered path and ghi-info is available, even a missed skill trigger mainly costs efficiency rather than letting an actual error through — e.g., a duplicate caught only later at merge time, or one comment retry needed.
3. The window during which ghi-info might be unreachable and the write proceeds unadjudicated ("the fail-open window"), along with the known enumeration gaps in what the hook can catch, are both accepted as known limitations, and both remain visible afterward in the delta feed.
4. The third layer is the CLAUDE.md file, serving only as passive/ambient background documentation, not an active enforcement mechanism — the parenthetical notes that issue #13 documents a past case where a written convention there was ultimately overridden by trained habit, presumably why this layer alone isn't relied upon and needs the other two layers to back it up.

# Division of labor

1. This row states that the work of fetching issue data, formatting it, merging in incremental changes (the delta), and splitting entries by state is owned by the `ghi-mirror-refresh.py` script, and this work is classified as "free" — meaning it costs no model/agent turn.
2. This row states that checking references and checking length are owned by the `ghi-issue-write.py` tool, and this work is also "free."
3. This row states that computing freshness numbers, scanning for the `Superseded-by` marker, and scanning link integrity are owned by the sweep scripts, and this work is "free."
4. This row states that post-checking ghi-info's answers and generating the drift notice are owned by `ghi-info-ask.py`; this is generally "free," but a drift notice that triggers a recheck does cost one model call to ghi-info.
5. This row states that determining which issues bear on a question, and rendering similarity verdicts, are owned by ghi-info itself, and this work costs a model call — requiring actual AI judgment, unlike the free rows above.
6. This row states that cross-link repairs are owned by ghi-info, with the cost/classification given as "its one write class" — echoing that this is the one and only kind of write ghi-info performs itself.
7. This row states that routing decisions, writing the substantive body content, and the "lean-split merge" (splitting content between body and pair MD when over length) are owned by the GHI author, guided via `ghi-write`; the cost is "context already loaded" — meaning no extra cost, since the author already holds the relevant context from doing their own work.
8. This row states that fixing stale MDs and over-length bodies, once found by the sweep, is owned by the spawned focused fixers, with the cost being one disposable one-shot agent per problem found.

# Prompts

1. This section is meant to contain the exact, word-for-word text of every prompt this design relies on — required by the user's rulings across 2026-08-09 and 2026-08-11. The stated reasoning is that a prompt existing only as a general description can't actually be built from or properly reviewed.
2. Each prompt is written to make sense to a reader with no prior context — presumably meaning the receiving agent, which won't necessarily recall this design document.
3. Before this document's overall status can be marked closed, the "Prompts" section itself must undergo and pass its own separate md-review.
4. Placeholder text in angle brackets (e.g. `<n>`, `<date>`) represents a "slot" filled in with actual values by whichever script sends the prompt; the receiving agent is never the one that fills these in — by the time it sees the prompt, the slot is already replaced with real content.
5. The current status is that every prompt in this section has reached final form: the two fixer-brief templates, the drift notice, the cold-start prompt (covering four request forms), the resume-ask prompt, the adjudication-request prompt, the link-repair-request prompt (which the user specifically decided on 2026-08-11 should be fully written here now rather than left to be figured out during implementation), and the write tool's various reply messages.
6. Despite every prompt now being content-complete, this section as a whole still needs to pass its md-review, a required step before the document's overall status can close.

## Fixer brief — pair document behind its issue

1. For this brief, the sweep itself fills in every placeholder slot, including the reading list — obtained by running `ghi-info-ask.py` itself before spawning the fixer — so the fixer agent doesn't need to invoke/run anything itself.
2. The prompt tells the receiving agent it is a "fixer": a disposable, one-shot agent created when a maintenance script detects that a pair document has fallen behind the issue it's paired with.
3. The agent is told its sole purpose is to update the specific document named below so it's current, then terminate.
4. The assigned job states that a given issue (number filled by slot) changed on a given date, while its pair document (at a given path) has not been touched since another given date.
5. The agent is instructed to update the pair document to match the issue's current state.
6. Before anything else, the agent is told to read: the issue, its pair document, and a list of related issues — whatever ghi-info returned when the sweep asked on the fixer's behalf, e.g. #13, #24.
7. The following rules apply.
8. The agent may change only the pair document, committing on its own branch with a message explaining what and why.
9. The agent is forbidden from writing to any issue.
10. The agent should do exactly and only the job stated above — nothing more or different.
11. The agent should stop and report itself "blocked" rather than proceed to edit, under any of the following conditions.
12. One condition: the change would alter text marked as a formal ruling (using markers like "user-ruled," "boss-ruled," "Accepted residual," or a dated ruling), or would require choosing between two such conflicting statements.
13. Another condition: the issue and document conflict in a way the existing record doesn't resolve.
14. A third condition: the agent itself isn't confident the change is correct.
15. The agent's final message must take exactly one of two forms.
16. A "done" message, describing what changed, specifically listing the files affected.
17. Or a "blocked" message, explaining what stopped the agent, quoting the specific text at issue.

## Fixer brief — issue body over the length limit

1. This second template follows the same slot-filling arrangement as the first — the sweep fills everything in ahead of time, including the reading list.
2. This brief includes a specific exception, decided by the user on 2026-08-11, for handling formally-ruled text: such text may be relocated (moved between documents), but its wording must never be changed.
3. The prompt tells the agent it is a fixer, created because a maintenance script found an issue body that has grown past the length limit.
4. The agent's entire purpose is to shorten the specified body, then exit.
5. The job states that a given issue's body currently has a certain word count (filled by slot), exceeding the stated limit (also filled by slot).
6. The agent is instructed to keep an adequate summary in the body while moving the substantive content into the issue's pair document at a given path, creating that document if it doesn't already exist.
7. Before anything else, the agent should read the issue, its pair document (noting it may not yet exist), and the related-issues list ghi-info returned when the sweep asked on the fixer's behalf, e.g. #13, #24.
8. The following rules apply.
9. Editing the body should go through `gh` normally (i.e., through the standard hook/write-tool path).
10. Any changes to the pair document should be committed on the agent's own branch with a message explaining what and why.
11. Any content removed from the body must not simply be lost — it must end up in the pair document.
12. Text marked as a formal ruling must, if moved, be moved exactly word-for-word into the pair document without rewording, with the body's remaining summary citing where it went.
13. The agent should do exactly and only the job stated above.
14. The agent should stop and report blocked rather than edit under any of the following conditions.
15. One condition: the intended change would require rewording ruled text — since moving it verbatim, as permitted, is the only allowed handling — or would require choosing between two conflicting ruled statements.
16. Another condition: the issue and document conflict in a way the record doesn't resolve.
17. A third condition: the agent isn't sure the change is correct.
18. The agent's final message must take exactly one of two forms.
19. A "done" message describing what changed, including both files and issue numbers affected.
20. Or a "blocked" message explaining what stopped the agent, quoting the relevant text.

## Drift notice

1. The heading indicates this prompt was finalized and its wording decided on 2026-08-09, within "The ask path" section.
2. The notice tells ghi-info that a specific issue (filled by slot) closed on a specific date, asserts the mirror is current, and instructs ghi-info to re-read that issue's entry in the closed-issues file — including checking for any `Superseded-by:` link — then provide a corrected reading list in response.

## Cold-start prompt

1. This prompt is sent as the very first message of a newly-started session; as described earlier, a cold start happens when no stored session exists to resume, or a recycle trigger has fired.
2. After this prompt, the actual question follows as a separate message, worded per the resume-ask prompt described in its own subsection.
3. The `<mirror-path>` placeholder is filled in by the wrapper script, not the agent.
4. The prompt establishes the agent's identity: it is told it is "ghi-info," the agent holding knowledge over this project's GitHub-issue corpus.
5. It's told other agents send one request at a time, and it should answer each from the corpus it holds in context, then stop.
6. It's told its role is to provide judgment, and that every mechanical fact (fetching, counting, verifying) has already been handled by scripts before a request reaches it.
7. It's told its knowledge is the local mirror at a given path, regenerated by script and refreshed before every request.
8. `issues-open.md` is described as containing every open issue in full — number, title, labels, updated time, body, comments — and the agent is instructed to read this file whole, right now, before anything else.
9. `issues-closed.md` is described as one line per closed issue, and the agent is instructed not to load it whole, only to grep it when a request asks about closed history.
10. It's told GitHub is the source of truth and the mirror is its only view of it.
11. It's explicitly told never to call GitHub directly by any means — no `gh`, no API, no web.
12. It's told requests arrive in four distinct forms, described below.
13. Form one: the agent is asked for a reading list — specifically what another agent should read before filing or editing an issue on some topic.
14. It should reply with a bare list (e.g. "read #13, #24, #31"), adding note lines in plain sentences only when needed.
15. Closed issues belong in the reply only when the request says closed history is wanted, each tagged truthfully, e.g. "#31 (closed 2026-08-08)."
16. Form two: the agent is shown a draft issue body and asked whether the corpus already covers it.
17. When the draft is an edit of an existing issue, the request names that issue, and the agent should exclude it from comparison.
18. The agent must reply with exactly one line and nothing else, in one of three exact forms: `verdict: too-similar #n` (an existing issue already covers this ground); `verdict: related #n,#m` (no collision, but the author should know these); or `verdict: unrelated`.
19. A reply in any other shape is discarded/ignored.
20. Form three: the agent is told a fact correcting its last reply — an issue it cited has closed — and asked to redo that one judgment.
21. It's told this fact is already established by script from the refreshed mirror, so it should not question or verify it; instead it should re-read the named entry in `issues-closed.md`, including any `Superseded-by:` link, and reply with a corrected reading list.
22. Form four: the agent is asked to repair a link — a cross-reference the maintenance sweep found broken.
23. The request states the defect, and the agent should repair exactly that link and nothing else.
24. Issue edits should go through `gh` as normal; document-side changes should be committed on the agent's own branch with a message stating what and why.
25. The agent should reply with either "done:" plus the repair, or "blocked:" plus what stopped it.
26. The following boundaries apply.
27. If asked anything beyond the issue corpus — the wiki, the code, anything else — the agent should reply with exactly: "out-of-scope."
28. It's told that whether an old ruling still binds is never its place to judge.
29. In that case it should reply "escalate:" followed by one sentence naming the ruling and the doubt.

## Resume ask prompt

1. This prompt is sent on every reading-list request.
2. On a fresh session it follows the cold-start prompt as a separate message; on a resumed session it stands alone, so it carries the re-read preamble itself — since in that case it's this prompt's job to make the agent aware of drift, echoing that the wrapper (not the agent) notices drift.
3. Angle-bracket lines are either filled in or dropped entirely by the script exactly as marked; the asker's actual question is inserted exactly as written, never reworded.
4. This request names which of the four forms it is, using the same wording the cold-start prompt itself uses, so the two prompts fit together consistently.
5. A line appearing only on resume, and only when the refresh changed entries, tells the agent which mirror entries (by issue number) changed since its last request, and instructs it to re-read them before answering — noting an entry may have moved to `issues-closed.md`.
6. The agent is told plainly it's being asked for a reading list, labeling this as form one; the actual question from the asker follows, inserted exactly as phrased, e.g.: "An agent is about to file an issue proposing a retry policy for the launch scripts. What should it read first?"
7. A line appearing only when `--include-closed` was used tells the agent that closed history is specifically wanted for this request, to also search `issues-closed.md`, and confirms that closed references are expected in the reply, each tagged with its close date.

## Adjudication request

1. This prompt is sent by the write tool for every body-bearing create or edit, before the write happens.
2. It travels through the same wrapper mechanism used for ordinary asks, so it carries the same changed-entries preamble, omitted entirely on cold start or when the delta found no changes.
3. The draft issue body being evaluated is included exactly as written, unmodified.
4. If ghi-info fails to reply, or replies in a form not matching the expected shape, the write proceeds without adjudication — this fail-open behavior is implemented by the write tool itself, not the prompt's wording.
5. A line appearing only on resume with changed entries tells the agent which mirror entries changed and instructs it to re-read them before answering.
6. The agent is told plainly it's being shown a draft issue body and asked whether the corpus already covers it — matching form two of the cold-start prompt.
7. A line appearing only for edits tells the agent which specific issue the draft is editing, instructing it to exclude that issue from comparison.
8. The draft body text follows, introduced as verbatim and inserted exactly as written.
9. The agent is instructed to reply with exactly one line, in one of the three exact verdict forms.

## Link-repair request

1. This prompt is sent by the sweep for each link-integrity finding — corresponding to ghi-info's one write class.
2. It travels through the same shared wrapper as the other requests, so it carries the same changed-entries preamble.
3. The done/blocked reply contract matches the one used in the fixer-brief prompts.
4. A line appearing only on resume with changed entries tells the agent which entries changed and instructs it to re-read them first.
5. The agent is told plainly it's being asked to repair a link; one sentence supplied by the sweep describes the specific defect, illustrated by two examples: "Issue #31's body cites docs/issues/31-foo.md, which does not resolve on main" (the cited file doesn't exist on main), or "docs/issues/31-foo.md backlinks #29, but its issue is #31" (the document links back to the wrong issue number).
6. The agent is instructed to repair precisely this one link and nothing else.
7. Issue edits should go through `gh` normally; document changes should be committed on the agent's own branch with a message explaining what and why.
8. The agent should reply with exactly one of: "done:" plus the repair, or "blocked:" plus what prevented it.

## Write tool replies

1. Every denial in this document follows the same structure — states the refusal, gives the reason, describes the way(s) forward — and ends with the audited one-use override, following the same pattern as the existing `instruction-file-guard.py`; here that override text is shown as a placeholder slot rather than spelled out each time.
2. The final two entries below are different in kind — not refusals at all, but additional lines the write tool appends after a write has already succeeded, placed after `gh`'s own output, which the tool relays exactly as-is.
3. This heading labels the following block as the message shown when the reference check fails — a cited in-repo path that doesn't resolve on main.
4. The message states the write was refused because the body cites a given path that doesn't resolve on main.
5. It offers two ways forward: get the referenced MD merged onto main first, then rerun the write; or file now without the reference and add it later by edit once the MD lands.
6. A placeholder marks where the audited one-use override line would be inserted.
7. This heading labels the following block as the message shown when the adjudication verdict comes back "too-similar."
8. The message states the write was refused because an existing issue (numbered n) already covers this ground.
9. It instructs the author to read that issue and merge their content into it by editing it, explicitly telling them not to file a new issue.
10. (The override placeholder appears again here.)
11. This heading labels the following block as the message shown when an author attempts `gh issue comment` or closing with a comment.
12. The message states the refusal, explaining that in this system comments don't land as comments.
13. It explains that the revision convention keeps the body current, and a comment can't be mechanically rewritten into the required body edit — because only the author knows where new content should go and what it supersedes.
14. It offers two ways forward: integrate the content into the body via an edit; or, if this is genuinely one of the recognized event kinds (instance outcome, completion, ruling challenge), resubmit through the tool's comment action naming that kind.
15. (The override placeholder appears again here.)
16. This heading labels the following block as the message shown when an author attempts to delete an issue.
17. The message states the deletion was refused because issues are never deleted — the record only grows by appending, never by removal.
18. It instructs the author to close the issue instead, with a reason of "completed" or "not planned."
19. (The override placeholder appears again here.)
20. This heading labels the following line as one appended after a successful write, specifically when adjudication returned "related."
21. The appended note lists the related issue numbers (filled by slots) worth the author knowing about.
22. This heading labels the following block as text appended after a successful write when the landed body exceeds the length limit.
23. It states the body's word count and the limit.
24. It instructs the author to keep a good summary in the body while moving substantive content into the linked pair MD, creating or updating it.
25. It tells the author to ask ghi-info what to link.

# Deliberately not in version 1

1. This row states that a vector- or graph-based database was deliberately excluded from version 1; the reason given is that the agent's context window itself serves as "the database"; this would be revisited if retrieval quality is measurably found to degrade, or if the open corpus grows too large to fit in the context window.
2. This row states that using a GitHub MCP server as the means of writing issues was excluded; the reason is that such generic writes wouldn't carry any of the project's custom checks; this would be revisited if some runtime's writes turn out to be impossible to intercept with a hook, making an MCP-style write surface necessary.
3. This row states that making the block on raw `gh` writes "hard" (unbypassable) was excluded; the reason given is that a hard block would create a single point of failure for all issue writes; this would be revisited if the override-usage audit shows people dodging the tool rather than working around genuine breakage.
4. This row states that actually purging old closed issues from GitHub was excluded; the reasoning is that the real burden of old closed issues is on context size and attention, and the compact closed-file approach already handles that cheaply; this would be revisited if that closed-file approach ever stops being sufficient.
5. This row states that using multiple watchdog processes (as nedsmessenger does) was excluded; the reasoning is that one overall timeout is judged sufficient at the current one-question scale; this would be revisited if that single timeout proves too blunt an instrument.
6. This row states that committing the mirror into version control was excluded; the reasoning is that the constant churn of a repeatedly-committed derived file would pollute the git history the user reads; this would be revisited if a need arose to grep the mirror across multiple machine checkouts in a way per-machine regeneration couldn't satisfy.

# Verify at build

1. This introduces a list of things needing verification once the system is built, each paired with a description of what happens if that verification fails (its "failure branch").
2. The first item to verify is whether an issue's `updated` timestamp actually changes not just on body edits and comments but also on close, reopen, and label changes — documented as expected but untested here; if not true, the fallback is that the periodic full mirror rewrite at each recycle would still bound how long such a discrepancy could persist.
3. The second item is whether the hook features `updatedInput` and `additionalContext` can both be used together in one PreToolUse reply — currently undocumented; if not, the fallback is that the tool's own reply would need to carry everything itself, leaving the separate context-injection mechanism unused.
4. The third item is whether Codex has an equivalent pre-tool-hook mechanism — known to have some form of hooks, but exact field names unverified; if this doesn't pan out, the fallback is that Codex-side writes remain in the accepted-holes class.
5. The fourth item is whether GitHub's cross-reference timeline event can serve as the source for detecting issue-to-issue backlinks — depending on confirming that part of the API's shape; if not, the fallback is that backlinks would have to be derived solely from parsing body text.
6. The fifth item is whether the tool's appended lines after relayed `gh` output avoid confusing authors; if they do confuse, the fallback is to adjust the reply format.
7. The sixth item is whether both of the box's credentials survive unattended operation — flagged as a real concern since the box's auth has expired unexpectedly before; the mitigation is that the sweep checks credential validity and flags impending expiry before it causes a failure.
8. The seventh item is the actual cost of fetching comments at real/production volume — so far measured only once, for a single issue with comments, at 0.42 seconds, implying the cost at larger scale still needs confirming.
9. This states that configuration constants live as plain named values at the top of whichever script owns them, rather than in any separate config file — version 1 deliberately has none. It then gives starting values expected to be tuned through live use: `BODY_WORD_LIMIT` starts at 500 (decided by the user on 2026-08-11, raised from an earlier value of 400 in a previously-approved batch — neither number was mathematically derived, both are reasonable starting guesses; this constant lives in the write tool's code, and the sweep imports it from there); the closes-since-birth recycle threshold is 20; the stale-match trigger fires at 2 out of the last 10 answers; the transcript-size threshold will be set at build time based on nedsmessenger's working values; the ask timeout is 5 minutes, within the overall hook budget; and only one drift-triggered recheck is allowed per ask.

