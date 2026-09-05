<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=84 tokens=24607 target=docs/walk/pr-review-graph-coder-reviewer-originator-loops-draft.md -->

# Review of the PR-review graph draft

## 1. What it says

### Opening

The document defines the PR-review graph as the hand-off process that takes a component design through coding and review to merge, and says it has seven items.

### Item 1 of 7: The nodes and the artifacts

The process has an originator who alone changes design promises, a coder, a separately designed-test coder, code and test reviewers who apply the stated review scope, and a merge-lane seat. Because each work round uses a fresh agent, files carry state: a serious design-issues file stops the coder and goes to the originator, a nits file travels with code, and reviewer findings return to the coder unless they change the promise; the 238 design is the running example.

### Item 2 of 7: The coder's first move — stop or continue

Before coding, the coder stops only when the design promises an unbuildable or wrong caller-visible behavior, records a failure scenario in an issues file, and sends it to the originator. All lesser defects are nits recorded with intentional deviations while coding continues; the cited 238 fast-forward assumption is an example of the stopping condition.

### Item 3 of 7: The two loops and their order

Code and test work each have a review-and-fix loop, and a loop ends when a review round has no finding with a failure scenario that changes code or tests. The coder's stop check comes first, then coder and test coder work in parallel, then code review runs the tests; after its first round, code review must substantiate a finding with a failing test or an unreachable-by-test manual reproduction, using a passing suite and failing red witness.

### Item 4 of 7: What the reviewer receives

The reviewer receives the design, code, and coder's nits file, never an issues file because that means no code exists. Giving the nits file avoids nonproductive reports of deliberate, non-failing deviations while retaining enough independent review for defects.

### Item 5.1 of 7: The reviewer's back edges — contract and implementation findings

A contract finding changes the caller promise, goes to the originator, restarts the process with both designs reopened, and earns one zero-context cold read of the revised design. An implementation finding changes only how the existing promise is met, so only code changes and the open loop receives another round because tests must run again.

### Item 5.2 of 7: The reviewer's back edges — prose findings and nits

Design-prose findings are not reported and await post-landing maintenance based on decisions rather than code. Nits have no observable effect and may be fixed or left without holding a loop; every finding with a failure scenario must be treated as more than a nit, with uncertain cases labelled upward.

### Item 6 of 7: Who arbitrates, and the two guards

When coder and reviewer disagree whether a finding changes the contract or only implementation, the originator decides after each supplies a paragraph and failure scenario. After the first round, a reviewer must demonstrate a real defect by test or manual reproduction, and a design gets no new cold read unless its contract changes.

### Item 7 of 7: Summary and the next step

If approved, the document adopts the stop test, ordering, reviewer inputs, four finding routes, originator arbitration, and the two guards. It then calls for a separate graph design with exact files and hand-offs, a cold read of it, its first use on the 238 build, and forwarding the labelling rule to issue 210's reviewer instructions.

## 2. Where you stumbled

1. [question] "Who reads that cold read is being measured by a separate campaign and is not decided here." Who performs the required cold read before the restarted loop can proceed?

2. [question] "The reviewer's findings, which go back to the coder, or to the originator when they change the design's promise." What exact finding artifact and hand-off identify its author, recipient, and the component it concerns?

3. [question] "From round two on, the run is the round." Does this guard apply to the test reviewer as well as the code reviewer, given item 3 names only the code reviewer?

4. [question] "A prose finding" What distinguishes a prose finding from a contract finding when ambiguous design wording changes a reader's understanding of the caller promise?

5. [question] "the author fixes it or leaves it" Which author has this choice when a reviewer, rather than the code or test author, identifies a nit?

6. [question] "the revised design earns one cold read" What constitutes completion of that one cold read when it produces a finding?

7. [two-readings] "The design is frozen from the second round on" This can mean no design text may change after round one, or only that prose-only changes are frozen; the preceding contract route permits a revised design later.

8. [question] "Y, N, or D." What does D mean and what action or decision rule follows each response?

## 3. What it does not cover

1. [no-rule] "The coder stops only on a contract defect with a failure scenario; everything else is noted and the coder continues." What does the coder do when the design omits a behavior needed to implement or test the component, so there is no stated promise to test but proceeding requires choosing one?

2. [no-rule] "There are two loops." When and how does the test-review loop run after the coder and test coder work in parallel, and how does it interact with the stated code-review sequence?

3. [no-rule] "The reviewer receives the design, the code, and the nits file." What does the test reviewer receive, including any test-side equivalent of the coder's nits file?

4. [rule-conflict] "implementation to the code only" and "The test-design-test-code loop" Where does a test-review finding that changes test implementation but not the contract go, when the implementation edge is specified as code only?

5. [no-rule] "the suite passes and a deliberately broken copy of the code, the red witness, fails it." What happens in a second-or-later code-review round if the required tests or red witness do not exist, cannot run, or do not establish the claimed behavior?

6. [no-rule] "the originator arbitrates." What happens to the loop when the originator does not rule, or rules that the finding is neither contract nor implementation?

7. [no-rule] "prose not reported and caught up in maintenance from decisions" Who performs that maintenance and what event or record determines when the frozen prose is caught up?

8. [no-rule] "with these decisions folded in and the file names and hand-offs made exact" What is the decision path if this draft is deferred or disapproved, given the 238 build is waiting on the process?
