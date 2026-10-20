# Techniques that shape what agents do and say, with hooks, prompts and code

This page lists the techniques this project uses to make agents do what is wanted, and do it well: in the work they do, in what they say to the user, and in how they respond to the user and to other agents. Read it before you propose a rule for CLAUDE.md or another file of standing instructions, and before you build a hook or a check: the rule you have in mind is usually better delivered by one of these techniques than by another line of text. When an agent wants to remember a lesson, [the page on saving a lesson where an agent meets it](nedschorus-how-to-save-a-lesson-where-an-agent-meets-it-when-it-applies-instead-of-in-a-memory-note.md) says which of these techniques delivers it.

Each technique below says what problem it solves, how it works, and where it is built; where they matter, also what fires it and who corrects a miss. *Planned* marks what is decided but not built; *pending the user's ruling* marks a question he has not decided.

## Choosing a technique

Ask these questions in order, and stop at the first that fits.

1. **Can a program do the step?** Then a program does it, and a prompt does only the judgment the program cannot: that is code-prompt-code. A step simple enough to state in a sentence and rarely done does not need a program.
2. **Can a check before the act tell, reliably, that the act is wrong?** Then refuse the act, and say in the refusal what to do instead: block-and-inform. A check that catches most cases before the act, but not every route, still blocks the ones it sees; detect-inform-correct catches the rest.
3. **Can a check see the wrong act only after it happens?** Then detect it, inform the agent, and correct it: detect-inform-correct. A program reverses or redoes what it can; the agent redoes the rest.
4. **Does the agent need to know something at one moment, with nothing wrong yet?** Then deliver it at that moment: a reminder hook, a skill triggered by its description, or the next step printed by the program the agent is running.
5. **Is it judgment no check can make?** Then it goes to a review by another agent, or to the user in an approval-walk.
6. **Only if none fits:** a line in the seat-brief when only one agent-seat does that job, in the glossary when it is what a word means, or, last of all, in CLAUDE.md. Text that is always loaded is easily ignored: a rule already in CLAUDE.md, citing by title rather than bare number, was still broken on 252 of 693 turn ends.

Whatever fires a reminder must fire rarely. A hook that speaks on most turns is ignored, and costs context: limit it to once per session, or to the case it can see exactly.

## What agents do

**Code-prompt-code (CPC).** Problem: a long procedure in prose is followed unreliably, and a prompt is slower and harder to debug than code. Technique: a program runs the steps, the bookkeeping and the checks, and hands a prompt only the judgment it cannot make, then acts on the answer. Fires: when the agent runs the program. Built: `nc-systems/cold-read/cold-read-grid.py`, which launches and collects cold-read-cells; `scripts/ghi-info-ask.py`. Planned: a walk-runner for approval-walks.

**Block-and-inform.** Problem: an agent is about to do something a check can tell is wrong. Technique: a PreToolUse hook refuses the tool call, and its refusal, an agent-facing-message, says what to do instead, so every refusal teaches. A refusal is a hard-block, a soft-block or a user-block, by what clears it. Fires: before the act. Corrects: the agent, by doing what the refusal says. Built: `scripts/hand-typed-codex-exec-redirect-hook.py` refuses a hand-typed `codex exec` and names `scripts/run-codex-task-from-brief.py`; `.claude/hooks/instruction-file-guard.py` refuses an edit of a guarded-file until the user's approval is quoted into a marker. Write the refusal by [the agent-facing-message page](nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md).

**Detect-inform-correct (DIC).** Problem: a check before the act misses some routes, such as a file changed by a shell command that a hook on the file-editing tools never sees. Technique: a program detects the act after it happened, tells the agent what went wrong and what to do from now on, and the act is corrected: by the program where it can reverse or redo it, otherwise by the agent, who redoes the work correctly. Fires: just after the act, while the agent still has the context to fix it cheaply. Built: `.claude/hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py` backs up a guarded-file changed without approval and has the agent ask the user; `scripts/markdown-edit-hard-wrapped-paragraph-reminder-hook.py` tells the agent to rejoin a paragraph it broke across lines. *Pending the user's ruling:* how the glossary entry separates what a program can safely correct from what the agent must correct.

**Reminder at the moment of use.** Problem: the agent does not know, at the moment it acts, that a rule or a tool applies. Technique: a hook adds a short note to the agent's context and lets the act go ahead. Fires: on the act the note is about. Built: `scripts/new-shared-names-reminder-hook.py` names each new shared name for a name check; `nc-systems/general-tools/python-edit-changed-agent-facing-message-check-reminder-hook.py` sends an agent that changed an agent-facing-message to the writing page; `nc-systems/general-tools/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py` gives the two citation checks on a push that changes Markdown.

**A skill triggered by its description.** Problem: a procedure with judgment in it, needed only at certain moments. Technique: a skill under `.claude/skills/`, whose `description:` line says when to use it, so the agent loads it at that moment and not before. Corrects: the agent, following the skill. Built: every skill in `.claude/skills/`, such as `/ghi-write` before any write to a GitHub issue.

**The program's own message teaches the next step.** Problem: a rule about one tool does not belong in CLAUDE.md. Technique: the program prints what to do next, or how to get more, where the agent reads its output. Built: `scripts/ghi-info-ask.py` prints how to include closed issues after an answer that searched only open ones. Write the message by [the agent-facing-message page](nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md).

**A gate in code.** Problem: a step agents forget even when reminded. Technique: a program does the step, or refuses to go on without it. Built: `scripts/git-client-side-hooks/prepare-commit-msg` stamps the session trailer on every commit, because agents left it out; `scripts/merge-gate.sh` refuses a pull request whose description lacks a `#root_cause`, `#root_cause_not_fixed` or `#no_defect_fixed` line.

**A task with a due time or a prerequisite.** Problem: a promise to act later is forgotten. Technique: the promise becomes a task whose metadata a program checks. Fires: at the end of a turn once the task is due. Built: `scripts/agent-seat-due-task-raise-hook.py`. Planned: a Stop hook that turns a promise in a reply into a task.

**A hashtag that code reads.** Problem: a label such as `Root cause:` written in prose is parsed badly. Technique: a fixed hashtag at the start of a line, which a program finds exactly. Built: the minutes' `#next_to_present` line, which the walk Stop hook reads; the merge gate's `#root_cause` lines.

**Use the project's parsers.** Problem: an agent writes its own regular expression to read a shell command, Markdown or git output, and it gets ordinary input wrong. Technique: one shared parser per kind of input, which every program uses:
- shell commands: `nc-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py`, on tree-sitter-bash;
- git output: `nc-systems/general-tools/git-machine-readable-output-runner-and-parser-common.py`, which runs git in its machine-readable forms;
- strings in Python source: `nc-systems/general-tools/python-source-agent-facing-string-collector-common.py`, on Python's `ast`;
- Markdown: the markdown-it-py library, pinned below; *planned:* a shared module on it;
- a library a parser needs is installed when missing by `nc-systems/general-tools/python-libraries-pinned-requirements-install-if-missing-then-import-common.py`, from `nc-systems/general-tools/python-libraries-pinned-requirements.txt`.

**Reuse what is already built.** Problem: agents solve again a problem the project has solved. Technique: a page of reusable components, organised by what the agent is about to do, with a reminder hook that names the right row when an agent starts on that problem. *Planned:* GHI [Agents reuse what the project has already solved: shared helpers, one page of reusable components, and a reuse check before, during and after the build](https://github.com/nedschorus/nedschorus/issues/1123).

## What agents say to the user

**Detect-inform-correct on a reply.** Problem: a reply breaks a rule about how the user is written to. Technique: a hook reads the agent's reply after it is sent, at the end of that turn or at the user's next prompt, and tells the agent what was wrong; the agent corrects it in its next reply. Built: `scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py` (a pull request or issue cited by bare number); `scripts/ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook.py` (a ned-box path the user cannot open on his Mac); `scripts/cold-read-fast-read-due-for-linked-document-reminder-hook.py` (a document linked before its fast read); `scripts/absence-claim-locator-reminder-hook.py` (a file called missing before anyone searched for it).

**A hook that shows the user what he must see.** Problem: during an approval-walk, the item waiting for his answer scrolls out of sight. Technique: a Stop hook prints the current item to the user after each agent message, instead of sending the agent back to repeat it. Built: `nc-systems/skills/walk-me-through/walk-me-through-current-item-shown-to-user-after-each-agent-message-stop-hook.py`.

**A cold read before the user reads.** Problem: prose the user cannot follow costs him a round trip. Technique: a fresh-agent restates the text sentence by sentence and reports where it struggled; the writer fixes it before the user sees it. A cold-read-fast-read is one cold-read-cell; a cold-read-full-run is six (both terms are in `.claude/skills/skills-glossary.md`). Built: the `/cold-read` skill, `nc-systems/cold-read/cold-read-fast-read.py`; `/explain`'s fast read of its reply.

## How agents respond to the user and to other agents

**An approval-walk.** Problem: several decisions put to the user at once get skimmed. Technique: `/walk-me-through` presents one item per message, records each answer in the walk-minutes, and the walk Stop hook keeps the current item in view.

**The user's exact words, quoted into a marker.** Problem: an agent rewrites a standing instruction on its own judgment. Technique: the instruction-file guard refuses the edit until the user's approval of the exact change is quoted into `.walk-approved`; the obvious-fix marker covers the four obvious errors CLAUDE.md lists.

**A review by another agent.** Problem: the agent that did the work shares its own blind spots. Technique: a fresh-agent, the other agent-binary, or an advisor reviews the work: pull request reviews by a Claude reviewer and a Codex review cell (`scripts/code-review-codex-cell.py`), the sanity-check (`/sanity-check`) for a design, and a fix-round subagent for each changes-requested review.

**The right place for a standing instruction.** Problem: an instruction meant for the whole agent-session is lost at compaction, or one meant only for the start is reread forever. Technique: whole-session instructions go in the seat-brief, `CLAUDE.local.md`, which reloads after compaction; start-only instructions go in the initial-agent-instructions, such as `docs/agents/seat-first-prompt.md`.

**A project-term for a technique agents find odd.** Problem: a reviewer who has not met detect-inform-correct objects that a check does not prevent the problem. Technique: name the technique in the glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`, so every agent and reviewer reads the same meaning.

## Tried and dropped

- **A soft-block on listed phrases.** It frightened agents into avoiding the tool; it was replaced by a note added to their context.
- **Hardening soft-blocks into hard-blocks.** It cost days of work and millions of tokens.
- **Parsing shell commands as a complete guard.** A shell has too many routes to a file; detect-inform-correct catches what the parse misses.
- **A Stop hook that sends the agent back to repeat a walk item.** It cost a turn each time; the hook now shows the item to the user itself.
- **A transcript watcher that alerted agents.** Its alerts were not useful, and it was retired.
- **Ranking techniques on a ladder from "impossible" to "text", and a table of hook events by moment.** Both described the mechanisms rather than what they achieve.

## Not built yet

- A hook on the agent's message as it is displayed, which starts slow checks early and lets the Stop hook add their result: GHI [One Claude Code hook starts slow work early and a later hook adds the result, and a wiki page on hook techniques for controlling and instructing agents](https://github.com/nedschorus/nedschorus/issues/1515). That GHI's wiki page is this page.
- The hook that turns a promise in a reply into a task, and an hourly sweep that raises due tasks to an idle agent-seat: GHI [Tasks raise themselves when their due time passes or their prerequisite is met](https://github.com/nedschorus/nedschorus/issues/940).
- The page of reusable components and its reminder hook: GHI [Agents reuse what the project has already solved: shared helpers, one page of reusable components, and a reuse check before, during and after the build](https://github.com/nedschorus/nedschorus/issues/1123).
- A trigger for the user's request that an agent run macOS `say` when it needs his attention: today it is only a line in his personal CLAUDE.md.
- A store that recalls lessons by subject: GHI [Save each lesson where agents meet it at the moment it applies, and decide whether a store that recalls lessons by subject is worth building](https://github.com/nedschorus/nedschorus/issues/1349).

**Checked against:** commit [ae70c3c430ada1ffb2580590ab10f8b575dfbdbd](https://github.com/nedschorus/nedschorus/commit/ae70c3c430ada1ffb2580590ab10f8b575dfbdbd)
