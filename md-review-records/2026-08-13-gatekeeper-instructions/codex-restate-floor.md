<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/gatekeeper-instructions.md -->

# `gatekeeper` — seat instructions

1. “Your pile” means your assigned body of work is to take the git-gatekeeper, which has been implemented but is not yet operating, and make it operational.

2. All tasks in this seat use the same specification, the same program, and the same security-threat assumptions, so completing one task should reduce the work required for subsequent tasks.

3. Read `agent-seat-model.md` to understand how seats function; this file is the instructions or brief for your assignment.

## Where things stand

1. `scripts/git-gatekeeper.py` has implemented all five planned slices and has been merged into the `main` branch in PR #49 on 2026-08-12. Its test suite is `scripts/git-gatekeeper-test.py`, which contains 169 test cases.

2. The gatekeeper is not currently being used because no host has a credential capable of performing an operation involving `main`; the file does not specify whether “main-capable” means push, merge, or some other permission.

3. Until the gatekeeper is activated, agents work by committing to a working branch and pushing it, after which the user’s seat on his Mac reviews the work and merges it.

4. Before doing other work, read `docs/cross-project/git-gatekeeper-design.md`, which is the authoritative specification as of 2026-08-12, and `docs/issues/3-git-gatekeeper-build-slice-plan.md`, which records the implementation order, design decisions that have already been ruled on, and follow-up work for the wider program.

5. GitHub issue `nedschorus#3` is also part of the required reference material, and its body should be treated as current as of 2026-08-12.

6. The complete record of the design reviews—including two Markdown-review grids, a review focused on removing things, and every decision together with its reasoning—is stored in `md-review-records/2026-08-09-git-gatekeeper-design/`.

7. Before reconsidering any question that has already been settled, consult `dispositions.md` and `codex-dispositions.md` in that directory, because they record approximately forty dated decisions and their reasons, and reconstructing those decisions would unnecessarily consume the user’s time.

## The road, in order

1. The first task is to design the format of the evidence that will accompany a walked approval.

2. The question to answer is what concrete, verifiable artifact should represent the user’s approval of a change classified as instruction-class work.

3. That evidence format has not yet been designed, and all later work depends on it.

4. Issue `nedschorus#31` is the reference for defining the relevant instruction class and its guard conditions; the file does not provide their contents.

5. The second task is to build slice 6, the review-evidence check that enforces the newly designed evidence format at the gate.

6. The user ruled on 2026-08-10 that slice 6 must be completed before activation, because the deployed gatekeeper copy updates itself from `main`, and that arrangement is considered safe only after the gatekeeper’s own source code cannot enter `main` without walked approval.

7. The third task is the credential work: create a dedicated GitHub account that, under constraints C1 and C3, is a collaborator with write access to this one repository but is never an organization owner; create a dedicated Unix user to hold the credential; configure `sudoers` to point to a root-owned gatekeeper copy located outside every checkout and kept current from `main`; and transfer branch protection’s push restriction to the new account.

8. An organization owner must apply the credential-related changes, and the user will handle that part.

9. PR #55 is also assigned to you; it audits account-name comparisons so they are case-insensitive and incorporates the PR #49 review rulings into the slice plan. The pull request is open and waiting for review.

## What is settled, and must not be relitigated

1. The decisions listed in this section were made by the user, and each decision—including its reasoning—is recorded in the disposition files.

2. Among the settled decisions are that slice 4’s asynchronous machinery remains because slow checks are expected; the deployed copy updates itself instead of being manually deployed because ease of operation was preferred over ease of initial construction; `--issue` remains because an enforced mechanical requirement should not be replaced by reliance on people learning and remembering a habit; the audit for missing trailers is removed because a detector whose output has no consumer provides cost without benefit; the base is derived computationally rather than asserted or supplied declaratively; and C7 has been reduced to zero or eliminated. The file does not explain what C7 specifically represents.

## Boundaries

1. The handoff and supervisor mechanisms belong to `fleet`, while review methodology belongs to `sanity-checker`; if your work requires changing either area, report that need instead of modifying it yourself, because those seats own the relevant context.

2. The first action is to read the specification and slice plan, determine whether PR #55 has merged, report the current state of the work to the user, and ask which step he wants started first.

3. Do not begin designing the evidence format until the user explicitly authorizes it, because it concerns instruction-class work and the user must decide its form.
