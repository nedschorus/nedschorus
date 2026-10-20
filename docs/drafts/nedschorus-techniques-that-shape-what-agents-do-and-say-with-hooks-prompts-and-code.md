# Techniques that shape what agents do and say, with hooks, prompts and code

This page lists the techniques this project uses to make agents do what is wanted, and do it well: in the work they do, in what they say to the user, and in how they work with the user and with other agents. Read it before you propose a rule for CLAUDE.md or another file of agent-instructions, and before you build a hook or a check: a rule is usually better delivered by one of these techniques than by another line of text. When an agent wants to remember a lesson, [the page on saving a lesson where an agent meets it](nedschorus-how-to-save-a-lesson-where-an-agent-meets-it-when-it-applies-instead-of-in-a-memory-note.md) says where the lesson goes, and it uses these techniques.

Each technique below says what problem it solves, how it works, and where it is built; where they matter, also when it runs and who corrects a wrong act. *Planned* marks what is decided but not built; *pending a user-ruling* marks a question the user has not decided. Hooks are Claude Code's; this project configures none for Codex, so a technique built as a hook does not reach a Codex agent.

## Choosing a technique

Ask these questions in order. Question 2 can lead on to question 3; otherwise stop at the first that fits.

1. **Can a program do the work?** Then a program does it. Where part of the work needs judgment, the program hands only that part to a prompt and acts on the answer: that is code-prompt-code. A step simple enough to state in one sentence, and rarely done, does not need a program: go on to question 2.
2. **Can a check before the act tell that the act is wrong, without refusing a correct one?** Then refuse the act, and say in the refusal what to do instead: block-and-inform. A check that catches only some routes before the act still blocks the ones it sees; go on to question 3 for the routes it misses. CLAUDE.md's rule on when to add a guard applies.
3. **Can a check see the wrong act only after it happens?** Then detect it, tell the agent, and have it corrected: detect-inform-correct.
4. **Does the agent need to know something at one moment, with nothing wrong yet?** Then deliver it at that moment: a skill whose description triggers it, the next step printed by the program the agent is running, or a reminder hook on the act.
5. **Is it judgment no check can make?** If another agent can judge it, a review by another agent; if only the user can decide it, an approval-walk.
6. **Only if none fits:** a line in the seat-brief when only one agent-seat does that work, in the glossary when it is what a word means, or, last of all, in CLAUDE.md. Text that is loaded at the start of an agent-session is easily ignored by the time it applies.

A hook should speak only in the case it can recognise exactly. A hook that speaks on most turns is ignored, and costs context.

## What agents do

**Code-prompt-code (CPC).** Problem: a long procedure written as prose is followed unreliably, and a prompt is slower and harder to debug than code. Technique: a program does the steps, the bookkeeping and the checks, and hands a prompt only the judgment. Built: `nc-systems/cold-read/cold-read-grid.py`, which launches the cold-read-cells and collects their reports; `scripts/ghi-info-ask.py`. *Planned:* a walk-runner for approval-walks.

**Block-and-inform.** Problem: an agent is about to do something a check can tell is wrong. Technique: a PreToolUse hook refuses the tool call, and its refusal, an agent-facing-message, says what to do instead. A refusal is a hard-block, a soft-block or a user-block, by what clears it. Runs: before the act. Corrects: the agent, by doing what the refusal says, or, for a user-block, the user, by approving. Built: `scripts/hand-typed-codex-exec-redirect-hook.py` refuses a hand-typed `codex exec` and names `scripts/run-codex-task-from-brief.py`; `.claude/hooks/instruction-file-guard.py` refuses an edit of a guarded-file until a `.walk-approved` marker file holds the user's approval or an obvious-fix marker. The guard checks that the marker exists, not that the approval in it is real. Write the refusal by [the agent-facing-message page](nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md).

**Detect-inform-correct (DIC).** Problem: a check before the act misses some routes, such as a guarded-file changed by a shell command, which a hook on the file-editing tools never sees. Technique: a program detects the act after it happened and tells the agent what went wrong and what to do from now on; the act is then corrected, as the glossary's entry for detect-inform-correct says. Runs: just after the act, while the agent still has the context to fix it cheaply. Built: `.claude/hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py` backs up a guarded-file changed without approval and has the agent ask the user, leaving the change in place; `scripts/markdown-edit-hard-wrapped-paragraph-reminder-hook.py` tells the agent to rejoin a paragraph it broke across lines. *Pending a user-ruling:* which wrong acts a program may undo itself, and which the agent must correct.

**A reminder on the act.** Problem: the agent does not know, at the moment it acts, that a rule or a tool applies. Technique: a hook adds a short note to the agent's context and lets the act go ahead. Built, before the act: `nc-systems/general-tools/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py` names `scripts/dangling-path-citation-check.py` and `scripts/stale-code-citation-check.py` on a push that changes Markdown. Built, after the act: `scripts/new-shared-names-reminder-hook.py` lists the shared names a branch adds, for a name check; `nc-systems/general-tools/python-edit-changed-agent-facing-message-check-reminder-hook.py` sends an agent that changed an agent-facing-message to the agent-facing-message page.

**A skill triggered by its description.** Problem: a procedure with judgment in it, needed only at certain moments. Technique: a skill under `.claude/skills/`, whose `description:` line says when to use it, so the agent loads it when that moment comes. Built: every skill in `.claude/skills/`, such as `/ghi-write`, used before any write to a GitHub issue.

**The program's own message teaches the next step.** Problem: a rule about one tool does not belong in CLAUDE.md. Technique: the program prints what to do next, or how to get more, where the agent reads its output. Built: `scripts/ghi-info-ask.py` prints how to include closed GHIs after an answer that searched only open ones. Write the message by the agent-facing-message page.

**Code does the step.** Problem: a step agents forget even when reminded. Technique: a program does the step itself. Built: `scripts/git-client-side-hooks/prepare-commit-msg` stamps the session trailer on every commit made inside an identified Claude Code agent-session, because agents left it out.

**A gate in code.** Problem: a step agents skip under pressure of other work. Technique: a program refuses to go on without the step. Built: `scripts/merge-gate.sh` refuses a pull request whose description says neither whether it fixes a defect nor what the defect's root cause is.

**A task with a due time or a prerequisite.** Problem: a promise to act later is forgotten. Technique: the promise becomes a Claude Code task whose metadata a program checks. Runs: at the end of a turn, once the task is due or its prerequisite is met. Built: `scripts/agent-seat-due-task-raise-hook.py`.

**A hashtag that code reads.** Problem: a label written as ordinary prose, such as `Root cause:`, is read unreliably by a program. Technique: a fixed hashtag, which a program finds exactly. Built: the walk-minutes' `#next_to_present` line, which the approval-walk Stop hook reads; the merge gate's `#root_cause`, `#root_cause_not_fixed` and `#no_defect_fixed` lines.

**Use the project's parsers.** Problem: an agent writes its own regular expression to read a shell command, Markdown or git output, and it gets ordinary input wrong. Technique: a new program reads each kind of input with the shared parser for it; older programs are moving onto them:
- shell commands: `nc-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py`, on tree-sitter-bash;
- git output: `nc-systems/general-tools/git-machine-readable-output-runner-and-parser-common.py`, which runs git in its machine-readable forms;
- agent-facing-messages in Python source: `nc-systems/general-tools/python-source-agent-facing-string-collector-common.py`, on Python's `ast`;
- Markdown: the markdown-it-py library; *planned:* a shared module on it;
- the libraries these need are pinned in `nc-systems/general-tools/python-libraries-pinned-requirements.txt`, and `nc-systems/general-tools/python-libraries-pinned-requirements-install-if-missing-then-import-common.py` installs one that is missing.

**Reuse what is already built.** Problem: agents solve again a problem the project has solved. Technique: a page of reusable components, organised by what the agent is about to do, with a hook that names the right row after an edit that writes such a solution again. *Planned:* GHI [Agents reuse what the project has already solved: shared helpers, one page of reusable components, and a reuse check before, during and after the build](https://github.com/nedschorus/nedschorus/issues/1123).

## What agents say to the user

**Detect-inform-correct on a reply.** Problem: a reply breaks a rule about how the user is written to. Technique: a hook reads the agent's reply and tells the agent what was wrong. A Stop hook runs as the agent finishes its turn and has it correct the reply in the same turn; a UserPromptSubmit hook runs at the user's next prompt, and the agent corrects it in its next reply. Built, at the end of the turn: `scripts/cold-read-fast-read-due-for-linked-document-reminder-hook.py` (a document linked before its cold-read-fast-read); `scripts/absence-claim-locator-reminder-hook.py` (a file called missing in a turn that ran no search for it). Built, at the next prompt: `scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py` (a pull request or GHI cited by bare number); `scripts/ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook.py` (a ned-box path the user cannot open on his Mac).

**The approval-walk Stop hook.** Problem: during an approval-walk, the item waiting for the user's answer scrolls out of sight. Technique: the agent shows each item in full in its own message, and while an approval-walk is open, a Stop hook refuses to end a turn that answers the user unless the reply names the waiting item. Built: `nc-systems/skills/walk-me-through/walk-me-through-current-item-shown-to-user-after-each-agent-message-stop-hook.py`.

**A cold read before the user reads.** Problem: prose the user cannot follow costs him a round trip. Technique: fresh-agents read the text before the user does. A cold-read-fast-read has one cold-read-cell restate the text sentence by sentence and say where it struggled; a cold-read-full-run has six cold-read-cells hunt for defects and check terms (all four terms are in `.claude/skills/skills-glossary.md`). The writer fixes the text before the user sees it. Built: the `/cold-read` skill and `nc-systems/cold-read/cold-read-fast-read.py`; `/explain` gives its own reply a cold-read-fast-read.

## How agents work with the user and with other agents

**An approval-walk.** Problem: several decisions put to the user at once get skimmed. Technique: `/walk-me-through` presents the decisions one item at a time, or a few small items together, records each answer in the walk-minutes, and the approval-walk Stop hook keeps the waiting item named.

**A review by another agent.** Problem: the agent that did the work misses what its own context hides from it. Technique: an agent without that context reviews the work: a fresh-agent; the other agent-binary, such as the Codex reviewer of each pull request (`scripts/code-review-codex-cell.py`); Claude Code's advisor tool, a stronger model that reads the agent's whole conversation; or the `/sanity-check` skill for a design. A fix-round then answers each changes-requested review.

**The right place for an agent-seat's own instructions.** Problem: an instruction for one agent-seat's whole agent-session is lost at compaction, or one meant only for its start is reread for ever. Technique: instructions for the whole agent-session go in the seat-brief, which reloads after compaction; instructions for the start only go in the initial-agent-instructions, such as `docs/agents/seat-first-prompt.md`.

**A project-term for a technique agents find odd.** Problem: a reviewer who has not met detect-inform-correct objects that a check does not prevent the problem. Technique: name the technique in `docs/nedschorus-wiki/nedschorus-glossary.md`, so every agent and reviewer finds one meaning there.

## Tried and dropped

- **A soft-block on listed words and phrases.** It frightened agents away from the tool; a note added to their context replaced it.
- **Hardening soft-blocks into hard-blocks across the board.** It cost days of work and millions of tokens; a hard-block is still used where nothing should override it.
- **Parsing shell commands as a complete guard.** A shell has too many routes to a file; detect-inform-correct catches more of what the parse misses.
- **A Stop hook notice that showed the waiting walk item to the user.** The Claude Mac app printed it as one "Stop says:" line per line of text, which read as a broken hook; the agent now shows the item, and the hook checks that its reply names it.
- **A watcher that read agents' transcripts and sent them alerts.** Its alerts were not useful, and it was retired.
- **Ranking techniques on a ladder from "impossible" to "text", and a table of Claude Code hook events by moment.** Both described the mechanisms rather than what they achieve.

## Not built yet

- *Planned:* a hook on the agent's message as it is displayed, which starts slow checks early so that a later hook can add their result: GHI [One Claude Code hook starts slow work early and a later hook adds the result, and a wiki page on hook techniques for controlling and instructing agents](https://github.com/nedschorus/nedschorus/issues/1515).
- *Planned:* an hourly maintenance-job that raises due tasks to an idle agent-seat: GHI [Tasks raise themselves when their due time passes or their prerequisite is met](https://github.com/nedschorus/nedschorus/issues/940).
- *Pending a user-ruling:* a Stop hook that turns a promise of later work in a reply into a task.
- *Planned:* the page of reusable components and its hook, the walk-runner, and the shared Markdown module, above.
- *Pending a user-ruling:* a trigger for the user's request that an agent run macOS `say` when it needs his attention; today it is only a line in his `~/.claude/CLAUDE.md`.
- *Pending a user-ruling:* a store that recalls lessons by subject: GHI [Save each lesson where agents meet it at the moment it applies, and decide whether a store that recalls lessons by subject is worth building](https://github.com/nedschorus/nedschorus/issues/1349).

**Checked against:** commit [ae70c3c430ada1ffb2580590ab10f8b575dfbdbd](https://github.com/nedschorus/nedschorus/commit/ae70c3c430ada1ffb2580590ab10f8b575dfbdbd)
