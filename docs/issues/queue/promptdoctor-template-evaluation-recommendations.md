---
status: research recommendations
research-as-of: 2026-09-06
disposition: queued for user review
---

# PromptDoctor: evaluate rendered prompts without adding a prompt parser

**NC already has the programmatic prompt-construction mechanism it needs. PromptDoctor is a useful evaluation reference, not a replacement for Cold Read or a reason to add prompt-extraction machinery.**

The precise reference is [PromptDoctor, section 3.1.3](https://arxiv.org/html/2501.12521v1), under “Prompt Parsing,” “Prompt Canonicalization,” and “Prompt Patching.” Canonicalization normalizes prompts extracted from code into a common representation. Patching supplies values for placeholders so the prompt can be exercised. The paper's checks target bias, vulnerability, and performance; they do not implement the described naive-reader interpretation protocol.

The local attachment point is [scripts/cold-read-cell-common.py](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/scripts/cold-read-cell-common.py) — compose_prompt. Both runtime cells already call it. It reads one shared template, fills target and report paths, and accepts a draft-template override. The accompanying [scripts/cold-read-cell-common-test.py](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/scripts/cold-read-cell-common-test.py) is the existing mechanical test home. [#23](https://github.com/nedschorus/nedschorus/issues/23) is the owner for broader baseline-versus-candidate evaluation.

For NC's known templates, invoking the actual composer is simpler and more faithful than extracting prompts from Python and reconstructing their meaning. The useful borrowing is the distinction between reviewing a reusable template and testing representative rendered instances.

The smallest extension is to save or otherwise identify the exact rendered prompt used in an evaluation, tied to the selected template and task inputs. Use compose_prompt for both the evaluated and production invocation. Populate values mechanically. Examples should come from the template's actual consumers, including path shapes those consumers already support.

A mechanical check can establish whether required placeholders were replaced and whether the supplied paths identify the intended artifacts. A Cold Read can establish what a fresh reader understood. Task-specific validation still has to establish whether the output is correct. Those responsibilities should remain separate.

There is no recommendation to add an automatic prompt optimizer, replace the current prompt formats, or add new adversarial checks to this cooperative supervised system. The next template experiment should answer a concrete question in issue 23 and keep the current workflow as its baseline.

**First proof.** Demonstrate that the evaluated prompt is the production composer's exact output for that input. Compare baseline and candidate on the same declared task and assertions. If the current composer and caller already provide that evidence, no additional component is needed.
