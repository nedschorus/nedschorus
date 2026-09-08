# Minutes: the fast-clarify prompt — suggested changes

Walk document: docs/walk/fast-clarify-prompt-suggested-changes.md
10 items (8 at opening, re-planned to 10 at item 5), the last in two sub-steps. Opened 2026-09-07.

What this walk is about, for someone who has not read it: the fast-clarify
prompt (.claude/skills/cold-read/prompts/fast-clarify.md) is the instruction
text a reviewer agent gets when the cold-read skill runs its fast tier. The
user rewrote it in Typora and it merged as PR #271 on 2026-09-07. In
conversation before the walk the user asked whether Question 1 of that prompt
was still too vague; the walk presents, one per item, the changes the session
then suggested for the whole file, in file order, and asks who applies them.

Rulings made before the walk, in conversation on 2026-09-07, folded into item
8.1 without a second asking:

- The sentence-level bullet in Question 1 quotes the original sentence word
  for word; the sub-bullets beneath it carry the restatement.
- The gap marker reads "?gap? followed by what is missing".
- Points are restated "in your own plain words" (the user added "plain").

Reviewer run over the draft, 2026-09-07: the walk's draft was read by the
fast-clarify cell at floor tier (gpt-5.6-terra, effort low), which is the
first live run of the user's merged prompt on a real target. Exit 0, 243 s,
47,980 tokens. Its Question 1 came back at roughly double the draft's
length, with the sentence-level bullets paraphrased rather than quoted, since
the verbatim rule is not yet in the file. Two of its stumbles changed the
walk: "settles" in item 1's proposed clause was undefined and became "defines
or covers"; "holding that sentence as written" in item 8.1 could be read as
content-preserving and became "quoting that sentence word for word". Report:
docs/walk/fast-clarify-prompt-suggested-changes-suggestions.md.

## Item 1 — what "atomic set" means across files

processed 2026-09-07 → revised. The session proposed settling the multi-document
case with the clause "what one of them defines or covers counts for all of
them"; the user called that "not great" and gave the rule in his own words:
treat the documents like multiple chapters in a book, consistent amongst
themselves, any one able to define or explain parts the others rely on;
repetition is fine, gaps or inconsistencies are not. Applied to the opener of
.claude/skills/cold-read/prompts/fast-clarify.md on this branch (uncommitted
until item 8.2 decides who lands the changes) as: "If {TARGET_PATH} contains multiple documents, treat them like chapters of one book: any one of them can define or explain what the others rely on, and they should be consistent amongst themselves; repetition is fine, gaps or inconsistencies are not. Read all of them, then answer the 3 questions for each document in the report."
The reading this settles: a term defined in one file of the set is defined for
all of them, and a rule stated in one file fills a gap in another.

## Item 2 — the ??? marker goes on the bullet or the sub-bullet

processed 2026-09-07 → accepted ("y"). The ??? rule in Question 1 now covers a
sentence or a point and puts the marker on the bullet or sub-bullet concerned;
the missing "of" is fixed. Applied to the file on this branch: "If a sentence or point does not make sense to you, your restatement may also not make sense, in which case add ??? to the end of that bullet or sub-bullet."

## Item 3 — "section-question" becomes "question"

processed 2026-09-07 → accepted ("y"). The coined term "section-question" in
Question 1's closing sentence is replaced by "question". Applied to the file on
this branch.

## Item 4 — a heading or a table row counts as a sentence

processed 2026-09-07 → accepted ("y"). Added to Question 1 after its first
sentence: "A heading or a table row counts as a sentence; a list item is split
into its sentences like any paragraph." So headings and table rows each get a
bullet, and a multi-sentence list item gets one bullet per sentence. Applied to
the file on this branch.

## Item 5 — frontmatter: restate prose fields, skip data fields

processed 2026-09-07 → accepted ("y"). Added to Question 1 after the gap rule:
"In frontmatter, restate prose fields such as a description like any other
sentences, and skip data fields such as a name, ids or dates." Applied to the
file on this branch.

Rider the user raised with the approval: the restatement (verbatim sentence
plus sub-bullets) is bloating the report files. He asked whether to add a note
about being succinct ("plain and succinct"), whether an agent reproducing a
sentence costs as many write tokens, and whether "make a copy, then add their
bullets after each sentence" would be simpler and faster.

RE-PLAN: the rider became two decision items inserted in file order, so the
walk grew from 8 items to 10. Old items 6, 7, 8.1, 8.2 are now 8, 9, 10.1,
10.2. New item 6: succinct sub-bullets. New item 7: a short anchor (the
sentence's first few words) in place of the verbatim sentence bullet ruled
earlier today.

Item 5 revised at item 6 (2026-09-07): the user said "skip" for frontmatter
data fields might confuse a reader and that those fields should simply get no
bullets. Sentence replaced on this branch with: "In frontmatter, a data field
such as a name, ids or dates gets no bullets; a prose field such as a
description is treated like any other sentence."

## Item 6 — succinct sub-bullets

presented 2026-09-07 — open. The user did not rule on "succinct"; he corrected
the session's reading of his scheme: a script copies the document, and the
reviewer only inserts "meaning" bullets after each sentence; there are no
sub-bullets, because the copied sentence is the top level. The session's
answer: the copy by itself saves no write tokens and no file size against the
verbatim-quote ruling (copied source + points is the same two layers), and
inserting per sentence costs one tool call per sentence; what shrinks the
report is short bullets (this item) and an anchor in place of the full
sentence (item 7). What the copy does buy: a simpler instruction and source
text the system can verify unchanged. Item 7 to be re-planned as the choice
of scheme.

Follow-up 2026-09-07: the user asked how copy-then-insert could cost a tool
round trip per sentence and what is most token-efficient. Answer given: the
model cannot point at a sentence; every insertion is typed through Edit (anchor
twice plus bullets, one call per sentence) or Write (the whole file), so the
copy saves nothing; the cheap path is the model writing only a locator (the
sentence's first few words) plus bullets, spliced into a copy by a script,
roughly half the output of the verbatim scheme (about 45 vs 80 vs 100 tokens
per 30-word sentence with three bullets, for locator / full write / edit).

processed 2026-09-07 → accepted ("add succinct"). Applied to the file on this
branch together with the pre-walk "plain" ruling: "Restate each point in your
own plain, succinct words, literally and precisely."

## Item 7 — which scheme Question 1 follows (re-planned; two sub-steps)

presented 2026-09-07 — awaiting the user's ruling. Choices: A verbatim quote by
the reviewer (ruled earlier today), B copy-and-insert (the user's scheme), C
locator plus bullets spliced by a script (recommended).

Discussion 2026-09-07: the user asked whether the locator is a line number and
whether it is needed at all; answer: the first few words of the sentence, needed
so the splice knows which sentence a block belongs under, since counting drifts
when the model and the script split sentences differently. The user then ruled
the system is all Claude and to go with whichever locator is best plus a simple
python script that complains when it cannot match. Session's design, recorded
for the plumbing (his system, not this file): anchor = first four words, exactly
as written; the script normalizes markdown markers, whitespace and case, searches
forward only from the previous match, and needs no sentence splitter because
each block's anchor marks a sentence start and the next anchor its end; an anchor
not found is reported with its text and the last good position and the block is
appended under a flag; a skipped sentence shows as one block landing after two
sentences.

processed 2026-09-07 → accepted with one revision ("how about ?nonsense?
instead of ??? otherwise approved"). Scheme C adopted. Question 1 replaced in
full on this branch with the 7.2 text, marker ?nonsense? in place of ???. Item
2's marker ruling is thereby superseded: the marker is ?nonsense?, placed on the
anchor line or the bullet concerned. The size sentence now reads "Your bullets,
taken together, should be roughly the length of the original."

## Item 8 — a doubled "and" in Question 2

processed 2026-09-07 → accepted, with a standing ruling: "you can fix any nit
or typo without asking me. I only need to review substantial edits or
changes." The doubled "and" is fixed; in the same pass trailing whitespace
and the run of blank lines before the delivery paragraph were removed.

## Item 9 — Question 2's two reference bullets

processed 2026-09-07 → revised and accepted ("yes two"). Two cases, the first
in the user's words. Applied on this branch:
"* references that do not resolve - the file does not exist at the path stated"
"* references you could not follow - no explicit path is given, so the context
rule above forbids looking for it"

## Item 10.1 — Question 1 as it now stands (read-back, no decision)

processed 2026-09-07 → next ("y"). The full Question 1 text, as applied on this
branch, was read back; it is the 7.2 text with ?nonsense?.

## Item 10.2 — who lands the changes

processed 2026-09-07 → accepted ("y"): the session commits the applied
changes on this branch and opens the PR. Done: PR #274,
https://github.com/nedschorus/nedschorus/pull/274, commit 1dbf90b. The user
added that the merge-lane agent reviews it, not him.

Rider raised with it: "we need to switch to gemini 3.8 medium or normal (not
low or high). Not sure the exact command - you should test/check." Checked:
`agy models` lists gemini-3.8-flash-low, -medium and -high; "normal" is
medium. Verified command, run on the new fast-clarify.md itself: 
scripts/cold-read-agy-cell.py --cell fast-clarify --tier fast --model
gemini-3.8-flash-medium --effort medium --target <document> --report <report>
Result: exit 0, 61 s, report 2,097 words for a ~700-word target; Question 1
followed the anchor scheme exactly (four-word anchors, bullets beneath), and
its bullets came to about twice the source rather than "roughly the length",
a first data point on the size sentence. The anchor for a heading carried its
"## " marker, so the splice script must normalize markers as designed.

Open tasks from the rider, each a separate topic and PR, not this one:
- scripts/cold-read-agy-cell.py pins the fast tier at gemini-3.8-flash-low
  (user-ruled earlier on 2026-09-07); the user's ruling in this walk moves it to
  medium. Code and its test (cold-read-agy-cell-test.py expects effort=low).
- .claude/skills/walk-me-through/SKILL.md still names the codex launcher with
  gpt-5.6-terra at low as the walk's reviewer command; it should name the fast
  tier on the Antigravity launcher.
- scripts/cold-read-fast-read.py's embedded copy of the old prompt: the
  MD-skills seat's task #57, unchanged by this walk.

## Closing

Walk complete 2026-09-07. All ten items ruled; nothing deferred. Standing ruling
recorded at item 8: nits and typos are fixed without asking, only substantial
edits go to the user.
