# Proposed improvements or changes: nedsnodes-handoff-architecture-overview.md (overview claim check, 2026-11-20)

Assertions of the overview that the claim check against commit def45b1a956380a8c5e036ae1920c81476f65e0b found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedsnodes-logs/overview-write-architecture-overview-claim-check-reports/nedsnodes-handoff-architecture-overview/e58308bc81b6568017a777f497c826a5fd6ed400-2026-11-20T20-50-48-342979Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: `nn-systems/handoff/session-handoff-field-names-common.py`: the session-handoff's field names, which the writer script and the handoff-supervisor load, so that renaming a field is one edit; every other reader takes them through the handoff-supervisor.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Two session-handoff field names are defined in handoff-supervisor.py, not in this module: handoff-supervisor.py:410-411 `COLD_READ_FULL_RUN_COMMAND_REFUSED_DURING_HANDOFF_DEFERRAL_FIELD_PREFIX = ("cold-read-full-run-command-refused-during-handoff-deferral-")` and :412 `BACKGROUND_TASK_PAST_WAIT_LIMIT_FIELD_PREFIX = "background-task-past-wait-limit-"`.
> - The writer takes them from the supervisor, not from the module: handoff-write-and-check-supervisor.py:152-154.
> - Ranked fix-later: renaming one of these fields still takes one edit, in handoff-supervisor.py, and a search finds it.
State: open
