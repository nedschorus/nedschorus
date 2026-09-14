# ADR form — extract from `engineering:architecture` before its curation-walk drop (2026-07-30)

Queued for the user's drain. Destination when drained: the `md-write` founding skill's text (step-1 build) or wiki doctrine — wherever NC's decision-record writing lands.

The one piece that survives the drop (the skill's design-evaluation half is subsumed by design-change, [nedschorus#17](https://github.com/nedschorus/nedschorus/issues/17)): the **architecture decision record form**, matching the walk-ruled decisions layer of design docs (append-only, dated, drift-immune, superseded not edited):

- **Title** — the decision as a noun phrase
- **Status** — proposed | accepted | superseded by [[link]]
- **Date** — decision date, absolute
- **Context** — the forces that made a decision necessary (what was true, what was constrained)
- **Decision** — one paragraph, active voice: what was chosen
- **Consequences** — what follows, good and bad, including what becomes harder
- **Supersession** — a later ADR links back; the old one is never edited

One NC-specific addition per the walk's SSOT rulings: a **claims line** — any falsifiable claim the decision creates (candidate for enforcement) is named explicitly, so the claims registry can pick it up.
