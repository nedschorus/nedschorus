---
name: walk-me-through
description: Present long or complex material to the user one item at a time, pausing for his response between items, and so long responses do not have to be condensed to fit. Also trigger when the user requests "one at a time", or "slower"; or, whenever your own reply will be longer than four paragraphs of substantive explanation, or when you present multiple items for approval that are not interdependent. Not for material he asked to receive whole. If the subject was requested but not yet produced, produce it first, then walk it.
---

# Walk me through

Deliver complex material as a sequence of items, each sized to one decision or one comprehension step, one item per presenting turn, advancing only on the word of the user. As decisions are made in walks, they are recorded in an MD file as they are made. Each walk will have 4 MD files in docs/walk/, a draft document with the proposed text of the walk, a suggestions document, which will contain the suggestions to make the document easier for any reader to understand, a walk document with the text to be presented to the user during the walk, and a minutes document which records the results or minutes of the walk with the user. The name of the walk <name> should be self-documenting, explaining the walk's topic, and be long enough to be unique.

## Opening a walk

State the subject in under 40 words, the item count, a clickable link of the name of the walk document, the MD file that contains the text of the walk to be presented to the user, in case the user wants to open it as a whole. Create the minutes document, empty; it fills as the walk runs.  The initial draft document is located at docs/walk/<name>-draft.md. The draft will be reviewed by a low context agent which will produce a suggestions md in docs/walk/<name>-suggestions.md. Read its suggestions carefully and create a final draft of the walk in the walk file before presenting item 1. The walk is located in docs/walk/<name>.md, the minutes in docs/walk/<name>-minutes.md. This enables an interrupted walk to be restarted correctly.  

Before the first item, write the whole walk into the draft document, every item's text — the item body as it would be presented. Run over that document — `scripts/cold-read-codex-cell.py --cell fast-clarify --tier floor --model gpt-5.6-terra --effort low --target docs/walk/<name>-draft.md --report docs/walk/<name>-suggestions.md` — it will report suggestions to make the document easier for a forgetful or low context human to understand. Read its suggestions carefully and create an easier to follow final draft of the walk before presenting item 1. If the review fails or produces nothing, use the draft as the walk and tell the user the review did not run.  When you try to resolve the reviewer's concerns, err on the side of simplicity, not complexity. Make corrections and clarifications by simplifying phrases, sentences or paragraphs. Aim for a stable word count. Fix an over-specifying claim by deleting the excess words, not by adding qualifiers. 

As the user responds to the walk, record those responses in the minutes document 

## Ordering

Follow the material's innate order when items depend on earlier ones to make sense — a system, a process, a dependency chain. Otherwise rank by importance, most important first. A mixed collection keeps required-sequence groups together, placing each group at the rank of its most important member, and uses the "Item N of M" heading scheme throughout.

## Each item

One item is one thing the user can react to on its own — one issue, one file, one decision. Before bundling parts into an item, test: could they get different answers? If yes, split. Also split: unrelated requests for approval; a complex issue, into the steps that explain it; an item that refers to a file, PR, or GHI (GitHub issue) that is not summarized, so a summary can be included. More but simpler items is better than fewer but more complex or cryptic items.

Head every item with the running count — "Item N of M: <the point>" (or "Step N of M" on an innate-order walk) — and lead with the point. M is the walk's current item count; a re-plan or size-split restates it. For a finding or recommendation, include the proposed action, not just the problem. Use examples to explain problems when helpful. Make a single recommendation. The user can adopt it with a Y or other expressions of agreement or approval, or respond as they see fit.  When there is no recommendation, simply list the options.  If the user responds with a question,  or new point: answer it, and stay on the current item. Do not advance to the next item until the user rules on the current item - they could Y or affirm the suggestion, N or not accept the suggestion. If they say next or continue, go to the next item, unless that current item has a suggestion that should be approved or disapproved.  In that case ask for a Y N or defer the suggestion. If they defer, move that item to  the end of the walk. 

The size cap is 300 words per item, using direct, clear and complete language, not condensed. Do not use agent created jargon. Use as many words as necessary to be clear. An item that needs more than the cap becomes two or more sub-steps, each presented separately. A size-split does not create separately answerable items: sub-steps share the item's number ("Item 4 of 9, part 2 of 3"), deliver the content in stages, and the item's single decision is asked once, at the last sub-step.

Style: Spock-like. Language: concrete, direct and precise standard terminology. The user is technical — do not over-simplify — but never coin vocabulary or reach for figurative phrasing where a standard term exists. Write each item in the register of one senior engineer explaining to another out loud: use examples, be direct, be concrete, prefer short sentences, concrete nouns, active verbs. When a term of art must appear, restate it in plain words at first use ("the entry checkpoint — the gate that records every legacy import"). Write every item for a reader with a limited memory and minimal context— the user runs many seats (parallel sessions) and returns after gaps. A sentence that leans on anything said before the walk opened is rewritten to stand alone; an earlier item of the same walk may be leaned on. The item's first sentence states its subject as if newly introduced. When the user says he does not understand, rewrite the item as a story built around one concrete example — either of a success or of a failure — rather than restating the abstraction. The user may say they are confused or ask for a rewrite. Give that rewrite the walk-open fast review before re-presenting it — run the same review command over the rewritten item's text — and fix what it finds. 

References: cite every issue, PR, commit, or file the user may want to open as a full clickable URL or absolute `file://` path, paired with a self-documenting handle — never a bare issue number or bare filename as the reference. A script or command named in prose stays plain text.

When the subject is a design or plan whose decisions the user has already ruled, present what it does — mechanisms, behaviors, branches — and omit the justification: re-derived rationale spends the budget without informing the reaction. Rationale returns when the user asks, or when the walk's subject IS the reasoning (a review's findings, a trade-off analysis).

## Advancing

Only the user advances the walk. A clear approval word — "y", "next", "go", "approved", or any equivalent unambiguous yes — or clear disapproval - moves to the next item, even when it rides alongside a reaction: answer the rider, then advance. Everything else — any reply with no approval word in it — stays on the current item:

On an item that offers options, a bare approval word enacts the stated recommendation. 

- An automated event (a finished background task, an injected notice): handle it, return, and restate position ("back to item 3 of 6"). An automated event is never approval.
- A genuinely ambiguous reply: ask — re-showing the current item is a fine way to ask — never guess.
- A near-duplicate of a recent user message is usually an amendment typed while your reply rendered: treat the pair as one message and respond to the delta. When the delta is empty it is a re-send — respond once, and never read repetition as a second approval.
- An instruction that changes the walk itself — stop, pause, hand over the rest whole, switch subjects — is followed, not treated as a stay-on-item reply: the user controls the walk's existence, not just its pace.

NOT: advance because progress feels owed — a completed side task, a long silence, an unrelated notice. DO: advance on the user's approval word alone.

## Capturing — the walk is a working review

After each user response, classify the item: accepted, rejected, revised, or open — open meaning raised but not decided, because the user deferred or the answer depends on something pending. Then, before advancing:

1. Mark the disposition in the minutes. Accepted, rejected, and revised items get a dated `processed <date> → <outcome>` line under the item's number. An open item gets an `open <date> — <what is pending>` note instead of a processed mark, so the resume rule returns to it. Marking never deletes the item's body.
2. Record any decision or commitment in its durable home — the issue body (edited in place; comments only for genuinely new events), the governing document, the code, or the commit that lands the change. When rulings accumulate, update the governing plan document alongside the specific artifacts it points to.
3. State where the capture landed, or that the item yielded none. A blanket "nothing to capture" at walk end is how decisions get lost in conversation. A question to the user that is not answered in the turn it is asked becomes a task on the seat's task list, titled as the question; a walk item is a home for it only while that walk runs, and anything still unanswered when the walk closes becomes a task too. On a walk where the user only needs to understand — nothing is being decided — per-item "nothing to capture" is the expected, legitimate state.

The same duties cover conclusions the discussion itself produces — a side ruling, a direction the user sets, a question the exchange settles — even when they are not the item's own decision: capture each in its durable home before the walk advances. Never advance past an important question the discussion raised but left unanswered — resolve it or record it as open first.

Approval is a pass, not a silencing. The user's word means the item passed his judgment; it does not settle how the change reads to the agents who must act on it. When an agent objects to what a walk adopted — especially to how its words are interpreted — that objection gets a hearing rather than being closed by citing the walk. Bring it back to the user in the objector's own words; often the outcome is wording that satisfies both. This applies while the walk runs too: an item built on an agent's objection is presented as that agent stated it, not as the presenting agent's preferred repair of it. This holds outside a walk too: wordings are chosen on merit, nobody's draft, the user's included, wins by authorship, and a real disagreement about wording goes to the user in the objector's own words.

Capture the decision, never the meeting: the durable record carries the ruling's substance, date, and reasoning, and reads correctly to someone who does not know a walk happened. Walk framing ("item 6", "the user said") stays out of decision records — issue bodies, commits, governing documents. The minutes are the sanctioned exception: their disposition marks are walk records by design.

## Re-planning

A ruling that invalidates or changes later items re-plans the walk before it advances: revise, remove, or reorder the remaining items, and tell the user the count or sequence changed. 

## Interruption and recovery

The minutes enables recovery after any interruption on this machine — a context reset, a session end, a long detour — the walk resumes at the first unresolved item (no processed mark; open notes count as unresolved) in the minutes. The results of each turn is its own line in the minutes. A recycle appends a dated line to the minutes: the current item, and any work in flight. Returning from any detour, restate position before continuing. After a context reset, never guess the position: reread the walk document and the minutes. If they are missing or inconsistent, say so and rebuild the item list with the user — still never guess.

## Closing

After the last item: confirm the final item's capture landed (or that it yielded none), then one closing sentence whose job is to state that the walk is complete and where its captures landed. NOT: produce an unsolicited recap, summary, or summary file of the walk — a recap the user asks for is his to have. DO: end with that single sentence — the captures in their homes are the walk's record.
