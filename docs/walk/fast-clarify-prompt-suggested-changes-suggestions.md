<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=243 tokens=47980 target=docs/walk/fast-clarify-prompt-suggested-changes-draft.md -->

# Files examined

- `docs/walk/fast-clarify-prompt-suggested-changes-draft.md` — read in full.
- `.claude/skills/cold-read/prompts/fast-clarify.md` — read; explicitly linked by the draft.
- `.claude/skills/cold-read/prompts/terminology.md` — read; explicitly linked by the draft.
- `.claude/skills/cold-read/prompts/restate.md` — read; explicitly linked by the draft.
- `scripts/cold-read-codex-cell.py` — read; explicitly named by the draft.
- `scripts/cold-read-agy-cell.py` — read; explicitly named by the draft.
- `scripts/cold-read-fast-read.py` — read; explicitly named by the draft.
- `docs/walk/fast-clarify-prompt-suggested-changes.md` — unable to read: the explicitly linked path does not exist in this checkout.

## Question 1: What it says

### Document: `docs/walk/fast-clarify-prompt-suggested-changes-draft.md`

- The document is a walk containing proposed edits to the fast-clarify prompt.
  - The fast-clarify prompt is the instructions given to a reviewer agent when the cold-read skill uses its fast tier.
  - In that tier, the agent reads one document and writes a report answering three questions about it.
- The user revised that prompt in Typora.
  - The revision merged today in PR #271.
  - The linked PR is described as the user's draft of the fast-clarify reviewer instructions.
- This walk examines the edits its writer proposes for that prompt file.
  - It handles one proposed edit in each item.
  - It presents the items in the order in which the affected material occurs in the file.
- The relevant file is `fast-clarify.md` on the current branch.
  - The document says that branch is at `main`.

- Before this walk, the user had already decided three matters concerning Question 1.
  - The bullet for a sentence preserves the original sentence verbatim.
  - A gap marker must say `?gap?` and then state what is absent.
  - Every point must be rewritten in the reviewer's own plain language.
- The final item incorporates those three decisions without asking for them again.

- The walk says that it has eight items.
- Its walk document is identified as `docs/walk/fast-clarify-prompt-suggested-changes.md`.

---

#### Item 1 of 8: the meaning of “atomic set” when one file defines a term used by another

- The first item concerns what “atomic set” means when one file defines a term and another file uses that term.
- The opening instructions finish with a quoted sentence.
  - The quoted rule says that if the target contains several documents, they are an atomic set.
  - It directs the reviewer to read every document in that set.
  - It then directs the reviewer to answer all three questions for every document in the report.
- Question 2 instructs the reviewer to report terms that are undefined.
- The item offers an example pull request.
  - The pull request adds a glossary definition for “cell.”
  - It also adds a design that uses “cell” without defining the word.
- The reviewer reads both files in that example.
- The issue is whether the reviewer should report “cell” as undefined when it encounters the word in the design.

- The first possible interpretation treats the files in an atomic set as shared context.
  - On that interpretation, the glossary's definition resolves the term.
  - Nothing needs to be reported for the use in the design.
- The second possible interpretation evaluates each document separately.
  - On that interpretation, the design itself does not define “cell.”
  - The reviewer should therefore report it as undefined in the design.
- The document predicts that different reviewers will choose different interpretations.

- The item's writer says that the opener's purpose statement supports the first interpretation.
  - The purpose statement says that the target must be usable by a future agent possessing only the supplied information.
  - The writer takes “this info” to mean the entire set of documents.
- The writer recommends making that shared-context reading explicit in one clause.

- The old sentence is reproduced.
  - It says to treat several target documents as an atomic set, read all of them, and answer the three questions for each document.
- A replacement sentence is reproduced.
  - It still tells the reviewer to treat several target documents as an atomic set.
  - It says to read all of the documents before answering.
  - It says that a term or reference resolved by one document is resolved for every document in the set.
  - It still tells the reviewer to answer the three questions for each document in the report.
- The writer says this is the sole item where the writer is inferring the user's intention.
- If the user intended separate-document evaluation instead, the proposed clause would instead say to judge every document solely by its own wording.
- The recommendation is to adopt the replacement sentence.
- The offered responses are Y for approval, N for disapproval, and D for deferral.

---

#### Item 2 of 8: whether the `???` marker belongs on a bullet or a sub-bullet

- The second item concerns where to put the `???` marker.
- Question 1 contains a quoted instruction.
  - It says that when a sentence does not make sense to the reviewer, the restatement may also fail to make sense.
  - It says that in that situation the reviewer should put `???` at the end of “that bullet.”
- The item identifies two problems with the quoted instruction.
  - “The end that bullet” lacks the word “of.”
  - “That bullet” refers only to the sentence-level bullet.
  - The writer says sentence-level placement is wrong when only one point is unclear.
- The example sentence has three points.
  - Its third clause is garbled.
  - The first two sub-bullets can be restated clearly.
  - Only the third sub-bullet is nonsensical.
- In that example, the reviewer should mark the third sub-bullet rather than the complete sentence bullet.
- The gap instruction two sentences later already permits a “bullet or sub-bullet.”
- The writer says the unclear-sentence rule should use the same scope.

- The old sentence is reproduced.
  - It limits the trigger to a sentence that does not make sense.
  - It contains the missing “of” in its direction to append `???`.
  - It calls only for marking “that bullet.”
- A replacement sentence is reproduced.
  - It applies when either a sentence or an individual point does not make sense.
  - It permits the restatement to be unclear in that case.
  - It tells the reviewer to add `???` to the end of the appropriate bullet or sub-bullet.
- The recommendation is to adopt the replacement sentence.
- The offered responses are Y to approve, N to disapprove, and D to defer.

---

#### Item 3 of 8: replacing “section-question” with “question”

- The third item proposes replacing “section-question” with “question.”
- Question 1 ends with a quoted sentence.
  - It says that the section-question lets the author check whether the reviewer understood the author's meaning.
  - It consequently tells the reviewer to be literal.
  - It tells the reviewer not to invent a coherent interpretation when none exists.
- The item says that “section-question” is an invented term without a definition in the file.
- The heading already calls the material “Question 1.”
- The opener already says that the report contains three questions in three sections.
- The writer says the ordinary word “question” is sufficient.
- The project terminology reviewer is linked through `terminology.md`.
  - That prompt tells its reviewer to scrutinize ordinary words silently given technical meanings.
  - The item says “section-question” is precisely such an ordinary word turned into an unannounced technical term.

- The old sentence is reproduced.
  - It uses “section-question” for the author-checking purpose.
- A replacement sentence is reproduced.
  - It uses “question” for exactly that same purpose.
- The recommendation is to adopt the replacement sentence.
- The offered responses are Y to approve, N to disapprove, and D to defer.

---

#### Item 4 of 8: treating a heading, list item, or table row as a sentence

- The fourth item proposes a rule that a heading, list item, or table row counts as a sentence.
- Question 1 requires one bullet for each sentence.
- It gives no instruction for Markdown parts that are not sentences.
- The writer says that the project's documents largely consist of those non-sentence parts.
- `CLAUDE.md` is said to contain only bullet points.
- A wiki page is said to contain headings, lists, and tables.

- The writer says reviewers will diverge without a rule.
- One reviewer might omit headings.
  - That produces a flat two-hundred-bullet output without landmarks.
- Another reviewer might rewrite every heading as a point.
- A third reviewer might combine an entire bulleted list into one bullet because the list is not a sentence.
- The author then cannot know which of those choices yielded the report.
- The report becomes hardest to verify in the places where the document is longest.

- The writer proposes one sentence inserted after Question 1's first sentence.
  - The proposed sentence says that a heading, list item, or table row counts as a sentence.
- Under that rule, a heading receives its own bullet retaining the heading text.
- Each list item receives its own bullet.
- Each table row receives its own bullet.
- Each resulting bullet receives sub-bullets for its points in the same way as any sentence.
- The recommendation is to add the proposed sentence.
- The offered responses are Y to approve, N to disapprove, and D to defer.

---

#### Item 5 of 8: frontmatter, prose fields, and data fields

- The fifth item concerns how Question 1 should handle frontmatter.
- The opener tells the reviewer to read the target including any YAML frontmatter.
- Question 1 supplies no frontmatter-specific rule.
- The item gives the cold-read skill's `SKILL.md` as an example.
  - Its frontmatter includes a `name:` field.
  - Its frontmatter includes a `description:` paragraph.
- The description is said to be the sentence most worth checking.
  - It determines when the skill triggers.
- The name is characterized as data.

- Without guidance, one reviewer may turn `name: cold-read` into a point.
  - The writer calls that noise.
- Another reviewer may omit the full frontmatter block.
  - That loses the description.
- The older restate prompt in `restate.md` already contains the needed rule.
- The proposed addition therefore carries that existing rule into this prompt.

- The proposed sentence is to be placed in Question 1 after the gap instruction.
  - It says to restate prose frontmatter fields, such as a description, as other sentences are restated.
  - It says to skip data fields, such as a name, IDs, or dates.
- The recommendation is to add that sentence.
- The offered responses are Y to approve, N to disapprove, and D to defer.

---

#### Item 6 of 8: a repeated “and” in Question 2

- The sixth item identifies a duplicated “and” in Question 2.
- The quoted concision instruction says to quote the exact phrase and provide a sentence naming the defect “and and why it matters.”
- The replacement sentence removes one of the two adjacent instances of “and.”
- The recommendation is to fix that typographical error.
- The offered responses are Y to approve, N to disapprove, and D to defer.

---

#### Item 7 of 8: whether Question 2's two reference bullets are one issue or two

- The seventh item asks whether two reference-related bullets in Question 2 represent one category or two.
- Question 2 lists six things that a reviewer should report.
- Two quoted bullets say “references that go nowhere” and “references you could not follow.”
- On a cold reading, the item says these can appear to be the same requirement.
- A reviewer finding a broken reference may report it under both bullets.
- Alternatively, the reviewer may spend effort deciding which bullet applies.

- The opener's context restriction makes two different failures possible.
- The reviewer may not search beyond references named with explicit paths.
- A reference can fail because its supplied path or name does not exist.
- A reference can also fail because it supplies no path.
  - It merely describes something.
  - The context restriction prohibits the reviewer from searching for it.
- If the author means those two separate failures, the item proposes additions that distinguish them.
  - “References that go nowhere” would be defined as a path or name that does not exist.
  - “References you could not follow” would be defined as something named without an explicit path, where the context rule prevents looking for it.
- If the author instead means one failure category, the solution is to remove the second bullet.
- The recommendation is to retain both bullets and add the distinguishing language.
- The offered responses are Y to approve, N to disapprove, and D to defer.

---

#### Item 8.1 of 8: the assembled version of Question 1

- The first part of item 8 presents the fully assembled Question 1.
- It says the walk's decisions are listed in the minutes as they were made.
- It says that, assuming every item was approved and the three earlier rulings were incorporated, Question 1 has the displayed wording.
- The displayed wording requires the reviewer to restate every document or source text as bullets and sub-bullets.
  - Each sentence gets one bullet that preserves the sentence exactly as written.
  - Each point, action, fact, idea, concept, or claim within that sentence gets one sub-bullet.
  - The sub-bullets follow the original order.
- The displayed wording treats a heading, list item, and table row as a sentence.
- It says a sentence can have several points.
- It forbids combining details or leaving them out.
- It requires each point to be restated in the reviewer's own plain words, with literal precision.
- When a sentence or point does not make sense, the restatement may also fail to make sense.
  - In that case, `???` is appended to the relevant bullet or sub-bullet.
- When the source has a clear omission, the reviewer must record it in a bullet or sub-bullet.
  - That marker begins with `?gap?`.
  - It is followed by a statement of what is absent.
- For frontmatter, prose fields such as descriptions are restated like ordinary sentences.
- Data fields such as a name, IDs, or dates are omitted from the restatement.
- The rewrite should be about twice as long as the source.
- The displayed wording says that the question lets an author determine whether the reviewer understood the author's intended meaning.
  - It therefore directs literal reading rather than an invented coherent meaning.
- The rewrite also helps the author see whether other agents parse the text correctly.

- Any item the user declined remains unchanged in the current file.
- This sub-step asks for no decision.
- The next sub-step asks who will implement the result.

---

#### Item 8.2 of 8: who implements accepted changes

- The second part of item 8 asks who should apply accepted edits.
- It presents two ways to land the edits.
- In the first way, the user pastes the accepted text into Typora.
  - A seat then submits it in a pull request.
  - The document says that was the process for PR #271.
- In the second way, the walk's writer changes the accepted text on the current branch.
  - The writer commits the changes.
  - The writer opens a pull request for the user to inspect as a diff.
- The writer recommends the second way.
  - The edits consist of exact sentences.
  - The branch is current.
  - A diff displays every edit against the merged text.

- The document adds a testing note that it says needs no decision.
- The user should run the resulting prompt through a cell launcher.
  - `scripts/cold-read-codex-cell.py` is one example.
  - `scripts/cold-read-agy-cell.py` is another example.
  - The invocation should use `--cell fast-clarify`.
  - Those launchers read the prompt file from the prompts directory.
- `scripts/cold-read-fast-read.py` is said to use an embedded copy of the previous prompt text.
- A run through that script therefore measures the old prompt.
- Replacing its embedded copy is assigned to the MD-skills seat as task #57.
- The recommendation is that the writer apply accepted changes on this branch and open the pull request.
- The offered responses are Y to approve, N to disapprove, and D to defer.

## Question 2: Where you struggled

1. “Walk document: [fast-clarify-prompt-suggested-changes.md]” — The only stated walk document is absent, so a fresh reader cannot inspect the decisions “listed in the minutes” or verify the claimed state of the assembled text.

2. “The file is [fast-clarify.md on this branch, which is at main]” — “This branch” can mean the branch holding the walk or `main`; the phrase does not establish whether the proposed edits are being considered from a topic branch or from main.

3. “The decisions this walk produced are listed in the minutes as they landed.” — No accessible minutes path is supplied, so the reader cannot know which of the conditional “with every item approved” edits actually landed.

4. “Three things about Question 1 the user already ruled before this walk” — The text names the three rulings but supplies neither their source nor a way to distinguish them from the writer's interpretation if their application is disputed.

5. “8 items.” — The document then labels both “Item 8.1” and “Item 8.2,” making it unclear whether these are two decision items, two parts of one item, or an item count that excludes implementation.

6. “the closing item folds in without asking again” — “The closing item” could mean Item 8.1, which assembles Question 1, or Item 8.2, which asks who applies edits; only the former actually folds in the rulings.

7. “a term or reference one of them settles is settled for all of them” — “Settles” is undefined: it could mean any mention, an explicit definition, a resolvable link, or an authoritative statement, which changes what Question 2 must report.

8. “one bullet per sentence, holding that sentence as written” — This can mean the bullet itself reproduces the sentence verbatim or merely preserves its content; that distinction conflicts materially with the surrounding demand to restate in the reviewer's own words.

9. “a heading, a list item or a table row counts as a sentence” — This does not say how to split a list item or table cell that contains multiple sentences, so the proposed rule can still yield different output structures.

10. “prose fields” and “data fields” — The categories are illustrated but not defined, leaving mixed fields such as a title, label, URL description, or structured multi-line value to the reviewer's judgment.

11. “The project's own terminology reviewer” — The linked prompt is a reviewer instruction, not an identifiable reviewer or authority; calling it “the project's own terminology reviewer” obscures whether it is evidence of a project rule or only analogous wording.

12. “Y to approve, N to disapprove, D to defer.” — The response letters are clear enough individually, but the document never says whether a response must be supplied for every item or how a combined response is formatted.

13. “the branch is current” — Current relative to which ref, commit, or time is unstated, so it does not substantiate the claim that the proposed PR would compare against the intended merged text.

14. “the MD-skills seat's task #57” — Neither the seat nor task #57 is linked or otherwise locatable under the stated minimal-context rule, so the ownership and status of the replacement cannot be checked.

## Question 3: What it does not cover that it implies it should

1. “This walk goes through the changes I suggest to that file, one per item, in file order.” — Item 8 contains both an assembled wording and an implementation decision, while the three pre-walk rulings are incorporated without their own items; the document does not explain how this exception still satisfies one proposed change per item in file order.

2. “If {TARGET_PATH} contains multiple documents, treat these documents as an atomic set” — The proposed resolution covers terms and references settled across documents but not whether Questions 1 and 3 are also evaluated collectively, for example when a definition is split between two documents or an instruction in one depends on another.

3. “a term or reference one of them settles is settled for all of them” — The proposed rule has no conflict case for two documents that define the same term or reference differently, nor does it state whether document order determines a winner.

4. “If a sentence or point does not make sense to you” — The replacement does not say how to handle a sentence that is meaningful overall but has an ambiguous point with two plausible restatements; `???` marks unintelligibility, not an unresolved choice.

5. “A heading, a list item or a table row counts as a sentence.” — The proposed addition does not state how to restate nested list structure, table headers versus data rows, blank rows, or a heading whose content is only organizational.

6. “In frontmatter, restate prose fields ... and skip data fields” — The rule does not cover a field containing both machine-readable data and prose, such as a list of descriptive tags or a multiline value with metadata and instructions.

7. “references that go nowhere - a path or name that does not exist” — The proposed distinction does not cover a path that exists but cannot be read under the context or permissions available to the reviewer.

8. “references you could not follow - named without an explicit path” — The wording does not cover a reference with an explicit path that is syntactically malformed, points outside the available checkout, or identifies several possible files.

9. “With every item approved” — The assembled Question 1 has no stated construction rule for mixed decisions, although each preceding item permits N or D and says declined text remains unchanged.

10. “You paste the accepted text into the file in Typora and have a seat PR it” — The first landing route does not state who selects the seat, reviews the pasted text, or resolves differences between the user's Typora text and the accepted wording.

11. “Or I apply the accepted changes on this branch, which is already at main, commit, and open the PR” — The second route does not resolve how a pull request is opened from a branch described as already at main, or what base and head branches the reader should use.

12. “run it through a cell launcher such as scripts/cold-read-codex-cell.py or scripts/cold-read-agy-cell.py with --cell fast-clarify” — The testing note does not provide the required target, report, tier, or prompt-file arguments, so it does not yield a runnable validation command despite directing the reader to test the result.
