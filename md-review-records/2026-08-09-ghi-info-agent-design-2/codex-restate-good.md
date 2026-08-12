<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=/Users/el/Projects/nedschorus/.claude/worktrees/shared-conversation-discussion-eb34e2/docs/drafts/ghi-info-agent-design.md -->

## Frontmatter

1. The document’s design is waiting for the user to review it interactively, beginning with a Markdown review before any later kind of walkthrough or disposition.

# ghi-info — the GHI knowledge agent (design)

1. This document describes a proposed way for agents in the nedschorus project to work with GitHub issues: a knowledge-focused agent retains continuity over the issue collection; scripts maintain a local copy of that collection; a dedicated tool handles writes; hooks redirect direct issue-writing commands through that tool; and a skill named `ghi-write` supplies the contextual judgment that the scripts, hooks, and tool cannot supply mechanically.

2. The decisions represented here were made on August 7, 2026, and their history—including the user’s disposition of each item—is recorded in `ghi-info-agent-plan-draft.md`; an earlier design based on putting all writes through a single gate was rejected, but remains documented in `ghi-gatekeeper-plan-draft.md`.

3. The central design choice is to let a current-generation language-model agent reason directly over the GitHub-issue corpus, because the corpus is small enough to fit within the model’s context window, rather than constructing a separate vector-search database or graph database.

4. Tasks that can be performed deterministically—fetching, formatting, measuring, and filtering—are assigned to scripts and consume no model tokens; model-token use is reserved for decisions requiring interpretation or judgment. “For free” means free of agent-token cost, not necessarily free of all computation or monetary cost.

## What ghi-info is

1. `ghi-info` is intended to be the first concrete implementation of the “domain knowledge agent” category defined in `26-dynamic-agent-team-model.md`, where GitHub issues are the first domain proposed for such an agent.

2. It has three responsibilities.

3. Its first responsibility is to answer requests for relevant reading.

4. Before another agent creates or edits an issue, that agent asks `ghi-info` which existing issues it should read.

5. `ghi-info` responds only with issue references, such as “read #13, #24, #31,” and does not add explanations of why those issues matter or summaries of their contents.

6. An incorrect issue pointer creates an obvious and limited failure because the requesting agent reads one irrelevant issue and can see the mismatch; an incorrect prose summary can be subtly misleading without being recognized as wrong, and it makes `ghi-info` reinterpret or rewrite the underlying material instead of merely directing the requester to it.

7. Explanations of why each issue was selected are considered unnecessary information because the requesting agent is expected to read the selected issues itself.

8. Its second responsibility is to maintain the reference graph.

9. This graph includes links among issues and the integrity of links crossing between GitHub issues and repository Markdown documents in both directions: every reference from a GitHub issue to a Markdown file must resolve to an existing target, and every corresponding Markdown document must link back to the correct issue or issues. I take “pair MD” here to mean a repository Markdown document paired with one or more GitHub issues, although the exact pairing model is not defined in this sentence.

10. Editing cross-links is the only category of writing that `ghi-info` itself is allowed to perform.

11. Its third responsibility is to judge proposed issue writes.

12. Before a new or edited issue body is actually written, the write tool described later sends the complete proposed body to `ghi-info` for comparison with the issue corpus.

13. `ghi-info` returns one of three judgments: if the proposed write is duplicative, substantially overlapping, or conflicting with an existing issue, the tool rejects it and tells the writer to reconsider the write and read the relevant existing material; if it is connected to existing issues but can coexist with them, the write is allowed and the writer is told which related issues it should understand; if it has no relevant relationship to existing issues, it is written normally without related-reading guidance.

14. `ghi-info` does not decide whether material belongs in a queue, a GitHub issue, a paired Markdown document, or an unpaired Markdown document—that decision belongs to the `ghi-write` skill; it does not author the substantive contents of issues or Markdown files; and it bases its answers only on the issue corpus, explicitly admitting when a question requires knowledge of the wiki or source code rather than attempting to infer an answer.

15. If a paired Markdown document has become inconsistent with its issue, or an issue body has become longer than the permitted limit without an agent currently performing a write, `ghi-info` reports the problem but does not repair it; the next agent that has the relevant authoring context is responsible for deciding and making the correction.

## The mirror

1. The design includes a local Markdown-formatted copy of the GitHub-issue corpus that is produced and updated entirely by scripts, so the agent does not spend model effort retrieving pages, following pagination, or converting API results into a usable format.

2. GitHub remains authoritative, while the local mirror is disposable data derived from GitHub.

3. The mirror consists of two files separated according to issue state: `issues-open.md` contains every open issue in a mostly unprocessed form, including its number, title, labels, last-updated time, body, and comments; `issues-closed.md` represents each closed issue with one compressed line organized according to some tiering scheme, although the tiers themselves are not specified here.

4. The physical separation expresses the expected workflow: ordinary searches for related work inspect only the open-issue file, while the closed-issue file is also searched when someone intends to claim that no issue covers a subject—because a rejected or previously attempted idea may appear only among closed issues—or when someone deliberately wants historical precedent.

5. The author expects closed issues to be relevant to roughly one search out of fifty; putting them in a separate file automatically excludes them from the other roughly forty-nine searches, without relying on an agent to remember an instruction to ignore them.

6. Each checkout stores the mirror at a conventional location excluded from Git, and the provided script can regenerate it independently on any machine.

7. Because the mirror is not committed, routine changes to this derived representation do not clutter the repository’s commit history.

8. Incremental refresh uses a single `gh` search whose `updated:>` filter is set to the newest timestamp already present in the mirror; the script retrieves issues changed after that point and transfers their entries between the open and closed files when their state changes.

9. A live-repository test on August 7, 2026, found that retrieving all 45 issues and their bodies took 0.82 seconds and produced approximately 109 KB, and that `updated:>` returned exactly the issues modified after a supplied timestamp.

10. A separate input based on Git history since the previous refresh detects changes to paired Markdown files, because editing such a file does not alter any GitHub issue’s timestamp and therefore cannot be detected by the GitHub issue-update search.

11. Because an agent cannot reliably determine from raw dates which material is current relative to recent project activity, every mirror entry includes both its ordinary update timestamp and a relative-freshness measure representing how much the project has changed since that issue last changed; this measure treats project activity, rather than elapsed calendar time, as the relevant form of aging.

12. When an issue is superseded, the agent that knows about the change explicitly adds a searchable marker naming the successor at the time of the change; because the marker follows a recognizable pattern, a script can flag the suspicious condition in which two open issues claim the same subject area but neither identifies the other as related or superseding. The document does not specify the exact mechanical test for deciding that two issues “claim the same ground.”

## The session

1. `ghi-info` runs on the Ubuntu machine, using `~/agents/ghi-info` in accordance with that machine’s directory convention, because agent workloads are being consolidated there.

2. Agents running on the Mac contact it through SSH using the communication path established by the `launch-claude` work.

3. The agent process exists only while it is handling a turn and exits afterward; continuity comes from a persisted session identifier, transcript, and issue mirror, not from a continuously running process.

4. Calling such a process “idle” would be inaccurate because an idle process is still alive and waiting, as in an interactive session or watcher, whereas this design starts or resumes a headless session separately for each question and leaves no process running between questions.

5. The model context is entirely focused on open issues.

6. When there is no resumable session, the wrapper loads all of `issues-open.md` into the new context, while closed issues are added to an individual turn only when a specific search requires them.

7. A resumed model context becomes increasingly inconsistent with current issue state: although the disk mirror is updated for every turn, material previously loaded into the model’s context remains there, so an issue that has since closed may still appear to the model as open, and the model has no direct way to detect that change.

8. To limit that drift, the wrapper discards and rebuilds the session when the first of three conditions occurs: the number of issues closed since the session began exceeds a configured threshold; the answer post-check described later has recently found closed-issue pointers at too high a rate; or the transcript has become too large.

9. The thresholds for all three conditions are configuration constants whose values will be adjusted based on observed production behavior.

10. Because refreshing requires only a sub-second fetch and one model turn to load the data, the policy favors recycling sooner rather than later: unnecessary recycling costs one inexpensive reload, whereas delayed recycling can produce incorrect answers without making the error visible.

## The ask

1. Any agent—and the first step of `ghi-write`—can run one wrapper script to ask `ghi-info` a question.

2. For each request, the wrapper performs this sequence: incrementally refresh the mirror so that every invocation starts with current disk data; resume the stored model session unless no session exists or a recycling condition has occurred; on a resumed session, prompt the model with both the question and the numbers of issues changed since the previous turn; check the resulting answer and remove any pointer that now refers to a closed issue, adding a note before returning the answer to the requester; count those removals for the second recycling trigger; and print the requested pointer list. The text says both that the removal produces a note and that the wrapper prints a bare list, but it does not specify whether the note is separate diagnostic output or an exception to the bare-list rule.

3. The whole operation has one timeout, and termination caused by that timeout is reported as a specifically named failure rather than as an ambiguous empty or partial result.

4. Authentication uses a persistent token installed on the Ubuntu machine because authentication created by an interactive login eventually expires and there is no human assigned to renew it.

5. The session-resumption mechanism is presented as already demonstrated in practice: nedsmessenger’s `adapter.py`, specifically `ask_claude`, runs headless `claude -p --resume` commands separately for each conversation, reads the answer from the process’s exit stream, and uses watchdog logic to terminate stuck executions.

6. Failure of a `ghi-info` request must never prevent an issue write.

7. If the agent request fails, the writer next searches the local mirror with `grep`, then searches GitHub with `gh`, and after those fallbacks continues under the normal issue-writing rules rather than stopping indefinitely.

8. Incorrect pointers are readily detectable, while the remaining possibility that all search stages fail to return a relevant issue is consciously tolerated because the system assumes cooperative agents rather than adversarial ones.

9. No explicit error-reporting channel back to `ghi-info` is required: if a writer discovers a relationship that `ghi-info` omitted, that writer adds the appropriate cross-link during its edit, after which the next mirror refresh incorporates the corrected relationship into the corpus from which future answers are derived.

## The write path

1. Agents continue issuing the ordinary `gh` commands they were trained to use for GitHub issues; hooks and supporting machinery redirect those actions as needed, so agents do not have to learn a different command interface.

2. For issue creation and editing, a `PreToolUse` hook replaces the proposed `gh issue create` or `gh issue edit` command with an invocation of the project’s dedicated write tool by returning `updatedInput`; the author verified both this rewrite-and-execute behavior and a configurable 600-second command-hook timeout against the linked Claude hooks documentation on August 7, 2026.

3. The dedicated tool mechanically checks body length and whether referenced targets can be opened, asks `ghi-info` to judge the actual proposed body, performs the write internally through `gh`, and formats its response so that an agent expecting the result of its original `gh` command will not misunderstand what happened.

4. If `ghi-info` cannot be reached, the tool allows the issue write to proceed without `ghi-info`’s checks.

5. Agents do not manually count words because the write tool measures the body after the write has occurred.

6. If the body exceeds the configured limit, the writer is immediately instructed to retain a useful summary in the issue body and move the detailed substance into a linked paired Markdown document, either by creating that document or updating the existing one.

7. The original writer performs this split because it still has the necessary understanding of the content, while `ghi-info` contributes broader corpus knowledge by identifying what existing material should be linked.

8. Issue bodies are intended to remain short combinations of summaries and links, while the detailed material resides in repository Markdown that ordinary text search can inspect; the phrase “one kind of document, at two depths” means the issue and its paired Markdown both represent the same work at different levels of detail, though they are technically different storage formats and locations.

9. Direct `gh issue comment` commands are rejected with an explanatory response because a hook cannot safely transform arbitrary proposed comment text into the body revision required by the project’s convention: only the agent proposing the comment knows where in the body the information belongs and which earlier text it replaces.

10. The rejection explains two permitted alternatives: incorporate the material into the issue body with an edit, or, if it records a genuinely new event allowed by the convention, submit it using the dedicated tool’s comment operation and identify its event type from a fixed catalog consisting currently of instance outcome, completion, and ruling challenge; new event types may be added only through an explicit ruling.

11. Losing one agent turn when a comment attempt is rejected is considered an acceptable cost.

12. One part of the event catalog remains deliberately unresolved until the `ghi-write` walkthrough: “completion” might be represented only as closing an issue with a stated reason, instead of retaining both a completion-comment event and a close-with-reason event as two names for effectively the same occurrence.

13. Closing an issue is treated as a state transition carrying either a “completed” or “not planned” reason, rather than as a comment; the hook does not redirect this command, and the ordinary incremental issue feed observes the resulting state change.

14. Issue deletion is prohibited without qualification; agents should close issues instead, preserving the historical record by moving it forward through new state rather than erasing it.

15. Every rejected operation includes an audited override usable once, following the same guard pattern already used on the main branch for protected instruction files, so the restriction is intentionally bypassable in an exceptional case and each bypass is recorded.

16. An absolute block would make the custom tool a single failure point for every issue write: if the tool broke or failed to account for a valid `gh` capability, agents could be unable to write issues precisely when an escape route was required.

17. The stated condition for considering stronger enforcement is audit evidence that agents are using overrides to avoid the tool’s intended requirements rather than to recover from real tool failures.

18. The design knowingly accepts interception gaps because the hook recognizes enumerated command patterns such as `gh issue …`; direct `gh api` calls, MCP-based writes, or unusual command quoting may bypass it under the assumed cooperative-agent model.

19. A later maintenance scan is expected to detect bypassed writes because even an unchecked change still appears in the incremental update data.

## The three-layer stack

1. The first layer is the `ghi-write` skill, which activates before an agent files or edits an issue and instructs it early enough to ask `ghi-info`, choose the destination according to the work’s state, revise existing material instead of duplicating it, and keep the issue concise; because these choices happen before a command is attempted, this is intended to be the most efficient path and to avoid rejection-and-retry cycles.

2. The second layer is the hook and dedicated write tool, which serves as a correctness backstop when the skill fails to activate; under the design’s claim, a missed skill activation may cause inefficiency, such as catching a duplicate later or rejecting one comment attempt, but the backstop still prevents the corresponding correctness error.

3. Because the backstop handles missed skill activations, the skill’s trigger description can be firm and narrowly stated rather than aggressively designed to trigger in borderline cases; avoiding that aggressive or “pushy” wording also avoids the testing burden created by excessive false activations.

4. The third layer is `CLAUDE.md`, which supplies general background documentation but is not relied upon as the active enforcement mechanism.

5. Written conventions alone are claimed to be weaker than agents’ learned habits: issue 13 commissioned the `ghi-write` skill because agents continued adding successive comments despite a written rule against doing so, whereas instructions delivered at the moment an agent acts are claimed to overcome that behavior more effectively.

## Division of labor

1. Scripts retrieve issues, format them, merge incremental changes, and divide them according to open or closed state; this work is considered free because it uses no model turn.

2. Scripts within the write tool measure body length and verify references; this work is also considered free of model-turn cost.

3. Scripts calculate freshness values, scan for supersession problems, and check link integrity; this likewise consumes no model turn.

4. A script in the wrapper compares returned issue pointers against the closed-issue file and removes stale results; this likewise has no model-turn cost.

5. `ghi-info` determines which issues are relevant to a question and judges similarity between proposed writes and existing issues; each such operation costs one model turn.

6. `ghi-info` owns edits whose sole purpose is maintaining cross-links, and this remains its only permitted class of write.

7. The agent currently writing the issue, assisted by `ghi-write`, decides where the material belongs, authors the body’s substance, and rewrites an overlong body into a short issue plus detailed paired Markdown; these tasks remain with that agent because it already possesses the authoring context needed to perform them.

## Deliberately not in version 1

1. Version 1 does not include a vector database or graph database because the model’s context window is being used directly as the database-like store for reasoning, and the current evidence gives no anticipated condition under which that decision should be reversed.

2. Version 1 does not use a GitHub MCP server as its issue-writing interface because a generic MCP write would not inherently apply the project’s custom checks; the document expects the project-owned tool to remain the write interface permanently.

3. Version 1 does not impose an absolute block on direct `gh` writes because such a block would create a single point of failure and absolute prohibitions are expected to cause harmful behavior; stronger blocking should be reconsidered only if override audits show agents bypassing the tool to avoid its requirements rather than responding to actual failures.

4. Version 1 does not delete older closed issues from GitHub because their practical cost is model-context and attention usage rather than GitHub storage, and the tiered mirror is expected to control that cost; deletion should be reconsidered only if mirror tiering ceases to be adequate.

5. Version 1 does not include supervision by several separate watchdog processes because a single overall timeout is considered sufficient for an operation that handles only one question at a time; more elaborate supervision should be reconsidered if the single timeout proves unable to distinguish or handle important failure modes.

6. Version 1 does not commit the issue mirror because changes to generated data would clutter the repository history that humans inspect; committing it should be reconsidered if users need to search the mirror consistently across different checkouts and regenerating it separately on each machine cannot satisfy that need.

## Verify at build

1. During implementation, verify that an issue’s `updated` timestamp changes when the issue is closed, reopened, or relabeled, just as documentation says it changes when the body is edited or a comment is added; this behavior is documented but was not tested for this design.

2. Verify that one `PreToolUse` response can use `updatedInput` and `additionalContext` together, because that particular combination is not documented.

3. Verify the Codex equivalent of the required pre-tool hooks; hooks are known to exist in the Codex runtime, but the corresponding field names have not been confirmed.

4. Verify whether GitHub’s cross-reference timeline event supplies the backlinks needed to construct the reference graph, including the exact API response structure.

5. Verify that the custom tool can format its output closely enough to ordinary `gh` output that agents interpret the result as expected.

6. Verify that both the Ubuntu machine’s `gh` authentication and its persistent Claude token remain valid during unattended operation, because authentication on that machine has expired previously.
