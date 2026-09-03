---
name: walk-me-through
description: Present long or complex material to the user one item at a time, if the display message will be >300 words or combines >4 independent items.
---

# Walk me through

Deliver complex material as a sequence of items, each step covering a single component, decision, section, or a step of a longer explanation, per turn. Write like one senior engineer explaining to another out loud. Assume the reader is new to this project, that they are not familiar with this repo, that this is the first conversation you have had with them about this project, so the walk should be understandable as a stand-alone document.  

Each walk has 4 MD files in docs/walk/, a draft document - the proposed text of the walk, a suggestions document - the suggestions to clarify the walk, a walk document -  the text to be presented to the user during the walk, and a minutes document - the recording of the interactions or minutes of the walk. Name the walk <name> by the project naming rule in CLAUDE.md; it names four files, so glob `docs/walk/<name>*` before using it.

## What goes into the walk text

The walk's opening sentence states its subject as if newly introduced - the point, subject, object and or goal of the walk in under 30 words, then the count of items in the walk, then a clickable link of the name of the walk file - so the user can click open that document. Follow the material's innate steps, sequence, order or timeline. When explaining complex topics, defects, mechanisms, or proposed changes, use a realistic concrete example, not an abstraction. The opening precedes item 1 and is not counted in M; the items carry the explanation and at most one decision each for the user's approval; the final item summarizes the decisions, tasks or other outcomes. 

Place the initial draft document at docs/walk/<name>-draft.md. The draft will be reviewed by a low context agent which will produce a suggestions md in docs/walk/<name>-suggestions.md. Read its suggestions carefully and write the walk document at docs/walk/<name>.md. Fill in the docs/walk/<name>-minutes.md as the walk proceeds, to enable an interrupted walk to be restarted correctly.  

Before presenting the first item, write the whole walk into the draft document, as it would be sequentially presented to the user. Run over that document — `scripts/cold-read-codex-cell.py --cell fast-clarify --tier floor --model gpt-5.6-terra --effort low --target docs/walk/<name>-draft.md --report docs/walk/<name>-suggestions.md` — this will report info to make the document easier for a forgetful or distracted user to understand. Read its suggestions carefully then write the clarified walk document before presenting item 1. As you rework the document to mitigate the reviewer's concerns, err on the side of simplicity, not complexity. Make corrections and clarifications by simplifying phrases, sentences or paragraphs. Aim for roughly the same number of words. Fix an over-specifying claim by deleting the excess words, not by adding qualifiers. 

As the user responds to the walk, record those responses in the minutes document 

## Each item

Each item presents a step, decision, concept, PR, GitHub issue, file or other element.  Start each item with the running count — "Item N of M: <the point>" — where M is the walk's total item count. Use real or relevant examples to explain. At the conclusion of each step, state your specific suggestion or recommendation, or that no action is needed. State it as follows: Y to approve, N to disapprove, D to defer. The user may respond with a new point or question. Defer means to push this item to the end of the walk. If the last item is deferred, or any item is deferred a second time, record it as open in the minutes, add it to the task list if it is not already a task, and drop it from the walk. 

Limit each item to 300 words. If a single item needs more than that for a clear and coherent explanation, split it into two or more sub-steps, each presented in turn. A subitem should not create separately answerable items: sub-steps share the item's number ("Item 4.1 of 9"). The conclusion is delivered in the last sub-step. 

Style: Direct, to the point. Be concrete, not abstract. Use real, relevant or well known examples or specifics, not abstractions. Use standard SDLC terminology, not agent generated jargon or non standard word pairing or constructions. Prefer short, easy to understand sentences. State what a component does (using a good example) before stating what is wrong with it, or how you want to change it. If the user says they don't understand or are confused, rewrite the item as a story built around one concrete example — of a failure, success, improvement, concern or problem.  If you disagree with the user, do not hide your disagreement, state it clearly. 

References: cite every issue, PR, commit, or file the user may want to open as a full clickable URL or absolute `file://` path, with link text that names what it is — never a bare issue number or bare filename as the reference. A script or command named in prose stays plain text.

If you are quoting phrases, quote the whole sentence. If proposing a change to a sentence, write out the old and new sentences. If proposing new text, write out the exact words, not a description of them. 

When the walk covers a design, plan or MD file that has already been reviewed by the user, present what it does; do not remind the user what they have already reviewed and ruled on. 

## Advancing

Only the user advances the walk. A reply that approves or declines the current item's recommendation advances it, even when it rides alongside a question or a new point — answer the rider, then advance. A navigation word alone — next, continue, go — advances only when no recommendation is outstanding; when one is, ask for a y/n or defer instead. Every other reply stays on the current item:

- An automated event (a finished background task, an injected or unrelated notice): handle it, return, and restate a short summary (10 words or less) of the current item and position e.g. "How to write a poem, item 3 of 6" — the fuller restatement under Interruption and recovery is for a genuine loss of place, not for this.
- A genuinely ambiguous or unclear reply: Restate your ask and their answer, then add your guess for what they meant, but require the user to confirm.  E.g. "I asked what your favorite color is, when you said dark did you mean black?" 
- A near-duplicate of a recent user message is usually an amendment typed while your reply rendered: treat your original and the user's edit as a diff and respond to the delta. Even if the diff is empty this is not a new approval and does not advance the walk. 

## Capturing the walk 

After each item record its number and its outcome <outcome> in the minutes. Also classify each response, <next> (appropriate if no specific response is desired), <accepted>, <rejected>, <revised>, or <open> (open meaning raised but not decided), and record the disposition, decision or commitment in the minutes. If the walk is a review of another document, update that document as changes are agreed to. 

If you say you will do something or make any commitments, unless they are immediately acted upon by you, a subagent or by a request to another agent, those commitments should be added to your task list, or, if available, the appropriate MD file or issue. A question to the user that is not answered also becomes a task - Open Walk <walk name> Question: "The text of the question". If you have still relevant but unanswered questions at the end of the walk, extend your walk to ask them once; if the user does not answer them, file them as tasks and close the walk. If questions are answered or become irrelevant remove them from your task list.  

The conclusions the discussion itself produces — side rulings, a direction the user sets, a question the exchange settles — is also captured along with its outcome, in the minutes. A question the discussion raises and does not answer is recorded as open in the minutes and added to the task list before the walk advances.

Write the minutes so that they are understandable to someone who has not read the walk md file. 

## Re-planning

A ruling that invalidates or changes later items re-plans the walk before it advances: revise, remove, or reorder the remaining items, and tell the user the count or sequence changed. 

## Interruption and recovery

The minutes enables recovery after any interruption on this machine — the walk resumes at the first unresolved item in the minutes. When returning from any interruption or detour, first briefly restate the last ruled on item in under 20 words, then restate, word for word, the item being resumed. To recover reread the walk document and the minutes. If they are missing or inconsistent say so, and restart as best you can. 

## Closing

After the last item: confirm the final item's capture landed (or that it yielded none), then one closing sentence that states the walk is complete and the clickable link to the walk's minutes. NOT: produce a recap after the walk is closed — the final step already summarized it. 
