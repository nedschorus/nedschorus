# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-09)

Assertions of the overview that the claim check against commit a17081fe3b0d0c6092273fa1e910bd22528cdd78 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/b7ae570d5bf93bceaf69d8d7d04bf3f3ee37db26-2026-11-09T01-08-43-906731Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: The successor's initial-agent-instructions give the next step and the sync's result, and either name the conversation-tail and roster or say where the transcript is. On the Mac they carry the memory review when due. For agent-instructions-editor alone they carry "an overview refresh reminder for each system whose code has moved past the commit its nc-architecture-overview names".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> Supported parts:
> - handoff-supervisor.py:1130, :1135, :1144 (roster) and :1165 (next step).
> - handoff-supervisor.py:1204-1210: when extraction failed, the note gives `that session's transcript is {self.unextracted_transcript_path}`.
> - handoff-supervisor.py:1576-1580: no memory review line on ned-box or before noon Pacific.
> - handoff-supervisor.py:2483-2484: `if settings.agent == AGENT_SEAT_GIVEN_OVERVIEW_REFRESH_LINES`.
> Contradicting lines: the reminder is not given for every system whose code moved. It is withheld when an open pull request already changes that overview, or when the user was shown that refresh earlier the same day.
> - handoff-supervisor.py:1530-1532 `print(f"handoff-supervisor: overview check for {system} withheld its line: " f"the open pull request \"{title}\" ({url}) already changes " f"{overview_path}")`
> - handoff-supervisor.py:1564-1565 `print(f"handoff-supervisor: overview check for {system} withheld its line: the " f"user was shown this overview's refresh today`
> The daily withholding is stated under handoff-architecture-overview-refresh-user-shown-mark.py. The open-pull-request withholding is stated nowhere in the overview. No agent would act wrongly on the omission.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: `clean-worktrees.py` removes the worktrees of the clone, other than the reference-checkout, whose work is done. "a worktree with no owner file, or locked ..., is kept". While its owner runs a worktree goes only after its pull request merged or closed and nothing is uncommitted; once its owner has stopped it goes unless an open pull request keeps it, after branching and snapshotting.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> Supported parts:
> - clean-worktrees.py:5-6 `Every worktree of the clone except its main checkout, the reference-checkout`
> - clean-worktrees.py:33-47: the while-running and once-stopped rules.
> Contradicting lines: a merge-lane review checkout has no owner file and can still be removed.
> - clean-worktrees.py:13-14 `it has no owner file, as agent-homes and worktrees made by hand have, and is not a merge-lane review checkout;`
> - clean-worktrees.py:63-70 `A worktree with no owner file directly inside ~/.cache/merge-lane-review-worktrees ... is removed when that pull request was merged or closed at least 24 hours ago`
> The overview's rule is incomplete, but no agent works in those checkouts, so no agent would act wrongly.
State: open
