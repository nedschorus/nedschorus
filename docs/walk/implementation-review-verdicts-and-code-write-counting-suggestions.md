<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=87 tokens=31678 target=docs/walk/implementation-review-verdicts-and-code-write-counting-draft.md -->

## 1. What it says

### Item 1 of 6: The component, and the three documents the reviewer holds

The walk concerns a small `create-topic-branch` script whose design requires refusal outside a git checkout and treats refusal as an error. An agent derives a numbered contract from that design, an implementor writes code from both without seeing tests, and a fresh reviewer receives only those three artifacts to decide whether code matches contract and contract matches design.

### Item 2 of 6: The reviewer's four verdicts, and the one thing it never says

The reviewer runs its own tests and issues exactly one of advance, reject the code, reject the contract, or reject the design, with each rejection routed to the indicated fresh writer or to the user through the arbitrator. It reports substantive mismatches but never reports wording that still conveys the correct meaning.

### Item 3 of 6: Verdict two, traced: the code is wrong

When code violates the contract, the reviewer rejects the code and a fresh implementor writes it again, which is another code write. The machine permits at most three code writes for one design version; a third failed review brings the arbitrator and user into an investigation that ends with a design fix, contract fix, or stop decision.

### Item 4 of 6: Verdict three, traced: the contract is wrong — and who pays for the rewrite

When code correctly implements a contract that contradicts the design, the reviewer rejects the contract, a fresh contract writer corrects it, and that rewrite is counted independently. The document recommends counting the consequent code rewrite as a code write because it is real work, while excluding contract corrections made before code exists and limiting contract rewrites to two before the user is involved.

### Item 5 of 6: When you are called

The user reviews every version of the design and test-design, and is not ordinarily a contract gate. Under the existing ruling, the user sees a contract after its second rewrite; the document offers a choice to retain that rule, instead see every rewrite, or select D.

### Item 6 of 6: What this walk settled

The closing list says the reviewer has the design, contract, and code but not the suite; has four possible verdicts and no wording verdict; and counts code writes, contract rewrites, and code rewritten because a contract changed as stated above. It says the user is called for all design and test-design versions and for a contract's second rewrite unless item 5 changes that, replacing item 3 of the closed round-2 walk.

## 2. Where you stumbled

1. [question] “[The design this walk explains](file:///Users/el/agents/reboot-test/docs/cross-project/design-to-main-state-machine-design.md), §3, §6 and §7.” Which document or source defines the cold read, the earlier walks, and the other rulings that this walk invokes but that are not available through this reference?

2. [question] “No decision. Say next.” Who is instructed to say “next,” and what action follows if that instruction is not given?

3. [question] “Nothing here is new; it is your rulings from the previous walk, items 3.1 and 6.8” Where can a reader obtain the previous walk and its numbered rulings?

4. [question] “Recommendation: count it. Y, N, or D.” What does “D” mean?

5. [question] “Tonight you said you thought you were in the loop for contracts too.” What conversation or record establishes the statement addressed as “Tonight” for a reader who has only this walk?

6. [question] “These replace item 3 of the round-2 walk” Which round-2 walk and item 3 are replaced, and where is the replacement record?

7. [question] “a fresh contract writer fixes the clause” and “the contract's second rewrite unless item 5 changed it.” Does a second contract rewrite occur before the user is called, or does reaching the second-rewrite limit call the user instead?

8. [question] “What this walk settled” and “Recommendation: count it. Y, N, or D.” Are the code-write and contract-gate recommendations already settled, or are they awaiting the stated response?

## 3. What it does not cover

1. [rule-conflict] “Reject the code. The code does not do what the contract promises.” and “Reject the contract. The code does what the contract says, but the contract does not say what the design says.” Which verdict applies when the code violates its contract and that contract also contradicts the design?

2. [rule-conflict] “Reject the contract.” and “Reject the design. The design itself has a defect — a promise that cannot be kept.” Which verdict applies when a contract is inconsistent with a design promise that cannot be kept?

3. [no-rule] “The reviewer reads the code and runs it.” What does the reviewer do when it cannot run the code or cannot complete its own test?

4. [no-rule] “You decide: fix the design, fix the contract, or stop.” After the user chooses to fix the design or contract following the third failed code write, which artifact is rewritten first and how are the affected counters handled?

5. [no-rule] “If you want every contract rewrite to come to you, the machine can do that” What happens when a contract rewrite is required but the user does not choose one of the offered responses?
