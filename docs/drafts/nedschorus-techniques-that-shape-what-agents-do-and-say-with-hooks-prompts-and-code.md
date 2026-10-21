# Techniques that shape what agents do and say, with hooks, prompts and code

This project's purpose is instructing and controlling agents: making them do what is wanted, and do it well, in the work they do, in what they say to the user, and in how they work with the user and with other agents. This page lists the techniques the project uses for that. Read it before you propose a rule for CLAUDE.md or another file of agent-instructions, and before you build a hook or a check: a rule is usually better delivered by one of these techniques than by another line of text. When an agent wants to remember a lesson, [the page on saving a lesson where an agent meets it](nedschorus-how-to-save-a-lesson-where-an-agent-meets-it-when-it-applies-instead-of-in-a-memory-note.md) says where the lesson goes, and it uses these techniques.

The goal is good enough, not perfect. In the user's words: "the goal is efficiency, reasonably safe, reasonably fast to develop, operate and maintain, but not the NP complete goal of perfection." Anything an agent does mostly works but sometimes does not, like a [nice-but-dirty](nedschorus-glossary.md) component. So a detection that is good enough, as a skill's trigger is, is very useful; and a block that refuses some correct acts and misses some wrong ones is acceptable, because a soft-block lets the agent past a wrong refusal, and a detection after the act catches what the block missed. CLAUDE.md's rule on when to propose a guard, validation, retry or workaround decides whether to build a check at all.

Each technique below says what problem it solves, how it works, and where it is built; and, where it matters, when the technique runs and who corrects a wrong act. *Planned* marks what is decided but not built; *proposed* marks what is designed or suggested but not decided; *pending a user-ruling* marks a question put to the user and not yet decided. Hooks are Claude Code's; this project configures none for Codex, so a technique built as a hook does not reach a Codex agent.

## Choosing a technique

Ask these questions in order. Question 2 can lead on to question 3; otherwise stop at the first that fits.

1. **Can a program do the work?** Then a program does it. Where part of the work needs judgment, the program hands only that part to a prompt and acts on the answer: that is code-prompt-code. A step simple enough to state in one sentence, and rarely done, does not need a program: go on to question 2.
2. **Can a check before the act tell that the act is wrong?** Then refuse the act, and say in the refusal what to do instead: block-and-inform. The check need not be perfect. When it will predictably or often refuse a correct act, make the refusal a soft-block, which asks the agent to check again and, if it is sure, to give its reason and try again. For the wrong acts the check misses, go on to question 3.
3. **Can a check see the wrong act only after it happens?** Then detect it, tell the agent, and have it corrected: detect-inform-correct.
4. **Does the agent need to know something, or be reminded of something, to act as instructed?** Then tell it just in time, just before it acts: a prompt, a reminder of a tool, a skill or a code-prompt-code procedure, or a series of steps to follow. Without a detection that triggers it, an instruction lies dormant. Sometimes a well-designed skill, whose `description:` line is the trigger, is all that is needed.
5. **Is it judgment no check can make?** If another agent can judge it, a review by another agent; if only the user can decide it, an approval-walk.
6. **Only if none fits:** a line in the seat-brief when only one agent-seat does that work, in the glossary when it is what a word means, or, last of all, in CLAUDE.md or the user's own `~/.claude/CLAUDE.md`. For a rule that several agent-seats need but not every agent, ask the user where it goes. [cut = if you know what agents need it don't ask the user -but cut all weak crap - when not sure if a statement is useful cut- we need a tough editor, not a sloppy mess] Text that is loaded at the start of an agent-session works nicely for a fresh, short lived agent, and poorly for a long lived agent after 50k tokens of context. 

A hook should speak only in the case it can recognise exactly [thats not right or consistent cut]. A hook that speaks on most turns is ignored, and costs context. [true but cut - the wrong way to explain] Ideally hooks are mechanical and precise, but we don't rule out good enough detection and good enough correction. In something is better than nothing, unless there so many false positives that agents learn to ignore the true positives.  [or something like that]

## How an agent's act passes through these techniques

```mermaid
stateDiagram-v2
    [*] --> PreToolHook
    PreToolHook --> Hard-block: Something unwanted is detected and blocked. Caller is told what happened, why and given advice on how to correct, including asking the user to explicitly approve the action. Expect the agent to try another way to make progress towards its goal. 
    PreToolHook --> Alert: Something is detected that could benefit from additional context or needs a post-tool-check. Unlock the appropriate post-tool detector or add helpful additional context. 
    PreTookHook --> Soft-block-no-reason-provided: Something potentially unwanted is detected and blocked. The caller is told why, and told if they have a reason to go ahead, to try again, but this time with a reason. This may scare off agents so soft-blocks need to be logged and reviewed.
    PreToolHook --> Soft-block-reason-provided: Something potentially unwanted is detected and blocked, but the caller has provided a reason they should be allowed to continue.
    Soft-block-reason-provided-->PostToolHook: The tool call procedes. 
    PreToolHook-->PostToolHook: Nothing is detected. The tool call procedes. 
    PostToolHook-->Done
    PostToolHook-->PostToolDetect: Something is detected after the tool has completed. A file's SHA has changed, or a new file has been created or deleted or name chaged with a known pre-fix or suffix, or other detection mechanisms, like #hashtags added within a file.
    PostToolDetect-->Programatic-correct: If necessary the file is reverted, or other result are corrected mechanically. The agent is instructed in correct techique for future reference (though this will fade as new tokens are added to its context) 
    PostToolDetect-->Agent-correct: If the result can not be mechanically corrected, the agent it told to revert as best it can, and instructed in correct technique for its future reference.  
    Agent-Correcting --> Done:
    Programtic-Correct --> Done:
    Done --> [*]
```

In words: before an agent acts, a detection may fire. It may block the act, with a hard-block, a soft-block or a user-block, and the refusal tells the agent what to do instead; or it may let the act go ahead with an instruction added just in time. After the act, a detection may fire again, and the act is corrected, by a program or by the agent. At every step, what the agent is told is instruction, the last section below.

## When a program does the work

**Code-prompt-code (CPC).** Problem: a long procedure written as prose is followed unreliably, and a prompt is slower and harder to debug than code. Technique: a program does the steps, the bookkeeping and the checks, and hands a prompt only the judgment. Built: `nc-systems/cold-read/cold-read-grid.py`, which launches the cold-read-cells and collects their reports; `scripts/ghi-info-ask.py`. *Planned:* a walk-runner for approval-walks.

**Code does the step.** Problem: a step agents forget even when reminded. Technique: a program does the step itself. Built: `scripts/git-client-side-hooks/prepare-commit-msg` stamps the session trailer on every commit made inside an identified Claude Code agent-session, because agents left it out.

**Reuse what is already built.** Problem: agents solve again a problem the project has solved. Technique: a page of reusable components, organised by what the agent is about to do, with a hook that names the right row after an edit that writes such a solution again. *Planned:* GHI [Agents reuse what the project has already solved: shared helpers, one page of reusable components, and a reuse check before, during and after the build](https://github.com/nedschorus/nedschorus/issues/1123).

## Detection

A detection notices the moment a technique applies. It can run before the act or after it. It leads the four groups because nothing else fires without it: no block, no correction, and no instruction that reaches the agent when it applies.

**A pattern in the act.** Problem: a wrong act, or a moment that needs an instruction, shows up as a keyword or a command form. Technique: a hook reads the tool call, the text just written or the reply, and matches the pattern. Built, before the act: `scripts/hand-typed-codex-exec-redirect-hook.py` matches a hand-typed `codex exec`. Built, after the act: `scripts/style-guide-word-checker-markdown-edit-hook.py` reports each word the style guide lists in Markdown just written; the reply hooks under Correction.

**A file name's prefix or suffix.** Problem: a program must know what kind of file it is handling, without reading it. Technique: the kind is in the name, and the program reads the name. Built: `.claude/hooks/instruction-file-guard.py` knows a reusable prompt by `-prompt.md` or `-instructions.md` and a reviewed design by `-design.md`; `scripts/run-all-test-suites.py` runs every file named `*-test.py` or `*-test.sh`. A name can also be read by an agent: a pull request reviewer holds a file whose name ends `-nbd` to the nice-but-dirty limits only, as CLAUDE.md's review scope says.

**A hashtag that code reads.** Problem: a label written as ordinary prose, such as `Root cause:`, is read unreliably by a program. Technique: a fixed hashtag, which a program finds exactly. Built: the walk-minutes' `#next_to_present` line, which the approval-walk Stop hook reads; the merge gate's `#root_cause`, `#root_cause_not_fixed` and `#no_defect_fixed` lines.

**A skill triggered by its description.** Problem: a procedure with judgment in it, needed only at certain moments. Technique: a skill under `.claude/skills/`, whose `description:` line says when to use it, so the agent itself detects the moment and loads the skill. It is good enough, not exact. Built: every skill in `.claude/skills/`, such as `/ghi-write`, used before any write to a GitHub issue.

**A task with a due time or a prerequisite.** Problem: a promise to act later is forgotten. Technique: the promise becomes a Claude Code task whose metadata a program checks, so the due time or the met prerequisite is what is detected. Runs: at the end of a turn. Built: `scripts/agent-seat-due-task-raise-hook.py`.

**Use the project's parsers.** Problem: an agent writes its own regular expression to read a shell command, Markdown or git output, and it gets ordinary input wrong, so the detection misfires. Technique: a new program reads each kind of input with the shared parser for it; older programs are moving onto them:
- shell commands: `nc-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py`, on tree-sitter-bash;
- git output: `nc-systems/general-tools/git-machine-readable-output-runner-and-parser-common.py`, which runs git in its machine-readable forms;
- agent-facing-messages in Python source: `nc-systems/general-tools/python-source-agent-facing-string-collector-common.py`, on Python's `ast`;
- Markdown: the markdown-it-py library; *planned:* a shared module on it;
- the libraries these need are pinned in `nc-systems/general-tools/python-libraries-pinned-requirements.txt`, and `nc-systems/general-tools/python-libraries-pinned-requirements-install-if-missing-then-import-common.py` installs one that is missing.

## Blocking

**Block-and-inform.** Problem: an agent is about to do something a check can tell is wrong. Technique: a PreToolUse hook refuses the tool call, and its refusal, an agent-facing-message, says what to do instead. Runs: before the act. A refusal is one of three kinds, by what clears it:
- a hard-block, which nothing overrides: the agent does what the refusal says instead;
- a soft-block, which the agent clears by writing its own reasoning into the marker the refusal names: for a check that sometimes refuses a correct act;
- a user-block, which only the user's approval, quoted into the marker the refusal names, clears.

Built: `scripts/hand-typed-codex-exec-redirect-hook.py` refuses a hand-typed `codex exec` and names `scripts/run-codex-task-from-brief.py`; `.claude/hooks/instruction-file-guard.py` refuses an edit of a guarded-file until a `.walk-approved` marker file holds the user's approval, a `#pre_approved_change` line with its reason, or an obvious-fix marker. The guard checks that the marker is not empty, not that the approval in it is real. Write the refusal by [the agent-facing-message page](nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md).

**A gate in code.** Problem: a step agents skip under pressure of other work. Technique: a program refuses to go on without the step. Built: `scripts/merge-gate.sh` refuses a pull request whose description says neither whether it fixes a defect nor what the defect's root cause is.

**The approval-walk Stop hook.** Problem: during an approval-walk, the item waiting for the user's answer scrolls out of sight. Technique: the agent shows each item in full in its own message, and while an approval-walk is open, a Stop hook refuses to end a turn that answers the user unless the reply names the waiting item. Built: `nc-systems/skills/walk-me-through/walk-me-through-current-item-shown-to-user-after-each-agent-message-stop-hook.py`.

## Correction

**Detect-inform-correct (DIC).** Problem: a check before the act misses some routes, such as a guarded-file changed by a shell command, which a hook on the file-editing tools never sees. Technique: a program detects the act after it happened and tells the agent what went wrong and what to do from now on; the act is then corrected, as the glossary's entry for detect-inform-correct says. Runs: just after the act, while the agent still has the context to fix it cheaply. Who corrects: a program that reverts the act itself, or the agent, told to revert or fix it. Built: `.claude/hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py` backs up a guarded-file changed without approval and has the agent ask the user, leaving the change in place; `scripts/markdown-edit-hard-wrapped-paragraph-reminder-hook.py` tells the agent to rejoin a paragraph it broke across lines. *Pending a user-ruling:* which wrong acts a program may undo itself, and which the agent must correct.

**Detect-inform-correct on a reply.** Problem: a reply breaks a rule about how the user is written to. Technique: a hook reads the agent's reply and tells the agent what was wrong. A Stop hook runs as the agent finishes its turn and has it correct the reply in the same turn; a UserPromptSubmit hook runs at the user's next prompt, and the agent sends a correction in its next reply, since the user has already read the first. Built, at the end of the turn: `scripts/cold-read-fast-read-due-for-linked-document-reminder-hook.py` (a document linked before its cold-read-fast-read); `scripts/absence-claim-locator-reminder-hook.py` (a file called missing in a turn that did not run `scripts/locate-file-copies-across-machines.py` or the `/locate-before-saying-a-file-is-missing` skill). Built, at the next prompt: `scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py` (a pull request or GHI cited by bare number); `scripts/ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook.py` (a ned-box path the user cannot open on his Mac).

**Rewinding the conversation.** Claude Code's rewind feature may serve as a correction; whether it does, and how a program could use it, is still to be found out. *Not yet proposed:* GHI to be filed.

## Instruction

Whatever the technique, the agent must be told whether its step worked, and if not, why not and the best way to do it. CLAUDE.md's rule on text a program hands an agent says how, and [the agent-facing-message page](nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md) says it in full. The places below are ordered from the moment the instruction applies to the start of an agent-session, which is the weakest.

**A reminder on the act.** Problem: the agent does not know, at the moment it acts, that a rule or a tool applies. Technique: a hook adds a short note to the agent's context and lets the act go ahead. Built, before the act: `nc-systems/general-tools/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py` names `scripts/dangling-path-citation-check.py` and `scripts/stale-code-citation-check.py` on a push that changes Markdown. Built, after the act: `scripts/new-shared-names-reminder-hook.py` lists the shared names a branch adds, for a name check; `nc-systems/general-tools/python-edit-changed-agent-facing-message-check-reminder-hook.py` sends an agent that changed an agent-facing-message to the agent-facing-message page.

**The steps of a skill.** Problem: a procedure needs judgment at each step, so a program cannot do all of it. Technique: the skill that its description triggers, under Detection, holds the steps, read at the moment they apply.

**The program's own output teaches the next step.** Problem: a rule about one tool does not belong in CLAUDE.md. Technique: the tool's result, or its manual, its `--help` text, says what to do next or how to get more, where the agent reads it. Built: `scripts/ghi-info-ask.py` prints how to include closed GHIs after an answer that searched only open ones.

**The right place for an agent-seat's own instructions.** Problem: an instruction for one agent-seat's whole agent-session is lost at compaction, or one meant only for its start is reread for ever. Technique: instructions for the whole agent-session go in the seat-brief, which reloads after compaction; instructions for the start only go in the initial-agent-instructions, such as `docs/agents/seat-first-prompt.md`.

**A project-term for a technique agents find odd.** Problem: a reviewer who has not met detect-inform-correct objects that a check does not prevent the problem. Technique: name the technique in `docs/nedschorus-wiki/nedschorus-glossary.md`, so every agent and reviewer finds one meaning there.

**CLAUDE.md, last.** CLAUDE.md is always loaded, but its space is scarce, it is read at the start of an agent-session, and agents easily ignore it by the time a rule applies. Extend the sentence there that already covers the action before adding a bullet.

**A cold read of every instruction.** Problem: the agent that reads an instruction has a very different context from the agent that wrote it, so what is clear to the writer is often unclear to the reader. Technique: fresh-agents read the text before it is used. A cold-read-fast-read has one cold-read-cell restate the text sentence by sentence and say where it struggled; a cold-read-full-run has six cold-read-cells hunt for defects and check the document's terms. The cold-read terms are defined in `.claude/skills/skills-glossary.md`. The writer fixes the text first. Built: the `/cold-read` skill and `nc-systems/cold-read/cold-read-fast-read.py`; `/explain` gives its own reply a cold-read-fast-read. The same holds for prose the user reads: a round trip costs him more than a cold read.

## Where only judgment will do

**A review by another agent.** Problem: the agent that did the work misses what its own context hides from it. Technique: an agent without that context reviews the work: a fresh-agent; the other agent-binary, such as the Codex reviewer of each pull request (`scripts/code-review-codex-cell.py`); the `advisor` tool, which Claude Code gives some agent-sessions: a stronger model that reads the agent's whole conversation and advises it; or the `/sanity-check` skill for a design. A fix-round then answers each changes-requested review.

**An approval-walk.** Problem: several decisions put to the user at once get skimmed. Technique: `/walk-me-through` presents the decisions one item at a time, or a few small items together, records each answer in the walk-minutes, and the approval-walk Stop hook keeps the waiting item named.

## Tried, then corrected or dropped

- **Corrected: a soft-block on listed words and phrases.** It frightened agents away from the tool it guarded; a note added to their context replaced it.
- **Corrected: hardening soft-blocks into hard-blocks across the board.** It cost days of work and millions of tokens; a hard-block is still used where nothing should override it.
- **Corrected: parsing shell commands as a complete guard.** A shell has too many routes to a file; detect-inform-correct catches more of what the parse misses.
- **Corrected: a Stop hook notice that showed the waiting walk item to the user.** The Claude Mac app printed it as one "Stop says:" line per line of text, which read as a broken hook; the agent now shows the item, and the hook checks that its reply names it.
- **Dropped: a watcher that read agents' transcripts and sent them alerts.** Its alerts were not useful, and it was retired.
- **Replaced by this page: ranking techniques on a ladder from "impossible" to "text", and a table of Claude Code hook events by moment.** Both described mechanisms by when they act. This page groups techniques by their job, makes detection and correction groups of their own, uses the soft-block for a check that is good enough, and starts from the purpose they serve.

## Not built yet

- *Proposed, not yet designed:* a hook on the agent's message as it is displayed, which starts slow checks early so that a later hook can add their result: GHI [One Claude Code hook starts slow work early and a later hook adds the result, and a wiki page on hook techniques for controlling and instructing agents](https://github.com/nedschorus/nedschorus/issues/1515).
- *Planned:* an hourly maintenance-job that raises due tasks to an idle agent-seat: GHI [Tasks raise themselves when their due time passes or their prerequisite is met](https://github.com/nedschorus/nedschorus/issues/940).
- *Planned:* a Stop hook that refuses to end a turn whose reply promises later work until the agent backs the promise with a task: GHI [A project style guide: words to avoid, a mechanical checker, and a check on unbacked promises](https://github.com/nedschorus/nedschorus/issues/14).
- *Planned:* the page of reusable components and its hook, the walk-runner, and the shared Markdown module, above.
- *Not yet proposed:* rewinding the conversation as a correction, above.
- *Not yet proposed:* a hook that reminds an agent to run macOS `say` when the agent needs the user's attention; today that rule is only a line in the user's `~/.claude/CLAUDE.md`.
- *Pending a user-ruling:* a store that recalls lessons by subject: GHI [Save each lesson where agents meet it at the moment it applies, and decide whether a store that recalls lessons by subject is worth building](https://github.com/nedschorus/nedschorus/issues/1349).

**Checked against:** commit [ce539455629470f01b6d247b20c47bb058c3a221](https://github.com/nedschorus/nedschorus/commit/ce539455629470f01b6d247b20c47bb058c3a221)
