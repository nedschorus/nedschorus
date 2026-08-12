<!-- provenance: runtime=codex model=gpt-5.6-terra effort=xhigh cell=restate tier=floor target=/Users/el/Projects/nedschorus/.claude/worktrees/linters-tool-usage-f8b0a0/docs/drafts/ghi-info-agent-design.md -->

## Frontmatter

1. The design is considered integrated; the plan walk settled its decisions on 2026-08-07, markdown-review corrections were settled on 2026-08-09, and the remaining status is waiting for the user’s integration walk.

## Walk order — integration walk

1. The already-walked and confirmed core covers `ghi-info`’s identity, responsibilities, answer format, hosting location, mirror structure, non-gating posture, and three-layer architecture.
2. The user confirmed that core in six parts on 2026-08-09.
3. A rider placed the over-specification correctness rule in the skill-authoring checklist’s Register section rather than in `CLAUDE.md`; that change was made the same day, and this design does not modify `CLAUDE.md`.
4. The walked write-path material covers the hook rewrite, the write tool’s four steps, comments, closing, deletion, the soft block and override, and intentionally accepted gaps.
5. The user approved that material in three parts on 2026-08-09.
6. The design records that reviewers may instinctively try to turn a soft block into a hard one, but the soft-block ruling is now an explicitly searchable accepted residual protected by the standing reviewer-counterpart rule.
7. Reviewers may raise that residual again only when evidence meets its named reopening condition, rather than treating it as a normal review finding.
8. The user also ruled that untouched state changes reach the mirror through the ordinary delta refresh, with full recycle refresh as a fallback.
9. The user further ruled that new mirror fields are added only through deliberate one-line script changes, never automatically.
10. The walked ask-path material covers wrapper steps, drift notification and recheck, `--include-closed`, throwaway-session concurrency, and the fallback sequence.
11. The user approved that material in two parts on 2026-08-09.
12. The drift notice was rephrased to remove ambiguity: the script, using the freshly refreshed mirror, establishes that an issue closed; it gives that fact to the agent and asks only for a renewed judgment using mirror files.
13. The agent must never call GitHub to independently verify the issue state.
14. The walked session-and-currency material covers lifecycle, recycle triggers, two refresh cadences, freshness, and the `Superseded-by` marker.
15. The user approved that material on 2026-08-09.
16. The walked maintenance-and-fixer material covers the sweep, focused spawned fixers, escalation, and the unresolved question of which model belongs to which role.
17. The user approved it on 2026-08-11 through a fixer-brief drafting exercise and a teaching walk for someone with no prior context.
18. The single fixer brief was split into two templates, one for each defect type.
19. The sweep selects the applicable template, and every resulting brief covers only one job.
20. Before spawning a fixer, the sweep runs `scripts/ghi-info-ask.py` and places the resulting reading list into the brief, so the fixer itself invokes no such tool.
21. “Do only the job stated above” replaced “smallest change.”
22. Every prompt must introduce itself sufficiently for a reader with no prior context.
23. The initial value of `BODY_WORD_LIMIT` is 500, and the constants line was changed accordingly.
24. Staleness is swept only from issue to pair document; the possibility of a missing citation is recorded as an accepted residual.
25. When ruled text appears in an over-length issue body, it is moved word-for-word into the pair document, and the body summary cites that destination.
26. Only Template B permits rewording blocks.
27. Every prompt required by the design must appear verbatim in the Prompts section, and that section must receive its own markdown review before the design can close.
28. Four prompts were still missing at this point.
29. The close-out stage covers the document’s final location, building GHI, and the riders: resuming the `ghi-write` walk, reviewing the correctness rule, and revising the lifecycle for issue 26.
30. That stage remained open on 2026-08-11.
31. The user approved this close-out order: draft the four missing Prompts entries one at a time, review that section with `md-review`, decide where the document lands—with the current recommendation being that it becomes the build GHI’s pair document—file the build GHI, and then queue the riders.
32. Prompt drafting was underway, and the Prompts section’s “owed” or “final” labels mark each prompt’s status.

## ghi-info — the GHI knowledge agent (design)

1. The design describes how agents handle GitHub issues in nedschorus through four connected parts: `ghi-info`, a long-lived agent that knows the issue corpus; a script-maintained local mirror; a hook-mediated write path for raw writes; and the `ghi-write` skill, which supplies judgment that automation cannot supply.
2. “GHI author” always means the agent that is filing or editing an issue.
3. The cited plan draft and markdown-review dispositions preserve the decision history, while the cited gatekeeper draft preserves the rejected design that would have imposed a single gate.
4. Rather than creating a vector or graph database for the issue corpus, the project uses a modern agent because the corpus fits into that agent’s context window; the measured corpus was 45 issues and about 109 KB.
5. Scripts perform mechanical tasks such as fetching, formatting, measuring, and filtering, while `ghi-info` uses model turns only where judgment is required.

## What ghi-info is

1. `ghi-info` is the first implementation of the domain-knowledge-agent class defined in the cited issue-26 document, whose first listed domain is GitHub issues.
2. The design assigns it three duties.
3. When a GHI author is about to file or edit an issue, that author asks what material to read.
4. The answer should be only a reading list, such as “read #13, #24, #31.”
5. `ghi-info` maintains cross-links between issues and keeps issue-to-Markdown links and Markdown-to-issue backlinks correct in both directions.
6. Every issue reference to Markdown must resolve on `main`, and every pair Markdown document must backlink to its correct issue or issues.
7. Repairing links is `ghi-info`’s only permitted class of write.
8. Other discovered defects, such as a pair document lagging its issue or an issue body exceeding its word limit, cause the Maintenance and fixers process to spawn fixers.
9. The write tool sends `ghi-info` the actual proposed body, and sends an edited issue’s number as well, except that target number is omitted from the similarity comparison.
10. `ghi-info` must return exactly one of three one-line verdict shapes: a too-similar verdict naming one issue, a related verdict naming one or more issues, or an unrelated verdict.
11. A malformed reply is treated as if `ghi-info` were unavailable, so the system fails open.
12. For a too-similar verdict—meaning duplicate, overlapping, or conflicting content—the tool refuses the write and tells the author to read the named issue and merge the new content into it by editing it.
13. For a related-but-compatible verdict, the write continues and the response names issues the author should know.
14. For an unrelated verdict, the write succeeds without an extra relation warning.
15. Routing work—deciding between queue, GHI, pair document, or standalone Markdown—is outside `ghi-info`’s scope and belongs to `ghi-write` under the cited project-organization definitions.
16. Writing substantive issue or Markdown content is outside `ghi-info`’s scope.
17. Questions about anything beyond the issue corpus, including the wiki or code, receive the fixed `out-of-scope` response.
18. Whether an earlier ruling still applies must always be escalated to the user.

## The GHI mirror (ghi-mirror)

1. The mirror is a gitignored `<checkout>/ghi-mirror/` directory that `scripts/ghi-mirror-refresh.py` can regenerate on any machine.
2. The authoritative mirror copy is in `ghi-info`’s checkout on the Ubuntu box.
3. GitHub is authoritative; the mirror is only derived data.
4. The mirror has two files separated by issue state.
5. `issues-open.md` contains near-raw records for every open issue, including number, title, labels, update time, body, and comments.
6. `issues-closed.md` contains one line per closed issue with its number, title, close reason, and close date.
7. Routine relatedness decisions search the open-issues file.
8. The closed-issues file must also be searched before claiming that no issue covers a topic, because such an absence receipt is invalid unless both states were searched.
9. The closed file is also used when deliberately looking for precedent.
10. For each ask, refresh performs a delta: one `updated:>` query based on the newest mirrored entry retrieves changed issues and moves entries between the two files when their state changes.
11. Comments are fetched only for changed issues, with one call per changed issue.
12. At each session recycle, the mirror is rebuilt completely from a full fetch.
13. That full rebuild removes things a delta refresh cannot observe, such as deletions or changes lost at a same-second timestamp boundary, so those blind spots last no longer than the recycle interval.
14. Mirror writes use a temporary file followed by rename, making concurrent refreshes safe.
15. On 2026-08-07, against the live repository, fully retrieving all 45 issue bodies took 0.82 seconds, and an `updated:>` query returned exactly the issues changed after a timestamp.
16. Refresh also fetches `origin` and reads `git log origin/main`.
17. Pair-Markdown changes do not alter an issue timestamp, so this Git history feed brings those changes into the corpus once they land on `main`.
18. Each mirror entry records its update time and a freshness measure based on project activity since that issue last changed.
19. The aging measure is project activity rather than elapsed calendar time.
20. Supersession is represented by the literal marker `Superseded-by: #<n>`, written at the time of change by the author who knows about it.
21. The sweep searches for that marker and validates the targets it names.
22. Detecting two same-ground issues that lack this marker requires similarity judgment and therefore belongs to `ghi-info`; write-time adjudication is intended to catch new cases.

## The ghi-info session

1. `ghi-info` runs on the Ubuntu box in `~/agents/ghi-info`, following the box convention documented by issue 45.
2. Session metadata such as the session ID and counters is stored there.
3. Mac callers contact it through SSH using `scripts/launch-claude`, as described by that same issue.
4. A session exists only while it is actively handling a turn; otherwise its process exits.
5. The session ID, transcript, and mirror remain after the process exits.
6. This agent class has no idle resident process.
7. A cold start loads all of `issues-open.md` into context.
8. Closed issues enter context only when searched with `grep`.
9. A resumed session’s context can become outdated because the mirror refreshes every turn but text loaded into the model’s earlier context remains there.
10. The agent cannot reliably detect that context drift by itself, so the wrapper detects it for the agent as described in the ask path.
11. The wrapper recycles a session when the first of three script-observable conditions occurs: issues have closed since session birth, the stale-match rate reaches its trigger, or the transcript becomes too large.
12. The design intentionally recycles early because an unnecessary recycle only costs a cheap reload, whereas a late recycle can silently produce incorrect answers.

## The ask path (ghi-info-ask)

1. Any agent can run `scripts/ghi-info-ask.py`, and `ghi-write` also runs it in its first step.
2. The write tool’s adjudication uses this same wrapper, as ruled by the user on 2026-08-11.
3. Therefore the system has one stored-session mechanism and one refresh-and-resume mechanism, serving two request types.
4. The first wrapper step runs a delta mirror refresh.
5. The second step resumes the stored session, or cold-starts one if none exists or recycling has been triggered.
6. If another request currently holds the stored session, the wrapper starts a separate throwaway cold session instead, so no request waits and no requests share a transcript.
7. The third step sends the question and, for a resumed session, tells the agent which issue entries changed and requires it to reread them from the mirror before answering.
8. `--include-closed` explicitly identifies a closed-history question, such as a precedent or absence question.
9. For such a request, `ghi-info` searches the closed file, and closed issue references are expected in its answer.
10. The fourth step verifies every issue pointer returned by the agent against the mirror; this is a script-only factual check, not an agent judgment.
11. The agent never establishes that verification fact itself.
12. If the agent unexpectedly points to a closed issue, the wrapper sends exactly one drift notice that states the closure fact, says the mirror is current, instructs the agent to reread the closed entry including any supersession marker, and requests a corrected reading list.
13. Only one recheck occurs per ask.
14. During that recheck, the agent may read only mirror files and may not call GitHub.
15. The wrapper delivers any remaining returned pointers with accurate labels, such as `#31 (closed 2026-08-08)`.
16. Explanatory note lines are ordinary sentences rather than special syntax.
17. Unexpected closed pointers contribute to the stale-match recycle trigger, while deliberately requested closed pointers do not.
18. The wrapper has one overall timeout that fits within the hook’s timeout budget.
19. If that run is killed by the timeout, the system reports a specifically named failure.
20. The Ubuntu box uses two credentials: its `gh` login and a long-lived Claude token, because unattended interactive logins expire.
21. Nedsmessenger already uses this general pattern in its cited `ask_claude` implementation: headless `claude -p --resume` with the answer read from the exit stream.
22. Nedsmessenger uses three watchdogs, but this first version begins with only one overall timeout.
23. A failed ask must not prevent a write.
24. The fallback sequence is: ask `ghi-info`; search the local mirror, while acknowledging that it may be stale if not regenerated; use `gh` search; then proceed under normal `ghi-write` and artifact-lifecycle rules.
25. If an author discovers a relation that `ghi-info` missed, the author adds the cross-link while editing.
26. The next mirror refresh carries that link into the corpus, and answers reflect it after the next session reload.
27. The recycle triggers bound the resulting delay.

## The GHI write path (ghi-issue-write)

1. GHI authors ordinarily use `gh` to create, edit, and close issues, while comments are the one specifically taught exception.
2. A PreToolUse hook rewrites body-bearing `gh issue create` and `gh issue edit` commands into `scripts/ghi-issue-write.py` through `updatedInput`.
3. The cited hook documentation was checked on 2026-08-07 and confirmed both the rewrite mechanism and a configurable 600-second command-hook timeout.
4. The write tool’s internal `gh` subprocesses run below the hook layer.
5. `ghi-info` and fixer writes pass through this tool in the same way as any other author’s writes.
6. The first tool step checks that every in-repository path cited in the issue body resolves on `main`.
7. If a reference fails, the tool refuses the write and offers two alternatives: land the Markdown first, or file without the reference and later add it by edit after the Markdown lands.
8. No issue is required to cite Markdown; this check responds only to references the body actually contains.
9. The second step performs similarity adjudication, excluding the edited issue itself when appropriate.
10. If `ghi-info` cannot be reached, the tool allows the write without adjudication while still running its mechanical checks.
11. The third step performs the write through internal `gh`.
12. The tool reproduces `gh`’s output exactly and adds its own lines afterward.
13. The fourth step measures length, so authors do not count words themselves.
14. If a body exceeds the limit, the tool tells the author to retain a useful summary in the issue and move the detailed substance into the linked pair Markdown document, creating or updating it as needed.
15. The author performs that division because the author already holds the relevant context.
16. The author asks `ghi-info` to determine what should be linked.
17. It is an accepted residual that the issue may change after the verdict but before the write occurs.
18. `gh issue comment` and `close --comment` are denied with an explanatory response.
19. The reason is that a comment cannot be mechanically converted into the body edit required by the revision convention, because only the author knows where the content belongs and what it supersedes.
20. The response teaches two permitted paths: edit the body to integrate the content, or resubmit through the tool’s comment verb while naming a fixed-catalog event kind.
21. The allowed event kinds are instance outcome, completion, and ruling challenge.
22. The catalog grows only through an explicit ruling.
23. Whether completion should instead be represented solely by closing with a reason remains deferred to the `ghi-write` walk.
24. Losing one turn to an attempted forbidden comment is accepted.
25. Closing is a state change that requires a reason—either completed or not planned—and ordinary `close` and `reopen` commands pass through the hook unchanged.
26. Delta refresh carries those state changes into the mirror.
27. Non-body changes, including labels, title-only changes, and milestones, also pass through.
28. It is an accepted residual that renaming an issue might conceal a duplicate.
29. Deletion is denied; the author must close the issue instead because the record proceeds by additions and forward state rather than removal.
30. The denial includes the same override mechanism as every other denial.
31. Every denial path includes an audited override usable once, following the live-on-`main` `instruction-file-guard.py` pattern.
32. The user ruled on 2026-08-07 and reaffirmed on 2026-08-09 that this is a soft block rather than a hard block, and that known ways around the enumerated command coverage remain open.
33. Those open routes include `gh api`, MCP tools, and creative command quoting.
34. The rationale is a cooperative posture: enforcement is intended to catch mistakes, not stop deliberate evasion, matching the cited gatekeeper design’s stance.
35. Reviewers may reopen this concern only when override-audit evidence shows overrides being used to evade the tool rather than to address genuine breakage.
36. Writes that bypass the tool still enter through delta refresh, where the maintenance sweep can detect their symptoms.
37. Codex is included as the intended companion runtime.
38. Until build-time verification establishes an equivalent Codex hook, Codex-side writes remain among the accepted holes, with the skill serving as their preliminary safeguard.

## Maintenance and fixers

1. The maintenance sweep is script work using both feeds: it checks changed issue bodies for length, scans `Superseded-by:` markers, and verifies links in both directions.
2. The Markdown side of link checking comes from the repository checkout rather than the mirror.
3. Each finding spawns a one-shot focused fixer agent of the issue-26 class, launched according to issue 41, with a narrow brief such as updating a pair document after its issue changed.
4. Fixers use the normal write path and consult `ghi-info` just as any GHI author does.
5. `ghi-info` itself repairs links and never edits substantive content.
6. Pair-document staleness is checked only in one direction: an issue changed while its pair Markdown did not.
7. The reverse condition—a Markdown document landed on `main` while its issue has been unchanged—is intentionally not swept, by a user ruling on 2026-08-11.
8. Markdown-ahead state is a normal temporary stage in the pair sequence, and many Markdown edits do not require changing the issue-body summary.
9. An accepted residual remains: if an author lands the Markdown but never adds the issue citation, this sweep does not catch it.
10. The bidirectional link-integrity scan also cannot catch that omission, because a link that was never added has no broken target to detect.
11. If a fixer cannot proceed, it escalates by filing one issue labelled `draft` that states the blocker.
12. Selecting models and runtimes for `ghi-info`, fixers, and adjudication—between Claude or Codex and fable, opus, or sonnet—remains an empirical open question.

## The three-layer stack

1. `ghi-write` is a skill still being built, with its walk underway in the cited draft.
2. It activates when an author is about to file or edit a GHI and places desired behavior before the write: ask `ghi-info`, route according to state, edit instead of duplicating, keep the issue lean, and follow the pair sequence of writing the Markdown, landing it, then citing it.
3. The hook and tool are the correctness backstop when the skill does not activate.
4. On the covered write path, when `ghi-info` answers, a missed skill trigger costs efficiency rather than correctness—for example, a late merge catch or one failed comment attempt.
5. The fail-open interval and enumerated bypass holes are accepted residuals visible through the delta feed.
6. `CLAUDE.md` is only ambient documentation.
7. The cited issue 13 records this project’s experience that a written convention can lose to trained behavior.

## Division of labor

1. `ghi-mirror-refresh.py` performs fetching, formatting, delta merging, and state splitting at no model-call cost.
2. `ghi-issue-write.py` performs reference and length checks at no model-call cost.
3. Sweep scripts calculate freshness, scan markers, and check link integrity at no model-call cost.
4. `ghi-info-ask.py` performs answer post-checking and drift notices at no model-call cost, except that a recheck consumes one `ghi-info` call.
5. `ghi-info` performs judgment about which issues matter to a question and issues similarity verdicts, both of which cost a model call.
6. `ghi-info` performs cross-link repairs, its sole write class.
7. The GHI author, using `ghi-write`, handles routing, substantive body content, and the lean-split merge because that author already has the relevant context loaded.
8. One-shot focused fixers repair stale pair documents and over-length issue bodies discovered by the sweep.

## Prompts

1. Every prompt required by this design must be included verbatim, because the user ruled on 2026-08-09 and 2026-08-11 that a merely described prompt cannot be built or reviewed.
2. Every prompt must begin in a way understandable to a reader without prior context.
3. The Prompts section itself must receive markdown review before the design’s status can close.
4. Angle-bracket slots are populated by the script that invokes a prompt, never by the agent receiving it.
5. Every prompt is final: the two fixer briefs, drift notice, cold-start prompt with four request forms, resume ask, adjudication request, link-repair request, and write-tool replies.
6. The user ruled on 2026-08-11 that the link-repair request must be worded here rather than left for the implementation.
7. This section still awaits its required markdown-review pass before the design can close.

### Fixer brief — pair document behind its issue

1. The sweep fills every placeholder, including the reading list that it obtains by running `ghi-info-ask.py` before spawning the fixer.
2. The fixer does not invoke anything itself.
3. The recipient is a one-shot fixer created because a maintenance script found that one pair document in the project’s issue records has fallen behind its issue.
4. Its entire purpose is to update that one document and then exit.
5. Its assigned job is to update the specified pair document because the named issue changed on a stated date while the document has remained untouched since another stated date.
6. Before acting, it must read the named issue, its pair document, and the related issue list that `ghi-info` returned to the sweep.
7. It may change only the pair document.
8. It must commit that document change on its own branch with a message explaining what changed and why.
9. It must not write to any issue.
10. It must perform only the stated job.
11. It must stop and report `blocked` instead of editing if the necessary change would alter ruled text—identified by labels such as “user-ruled,” “boss-ruled,” “Accepted residual,” or a dated ruling—or would choose between two such ruled statements.
12. It must also stop and report `blocked` if the issue and document conflict in a way the record does not resolve.
13. It must likewise stop if it is not sure the change is correct.
14. Its final message must be exactly either `done: <what changed — files>` or `blocked: <what stopped you, quoting the text at issue>`.

### Fixer brief — issue body over the length limit

1. This brief uses the same slot-filling arrangement as the prior fixer brief.
2. Ruled text may be moved verbatim but may not be reworded; that is the user-ruled exception for handling such text.
3. The recipient is a one-shot fixer created because a maintenance script found one issue body in the project’s issue records exceeding the length limit.
4. Its entire purpose is to shorten that one body and then exit.
5. Its job is to reduce the named issue body, whose stated word count exceeds the stated limit, while retaining a useful body summary and moving the detailed substance into the named pair document, creating that document if necessary.
6. Before acting, it must read the named issue, its pair document even if absent, and the related issue list that `ghi-info` returned to the sweep.
7. It must make the body edit through normal `gh` usage.
8. It must commit document changes on its branch with a message that explains what changed and why.
9. Nothing removed from the issue body may disappear; all removed content must be preserved in the pair document.
10. Text marked as ruled—including “user-ruled,” “boss-ruled,” “Accepted residual,” or dated rulings—may change location only word-for-word.
11. The fixer must copy that ruled text verbatim into the pair document, and the body summary must cite the new location.
12. It must perform only the stated job.
13. It must stop and report `blocked` rather than edit if the change would reword ruled text or choose between two ruled statements.
14. Moving ruled text word-for-word is the sole permitted way to handle it.
15. It must also stop if the issue and document conflict in a way the record does not resolve.
16. It must stop if it is unsure the result is correct.
17. Its final message must be exactly either `done: <what changed — files, issue numbers>` or `blocked: <what stopped you, quoting the text at issue>`.

### Drift notice

1. The named issue closed on the supplied date.
2. The mirror is current, so the agent must reread that issue’s closed-file entry, including any `Superseded-by:` link, and return a corrected reading list.

### Cold-start prompt

1. This prompt is the first prompt in a fresh session.
2. A fresh session starts when there is no saved session or when a recycle trigger has fired, as defined by ask-path step 2.
3. The actual ask follows using the resume-ask wording.
4. The wrapper fills `<mirror-path>`.
5. `ghi-info` is the project’s knowledge agent for its GitHub-issue corpus.
6. Other agents send it one request at a time, and it answers from the corpus held in context and then stops.
7. It is the judgment layer; scripts perform every mechanical factual task, including fetching, counting, and verification, before a request reaches it.
8. Its knowledge source is the local mirror at the wrapper-provided path, which scripts regenerate and refresh before every request.
9. `issues-open.md` contains all open issues in full, including their number, title, labels, update time, body, and comments.
10. The agent must read the complete open-issues file before doing anything else.
11. `issues-closed.md` has one line for every closed issue.
12. The agent must not load all of the closed file; it may search it only when a request concerns closed history.
13. GitHub is the source of truth, but the mirror is the agent’s sole permitted view of GitHub.
14. The agent must never call GitHub through `gh`, an API, the web, or any other means.
15. Requests come in four forms.
16. In the reading-list form, the agent is asked what another agent should read before filing or editing an issue on a topic.
17. It must reply with only a bare list such as `read #13, #24, #31`, adding plain-sentence notes only when necessary.
18. It may include closed issues only if the request explicitly wants closed history.
19. Each closed pointer must be honestly labelled with its close date, such as `#31 (closed 2026-08-08)`.
20. In the adjudication form, the agent receives a draft issue body and is asked whether the corpus already covers it.
21. If the draft edits an existing issue, the request identifies that issue and the agent must exclude it from comparison.
22. The agent must reply with exactly one line and no other text.
23. A `verdict: too-similar #n` response means existing issue `#n` already covers the draft’s ground.
24. A `verdict: related #n,#m` response means the draft does not collide with those issues, but the author should know them.
25. A `verdict: unrelated` response means neither of those relations applies.
26. Any response in a different format is discarded.
27. In the correction form, the agent is told that an issue it cited has closed and is asked to redo that single judgment.
28. The script already established the closure fact using the refreshed mirror, so the agent must neither question nor verify it.
29. The agent must reread the named `issues-closed.md` entry, including any `Superseded-by:` link, and return a corrected reading list.
30. In the link-repair form, the agent is asked to repair a broken cross-reference found by the maintenance sweep.
31. The request identifies the defect, and the agent must repair exactly that link and nothing else.
32. Issue edits use normal `gh` operations.
33. Document-side changes must be committed on the agent’s branch with a commit message explaining what and why.
34. The response must be either `done: <the repair>` or `blocked: <what stopped you>`.
35. If asked about anything outside the issue corpus—including the wiki, code, or anything else—the agent must reply exactly `out-of-scope`.
36. The agent may never decide whether an old ruling still applies.
37. In that situation, it must reply as `escalate: <one sentence naming the ruling and the doubt>`.

### Resume ask prompt

1. This prompt is sent for every request for a reading list.
2. In a fresh session it follows the cold-start prompt.
3. In a resumed session it appears by itself, so it contains the reread preamble through which the wrapper informs the agent about drift.
4. The script either fills or removes each angle-bracket line as indicated.
5. The asker’s question is passed through exactly as asked and is never rewritten.
6. The prompt names the request form in the cold-start prompt’s own terminology so that the two prompts fit together.
7. When the session is resumed and refresh changed entries, the prompt names those issue entries and tells the agent to reread them in the mirror before answering.
8. Such an entry may have moved into `issues-closed.md`.
9. The agent is being asked for a reading list.
10. The question following that declaration is the asker’s verbatim question, such as what to read before proposing a retry policy for launch scripts.
11. When `--include-closed` is present, the prompt says that closed history is wanted.
12. The agent must then search `issues-closed.md`; closed pointers are expected and each must carry its close date.

### Adjudication request

1. The write tool sends this request before every body-bearing create or edit.
2. It uses the same wrapper as ordinary asks, so the changed-entries preamble follows the same rules and is omitted entirely for a cold start or an empty delta.
3. The draft body is transmitted without rewriting.
4. When the session is resumed and refresh changed entries, the prompt identifies those entries and directs the agent to reread them in the mirror before answering.
5. The agent is shown a draft issue body and asked whether the corpus already covers it.
6. For an edit, the prompt names the edited issue and requires the agent to omit that issue from comparison.
7. The subsequent draft body is verbatim.
8. The response must be exactly one line and must be one of `verdict: too-similar #n`, `verdict: related #n,#m`, or `verdict: unrelated`.

### Link-repair request

1. The sweep sends this request for every link-integrity finding.
2. It uses the same wrapper as the other request forms and therefore the same changed-entry preamble.
3. When the session is resumed and refresh changed entries, the prompt identifies those entries and requires rereading them in the mirror before answering.
4. The agent is asked to repair a link.
5. The sweep supplies one sentence describing the particular defect, such as an issue’s cited document failing to resolve on `main` or a document backlink naming the wrong issue.
6. The agent must repair only that link and nothing else.
7. Issue edits use normal `gh` operations.
8. Document changes must be committed on the agent’s branch with a message stating what changed and why.
9. The agent must respond with exactly either `done: <the repair>` or `blocked: <what stopped you>`.

### Write tool replies

1. Every denial response has the same structure: it says the action was refused, explains why, gives one or more forward paths, and ends with the audited one-use override line based on the live-on-`main` `instruction-file-guard.py` pattern.
2. The final two response templates are not denials; the tool appends them after a successful write, after relaying `gh`’s output exactly.
3. The reference-check refusal applies when a cited repository path does not resolve on `main`.
4. It tells the author that the cited path does not resolve and offers two routes: land the Markdown first and rerun the write, or file without the reference now and add it by edit after the Markdown lands.
5. The reference-check refusal ends with the audited one-use override line.
6. The too-similar refusal applies when adjudication returns that verdict.
7. It tells the author that the named issue already covers the subject, requires reading that issue, and directs the author to merge the proposed content into it by editing rather than creating another issue.
8. The too-similar refusal ends with the audited one-use override line.
9. The comment denial applies to `gh issue comment` and `close --comment`.
10. It says that comments are not retained as comments in this system.
11. The reason is that the revision convention requires a current issue body, and a tool cannot mechanically transform a comment into the needed body edit because only the author knows where its content belongs and what it supersedes.
12. It offers two paths: incorporate the material into the issue body by editing, or, if the material is a genuine event of instance outcome, completion, or ruling challenge, resubmit through the tool’s comment verb while naming that event kind.
13. The comment denial ends with the audited one-use override line.
14. The delete denial says issues are never deleted because the record is append-forward.
15. It directs the author to close the issue instead, stating either completed or not planned as the reason.
16. The delete denial ends with the audited one-use override line.
17. The related-verdict note is appended after a successful write when adjudication produced `related`.
18. It identifies the named related issues as ones the author should know.
19. The over-length instruction is appended when the landed body is over the limit.
20. It tells the author the body’s word count and the limit, requires retaining a good issue-body summary, and requires moving the detailed substance to the linked pair Markdown, creating or updating it.
21. It also directs the author to ask `ghi-info` what should be linked.

## Deliberately not in version 1

1. Version 1 excludes a vector or graph database because the context window itself serves as the database.
2. That capability returns if retrieval quality demonstrably worsens or the open issue corpus no longer fits in the context window.
3. Version 1 excludes a GitHub MCP server as the write interface because generic writes would carry none of this project’s checks.
4. It returns if a runtime whose writes cannot be hooked must become a write surface.
5. Version 1 excludes a hard block on raw `gh` writes because it would make one mechanism a single failure point for every issue write.
6. It returns if the override audit shows people using overrides to evade the system rather than to handle breakage.
7. Version 1 excludes deleting old closed issues on GitHub because their cost is context and attention, while the closed file stores them cheaply.
8. That policy changes if the closed-file approach no longer works sufficiently.
9. Version 1 excludes multi-watchdog supervision because one overall timeout is adequate at the one-question scale.
10. It returns if the single timeout proves insufficiently precise.
11. Version 1 excludes committing the mirror because its derived-data churn would clutter the history the user reads.
12. It returns if the project needs to search mirrors across checkouts and regenerating them separately on each machine cannot meet that need.

## Verify at build

1. The build must verify that an issue’s `updated` timestamp changes on close, reopen, and label changes just as it does on body edits and comments.
2. This behavior is documented but had not been tested in this design.
3. If it is not true, the full recycle-time mirror rewrite limits the delay.
4. The build must verify the undocumented combination of `updatedInput` and `additionalContext` in one PreToolUse response.
5. If that combination does not work, the tool response itself contains all needed information and context injection is simply unused.
6. The build must verify Codex pre-tool-hook equivalents because hooks exist but their relevant field names were not verified.
7. If no equivalent is available, Codex writes remain in the accepted-holes category.
8. The build must verify that the cross-reference timeline event can supply issue-to-issue backlinks, including its API shape.
9. If it cannot, backlinks are derived only by parsing issue bodies.
10. The build must verify that the tool’s appended lines after relayed `gh` output do not confuse authors.
11. If they do confuse authors, the reply format must change.
12. The build must verify that both Ubuntu-box credentials remain valid without attendance, since that box’s authentication has expired before.
13. The sweep checks credential validity and reports pending expiry before it causes a failure.
14. The build must measure comment-fetch cost at real scale; the one existing measurement was 0.42 seconds for one issue with comments.
15. Constants are named values at the top of the script that owns them, and version 1 has no configuration file.
16. Their initial values are to be tuned through live use.
17. `BODY_WORD_LIMIT` starts at 500, as ruled by the user on 2026-08-11.
18. This replaced the 400 value in the approved constants batch; neither number was derived from measurement, and both are starting guesses.
19. The write tool owns that constant, and the sweep imports it.
20. The session recycles after 20 closures since its birth.
21. The stale-match trigger is two stale matches among the last ten answers.
22. The transcript-size threshold will be set during the build using Nedsmessenger’s working values.
23. The ask timeout is five minutes and must fit within the hook budget.
24. There is at most one drift recheck for each ask.
