<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/gatekeeper-instructions.md -->

# `gatekeeper` — seat instructions

1. The work assigned to this seat is to turn the already-built Git gatekeeper from inactive software into the mechanism actually used to control changes reaching the repository’s main branch.
2. All tasks assigned here concern the same requirements, implementation, and security model, so completing one should reduce the effort needed for the following tasks.
3. The linked seat-model document explains what a “seat” is and how seats operate, while this document supplies the specific responsibilities and instructions for the `gatekeeper` seat.

## Where things stand

1. `scripts/git-gatekeeper.py` has been implemented through the first five planned development increments, called “slices,” merged into `main` through PR #49 on August 12, 2026, and accompanied by 169 test cases in `scripts/git-gatekeeper-test.py`.
2. Although the gatekeeper exists, it is not yet being used because no machine currently possesses an authentication credential capable of writing to or otherwise delivering changes into `main`.
3. For now, agents reach `main` through the temporary workflow of committing changes on a non-main working branch, pushing that branch, and having the review-and-merge role operating from the user’s Mac review and merge the work.
4. Before doing this seat’s work, the assignee must read `docs/cross-project/git-gatekeeper-design.md`, which is the authoritative gatekeeper specification reflecting the design as of August 12, 2026, and `docs/issues/3-git-gatekeeper-build-slice-plan.md`, which records the implementation order, design decisions already made, and follow-up work for the program.
5. GitHub issue `nedschorus#3` is the issue associated with this work, and its body was considered up to date as of August 12, 2026.
6. The directory `md-review-records/2026-08-09-git-gatekeeper-design/` contains the complete history of the design reviews: two review grids, a review concerned with removing unnecessary material, and all recorded decisions together with their rationales.
7. Before reconsidering any issue that has already been decided, the assignee must consult `dispositions.md` and `codex-dispositions.md` in that directory because they contain about forty dated decisions and their justifications, and independently repeating that analysis would consume the user’s time unnecessarily.

## The road, in order

1. The first required step is to design the evidence format for “walked approval,” meaning a checkable artifact that records the user’s approval of a change belonging to the instruction class; the exact mechanics of “walked” are not defined here, but the term appears to refer to the prescribed approval process rather than ordinary informal approval.
2. That design must answer what concrete, inspectable representation demonstrates that the user approved an instruction-class change.
3. No such representation has yet been designed, and all later gatekeeper work described here depends on it.
4. GitHub issue `nedschorus#31` contains or is intended to contain the definition of the instruction-change class and the rules that identify or protect that class.
5. The second required step is to implement slice 6, which adds a gatekeeper check that verifies the required review or approval evidence.
6. On August 10, 2026, it was decided that slice 6 must exist before the gatekeeper can be activated because the operating copy of the gatekeeper automatically updates itself from `main`, and that arrangement is safe only after changes to the gatekeeper’s own source code are prevented from reaching `main` without the required walked approval.
7. The third required step is the credential and deployment work: create a dedicated GitHub account that, under requirements identified as C1 and C3, is a write-capable collaborator only on this repository and is never an organization owner; create a dedicated Unix account that holds its credential; configure `sudoers` to use a root-owned gatekeeper copy located outside every source checkout and capable of keeping itself synchronized with `main`; and change branch protection so that permission to push is restricted to the new GitHub account.
8. A GitHub organization owner must apply the changes requiring owner authority, and the user is responsible for performing that portion.
9. PR #55 is also assigned to this seat; it changes the gatekeeper audit so that differences in capitalization do not make equivalent account names compare as different, incorporates the review decisions from PR #49 into the slice plan, and was open and waiting for review when these instructions were written.

## What is settled, and must not be relitigated

1. The user has already made the decisions listed here, and the disposition files record the reasoning behind each one.
2. The important settled decisions are that slice 4’s asynchronous processing remains because some checks are expected to take a long time; the deployed gatekeeper automatically updates itself instead of requiring manual deployment because ease of operation was prioritized over ease of initial implementation; the `--issue` option remains mandatory because mechanically requiring an issue reference is considered more reliable than expecting people to remember a convention; the audit that merely detected the absence of a trailer was removed because nothing used its result and therefore it imposed cost without producing value; the base revision or comparison point is derived by the program rather than supplied as a declaration; and requirement C7 has been eliminated entirely, although this file does not state what C7 formerly required.

## Boundaries

1. Work concerning handoff and supervisor mechanisms is owned by the `fleet` seat, while work concerning review methodology is owned by the `sanity-checker` seat.
2. If gatekeeper work depends on a change in either of those areas, the assignee must identify that dependency instead of directly changing the other area because the corresponding seat has the relevant specialized context.

## First action

1. The assignee’s initial workflow is to read the authoritative specification and slice plan, determine whether PR #55 has been merged, tell the user the gatekeeper program’s current position along the ordered road described above, and ask which step the user wants undertaken first.
2. The assignee must not begin designing the approval-evidence format until the user explicitly authorizes it because that design affects the instruction class and the user, rather than the assignee, has authority to decide its form.
