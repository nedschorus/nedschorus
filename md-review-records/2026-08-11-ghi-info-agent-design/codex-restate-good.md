<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=/Users/el/Projects/nedschorus/.claude/worktrees/linters-tool-usage-f8b0a0/docs/drafts/ghi-info-agent-design.md -->

## YAML frontmatter

1. The document considers its design decisions integrated into the text: decisions from the August 7, 2026 plan walkthrough and corrections from the August 9 Markdown review have been incorporated, but the document is still waiting for the user to walk through and approve the integration as a whole.

# ghi-info — the GHI knowledge agent (design)

## Walk order — integration walk

1. The first walkthrough topic is the already-reviewed core design: what `ghi-info` is, what it must do, how it answers, where it runs, how its mirror is structured, its refusal to become a mandatory gate, and the three layers that govern GHI work.
2. On August 9, the user confirmed that core in six parts; the user also ruled that the rule about correctness through deliberate over-specification belongs in the “Register” section of the skill-authoring checklist rather than in `CLAUDE.md`, that ruling was applied the same day, and this design makes no changes to `CLAUDE.md`.
3. The second walkthrough topic is the path for writing GHIs: the hook rewrite, the write tool’s four steps, treatment of comments, closing, and deletion, the deliberately soft block and its override, and the enforcement gaps the design accepts.
4. On August 9, the user approved that topic in three parts; the design records that reviewers tend to recommend turning soft blocks into hard blocks, so the decision to keep this block soft is now preserved as a searchable “Accepted residual,” protected by the standing rule about respecting prior reviewer counterparts, and may be raised again only if evidence satisfies the specified reopening condition—not merely as an ordinary review concern.
5. Two related decisions were also made: state changes that bypass the write tool ordinarily reach the mirror through delta refreshes, with complete mirror regeneration as a backup, and new mirror fields are added only through intentional one-line edits to the script rather than automatic schema growth.
6. The third walkthrough topic is the path for asking `ghi-info`: wrapper behavior, detection and correction of contextual drift, the `--include-closed` option, concurrency through disposable sessions, and the fallback sequence when asking fails.
7. On August 9, the user approved that topic in two parts and clarified the drift notice: after refreshing the mirror, the script itself establishes that an issue is closed; the notice gives that fact to the agent and asks it only to reconsider its judgment using mirror files, never to contact GitHub to verify the issue’s state.
8. The fourth walkthrough topic is session behavior and information currency: lifecycle, session-recycling conditions, the two refresh cadences, the freshness measure, and the `Superseded-by` convention.
9. The user approved that topic on August 9.
10. The fifth walkthrough topic is maintenance: the automated sweep, narrowly tasked fixer agents spawned from its findings, escalation behavior, and the unresolved choice of which model should perform each role.
11. The user approved that topic on August 11 after a round of drafting fixer instructions and a walkthrough written for a reader with no prior context.
12. The resulting rulings are these: the single generic fixer instruction became two templates, one for each kind of defect; the sweep chooses the applicable template; each fixer receives exactly one job; the sweep runs `scripts/ghi-info-ask.py` first and embeds the resulting reading list, so the fixer invokes no tools merely to discover what to read; “do only the job stated above” replaced the less definite “smallest change”; every prompt begins with enough explanation for a reader who has no context; `BODY_WORD_LIMIT` initially equals 500; staleness detection covers only the case in which an issue has advanced beyond its pair document; the failure to detect a document that was landed without the required issue citation is recorded as an accepted residual; ruled text removed from an overlong issue body must be copied verbatim into the pair document and cited by the shortened body; only rewording ruled text causes Template B to stop; and every prompt required by the design must appear verbatim in the Prompts section and receive its own Markdown review before the overall design can close.
13. At that moment, four prompts were still missing from the Prompts section.
14. The sixth walkthrough topic is closure: deciding where this design document will permanently live, creating the GHI that tracks implementation, and scheduling three follow-up matters—the resumed `ghi-write` walkthrough, review of the correctness rule, and revision of issue #26’s lifecycle design.
15. As of August 11, that close-out remained open, but the user had approved this sequence: draft the four missing prompts individually, Markdown-review the completed Prompts section, decide where this design belongs—with the current recommendation being to use it as the pair document for the implementation GHI—file that implementation GHI, and then queue the follow-up matters.
16. Prompt drafting was then underway, and each prompt’s “owed” or “final” label served as its individual completion marker.

## Opening description

1. The proposed way for nedschorus agents to work with GitHub issues consists of four pieces: a persistent knowledge role named `ghi-info` that reasons over the issue collection, a script-generated local copy of that collection, a write path whose hook redirects raw issue-writing commands through the project’s controlled write tool, and a `ghi-write` skill that supplies human-like judgment that scripts and hooks cannot provide.
2. In this document, “GHI author” means any agent currently filing a new issue or editing an existing one.
3. The detailed history of decisions is recorded in the linked plan draft and Markdown-review dispositions, while the separately linked gatekeeper draft preserves the rejected alternative in which one component would have acted as a universal gate.
4. The central design choice is to use a capable language-model agent rather than construct a vector database or graph database, because the entire current issue collection can fit in the agent’s context window; the cited measurement was 45 issues occupying approximately 109 KB.
5. Scripts perform deterministic operations such as fetching, formatting, measuring, and filtering, while model invocations are reserved for decisions requiring interpretation.

## What ghi-info is

1. `ghi-info` is intended to be the first implemented example of the “domain-knowledge agent” category defined in issue #26, where GitHub issues are the first domain proposed for such an agent.
2. It has three responsibilities.
3. Its first responsibility is answering requests for reading lists.
4. Before filing or editing a GHI, an author asks which existing issues it should read.
5. `ghi-info` answers with nothing more elaborate than a direct list such as “read #13, #24, #31.”
6. Its second responsibility is maintenance.
7. That maintenance covers links among issues and link correctness across the boundary between issues and Markdown documents in both directions: every issue-to-document path must resolve on the `main` branch, and every paired Markdown document must link back to the issue or issues it actually belongs to.
8. Repairing those links is the only category of write that `ghi-info` performs itself.
9. If it detects a problem involving substantive content rather than links—such as a pair document lagging behind its issue or an issue body exceeding the word limit—it causes a fixer agent to be created as described later.
10. Its third responsibility is adjudicating proposed writes.
11. Before writing, the write tool sends `ghi-info` the exact proposed body; for an edit, it also supplies the issue being edited and instructs `ghi-info` not to compare the draft against that same issue.
12. `ghi-info` must reply in one of three one-line forms: the draft is too similar to issue `#n`, it is compatible but related to issues `#n` and `#m`, or it is unrelated.
13. If the reply does not match the required syntax, the tool treats adjudication as unavailable and allows the write to continue.
14. The tool converts a valid verdict into guidance for the author.
15. “Too-similar” means the new material duplicates, overlaps, or conflicts with an existing issue; the tool refuses the new write and instructs the author to read the identified issue and merge the proposed content into that issue through an edit.
16. “Related” means the write is compatible and may proceed, but the author should become familiar with the named related issues.
17. “Unrelated” means the write succeeds without an additional relatedness warning.
18. `ghi-info` does not decide whether material belongs in a queue, a GHI, a paired document, or an unpaired Markdown file; that routing is a judgment assigned to `ghi-write`, using terms defined in the founding plan.
19. It also does not compose the substantive contents of issues or Markdown documents.
20. If asked about anything outside the issue corpus, including the wiki or source code, it returns the fixed response `out-of-scope`.
21. Any question about whether an old ruling remains binding must be escalated to the user rather than decided by `ghi-info`.

## The GHI mirror (ghi-mirror)

1. The mirror is a gitignored directory named `ghi-mirror` at the checkout root and can be regenerated on any machine by `scripts/ghi-mirror-refresh.py`.
2. The operationally authoritative generated copy is the one in `ghi-info`’s checkout on the designated box.
3. GitHub remains authoritative for the underlying issue data; the mirror is only a derived local representation.
4. The mirror has two files divided by issue state.
5. `issues-open.md` contains every open issue in a mostly unprocessed form, including its number, title, labels, update time, body, and comments.
6. `issues-closed.md` contains one line for each closed issue, recording its number, title, closing reason, and closing date.
7. Ordinary searches for related issues inspect the open file.
8. A claim that no issue covers a topic is considered unsupported unless both files were searched, and an intentional search for historical precedent likewise includes the closed file.
9. Before each ask, the script performs an incremental refresh.
10. It issues one `updated:>` query based on the newest update timestamp represented in the mirror and refetches issues reported as changed, moving them between the open and closed files when their state changes.
11. Comments are fetched only for issues identified as changed, requiring one additional call for each such issue.
12. Whenever the session is recycled, the script replaces the mirror using a complete fetch.
13. That full rewrite eventually removes changes an incremental query cannot detect, including deleted issues and issues missed at an equal-timestamp boundary, so such blind spots can last no longer than the interval between session recycles.
14. The script writes a temporary file and then renames it into place, which is intended to prevent concurrent refreshes from exposing partially written mirror files.
15. A measurement taken against the live repository on August 7 found that fetching all 45 issues with their bodies took 0.82 seconds and that `updated:>` returned exactly the issues changed since the supplied timestamp.
16. Refreshing also uses a second source of changes: it fetches the Git remote and reads the history of `origin/main`.
17. This second source is necessary because an edit to a pair Markdown document does not alter an issue’s GitHub update timestamp, and that document becomes part of the available corpus only after it reaches `main`.
18. Each issue entry records its update time and an activity-relative freshness value measuring how many project events have occurred since that issue last changed.
19. Thus project activity, rather than elapsed calendar time, determines how old an issue is considered.
20. Supersession is explicitly recorded with the literal text `Superseded-by: #<n>`, added when the change is made by the author who knows that the older issue was superseded.
21. The maintenance sweep finds those markers and confirms that their target issues exist and resolve correctly.
22. Deciding that two issues cover the same ground when neither has a supersession marker requires semantic similarity judgment, so that task belongs to `ghi-info`; the write-time check is expected to catch newly created cases, not necessarily discover every historical unmarked pair.

## The ghi-info session

1. `ghi-info` runs on the designated Ubuntu machine in `~/agents/ghi-info`, following the machine convention documented in issue #45.
2. Persistent wrapper information, including the session identifier and counters, is stored there.
3. Callers on Macs access it through SSH by way of `scripts/launch-claude`.
4. The agent process exists only while handling a turn and exits afterward, but its session identifier, transcript, and mirror survive between turns.
5. This agent class therefore has no running-but-idle state.
6. A new session loads all of `issues-open.md` into context, while closed issues are introduced into a turn only through targeted searches.
7. A resumed session can contain stale issue text: the mirror is refreshed before every turn, but previously loaded text remains in the model’s context, and the model cannot be trusted to notice the difference by itself.
8. The wrapper therefore detects relevant changes and tells the model about them through the ask-path mechanism.
9. The session is recycled as soon as any of three script-observable thresholds is reached: enough issues have closed since the session began, the recent stale-match rate is high enough, or the transcript has grown too large.
10. The system intentionally recycles sooner rather than later because an unnecessary recycle costs only a comparatively cheap context reload, while a delayed recycle can produce incorrect answers without any visible warning.

## The ask path (ghi-info-ask)

1. Any agent can run `scripts/ghi-info-ask.py`, and the `ghi-write` workflow also runs it during its first step.
2. The adjudication performed by the write tool uses the same wrapper, as the user ruled on August 11: there is one stored session and one refresh-and-resume mechanism, with two different forms of request.
3. The following operations occur in order.
4. First, the wrapper incrementally refreshes the mirror.
5. Second, it resumes the stored session unless no session exists or a recycle condition has fired, in which case it starts a fresh session.
6. If the stored session is already being used by another ask, the wrapper creates a disposable fresh session for the new ask instead of waiting or sharing a transcript between concurrent requests.
7. Third, it sends the user’s question and, when resuming, identifies any changed issue numbers and instructs the agent to reread those issues from the refreshed mirror before answering.
8. The `--include-closed` flag marks a request as intentionally concerned with closed history, such as precedent or proof of absence; for such a request, `ghi-info` searches the closed file and may legitimately return closed issues.
9. Fourth, the script checks every issue number in the answer against the mirror.
10. This check is deterministic script work, and the script—not the model—establishes each issue’s current state.
11. If the agent unexpectedly cites a closed issue, the wrapper sends one corrective notice that states the closing fact and asks the agent only to reconsider the reading list.
12. The notice means that issue `#31` closed on the stated date, that the mirror has just been refreshed, and that the agent must reread the issue’s closed-file entry—including any supersession marker—before supplying a corrected list.
13. There is at most one such reconsideration for each ask.
14. During it, the agent may read mirror files but must not query GitHub.
15. After that recheck, the wrapper returns whatever pointers remain, honestly labeling closed ones with their closing dates.
16. Any explanatory notes are ordinary prose sentences rather than another structured output format.
17. Unexpected closed pointers increment the stale-match measure used for recycling, while closed pointers expected because of `--include-closed` do not.
18. Fifth, the wrapper prints the final list.
19. The whole operation has a single timeout chosen to fit within the hook’s time allowance.
20. If the process is killed by that timeout, the system reports a specific, named failure rather than treating it as an unspecified error.
21. Authentication relies on two credentials stored on the box: the box’s GitHub CLI login and a durable Claude token, because unattended operation cannot rely on short-lived interactive login sessions.
22. The cited precedent is nedsmessenger’s live implementation, whose adapter invokes headless Claude with `-p --resume` and reads the answer from the process’s exit stream; although nedsmessenger uses three watchdogs, version 1 of this design begins with only one timeout.
23. Failure of an ask must never prevent a GHI write.
24. The fallback sequence is: try the agent ask; if that fails, search the local mirror even though it may be stale if regeneration failed; if necessary, search GitHub with `gh`; then continue under the ordinary `ghi-write` and artifact-lifecycle rules.
25. If an author notices a relationship `ghi-info` missed, the author corrects the corpus by adding the cross-link during the edit.
26. The following mirror refresh incorporates that link, and answers begin reflecting it after the next context reload, so the delay is limited by the recycling conditions rather than necessarily disappearing on the immediately following refresh.

## The GHI write path (ghi-issue-write)

1. Agents are trained to use `gh` for creating, editing, and closing GHIs, with comments as the one separately taught exception.
2. A `PreToolUse` hook at `.claude/hooks/ghi-issue-write-redirect.py`, modeled as a sibling of the instruction-file guard, rewrites body-bearing `gh issue create` and `gh issue edit` commands into invocations of `scripts/ghi-issue-write.py` by replacing the tool input through `updatedInput`.
3. The cited Claude documentation was used on August 7 to verify both that rewrite mechanism and the configurable 600-second timeout for command hooks.
4. When the write tool itself invokes `gh`, those invocations are subprocesses beneath the hook layer and therefore are not additional top-level tool calls subject to the same interception.
5. Writes performed by `ghi-info` or by fixer agents use this same tool-controlled path, just like writes from any other author.
6. Each write follows the sequence below.
7. First, every repository-relative path cited in the proposed body must exist on `main`.
8. If a path does not resolve, the tool refuses the write and gives two alternatives: land the Markdown document before retrying, or omit the reference now and add it through a later edit after the document lands.
9. An issue is not required to cite a Markdown document at all; this check applies only when the proposed body actually contains such a citation.
10. Second, `ghi-info` judges similarity as defined earlier and excludes the issue being edited from its comparison.
11. If `ghi-info` cannot be reached, the write continues without semantic adjudication, although the deterministic checks still execute.
12. Third, the tool performs the write internally through `gh`, reproduces `gh`’s output exactly, and places the tool’s own additional lines after that output.
13. Fourth, the tool measures the already-written body’s length, so authors never have to count words themselves.
14. If the body exceeds the limit, the tool instructs the author to preserve a useful summary in the issue and move or merge the full substance into its linked pair document, creating or updating that document as needed.
15. The author performs that division because the author already understands the material, and asks `ghi-info` which existing material or issue should be linked.
16. The design explicitly accepts a race in which another issue changes after the similarity verdict but before the write completes.
17. Direct `gh issue comment` and `close --comment` operations are denied and replaced with an explanatory response.
18. The reason is that the project’s revision convention expects ongoing information to be integrated into the issue body, but software cannot determine automatically where comment material belongs in that body or which earlier statement it supersedes.
19. The denial teaches two permitted routes: incorporate the content through an issue-body edit, or submit it through the controlled comment operation while naming one of the recognized event types—instance outcome, completion, or ruling challenge.
20. The event-type catalog may expand only through an explicit ruling, and the question of whether a “completion” event should instead be represented solely by closing with a reason remains deferred to the `ghi-write` walkthrough.
21. The design accepts that an author who first attempts a forbidden comment will lose one interaction turn before retrying correctly.
22. Closing is treated as a state change carrying either the reason `completed` or `not planned`.
23. Plain close and reopen commands are not rewritten by the hook, and their effects enter the mirror through incremental refresh.
24. Edits that do not change the body—including labels, title-only edits, and milestones—also pass through untouched; the accepted consequence is that a title change could conceal a duplicate from the guarded path.
25. Deletion is denied in favor of closure because the record is intended to preserve history by appending later states rather than erasing earlier ones, although the same override offered for other denials remains available.
26. Every refusal includes the audited, single-use override mechanism already used by the instruction-file guard on `main`.
27. The user explicitly ruled that this remains a soft rather than absolute block and that known bypasses remain available, including direct `gh api` use, MCP tools, or cleverly quoted commands.
28. Those gaps are accepted under a cooperative enforcement model in which safeguards are designed to prevent mistakes by participating agents, not defeat deliberate evasion.
29. Reviewers should raise the softness of the block again only if the override audit shows agents using overrides to evade the write tool rather than recover from genuine tool failure.
30. A write that bypasses the tool still appears in a later mirror delta, allowing the maintenance sweep to detect resulting symptoms even though it did not intercept the write itself.
31. Codex is intended to be a companion execution environment, but until equivalent pre-tool hooks are verified during implementation, Codex-originated writes are treated as another accepted bypass and rely on the skill for advance guidance.

## Maintenance and fixers

1. The maintenance sweep is deterministic script work using both the GitHub-issue and Git-history feeds.
2. It checks changed issue bodies for excessive length, validates `Superseded-by:` markers, and checks links in both directions, reading the Markdown side directly from the repository checkout rather than from the issue mirror.
3. Each finding creates a one-use fixer agent of the class described in issue #26 and launched according to issue #41, with an instruction narrowly describing one defect—for example, that issue #31 changed on one date while its pair document has not changed since another date.
4. Fixers use the ordinary write path and consult `ghi-info` under the same rules as any other GHI author.
5. `ghi-info` itself may correct links but must never revise substantive content.
6. Pair-document staleness is detected only when the issue has changed more recently than its paired document.
7. The opposite ordering—a document landing on `main` while its issue has not subsequently changed—is deliberately ignored under the user’s August 11 ruling.
8. The reason is that a document leading its issue is a normal intermediate stage of the required sequence and that the issue body is only a summary, so many legitimate document edits require no body change.
9. The accepted gap is that an author may land a document and then fail to add the promised citation to the issue without this sweep detecting the omission.
10. The link-integrity scan also cannot detect that case, because a link that was never added cannot be invalid or broken; there is simply nothing for the scan to test.
11. If a fixer cannot complete its job, it escalates by filing one issue labeled `draft` that states what blocked the repair.
12. The best model and runtime for each role—knowledge answering, fixing, and adjudication, using Claude or Codex and fable, opus, or sonnet—remain undecided and are to be chosen from observed performance.

## The three-layer stack

1. The first layer is the in-development `ghi-write` skill, whose walkthrough is still in progress.
2. It activates when an author is about to file or edit a GHI and teaches the desired behavior in advance: ask `ghi-info`, route the material according to its state, edit existing issues instead of duplicating them, keep issue bodies concise, and follow the pair sequence of writing the Markdown document, landing it, and only then citing it.
3. The second layer is the hook and write tool, which provide a correctness backstop when the skill fails to activate.
4. On paths the hook covers and while `ghi-info` is available, missing the skill mainly wastes effort—for example, discovering a required merge late or forcing one retry after an attempted comment.
5. The fail-open interval and commands outside the hook’s enumeration remain accepted gaps, although their resulting writes become visible in mirror deltas.
6. The third layer is `CLAUDE.md`, which serves only as general background documentation.
7. Issue #13 is cited as this project’s evidence that merely writing down a convention is less effective than training the desired behavior.

## Division of labor

1. `ghi-mirror-refresh.py` owns fetching, formatting, incremental merging, and separating open from closed state; “free” means this needs no model call, not that it consumes literally no computing resources.
2. `ghi-issue-write.py` owns reference validation and body-length checks, also without a model call.
3. Sweep scripts calculate freshness, validate supersession markers, and scan link integrity without model judgment.
4. `ghi-info-ask.py` validates returned pointers and issues drift notices; the validation is script work, although an actual drift recheck costs one additional call to `ghi-info`.
5. `ghi-info` decides which issues are relevant to a question and supplies similarity verdicts, costing a model call.
6. `ghi-info` also owns cross-link repair, which is its only permitted category of write.
7. The GHI author, guided by `ghi-write`, owns routing, substantive body content, and merging a concise issue summary with a fuller pair document, using context the author already has.
8. Individually spawned fixer agents repair stale pair documents and overlong issue bodies found by the sweep, with one single-purpose agent per finding.

## Prompts

1. This section is intended to contain the exact text of every prompt on which the design depends, because a prompt described only abstractly cannot be implemented or reviewed precisely.
2. Every prompt must explain enough for a recipient with no prior context.
3. The Prompts section must pass a separate Markdown review before the overall design status can close.
4. Text inside angle brackets denotes a slot filled by the calling script, not by the agent receiving the prompt.
5. At the document’s current state, all required prompts are marked final: two fixer instructions, the drift correction, the cold-start instruction covering four request forms, the resumed-session ask, the adjudication request, the link-repair request, and the write tool’s responses.
6. Despite being drafted and marked final, this section is still awaiting the required Markdown-review pass.

### Fixer brief — pair document behind its issue

1. Before spawning this fixer, the sweep fills every variable slot and obtains the reading list by running `ghi-info-ask.py` itself, so the fixer is not expected to invoke anything to discover its inputs.
2. The recipient is a disposable fixer agent created because a maintenance script found that a paired document is less current than its GitHub issue.
3. Its sole purpose is to update that one document and then terminate.
4. The concrete job states that issue `#<n>` changed on the first supplied date while its pair document at `<path>` has not changed since the second supplied date.
5. The required result is for that document to represent the issue’s current state.
6. Before editing, the fixer must read the named issue, the named pair document, and the related issues already selected by `ghi-info`.
7. The following items are mandatory rules.
8. The fixer may modify only the pair document, must commit that modification on its branch with a commit message explaining both the change and its reason, and must not write to any issue.
9. It must perform only the explicitly stated update.
10. The following conditions require it to stop without editing and report that it is blocked.
11. It must stop if completing the update would alter language marked as a ruling—including `user-ruled`, `boss-ruled`, `Accepted residual`, or another dated ruling—or require choosing which of two ruled statements should prevail.
12. It must stop if the issue and document conflict and the existing record does not resolve the conflict.
13. It must stop if it is uncertain that the proposed change is correct.
14. Its final response must use exactly one of the two permitted forms.
15. On success, it must begin with `done:` and identify what changed and which files were involved.
16. On failure, it must begin with `blocked:` and identify the obstacle while quoting the disputed text.

### Fixer brief — issue body over the length limit

1. This prompt uses the same rule as the preceding prompt: the sweep, rather than the fixer, fills every slot.
2. Ruled text has one special treatment established by the user: it may be relocated from the issue body to the pair document, but its wording may not change.
3. The recipient is a disposable fixer created because a maintenance script found that one issue body exceeded the project’s length limit.
4. Its sole purpose is to shorten that one issue body and then terminate.
5. The concrete job identifies the issue, its measured word count, the applicable limit, and the path of its pair document.
6. The required result is a useful summary in the issue body and the full substance merged into the pair document, which the fixer must create if it does not exist.
7. Before editing, the fixer must read the issue, the pair document if one exists, and the related issues already selected by `ghi-info`.
8. The following items are mandatory rules.
9. The issue-body edit must be submitted through the ordinary `gh` path, while document changes must be committed on the fixer’s branch with a message explaining what changed and why.
10. Every piece of material removed from the issue body must be preserved in the pair document.
11. Any text marked as ruled must be copied word-for-word into the pair document, and the shortened issue summary must cite the new location of that text.
12. The fixer must perform only this stated shortening-and-transfer job.
13. The following conditions require it to stop without editing and report that it is blocked.
14. It must stop if the change would reword ruled text or require choosing between conflicting ruled statements; verbatim relocation is expressly allowed and is the only permissible treatment of such text.
15. It must stop if the issue and document conflict and the existing record does not resolve the conflict.
16. It must stop if it is uncertain that the proposed change is correct.
17. Its final response must use exactly one of the two permitted forms.
18. On success, it must begin with `done:` and identify the changes, files, and issue numbers.
19. On failure, it must begin with `blocked:` and identify the obstacle while quoting the disputed text.

### Drift notice

1. The notice tells `ghi-info` that issue `#<n>` closed on the supplied date and that the local mirror is current; `ghi-info` must accept that state as established, reread the closed-file entry and any supersession link, and return a corrected reading list.

### Cold-start prompt

1. This prompt is the first message sent to a newly created session.
2. Such a cold start occurs when no stored session exists or when a recycling condition has fired.
3. The actual request is sent afterward using the wording defined for resumed asks.
4. The wrapper supplies the value of `<mirror-path>`.
5. The prompt assigns the agent the identity `ghi-info`, the project’s knowledge agent for the GitHub-issue corpus.
6. Other agents will send one request at a time, and `ghi-info` must answer from the corpus currently in context and then stop.
7. Its role is interpretive judgment; scripts have already performed deterministic tasks such as fetching, counting, and verification before each request reaches it.
8. Its information source is the local mirror at the supplied path, which scripts regenerate and refresh before every request.
9. `issues-open.md` contains the complete listed representation of every open issue, and the agent must read the entire file immediately before doing anything else.
10. `issues-closed.md` contains one line per closed issue and must not be loaded wholesale; the agent searches it only when a request explicitly concerns closed history.
11. GitHub is authoritative, but the local mirror is the agent’s only permitted representation of GitHub.
12. The agent must never use `gh`, an API, or the web to contact GitHub directly.
13. Requests can take four forms.
14. The first form asks which issues an author should read before filing or editing an issue on a particular topic.
15. The answer must be a bare `read #…` list, with ordinary explanatory note lines only when necessary.
16. Closed issues may appear only when the request explicitly asks for closed history, and every such issue must be labeled with its closing date.
17. The second form supplies a draft issue body and asks whether an existing issue already covers it.
18. For an edit, the request identifies the issue being edited, and the agent must exclude that issue from comparison.
19. The answer must consist of exactly one line in one of the three specified verdict formats, with no additional text.
20. `too-similar #n` means the existing issue already covers the draft’s ground and identifies that issue.
21. `related #n,#m` means there is no collision but the author should know the named issues, while `unrelated` means no relevant collision or relation was found.
22. Any response with a different structure is discarded.
23. The third form states a fact correcting the previous answer—specifically, that a cited issue has closed—and asks the agent to redo only that judgment.
24. Because the script has already established the fact from the refreshed mirror, the agent must neither dispute nor independently verify it.
25. It must reread the specified closed-file entry and any supersession link, then return a corrected reading list.
26. The fourth form asks the agent to repair one broken cross-reference discovered by the maintenance sweep.
27. The request describes the exact defect, and the agent must repair only that link.
28. An issue-side change uses the normal `gh` write path, while a document-side change is committed on the agent’s branch with a message stating what changed and why.
29. The response must begin either with `done:` followed by the repair or `blocked:` followed by the obstacle.
30. The following statements define the agent’s boundaries.
31. For any request outside the issue corpus—including the wiki or code—it must reply with exactly `out-of-scope`.
32. The agent must never decide whether an old ruling still applies.
33. Instead, it must respond in the form `escalate:` followed by one sentence identifying the ruling and explaining the uncertainty.

### Resume ask prompt

1. This prompt is sent for every reading-list request.
2. In a new session it follows the cold-start prompt; in a resumed session it appears by itself and therefore contains the reminder to reread changed entries that the model could not reliably detect on its own.
3. The script either fills each conditional angle-bracket line or removes that entire line, depending on whether its condition applies.
4. The caller’s question is transmitted exactly as written rather than paraphrased.
5. The prompt identifies the request using the same “reading list” terminology introduced in the cold-start prompt, so the two instructions refer to the same request category.
6. On a resumed session with changed mirror entries, the prompt lists their issue numbers and instructs the agent to reread them before answering because an entry may now be in the closed file.
7. It then states that this is a reading-list request and includes the caller’s original question verbatim.
8. When `--include-closed` is present, it additionally says that closed history is intentionally requested, directs the agent to search the closed file, and requires each closed result to carry its closing date.

### Adjudication request

1. The write tool sends this request before every create or edit containing an issue body.
2. It uses the same wrapper as reading-list asks, so a resumed session with changed entries receives the same reread preamble, while a cold start or refresh with no changes omits that preamble entirely.
3. The proposed body is transmitted without alteration.
4. If no reply arrives or the reply has the wrong structure, the write proceeds without semantic adjudication.
5. That fail-open behavior is implemented by the tool and is not an instruction the model is being asked to apply.
6. When applicable, the preamble lists entries changed since the prior request and instructs the agent to reread them.
7. The main request says that the agent is receiving a draft issue body and must decide whether the corpus already covers it.
8. For an edit, the prompt identifies the target issue and instructs the agent to exclude that issue from comparison.
9. The prompt labels the following inserted text as the verbatim draft body.
10. The draft-body slot contains the exact proposed body.
11. The agent must reply with exactly one of the three specified one-line verdict formats.

### Link-repair request

1. The sweep sends this request for each link-integrity defect, and these repairs constitute `ghi-info`’s only permitted write category.
2. It uses the same wrapper as other requests and therefore uses the same changed-entry preamble when applicable.
3. Its success-or-blocked response format intentionally matches the fixer prompts.
4. When applicable, the preamble lists mirror entries changed since the previous request and requires the agent to reread them.
5. The main request identifies one broken link in a sentence supplied by the sweep, such as an issue citing a document absent from `main` or a document linking back to the wrong issue.
6. The agent must fix exactly that link and nothing else; issue changes use the normal `gh` path, document changes are committed on its branch with a message explaining what and why, and the reply must use exactly either `done: <repair>` or `blocked: <obstacle>`.

### Write tool replies

1. Every refusal follows the same overall structure: it says the write was refused, explains why, identifies one or more permitted next actions, and ends with an audited single-use override line following the live instruction-file-guard pattern.
2. The relatedness and over-length messages are not refusals; the tool appends them after a successful write and after reproducing `gh`’s own output exactly.

#### Reference-check refusal

1. The write is refused because the body cites a repository path that does not exist on `main`; the author may either land the Markdown document and retry or remove the reference, file now, and add the reference through an edit after the document lands.
2. The response then includes the standard audited single-use override line.

#### Too-similar refusal

1. The write is refused because the identified existing issue already covers the proposed ground; the author must read that issue and merge the new material into it through an edit rather than file a separate issue.
2. The response then includes the standard audited single-use override line.

#### Comment denial

1. The attempted comment is refused because this project ordinarily integrates revisions into the current issue body, and software cannot infer where the comment belongs or what earlier material it supersedes.
2. The author may either incorporate the material into the issue body through an edit or, if it records a genuine event of one of the three named kinds, resubmit it using the controlled comment operation and explicitly name that event kind.
3. The response then includes the standard audited single-use override line.

#### Delete denial

1. Deletion is refused because issue history is intended to move forward by retaining prior records; the author must instead close the issue with either the reason `completed` or `not planned`.
2. The response then includes the standard audited single-use override line.

#### Related-verdict note

1. After a successful write judged related, the tool tells the author which related issues are worth knowing.

#### Over-length instruction

1. After a successful write whose body exceeds the limit, the tool reports the measured count and limit, instructs the author to retain a useful body summary and move the substance into a newly created or existing linked pair document, and tells the author to ask `ghi-info` what should be linked.

## Deliberately not in version 1

1. A vector or graph database is omitted because the model’s context window currently serves as the database; it should be reconsidered if retrieval quality measurably declines or the open-issue collection no longer fits.
2. A GitHub MCP server is not used as the normal write interface because generic MCP writes would omit the project’s checks; it should be reconsidered as a write surface if a runtime cannot have its writes intercepted by hooks.
3. A hard prohibition on raw `gh` writes is omitted because it would create a single failure point for all issue writes; it should be reconsidered if override records show deliberate avoidance rather than legitimate recovery from breakage.
4. Old closed issues are not purged from GitHub because their primary cost is contextual attention and the compact closed file handles them cheaply; purging should be reconsidered if that compact-file approach becomes inadequate.
5. Multiple watchdog processes are omitted because one overall timeout is considered sufficient for a single-question operation; multiple watchdogs should return if one timeout proves too coarse to distinguish useful failure modes.
6. The mirror is not committed because regenerated derived data would add noise to the repository history read by the user; committing it should be reconsidered if people need to search the mirror across checkouts and per-machine regeneration cannot satisfy that need.

## Verify at build

1. Every item below must be tested during implementation and has a stated response if the assumption fails.
2. Verify that an issue’s `updated` timestamp changes after close, reopen, and label operations just as it does after body edits and comments; this behavior is documented but was not tested for this design, and if it is false, complete regeneration at session recycle remains the mechanism that bounds the resulting delay.
3. Verify that a single `PreToolUse` response can contain both `updatedInput` and `additionalContext`, because that combination is undocumented; if it cannot, the write tool’s own response must carry all necessary information and context injection will simply not be used.
4. Verify Codex’s equivalents to pre-tool hooks, since hooks exist but the relevant field names have not been checked; if equivalent interception cannot be implemented, Codex writes remain an accepted bypass.
5. Verify the API representation of cross-reference timeline events before using them as the source of issue-to-issue backlinks; if that source is unsuitable, derive backlinks solely by parsing issue bodies.
6. Verify that authors understand the write tool’s additional lines after the verbatim `gh` output; if those lines cause confusion, change their presentation.
7. Verify that both credentials on the box remain valid during unattended operation, because authentication there has expired previously; the sweep must test validity and report impending or actual expiration before it disrupts work.
8. Measure comment-fetch cost at realistic scale; the only measurement currently stated is 0.42 seconds for one issue containing comments, and this item does not specify a particular failure response.
9. Configuration values live as named constants at the beginning of the script that owns each behavior; version 1 has no separate configuration file.
10. The initial `BODY_WORD_LIMIT` is 500, following the August 11 ruling; this replaces an earlier approved value of 400, neither number was empirically derived, both were provisional guesses, the write tool owns the constant, and the sweep imports it.
11. A session recycles after 20 issues have closed since its birth.
12. The stale-match threshold is two stale matches among the latest ten answers.
13. The transcript-size threshold will be selected during implementation using working values from nedsmessenger.
14. An ask has a five-minute timeout that must fit inside the hook’s larger time budget.
15. Each ask permits only one drift-correction recheck.
