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

## Outcome

Closed as not planned on 2026-09-30, by the user's "y" to item 6 of the walk eight-deferrals-with-no-trigger-2026-09-29, as revised during the walk (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/eight-deferrals-with-no-trigger-2026-09-29-minutes.md`).

Before ruling, the user asked: "We are using skills to 'push' stuff when needed to agents. are you sure there is no class of 'stuff' that skills or other existing claude systems don't handle well that we could use?" An independent reviewer answered from the project record, and the quotes below were checked against the walk minutes they cite.

**One class exists that nothing pushes today: a situational ruling the user gave in another seat's conversation, written in no file when a different seat needs the ruling.** Skills fire when the agent recognises its own need, hooks fire on a file path or a git event, and the handoff-supervisor's first-prompt lines report what a program can compute from main. A ruling that lives only in another seat's conversation reaches none of the three. Four cases, 2026-09-17 to 2026-09-22:

- A ruling lived only in another seat's handoff and was saved by "a peer volunteering the ruling unprompted, which is not a mechanism" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-write-session-open-rulings-and-concerns-minutes.md`, line 92).
- One seat landed the term `link-type` while the user ruled `ID-type` in a different seat the same evening; "Neither seat could see the other's ruling" (the same minutes, line 96).
- A walk paused on "a conflict with what the user told another seat" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/claude-md-file-citation-and-drift-findings-2026-09-22-minutes.md`, line 61).
- The user said "You might have to check ghis or jsonls", and the seat running that walk found the ruling in the MD-skills seat's conversation of 2026-09-17 (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/design-phasing-issue-draft-cold-read-review-2026-09-18-minutes.md`, line 13).

**Why a watcher still fits that class poorly.**

- On 2026-09-23 the user withdrew a rulings index with these words: "There is no way to ensure that agents know everything. ... Things agents call my rules are usually situational, not a universal truth." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/rulings-agents-cannot-find-from-problem-to-build-plan-minutes.md`, line 18). A watcher that pushes pointers would have to decide which of the user's rulings bears on what an agent is doing now, which is the problem the user named. That walk did not have this issue in front of the user; this issue is the push form of the index he withdrew.
- A cross-session message reaches an agent on the agent's next turn, after the action the pointer was meant to guide.
- In the 2026-09-18 case, what worked was a search at the moment of need: the seat searched another seat's conversation when the user asked. The Mac's transcripts are mirrored into the log-store under `nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts/mac/`, and ned-box's transcripts are in `~/.claude/projects/` on ned-box, so a seat can search both.

**Duplicate builds across seats are a different gap, and git already holds the evidence.** In the cases the reviewer found, the other seat's work was already on main or in a pull request when the second seat started. For example, PR [Show every seat's task list, from both machines](https://github.com/nedschorus/nedschorus/pull/634) was closed as a second task viewer because `scripts/seat-task-list-read.py` was already on main under a different name; only a search of main before work starts finds that case. The other case, an open pull request that already touches the files a seat will change, is section 1, "File-overlap check before a seat starts work", of GHI [Three mechanical checks agents keep forgetting to run: file-overlap before work starts, exit status through a pipe, and the settled-decision list](https://github.com/nedschorus/nedschorus/issues/216).

**Reopen** when a ruling given in another seat's conversation is missed, and searching the other seats' conversations would not have caught the miss.
