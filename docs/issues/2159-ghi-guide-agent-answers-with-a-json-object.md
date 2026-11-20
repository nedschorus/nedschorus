---
issue: "[ghi-guide-agent answers with a JSON object checked against a schema, so its callers stop sorting its prose replies](https://github.com/nedschorus/nedschorus/issues/2159)"
---

# ghi-guide-agent answers with a JSON object checked against a schema, so its callers stop sorting its prose replies

## What has gone wrong

ghi-guide-agent, the project's knowledge agent over its GHIs, named ghi-info until PR [Rename ghi-info to ghi-guide-agent](https://github.com/nedschorus/nedschorus/pull/1878) merged on 2026-10-29, answers in prose, and two programs sort that prose with regular expressions and string prefixes. Each time ghi-guide-agent, or a hook speaking inside its agent-session, wrote something the sorting did not expect, the caller got a wrong answer with exit 0, and the fix was one more pattern. Four fixes so far:

- [ghi-info ask: return the answer, not whatever the session said last](https://github.com/nedschorus/nedschorus/pull/474) (commit 1e84c0c6d, 2026-09-17). ghi-guide-agent answered a reading-list question, then 13 seconds later answered the checkout-freshness Stop hook. `scripts/ghi-info-ask.py`, now `scripts/ghi-guide-agent-ask.py`, returned the last message, "No action needed on my part -- this session hasn't touched any scripts or tests", with exit 0, and the ghi-write skill's fallback ladder never fired. The fix added `reply_answers_the_question`, which refuses a reply that names no GHI.
- [ghi-info-ask reports out-of-scope and escalate: as errors that say what to do, not as answers](https://github.com/nedschorus/nedschorus/pull/813) (commit bf478363b, 2026-09-29). ghi-guide-agent's two boundary replies went to stdout with exit 0, as if they were answers. The fix added `is_passthrough_reply` and `caller_message_for_passthrough_reply`, and `scripts/ghi-issue-write.py` learned to find the resulting messages on stderr by their opening words.
- [ghi-info's two boundary replies say what they mean: not-about-issues and ask-user-about-ruling:](https://github.com/nedschorus/nedschorus/pull/899). Renaming the two replies meant reading the old words too, in `RETIRED_BOUNDARY_REPLY_WORDS`, because a resumed ghi-guide-agent agent-session answers with the words its own cold-start prompt taught it.
- [ghi-info-ask: a verdict: unrelated reply is an answer, not a rejection](https://github.com/nedschorus/nedschorus/pull/1041) (commit 6ec9645b5, 2026-10-04). The test of a reply that PR 474 added threw away every correct `verdict: unrelated`, because that verdict names no GHI: ghi-guide-agent gave it 15 times between 2026-09-27 and 2026-10-04, and each time create-GHI logged "adjudication skipped" and filed without asking whether a GHI already covered the same ground.

## Where the prose is sorted, on main at 3d5591c4b

- `scripts/ghi-guide-agent-ask.py`: `COLD_START_PROMPT_TEMPLATE` (line 232) tells ghi-guide-agent the reply formats, as prose; `POINTER_PATTERN` and `VERDICT_UNRELATED_LINE_PATTERN` (lines 226 and 229), `RETIRED_BOUNDARY_REPLY_WORDS` (line 307), `is_passthrough_reply` (line 319), `caller_message_for_passthrough_reply` (line 358) and `reply_answers_the_question` (line 379) sort the reply. `run_claude` (line 544) already launches `claude -p --output-format json` with the prompt on stdin.
- `scripts/ghi-issue-write.py`: `adjudicate` (line 1037) asks for a one-line verdict in prose and finds it by looking for a line that starts with `verdict:` (lines 1114-1117), then pulls the number out of it with a regular expression. `ruling_conflict_from_stderr` (line 492) reads ghi-guide-agent's question about a user-ruling back out of `ghi-guide-agent-ask.py`'s stderr by copies of that program's message text (`GHI_GUIDE_AGENT_ASK_NO_LIST_MESSAGE_OPENINGS`, line 440), including the ` (held in GHI <n>)` suffix (`GHI_GUIDE_AGENT_ASK_RULING_QUESTION_RULING_GHI_NUMBER_SUFFIX_PATTERN`, line 451), and `scripts/ghi-issue-write-test.py` (lines 1405-1420) checks that the copies stay equal to the originals.

## What to do

Have ghi-guide-agent's final answer be a JSON object that `claude -p --json-schema '<schema>'` constrains, and have `ghi-guide-agent-ask.py` read its fields instead of sorting text. `ghi-guide-agent-ask.py` passes `--json-schema` on every `claude -p` turn it runs, the drift recheck turn (line 840) included.

- **One schema** covers the four request forms that `COLD_START_PROMPT_TEMPLATE` lists and the two boundary replies, for example through a `kind` field with five values: `reading-list` (form 1, and form 3, whose corrected reading list is a reading list too), `verdict` (form 2), `repair` (form 4), `not-about-issues` and `ask-user-about-ruling`. Each kind would have its own fields: the GHI numbers of a reading list and its note lines; the verdict (`too-similar`, `related` or `unrelated`) and its GHI numbers; a repair's outcome (`done`, `no-change` or `blocked`) and its sentence; and, for a question about a user-ruling, the number of the GHI that holds the user-ruling and the sentence naming the user-ruling and the doubt. The builder decides the exact design and field names.
- **`ghi-issue-write.py` never runs `claude` itself**: it runs `ghi-guide-agent-ask.py` as a subprocess. So `ghi-guide-agent-ask.py` has to hand the answer's fields on as data, for example under a flag that prints them as JSON on stdout whatever the exit code, and `ghi-issue-write.py` asks for that and reads the verdict, and the number of the GHI that holds a user-ruling, from it; the builder decides the interface. `ghi-issue-write.py` then no longer needs the copied message openings, the copied suffix pattern or the test that keeps them equal, and they go. Without that request, `ghi-guide-agent-ask.py` prints what it prints today, with the same exit codes.
- **The old reply words go in the same pull request.** The values the schema allows are the only words ghi-guide-agent can answer with, even in a resumed agent-session that was started before the change, so `RETIRED_BOUNDARY_REPLY_WORDS` and the regular expressions and prefix lists the JSON replaces are deleted.

Do it now rather than adding a fifth pattern: the user decided on 2026-10-23, "once we decide to make a change, to make it now, not do throwaway work." Dates here are UTC.

### Two traps found on ned-box with Claude Code 2.1.309

reboot-test tested `claude -p --json-schema` on 2026-10-23, record `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/reboot-test/claude-p-json-schema-spike-2026-10-23/README.md`. The final answer was schema-valid after many tool calls. Two traps:

1. An invocation of `claude -p` that never produces valid output still looks successful. When the model could not satisfy the schema, `claude -p` exited 0 with `"subtype": "success"` and `"is_error": false`; only `"structured_output": null` showed the failure. `ghi-guide-agent-ask.py` must treat a null `structured_output`, and one that lacks a field it reads or holds a value outside the schema, as a failed ask: it fails with a message that says what came back, and never passes it on as an answer.
2. `--allowedTools` takes any number of values and swallows a prompt given after it as one more tool name. `run_claude` already gives the prompt on stdin; keep it there when adding `--json-schema`.

`--json-schema` also works on a `--resume` of an agent-session that began without it, which is how `ghi-guide-agent-ask.py` reuses the stored ghi-guide-agent agent-session. The spike record does not show this case, since its run 3 resumed without `--json-schema`; the subagent that wrote this GHI-MD tried it on ned-box on 2026-10-23 with Claude Code 2.1.309: a `claude -p` turn without the flag, then a `--resume` of that agent-session with `--json-schema`, which returned a schema-valid `structured_output` that recalled the first turn's words, under the same agent-session id.

### Tests

Each failure above is a test case: a hook's reply after the answer, a boundary reply, a `verdict: unrelated`. Add two for trap 1: a reply whose `structured_output` is null with exit 0, and one whose `structured_output` lacks a field or holds a value outside the schema; both must fail the ask with a message that says so. Trap 2 needs no test of its own while the prompt stays on stdin. Check the failure paths by mutation testing.

## Next action

reboot-test writes the schema and opens one pull request that moves `ghi-guide-agent-ask.py` and `ghi-issue-write.py` onto it, with the tests above. reboot-test wrote most of `scripts/ghi-issue-write.py`, in PR [Build the GHI write tool's create verb](https://github.com/nedschorus/nedschorus/pull/569) and PR [Build the GHI write tool's edit verb](https://github.com/nedschorus/nedschorus/pull/596), and wrote PR 813 above. Most of `scripts/ghi-guide-agent-ask.py` came from PR [ghi-info's ask path: the GHI mirror and the ask wrapper (nedschorus#46, first half)](https://github.com/nedschorus/nedschorus/pull/143), written by agent-seat mac-ubuntu-bridge on the Mac, whose newest transcript mirrored on ned-box is from 2026-09-23; if mac-ubuntu-bridge still runs, reboot-test tells it before starting.
