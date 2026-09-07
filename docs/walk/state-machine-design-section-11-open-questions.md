# Walk: three questions the state-machine design leaves to you

The design-to-main state machine turns an approved design into code and tests and submits them to the gate that guards main. Its design holds three questions open that only you can answer. This walk takes each one from a concrete example to a recommendation. 4 items. [The walk document](file:///Users/el/agents/reboot-test/docs/walk/state-machine-design-section-11-open-questions.md).

[The design](file:///Users/el/agents/reboot-test/docs/design-to-main/design-to-main-state-machine-design.md), §11 "Not decided here". This walk answers item 7 of [the round-2 walk](file:///Users/el/agents/reboot-test/docs/walk/state-machine-design-round-2-cold-read-flags.md). The example script, `create-topic-branch`, is the one [the earlier walk today](file:///Users/el/agents/reboot-test/docs/walk/implementation-review-verdicts-and-code-write-counting.md) used: a small script that cuts a topic branch, and refuses if it is not run inside a git checkout.

---

## Item 1.1 of 4: An implementation that is agent-instructions — what it is, and the two rules that meet on it

Most components the machine builds are scripts. Some are agent-instructions: a prompt or MD file that an agent reads and follows. The walk-me-through skill is one, at [.claude/skills/walk-me-through/SKILL.md](file:///Users/el/agents/reboot-test/.claude/skills/walk-me-through/SKILL.md). If that skill went through the machine, the implementor would write the prompt and the reviewer would check it against the contract.

Two of your rules meet on it.

**Rule one: prose handed to a next node is cold-read.** The writer runs the cold-read grid on its draft inside its own node, reads what zero-context reviewers misunderstood, revises, and only then emits. The design, the contract and the test-design get this. The reason is that a reader who was not in the conversation is the reader the prose has to survive.

**Rule two: an implementation is reviewed and run, not cold-read.** The reviewer reads the code against the contract, writes its own tests, runs it, and gives a verdict.

Agent-instructions are both. They are prose, and their reader is an agent that was not in the conversation, which is exactly what the cold read simulates. They are also an implementation with a contract: the contract says what the agent following them must produce, and the reviewer runs them to see whether it does.

The fleet already answers this in practice. Every skill under `.claude/skills/` is cold-read before it lands, and you review it, by the rule in `CLAUDE.md`; the reviewer of the pull request then takes it as settled. And today you split agent-instructions in two, the glossary's word for prompts or MD files that instruct agents: a skill is agent-instructions a person invokes; an agent node's agent-instructions are read only by that agent. Not every node is an agent: the machine has user states and machine states too, and those have no agent-instructions. The design already calls a skill final prose, which by your 2026-09-04 ruling comes to you after its cold read, and an agent node's agent-instructions are pipeline prose, which does not.

No decision yet; the recommendation is in 1.2. Say next.

---

## Item 1.2 of 4: The recommendation

An implementation that is agent-instructions, coverage type `prompt`, is cold-read by its writer inside the implementor node before it is emitted, as every prose writer does, and then reviewed against its contract and run by the reviewer, as every implementation is. A script is not cold-read. The same holds on the test line: a test that is agent-instructions, a test run by a single-purpose agent, is cold-read by the test-implementor before it is emitted, then read by the test reviewer.

Your rider from 1.1: many agent-instructions are forms. The handoff supervisor composes each seat's launch prompt from a template with that seat's handoff filled in; a reviewer agent node's agent-instructions are one text with the component's documents filled in. The cold read of a form reads a filled-in sample, the way its reader will receive it, never the blank form.

Your review of it. You said you will read the instructions to the reviewer on how to prepare its comments, and the instructions to the implementor on how to write, but not the reviewer's comments themselves. So the line is not skill versus agent node. It is standing versus per-run: agent-instructions any agent will follow are final prose and come to you after their cold read, whether they land as a skill or as an agent node's instructions; what an agent writes during one run for another agent, review notes, a could-not, a corrected contract, does not. An implementation that is agent-instructions is standing text, so it comes to you: after the implementation reviewer advances it, a user-review state the same shape as the design's.

The design's §4 sentence today:

> Implementations and tests are reviewed and run, not cold-read. Whether a `prompt`-typed implementation should also be cold-read is open (§11).

Becomes:

> Implementations and tests are reviewed and run. An implementation or test that is agent-instructions, coverage type `prompt`, is also cold-read by its writer inside the writer's node before it is emitted, because its reader is an agent that was not in the conversation. Agent-instructions that are a form, with sections filled in mechanically or per reader, are cold-read as a filled-in sample, as their reader will receive them, never blank. Agent-instructions any agent will follow, a skill or an agent node's instructions, are final prose and reach the user after the reviewer advances them; text one agent writes during a run for another, notes, a could-not, a corrected contract, does not.

Y, N, or D.

---

## Item 2 of 4: Can an implementor say "I wrote nothing"?

Every test the machine writes carries one word saying what kind of thing it is: `script`, `prompt`, or `script-and-prompt`. That word is its coverage type. Tests have a fourth word, `excluded`, which means "no test was written for this requirement," and it must be followed by one of four reasons and a sentence: can't-test, no-test-needed, don't-know-how-to-test, no-test-available. You ruled that on 2026-09-03.

On 2026-09-05 you confirmed that the same word is written on an implementation too: a script, a prompt, or both.

The question here is the fourth word. Can an implementor finish and say `excluded`, meaning "I wrote nothing"? I say no, and this narrows your confirmation by one word. The four reasons are all about tests. "No test needed" says nothing about an implementation. If an implementor truly has nothing to write, then either the design is wrong, and the machine already has a way to say that, a could-not against the design, or the design describes something this machine does not make.

Here is that second case. The branch protection on main is a rule on GitHub: only two accounts may push to main. The [gatekeeper design](file:///Users/el/agents/reboot-test/docs/cross-project/main-gatekeeper-design.md) asked for it, and you applied it by hand on 2026-07-21, in GitHub's settings. There is no file to write, so there is nothing to review, nothing to test, and nothing to land on main. Design-to-main is the wrong tool for it, and the design that asks for it should say "done by hand." If a component needs both a script and a setting, the script goes through the machine and the setting is written into the contract as a precondition: "the branch protection exists," checked by a test or marked unchecked.

The design's §2 today:

> An implementation is what the implementor builds; its coverage type is `script`, `prompt`, `script-and-prompt`, or `excluded` with one of four reasons — `can't-test`, `no-test-needed`, `don't-know-how-to-test`, `no-test-available`.

Becomes:

> An implementation is what the implementor builds; its coverage type is `script`, `prompt`, or `script-and-prompt`. Only a test can be `no-tests`, with one of three reasons and a sentence: `can-not-be-tested`, `do-not-know-how-to-test`, `no-tests-written`. A design that asks for something that is not a file in the repository is done by hand and does not enter the machine.

And §5.2 rule 3 loses its last sentence, "An `excluded` implementation has no contract of this kind (§11)."

Recommendation: adopt. Y, N, or D.

---

## Item 3 of 4: How much a contract may say

The first walk, on 2026-09-03 ([its minutes](file:///Users/el/agents/reboot-test/docs/walk/pr-review-graph-coder-reviewer-originator-loops-minutes.md)), defined the contract as everything a caller can observe without reading the code. The cold-read reviewers said, rightly, that "everything" has no edge: timing, memory, the wording of an error from a dependency, all observable, all unbounded.

Today you said: "I think the contract can mutate without the design mutating as it will need to bring in implementation details that are necessary for testing or full implementation." That sentence is the bound. Its two halves are one: a detail an implementor needs that no caller can observe is, by the design's own rule, implementation and not contract; a detail an implementor needs that a caller can observe is exactly what a tester needs.

`create-topic-branch`. The design promises: "If the working copy is not inside a git checkout, refuse. A refusal is an error." The contract clause: "On refusal, exit status 1; nothing on stdout; stderr names the fact." The exit status, the empty stdout and the stderr line are details the design never mentions. They are in the contract because without them a tester cannot observe the promise. How long the refusal takes is also observable. It is not in the contract, because no promise in the design needs it to be seen.

The test for a clause: delete it, and some promise in the design becomes impossible to observe. If nothing becomes unobservable, the clause does not belong. Two clauses that observe one promise the same way are one clause written twice; keep one.

The design's §5.1 today:

> Everything about a component a caller can observe without reading its code, where a caller is anything that invokes the component or reads what it leaves. Anything you would have to read the source to know is implementation, not contract. Bounding "everything" to what the design promises is open (§11).

Becomes:

> What the design promises its component-consumers, plus the details a tester needs to observe those promises, and nothing else, where a component-consumer is anything that invokes the component or reads what it leaves. Anything you would have to read the source to know is implementation, not contract. A clause belongs if deleting it leaves some promise of the design unobservable.

And the contract's groups `caller-supplies` and `caller-receives` become `component-consumer-supplies` and `component-consumer-receives`; "caller" is struck from the design.

Recommendation: adopt. Y, N, or D.

---

## Item 4 of 4: What this walk settled

- An implementation or test that is agent-instructions, coverage type `prompt`, is cold-read by its writer inside the writer's node, then reviewed like any implementation; standing agent-instructions, a skill or an agent node's, reach you after the reviewer advances them; per-run text between agents does not (item 1).
- An implementation is a script, a prompt, or both. Only a test can be `no-tests`, your new name for `excluded`, with the reasons `can-not-be-tested`, `do-not-know-how-to-test`, `no-tests-written`; a design that asks for something that is not a file in the repository is done by hand and never enters the machine (item 2).
- A contract states what the design promises its component-consumers plus the details a tester needs to observe those promises, and nothing else. "Caller" becomes "component-consumer" throughout, including the two contract groups; one design still describes one component (item 3).

The three questions are removed from the design's §11 in the post-walk commit. The round-2 walk resumes at its item 8.

The decisions were items 1 to 3; this item has none. Say next to close.
