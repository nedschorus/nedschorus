---
issue: "[Review the legacy system's bad-phrase list (command-vocabulary.md): add the status-inflation fail-indicator class ('standing doctrine') and pick NC's enforcement mechanism](https://github.com/nedschorus/nedschorus/issues/14)"
---

# Review the legacy system's bad-phrase list (command-vocabulary.md): add the status-inflation fail-indicator class ('standing doctrine') and pick NC's enforcement mechanism

## Commission

Review the legacy system's bad-phrase material, extend it with the newly ruled fail-indicator class, and pick NC's enforcement mechanism.

1. **Review the legacy system list and its lookers (all verified 2026-07-22):**
   - The list: [docs/wiki/reference/command-vocabulary.md](https://github.com/nedlern/nedlern/blob/main/docs/wiki/reference/command-vocabulary.md) — § Overloaded Words to Avoid, § Deceptive Phrases That Hide Intent.
   - Session-scan detection: [.claude/skills/scan-errors/SKILL.md](https://github.com/nedlern/nedlern/blob/main/.claude/skills/scan-errors/SKILL.md) — pattern 17 (cargo-culting peer vocabulary), a deceptive-phrase check that cites the page directly, and the v3 turn-final false-progress phrase check.
   - Live hook enforcement (one class only): [.claude/hooks/postal-softener-guard.py](https://github.com/nedlern/nedlern/blob/main/.claude/hooks/postal-softener-guard.py) with companion [test-postal-softener-guard.py](https://github.com/nedlern/nedlern/blob/main/.claude/hooks/test-postal-softener-guard.py) — a PostToolUse REMIND (not a block), fail-open, single source registered in both runtimes (Claude via settings.json; CDX via scripts/run-sonnet-remote-agent.sh). Its motivation is the key precedent: the text-only softener ban demonstrably failed against reflexive training defaults ([nedlern/nedlern#1513](https://github.com/nedlern/nedlern/issues/1513)); the moment-of-action nudge is what holds.
   - Search receipt for "no other enforcement": `git grep -iln "softener|no rush|when convenient|deceptive phrase|banned phrase"` over `.claude/hooks/`, `scripts/`, `config/` — only the guard, its test, its CDX registration, and text mentions.

2. **Add the status-inflation class (boss-ruled 2026-07-22, a "100% fail indicator"):** phrases that declare a fresh or informal thing established — "standing doctrine" is the ruled specimen (live instance: new-vp called a ninety-second-old convention "standing doctrine" during the founding walk). The review hunts the class, not just the phrase — sweep for siblings ("is now doctrine," "established practice," "landed as doctrine") and classify hits. Related legacy work in flight: the "doctrine sentences are selected toward over-claiming" clause being drafted for wiki-page-standards.md (legacy wiki keeper, 2026-07-22 fleet status).

3. **Pick NC's enforcement mechanism:** candidates, informed by the softener-guard precedent (doctrine text alone loses to training reflexes; a fail-open moment-of-action remind holds) and NC's writing-time-enforcement pattern (skills enforce at writing time, not the git-gatekeeper): embed the check in `md-write`/`ghi-write`/`d-review` at their step-1 builds; a remind-class lexical hook like the softener guard; scan-at-ceremony. Decide with evidence.

## Trigger to close

The list is reviewed and updated (legacy page edited or NC successor page created at the step-3 wiki walk), and the chosen NC enforcement mechanism is ruled and recorded — likely landing with the step-1 writing-skill builds.

Session: 135a4f6d (new-vp)
