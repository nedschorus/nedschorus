---
issue: "[Active knowledge-injection supervisor: watch the fleet's dialogs, push pointers at need (placeholder, design deferred)](https://github.com/nedschorus/nedschorus/issues/144)"
---

# Active knowledge-injection supervisor: watch the fleet's dialogs, push pointers at need (placeholder, design deferred)

## What this is

A placeholder for a design not yet begun (user-directed 2026-08-23): an
active knowledge-injection supervisor — a process that watches the fleet's
agent conversations and pushes a pointer to relevant recorded knowledge to
a running agent at the moment it needs it, instead of waiting for the
agent to look.

## Why

The project's knowledge-retrieval ladder is passive: forced instruction
files for always-needed rules, per-system READMEs reached through skill
triggers, and the ghi-info agent for issue knowledge. All three require
the needing agent to look. The failure mode on record: knowledge that was
written down but not found at need (the merge seat's memory notes record
this as memory's standing failure — the read path fails, not the store).

## The shape sketched, undesigned

- The fleet already runs the monitor half: `scripts/watch-agent-dialogs.py`
  streams a filtered subset of every seat's conversation.
- The missing half: a cheap-fast classifier over that stream that triggers
  on shapes like "agent approaching X without knowing Y" and sends the
  agent a POINTER to the knowledge's home via cross-session message.
- Constraints already ruled by the user during the 2026-08-23 review-process
  walk, recorded so the eventual designer inherits them:
  - Pointers, never retellings — an intermediary that restates knowledge
    re-creates the qualifier-stripping amplifier measured in the review
    study (merge-lane seat, phase-1-timeline-118-supervisor analysis).
  - Injections rare and load-bearing — the same discipline as the fleet's
    voice-line rule; a noisy injector is ignored, then harmful.
  - The injector reads the same knowledge homes agents do (READMEs, seat
    rules); it is a retrieval layer, never a second store.

## Next action

None until the user opens the design. This issue exists so the idea and
its ruled constraints survive with a number; when the user says design it,
the designer starts from this body plus the constraints' source
(machine-local study workspace at the merge seat; durable homes land via
that walk's item 15/16 closures).
