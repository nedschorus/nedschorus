---
issue: "[Concerns about a GHI are handled by agents first, and reach the user only when they need him](https://github.com/nedschorus/nedschorus/issues/1132)"
---

# Concerns about a GHI are handled by agents first, and reach the user only when they need him

## Problem

An agent sometimes finds a problem with a GHI that is not its own work to fix. The first case is ghi-info's ruling question. Before an agent files or edits a GHI, the ghi-write-tool (`scripts/ghi-issue-write.py`) asks ghi-info whether an open GHI already covers the draft. ghi-info may answer instead that the draft may conflict with a user-ruling, because whether a user-ruling still applies is never ghi-info's to judge (GHI [Build ghi-info — the GHI knowledge agent](https://github.com/nedschorus/nedschorus/issues/46)).

Today, on main, the ghi-write-tool records that question as a comment on the GHI and adds the label `conflicts-with-a-ruling`, then lets the write go ahead (merged in PR [A ruling question from ghi-info no longer holds up the GHI write: the tool writes the issue and records the question on it](https://github.com/nedschorus/nedschorus/pull/983)). Nothing then reads the comment or acts on it, and every such question waits for the user, although most can be settled without him.

design-to-main settles doubts like this inside a run (§ Reuse below), but it has no place for a doubt raised outside a run, such as ghi-info's about a GHI that no run owns.

The user's direction, 2026-10-09: agents handle every concern they can, with at most 3 tries so that they never loop, and the user sees only what needs him. The full discussion is in the minutes `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/concerns-files-design-explained-step-by-step-2026-10-09-minutes.md`.

## Example

An agent edits an invented closed GHI whose GHI-MD is `docs/issues/<n>-reopen-old-design-notes.md`. The user once ruled "closed GHIs are frozen", a user-ruling recorded in another GHI; both GHIs are invented for this example. ghi-info asks: "Does the ruling that closed issues are frozen still allow this edit?" The edit only fixes a broken link.

## The design

1. **Raising a concern.** A reviewer writes one concerns-file per review, beside the GHI-MD, named `<GHI-MD name>-concerns-<source>-<date>.md`. The file lists everything that review found; each entry gives a failure scenario: what goes wrong, and when. A second concerns-file from the same source on the same day gets `-2`, then `-3`, at the end of its name. A concerns-file is never edited once written. The GHI-MD carries one line under its first heading pointing to its concerns-files. The concerns-file and that line reach main in the same pull request as the write that raised the concern. ghi-info, through the ghi-write-tool, is the first reviewer that writes them.
2. **Who picks it up.** The agent that ran the ghi-write-tool, when the tool's output says a concern was recorded, dispatches a forked subagent at once, here called the concerns handler, as CLAUDE.md already has an agent do for review findings. Later, a program starts one concerns handler per GHI instead (What must be built, item 4).
3. **Several concerns.** The concerns handler reads every concerns-file of the GHI before it acts. Dependent concerns: it fixes the one furthest upstream first, then checks the others again, since a fix upstream may settle them. Related concerns, sharing one cause: one fix, counted as one try for all of them. Independent concerns: each on its own.
4. **Tries.** At most 3 for a concern or a group of related concerns. Each try is recorded as a new concerns-file whose source is the concerns handler, naming the concerns it worked on and saying what it tried and what it found; the tries spent on a concern are the concerns handler's files that name it, with no other state. After the user has ruled on a concern, its count starts again.
5. **A false alarm.** The concerns handler must show why the concern does not hold, from the sources: in the example, the user-ruling's text and the edit's diff, showing the ruling governs changing a closed GHI's decision, not fixing its links. A second, independent agent must agree. Then one pull request, through edit-GHI, deletes the concerns-files the two agreed on. Without agreement the concern stays.
6. **A real concern.** If the edit can be brought into line with the ruling, the concerns handler fixes it now, and the same pull request deletes the concerns-files it settled. If the remedy is new work, it files a new GHI, then deletes the concerns-file in a separate edit-GHI pull request on the original GHI. Otherwise the concerns-file stays; it is the reminder, and no separate task is needed.
7. **What reaches the user.** Only these, and nothing else:
   - a fix that would change a document the cold-read skill sends to a cold-read-full-run, in a way its step 9 sends to the user;
   - a question whether a user-ruling should change;
   - a concern still open after 3 tries.

   A concern of the first kind, whose fix would change a design, may reach him before its tries are spent, as in design-to-main. Whatever reaches him comes as one report about the GHI, a file he reads in an approval-walk and not a GitHub comment, cold-read first, carrying the user-rulings already made on it so he is never asked twice, and taken one item at a time with the /walk-me-through skill.

The pointer line in the GHI-MD is removed only in the pull request that deletes the GHI's last concerns-file. While any concerns-file remains, the line stays.

### The cold-read skill's wording that rule 7 uses

From `.claude/skills/cold-read/SKILL.md` on main, step 2, the documents that need a cold-read-full-run:

> "Wiki files, skills and their prompts, the files under `docs/agents/`, designs, including a GHI-MD that is a design, test designs, and design-contracts need a cold-read-full-run, and so does a change to one of them, with one exception: a change of at most one sentence, or a mechanical one applied by search and replace, such as a rename or a path, gets the cold-read-fast-read instead."

Step 9, which changes to them go to the user:

> "every change you applied that adds, alters or removes what a program or an agent does, must do or may do, or what the document decides or plans, and every finding you declined that would have made such a change. A correction of past events, of a citation or a reference, or of spelling or punctuation that leaves a sentence's meaning unchanged, does not go to the user. When you cannot tell, it goes to the user."

In the example, the fix for the broken link changes no such document in such a way, and no user-ruling needs to change, so the concern never reaches the user.

## Reuse of design-to-main

The design takes these rules from `docs/design-to-main/design-to-main-state-machine-design.md` on main:

- §1: code routes and agents judge; "The state machine is code and holds no judgement." Rule 2's forked subagent is a stopgap until a program routes concerns.
- §6.1: a reviewer's notes file, each material entry "a finding with a failure scenario"; the reviewer names the artifact at fault that is furthest upstream, "since whatever is downstream of it is rewritten from the corrected version anyway" (rules 1 and 3).
- §6.1 and §6.5: a reviewer and the arbitrator prove before they rule, and the arbitrator, ruling `advance` on a reviewer's reject, closes it as unfounded (rule 5).
- §6.6: the user is reached through one cold-read report, carrying prior user-rulings, delivered one item at a time, and only when he is needed (rule 7).
- §7: implementation-writes and test-writes have a ceiling of three, and "A resume from an investigation zeroes the six per-version counters", so every agent gets its chance again after the user steps in (rule 4).

**One difference:** design-to-main's ceilings vary by what is being revised, from one try for a contract-revision to three for a write. Here every concern gets 3, because a concern is smaller than a design-to-main artifact.

## What must be built

1. **The ghi-write-tool records concerns-files, not a comment and a label.** This replaces what PR [A ruling question from ghi-info no longer holds up the GHI write: the tool writes the issue and records the question on it](https://github.com/nedschorus/nedschorus/pull/983) merged, in one new pull request cut from main. The concerns-file's text and the tool's success message tell the agent to dispatch the concerns handler. Tracked on the reboot-test agent-seat's task list as task #128, "Replace main's comment-and-label ruling-question recording with concerns-files (new PR from main)". Everything below depends on it.
2. **The concerns handler's instructions:** rules 3 to 7, in one file under `docs/agents/`.
3. **The check by a second agent for a false alarm** (rule 5): the instructions for the agreeing agent, and how its agreement is recorded so the deleting pull request can cite it.
4. **Later, a per-GHI launcher:** when the rebuild of GHI [An issue has one GHI-MD and many supporting documents, and the GHI write tool cannot tell them apart](https://github.com/nedschorus/nedschorus/issues/783) finds concerns-files on main, a program starts a concerns handler for that GHI, and for a concern that reaches the user opens a window on the Mac through the helper of PR [ned-box opens a window on the Mac through one forced command](https://github.com/nedschorus/nedschorus/pull/982).

## Next action

Build item 1 first, then items 2 and 3 together; item 4 waits for the rebuild it names.
