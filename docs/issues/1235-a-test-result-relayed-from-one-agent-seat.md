---
issue: "[A test result relayed from one agent-seat to another without its exit code can hide a crash as a pass](https://github.com/nedschorus/nedschorus/issues/1235)"
---

# A test result relayed from one agent-seat to another without its exit code can hide a crash as a pass

When one agent-seat runs a test for another, such as a run on the Mac for a pull request merge-lane-2 is reviewing on ned-box, the result reaches the reviewing agent-seat in a message, directly or through the pull request's author. When that message says the test passed because the output showed no failures, and does not give the test's exit code, a test that crashed part-way reads as a pass: a crash prints no FAIL line, and the cases after the crash print nothing at all.

## What happened

On 2026-10-13 (UTC), in the first review round of pull request [#1226](https://github.com/nedschorus/nedschorus/pull/1226), the agent-seat cold-read-research ran `scripts/mac-window-opened-for-ned-box-forced-command-test.py` on the Mac at the pull request's head `0524e16e`, and the result reached merge-lane-2, through the pull request's author, as a run with no failure, with no exit code. merge-lane-2's [review of that round](https://github.com/nedschorus/nedschorus/pull/1226#pullrequestreview-5497576888) records the relay: "The author relays a Mac run by cold-read-research on this head with no failure."

The test had crashed instead. The Mac's `/bin/bash` is 3.2.57, which has no `globasciiranges` option; the test's probe for that option took it as present, ran `bash +O globasciiranges`, bash 3.2 refused, and an AssertionError ended the test file part-way. The author's [fix-round comment](https://github.com/nedschorus/nedschorus/pull/1226#issuecomment-6135668872) explains the crash and why the run read as a pass: the relayed output "had no FAIL line, and none of the SKIP lines printed after that point". The blocking finding that caught the defect came from a reviewer reading the code, not from the relayed run. According to merge-lane-2, cold-read-research then withdrew the report, and its rerun on the fixed head `66c4259a` reported exit 0, 146 PASS, with `/bin/bash` 3.2.57.

## Why it matters

A crash relayed as a pass lets a pull request that breaks the Mac merge, and the Mac is the machine a reviewer on ned-box cannot check directly. The exit code is the one part of a test run's result that a crash cannot hide: `scripts/run-all-test-suites.py` judges every suite by its exit code alone, and a Python test file that ends on an uncaught error exits nonzero. An exit code of 0 alone does not show that the cases ran, so the count of cases run belongs beside it.

## What is undecided

Whether to act, and how, is not yet decided. Possible actions:

- a standing instruction that a relayed test result gives the command, the machine, the exit code and the test's closing summary line with its count of cases, and that a reviewer treats a result without an exit code as not yet run, asking for the exit code or running the test again;
- a program that runs a test on the Mac for an agent-seat on ned-box and reports the exit code itself, so no agent-seat retypes the result;
- recording this in GHI [#216](https://github.com/nedschorus/nedschorus/issues/216), which collects checks agents forget to make and whose item 2 is an exit status lost through a shell pipe, as one more case of an exit status that never reaches the reader; a fix for item 2, a check of committed shell, would not by itself fix this case.

## Next action

The queue-drain decides whether this becomes work, joins #216, or is dropped; the user rules on any standing instruction it leads to.

## Related

- GHI [#216](https://github.com/nedschorus/nedschorus/issues/216), item 2: an exit status lost through a pipe in committed shell. The cause differs: there, a pipe hides the status; here, no one read the status before reporting the result.
- GHI [#172](https://github.com/nedschorus/nedschorus/issues/172), closed: a test file that aborted on Linux part-way, so that the aborted run read as a pass.

Search receipt: on 2026-10-13 (UTC), `scripts/ghi-info-ask.py --include-closed` searched for "exit code", "relay", "bash 3.2", "crash...pass" and "reads as a pass", and found no issue about a test result relayed between agent-seats without its exit code; its nearest results were #216 and #172. `gh issue list --state all --search` on "exit code relayed", "passed without exit code", "globasciiranges" and "test result relayed" found none either.
