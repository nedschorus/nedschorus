<!-- provenance: runtime=codex model=gpt-5.6-terra effort=xhigh cell=defect-hunt tier=floor target=docs/cross-project/git-gatekeeper-design.md -->

1. “is BUILT through slice 3 of five — plus slice 6 (the review-evidence check), scheduled 2026-08-10 as a prerequisite of activating the privileged lane” — This supports two incompatible readings: that slice 6 is built, or that it is merely scheduled. Later text says the evidence format is undesigned and slice 6 waits on it. That can cause an agent to rely on nonexistent review-evidence enforcement or treat privileged-lane activation as unblocked. Confidence: unsure — “scheduled” may intend the latter reading, but the sentence grammatically permits the former.

2. “For each check-in request the program does exactly one of two things: **checks the work in**, or **refuses and teaches the fix**.” — A valid `--no-wait` check-in first returns `accepted <digest>`; it has neither checked work in nor refused. `accepted` is described later as a normal check-in outcome, so callers following this exhaustive two-outcome statement lack a branch for it. Confidence: sure.

3. “The repository is untouched — a refusal has no side effects, with one named exception” — This is false for ordinary refusals after base computation: the specified `git fetch` in the caller checkout updates Git metadata such as `FETCH_HEAD`. It is also false for an uncertain push failure: a remote can accept the atomic push and the response can be lost, after which the program reports `network-down` even though main changed. Both are reachable refusals outside the stated exception. Confidence: sure.

4. “Same request, same answer” — A request can first return `network-down` and later return either `checked-in` (if the push never reached GitHub) or `already-checked-in` (if GitHub accepted it before the response failed). The bytes and declared request can be unchanged. This makes retry logic that expects answer stability incorrect. Confidence: sure.

5. “[--repo <path>] [--remote <url>]” together with “the program runs `git merge-base HEAD origin/main`” — The allowed `--remote` can name a different target from the caller checkout’s `origin`, but the base is always computed against `origin/main`. The claimed base is then not necessarily a commit on the remote that will receive the candidate; it may not exist there at all. No behavior is stated for that reachable test-seam invocation. Confidence: sure.

6. “repository-relative paths, normalized: no absolute paths, no `..`, nothing under `.git/`” — This validation leaves symlink traversal unspecified. A declared repository-relative symlink can point outside the checkout without containing `..` itself; reading it follows the target and can commit external bytes as the declared path. That violates the stated worktree-content boundary and leaves the result of this reachable path form undefined. Confidence: sure.

7. “after a fetch … every caller gets the exact right value deterministically” — A fetch can fail while an old `origin/main` still exists locally; `merge-base` can then succeed against stale data. The document neither requires fetch success nor gives its failure an outcome, so the computed base can be stale despite the exactness claim. Confidence: sure.

8. “the legacy repository” / “unreadable legacy checkout” — The request syntax provides no legacy-checkout location or selection rule, yet importing requires one and the documented failure requires the caller to recover from it. The referenced executable has a `--legacy-repo` input, but this specification never documents it. A future caller cannot form a portable import request from this document. Confidence: sure.

9. “The artifact-lifecycle rule (the founding plan’s standing rule for which work gets an issue and when)” — This is the rule that decides whether `--issue` is `none` or a number, but it has neither a definition nor an explicit path to read. “Trivial work” is not a usable decision rule either. An agent with the allowed context cannot determine the required field value consistently. Confidence: sure.

10. “Every invocation prints exactly one JSON object on stdout” — Invoking the referenced program with no subcommand, or `check-in` without a required parser argument such as `--files`, produces argparse usage text and exit 2, not JSON. These are ordinary invocations and directly contradict the absolute contract and the catalog’s promise that malformed fields are catalog refusals. Confidence: sure.

11. “a retained B4d refusal record (returned once in the full three-part form, then swept)” — Two simultaneous `status <digest>` calls can both observe the record before either sweeps it, or one can sweep it while the other reads. No atomic consume/locking rule or outcome for the loser is stated, so “once” is not executable under the design’s concurrent-caller model. Confidence: sure.

12. “`git log origin/main --grep "Gatekeeper-import:"` lists every import” — `origin/main` is a local tracking ref and can be stale. A caller who has not fetched since a later import will not see that import, so the command does not literally list every import. Confidence: sure.

13. “SCREENING (synchronous, in memory, nothing on disk)” — This conflicts with the procedure’s explicit statement that “the built program creates the workspace clone during screening.” It leaves crash handling and the state model ambiguous; the state description also has an unclosed `WORKING (` parenthesis, obscuring where the transition to `PUSHING` belongs. Confidence: sure.

14. “WORKING (candidate built and checked …) → PUSHING” — No named state covers a detached worker while it is cloning, constructing the candidate, or running checks. That interval is observable by `status`, especially in `--no-wait` mode, but is excluded both from diskless `SCREENING` and from the described post-check `WORKING` state. Confidence: sure.

15. “`<workspace-root>/<digest>/`” and “discoverable from the digest alone” — The digest deliberately contains base, paths, bytes, and import data, but not repository or remote. Two concurrent test-seam requests against different remotes with the same base and declared bytes therefore use the same global workspace and can overwrite each other’s candidate, request record, PID, or cleanup. The store has no stated collision behavior. Confidence: sure.

16. “absent means the leftover workspace is swept and the work runs fresh” — A caller can lose its connection while its detached worker continues. A resubmission then finds no digest in history but does find a live workspace; this rule sweeps it, despite the separate `status` rule that distinguishes live `WORKING` from `abandoned`. The recovery procedure does not say how resubmit detects or preserves the live worker. Confidence: sure.

17. “**`cancel <digest>` — built in version 1” — This conflicts with the implementation-status statement that slice 4, including `cancel`, “remain contract-only” and reaches `unbuilt-option`. It gives incompatible instructions about whether an agent can use cancellation now. Confidence: sure.

18. “live worker found → kill it, sweep the workspace, `cancelled`” — Killing the worker process does not necessarily kill a child process already running a check or `git push`. A child push can complete after history is queried and `cancelled` is returned. The design gives no process-group, wait, or late-push outcome, so cancellation can report success while the check-in later reaches main. Confidence: sure.

19. “the account’s name is recorded here verbatim when the amendment is applied” — The required dedicated account is unnamed. An agent asked to apply the already-ruled amendment cannot configure branch protection, create the correct credential, or verify the result without an additional identity decision; the document provides no completion condition for that decision. Confidence: sure.

20. “The copy keeps itself current from main automatically (no manual deploy step; a checked-in fix is live on the next call)” — The document specifies a root-owned file and a sudoers rule scoped to the program, but no updater, authority, trigger, integrity check, or failure behavior for updating that root-owned file. The claimed automatic deployment is therefore not executable from this design. Confidence: sure.

21. “a stale copy … can never be made to run agent-written bytes” — This conflicts literally with the preceding automatic-update claim. A gatekeeper-source change written by an agent, walked, and checked into main is specifically supposed to become the next deployed copy. “Agent-written” is unqualified, so the two statements cannot both hold. Confidence: sure.

22. “a foreign remote dies at GitHub’s authentication because the credential is scoped to this one repository” — `--remote` accepts more than GitHub remotes. A writable local bare repository is an ordinary Git remote and requires no GitHub authentication, so it is a counterexample to the stated reason for omitting a privileged-mode guard. Confidence: sure.

23. “The raw-push residual is *detected at its source*, not prevented: a standing **branch-protection audit** at each handoff scrub” — The stated audit checks configuration, not commits. Before C2, anything running as the permitted account can raw-push while protection remains perfectly configured; this audit reports `protection-ok` and does not detect the bypass. It is also currently contract-only under slice 5, and “handoff scrub” has no procedure here or in the referenced handoff design that makes the audit run or consumes `audit-failed`. Confidence: sure.

24. “once C2/C3 apply, a trailer-less commit can arise only from break-glass … or from a protection failure” — C2/C3 restrict credentials and account ownership; they do not prove that the gatekeeper program always writes trailers. A regression or defect in its commit-construction path can push a trailer-less commit through correctly configured protection, making this “only” claim false and leaving the removed detector’s case unaddressed. Confidence: sure.

25. “Never — `status` derives from history” — This conflicts with the reply definition: `in-progress`, `abandoned`, and retained refusal records come from the workspace, not history. Removing the separate audit log does not make `status` history-derived. Confidence: sure.

26. “T5 conflict: same-content collision refuses” — The concurrency rule defines conflict by overlap in changed **paths**, not equal content. Equal final content is not necessarily a conflict, while different content in the same path is. The acceptance-test index therefore names a different condition from the contract it is meant to test. Confidence: sure.

27. “T8 cancel: all three outcomes” — The cancellation section defines “Outcomes, exactly four”: already checked in, live worker, abandoned/refusal workspace, and nothing found. The test index’s three-outcome requirement cannot verify the stated contract. Confidence: sure.

28. “The walked-approval evidence format … — undesigned; slice 6 waits on it,” alongside “instruction-bearing text … whose check-ins require walked-approval evidence” — The required evidence is neither defined nor reachable through an explicit local path, yet it is required for the designated artifact class and for privileged-lane activation. A future agent cannot determine what constitutes approval, validate it, or know when the prerequisite is complete. Confidence: sure.

clean sections: The trailer; Constructive guarantees, the advisory, and the growth point; Concurrent check-ins; Cross-spec consequence (resolved); Relationship to the legacy design
