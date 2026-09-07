Read {TARGET_PATH} in full, including any YAML frontmatter, and answer three questions about it, in three sections, in the order below. Your context is deliberately minimal — what your runtime already loaded, these documents, and whatever they reference by an explicit path. Nothing else: do not go looking. That limit is the point, because {TARGET_PATH} must be usable by a future agent who has only this info. {TARGET_PATH} is read-only: do not edit it or anything else in the checkout. The one file you create is your report. If {TARGET_PATH} contains multiple documents, treat these documents as an atomic set, read all of them, then answer the 3 questions for each document in the report.

## Question 1: What it says

Restate each document or source text as a list of bullets and sub-bullets, one bullet per sentence, one sub bullet per point, action, fact, idea, concept or claim, in that sentence, in the order they were originally presented. A sentence may contain many points. Do not merge or omit details. Restate each point in your own words, literally and precisely. If the sentence does not make sense to you, your restatement may also not make sense, in which case add a ??? to the end that bullet. If there is a clear gap in the source text note that gap with bullet or sub-bullet that says ?gap?. Your rewrite should be roughly double the length of the original. This section-question exists so the author can check whether you understood what they meant, which is why you should be literal, and not try to guess a coherent meaning if there is none.  Your rewrite helps the author determine if other agents correctly parse their text. 

## Question 2: Where you struggled

Note where an agent might waste tokens or come to incorrect conclusions:

* every place in the text that seemed unclear, opaque, incoherent.
* ambiguities - phrases or sentences that could read two different ways, in which case describe both readings, including the use of pronouns with ambiguous subjects
* references that go nowhere
* meanings you resolved only by reading into it your own ideas, because the document is not clear and complete.
* undefined terms, or terms the document uses as if they were already defined
* references you could not follow

BE CONCISE: for each issue, quote the exact phrase and then a sentence naming the defect and and why it matters. Focus on issues that would actually misdirect or block a fresh reader following the document's instructions. Report every real issue you found — conciseness is about the length of each item, never about dropping a genuine problem. Number each item. 

## Question 3: What it does not cover that it implies it should

The text explains something or tells its reader what to do. Find the gaps within its logic, situations it covers incompletely, likely cases or states that are not covered, or are covered in conflicting ways. Take each rule, instruction, case, or definition the document states, and ask what a reader needs to know that is not explained — a boundary value falling between two cases, a state the document's own machinery could reach but never names, a step with no stopping point, a failure the text neither handles nor rules out. BE CONCISE here too: for each gap, quote the relevant text and describe its gap. Ask this only of what {TARGET_PATH} sets out to cover; a subject it never takes up is not a gap.

Number the items in sections 2 and 3 separately, ORDERED MOST IMPORTANT FIRST — the issue most likely to stop a fresh reader leads its section. If there are no issues, say "No issues"

{REPORT_PATH} is the only file to create; write nothing anywhere else.



Write your report to {REPORT_PATH}, once, when your analysis is complete. That file is your entire deliverable: what you say in conversation is discarded. Start your report with a list of the files you were told to examine. Note if you were unable to read any of them. Create no other file.
