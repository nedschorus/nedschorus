---
status: research recommendations
research-as-of: 2026-09-06
disposition: queued for user review
---

# LangGraph: durable questions without retaining agent context

**Borrow the boundary between a durable work item and a replaceable execution attempt. Adopt the runtime only if persistent workflow execution becomes cheaper with it than with the existing controller.**

The immediate consumer is [#41](https://github.com/nedschorus/nedschorus/issues/41). Its question contract is explicit: an agent returns QUESTION, the invoker revises the prompt, and a fresh agent attempts the task. The current [architecture](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/docs/cross-project/nedschorus-ai-native-software-development.md) also describes durable work-item state and human decision packets, while identifying the persistent master as unbuilt and requiring a design decision.

| Exact source location | Relevant mechanism |
| --- | --- |
| [Interrupts: pause and resume](https://docs.langchain.com/oss/python/langgraph/interrupts#pause-using-interrupt) | Persist a JSON-serializable question and resume the associated workflow after input arrives. |
| [Interrupts: handling multiple interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts#handling-multiple-interrupts) | Match each answer to its particular pending interrupt. |
| [Interrupts: side effects before an interrupt](https://docs.langchain.com/oss/python/langgraph/interrupts#side-effects-called-before-interrupt-must-be-idempotent) | A resumed node restarts from its beginning, so preceding effects can execute again. |
| [Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api) — tasks, persistence, and idempotency | Separates recoverable task results from the surrounding execution. This API does not require a visual graph-building style. |

For NC, the first implementation need not resume an agent session. Store the question against its work item and input version, let the worker terminate, and incorporate the answer into a new bounded input package. Start a fresh attempt through the eventual run-agent primitive. Keep the same work identity across that wait; create a new attempt identity. That preserves the existing fresh-context rule.

Question-to-answer matching matters once several independent nodes can ask simultaneously. A specific question identifier and the artifact version it concerns are sufficient; a larger event platform is not required just to avoid answering the wrong pending question. Reuse whatever durable work record the controller already owns.

LangGraph's replay behavior supplies concrete cases for the design: a question survives a stopped process; an answer resumes the correct work; a repeated resume does not repeat an external action. Resolve those cases at the actual effect boundary. NC already has an example of duplicate-effect handling in [scripts/main-gatekeeper.py](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/scripts/main-gatekeeper.py) — find_existing_check_in — rather than needing to invent all recovery ideas from scratch.

This recommendation does not replace [#116](https://github.com/nedschorus/nedschorus/issues/116)'s machine-login recovery or [#242](https://github.com/nedschorus/nedschorus/issues/242)'s seat-process checks. A persisted workflow cannot by itself reopen terminal windows, determine whether a named seat is alive, or restore the user's interactive environment.

**First proof.** When the controller build is authorized, run a small human-question scenario that stops its worker, retains the pending question, accepts an answer, and launches a fresh attempt with the revised input. Keep LangGraph as the alternative implementation if maintaining that behavior and its recovery cases becomes more work than the dependency removes.
