<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/sanity-checker-instructions.md -->

1. “Does the sanity-checker join the md-review grid as three stance attacks … run on both Fable and gpt-5.6-sol at xhigh?” The existing grid launches restate/defect-hunt cells across good/floor tiers, while the attack experiment uses a separate runner. “Join” does not say whether these cells replace, supplement, or modify the existing grid, so a yes/no decision is not executable. Confidence: sure.

2. “gatekeeper 4 of 5 in-band accepted cuts against the baseline's best 3 of 6” uses undefined “in-band” and unexplained denominators. The scorecard lists six accepted S-rulings but gives no reason here for excluding one from the 5. The evidence cannot be reproduced from this sentence. Confidence: sure.

3. “zero unflagged false positives across eight judgment cells” conflicts with the cited experiment’s provenance: three attacks × two runtimes × two documents produces 12 cells. If four cells are excluded from “judgment cells,” the exclusion is unstated. Confidence: sure.

4. “A skill change is walked with the user before it lands, so this is a walk, not an application.” “Walk” and “application” have no procedure or explicit skill path here. A future agent cannot tell whether this means one approval, an item-by-item interaction, or some other operation. Confidence: sure.

5. “The experiment surfaced four findings beyond both ground-truth sets.” The cited scorecard records substantially more than four novel findings, including the spec bug, `--agent` issue, provisioning command, AST test, and several others. This may intend only the four selected for this seat, but that restriction is not stated. Confidence: unsure — the heading could imply a selected subset.

6. “Never presented, never triaged” is unclear against the scorecard’s “Fresh-eyes yield (diffed against the real designs by triage)” and its recommendation to the user. If “triaged” means internal report triage, it is contradicted; if it means user triage, that meaning is unstated. Confidence: unsure — “presented” and “triaged” have multiple plausible scopes.

7. “each read an archived snapshot” is false for the fresh-eyes findings. The experiment runner gives fresh-eyes cells only a problem statement from an empty scratch directory; the gate-edits-the-gate and wedged-session findings came from those cells. Confidence: sure.

8. “so the gate runs no checks today.” The preceding evidence supports only that the project test suite is not wired into the gate. The gate still performs form validation, candidate construction, refusal checks, and other deterministic checks; the specification explicitly calls construction the version-one check set. Confidence: sure.

9. “Findings 1 and 2 are gatekeeper territory and 4 is fleet territory” assigns no owner or destination for finding 3. The pin-stamp finding concerns the writer/session machinery, but the file gives no disposition for it, so it can remain indefinitely in this seat. Confidence: sure.

10. “triage them here, then hand the survivors to those seats” requires triage but defines neither what counts as triage-complete nor what makes a finding a “survivor.” It also gives no handling for disagreement, failed verification, or an unowned finding. Confidence: sure.

11. “the per-runtime cells” is not a path or an identifiable name. The file names the grid script but not the Claude and Codex cell launchers, so a future agent cannot determine which files constitute this machinery by following the stated references alone. Confidence: sure.

12. “Codex floor tier moved terra → luna on 2026-08-13 (in PR #57).” “terra” and “luna” are opaque aliases, PR #57 is not linked or locally identified, and the sentence does not say whether the floor tier applies to the proposed sanity-checker cells. It conflicts in possible reading with the decision’s stated `gpt-5.6-sol`-only model set. Confidence: sure.

13. “Open PRs yours to shepherd” and “coordinate with `fleet` if it needs work” assign continuing work without a completion condition. “Shepherd,” “under a Monitor,” and “needs work” do not identify when the responsibility ends. Confidence: sure.

14. “a detector with no consumer is cost without value” drops qualifications present in the cited prompt: a detector is a cut candidate only when no consumer is present and none is planned, and forcing a decision counts as consumption. Taken literally, this could discard machinery intentionally built for a future trigger or human decision. Confidence: sure.

15. “never trade a deterministic script for probabilistic agent behavior.” This absolute is broader than the project’s own model/code division: a deterministic script can encode incorrect assumptions, while semantic ambiguity or open-ended judgment may require a model. The literal rule could reject valid cases where probabilistic judgment is the intended mechanism. Confidence: sure.

16. “Read the scorecard and the prompt draft's header” leaves “header” ambiguous. The draft has a title/status area and a separate operating-rulings section before its horizontal rule; reading only the former can omit the rules this file says are load-bearing. Confidence: sure.

17. “verify the four novel findings against current code before proposing anything” gives no code paths, revision pin, or failure outcome. The findings span gatekeeper code, fleet/session code, and writer behavior, so “current code” does not identify what must be checked or what to do when a quoted ground no longer holds. Confidence: sure.

18. “then offer the user the grid-seat walk” conflicts in order with “triage them here” and “ask again plainly and let him choose” between the walk and triage. One reading requires triage before the user interaction; another requires asking the user which comes first. Confidence: sure.

19. “He has already been asked ‘which first, the walk or the triage?’ and has not answered; ask again plainly” is a stale external-state assertion with no date or check. Once the user has answered, a future agent following this literally will repeat a question and disregard the existing ruling. Confidence: sure.

clean sections: An unowned thread worth claiming
