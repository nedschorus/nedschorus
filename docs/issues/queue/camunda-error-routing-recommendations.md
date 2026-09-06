---
status: research recommendations
research-as-of: 2026-09-06
disposition: queued for user review
---

# Camunda: keep operational retries separate from semantic repair

**Borrow the error-routing distinction. Camunda's runtime and BPMN notation are unnecessary for implementing this particular improvement.**

The relevant sources are [error events](https://docs.camunda.io/docs/components/modeler/bpmn/error-events/), particularly “Catching the error” and “Business error vs. technical error,” and [architecture guidance](https://docs.camunda.io/docs/components/agentic-orchestration/ao-design/). They separate explicit process reactions from generic retries and incidents, and describe where deterministic work and human intervention belong. An enclosing subprocess can handle an error without each inner step carrying the full recovery process.

The local consumer is [#21](https://github.com/nedschorus/nedschorus/issues/21) and its [queued test-failure procedure](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/docs/issues/queue/21-diagnose-failure-test-procedure.md), together with [the queued agent-loop rules](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/docs/wiki/queue/agent-loop-rules-draft.md). The live [scripts/cold-read-cell-common.py](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/scripts/cold-read-cell-common.py) handles operational production of a report; it does not decide whether that report's findings are correct.

A small controller can keep PASS, FAIL, and HELP as the visible outcomes while carrying an explanation that tells it which established path applies:

| Evidence | Appropriate reaction |
| --- | --- |
| No report was produced because the runtime could not complete | Apply the caller's existing operational failure policy. |
| The task lacks necessary information | Return the question to its sender and prepare a revised task. |
| An artifact fails its governing check | Start a bounded repair or diagnosis attempt with the failed check as evidence. |
| Diagnosis cannot resolve the responsible scope | Ask the human with the diagnosis and supporting artifacts. |

These are routing examples for the design, not a new universal outcome schema. In particular, the current grid's required-model rules remain controlling: the inspected code does not permit silently substituting another model when an Opus cell is absent.

The useful simplification is that ordinary nodes report evidence and their simple outcome; a shared handler owns the broader response. The handler may inspect the dependency chain, but its repair request remains bounded. The existing queued diagnosis procedure already provides more semantic detail than a BPMN error event: code, test expectations, design, instrument, and environment can all be responsible.

Camunda does not provide NC's root-cause judgment merely by catching an error. Implement the arbitrator as a bounded diagnostic task with explicit evidence and human escalation. Apply the retry ceiling of the governing work item; this note does not settle the different retry counts discussed in the architecture and queued rules.

**First proof.** Use the recorded stale-daemon incident in the diagnosis queue: show that unchanged failures route to an environment hypothesis rather than repeatedly editing code that the running process never loaded. Keep runtime retries and evidence-driven repair attempts distinguishable in the record.
