---
name: walk-me-through
description: Present material the user must rule on to him one item at a time, when it would otherwise reach him as one message of more than 300 words or with more than four separate decisions.
---

# Walk me through

Deliver complex material as a sequence of items, one item per message, except that items with little at stake may share a message, as Each item says. Write like one senior engineer explaining to another out loud. Write each item so that it stands on its own: a reader new to this project, who remembers nothing of earlier conversations, can follow it. When the approval-walk covers a design, plan or Markdown file the user has already reviewed, present what it does, not the history of his review.

Each approval-walk has four Markdown files in `docs/walk/`, named from the approval-walk's name, `<name>`: `<name>-draft.md`, the approval-walk as first written; `<name>-suggestions.md`, the cold-read-fast-read's report on the draft; `<name>.md`, the walk-document; and `<name>-minutes.md`, the walk-minutes. An older cold-read approval-walk may also have `<name>-dispositions.md`, which ships with the other four. Name the approval-walk by the project naming rule in CLAUDE.md, leaving out its search of main and pull requests, which walk files never reach; an approval-walk on a cold-read-record takes that cold-read-record's name. Before you use a name, check that neither `docs/walk/<name>.md` nor `docs/walk/<name>-minutes.md` exists; if one does, resume that approval-walk or choose another name. An approval-walk on a cold-read-record also writes each ruling at the end of that cold-read-record's `triage.md`, as step 9 of `.claude/skills/cold-read/SKILL.md` says, as well as in the walk-minutes.

## What goes into the walk-document

The message that presents item 1 opens with one sentence of under 30 words that names its subject as if the user had never heard of it, then gives the number of items, M, and a link to the walk-document. That opening is not an item. Follow the material's own order. When explaining a defect, a mechanism or a proposed change, use a realistic concrete example, not an abstraction. Each item carries at most one decision; the last item summarizes the decisions, tasks and other outcomes; the draft holds a placeholder for it, which you replace in the walk-document when the approval-walk reaches it.

Before presenting the first item: read the project glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`, and the system glossary of any system the approval-walk covers. Write the whole approval-walk into `docs/walk/<name>-draft.md`, as it would be presented, using every project-term and system-term as its glossary spells it. Then send the user one message listing each key-term the draft uses that no glossary lists, with a one-sentence definition each, as proposed terms; do not wait for his answer, and until he approves a term, write it as plain unhyphenated prose. Then run `nc-systems/cold-read/cold-read-fast-read.py --target docs/walk/<name>-draft.md`; it writes its report to `docs/walk/<name>-suggestions.md`. If it prints a line opening `FAILED`, tell the user what it printed, copy the draft to the walk-document, `docs/walk/<name>.md`, and present that. Otherwise read the report and write the walk-document, `docs/walk/<name>.md`, before presenting item 1. Fix what the report shows a reader would misread by simplifying phrases, sentences or paragraphs, aiming for roughly the same number of words; fix an over-specifying claim by deleting the excess words, not by adding qualifiers. Add words only where an item leaves out something the user needs in order to rule.

Write each ruling into the walk-minutes as soon as the user gives it, so that an interrupted approval-walk can resume.

## Each item

Start each item with the running count, "Item N of M: <the point>". Present a step, decision, concept, pull request, GHI, file or other element, using real or relevant examples.

An item that asks for a decision ends with your recommendation, written as "Recommendation: Y" or "Recommendation: N" followed by what that answer does. Phrase the item so that Y makes the change it describes and N leaves things as they are; in an approval-walk on a cold-read-record, Y keeps a change already committed and N undoes it, and for a finding you declined, Y applies it and N leaves it declined. D defers the item. An item that only explains, or that asks the user to choose among more than two options, says so, ends with "Recommendation: <the option>", and asks for his choice. Items that each carry a recommendation and little at stake, such as a correction or a change whose substance the user has already approved, may be shown together in one message of at most 300 words, each keeping its own number and recommendation, and the user answers each one, as in "5 n, 6 y"; an item he does not answer, or answers with a question, stays undecided and is shown again on its own after the other items in that message. Defer means to move the item, keeping its number, to just before the summary item. An item deferred a second time, or deferred when it is the last item before the summary, is recorded as undecided in the walk-minutes, added to your task list if it is not already a task, and dropped from the approval-walk.

Limit each message to 300 words. An item that needs more is split into parts, one message each, sharing the item's number ("Item 4.1 of 9"); the recommendation comes in the last part, and a reply to an earlier part that is not a question moves on to the next.

Style: direct, concrete, short sentences. Use standard SDLC terminology, not jargon agents make up or unusual word pairings. State what a component does, with a good example, before stating what is wrong with it or how you want to change it. If the user says he does not understand an item or is confused, rewrite the item as a story built around one concrete example of a failure, success, improvement, concern or problem, and put the rewritten text in the walk-document. If you disagree with the user, do not hide your disagreement, state it clearly. Just before each Y or N recommendation, state in one sentence the strongest case for the other letter; items shown together because little is at stake leave this sentence out.

References: cite every issue, pull request, commit or file the user may want to open as a clickable link with link text that names what it is, never a bare number or bare file name: a URL, or a `file://` path that opens on the user's Mac. For a file on ned-box that is `file:///Volumes/nedhome/` followed by the path after `/home/nedlern/`. A script named as a command to run stays plain text; link it when the item is about what the script contains.

If you quote a phrase, quote the whole sentence. If you propose a change to a sentence, write out the old and new sentences. If you propose a rewrite of a section, where sentences are added, removed or reordered, show the section whole, original and proposal, split across parts if it needs more than 300 words. If you propose new text, write out the exact words, not a description of them.

## Advancing

Only the user advances the approval-walk. A reply that approves, declines or defers the current item advances it, even when it rides alongside a question or a new point: answer the question or point, then advance. A navigation word alone, such as next, continue or go, advances only an item with no recommendation; when one is outstanding, ask for his answer instead. Every other reply stays on the current item:

- An automated event, such as a finished background task or an injected or unrelated notice: handle it, return, and restate in 10 words or less the current item and its position, for example "How to write a poem, item 3 of 6".
- A reply you cannot read with confidence: restate your question and his answer, give your guess at what he meant, and ask him to confirm. For example: "I asked what your favorite color is; when you said dark, did you mean black?"
- A message nearly the same as one he sent just before is usually an amendment typed while your reply was being written: treat the difference between his two messages as his amendment, and answer that difference. If there is no difference, it is not a new approval and does not advance the approval-walk.

## Capturing the approval-walk

When the user rules on an item, record in the walk-minutes the item's number, its outcome, and its classification: accepted, rejected, revised (accepted with a change he gave), deferred, or undecided. Record any decision or commitment it produced. If the approval-walk reviews another document, update that document as changes are agreed.

A commitment you make that is not carried out at once, by you, a subagent or another agent, goes on your task list, the one the TaskCreate tool writes to, or, when it belongs to a GHI, into that GHI's GHI-MD. A conclusion the discussion itself produces, such as a side ruling, a direction the user sets or a question the exchange settles, is recorded in the walk-minutes with its outcome. A question the discussion raises and does not answer is recorded in the walk-minutes as undecided and added to your task list, as "Open Walk <name> Question: <the text of the question>", before the approval-walk advances; when it is answered or no longer matters, remove the task.

Write the walk-minutes so that someone who has not read the walk-document can understand them.

## Re-planning

A ruling that invalidates or changes later items re-plans the approval-walk before it advances: revise, remove or reorder the remaining items in the walk-document, give M its new value from the next item on, and tell the user the count or order changed.

## Interruption and recovery

An interruption is a loss of place: a new agent-session, a compacted context, or a crash. The approval-walk resumes at the first item whose outcome the walk-minutes do not record. On resuming, restate the last item the user ruled on in under 20 words, if there is one, then restate the item being resumed word for word from the walk-document. If the walk-document or the walk-minutes is missing, tell the user which, and ask him where to resume.

## Closing

After the summary item, check that its outcome is in the walk-minutes. Then check the whole approval-walk for loose ends: every commitment you made, every question left unanswered, every item deferred or undecided, and every decision whose work is not done and not already a task. Each becomes a task, or a question asked once in the closing message; a question he leaves unanswered becomes a task.

Then run `scripts/walk-files-ship.py <name>`. Its last line of output ends with where the walk-minutes now are in the log-store, in the form `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/<name>-minutes.md`. If a line opens `FAILED` or `REFUSED`, show it to the user as it is; the approval-walk is still complete, its files stay in `docs/walk/`, and a later run ships them. If a closed approval-walk is reopened, run the shipper again when it closes.

End with one sentence saying the approval-walk is complete and where its walk-minutes are: in the log-store, or in `docs/walk/` if shipping failed. Do not recap after it: the summary item already did. In the same message, start the next piece of queued work without asking, such as the next approval-walk, task or question on your task list. Ask first only for a decision that is the user's to make, or before an action that is hard to undo or reaches outside the project.
