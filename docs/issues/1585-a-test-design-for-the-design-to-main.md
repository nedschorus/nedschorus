---
issue: "[A test-design for the design-to-main state machine, and a review of its design, drawn from what the current path to main has learned](https://github.com/nedschorus/nedschorus/issues/1585)"
---

# A test-design for the design-to-main state machine, and a review of its design, drawn from what the current path to main has learned

## Why

design-to-main is the planned pipeline that takes a design to merged code through fixed states, each run by an agent, with the user ruling where the design says so. Its design is `docs/design-to-main/design-to-main-state-machine-design.md`; its build is GHI [Build the design-to-main state machine: the Python machine, its per-state agent-instructions, and the nine items the design defers to the build](https://github.com/nedschorus/nedschorus/issues/282). Meanwhile work reaches main by a simpler path: a GHI-MD, then pull requests that merge-lane-2 reviews and merges. That path has handled many cases, and each problem it met left a fix: a hook, a test-runner rule, a reviewer instruction, a merge-lane rule. The user directed (2026-10-14, approval-walk prime-intellect-open-decisions-for-the-user-2026-10-13, item 16) that design-to-main learn from that path: start a test-design for design-to-main from what the path taught, and review design-to-main's design with it. He also ruled that design-to-main gets no change until its design is mastered, so this review is part of mastering it, and its outcome is changes the user approves to the design, not code.

The design has a test-design for each component that design-to-main builds, but none for the machine itself: twelve test files under `scripts/design-to-main/tests/` check its transitions, counters and recovery, every run with a scripted launcher and no real agent, and the design does not say how the machine or its per-state agent-instructions are tested.

## What the work produces

1. A test-design for the design-to-main machine and its per-state agent-instructions: its test-requirements, and what runs the tests that need a real agent, which today's scripted launcher cannot; it starts from the sixteen candidate tests T1 to T16 in `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/design-to-main-lessons-from-current-system-2026-10-14.md`, section 1.
2. A review of the design against what the current path learned, with each finding proposed to the user as a change to the design or as a deferred line. The starting list:
   - The twelve gaps G1 to G12 in section 2 of the same file, among them review depth by change kind, root-cause lines in fix pull requests, resource limits and hangs, concurrency with the fleet's hooks, what a launched agent may write or reach, nice-but-dirty files, where the run record lives, and who restarts the machine after a crash.
   - States with no state-exit for stopping when they cannot proceed: `design-writing` has one verdict, `emitted`, so a run cannot stop or park itself from inside the design conversation when the user will neither settle nor defer a line; `implementation-writing` and `test-writing` have no `escalate-to-user`.
   - Section 3 of the same file: what design-to-main makes unnecessary, so the review also proposes what the design can drop.

## Decided elsewhere

- Sorting every deferred-decisions line at the start of each coding run, the markers `#not_in_this_run`, `#rejected`, `#revisit_before` and `#revisit_after`, and splitting the design's §11 "Not decided here" into "Deferred-decisions" and "Decided elsewhere": ruled by the user in approval-walk design-to-main-deferred-decisions-proposal-two-buckets-2026-10-15, landing by a pull request under GHI 282 that prime-intellect opens after that walk closes. This review reads the design after that pull request merges; if it is closed unmerged, the review reads the design as main has it then.
- Three questions about the machine's code, which cold-read-research handed over on 2026-10-17 and which prime-intellect is adding to GHI 282's GHI-MD as provisional additions: whether design-to-main's four upstream entry reasons become one, whether rulings the machine does not recognise stay recorded as free text, and whether `scripts/design-to-main/tests/design-to-main-counters-write-and-ruling-ceilings-test.py` splits into one file per counter. GHI 282's GHI-MD owns them.

## Next action

After the deferred-decisions pull request under GHI 282 merges, prime-intellect reads the design whole and the lessons file, writes the test-design and the review's findings as one document, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/design-to-main-test-design-and-design-review-<date>.md`, gives it a /cold-read, and walks it with the user. The changes the user approves land on the design by one pull request; a finding he rejects is recorded in the design as a `#rejected` line.

## Prior work

- The lessons inventory, mined from main's history, merge-lane-2's rules and the review, merge and frozen-head GHIs on 2026-10-14: `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/design-to-main-lessons-from-current-system-2026-10-14.md`.
- The deferred-decisions proposal: `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/design-to-main-deferred-decisions-proposal-2026-10-15.md`.
- GHI [Review-system design requirements learned from the legacy gate — dormant until a class of work first requires review](https://github.com/nedschorus/nedschorus/issues/31) collected an earlier set of such lessons.
