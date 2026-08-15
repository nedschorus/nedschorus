<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/gatekeeper-instructions.md -->

No YAML frontmatter is present in this file — it begins directly with the H1 title.

## `gatekeeper` — seat instructions (opening paragraph, before any `##` heading)

1. This document introduces the scope of work assigned to this agent role ("seat"): moving the git-gatekeeper system from a state where it is completely built but not yet operating ("built-but-dormant") to a state where it is actively enforcing/running ("live"). "Your pile" means the body of work belonging to this seat.
2. All the tasks under this seat draw on one shared design document, one shared codebase, and one shared analysis of what attacks/failure modes the system must guard against; because they share this common foundation, finishing one task reduces the effort required for the next one.
3. Go read a separate document (linked as "the seat model," at `agent-seat-model.md`) to learn how the general "seat" concept works in this project; this document itself is the specific set of instructions ("brief") for this one seat.

## Where things stand

1. The file `scripts/git-gatekeeper.py` has been fully implemented across all five planned build increments ("slices") and that implementation has been merged into the main branch via pull request #49 on August 12, 2026; a companion test suite containing 169 individual test cases exists in `scripts/git-gatekeeper-test.py`.
2. The gatekeeper program is built but not currently active in practice ("dormant"), because no machine currently holds a credential capable of pushing to the main branch, so at present no actual operations are being routed through it.
3. As a temporary substitute process, agents currently get changes into the main branch by committing to a branch other than main, pushing that branch, and then having a specific agent seat that runs on the user's Mac computer review and merge it.
4. Before doing anything else, one should read two documents: `docs/cross-project/git-gatekeeper-design.md`, described as the authoritative design specification and current as of August 12, 2026, and `docs/issues/3-git-gatekeeper-build-slice-plan.md`, which contains the order the build increments were done in, the design decisions formally settled within it, and follow-up items for the program.
5. There is a corresponding GitHub issue, number 3 in the nedschorus repository, and its text is up to date as of August 12, 2026.
6. The complete record of how the design was reviewed — two documents in a structured review format called "md-review," one review focused specifically on finding things to cut ("a subtraction review"), and a record of every decision made along with its reasoning — is stored in the directory `md-review-records/2026-08-09-git-gatekeeper-design/`.
7. Before revisiting any question that has already been decided, one should consult two files in that directory, `dispositions.md` and `codex-dispositions.md` (the second apparently holding rulings from a separate reviewing entity or tool called "codex"); roughly forty decisions are recorded there with dates and reasoning, and redoing the work of reaching those decisions again would waste the user's time.

## The road, in order

Item 1:
1. The task named by this list item is: create a design for something called "the walked-approval evidence format."
2. This sentence poses the design question directly: when the user approves a change belonging to the category "instruction-class" (apparently changes to instructions/policy, as distinct from ordinary code), what concrete, checkable object or record should represent that approval having happened?
3. This format does not exist yet as of now, and other work later in the plan cannot proceed until it does.
4. The definition of what counts as "instruction-class," along with associated protective checks ("guards"), is documented in GitHub issue #31 in the nedschorus repository.

Item 2:
1. The next build increment ("slice 6") is a check called "the review-evidence check," whose job is to require/enforce the evidence format from item 1 at the point where the gatekeeper decides whether to let a change through ("the gate").
2. It was formally decided on August 10, 2026 that this slice must be finished before the gatekeeper can be turned on, because the running copy of the gatekeeper updates itself automatically from the main branch, and that self-updating behavior is only safe once changes to the gatekeeper's own source code are guaranteed not to reach main without having gone through the walked-approval process.

Item 3:
1. This sentence lists four sub-parts of "the credential work": setting up a dedicated GitHub account (subject to constraints labeled C1 and C3, apparently referencing numbered points from the design document) that has write access only to this one repository and never organization-owner-level access; creating a dedicated Unix operating-system user account to hold this credential; creating a "sudoers" rule (a controlled-privilege-elevation permission rule) pointing at a copy of the program that is owned by the root user, stored outside any regular git working copy, and which updates itself automatically from main; and reconfiguring the repository's branch-protection setting so its restriction on who may push to main applies to this new dedicated account.
2. Carrying out this credential work requires someone with GitHub organization-owner permissions, and the user (the human) is the one who will personally do this part, rather than an agent.

Following line:
1. Also assigned to this seat is pull request #55, titled "gatekeeper audit: account names compared case-insensitively; PR #49 review rulings folded into the slice plan" (indicating it fixes an audit so account-name comparisons ignore letter case, and also incorporates review decisions from PR #49 into the slice-plan document); this PR is currently open and waiting for someone to review it.

## What is settled, and must not be relitigated

1. The user made formal decisions on the points that follow, and each decision together with its reasoning is written down in the disposition files mentioned earlier.
2. This single sentence lists six settled decisions as semicolon-separated clauses: the asynchronous processing machinery built in slice 4 will remain in place, because it's expected/accepted that some checks the gatekeeper runs will be slow; the copy of the program that is actually deployed will keep updating itself automatically rather than being redeployed by hand, because the design favors being easy to operate day-to-day over being easy to build initially; the `--issue` command-line option will remain, because a check that is mechanically enforced by the tool should never be replaced by relying on people simply remembering to do the equivalent thing ("trained habit"); the "trailer-absence audit" (apparently a check that flags when some expected item — likely a git commit trailer — is missing) will be removed from the design, because a detection mechanism that nothing downstream actually consumes/acts on provides cost without benefit; the "base" (likely the base commit or branch used as a comparison point) will be determined by calculation rather than being explicitly specified/hardcoded by a person; and the item referred to as "C7" (apparently another numbered constraint from the design document, akin to C1/C3 mentioned earlier) has been "struck to zero," meaning that constraint has been eliminated or reduced to having no remaining effect or requirement.

## Boundaries

1. Two areas of responsibility belong to different seats rather than to this one: the machinery for "handoff" (transferring context between agent sessions) and for "supervisor" functions (apparently overseeing/coordinating agent seats) belongs to a seat named `fleet`, and the methodology used for conducting reviews belongs to a seat named `sanity-checker`.
2. If, while doing the gatekeeper work, a change turns out to be needed in one of those other seats' areas, the correct action is to explicitly state that need rather than making the change directly oneself, because those other seats hold the necessary background understanding of their respective domains that this seat does not have.

## First action

1. The very first thing to do is: read the specification document and the slice-plan document, check whether pull request #55 has been merged into main yet, and then give the user a status report on where progress stands along "the road" (the three-step plan described earlier), asking him which step he wants tackled first.
2. Do not begin work on designing the walked-approval evidence format until the user has explicitly given his go-ahead, because that design work falls in the "instruction-class" category, and decisions about the shape of instruction-class work are reserved for the user to make, not for an agent to decide on its own.

