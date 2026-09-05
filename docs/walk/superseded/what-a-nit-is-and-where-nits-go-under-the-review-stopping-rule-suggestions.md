<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=58 tokens=17515 target=docs/walk/what-a-nit-is-and-where-nits-go-under-the-review-stopping-rule-draft.md -->

# Review suggestions: what a nit is, and where nits go under the review stopping rule

## 1. What it says

### Item 1 of 4: What a nit is

A nit is a correct review observation that does not affect whether the change works, so leaving it forever produces no observable difference for callers, tests, or users. It is the lowest severity class: unlike BLOCKER, MAJOR, and MINOR, it names a case in which nothing goes wrong.

### Item 2 of 4: What a nit is not — the two things it gets confused with

A small defect is not a nit even if it is tiny, because it creates an observable difference; a prose finding on a frozen design document is also not a nit, because changing it creates new prose that can itself be defective. The three categories are therefore nits with no observable effect, small observable defects, and frozen-document prose findings.

### Item 3 of 4: Where each one goes under the stopping rule

A review loop ends when a round finds nothing that changes code or tests: small defects are fixed and hold it open, while frozen-document prose findings are deferred to weekly maintenance. Nits are fixed only alongside other real fixes; nits alone do not hold the loop open and may be handled by the author or maintenance, which the text recommends adopting.

### Item 4 of 4: What a reviewer has to do for this to work

Reviewers must not call an uncertain possible defect a nit: any failure scenario makes the finding a MINOR or worse, regardless of fix size, and uncertainty is resolved by labelling upward. Over-labelling a true nit is presented as low-cost, whereas under-labelling a defect risks a passing suite with a wrong result; the text recommends adding this rule to reviewer instructions when issue 210 next changes them.

## 2. Where you stumbled

1. [question] "It is logged for the weekly maintenance pass and not fixed during review." Does this logging rule override the referenced `CLAUDE.md` instruction that findings about all `docs/` prose are not reported at all?

2. [question] "The document is frozen from round two on" What makes a document frozen, and which review round is round two when the document is encountered by a zero-context reviewer?

3. [question] "the weekly maintenance pass" What is the maintenance pass, and where or how is a deferred prose finding logged for it?

4. [question] "when [issue 210, the review-scope rule] ... next edits them" Which reviewer instructions does issue 210 govern, and how can a reader determine when that issue next edits them?

## 3. What it does not cover

1. [no-rule] "**A small defect changes a line of code.**" What should a reviewer do with a real, observable defect whose correction changes only a test and no line of code?

2. [rule-conflict] "It is logged for the weekly maintenance pass and not fixed during review." When a frozen-document prose finding is found, which rule wins between this instruction and the referenced `CLAUDE.md` instruction to report nothing at all about `docs/` prose?

3. [no-rule] "It is fixed by the author at their discretion, or it rides to maintenance" Who decides between those two destinations for a nit-only clean round, and what action records that decision?

4. [no-rule] "A nit is fixed in the round it is found **if and only if the round has other, real findings that are being fixed anyway**." What happens if fixing a nit or the other findings creates a new finding within that same review round?
