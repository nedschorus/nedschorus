# Walk: what the code reviewer can find, where each finding goes, and what gets counted

One script goes through the design-to-main machine. This walk follows it from the design to the code review, through each thing the reviewer can find, and shows what is counted and when you are called. 6 items.

[The design this walk explains](file:///Users/el/agents/reboot-test/docs/cross-project/design-to-main-state-machine-design.md), §3, §6 and §7.

---

## Item 1 of 6: The component, and the three documents the reviewer holds

The component is a small script, `create-topic-branch`. It has three documents above it.

**The design.** English, written by you with an agent, approved by you. One sentence of it matters here: "If the working copy is not inside a git checkout, refuse. A refusal is an error."

**The contract.** Derived from the design by an agent, the contract writer. It turns each promise into a numbered, testable clause. The clause that matters: `caller-receives-2`: "On refusal, exit status 1; nothing on stdout; stderr names the fact."

**The code.** Written by an agent, the implementor, from the design and the contract together. The implementor never sees the tests.

Then the code reviewer runs. It is a fresh agent. It receives exactly three things: the design, the contract, and the code. It does not receive the test suite or the suite's result, because you ruled that a reviewer handed the project's tests tries less hard to write its own.

Its job is one question with three possible answers: does the code do what the contract promises, and does the contract promise what the design says?

No decision. Say next.

---

## Item 2 of 6: The reviewer's four verdicts, and the one thing it never says

The reviewer reads the code and runs it. It writes its own small tests — for our script, it runs it outside a git checkout and looks at the exit status. Then it gives exactly one verdict:

- **Advance.** The code does what the contract says and the contract says what the design says. The work moves on.
- **Reject the code.** The code does not do what the contract promises. Example: the contract says exit 1 on refusal; the script exits 0. The code goes back to a fresh implementor with the reviewer's notes.
- **Reject the contract.** The code does what the contract says, but the contract does not say what the design says. Example: the contract says "exit 0 on refusal"; the design says a refusal is an error. The code is correct to its contract; the contract is wrong. It goes back to a fresh contract writer.
- **Reject the design.** The design itself has a defect — a promise that cannot be kept. That comes to you, through the arbitrator.

The one thing the reviewer never reports is **wording**: "clause 2 is phrased awkwardly," "this term is used before it is defined." A clause that means the right thing, badly said, is not a finding. A clause that promises the wrong thing is.

So the reviewer does complain about the contract, and often. It is the second verdict.

No decision. Say next.

---

## Item 3 of 6: Verdict two, traced: the code is wrong

Contract `caller-receives-2` says exit 1 on refusal. The implementor's script exits 0. The reviewer runs it, sees 0, and writes: "on refusal the script exits 0; `caller-receives-2` requires 1." Verdict: reject the code.

A fresh implementor receives the design, the contract, the old code and those notes, and writes the code again. That is **code write 2**. The reviewer runs again.

This is the loop the machine counts. Every time the implementor finishes writing the code, the machine adds one. You set the limit at **up to three code writes per version of the design**. If the third code write also fails review, the machine does not try a fourth: the arbitrator — the one agent that reads the whole history of the branch — opens an investigation with you, showing the three attempts and what failed each time. You decide: fix the design, fix the contract, or stop.

Nothing here is new; it is your rulings from the previous walk, items 3.1 and 6.8, in one place.

No decision. Say next.

---

## Item 4 of 6: Verdict three, traced: the contract is wrong — and who pays for the rewrite

Now the other case. The contract writer made a mistake: `caller-receives-2` says "exit 0 on refusal." The design says a refusal is an error.

The implementor, working from that contract, writes a script that exits 0 on refusal. **Code write 1.** It matches its contract exactly.

The reviewer reads the design, reads the contract, and sees the contradiction: the contract promises what the design forbids. Verdict: reject the contract. Not the code — the code did what it was told.

A fresh contract writer fixes the clause: "exit 1 on refusal." That is **contract rewrite 1**. It is counted separately from code writes: up to two, then you.

Here is the question the cold read forced. The contract changed, so the script no longer matches it. Someone has to write the code again. Is that **code write 2**, counted against the limit of three, even though the code was not at fault?

The design now says yes, for one reason: it is real work — the code is different afterwards — and a count that hides real work is a fiction. What your rule protects stays protected: contract rewrites that happen *before* any code exists cost no code write at all, because there is nothing to rewrite. And the limit still holds: the second contract rewrite brings you in, so a bad contract can cost at most two code writes before you see it.

Recommendation: count it. Y, N, or D.

---

## Item 5 of 6: When you are called

From the previous walk, as ruled:

- **The design** — you review every version, after its cold read, before anything is built from it. Every rejection of the design comes to you.
- **The test-design** — the same.
- **The contract** — you said, in the previous walk, "I'd rather not" be its gate. So the contract does not come to you routinely. It comes to you when it has been rewritten twice: at that point the contract is the suspect, and you see both versions.

Tonight you said you thought you were in the loop for contracts too. If you want every contract rewrite to come to you, the machine can do that; item 4's bound then becomes one code write, not two, and you will see more contracts.

Recommendation: keep the ruling as it stands — contracts reach you at the second rewrite. Y to keep it, N to see every contract rewrite, or D.

---

## Item 6 of 6: What this walk settled

- The reviewer holds the design, the contract, and the code, and never the suite.
- It gives one of four verdicts: advance, reject the code, reject the contract, reject the design. It never reports wording.
- Code writes are counted, up to three per design version; the third failure brings the arbitrator to you.
- Contract rewrites are counted separately, up to two; a code rewrite forced by a contract change counts as a code write (item 4).
- You are called on every design and test-design, and on the contract's second rewrite unless item 5 changed it.

These replace item 3 of the round-2 walk, which is closed by this one.

No decision. Say next to close.
