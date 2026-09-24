---
issue: "[Three mechanical checks agents keep forgetting to run: file-overlap before work starts, exit status through a pipe, and the settled-decision list](https://github.com/nedschorus/nedschorus/issues/216)"
---

# Three mechanical checks agents keep forgetting to run: file-overlap before work starts, exit status through a pipe, and the settled-decision list

Three small mechanical checks, each proposed after an agent that knew the rule broke it anyway. The pattern is the point: a rule stating "check X before you do Y" is forgotten by the very agents who wrote it, while a program that performs the check is not. This issue holds them together so they get built or dropped as a set.

None is blocking, none is scheduled. This is a candidate list with its evidence attached.

## 1. File-overlap check before a seat starts work

Before starting a task, does an open pull request already touch the files it will change? Two seats editing one file produce a merge conflict at best and a lost edit at worst.

Evidence: the six routed fix rounds of 2026-08-28 were dispatched only after this seat checked overlap **by hand** ("all four disjoint from each other and from PR [CLAUDE.md: six rules leave for the skills that own them](https://github.com/nedschorus/nedschorus/pull/184)"). Nothing enforces that check; it happened because one agent remembered.

Distinct from the git-gatekeeper's same-path overlap refusal (GHI [main-gatekeeper — the single check-in gate (design: nc-systems/main-gatekeeper/main-gatekeeper-design.md)](https://github.com/nedschorus/nedschorus/issues/3)), which fires at check-in between competing landings — a landing-race guard, not a work-assignment guard, and far too late to prevent duplicated work.

## 2. Exit status read through a pipe

`command | tail` reports `tail`'s exit status, not the command's, so a failing run reads as a pass. A check greps committed shell for pipelines whose status is then tested, and for a missing `pipefail`.

Evidence, and the reason this issue exists: while verifying the fix for exactly this defect in PR [find-deleted-path-across-backups: one command that searches all four histories](https://github.com/nedschorus/nedschorus/pull/146), the reviewing seat committed the same defect within the hour — piping a run through `tail` and reading `tail`'s status. Its own words: *"this class needs an instrument rather than a rule."*

## 3. The settled-decision list, pasted into the reviewer's prompt

A later review pass re-raises what an earlier round deliberately decided — a wording the user ruled, a gap left open on purpose — because the reviewer has no way to know it was decided. The author then re-argues settled ground every round.

The mechanism follows the same shape as 1 and 2 and as GHI [pr-reviewer-instructions.md: the review-scope rule (code blocks; operative prose gospel; other prose silent), included verbatim in every composed reviewer prompt](https://github.com/nedschorus/nedschorus/issues/210): not a rule reviewers must remember, but text a program includes at composition time. The pull request body carries a "decided, not a finding" list; the commissioning instrument pastes it into the reviewer's prompt beside the scope rules. A decision that was never written down cannot be protected by any marker, which is the honest limit of this check.

Evidence and scope, both worth stating plainly:

- The class that made this urgent — four review rounds on PR [Retire the skill-authoring checklist as obsolete](https://github.com/nedschorus/nedschorus/pull/198), every blocking finding about prose — is already killed by the 2026-08-30 review-scope rule (GHI [pr-reviewer-instructions.md: the review-scope rule (code blocks; operative prose gospel; other prose silent), included verbatim in every composed reviewer prompt](https://github.com/nedschorus/nedschorus/issues/210)): prose findings are silent, so those rounds cannot recur. What remains is settled *code* decisions being re-raised.
- A settled-marker does not shrink a re-review much. Measured 2026-08-30 in the filter-order experiment: a later pass re-finds 80–104% of the first pass's volume, because rewriting mints new defects rather than exhausting a fixed pool. This check prevents re-litigation of specific decisions; it does not reduce finding counts.

Absorbed here from the standing task "Design the mechanism that tells a later review pass what is already settled" (user-ruled 2026-08-31: fold it into this family rather than design it standalone).

## A fourth candidate, considered and dropped

A "citation sweep" — given a rule's opening phrase, find every copy across main and every open branch so an edit to one copy does not leave the others stating it differently — was proposed and **rejected by the user 2026-08-30**: detection for a problem that should not exist. Two standing rules already prevent the copies: where a program composes a prompt it includes the master file's text verbatim at composition time (GHI [pr-reviewer-instructions.md: the review-scope rule (code blocks; operative prose gospel; other prose silent), included verbatim in every composed reviewer prompt](https://github.com/nedschorus/nedschorus/issues/210)), and where a document refers to a rule it cites the master rather than restating it. Finding whatever duplicates already exist is a one-off grep during cleanup, not an instrument. Recorded here so the idea is not re-proposed without new evidence.

Separately, verifying that a citation points at something reachable — the dangling-SHA class, four instances in one day on 2026-08-28 — is GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42)'s reference-integrity checker, already filed.

## Next action

The user decides whether to build any of these, and in what order; each is small enough for one fresh agent with a test suite. GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42) scopes itself as "the home for what-else-can-code-check" and is the natural home for 2; 1 runs at a different moment — before work starts, not at review — and may want its own entry point; 3 belongs wherever reviewer prompts are composed, beside GHI [pr-reviewer-instructions.md: the review-scope rule (code blocks; operative prose gospel; other prose silent), included verbatim in every composed reviewer prompt](https://github.com/nedschorus/nedschorus/issues/210)'s inclusion wiring.

Search receipt, 2026-08-30: ghi-info asked over both mirrors for a pre-flight file-overlap check and for pipe-masked exit status; zero hits for `pipefail` or `PIPESTATUS` anywhere in the corpus, and no issue owns either check.
