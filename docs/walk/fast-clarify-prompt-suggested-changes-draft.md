# Walk: the fast-clarify prompt — suggested changes

The fast-clarify prompt is the instruction text a reviewer agent receives when the cold-read skill runs its fast tier: read one document, answer three questions about it in a report. The user rewrote that prompt in Typora and it merged today as [PR #271, the user's draft of the fast-clarify reviewer instructions](https://github.com/nedschorus/nedschorus/pull/271). This walk goes through the changes I suggest to that file, one per item, in file order. The file is [fast-clarify.md on this branch, which is at main](file:///Users/el/Projects/nedschorus/.claude/worktrees/document-bullet-restatement-db7518/.claude/skills/cold-read/prompts/fast-clarify.md).

Three things about Question 1 the user already ruled before this walk, and which the closing item folds in without asking again: the sentence-level bullet holds the original sentence word for word; the gap marker reads "?gap? followed by what is missing"; and each point is restated "in your own plain words".

8 items. Walk document: [fast-clarify-prompt-suggested-changes.md](file:///Users/el/Projects/nedschorus/.claude/worktrees/document-bullet-restatement-db7518/docs/walk/fast-clarify-prompt-suggested-changes.md).

---

## Item 1 of 8: What "atomic set" means when a term is defined in one file and used in another

The opener ends with this sentence:

> If {TARGET_PATH} contains multiple documents, treat these documents as an atomic set, read all of them, then answer the 3 questions for each document in the report.

Question 2 asks the reviewer to report undefined terms. Take a pull request that adds a glossary entry for "cell" and a design that uses "cell" without defining it. The reviewer reads both. When it reaches "cell" in the design, does it report an undefined term or not?

Under one reading, "atomic set" means the files are one unit of context, so the glossary settles the term and there is nothing to report. Under the other, each document is judged on its own, so "cell" is undefined in the design and gets an item. Two reviewers will pick differently.

The opener's own purpose sentence points to the first reading: the target "must be usable by a future agent who has only this info", and "this info" is the whole set. I recommend saying so in one clause.

Old sentence:

> If {TARGET_PATH} contains multiple documents, treat these documents as an atomic set, read all of them, then answer the 3 questions for each document in the report.

New sentence:

> If {TARGET_PATH} contains multiple documents, treat these documents as an atomic set: read all of them before answering, and a term or reference one of them settles is settled for all of them; then answer the 3 questions for each document in the report.

This is the one item where I am guessing your intent. If you meant the second reading, the clause flips to "and judge each document on its own words".

Recommendation: adopt the new sentence. Y to approve, N to disapprove, D to defer.

---

## Item 2 of 8: The ??? marker goes on the bullet or the sub-bullet

Question 1 says:

> If the sentence does not make sense to you, your restatement may also not make sense, in which case add a ??? to the end that bullet.

Two problems. "The end that bullet" is missing "of". And "that bullet" names only the sentence-level bullet, which is the wrong place when one point is the problem. Take a sentence with three points where the third clause is garbled: the first two sub-bullets restate cleanly and only the third is nonsense. The reviewer wants to mark the third sub-bullet, not the whole sentence. The gap rule two sentences later already says "bullet or sub-bullet", so this rule should match it.

Old sentence:

> If the sentence does not make sense to you, your restatement may also not make sense, in which case add a ??? to the end that bullet.

New sentence:

> If a sentence or point does not make sense to you, your restatement may also not make sense, in which case add ??? to the end of that bullet or sub-bullet.

Recommendation: adopt the new sentence. Y to approve, N to disapprove, D to defer.

---

## Item 3 of 8: "section-question" becomes "question"

Question 1 closes with:

> This section-question exists so the author can check whether you understood what they meant, which is why you should be literal, and not try to guess a coherent meaning if there is none.

"Section-question" is a term the file invents and never defines. The heading above it already says "Question 1", and the opener says "three questions ... in three sections", so the plain word does the job. The project's own terminology reviewer, [terminology.md, the cold-read terminology prompt](file:///Users/el/Projects/nedschorus/.claude/worktrees/document-bullet-restatement-db7518/.claude/skills/cold-read/prompts/terminology.md), is told to look hardest at "ordinary words made quietly technical", which is exactly this.

Old sentence:

> This section-question exists so the author can check whether you understood what they meant, which is why you should be literal, and not try to guess a coherent meaning if there is none.

New sentence:

> This question exists so the author can check whether you understood what they meant, which is why you should be literal, and not try to guess a coherent meaning if there is none.

Recommendation: adopt the new sentence. Y to approve, N to disapprove, D to defer.

---

## Item 4 of 8: A heading, a list item or a table row counts as a sentence

Question 1 says "one bullet per sentence" and nothing about the parts of a markdown document that are not sentences. This project's documents are mostly those parts. CLAUDE.md is entirely bullet points. A wiki page is headings, lists and tables.

Without a rule, reviewers diverge. One drops the headings and hands the author a flat list of two hundred bullets with no landmarks. Another restates each heading as a point. A third folds a whole bulleted list into one bullet because it is not "a sentence". The author cannot tell which choice produced the report, and the report is hardest to check exactly where the document is longest.

One sentence, added after the first sentence of Question 1, settles it:

> A heading, a list item or a table row counts as a sentence.

So a heading gets its own bullet holding the heading text, each list item gets a bullet, each table row gets a bullet, and each of those gets sub-bullets for its points like any sentence.

Recommendation: add the sentence. Y to approve, N to disapprove, D to defer.

---

## Item 5 of 8: Frontmatter — restate the prose fields, skip the data fields

The opener tells the reviewer to read the target "including any YAML frontmatter". Question 1 then gives frontmatter no rule. Take the cold-read skill's own SKILL.md: its frontmatter has a `name:` line and a `description:` paragraph. The description is the sentence the author most wants checked, because it is what makes the skill trigger. The name is data.

Left alone, one reviewer bullets "name: cold-read" as a point, which is noise, and another skips the whole frontmatter block, which loses the description. The project's older restate prompt, [restate.md, the cold-read restate prompt](file:///Users/el/Projects/nedschorus/.claude/worktrees/document-bullet-restatement-db7518/.claude/skills/cold-read/prompts/restate.md), already has the rule, so this lifts it.

New sentence, added to Question 1 after the gap rule:

> In frontmatter, restate prose fields such as a description like any other sentences, and skip data fields such as a name, ids or dates.

Recommendation: add the sentence. Y to approve, N to disapprove, D to defer.

---

## Item 6 of 8: A doubled "and" in Question 2

Question 2's concision line reads:

> BE CONCISE: for each issue, quote the exact phrase and then a sentence naming the defect and and why it matters.

New sentence:

> BE CONCISE: for each issue, quote the exact phrase and then a sentence naming the defect and why it matters.

Recommendation: fix the typo. Y to approve, N to disapprove, D to defer.

---

## Item 7 of 8: Question 2's two reference bullets — one item or two?

Question 2 lists six things to report. Two of them are:

> * references that go nowhere

> * references you could not follow

Read cold, these are one item, and a reviewer who finds a broken reference will list it under both or wonder which one it belongs under. But the opener's context rule makes a real distinction possible. The reviewer may not go looking beyond what the document names by explicit path. So a reference can fail two ways: the path or name it gives does not exist, or it gives no path at all, only a description, and the rule forbids the search.

If you mean the two cases, a few words on each bullet keeps them apart:

> * references that go nowhere - a path or name that does not exist

> * references you could not follow - named without an explicit path, so the context rule above forbids looking for them

If you mean one case, the fix is to delete the second bullet.

Recommendation: keep both bullets with the added words. Y to approve, N to disapprove, D to defer.

---

## Item 8.1 of 8: The assembled Question 1

The decisions this walk produced are listed in the minutes as they landed. With every item approved, and the three pre-walk rulings folded in, Question 1 reads:

> Restate each document or source text as a list of bullets and sub-bullets: one bullet per sentence, holding that sentence as written, and under it one sub-bullet per point, action, fact, idea, concept or claim in that sentence, in the order they were originally presented. A heading, a list item or a table row counts as a sentence. A sentence may contain many points. Do not merge or omit details. Restate each point in your own plain words, literally and precisely. If a sentence or point does not make sense to you, your restatement may also not make sense, in which case add ??? to the end of that bullet or sub-bullet. If there is a clear gap in the source text, note that gap with a bullet or sub-bullet that says ?gap? followed by what is missing. In frontmatter, restate prose fields such as a description like any other sentences, and skip data fields such as a name, ids or dates. Your rewrite should be roughly double the length of the original. This question exists so the author can check whether you understood what they meant, which is why you should be literal, and not try to guess a coherent meaning if there is none. Your rewrite helps the author determine if other agents correctly parse their text.

Any item you declined stays as it is in the file today. No decision in this sub-step; the next one asks who applies the result.

---

## Item 8.2 of 8: Who applies the accepted changes

Two ways to land it. You paste the accepted text into the file in Typora and have a seat PR it, as with PR #271. Or I apply the accepted changes on this branch, which is already at main, commit, and open the PR for you to read as a diff. I recommend the second: the edits are exact sentences, the branch is current, and the diff shows each one against the merged text.

One note for testing the result, no decision needed: run it through a cell launcher such as scripts/cold-read-codex-cell.py or scripts/cold-read-agy-cell.py with --cell fast-clarify, which read this file from the prompts directory. The scripts/cold-read-fast-read.py script runs its own embedded copy of the previous prompt text, so a run through it measures the old prompt. Replacing that copy is the MD-skills seat's task #57.

Recommendation: I apply the accepted changes on this branch and open the PR. Y to approve, N to disapprove, D to defer.
