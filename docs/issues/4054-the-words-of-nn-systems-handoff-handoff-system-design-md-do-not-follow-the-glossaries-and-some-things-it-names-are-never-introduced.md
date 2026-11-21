---
issue: "[The words of `nn-systems/handoff/handoff.system.design.md` do not follow the glossaries, and some things it names are never introduced](https://github.com/nedsnodes/nedsnodes/issues/4054)"
---

# The words of `nn-systems/handoff/handoff.system.design.md` do not follow the glossaries, and some things it names are never introduced

## What is wrong

The handoff-system design, `nn-systems/handoff/handoff.system.design.md`, writes several glossary terms in other spellings, uses one word for two things, and names things that neither it nor a glossary introduces. Examples, each from the design as it stood on 2026-11-20:

- Other spellings of a glossary's term, or of the design's own word: "threshold hook" for the handoff-system glossary's threshold-hook, fourteen times after the components list spells it with the hyphen; "roster" for spawned-subagent-roster; "the deferral" for handoff-deferral; "rulings" for the project glossary's user-ruling; "the successor's instructions" for its initial-agent-instructions; and, beside the design's own words, "retiring agent" where it elsewhere says the predecessor, and "dark" where it elsewhere says an agent-seat is left down.
- Several words for one thing, and one word for several: "in flight", "running", "holds" and "show work" all for what the threshold-hook counts as holding a session-handoff; "notice" for a subagent's last task-notification, for the passage telling the successor its handoff-supervisor did not restart on main's code, and for the failed-restart-notice; "restart", "queues", "dialog", "reader", "wait", "fired" and "handed off" likewise.
- Things named but never introduced: "the handoff-deferred marker file", "the file of refused commands" and "the refusal hook"; "the complete dialog" and "the log-store's session dialogs"; "the not-restarted notice"; "stopped on purpose", which decides whether the agent-crash-watcher writes tasks; "fleet-restart-at-login" at its first use; and "the queues".
- Words whose ordinary computing meaning misleads: "holes" (a security hole) for known limitations, "ledger" (append-only) for a record that is rewritten, "pin" (a version) for a reference, "canary" (a release) for a test, "generations" for successive agent-sessions.

The terminology reviewers proposed five new terms for the user to rule on: handoff-deferral-ceiling, agent-session-complete-dialog, agent-seat-stopped-on-purpose, log-store-agent-session-filtered-transcript, and handoff-background-task-command-pattern-wait-limit-rule.

The findings come from the cold-read-full-run `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/handoff.system.design-2026-11-20-6`, whose reports `claude-terminology-deep.md` and `codex-terminology-deep.md` give each term's uses and a proposed fix; its `cold-read-triage.md`, in that directory beside the reports named here, gives each of these findings the link of the GHI filed from this file: `claude-terminology-deep.md` 1 to 13, 15 to 35, and 37 to 39; `codex-terminology-deep.md` 1 to 13, 15 and 16; `claude-hunt-deep.md` 4, 5, 34 and 40; `claude-hunt-second-strongest-model.md` 4, 5, 26, 29, 43, 47 and 48.

## Why it matters

CLAUDE.md tells every agent to use a glossary's term as the glossary spells it, and a search for the glossary's spelling finds one line of this design where it should find fifteen. Where one word names two things, or a name is never introduced, a reader acting on the design, such as a successor told to look in "the log-store's session dialogs", cannot find what it is sent to.

## Next action

The agent-seat agent-instructions-editor brings the user the five proposed terms, and any other new term the fixes need, in one approval-walk, as steps 1 and 8 of the /cold-read skill say for a new term. Each term he accepts is added to the glossary he names as its own change, before the design uses it, as step 1 says; a term he rejects is written in the plain words or SDLC-term he directs. Then, in one pull request on the design, it applies the glossary spellings, says in a sentence where each thing above is first named what it is and where it lives, and uses the accepted terms once their glossary change is on main. A test that fails when a design writes a hyphenated glossary term with spaces instead of hyphens, such as "threshold hook", would keep the spellings from drifting back; the agent-seat proposes it to the user with the terms. The design's change gets the cold-read-full-run the /cold-read skill gives a design.
