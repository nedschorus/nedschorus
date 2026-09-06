---
status: research recommendations
research-as-of: 2026-09-06
disposition: queued for user review
---

# Existing components to reuse before adding external machinery

**Two of the clearest improvements are already described in NC's own queue. They primarily need integration or a narrow missing check, rather than an external dependency.**

**Reference integrity: grow the existing checker.** [#42](https://github.com/nedschorus/nedschorus/issues/42) asks for relative-link resolution and validation of revision/path citations. The overlap is documented in [docs/issues/queue/42-commit-pin-resolution-and-drift-lint-overlap.md](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/docs/issues/queue/42-commit-pin-resolution-and-drift-lint-overlap.md). Current [scripts/md-drift-lint.py](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/scripts/md-drift-lint.py) already has resolve, check_markdown_links, and lint_markdown, with tests in [scripts/md-drift-lint-test.py](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/scripts/md-drift-lint-test.py). Current [scripts/cold-read-grid.py](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/scripts/cold-read-grid.py) also has reference_integrity_pre_pass, which extracts path-like candidates and writes leads rather than verdicts.

Recommend one shared resolution implementation with reporting appropriate to each caller. The grid's heuristic candidates are not automatically lint failures: examples, foreign repositories, and intended install locations need their existing distinctions. Add the missing revision/path check to this common work rather than building a second reference-integrity program that rediscovers what exists.

The queue's cross-repository examples are useful acceptance cases. Resolve a citation in the repository it identifies. An unavailable foreign repository is unresolved evidence, not proof that the citation is false. Stamp new revision identifiers from Git mechanically when an artifact is generated; do not ask an agent to remember the hash.

**Prose claims about code: add only the missing context.** The queued [code-claim verification gap](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/docs/issues/queue/cold-read-cannot-check-claims-about-code.md) records four real mismatches that a minimal-context prose review could not establish. The current [defect-hunt prompt](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/.claude/skills/cold-read/prompts/defect-hunt.md) deliberately limits context. The current [PR review rule](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/CLAUDE.md) excludes ordinary prose findings from PR review.

Recommend the queue's separate code-claim verification pass, initially run only for a document that makes implementation claims. Give that checker the relevant claims, the named source paths at a fixed revision, and the requirement it must compare. Let it return verified, contradicted, or unresolved findings with source evidence. A path or symbol's existence can be checked mechanically; what the code actually guarantees can require execution or agent judgment.

This is a separate authoring-time task. It preserves the existing Cold Read context boundary and PR review scope. It should not turn every prose review into a repository-wide search. The existing [#219](https://github.com/nedschorus/nedschorus/issues/219) proposal for documents that point to built code can reduce the number of duplicated claims that need checking in the first place.

**Gate checks: preserve the existing attachment point.** [scripts/main-gatekeeper.py](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/scripts/main-gatekeeper.py) — integrate_and_push — rebuilds a candidate, contains the placeholder for future checks, and calls attempt_push. The missing wiring is already recorded in [docs/issues/queue/3-gatekeeper-checks-never-run-at-check-in.md](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/docs/issues/queue/3-gatekeeper-checks-never-run-at-check-in.md) under [#3](https://github.com/nedschorus/nedschorus/issues/3). When gate activation and check selection are addressed, attach verification to the actual candidate revision there, after each reapplication. This is not a reason to introduce LangGraph or a parallel promotion service. The gate remains dormant under the inspected CLAUDE.md rules.

**First work item.** Resolve issue 42's ownership and shared-reporting question, then implement its missing revision check against the existing checker tests. Keep the code-claim check as its own bounded design decision. These recommendations point to existing owners rather than creating duplicate issues.
