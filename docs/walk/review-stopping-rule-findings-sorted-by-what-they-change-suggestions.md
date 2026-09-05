<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=59 tokens=14535 target=docs/walk/review-stopping-rule-findings-sorted-by-what-they-change-draft.md -->

# Review of the stopping-rule walk

## 1. What it says

### Title and opening

The walk proposes a stopping rule for review loops, classifies four finding types, adds two safeguards, and says its evidence justifies the proposal. It contains seven items.

### Item 1 of 7: The problem the rule solves — reviews that never end

A review loop repeatedly reviews and fixes a change, but prose-only review can continue indefinitely because each fix is new prose with further possible defects. Code and tests have a pass/fail oracle, so the proposed stopping rule relies on that difference; this item makes no decision.

### Item 2 of 7: The rule itself

A review loop ends when a round has no finding requiring a code or test-line change, irrespective of the finding's effort, importance, commentary volume, or document movement. The item recommends adopting that rule.

### Item 3 of 7: A contract finding reopens both designs

A contract finding changes externally promised behavior and therefore changes both the code and test designs, restarts the loop from the top, and warrants a new cold read of the design. The cited fast-forward merge behavior illustrates a promised safety property that did not hold; the item recommends this treatment.

### Item 4 of 7: An implementation finding touches the code and nothing else

An implementation finding changes the way an unchanged contract is fulfilled, so only code changes and neither design changes. It keeps review open for another round because code changed and tests must run again; the item recommends this treatment.

### Item 5 of 7: A prose finding does not enter the loop

A prose finding changes a design's wording but no code or test, so it is not reported in review and the design remains frozen after round one. Maintenance later updates the design from decisions rather than observed code behavior; the item recommends this approach.

### Item 6 of 7: A nit changes code but nothing observable — and never holds the loop open alone

A nit is a correct but unobservable improvement with no failure scenario, not merely a small defect; any observable difference makes it a defect instead. Nits may be fixed alongside real findings but a nit-only round is clean and does not itself prolong review; the item recommends that rule and adding its labelling guard to a future reviewer-instructions file.

### Item 7 of 7: The two guards, and the summary

After round one, review is to rely on a passing suite and a red witness that fails rather than further general commentary; untestable findings are treated as prose for maintenance. A design receives no new cold read unless its mechanism changes, and the item says three observed rounds support stopping once findings become prose; it recommends adopting both guards and, if approved, recording the decisions and filing the proposed rider.

## 2. Where you stumbled

1. [question] "the two guards that keep it honest" — What do the two guards prevent, and what makes them sufficient to do so?

2. [question] "the design for the topic-branch script" — Which design document is the reader to treat as the code design, and which as the test design throughout this walk?

3. [question] "the seat's branch carried stray commits" — What is a seat and how does a reader determine which branch belongs to it?

4. [question] "fresh cold read" — What work does a cold read consist of, who performs it, and what completes it?

5. [question] "the freeze-then-retrofit shape you ruled with the merge-lane seat today" — What prior ruling establishes this shape and what is its applicable procedure?

6. [question] "a red witness turn red" — What is a red witness and how is the reader to produce or evaluate one?

7. [question] "the captures land in this walk's minutes" — What are the captures and minutes, and where must they be recorded?

8. [question] "`pr-reviewer-instructions.md`" — Where is this file located or how is a reader to identify it when issue 210 creates it?

9. [question] "Y to approve, N to disapprove, D to defer" — To whom and by what mechanism is the reader expected to send this decision?

## 3. What it does not cover

1. [rule-conflict] "a review round ends the loop when it produces no finding that changes a line of code or a line of test" / "A round that produces only nits is a clean round" — Which rule governs a round containing only nits that require code-line changes?

2. [rule-conflict] "No fresh cold read of a design unless the mechanism changes" / "A contract finding earns one. Nothing else does" — Does every contract finding necessarily change the mechanism and earn a cold read, or can a contract finding leave the mechanism unchanged?

3. [no-rule] "If it cannot be made to fail a test, it is prose" — How should a reviewer classify a real, observable failure that cannot be reproduced in an automated test?

4. [no-rule] "the suite pass[es], and ... the red witness turn[s] red" — What is the rule when the suite passes but the required witness cannot run, is flaky, or gives an inconclusive result?

5. [no-rule] "it is fixed in the round it is found only when that round has real findings being fixed anyway" — What happens to a nit reported with real findings when those real findings are rejected, deferred, or otherwise not fixed in that round?

6. [no-rule] "a finding that changes a line of code or a line of test" — How is a finding classified when it changes review-relevant executable behavior outside a code or test line, such as test execution configuration or a command invocation embedded in prose?
