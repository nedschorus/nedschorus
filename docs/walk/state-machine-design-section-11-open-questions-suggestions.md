<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=97 tokens=51354 target=docs/walk/state-machine-design-section-11-open-questions-draft.md -->

# 1. What it says

**YAML frontmatter.** This is a walk with four items about three questions that the design leaves open; it identifies the design and the prior round-two walk as its context.

**Opening.** The state machine turns an approved design into code, tests, and a submission to the gate for `main`; this walk presents recommendations on its three open questions.

## Item 1 of 4: A prompt that is the product — is it cold-read as well as reviewed?

Prompt implementations are both prose for an agent without the originating context and implementations governed by a contract, so the prose cold-read rule and implementation review-and-run rule both apply. The document recommends that the implementor cold-read a prompt implementation before emitting it, after which the reviewer reviews it against the contract and runs it; scripts are not cold-read.

## Item 2 of 4: An implementation that is nothing — does `excluded` belong on the implementor's exit?

The four `excluded` reasons describe test coverage rather than an implementation, so they do not describe what an implementor built. The document recommends limiting implementation types to `script`, `prompt`, and `script-and-prompt`, retaining `excluded` for tests, and keeping a component with no repository artifact outside the machine.

## Item 3 of 4: How much a contract may say

The earlier definition of a contract as everything observable has no limit, while the stated newer bound is the design plus details required for testing or implementation. The document recommends including only design promises and the details needed to observe them in tests; a clause belongs only when removing it would make a design promise unobservable.

## Item 4 of 4: What this walk settled

This section restates the three recommendations: cold-read and then review prompt implementations, keep `excluded` on the test side and exclude no-artifact components from the machine, and limit contracts to promises and their necessary observable details. It says these resolve the design’s section 11 questions and that the prior walk resumes at item 8.

# 2. Where you stumbled

1. [question] "No decision. Say next to close." Must the reader rule on the preceding recommendations or merely advance?

2. [question] "These three leave the design's §11." Does “leave” mean that the three questions remain open in §11 or that the recommendations remove them from it?

3. [question] "The script `create-topic-branch`." What is `create-topic-branch`, and where is its definition or contract available to the reader?

4. [question] "The first walk defined the contract" Which walk is “the first walk,” and where is the definition being replaced recorded?

# 3. What it does not cover

1. [no-rule] "The implementor cold-reads a prompt-typed implementation" What rule applies when `test-implementor-node` emits a prompt-typed test, given that item 2 says the same coverage-type field applies to tests?

2. [no-rule] "a component with no artifact in the repository never enters the machine" What happens when one component requires both a repository artifact and a non-repository change, such as a repository script together with a GitHub setting?

3. [no-rule] "delete it, and some promise in the design becomes impossible to observe" What happens when two contract clauses provide redundant ways to observe the same design promise, so deleting either one alone leaves the promise observable?
