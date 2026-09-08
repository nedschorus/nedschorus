Read {TARGET_PATH} in full, including any YAML frontmatter, and answer three questions about it, in three sections, in the order below. Your context is deliberately minimal — what your runtime already loaded, the document or documents under review, and whatever they reference by an explicit path. Nothing else: do not go looking. That limit is the point, because {TARGET_PATH} must be usable by a future agent who has only this info. {TARGET_PATH} is read-only: do not edit it or anything else in the checkout. The one file you create is your report. If {TARGET_PATH} contains multiple documents, treat them like chapters of one book: any one of them can define or explain what the others rely on, and they should be consistent amongst themselves; repetition is fine, gaps or inconsistencies are not. Read all of them, then answer the 3 questions for each document in the report.

## Question 1: What it says

Restate each document or source text as follows. For each sentence, write its first four words, exactly as written, on a line of their own, then one bullet per point, action, fact, idea, concept or claim in that sentence, in the order they were originally presented. A heading or a table row counts as a sentence; a list item is split into its sentences like any paragraph. A sentence may contain many points. Do not merge or omit details. Restate each point in your own plain, succinct words, literally and precisely. If a sentence or point does not make sense to you, your restatement may also not make sense, in which case add ?nonsense? to the end of that line or bullet. If there is a clear gap in the source text, note that gap with a bullet that says ?gap? followed by what is missing. In frontmatter, a data field such as a name, ids or dates gets no bullets; a prose field such as a description is treated like any other sentence. Your bullets, taken together, should be roughly the length of the original. This question exists so the author can check whether you understood what they meant, which is why you should be literal, and not try to guess a coherent meaning if there is none. Your rewrite helps the author determine if other agents correctly parse their text.

## Question 2: Where you struggled

Note where an agent might waste tokens or come to incorrect conclusions:

* every place in the text that seemed unclear, opaque, incoherent.
* ambiguities - phrases or sentences that could read two different ways, in which case describe both readings, including the use of pronouns with ambiguous subjects
* references that do not resolve - the file does not exist at the path stated
* meanings you resolved only by reading into it your own ideas, because the document is not clear and complete.
* undefined terms, or terms the document uses as if they were already defined
* references you could not follow - no explicit path is given, so the context rule above forbids looking for it

BE CONCISE: for each issue, quote the exact phrase and then a sentence naming the defect and why it matters. Focus on issues that would actually misdirect or block a fresh reader following the document's instructions. Report every real issue you found — conciseness is about the length of each item, never about dropping a genuine problem. Number each item.

## Question 3: What it does not cover that it implies it should

The text explains something or tells its reader what to do. Find the gaps within its logic, situations it covers incompletely, likely cases or states that are not covered, or are covered in conflicting ways. Take each rule, instruction, case, or definition the document states, and ask what a reader needs to know that is not explained — a boundary value falling between two cases, a state the document's own machinery could reach but never names, a step with no stopping point, a failure the text neither handles nor rules out. BE CONCISE here too: for each gap, quote the relevant text and describe its gap. Ask this only of what {TARGET_PATH} sets out to cover; a subject it never takes up is not a gap.

Number the items in sections 2 and 3 separately, ORDERED MOST IMPORTANT FIRST — the issue most likely to stop a fresh reader leads its section. If there are no issues, say "No issues".

Write your report to {REPORT_PATH}, once, when your analysis is complete. That file is your entire deliverable: what you say in conversation is discarded. Start your report with a list of the files you were told to examine. Note if you were unable to read any of them. {REPORT_PATH} is the only file to create; write nothing anywhere else.
