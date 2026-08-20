---
name: walk-me-through
description: Present complex, multi-part material to the user one item at a time, pausing for his go-ahead between items. Use when a large multi-part result has just been produced or requested — findings, a design or plan to review, a triage list, a queue to drain — and the user will react or rule per item; when he says "walk me through X", "one at a time", or "slower"; or, unprompted, whenever your own reply would run past about four paragraphs of substantive explanation, or would ask a single approval covering several separately-decidable parts — walk it, whether it decomposes into decisions or is one explanation delivered in comprehension-sized steps. Not for material he asked to receive whole, or a reply short enough to land in one message. With no argument, walk the most recent large result in this conversation; if none exists, say so and ask for the subject. If the subject was requested but not yet produced, produce it first, then walk it.
---

# Walk me through

Deliver complex material as a sequence of items, each sized to one decision or one comprehension step, one item per presenting turn, advancing only on the word of the user — the human operator running the project. A deciding walk's product is the decisions captured in their durable homes as they land; a teaching walk's product is comprehension, and its items legitimately capture nothing.

## Opening a walk

State the subject, the item count, and the walk's anchor in one line, then present the first item. A wrong subject guess in that line gives the user an immediate chance to correct it.

Every walk needs an anchor for its marks, resolved in priority order:

1. **The subject document**, when it lists or contains the items being walked (a plan, spec, queue file, findings report): dispositions are marked there, in place.
2. **The walk's issue pair document** — the issue's companion document (`docs/issues/<n>-<slug>.md`) — when the walk serves an issue; or, when the walk's outcome is task-shaped work the project would track as an issue, create the pair at walk open. The pair document carries the marks and follows its normal close lifecycle.
3. **Otherwise, a tmp-file ledger**: machine-local and uncommitted, in the checkout's gitignored `walk-ledgers/` directory with a dated, topic-named filename — a fixed location, so an interrupted session recovers the ledger by listing that directory, never from conversation memory. The ledger has one reader — the interrupted walk resuming at its first unresolved item — and it is deleted when the walk closes. Decisions survive only in their durable homes (issue bodies, commit messages, the governing documents, the artifacts themselves); the ledger is never committed.

Whenever the walk's order is not inherent in the anchor itself, also record the ordered item list in the anchor as a walk-order block (a numbered list under a `## Walk order` heading) — in-place marks alone cannot say which unresolved item is next.

When the walk decides things — the user will rule per item — open with a purpose item before any mechanism item: one item establishing what the decisions are for and the bar they will be judged by. A walk where the user only needs to understand is a teaching walk and needs no purpose item.

## Ordering

Follow the material's innate order when items depend on earlier ones to make sense — a system, a process, a dependency chain. Otherwise rank by importance, most important first. The test is comprehension, not execution: a findings list whose fixes must land in sequence still walks by importance. A mixed collection keeps required-sequence groups together, placing each group at the rank of its most important member, and uses the "Item N of M" heading scheme throughout.

## Each item

One item is one thing the user can react to on its own — one issue, one file, one decision. Before bundling parts into an item, test: could they get different answers? If yes, split. Also split: unrelated requests for approval; a complex issue, into the steps that explain it; an item that refers to a file, PR, or GHI that is not summarized, so a summary can be included. More but simpler items is better than fewer but more complex or cryptic items.

Head every item with the running count — "Item N of M: <the point>" (or "Step N of M" on an innate-order walk) — and lead with the point. M is the current plan's count, purpose item included; a re-plan or size-split restates it. For a finding or recommendation, include the proposed action, not just the problem. When an item asks the user to choose among options, present it as a proposal: name the recommended option first and state that approval enacts it, then list the alternatives, each with the word that selects it. When there is no recommendation, say so and ask for an explicit choice. Never end a choice item with wording under which an approval word has no defined meaning. End every non-final presenting turn with exactly "Ready for the next item?" (or "Ready for the next step?" on an innate-order walk, or "Ready for the next part?" between sub-steps) — the visible pause is a required slot, not a flourish. A turn that answers a question and stays on the current item does not repeat the pause line — re-asking after the user withheld approval reads as pressure; end with the answer.

The size cap is 300 words per item, and it is a comprehension budget, not a brevity target: the target is complete and clear. Length is not the measure: never cut needed substance to be shorter, never pad to look thorough; use what completeness needs within the cap, and split when the cap is too small. An item that needs more than the cap becomes two or more sub-steps, each presented separately. A size-split does not create separately answerable items: sub-steps share the item's number ("Item 4 of 9, part 2 of 3"), deliver the content in stages, and the item's single decision is asked once, at the last sub-step.

Language: precise standard terminology, plainly used. The user is technical — do not over-simplify — but never coin vocabulary or reach for figurative phrasing where a standard term exists. Write each item in the register of one senior engineer explaining to another out loud: short sentences, concrete nouns, active verbs. When a term of art must appear, restate it in plain words at first use ("the entry checkpoint — the gate that records every legacy import"). A sentence that needs the conversation's history to parse is rewritten to stand alone. When the user says he does not understand, rewrite the item as a story built around one concrete failure example — or a concrete worked example when nothing fails — rather than restating the abstraction.

References: cite every issue, PR, commit, or file the user may want to open as a full clickable URL or absolute `file://` path, paired with a self-documenting handle — never a bare issue number or bare filename as the reference. A script or command named in prose stays plain text.

When the subject is a design or plan whose decisions the user has already ruled, present what it does — mechanisms, behaviors, branches — and omit the justification: re-derived rationale spends the budget without informing the reaction. Rationale returns when the user asks, or when the walk's subject IS the reasoning (a review's findings, a trade-off analysis).

## Advancing

Only the user advances the walk. A clear approval word — "y", "next", "go", "approved", or any equivalent unambiguous yes — moves to the next item, even when it rides alongside a reaction: answer the rider, then advance. Everything else — any reply with no approval word in it — stays on the current item:

On an item that offers options, a bare approval word enacts the stated recommendation; an alternative is chosen by naming it. On an item with no stated recommendation, a bare approval word is ambiguous — ask, never guess.

- A question, reaction, or new point: answer it, stay.
- An automated event (a finished background task, an injected notice): handle it, return, and restate position ("back to item 3 of 6"). An automated event is never approval.
- A genuinely ambiguous reply: ask — re-showing the current item is a fine way to ask — never guess.
- A near-duplicate of a recent user message is usually an amendment typed while your reply rendered: treat the pair as one message and respond to the delta. When the delta is empty it is a re-send — respond once, and never read repetition as a second approval.
- An instruction that changes the walk itself — stop, pause, hand over the rest whole, switch subjects — is followed, not treated as a stay-on-item reply: the user controls the walk's existence, not just its pace.

NOT: advance because progress feels owed — a completed side task, a long silence, an unrelated notice. DO: advance on the user's approval word alone.

## Capturing — the walk is a working review

After each user response, classify the item: accepted, rejected, revised, or open — open meaning raised but not decided, because the user deferred or the answer depends on something pending. Then, before advancing:

1. Mark the disposition at the anchor — the subject document, pair document, or ledger. Accepted, rejected, and revised items get a dated `processed <date> → <outcome>` line at the item's place. An open item gets an `open <date> — <what is pending>` note instead of a processed mark, so the resume rule returns to it. Marking never deletes the item's body.
2. Record any decision or commitment in its durable home — the issue body (edited in place per the revision convention: revise the body itself; comments only for genuinely new events), the governing document, the code, or the commit that lands the change. When rulings accumulate, update the governing plan document alongside the specific artifacts it points to.
3. State where the capture landed, or that the item yielded none. A blanket "nothing to capture" at walk end is how decisions get lost in conversation. On a teaching walk, per-item "nothing to capture" is the expected, legitimate state.

The same duties cover conclusions the discussion itself produces — a side ruling, a direction the user sets, a question the exchange settles — even when they are not the item's own decision: capture each in its durable home before the walk advances. Never advance past an important question the discussion raised but left unanswered — resolve it or record it as open first.

Approval is a pass, not a silencing. The user's word means the item passed his judgment; it does not settle how the change reads to the agents who must act on it. When an agent objects to what a walk adopted — especially to how its words are interpreted — that objection gets a hearing rather than being closed by citing the walk. Bring it back to the user in the objector's own words; often the outcome is wording that satisfies both. This applies while the walk runs too: an item built on an agent's objection is presented as that agent stated it, not as the presenting agent's preferred repair of it.

Capture the decision, never the meeting: the durable record carries the ruling's substance, date, and reasoning, and reads correctly to someone who does not know a walk happened. Walk framing ("item 6", "the user said") stays out of decision records — issue bodies, commits, governing documents. The anchor is the sanctioned exception: its disposition marks and walk-order block are walk records by design.

## Re-planning

A ruling that invalidates or changes later items re-plans the walk before it advances: revise, remove, or reorder the remaining items, update the anchor to match, and tell the user the count or sequence changed. Superseded material stays marked in the anchor rather than deleted — evidence for the walk's duration under a tmp ledger, durably where the anchor is durable. Questions and reactions that change no decision trigger no re-planning and no anchor edits.

## Interruption and recovery

The anchor is the recovery contract: after any interruption on this machine — a context reset, a session end, a long detour — the walk resumes at the first unresolved item (no processed mark; open notes count as unresolved) in the anchor's recorded order, recoverable from the anchor alone with no conversation state. A tmp-file ledger is machine-local, so recovery crosses sessions and context resets, not machines. Returning from any detour, restate position before continuing. After a context reset, never guess the position: reread the anchor. If the anchor is missing or inconsistent, say so and rebuild the item list with the user — still never guess.

## Closing

After the last item: confirm the final item's capture landed (or that it yielded none), then one closing sentence whose job is to state that the walk is complete and where its captures landed. NOT: produce an unsolicited recap, summary, or summary file of the walk — a recap the user asks for is his to have. DO: end with that single sentence — the captures in their homes are the walk's record.

## Runtime parity

This file is the canonical behavioral contract. A companion-runtime wrapper — Codex, once it is admitted as a companion runtime — derives from it: thin differences only (metadata, invocation syntax, tool names), with semantic parity to this contract. The contract and every derived wrapper are exercised against the same shared scenarios below.

## Shared acceptance scenarios

Live user-supervised use is the quality judgment for this skill's interaction behavior — its interaction failures are visible immediately, so it iterates in live use per the project's skill-authoring checklist (findable by that name under `docs/`). These six scenarios are the shared set the contract and every derived wrapper must handle; the mechanically checkable behaviors in them (word caps, count labels, mark-before-advance) get scripted tests only if this skill's failures ever prove silent and frequent enough that live iteration misses them:

1. An over-compressed explanation the user cannot interpret.
2. A complex item that must split into sub-steps.
3. A settled-design walk that must not re-derive already-ruled rationale.
4. A rejected or revised item, captured correctly.
5. An interruption and correct resumption from the anchor.
6. A response that changes later items, forcing a re-plan.
