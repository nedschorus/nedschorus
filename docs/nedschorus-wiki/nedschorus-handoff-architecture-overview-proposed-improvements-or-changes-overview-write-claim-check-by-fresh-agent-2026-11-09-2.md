# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-09)

Assertions of the overview that the claim check against commit 731c1517b92f4ddaa928f0cfbc7afe98dbc275ad found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/c39cbdf2d362ca565b27ae65b14c052b8a29eeac-2026-11-09T04-56-31-029366Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: handoff-supervisor: "These leftovers go between the opening of the initial-agent-instructions and their next step", under the background-subagent instructions, with listing counts, and the deleted branches above that sentence.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The instructions, counts and deleted-branch placement are supported by `nc-systems/handoff/handoff-supervisor.py:1633-1639` and :1703-1707.
> - Contradicted for prompts that have no next step, such as a resume prompt or the first prompt of an agent-seat without a session-handoff. There the leftovers go after the prompt: `nc-systems/handoff/handoff-supervisor.py:1689` "or after it when it has no next step"; :1714-1715 `if not next_step_heading: return f"{prompt}\n\n{inserted}"`.
> - Incomplete wording; no agent would act wrongly on it.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: handoff-supervisor: at its first launch it carries out a waiting session-handoff, unless started with `--resume-session-id`; "otherwise it starts fresh when an exit is recorded, and else resumes the agent-seat's last transcript worth resuming", and stops when it cannot read the transcript folder.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The handoff, `--resume-session-id`, exit-record and stop parts are supported by `nc-systems/handoff/handoff-supervisor.py:2393-2403`, :2406-2444 and :2455-2463.
> - The sentence leaves out a third case that also starts fresh with no exit recorded: `nc-systems/handoff/handoff-supervisor.py:2449` `and not settings.first_prompt_wins_over_crashed_transcript`, set by `--first-prompt-file-wins-over-crashed-transcript` (:2697-2703).
> - Incomplete; no agent would act wrongly on it.
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: `clean-worktrees.py`: "a worktree with no owner file, or locked ... is kept".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Contradicted for merge-lane review checkouts, which have no owner file and are removed: `scripts/clean-worktrees.py:6-8` "Only a worktree holding an owner file, or a merge-lane review checkout ... can be removed", and :64-71 "It is removed when that pull request was merged or closed at least 24 hours ago".
> - Also `scripts/worktree-owner-file-read-and-write.py:38-41`.
> - The owner-running and owner-stopped rules are supported by `scripts/clean-worktrees.py:34-48`.
> - Incomplete; no agent-seat other than merge-lane-2 works in that directory, so no agent would act wrongly.
State: open
