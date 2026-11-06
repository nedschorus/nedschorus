# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-06)

Assertions of the overview that the claim check against commit e0f608a0a433a189da0c362861753d098c48a959 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/eb5b14ff122f03688551f6bfc827f605d3fd032d-2026-11-06T15-33-42-134028Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: These leftovers go between the opening of the initial-agent-instructions and their next step, under one sentence that says to keep, delete or hand on each before the next step. Each entry opens with how many first prompts have listed it, and the branches the first-prompt list deleted go above that sentence.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - `nc-systems/handoff/handoff-supervisor.py:1690-1691` "The prompt with the leftovers between its opening and its next step, or after it when it has no next step."
> - `nc-systems/handoff/handoff-supervisor.py:1712-1713` "if not next_step_heading: return f\"{prompt}\n\n{inserted}\""
> - A resume launch uses RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF (`nc-systems/handoff/handoff-supervisor.py:249-253`), which has no next-step heading. For a resume, which the same paragraph says every launch includes, the leftovers therefore come after the prompt.
> - The sentence, the counts and the deleted-branches placement are borne out at `nc-systems/handoff/handoff-supervisor.py:1638-1642`, `:1672` and `:1701-1705`.
> - Suggested fix: add "or after the prompt when it has no next step".
State: open
