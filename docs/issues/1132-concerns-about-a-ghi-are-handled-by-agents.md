---
issue: "[Proposed improvements or changes to a GHI are handled by agents first, and reach the user only when they need him](https://github.com/nedschorus/nedschorus/issues/1132)"
---

# Proposed improvements or changes to a GHI are handled by agents first, and reach the user only when they need him

## Problem

A reviewer of a GHI, or of the code a GHI describes, can find two kinds of thing: an improvement, such as something to remove, archive, simplify or add, and a possible problem. Reviews have tended to look only for problems and their fixes, although simplifying and removing what is obsolete do more for the project's health over time.

The first reviewer that records anything is ghi-info. Before an agent files or edits a GHI, the ghi-write-tool (`scripts/ghi-issue-write.py`) asks ghi-info whether an open GHI already covers the draft. ghi-info may answer instead that the draft may conflict with a user-ruling, because whether a user-ruling still applies is never ghi-info's to judge (GHI [Build ghi-info — the GHI knowledge agent](https://github.com/nedschorus/nedschorus/issues/46)).

Today, on main, the ghi-write-tool records that question as a comment on the GHI and adds the label `conflicts-with-a-ruling`, then lets the write go ahead (merged in PR [A ruling question from ghi-info no longer holds up the GHI write: the tool writes the issue and records the question on it](https://github.com/nedschorus/nedschorus/pull/983)). Nothing then reads the comment or acts on it, and every such question waits for the user, although most can be settled without him.

design-to-main settles findings like these inside a run (§ Reuse below), but it has no place for one raised outside a run, such as ghi-info's about a GHI that no run owns, or an overview writer's about the code it describes.

The user's direction, 2026-10-09: agents handle every proposed improvement or change they can, with at most 3 tries so that they never loop, and the user sees only what needs him. The full discussion is in the minutes `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/concerns-files-design-explained-step-by-step-2026-10-09-minutes.md`.

## Example

An agent edits an invented closed GHI whose GHI-MD is `docs/issues/<n>-reopen-old-design-notes.md`. The user once ruled "closed GHIs are frozen", a user-ruling recorded in another GHI; both GHIs are invented for this example. ghi-info asks: "Does the ruling that closed issues are frozen still allow this edit?" The edit only fixes a broken link.

## The design

1. **Recording.** A reviewer writes one proposed-improvements-or-changes-file per review, beside the document it reviewed, or, for ghi-info, in the log-store (below), named `<document name>-proposed-improvements-or-changes-<source>-<date>.md`. The file lists everything that review found worth changing. Each entry is an improvement, saying what it would gain (simpler, smaller, an obsolete thing removed, a better way, a helpful addition), or a possible problem, saying what goes wrong and when. A second file from the same source on the same day gets `-2`, then `-3`, at the end of its name. Each entry has an ID, `E1`, `E2` and so on in its file, and its own state, written as one line under it: open, needs the user, or settled, with who settled it, how and when. The handler changes only those state lines and the try lines of rule 4; it never rewrites an entry's text or another entry's lines. For example:

   ```
   ## E1 — possible problem: the edit may break the user-ruling "closed GHIs are frozen"
   Goes wrong when: a closed GHI's decision changes without the user.
   State: settled, not worth doing — reboot-test handler, 2026-10-09T22:30Z: the edit only fixes a broken link; second agent agreed.
   Try 1 — reboot-test handler, 2026-10-09T22:20Z: read the user-ruling and the diff; the ruling covers decisions, not links.
   ```
   - About a GHI-MD: ghi-info, through the ghi-write-tool, is the reviewer that writes them. Its files never reach main: the ghi-write-tool writes each to the log-store directory `nedlern@ned-box:/home/nedlern/nedschorus-logs/ghi-info-proposed-improvements-or-changes/`, and the GHI-MD carries no line pointing to them. The handler settles each entry in that file, without a pull request; where rules 5 and 6 say a pull request marks an entry settled, the handler marks it in the file. Only the change an entry calls for reaches main, such as an edit of the GHI-MD through edit-GHI or a new GHI. A settled file stays in the log-store as a record of what ghi-info asked.
   - Beside an architecture overview: the overview's writer records what it notices in the code, adds one line under the overview's first heading pointing to these files, "This document has proposed improvements or changes: read every file in this folder whose name starts with `<overview name>-proposed-improvements-or-changes-`.", and starts the handler (rule 2). The file and that line reach main in the same pull request.
2. **Who picks them up.** The writer that recorded the file, meaning the agent that ran the ghi-write-tool or the agent that wrote the overview, the nightly refresh included, dispatches a forked subagent at once, here called the handler, as CLAUDE.md already has an agent do for review findings. The handler settles what it can, and marks each entry that needs the user as needing the user. The agent-seat that owns the document brings those entries to the user in its next approval-walk. Once a program exists that starts one handler per document (What must be built, item 4), the program takes this over.
3. **Several entries.** The handler reads every proposed-improvements-or-changes-file of the document before it acts. Dependent entries: it handles the one furthest upstream first, then checks the others again, since a change upstream may settle them. Related entries, sharing one cause: one change, counted as one try for all of them. Independent entries: each on its own.
4. **Tries.** At most 3 for an entry or a group of related entries. Each try is recorded as one line under the entry it worked on, in the same file, saying what was tried, what was found, by whom and when; the tries spent on an entry are its try lines, with no other state. A try on a group of related entries is recorded under each of them. After the user has ruled on an entry, a line under it records his ruling, and its count starts again from that line.
5. **Not worth doing.** An entry is not worth doing when the problem is not real, or the improvement does not pay for itself. The handler must show this from the sources: in the example, the user-ruling's text and the edit's diff, showing the ruling governs changing a closed GHI's decision, not fixing its links. A second, independent agent must agree. Then one pull request marks the entry settled as not worth doing. Without agreement the entry stays open.
6. **Worth doing.** The handler makes the change now: a removal, an archiving, a simplification, an addition, or bringing the edit into line with the ruling. Removing or archiving is a change in its own right, not the side effect of a fix. The same pull request marks the entry settled. If the change is new work, it files a new GHI, and marks the entry settled with that GHI's link. If the entry is worth doing but cannot be done now, the entry stays open; it is the reminder, and no separate task is needed.
7. **What reaches the user.** Only these, and nothing else:
   - a change that would alter a document the cold-read skill sends to a cold-read-full-run, in a way its step 9 sends to the user;
   - a question whether a user-ruling should change;
   - an entry still open after 3 tries.

   An entry of the first kind, whose change would alter a design, may go to him at once, without spending a try, as in design-to-main. Whatever reaches him comes as one report about the document, a file he reads in an approval-walk and not a GitHub comment, cold-read first, carrying the user-rulings already made on it so he is never asked twice, and taken one item at a time with the /walk-me-through skill. Until the program of What must be built, item 4, exists, the agent-seat that owns the document brings it to him in its next approval-walk.

A file beside an overview is deleted in the ordinary pull request that settles its last open entry. The pointer line is removed only in the pull request that deletes the overview's last proposed-improvements-or-changes-file. While any such file remains, the line stays.

### The cold-read skill's wording that rule 7 uses

From `.claude/skills/cold-read/SKILL.md` on main, step 2, the documents that need a cold-read-full-run:

> "Wiki files, skills and their prompts, the files under `docs/agents/`, designs, including a GHI-MD that is a design, test designs, and design-contracts need a cold-read-full-run, and so does a change to one of them, with one exception: a change of at most one sentence, or a mechanical one applied by search and replace, such as a rename or a path, gets the cold-read-fast-read instead."

Step 9, which changes to them go to the user:

> "every change you applied that adds, alters or removes what a program or an agent does, must do or may do, or what the document decides or plans, and every finding you declined that would have made such a change. A correction of past events, of a citation or a reference, or of spelling or punctuation that leaves a sentence's meaning unchanged, does not go to the user. When you cannot tell, it goes to the user."

In the example, the fix for the broken link changes no such document in such a way, and no user-ruling needs to change, so the entry never reaches the user.

## Reuse of design-to-main

The design takes these rules from `docs/design-to-main/design-to-main-state-machine-design.md` on main:

- §1: code routes and agents judge; "The state machine is code and holds no judgement." Rule 2's forked subagent is a stopgap until a program routes these files.
- §6.1: a reviewer's notes file, each material entry "a finding with a failure scenario"; the reviewer names the artifact at fault that is furthest upstream, "since whatever is downstream of it is rewritten from the corrected version anyway" (rules 1 and 3).
- §6.1 and §6.5: a reviewer and the arbitrator prove before they rule, and the arbitrator, ruling `advance` on a reviewer's reject, closes it as unfounded (rule 5, not worth doing).
- §6.6: the user is reached through one cold-read report, carrying prior user-rulings, delivered one item at a time, and only when he is needed (rule 7).
- §7: implementation-writes and test-writes have a ceiling of three, and "A resume from an investigation zeroes the six per-version counters", so every agent gets its chance again after the user steps in (rule 4).

**One difference:** design-to-main's ceilings vary by what is being revised, from one try for a contract-revision to three for a write. Here every entry gets 3, because an entry is smaller than a design-to-main artifact.

## What must be built

1. **The ghi-write-tool records proposed-improvements-or-changes-files, not a comment and a label.** This replaces what PR [A ruling question from ghi-info no longer holds up the GHI write: the tool writes the issue and records the question on it](https://github.com/nedschorus/nedschorus/pull/983) merged, in one new pull request cut from main. The file's text and the tool's success message tell the agent to dispatch the handler. Tracked on the reboot-test agent-seat's task list as task #128, "Replace main's comment-and-label ruling-question recording with proposed-improvements-or-changes-files (new PR from main)". Everything below depends on it.
2. **The handler's instructions:** rules 3 to 7, in one file under `docs/agents/`.
3. **The check by a second agent that an entry is not worth doing** (rule 5): the instructions for the agreeing agent, and how its agreement is recorded so the deleting pull request can cite it.
4. **Later, a per-GHI launcher:** when the rebuild of GHI [An issue has one GHI-MD and many supporting documents, and the GHI write tool cannot tell them apart](https://github.com/nedschorus/nedschorus/issues/783) finds proposed-improvements-or-changes-files on main, a program starts a handler for that document, and for an entry that reaches the user opens a window on the Mac through the helper of PR [ned-box opens a window on the Mac through one forced command](https://github.com/nedschorus/nedschorus/pull/982).

## Decided by the user

- Entries are settled one at a time: "entries should be flagable item by item - that seems obvious." The user, 2026-10-09T21:57Z, in the cold-read-improvement agent-seat's agent-session on ned-box, relayed by cold-read-improvement-31; rules 1, 4, 5 and 6 follow from it.
- Where ghi-info's files go: the log-store on ned-box, not beside the GHI-MD on main, settled there with no pull request, with only the change an entry calls for reaching main. The user, 2026-10-19T23:18:46Z, in the reboot-test agent-session on ned-box (transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts/ned-box/projects/-home-nedlern-agents-reboot-test/a57e7234-a0b4-4b5c-9bcb-22b1cc32c76a.jsonl`), answering that proposal: "I don't see any reason to keep the doubts on main, and you didn't. So if that's correct, then yeah, don't put them where you think they should be put." Rule 1's GHI-MD bullet and the paragraph after rule 7 follow from it; ned-box-helper's task #102 builds it.
- Who starts the handler: the writer, at once; the handler settles what it can and marks entries that need the user; the owning agent-seat brings those to him in its next approval-walk; a program takes over when one exists. The user answered "1 y" to that recommendation, 2026-10-09T22:08Z, same agent-session, relayed by cold-read-improvement-31; rules 2 and 7.

## Open questions

1. For an overview's file, the handler may start before the file has reached main, while the pull request that carries it is still open: whether it waits for the merge, or works on the pull request's branch. ghi-info's files are in the log-store, so their handler starts at once.
2. The second agent of rule 5: who starts it, what it is given, where its agreement is recorded, and whether a disagreement counts as a try.
3. Other kinds of document, such as designs, skills and wiki pages: whether they get these files, and where "architecture overview" is defined.
4. What happens to an entry that reaches the user and he does not rule on it.
5. Whether "handler" becomes a project-term.
6. Which agent-seat "owns" a document, for rule 2 and rule 7, when no agent-seat is plainly responsible for it, such as a closed GHI-MD.
7. What brings an entry that stays open, worth doing but not doable now, back to an agent's attention later.
8. Two handlers settling different entries of the same file at the same time, in two pull requests that both change the file.

## Next action

Build item 1 first, then items 2 and 3 together; item 4 waits for the rebuild it names.

## Provisional additions (not yet vetted by the user)

- ned-box-helper, 2026-10-14: the build of this GHI is on the pushed branch `ghi-write-tool-ghi-info-ruling-question-recorded-in-proposed-improvements-or-changes-file-not-ghi-comment-topic-branch`, with no pull request yet; its texts are in an approval-walk of ned-box-helper (glossary-naming-rule-reader-categories-and-open-questions-2026-10-13, items 25 to 26.3).
- ned-box-helper, 2026-10-14: the problem this GHI fixes, a ruling-conflict question that `scripts/ghi-issue-write.py` posts as a GHI comment the user never reads, still happens on main until that build merges.
- ned-box-helper, 2026-10-14: notes on the wording of that ruling-question message, from the fast read of PR [A ruling question from ghi-info no longer holds up the GHI write: the tool writes the issue and records the question on it](https://github.com/nedschorus/nedschorus/pull/983), go into the same build.
- reboot-test, 2026-10-14: three points for design-to-main's owner, which this GHI's handling could serve: findings that arise before a design-to-main run starts, handed to whoever starts the run; showing all of one component's findings together instead of one investigation per escalation; and design-to-main has no place to pick up a doubt raised outside a run, which this GHI's handling fills and design-to-main could adopt.
