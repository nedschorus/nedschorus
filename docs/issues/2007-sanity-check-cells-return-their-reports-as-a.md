---
issue: "[Sanity-check-cells return their reports as a JSON object checked against a schema, so the runner stops guessing from prose whether a text is a report](https://github.com/nedschorus/nedschorus/issues/2007)"
---

# Sanity-check-cells return their reports as a JSON object checked against a schema, so the runner stops guessing from prose whether a text is a report

## What has gone wrong

`scripts/sanity-check-adversarial-prompts.py` saves the last message of each sanity-check-cell as that sanity-check-cell's report, and has to guess from the prose whether the message is a report at all. On 2026-09-15 two of the three claude sanity-check-cells of one sanity-check lost their reports: the checkout-freshness Stop hook spoke inside each sanity-check-cell after the review was written, the sanity-check-cell answered the hook, and the runner saved the answer as the report. One of the two saved answers began "The report above is my complete reply." The runner's test for an empty report did not fire, because the text was not empty. The record is GHI [A Stop hook's report inside a claude -p review cell displaces the cell's report: two of three claude cells lost tonight](https://github.com/nedschorus/nedschorus/issues/397).

The fix, [Sanity-check cells: keep project hooks out, refuse a text that is not a report](https://github.com/nedschorus/nedschorus/pull/417), kept project hooks out with `--setting-sources user`, and added a guess: a text that lacks any of a list of words, such as "leanness" or "hard parts", is refused as not a report. The guess is still how the runner tells a report from anything else, and it can be wrong both ways: a report that words a section differently is refused, and a reply that happens to contain the words is saved.

## Where the prose is read, on main at 92912c534

- `ADVERSARIAL_PROMPT_REPORT_REQUIRED_PHRASES` (line 512) and `missing_report_phrases` (line 949): the required words for each adversarial prompt. A text missing one fails the sanity-check-cell with cause class `not-a-report` (`CAUSE_CLASS_NOT_A_REPORT`, line 414).
- `quote_scan` (line 930): finds quoted spans in the report with a regular expression over straight and curly double quotes, and warns about each one found in no tracked file.
- The two launches: `run_claude` (line 587) runs `claude -p --output-format text` (line 614), the prompt on stdin; `run_codex` (line 733) runs `codex exec ... --output-last-message <file>` (line 750), the prompt as the last argument.

## What to do

Have each sanity-check-cell end with a JSON object that the agent-binary constrains to a schema, and have the runner read its fields instead of guessing.

- **One schema per adversarial prompt**, kept as one file that both agent-binaries read, for example beside that prompt under `docs/agents/`: Codex takes its path, and `run_claude` reads the file and passes its text. Each section the prompt requires, the ones `ADVERSARIAL_PROMPT_REPORT_REQUIRED_PHRASES` stands for today, becomes a required field. A finding that quotes the reviewed text carries its quotes in a list field of its own, which may be empty.
- **The saved report** is Markdown the runner renders from the object, for example one heading per field, in the order the prompt lists its sections, with each finding's quotes under it. Whoever reads a saved report then finds the sections it has today.
- **The quote scan** reads the quote fields instead of finding quotes with a regular expression. A quote written into a prose field rather than a quote field is not scanned; the prompt tells the model where quotes go.
- **Delete** the required-word list, `missing_report_phrases` and the quote regular expression.

Both agent-binaries the runner uses can constrain the answer:

- Claude Code: `claude -p --json-schema '<schema>' --output-format json`; the answer is in the result's `structured_output` field.
- Codex: `codex exec --output-schema <FILE>`, "Path to a JSON Schema file describing the model's final response shape" (`codex exec --help`, codex-cli 0.159.3 on ned-box). The final message that `--output-last-message` writes is then the JSON object.

Do it now rather than refining the word list: the user decided on 2026-10-23, "once we decide to make a change, to make it now, not do throwaway work." Dates here are UTC.

### Two traps found on ned-box with Claude Code 2.1.309

reboot-test tested `claude -p --json-schema` on 2026-10-23, record `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/reboot-test/claude-p-json-schema-spike-2026-10-23/README.md`. The final answer was schema-valid after many tool calls. Two traps:

1. An invocation of `claude -p` that never produces valid output still looks successful. When the model could not satisfy the schema, `claude -p` exited 0 with `"subtype": "success"` and `"is_error": false`; only `"structured_output": null` showed the failure. The runner must treat a null `structured_output`, and one that lacks a required field, as a failed sanity-check-cell, for example with the existing cause class `not-a-report`, and never save it. What Codex does when it cannot satisfy `--output-schema` has not been tested, so the runner parses the Codex sanity-check-cell's final message as JSON and checks its required fields too; text that is not JSON, or JSON that lacks a field, fails the same way.
2. `--allowedTools` takes any number of values and swallows a prompt given after it as one more tool name. `run_claude` already gives the prompt on stdin; keep it there when adding `--json-schema`.

### Tests

The record of GHI 397 is a test case: a sanity-check-cell whose final message is a reply to a hook, not a report. Add three for trap 1: a Claude Code result with a null `structured_output` and exit 0, a Claude Code object that lacks a required field, and a Codex final message that is not JSON. Each must fail the sanity-check-cell with a message that says so. Trap 2 needs no test of its own while the prompt stays on stdin. Check the failure paths by mutation testing.

## Next action

cold-read-research writes one schema for each adversarial prompt and opens one pull request that moves both agent-binaries' launches and the runner's reading onto them, with the tests above. cold-read-research wrote most of `scripts/sanity-check-adversarial-prompts.py`: 974 of its 2,098 lines on main come from PR [Sanity-check cells read a copy of the reviewed commit](https://github.com/nedschorus/nedschorus/pull/885) and PR [The sanity-check runner's stop lets agent-binaries end, and a stop that ends no cell ends the run as finished](https://github.com/nedschorus/nedschorus/pull/928), whose commits' `Claude-Session` links appear in cold-read-research's transcripts. The three adversarial prompts under `docs/agents/` change too, to ask for the object, so that pull request needs the user's approval of their new wording.
