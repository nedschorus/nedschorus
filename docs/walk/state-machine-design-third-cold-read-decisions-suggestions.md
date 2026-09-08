<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=70 tokens=32027 target=docs/walk/state-machine-design-third-cold-read-decisions-draft.md -->

# Third cold read — suggestions

## 1. What it says

### Opening

This walk says a third cold read found and fixed defects in the design-to-main state machine, and presents seven decisions for the user across eight items. It links the design, its glossary, and the machine-local dispositions record; it has no YAML frontmatter.

### Item 1 of 8: What the read found, and what I fixed without asking

Six agents produced roughly 500 findings, reduced to about 60 distinct findings, mostly contradictions introduced while applying the user's rulings; those contradictions were fixed in a second commit. The fixes clarify each state's actor, define the test-design and the placement of `no-tests`, count the third failed write rather than the third emitted write, correct redesign counting and counter resets, give the user's contract check three exits at item 5, sequence the first contract form check before design review, and give agents topic-branch worktrees without the other work-stream's files. Sixteen findings were left unapplied because prior rulings already decided them, and this item asks for no decision.

### Item 2 of 8: Your glossary rule applied to the document's own words

The user's rule against redefining bare common engineering words required the document to replace eight such words with listed hyphenated phrases. The author rejected longer proposed names because the shorter replacements neither collide nor remain ambiguous, and recommends confirmation of the table by Y, N, or D.

### Item 3 of 8: The short words a state emits

The state-exit words `advance`, `emitted`, `discuss`, `stop`, `resume`, `green`, and `red` are kept short because they appear with a state name in topic-branch commit trailers, making the pair searchable and tables readable. The recommendation is to keep them, with Y, N, or D as the requested response.

### Item 4 of 8: Two words that were not yours, and one that is

`unreliable-test` was changed to `flaky-test`, and `over-its-head` to `escalate-to-user`, to use the standard term and to name the disposition rather than the arbitrator's inadequacy. The remaining choice is whether the design keeps the user's `arbitrator` and the fleet glossary changes its existing `adjudicator` entry, or the design adopts `adjudicator`; the recommendation is the former.

### Item 5 of 8: Your contract check, settled

After the original component-contract and its first revision have each failed review, the machine shows the user both versions and both reviewers' notes before writing another version. The user can advance the first revision despite review, discuss so a fresh agent writes from the ruling, or open a contract-focused investigation; no third version is written first. The item asks for Y, N, or D.

### Item 6 of 8: A consequence of your standing-versus-per-run rule

Because prompt tests are standing agent-instructions, they now receive `test-acceptance-by-user` after their agent check, matching implementation-side standing instructions; script tests do not reach the user. The recommendation is to retain that outcome, with Y, N, or D as the response.

### Item 7 of 8: Where the run's files live on the branch

Implementation and test files now live at the paths named by the design, while each run's records live under `design-to-main-runs/<component>/` and include its listed documents and records. The unresolved choice is whether durable design and test-design prose remains there after gate acceptance or moves under `docs/`; the item recommends the layout and asks the user to provide the landing place if known.

### Item 8 of 8: What this walk settled, and the next step

This item summarizes the terminology, exit words, names, contract check, prompt-test review, and branch-layout outcomes, while retaining the landing place for durable prose as the user's choice. It says the next step is the ruled pull request, containing the named design, glossary, pointer entries, and four walk files for merge-lane review, while record directories remain on this machine; no decision is requested.

## 2. Where you stumbled

1. [question] "Your ruling was that a contract reaches you when it has \"failed review twice,\"" What ruling is this referring to, and where can a reader with only this walk inspect it?

2. [question] "Y, N, or D." What does `D` mean in these requested responses?

3. [question] "The contract you discussed says exit 0 on refusal; the reviewer rejects it." Which contract is "you discussed," and what does its exit 0 establish in this sequence?

4. [question] "the fleet glossary already has **adjudicator**" Where is the fleet glossary entry that defines `adjudicator`?

5. [question] "merge-lane is routing" What is merge-lane, and what does it mean for it to route the gate-payload question?

6. [question] "Next: the pull request, as you ruled in the round-2 walk's item 8." Which round-2 walk and item 8 supply this rule?

## 3. What it does not cover

1. [rule-conflict] "What this walk settled" and "Recommendation: confirm the table. Y, N, or D." Is each listed recommendation already settled, or does it still require the requested response before the pull request proceeds?

2. [no-rule] "No decision. Say next." What happens when the reader says `next`, and what must the reader do if they disagree with an earlier applied fix rather than one of the listed recommendations?

3. [no-rule] "where durable prose lands after acceptance is yours" What happens if the user confirms the layout but does not choose a landing place before the gate accepts the component?

