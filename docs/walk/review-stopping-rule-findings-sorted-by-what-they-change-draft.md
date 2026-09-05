# Walk: the review stopping rule — findings sorted by what they change

The stopping rule says when a review loop ends: a round that changes no line of code or test closes it. This walk explains the rule, the four kinds of finding it sorts, the two guards that keep it honest, and why the evidence supports it.

7 items.

---

## Item 1 of 7: The problem the rule solves — reviews that never end

A review loop is: an agent writes code, a reviewer reports findings, the agent fixes them, the reviewer reads the fixed version, and the cycle repeats until the reviewer has nothing to report. The question is when that ends.

The project has measured what happens without a rule. One pull request deleted a single obsolete file — ten lines added, sixty-five removed. It drew four review rounds over five hours. Every blocking finding was about prose, and two of the three were errors the previous round's own fix had introduced. That record is in `CLAUDE.md`, under the review-scope rule.

The mechanism is simple. A fix is new text. New text has new defects. A reviewer who reads carefully will always find something to say about a sentence, because prose has no test that says "done." So a loop that runs until the reviewer is silent runs until the reviewer gives up.

Code is different. A test passes or fails. A deliberately broken version either fails the test or it does not. That gives code an oracle prose lacks, and the stopping rule is built on using it.

No decision here. This item is the problem the rest answers.

---

## Item 2 of 7: The rule itself

The rule: **a review round ends the loop when it produces no finding that changes a line of code or a line of test.**

That is the whole rule. Everything else in this walk is how to apply it — how to sort a finding into "changes code or test" or "does not."

Two things it deliberately measures. It counts lines changed, not effort or importance: a one-character fix to an exit code is a real finding and keeps the loop open exactly as a large one would. And it counts test lines the same as code lines: a wrong fixture or a missing case is a finding, even when no line of the program moves.

Two things it deliberately ignores. How much the reviewer wrote, and how much the documents moved. A round can produce three pages of commentary and be a clean round, if none of it changes code or a test.

Recommendation: adopt the rule as stated. Y to approve, N to disapprove, D to defer.

---

## Item 3 of 7: A contract finding reopens both designs

A contract finding is one that changes what the script promises its caller — an exit status, an output line, a condition it refuses, a state guarantee.

Concrete example from today. The design for the topic-branch script promised that `git merge --ff-only origin/main` would refuse when the seat's branch carried stray commits, and called that the safety net. Measured in a throwaway repository: when the branch is strictly ahead of main, that command prints "Already up to date", exits 0, and the stray commit rides into the next topic branch. The safety net was not one. That is a contract finding — the script would not have done what it promised.

A contract finding changes both documents: the code design, because the mechanism it describes is wrong, and the test design, because the test cases derive from the contract. It is the only kind of finding that can restart the loop from the top, and it is the kind that should. It is also the one kind of finding that earns a design a fresh cold read — the design's mechanism moved, so its text must be read again.

Recommendation: a contract finding reopens both designs and earns one cold read. Y, N, or D.

---

## Item 4 of 7: An implementation finding touches the code and nothing else

An implementation finding changes how the contract is met, without changing what it promises. Same exit codes, same output, same refusals — a different way of getting there.

Example: the design says the script refuses when a ref-path collision exists — branch `foo` blocks creating `foo/bar`. A reviewer points out the implementation checks this by parsing `git branch --list` output, which is fragile, when `git for-each-ref refs/heads/` is the reliable form. The behavior a caller sees is identical. The code changes; the contract does not.

An implementation finding changes the code and nothing else. Neither design moves, because neither design said how the check should be written. It keeps the loop open for one more round, because a line of code changed and the tests must run again.

Recommendation: an implementation finding changes code only; neither document moves. Y, N, or D.

---

## Item 5 of 7: A prose finding does not enter the loop

A prose finding is about the wording of a design — a claim stated too strongly, a term used before it is defined, a sentence that supports two readings. It changes no code and no test.

`CLAUDE.md` already rules on this for pull request review: a reviewer reports nothing about `docs/` prose — silent, not merely non-blocking. The reason given there is exact: everything a reviewer writes gets read and "fixed" by another agent, and those fixes introduce defects of their own. That is the mechanism from item 1.

So a prose finding does not enter the review loop at all. The design is frozen from the second round on. It catches up with the code in maintenance after the change lands — the freeze-then-retrofit shape you ruled with the merge-lane seat today. One boundary on that: the design is updated in maintenance from what was *decided*, never from what the code *does*. A design revised to match the code is a tautology with a delay.

Recommendation: a prose finding is not reported during review and the design catches up in maintenance. Y, N, or D.

---

## Item 6 of 7: A nit changes code but nothing observable — and never holds the loop open alone

A nit is a finding that is real, correct, and does not matter to whether the change works. The word is short for nitpick. This project's severity scale, in [the adversarial package review brief](file:///Users/el/agents/reboot-test/docs/issues/8-adversarial-package-review.md), lists BLOCKER, MAJOR, MINOR, and NIT — the first three each say what goes wrong, and NIT is the class where nothing does.

Examples: a variable named `tmp` where `candidate_path` reads better; a comment restating the line below it; a function that could be two lines shorter. Fixing any of them changes what a reader sees. Fixing none changes what the program does.

The test for a nit: if it were left forever, would any caller, test, or user observe a difference? No means nit. Yes means it is a small defect mislabelled — and size is not the test, observability is. A one-character bug is a bug.

Where a nit goes: it is fixed in the round it is found only when that round has real findings being fixed anyway. A round that produces only nits is a clean round, because nothing in it can be told apart by a test from the round before. Counting nits would mean the loop can never close — there is always one more name that could be better.

The guard that makes this safe: **a nit carries no failure scenario, by definition. A finding that has a failure scenario — any way a caller, test, or user could observe the difference — cannot be labelled a nit, however small the fix.** When in doubt, label up. An over-labelled nit costs one sentence of disagreement. An under-labelled defect costs a green suite and a wrong result — which is what pull request 223 shipped, 143 passing tests and a wrong answer.

Recommendation: a nit never keeps the loop open on its own, and the labelling sentence in bold goes into `pr-reviewer-instructions.md` when [issue 210](https://github.com/nedschorus/nedschorus/issues/210) writes that file. Y, N, or D.

---

## Item 7 of 7: The two guards, and the summary

Two guards keep the sorting from being gamed.

**From round two on, the run is the round.** After the first round, the question is not "is there anything to say about this code" — there always is — but "does the suite pass, and does the red witness turn red." A reviewer who finds a real defect after round one demonstrates it with a failing test, not a paragraph. If it cannot be made to fail a test, it is prose, and it waits for maintenance.

**No fresh cold read of a design unless the mechanism changes.** A contract finding earns one. Nothing else does, however much the text moved. A cold read of a design whose behavior is already pinned by tests is the loop from item 1 restarting under another name.

Why the rule can be trusted: today's three cold-read rounds on one design found mechanism defects in round one, contract gaps in round two, and prose in round three. The class of finding got shallower every round, and the rule stops exactly where that curve flattens.

Summary of what this walk decided, if approved: the rule (item 2); contract findings reopen both designs and earn a cold read (3); implementation findings change code only (4); prose findings wait for maintenance, updated from decisions not code (5); nits never hold the loop alone, guarded by the no-failure-scenario labelling rule (6); and the two guards above.

Recommendation: adopt the two guards. Y, N, or D. If the whole walk is approved, the captures land in this walk's minutes and the labelling sentence is filed as a rider on issue 210.
