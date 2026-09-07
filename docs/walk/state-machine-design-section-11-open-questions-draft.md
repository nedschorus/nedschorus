# Walk: three questions the state-machine design leaves to you

The design-to-main state machine turns an approved design into code and tests and submits them to the gate that guards main. Its design holds three questions open that only you can answer. This walk takes each one from a concrete example to a recommendation. 4 items.

[The design](file:///Users/el/agents/reboot-test/docs/cross-project/design-to-main-state-machine-design.md), §11 "Not decided here". This walk answers item 7 of [the round-2 walk](file:///Users/el/agents/reboot-test/docs/walk/state-machine-design-round-2-cold-read-flags.md).

---

## Item 1 of 4: A prompt that is the product — is it cold-read as well as reviewed?

Most components the machine builds are scripts. Some are prompts: a file of instructions that an agent reads and follows. The walk-me-through skill is one, at [.claude/skills/walk-me-through/SKILL.md](file:///Users/el/agents/reboot-test/.claude/skills/walk-me-through/SKILL.md). If that skill went through the machine, the implementor would write the prompt and the reviewer would check it against the contract.

Two of your rules meet on it.

**Rule one: prose handed to a next node is cold-read.** The writer runs the cold-read grid on its draft inside its own node, reads what zero-context reviewers misunderstood, revises, and only then emits. The design, the contract and the test-design get this. The reason is that a reader who was not in the conversation is the reader the prose has to survive.

**Rule two: an implementation is reviewed and run, not cold-read.** The reviewer reads the code against the contract, writes its own tests, runs it, and gives a verdict.

A prompt is both. It is prose, and its reader is an agent that was not in the conversation, which is exactly what the cold read simulates. It is also an implementation with a contract: the contract says what the agent running the prompt must produce, and the reviewer runs the prompt to see whether it does.

The fleet already answers this in practice. Every skill under `.claude/skills/` is cold-read before it lands, by the rule in `CLAUDE.md`, and the reviewer of the pull request takes it as settled after that.

Recommendation: both. The implementor cold-reads a prompt-typed implementation inside its node before emitting, as every prose writer does, and the reviewer then reviews it against the contract and runs it. A script is not cold-read. The design's §4 says so. Y, N, or D.

---

## Item 2 of 4: An implementation that is nothing — does `excluded` belong on the implementor's exit?

On 2026-09-03 you ruled the vocabulary for tests. Each test-requirement is covered by a test script, a test prompt, both, or it is excluded, for one of four reasons: can't-test, no-test-needed, don't-know-how-to-test, no-test-available. Each reason carries a sentence saying why.

On 2026-09-05 you confirmed that the same field applies to what an implementor builds, not only to tests. So the design says an implementation's type is `script`, `prompt`, `script-and-prompt`, or `excluded` with one of those reasons.

The first three make sense for an implementation. The fourth does not, and the reasons show it. An implementor that reports "no-test-needed" has said nothing about what it built. "can't-test" and "no-test-available" describe the tests. "don't-know-how-to-test" is an open question for you, which the machine already carries as a could-not against the design.

The case that looks like an excluded implementation is a component with no artifact in the repository. The branch protection on main is one: the [gatekeeper design](file:///Users/el/agents/reboot-test/docs/cross-project/main-gatekeeper-design.md) records it as applied on 2026-07-21, and it is a GitHub setting, not a file. Nothing about it can land on main, so it never enters this machine. It is done by hand, and the design that asks for it says so.

Recommendation: an implementation's type is `script`, `prompt`, or `script-and-prompt`. `excluded` and its four reasons stay on tests, where you ruled them. An implementor never exits `excluded`; a design whose component has no artifact does not enter the machine. Y, N, or D.

---

## Item 3 of 4: How much a contract may say

The first walk defined the contract as everything a caller can observe without reading the code. The cold-read reviewers said, rightly, that "everything" has no edge: timing, memory, the wording of an error from a dependency, all observable, all unbounded.

Today you said the contract is the design with more detail, and that it brings in the implementation details needed for testing or full implementation. That is the bound.

The script `create-topic-branch`. The design promises: "If the working copy is not inside a git checkout, refuse. A refusal is an error." The contract clause: "On refusal, exit status 1; nothing on stdout; stderr names the fact." The exit status, the empty stdout and the stderr line are details the design never mentions. They are in the contract because without them a tester cannot observe the promise. How long the refusal takes is also observable. It is not in the contract, because no promise in the design needs it to be seen.

The test for a clause is this: delete it, and some promise in the design becomes impossible to observe. If nothing becomes unobservable, the clause does not belong.

Recommendation: the contract states what the design promises, plus the details a tester needs to observe those promises, and nothing else. This replaces "everything a caller can observe" in the design's §5.1. Y, N, or D.

---

## Item 4 of 4: What this walk settled

- A prompt-typed implementation is cold-read by its writer inside the implementor node, then reviewed against its contract and run, like any implementation (item 1).
- An implementation is a script, a prompt, or both. `excluded` stays a test-side value; a component with no artifact in the repository never enters the machine (item 2).
- A contract states what the design promises plus the details a tester needs to observe those promises, and nothing else (item 3).

These three leave the design's §11. The round-2 walk resumes at its item 8.

No decision. Say next to close.
