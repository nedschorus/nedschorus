# 26-dynamic-agent-team-model lifecycle revision — fold in the ghi-info session rulings (queued 2026-08-11)

Queued for the user's drain; a rider from the ghi-info design's integration walk. Destination when drained: [26-dynamic-agent-team-model.md](../../issues/26-dynamic-agent-team-model.md), revised in place (and issue nedschorus#26's body per the revision convention).

The ghi-info design — the first build of the domain-knowledge-agent class, landed at [46-ghi-info-agent-design.md](../../issues/46-ghi-info-agent-design.md) § The ghi-info session — settled lifecycle facts the class definition in #26 predates:

- Active only while taking a turn; otherwise exited. No idle state exists for the class — what persists is a session id, a transcript, and derived data (the mirror), never a process.
- Recycling fires on the first of a set of script-observable triggers, never on the agent's self-assessment; the stance is recycle-eager (an eager recycle costs one cheap reload; a lazy one costs silently wrong answers).
- A resumed session's context drifts from its refreshed data sources, and the agent cannot reliably notice on its own — the wrapper notices for it.

The queued task: revise #26's lifecycle content to carry these as class-level facts rather than ghi-info particulars, so later builds of the class inherit them.
