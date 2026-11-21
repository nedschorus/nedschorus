# Proposed improvements or changes: nedsnodes-handoff-architecture-overview.md (overview claim check, 2026-11-20)

Assertions of the overview that the claim check against commit def45b1a956380a8c5e036ae1920c81476f65e0b found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedsnodes-logs/overview-write-architecture-overview-claim-check-reports/nedsnodes-handoff-architecture-overview/9e1363ae17500ef1e89a5b5cfdef8335e67872af-2026-11-20T20-39-55-747649Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: These leftovers go between the opening of the initial-agent-instructions and their next step, under instructions to hand them to a background subagent; each entry opens with a count of first prompts; the branches the first-prompt list deleted go above those instructions.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The instructions, the counts and the placement of deleted branches are borne out by handoff-supervisor.py:1823-1829 `LEFTOVERS_BEFORE_THE_NEXT_STEP_SENTENCE` and :1893-1897.
> - The placement claim fails for a launch whose prompt has no next step, such as every resume or a first-prompt launch. handoff-supervisor.py:1879-1880 `"""The prompt with the leftovers between its opening and its next step, or after it when it has no next step.` and :1904-1905 `if not next_step_heading: return f"{prompt}\n\n{inserted}"`. Such prompts are RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF (:280-284), which carries no NEXT_STEP_HEADING.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: The task list is written by Claude Code, by the crash watcher, by the `restore` command, and by `clean-worktrees.py`, "which marks such a task completed once its branch's work is done"; the writer removes completed tasks after comparing log-store copies written by the mirror and by itself.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Most of this is borne out: handoff-agent-crash-watcher.py:1118-1123; uncommitted-work-snapshots.py:35-37; handoff-write-and-check-supervisor.py:830-861; transcript-mirror-to-log-store.py:191.
> - But clean-worktrees.py:249-252 also completes the task when no ref holds the restore commit at all, with no merge: `marks the task completed ... when that commit is reachable from origin/main, or when git for-each-ref --contains names no ref holding it`. So a deleted, unmerged restored branch also closes it, which is not "work done".
State: open
