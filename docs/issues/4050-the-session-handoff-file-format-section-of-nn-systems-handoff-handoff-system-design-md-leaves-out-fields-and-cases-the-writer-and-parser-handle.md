---
issue: "[The session-handoff file format section of `nn-systems/handoff/handoff.system.design.md` leaves out fields and cases the writer and parser handle](https://github.com/nedsnodes/nedsnodes/issues/4050)"
---

# The session-handoff file format section of `nn-systems/handoff/handoff.system.design.md` leaves out fields and cases the writer and parser handle

## What is wrong

`nn-systems/handoff/handoff.system.design.md` makes its section "The session-handoff file format" the one part of the design that states mechanism, since the writer script, `nn-systems/handoff/handoff-write-and-check-supervisor.py`, and the handoff-supervisor's parser, `parse_handoff_file` in `nn-systems/handoff/handoff-supervisor.py`, must agree on it. The section does not match them:

- It says it gives "the two" fields whose form takes more than a line, the verbatim next step and the spawned-subagent-roster, then has four subsections: those two, "The background-task fields" and "The handoff-deferral fields".
- It never gives the field `background-task-past-wait-limit-<n>`, which `write_handoff_file` writes for a task past its wait-limit, although section "What a reincarnate-seat kills, and how work survives it" says the session-handoff lists such a task's command, kind, wait-limit, time run and table path. Its example also leaves out `restart-counter`, the earlier name of the sequence-number field, which `write_handoff_file` always writes beside it.
- It says a background Bash task "counts as running when the agent-session's transcript records its launch and no completion notification names it", and a subagent's last event decides the spawned-subagent-roster; a task or subagent stopped with the `TaskStop` tool gets no `<task-notification>`, and the writer counts the `TaskStop` result as its end, which the section does not say.
- It does not say what form a description takes when it holds a double quote or a line break, nor what start time is written when a launch record has no readable time; for the second the writer writes "an unrecorded time"; `background_task_field_lines` puts the description between double quotes without escaping a quote it holds, and whether it collapses a line break is unverified.
- It allows hand-written session-handoffs but does not say what the successor gets when such a file has no usable `next-step` line, or what the parser does with a line that is not `key: value`.
- "Writing the block last ... a content line that happens to look like `key: value` cannot shadow a real field" is broader than its own "Compatibility" paragraph, which gives a case where such a line becomes `dont-restart` for an older handoff-supervisor.
- `completed` is the status of both an interim and a final task-notification, and the section does not say how the writer tells them apart.

The findings come from the cold-read-full-run `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/handoff.system.design-2026-11-20-6`; its `cold-read-triage.md`, in that directory beside the reports named here, gives each of these findings the link of the GHI filed from this file: `agy-hunt-gemini-4-argon-high.md` 4, 7, 9, 10 and 21; `claude-hunt-deep.md` 10, 14, 15 and 16; `claude-hunt-second-strongest-model.md` 10, 21, 22, 23 and 25; `codex-hunt-deep.md` 10 and 12; `codex-hunt-second-strongest-model.md` 6.

## Why it matters

Whoever writes or tests a reader of the session-handoff, or checks one by hand, takes this section as the specification; a field it leaves out cannot be recognised, and a case it leaves open is decided differently by each reader.

## Next action

The agent-seat agent-instructions-editor checks each point above against `write_handoff_file` in the writer and `parse_handoff_file` on main, settling each case with a unit test where none exists, such as a description holding a double quote, written and read back; then in one pull request makes the section state the format the code writes and reads, citing those tests, and brings the user any point where the code's behaviour is itself in question, such as an unescaped quote. The same pull request adds a test that fails when a field `write_handoff_file` writes is missing from the section, or the section names one it does not write, so the two cannot drift apart unnoticed again. The design's change gets the cold-read-full-run the /cold-read skill gives a design.
