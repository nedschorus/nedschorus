# Walk: the PR-review graph — coder, reviewer, and originator loops

The PR-review graph is the process a component design goes through to become merged code: who codes it, who reviews it, what each hands to whom, and when each loop ends.

7 items.

---

## Item 1 of 7: The nodes and the artifacts

Five roles and a handful of files. The roles are agents; in this fleet each round of work is done by a fresh agent, so the files are the only state that crosses from one round to the next.

- **The originator** owns the component design. It commissioned the work and is the only role that can change what the design promises.
- **The coder** builds the component from the design.
- **The test coder** builds the tests from a separate test design. The user ruled that the test design is its own document and that the coder does not write it.
- **The code reviewer** and **the test reviewer** read the design and the code, or the test design and the tests, and report findings under the project's review-scope rule in `CLAUDE.md`: code is reviewed adversarially, operative prose is taken as settled, other prose is not reported.
- **The merge-lane seat** merges. The graph runs inside the existing PR process, not beside it.

The files, named for the component X and the agent that wrote them:

- `X-coder1-design-issues.md` — the coder found the design seriously flawed. It goes to the originator and the coder stops.
- `X-coder1-design-nits.md` — minor problems the coder noted and worked around. It travels forward with the code.
- The reviewer's findings, which go back to the coder, or to the originator when they change the design's promise.

Running example for the rest of this walk: the topic-branch creation script, [design for issue 238](file:///Users/el/agents/reboot-test/docs/issues/238-topic-branch-creation-script-design.md). Its design was cold-read three times on 2026-09-02, and one of those rounds found the defect item 2 uses.

No decision here. This item names the parts the rest connects.

---

## Item 2 of 7: The coder's first move — stop or continue

The coder reads the design before writing any code and makes one call: is this design seriously flawed, or merely imperfect?

"Seriously flawed" needs a test, or the coder holds a veto on judgment alone. The test: the design promises something to its caller that cannot be built, or that is wrong when built. A promise is an exit status, an output line, a condition the script refuses, a state guarantee.

The 238 design gave a concrete case. It said `git merge --ff-only origin/main` would refuse when a seat's branch carried stray commits, and called that the safety net. Measured in a throwaway repository: when the branch is strictly ahead of main, that command prints "Already up to date", exits 0, and the stray commit rides into the next topic branch. The safety net was not one. A coder who found that should write it to `X-coder1-design-issues.md`, hand the file to the originator, and stop. Code written against that design would be wrong on delivery.

Every entry in the issues file carries a failure scenario: which caller does what, and what breaks. An entry without one is not an issue; it is a nit, and it goes in the other file.

Everything short of that test — a term used before it is defined, a check the coder would write differently, a claim stated too strongly — goes in `X-coder1-design-nits.md`, and the coder continues. The nits file records where and why the code deviates from the design on purpose.

Recommendation: the coder stops only on a contract defect with a failure scenario; everything else is noted in the nits file and the coder continues. Y to approve, N to disapprove, D to defer.

---

## Item 3 of 7: The two loops and their order

Each loop runs on the stopping rule the user already adopted: a review round ends the loop when it produces no finding that changes a line of code or a line of test. A finding is a report with a failure scenario. Commentary, however long, and document movement, however large, do not count.

There are two loops. The design-code loop: coder, code reviewer, fix, review again. The test-design-test-code loop: test coder, test reviewer, fix, review again. They are the same shape.

Order matters because of one guard: from the second round on, the code reviewer proves a finding by a failing test, or by a reproduction by hand where no test can reach it. That needs the tests to exist by the code loop's second round.

So the sequence is:

1. The coder reads the design and makes the stop-or-continue call of item 2. This goes first because it is cheap and because a stop invalidates the test loop too: the test cases derive from the contract, and a contract defect means the test design must also change.
2. The test coder and the coder work in parallel from their two designs.
3. The code review loop runs the tests. From round two on, the run is the round: the suite passes and a deliberately broken copy of the code, the red witness, fails it.

For the 238 script: the coder reads the design, finds nothing that fails item 2's test, writes its nits, and starts. The test coder starts from the test design at the same time. When the first review round arrives, the tests are there to run.

Recommendation: adopt this order — stop check first, then test code and code in parallel, then a code review that runs the tests. Y, N, or D.

---

## Item 4 of 7: What the reviewer receives

The reviewer gets the design, the code, and the coder's nits file. Not the issues file, because when an issues file exists no code was written.

The user's sketch left the nits file open — "but not the notes?" — and there is a case for keeping it back: a reviewer who reads the coder's notes is primed by them, and independence is the point of a review.

The case for handing it over is stronger. A coder who continues past a minor design flaw has written code that deviates from the design on purpose, and the nits file says where and why. A reviewer checking code against design without that file reports every one of those deviations as a finding. The coder answers each with the note it already wrote. That is a round that changes no line of code, spent on paperwork.

The independence lost is small, because the nits file holds only what failed item 2's test: things with no failure scenario. A reviewer primed by a list of nits still reads the code cold for defects.

Example: the 238 design says the script checks for a ref-path collision, where a branch `foo` blocks creating `foo/bar`. Suppose the coder chose `git for-each-ref refs/heads/` over the design's wording and noted why. Without the note, the reviewer's first round reports "does not match the design." With it, the reviewer reads the check itself.

Recommendation: the reviewer receives the design, the code, and the nits file. Y, N, or D.

---

## Item 5.1 of 7: The reviewer's back edges — contract and implementation findings

A reviewer's finding goes back along one of four edges, sorted by what it changes.

**A contract finding** changes what the code promises its caller. It is item 2's test applied by the reviewer instead of the coder, and it takes the same path: the reviewer writes it to the originator, the loop restarts from the top, and the revised design earns one cold read — the fresh-reader review the project runs on any document of lasting value — because its promise moved, so its text must be read again. Both designs reopen, the code design because what it describes is wrong and the test design because the test cases derive from the contract. Who reads that cold read is being measured by a separate campaign and is not decided here.

**An implementation finding** changes how the contract is met without changing what it promises. Same exit codes, same output, same refusals, a different way of getting there. Example: the design says the script refuses on a ref-path collision. The reviewer points out the code checks this by parsing `git branch --list` output, which is fragile, when `git for-each-ref refs/heads/` is the reliable form. The caller sees no difference. The code changes and nothing else: neither design moves, because neither design said how the check should be written. The loop stays open one more round, because a line changed and the tests must run again.

Continued in 5.2.

---

## Item 5.2 of 7: The reviewer's back edges — prose findings and nits

**A prose finding** is about the wording of a design: a claim stated too strongly, a term used before it is defined, a sentence that supports two readings. It changes no code and no test. `CLAUDE.md` already rules that a reviewer reports nothing about `docs/` prose, silent rather than merely non-blocking, because everything a reviewer writes gets read and "fixed" by another agent and those fixes introduce defects of their own. So a prose finding does not enter the loop. The design is frozen from the second round on and catches up in maintenance after the change lands, updated from what was decided, never from what the code does. A design revised to match the code is a tautology with a delay.

**A nit** is real, correct, and does not matter to whether the change works: a variable named `tmp` where `candidate_path` reads better, a comment restating the line below it. The test: if it were left forever, would any caller, test, or user observe a difference? No means nit. The author fixes it or leaves it, in any round. A round that produces only nits is a clean round.

The guard that makes this safe: a nit carries no failure scenario, by definition. A finding that has a failure scenario cannot be labelled a nit, however small the fix. When in doubt, label up. An over-labelled nit costs one sentence of disagreement. An under-labelled defect costs a green suite and a wrong result, which is what [pull request 223](https://github.com/nedschorus/nedschorus/pull/223) shipped: 143 passing tests and a wrong answer.

Recommendation: adopt the four edges as stated — contract to the originator with one cold read, implementation to the code only, prose not reported, nits never holding the loop — with the labelling guard. Y, N, or D.

---

## Item 6 of 7: Who arbitrates, and the two guards

The graph has one disagreement built in. The coder says a reviewer's finding is implementation; the reviewer says it is contract. The difference decides whether the loop runs one more round or restarts from the top with both designs reopened.

Neither party should settle it, because each has a stake: the coder wants the loop to close, the reviewer wants its finding to count. The originator owns the design and is the only role that can say what it promised. So the originator arbitrates. The coder and reviewer each state their reading in one paragraph with the failure scenario, and the originator rules.

Two guards keep the sorting from being gamed.

**From round two on, the run is the round.** After the first round the question is not "is there anything to say about this code," because there always is, but "does the suite pass, and does the red witness turn red." A reviewer who finds a real defect after round one demonstrates it with a failing test, or with a reproduction by hand where no test can reach it. If it cannot be demonstrated either way, it is prose, and it waits for maintenance.

**No fresh cold read of a design unless the contract changes.** A contract finding earns one. Nothing else does, however much the text moved. A cold read of a design whose behavior is already pinned by tests is the never-ending prose loop restarting under another name.

Recommendation: the originator arbitrates contract-versus-implementation disagreements, and the two guards are adopted. Y, N, or D.

---

## Item 7 of 7: Summary and the next step

What this walk decides, if approved:

- The coder stops only on a contract defect with a failure scenario, written to the originator; everything else is noted and the coder continues (item 2).
- The stopping rule closes each loop, and the order is stop check, then test code and code in parallel, then a code review that runs the tests (item 3).
- The reviewer receives the design, the code, and the nits file (item 4).
- The four back edges: contract to the originator with one cold read, implementation to the code only, prose not reported and caught up in maintenance from decisions, nits never holding the loop, with the labelling guard (item 5).
- The originator arbitrates, and the two guards hold (item 6).

The next step is to write the graph down as a design document of its own, with these decisions folded in and the file names and hand-offs made exact, and give it its cold read before it lands. Its first run is the 238 script build, which is waiting on exactly this process: the design is cold-read and fixed, the test design is to be written as a separate document, and the coder's first move is item 2.

The labelling sentence from item 5.2 also goes to the reviewer instructions that [issue 210](https://github.com/nedschorus/nedschorus/issues/210) is writing, as a rider.

Recommendation: record these decisions in the minutes, write the graph as a design document and cold-read it, and file the labelling sentence on issue 210. Y, N, or D.
