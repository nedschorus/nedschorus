<!-- provenance: runtime=agy model=gemini-3.8-flash-medium effort=medium cell=fast-clarify tier=fast duration_s=57 checkout=7f3feca3 prompt_file=/var/folders/ss/txf505y50sq9kxg2bfzkcmlc0000gn/T/cold-read-fast-read-q10zvvlh/cold-read-fast-read-embedded-fast-clarify-prompt.md target=/Users/el/agents/merge-lane-backlog/.claude/worktrees/explain-skill-folds-in-the-identifier-rules/cold-read-records/explain-reply-draft-2026-09-29/explain-reply-draft-with-sentence-ids.md -->

# Cold-Read Report: explain-reply-draft-with-sentence-ids.md

## Files Examined

1. `docs/nedschorus-wiki/nedschorus-glossary.md` (read prior to document under review)
2. `/Users/el/agents/merge-lane-backlog/.claude/worktrees/explain-skill-folds-in-the-identifier-rules/cold-read-records/explain-reply-draft-2026-09-29/explain-reply-draft-with-sentence-ids.md`

Both files were read successfully in full; none were unreadable.

---

## Question 1: What it says

[s1]
> He wrote: "confused explain.
* The user or reviewer wrote that he is confused and asked for an explanation.

[s2]
> Is this a soft block, that is do we refuse the first time, then let the agent resubmit with a reason?"
* He asks whether this behavior is a soft block.
* He defines his understanding of a soft block as refusing on the first attempt and then allowing the agent to resubmit with a reason.

[s3]
> The reply:
* Heading introducing the response to the user's question.

[s4]
> No, it is not a soft block.
* The author answers that it is not a soft block.

[s5]
> Nothing is refused, not even once: the launcher always starts the seat.
* Nothing is refused, not even a single time.
* The launcher consistently starts the agent-seat.

[s6]
> The question is only whether it should refuse instead.
* The only question to decide is whether the launcher should refuse instead of starting.

[s7]
> What it is.
* Section heading introducing what the script is.

[s8]
> `launch-claude-ubuntu` is the shell script you run to start an agent-seat on ned-box.
* `launch-claude-ubuntu` is a shell script.
* You execute this shell script to start an agent-seat on ned-box.

[s9]
> No agent is involved, so there is nobody to resubmit with a reason.
* No AI agent is involved in executing the script.
* Because no agent is involved, there is nobody who could resubmit a failed request with an explanation.

[s10]
> What happens today.
* Section heading introducing the current existing behavior.

[s11]
> You are in a Mac seat and run `launch-claude-ubuntu my-seat`.
* You are operating inside a Mac seat.
* You execute `launch-claude-ubuntu my-seat`.

[s12]
> Your shell carries the environment variable `NEDSCHORUS_AGENTS_ROOT=/Users/el/agents`, a Mac path.
* Your shell environment contains the environment variable `NEDSCHORUS_AGENTS_ROOT=/Users/el/agents`.
* That value is a macOS path.

[s13]
> You never set it: the Mac launcher, `launch-claude-mac`, puts it into every Mac seat and never removes it.
* You did not set this variable yourself.
* The Mac launcher script, `launch-claude-mac`, exports it into every Mac seat.
* The Mac launcher never unsets or cleans up the variable.

[s14]
> The ubuntu launcher ignores it, prints one warning line naming the variable, and starts the seat in `~/agents/my-seat` on ned-box.
* The Ubuntu launcher ignores the environment variable's value.
* The Ubuntu launcher prints a single warning line mentioning the variable name.
* The Ubuntu launcher starts the requested seat in `~/agents/my-seat` on ned-box.

[s15]
> The alternative.
* Section heading introducing the proposed alternative behavior.

[s16]
> It refuses to start until you run `unset NEDSCHORUS_AGENTS_ROOT`, then starts the same seat in the same place.
* The launcher refuses to start as long as the variable is present until you run `unset NEDSCHORUS_AGENTS_ROOT`.
* Once unset, it starts the identical seat in the identical directory.

[s17]
> Why I am asking.
* Section heading introducing the reason for asking this question.

[s18]
> You ruled on 2026-08-22 that a setting which overrides where a seat lives either works or is blocked, never half-honoured.
* You issued a ruling on 2026-08-22 regarding settings that override where a seat lives.
* That ruling states that such a setting must either take effect or be blocked, but never half-honoured.

[s19]
> I read this variable as leftover junk from the Mac, not an override anyone chose.
* The author interprets this variable as residual clutter from the Mac environment.
* The author does not view it as a seat location override that anyone intentionally chose.

[s20]
> The leak itself is being fixed at its source: you approved that fix as item 9.
* The variable leak itself is being resolved at its source.
* You previously approved that source fix as walk item 9.

[s21]
> Seats started before it lands still carry the variable until they are restarted, so this choice only decides how the launcher treats that leftover.
* Seats launched prior to that fix landing will continue carrying the variable until they are restarted.
* Therefore, this decision solely determines how the Ubuntu launcher handles that leftover variable.

[s22]
> Item 10 of 11 of the reboot-test walk, "I chose to warn where a recorded ruling says block":
* This decision is Item 10 out of 11 in the reboot-test walk.
* The item title is "I chose to warn where a recorded ruling says block".

[s23]
> Y: keep warning and starting the seat.
* Option Y is to continue warning about the variable while still starting the seat.

[s24]
> I recommend this.
* The author recommends selecting option Y.

[s25]
> N: refuse until you clear the variable.
* Option N is to refuse starting until you clear the environment variable.

---

## Question 2: Where you struggled

1. `"You are in a Mac seat and run launch-claude-ubuntu my-seat."` [s11]
The text does not explain how a script for starting a seat on ned-box is invoked from inside a Mac seat, leaving it ambiguous whether `launch-claude-ubuntu` runs locally on macOS (reaching ned-box via SSH) or runs on ned-box with environment variables forwarded over SSH, which prevents a reader from understanding where the command actually executes.

2. `"the reboot-test walk"` [s22] and `"item 9"` [s20]
These references provide no file path or citation to the walk document or its minutes, so a fresh reader cannot locate item 9 to inspect what was approved or examine the surrounding context of the walk.

3. `"It refuses to start until you run unset NEDSCHORUS_AGENTS_ROOT, then starts the same seat in the same place."` [s16]
The phrasing ambiguously suggests either that the launcher script blocks interactively waiting for the variable to be unset before resuming, or that it terminates immediately with an error requiring the user to run `unset` and re-invoke the command.

4. `"You ruled on 2026-08-22 that a setting which overrides where a seat lives either works or is blocked, never half-honoured."` [s18]
The text cites a ruling by date without providing a file path or document reference, making it impossible for a fresh reader to verify the ruling's exact text or determine what "half-honoured" means in this context.

5. `"[s1] He wrote: ... [s11] You are in a Mac seat ... [s18] You ruled on 2026-08-22"` [s1, s11, s18]
The text shifts between third-person reference ("He wrote") and second-person address ("You are", "You ruled"), leaving it ambiguous whether "He" in [s1] is the user or a third party such as another reviewer.

6. ``launch-claude-ubuntu`` [s8] and ``launch-claude-mac`` [s13]
The scripts are named without file paths, leaving a reader unable to locate and inspect their source implementations in the repository.

---

## Question 3: What it does not cover that it implies it should

1. `"The ubuntu launcher ignores it, prints one warning line naming the variable, and starts the seat in ~/agents/my-seat on ned-box."` [s14] and `"I read this variable as leftover junk from the Mac, not an override anyone chose."` [s19]
The text implies that `NEDSCHORUS_AGENTS_ROOT` is an override mechanism for seat locations under the 2026-08-22 ruling, but does not explain whether `launch-claude-ubuntu` ever supports intentional Linux directory overrides, or whether it ignores all values unconditionally (and if it differentiates between Mac paths and valid Linux paths, how it does so).

2. `"The leak itself is being fixed at its source: you approved that fix as item 9. Seats started before it lands still carry the variable until they are restarted, so this choice only decides how the launcher treats that leftover."` [s20, s21]
The text presents this decision as a temporary problem existing only until pre-existing seats restart, but formulates options Y and N as permanent design choices without defining a stopping point, sunset condition, or plan for removing the warning/block once all seats have restarted.

3. `"It refuses to start until you run unset NEDSCHORUS_AGENTS_ROOT, then starts the same seat in the same place."` [s16] and `"N: refuse until you clear the variable."` [s25]
The text does not specify the failure mechanics under Option N — specifically the exit status code, whether an actionable error message is printed to stderr directing the caller to run `unset`, or how non-interactive/automated invocations handle the refusal.

4. `"N: refuse until you clear the variable."` [s25]
The text does not define what constitutes clearing the variable — specifically whether an empty string (`NEDSCHORUS_AGENTS_ROOT=""`) satisfies the requirement or if the variable must be entirely removed from the environment via `unset`.

## Sentence coverage (added by cold-read-fast-read)

- 25 sentences in the document, 25 restated.
- Every sentence was restated.
- The reviewer read `/Users/el/agents/merge-lane-backlog/.claude/worktrees/explain-skill-folds-in-the-identifier-rules/cold-read-records/explain-reply-draft-2026-09-29/explain-reply-draft-with-sentence-ids.md`, the marked copy of `/private/tmp/claude-501/-Users-el-agents-merge-lane-backlog/c361f374-c9ca-40c3-9241-3b8a1de47a36/scratchpad/explain-reply-draft.md`, kept beside this report.
