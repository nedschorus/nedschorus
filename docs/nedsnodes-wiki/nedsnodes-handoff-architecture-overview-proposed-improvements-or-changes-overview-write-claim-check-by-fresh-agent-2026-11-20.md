# Proposed improvements or changes: nedsnodes-handoff-architecture-overview.md (overview claim check, 2026-11-20)

Assertions of the overview that the claim check against commit 01244b69d330737fa2f0d29044889d0979ec8070 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedsnodes-logs/overview-write-architecture-overview-claim-check-reports/nedsnodes-handoff-architecture-overview/a344ba612326904a96aaab99bb1f5566f5d0ac9b-2026-11-20T01-59-50-593666Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: The `list` command of `uncommitted-work-snapshots.py` is run by a person, or by an agent its initial-agent-instructions send there.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The statement is true as far as it goes, but as this module's only entry-point line it leaves out the commands the initial-agent-instructions actually send agents to. nn-systems/handoff/uncommitted-work-snapshots.py:649 `3. Run the entry's command. To keep one file or more, run \`restore\` ... To keep nothing, run \`python3 {module} discard <ref>\`.` and :13-17 `each entry ending with the restore or discard command that handles it`. The `list` command appears there only for overflow or a listing failure (:702, :709). Entry points should also name `restore` and `discard` (usage at :29-40). No agent would act wrongly, because the restore steps in the prompt are complete.
State: open
