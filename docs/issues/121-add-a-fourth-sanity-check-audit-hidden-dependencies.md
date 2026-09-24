---
issue: "[Add a fourth sanity-check audit: hidden dependencies, untestable claims, criteria vs intent (user-ruled 2026-08-21)](https://github.com/nedschorus/nedschorus/issues/121)"
---

# Add a fourth sanity-check audit: hidden dependencies, untestable claims, criteria vs intent (user-ruled 2026-08-21)

The sanity-check instrument (`scripts/sanity-check-attacks.py`; its docstring is the operating-rules home) runs three audits — cut, mechanization, fresh-eyes — each on both runtimes, so every audit is a pair of agents. The user ruled on 2026-08-21 to add a fourth audit covering three hunts none of the standing three carries by name. This amends his 2026-08-17 ruling that fixed the shape at three stance audits — reopened by the ruler; the seat brief (`docs/agents/sanity-checker-instructions.md`, § The standing shape) points here until the build lands.

Origin: an adversarial-review checklist the user read — find contradictions, ambiguous terms, hidden dependencies, untestable claims, missing failure modes, and places where an implementation could pass the written criteria while still violating the intent. Mapped against the instrument: contradictions are the cut audit's ("Internal consistency is yours"); missing failure modes are fresh-eyes' (Hard parts, Late discoveries, and payoff sentences that name failure modes since commit 5e2ed7a, branch doctrine-queue-drain); ambiguous terms are md-review's, which runs first by rule. The remaining three are this audit's charter — one stance, reading the document adversarially as a specification:

- **Hidden dependencies** — what the design silently depends on but never states.
- **Untestable claims** — what it asserts that cannot be tested or falsified.
- **Criteria vs intent** — where its written criteria could be satisfied while its intent is betrayed.

Two boundaries the prompt must draw, or it poaches from siblings: mechanization's Verify question asks whether code can check a step's output — this audit asks whether the document's claims and criteria can be tested at all. Fresh-eyes' Assumptions section surfaces what the problem statement left unsaid, blind to the design — this audit reads the design and hunts its own unstated dependencies.

Build path, mirroring how the standing three earned their STANDING headers: draft the prompt (name it per the multi-part naming convention, grep-checked); md-review it; walk the findings; STANDING header; register it in the runner (an `ATTACK_PROMPT_FILES` entry plus docstring lines — the infrastructure is audit-count-agnostic). The two queued first-run sanity-checks (mechanization and fresh-eyes prompts as targets) run on the standing three and do not wait for this build.

Search receipt: `gh issue list --state all --search "sanity-check audit"` and `--search "sanity"` (2026-08-21) returned no issue covering the instrument's stances; `scripts/ghi-info-ask.py` is absent from this checkout.

— filed from session https://claude.ai/code/session_01F9s9L5vPfehGRgrDHoc4Pk (doctrine-queue-drain seat)
