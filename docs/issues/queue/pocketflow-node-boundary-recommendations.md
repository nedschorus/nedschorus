---
status: research recommendations
research-as-of: 2026-09-06
disposition: queued for user review
---

# PocketFlow: useful node boundaries and mechanical reduction

**Borrow the preparation/execution/post-processing boundary and the code-reduction example. Keep NC's current runtime wrappers and Cold Read grid.** A framework migration would need to preserve numerous working behaviors while contributing little to the two immediate gaps below.

| Exact upstream location | Piece worth examining | Local consumer |
| --- | --- | --- |
| [pocketflow/__init__.py](https://github.com/The-Pocket/PocketFlow/blob/f74d023f93607b8c3268133339a5e532a949898c/pocketflow/__init__.py) — BaseNode._run | Pass prepared input to execution, then give the result to post-processing. | [#41](https://github.com/nedschorus/nedschorus/issues/41), generic agent invocation. |
| Same file — Node._exec and exec_fallback | A small example separating attempts from the surrounding node. | The existing [shared cell runner](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/scripts/cold-read-cell-common.py), especially run_model_chain. |
| Same file — Flow.get_next_node and Flow._orch | Route using returned action strings and compose a flow as a node. | A future bounded controller; no need to introduce it into today's grid. |
| [cookbook/pocketflow-map-reduce/nodes.py](https://github.com/The-Pocket/PocketFlow/blob/f74d023f93607b8c3268133339a5e532a949898c/cookbook/pocketflow-map-reduce/nodes.py) — ReduceResultsNode | Ordinary code aggregates model-produced records. | [#166](https://github.com/nedschorus/nedschorus/issues/166), consolidating the Cold Read evidence. |
| [pocketflow/__init__.py](https://github.com/The-Pocket/PocketFlow/blob/f74d023f93607b8c3268133339a5e532a949898c/pocketflow/__init__.py) — AsyncParallelBatchNode | Uses asyncio.gather to collect independent executions. | A comparison for fan-out behavior; NC already launches its cells concurrently. |

For [#41](https://github.com/nedschorus/nedschorus/issues/41), the usable NC attachment points are [scripts/cold-read-cell-common.py](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/scripts/cold-read-cell-common.py) — compose_prompt, run_cell, run_model_chain, verify_report, and stamp_provenance — and invocation_builder in each runtime launcher. Preparation already renders the shared template. The runtime-specific callback supplies the command and stdin. The common code checks that a nonempty report exists and records who produced it.

The smallest useful extraction is the generic invocation/result boundary when a second caller needs it. Keep report-file verification and Cold Read policy with the Cold Read caller. Preserve the measured stdin handling, runtime flags, model/effort selection, report provenance, and failed-attempt behavior. A smaller-looking runner that loses those behaviors would move complexity into failures.

For [#166](https://github.com/nedschorus/nedschorus/issues/166), add one mechanical post-processing step after the grid completes and its target-fingerprint check has classified the reports. Extract each finding with its original wording, source cell, and quoted passage; group findings whose quotes refer to overlapping spans in the target; order by target position. Ambiguous or unmatched quotes should remain visible for judgment. Keep the source reports.

The current default roster has four defect-hunt reports and two terminology reports. Their formats differ. Read [.claude/skills/cold-read/prompts/defect-hunt.md](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/.claude/skills/cold-read/prompts/defect-hunt.md) and [.claude/skills/cold-read/prompts/terminology.md](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/.claude/skills/cold-read/prompts/terminology.md) before designing extraction. The issue's proposed four-way restatement alignment applies to an older roster; it is not a reason to add restate cells back.

The reducer must not decide that matching passages imply identical defects or that agreement proves truth. Those decisions remain with the commissioning agent and human. This is the part of the MapReduce example worth adapting: mechanically combine the records already produced.

**Fit limits.** PocketFlow's unknown-action behavior warns and ends the flow; that is not NC's explicit HELP contract. Its exception retries also do not implement fresh prompts after a question or semantic root-cause diagnosis. Shared-state separation is a programming convention, not an enforced context sandbox. The core does not replace NC's artifact validation or its current rules for failed required cells.

**First proof.** Use one existing reviewed record set to show that every original finding remains attributable and visible in the consolidated output. Keep the existing report-count, required-model, and changed-target rules. No additional agent call is needed for the mechanical merge itself.
