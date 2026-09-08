# Walk: the fast-clarify prompt — suggested changes

The fast-clarify prompt is the instruction text a reviewer agent receives when the cold-read skill runs its fast tier: read one document, answer three questions about it in a report. The user rewrote that prompt in Typora and it merged today as [PR #271, the user's draft of the fast-clarify reviewer instructions](https://github.com/nedschorus/nedschorus/pull/271). This walk goes through the changes I suggest to that file, one per item, in file order; the last item assembles the result and asks who applies it. The file is [fast-clarify.md on the topic branch this walk works from](file:///Users/el/Projects/nedschorus/.claude/worktrees/document-bullet-restatement-db7518/.claude/skills/cold-read/prompts/fast-clarify.md); that branch was cut from main and is identical to it today.

Three things about Question 1 the user ruled in conversation with me earlier today, 2026-09-07, which item 10.1 folds in without asking again: the sentence-level bullet quotes the original sentence word for word; the gap marker reads "?gap? followed by what is missing"; and each point is restated "in your own plain words".

10 items; the last has two sub-steps. Re-planned at item 5 from 8 items, when the user raised the report's bulk: items 6 and 7 were inserted. Walk document: [fast-clarify-prompt-suggested-changes.md](file:///Users/el/Projects/nedschorus/.claude/worktrees/document-bullet-restatement-db7518/docs/walk/fast-clarify-prompt-suggested-changes.md). Minutes: [fast-clarify-prompt-suggested-changes-minutes.md](file:///Users/el/Projects/nedschorus/.claude/worktrees/document-bullet-restatement-db7518/docs/walk/fast-clarify-prompt-suggested-changes-minutes.md).

---

## Item 1 of 10: What "atomic set" means when a term is defined in one file and used in another

The opener ends with this sentence:

> If {TARGET_PATH} contains multiple documents, treat these documents as an atomic set, read all of them, then answer the 3 questions for each document in the report.

Question 2 asks the reviewer to report undefined terms. Take a pull request that adds a glossary entry for "cell" and a design that uses "cell" without defining it. When the reviewer reaches "cell" in the design, does it report an undefined term?

Under one reading, "atomic set" means the files are one unit of context, so the glossary defines it and there is nothing to report. Under the other, each document is judged on its own, so "cell" is undefined in the design. Two reviewers will pick differently. The same choice arises in Question 3: a rule stated in one file may fill a gap in another.

The opener's own purpose sentence points to the first reading: the target "must be usable by a future agent who has only this info", and "this info" is the whole set.

Old sentence:

> If {TARGET_PATH} contains multiple documents, treat these documents as an atomic set, read all of them, then answer the 3 questions for each document in the report.

New sentence, in the user's words (ruled during the walk; the session's proposed clause "what one of them defines or covers counts for all of them" was rejected as not great):

> If {TARGET_PATH} contains multiple documents, treat them like chapters of one book: any one of them can define or explain what the others rely on, and they should be consistent amongst themselves; repetition is fine, gaps or inconsistencies are not. Read all of them, then answer the 3 questions for each document in the report.

Ruled: revised and adopted as above.

---

## Item 2 of 10: The ??? marker goes on the bullet or the sub-bullet

Question 1 says:

> If the sentence does not make sense to you, your restatement may also not make sense, in which case add a ??? to the end that bullet.

Two problems. "The end that bullet" is missing "of". And "that bullet" names only the sentence-level bullet, which is the wrong place when one point is the problem. Take a sentence with three points where the third clause is garbled: the first two sub-bullets restate cleanly and only the third is nonsense. The reviewer wants to mark the third sub-bullet, not the whole sentence. The gap rule two sentences later already says "bullet or sub-bullet", so this rule should match it.

A point the reviewer can read two ways is a different case and is not marked ???; Question 2's second bullet asks for both readings there.

Old sentence:

> If the sentence does not make sense to you, your restatement may also not make sense, in which case add a ??? to the end that bullet.

New sentence:

> If a sentence or point does not make sense to you, your restatement may also not make sense, in which case add ??? to the end of that bullet or sub-bullet.

Recommendation: adopt the new sentence. Y to approve, N to disapprove, D to defer.

---

## Item 3 of 10: "section-question" becomes "question"

Question 1 closes with:

> This section-question exists so the author can check whether you understood what they meant, which is why you should be literal, and not try to guess a coherent meaning if there is none.

"Section-question" is a term the file invents and never defines. The heading above it already says "Question 1", and the opener says "three questions ... in three sections", so the plain word does the job. The cold-read terminology prompt, [terminology.md](file:///Users/el/Projects/nedschorus/.claude/worktrees/document-bullet-restatement-db7518/.claude/skills/cold-read/prompts/terminology.md), tells its reviewer to look hardest at "ordinary words made quietly technical", which is exactly this.

Old sentence:

> This section-question exists so the author can check whether you understood what they meant, which is why you should be literal, and not try to guess a coherent meaning if there is none.

New sentence:

> This question exists so the author can check whether you understood what they meant, which is why you should be literal, and not try to guess a coherent meaning if there is none.

Recommendation: adopt the new sentence. Y to approve, N to disapprove, D to defer.

---

## Item 4 of 10: A heading or a table row counts as a sentence

Question 1 says "one bullet per sentence" and nothing about the parts of a markdown document that are not sentences. This project's documents are full of those parts. CLAUDE.md is entirely bullet points. A wiki page is headings, lists and tables.

Without a rule, reviewers diverge. One drops the headings and hands the author a flat list of two hundred bullets with no landmarks. Another restates each heading as a point. A third folds a whole table into one bullet because a row is not "a sentence". The author cannot tell which choice produced the report, and the report is hardest to check exactly where the document is longest.

One sentence, added after the first sentence of Question 1, settles it:

> A heading or a table row counts as a sentence; a list item is split into its sentences like any paragraph.

So a heading gets its own bullet quoting the heading text, each table row gets a bullet, a list item with three sentences gets three bullets, and each bullet gets sub-bullets for its points like any sentence.

Recommendation: add the sentence. Y to approve, N to disapprove, D to defer.

---

## Item 5 of 10: Frontmatter — restate the prose fields, skip the data fields

The opener tells the reviewer to read the target "including any YAML frontmatter". Question 1 then gives frontmatter no rule. Take the cold-read skill's own SKILL.md: its frontmatter has a `name:` line and a `description:` paragraph. The description is the sentence the author most wants checked, because it is what makes the skill trigger. The name is data.

Left alone, one reviewer bullets "name: cold-read" as a point, which is noise, and another skips the whole frontmatter block, which loses the description. The project's older restate prompt, [restate.md](file:///Users/el/Projects/nedschorus/.claude/worktrees/document-bullet-restatement-db7518/.claude/skills/cold-read/prompts/restate.md), already has the rule, so this lifts it.

New sentence, added to Question 1 after the gap rule:

> In frontmatter, restate prose fields such as a description like any other sentences, and skip data fields such as a name, ids or dates.

Recommendation: add the sentence. Y to approve, N to disapprove, D to defer.

---

## Item 6 of 10: Succinct sub-bullets

Raised by the user at item 5: the restatement is bloating the report files. The sub-bullets are the bulk of it. The reviewer run over this walk's draft shows the shape: Question 1 came back at about twice the draft's length, and nearly all of that is sub-bullets, since the sentence lines were short paraphrases.

On the token question. An agent writing a sentence out costs the same output tokens whether it copies or composes; copying is easier for the model, not cheaper. A shell copy of the file is free, but adding bullets after each sentence then takes one edit per sentence, and each edit quotes the sentence again as its anchor, so that route costs more, not less. The lever is the length of each sub-bullet.

Old sentence:

> Restate each point in your own plain words, literally and precisely.

New sentence:

> Restate each point in your own plain, succinct words, literally and precisely.

Every point still gets its sub-bullet; "do not merge or omit details" stands. Each sub-bullet is short.

Recommendation: adopt the new sentence. Y to approve, N to disapprove, D to defer.

---

## Item 7.1 of 10: Which scheme Question 1 follows

Three ways for the reviewer to lay out Question 1. They differ in what the model types, not in what the author reads, provided your system splices for the third.

A. Verbatim, as ruled earlier today. The reviewer quotes each sentence, then sub-bullets. It types the whole document plus the bullets. The report reads on its own; it costs the most.

B. Copy and insert, your scheme. A script copies the document to the report; the reviewer inserts bullets after each sentence and changes nothing else. The simplest instruction, and the system can diff the result against the source to prove it came through unchanged. It costs the same as A or more, because every insertion is typed together with its anchor.

C. Locator and bullets. The reviewer writes each sentence's first few words on a line, then the bullets. It never types the source; your script splices each block into a copy after the matching sentence. About half the output of A.

Opening sentence of Question 1 under B:

> {REPORT_PATH} holds a copy of the document. After each sentence, insert one bullet per point, action, fact, idea, concept or claim in that sentence, in the order they were originally presented, and change nothing else in the copy.

Under C:

> For each sentence, write its first few words, exactly as written, on a line of their own, then one bullet per point, action, fact, idea, concept or claim in that sentence, in the order they were originally presented.

No decision in this sub-step. 7.2 shows the whole of Question 1 under C and asks.

---

## Item 7.2 of 10: Question 1 under the locator scheme

With C, and every ruling so far, Question 1 reads:

> Restate each document or source text as follows. For each sentence, write its first few words, exactly as written, on a line of their own, then one bullet per point, action, fact, idea, concept or claim in that sentence, in the order they were originally presented. A heading or a table row counts as a sentence; a list item is split into its sentences like any paragraph. A sentence may contain many points. Do not merge or omit details. Restate each point in your own plain, succinct words, literally and precisely. If a sentence or point does not make sense to you, your restatement may also not make sense, in which case add ?nonsense? to the end of that line or bullet. If there is a clear gap in the source text, note that gap with a bullet that says ?gap? followed by what is missing. In frontmatter, a data field such as a name, ids or dates gets no bullets; a prose field such as a description is treated like any other sentence. Your bullets, taken together, should be roughly the length of the original. This question exists so the author can check whether you understood what they meant, which is why you should be literal, and not try to guess a coherent meaning if there is none. Your rewrite helps the author determine if other agents correctly parse their text.

Three wordings moved with the scheme: "that line or bullet" for the ??? marker, "a bullet" for the gap marker, and the size sentence.

Ruled: approved with one revision, the marker ?nonsense? in place of ???, which is in the text above.

---

## Item 8 of 10: A doubled "and" in Question 2

Question 2's concision line reads:

> BE CONCISE: for each issue, quote the exact phrase and then a sentence naming the defect and and why it matters.

New sentence:

> BE CONCISE: for each issue, quote the exact phrase and then a sentence naming the defect and why it matters.

Recommendation: fix the typo. Y to approve, N to disapprove, D to defer.

---

## Item 9 of 10: Question 2's two reference bullets — one item or two?

Question 2 lists six things to report. Two of them are:

> * references that go nowhere

> * references you could not follow

Read cold, these are one item, and a reviewer who finds a broken reference will list it under both or wonder which one it belongs under. But the opener's context rule makes a real distinction possible. The reviewer may not go looking beyond what the document names by explicit path. So a reference can fail two ways: the path or name it gives does not exist, or it gives no path at all, only a description, and the rule forbids the search.

If you mean the two cases, a few words on each bullet keeps them apart:

> * references that go nowhere - the path or name given does not exist

> * references you could not follow - no explicit path is given, so the context rule above forbids looking for it

If you mean one case, the fix is to delete the second bullet.

Recommendation: keep both bullets with the added words. Y to approve, N to disapprove, D to defer.

---

## Item 10.1 of 10: Question 1 as it now stands

Every ruling of this walk is applied to the file on this branch. Question 1 reads, in full:

> Restate each document or source text as follows. For each sentence, write its first four words, exactly as written, on a line of their own, then one bullet per point, action, fact, idea, concept or claim in that sentence, in the order they were originally presented. A heading or a table row counts as a sentence; a list item is split into its sentences like any paragraph. A sentence may contain many points. Do not merge or omit details. Restate each point in your own plain, succinct words, literally and precisely. If a sentence or point does not make sense to you, your restatement may also not make sense, in which case add ?nonsense? to the end of that line or bullet. If there is a clear gap in the source text, note that gap with a bullet that says ?gap? followed by what is missing. In frontmatter, a data field such as a name, ids or dates gets no bullets; a prose field such as a description is treated like any other sentence. Your bullets, taken together, should be roughly the length of the original. This question exists so the author can check whether you understood what they meant, which is why you should be literal, and not try to guess a coherent meaning if there is none. Your rewrite helps the author determine if other agents correctly parse their text.

The opener carries the chapters-of-one-book sentence from item 1. No decision in this sub-step; the next one asks who lands the changes.

---

## Item 10.2 of 10: Who lands the changes

Every ruling of this walk is already applied to fast-clarify.md on this branch, uncommitted. Two ways to land it. I commit on this branch and open the PR, and you read the diff against the merged text of PR #271; the branch was cut from main and carries no other change. Or you take the text into Typora on the main checkout and have a seat PR it, as with PR #271, and this branch's copy is discarded. I recommend the first.

One note for testing the result, no decision needed. The cell launchers read this file from the prompts directory, so a run like this one measures the new text. The user ruled during this item that the fast tier moves to Gemini 3.8 Flash at medium; this is the verified command (exit 0, 61 seconds, on this file itself):

```
scripts/cold-read-agy-cell.py --cell fast-clarify --tier fast --model gemini-3.8-flash-medium --effort medium --target <document> --report <report>
```

The scripts/cold-read-fast-read.py script does not: it runs its own embedded copy of the previous prompt text. Replacing that copy is the MD-skills seat's task #57, named in the PR #271 commit message. The splice script for Question 1's anchors is your system's, outside this file.

Ruled: approved. Committed on this branch and PR'd.
