---
issue: "[Cite files by name, not by path](https://github.com/nedschorus/nedschorus/issues/610)"
---

# Cite files by name, not by path

"What points at this file?" has three different correct answers in this repository, nothing marks which one applies, and the cheapest method — search for the path — is the one that works least often.

**The behaviour, named.** On 2026-09-21 a seat verified that moving `handoff-supervisor.py` out of `scripts/` had broken nothing, by searching the merged tree for `scripts/handoff-supervisor.py`. Zero hits, reported as a pass. That text appears nowhere in the repository and never did — the live reference is `Path(__file__).with_name("handoff-supervisor.py")`. The search could not have returned anything whether the move was clean or broken. It happened to be clean.

**Measured on main, 2026-09-21.**

- Of 62 non-test programs, **15 are referenced by name and by no full path at all**. A path search is blind to a quarter of them. Searching by name finds every reference a path search finds, plus those 15.
- Composed references rooted at the repository: 88. Rooted at runtime locations that genuinely vary (scratch directories, a seat's worktree, the log-store): 87. A further 413 cannot be classified without reading the surrounding code.
- Ten filename families are assembled at runtime from suffix constants, so no text search can find them even in principle.
- **File names are already unique**: 286 files, 277 distinct names. The only three repeats are names the project does not choose — `SKILL.md`, `README.md`, `.gitkeep`.

**Proposed:** cite a file by its name rather than its path wherever the name identifies it; keep names unique, which costs nothing today; cite by path only for the handful whose names cannot identify them; and build a uniqueness check, which compares the tree against itself and so cannot go silently blind as the thing it watches moves.

**Open and unresolved:** the user ruled "always write paths out" before these measurements were taken, and they point the other way. That reversal is his to confirm. Also open: whether a directory should declare itself stable or working, which is what the 413 unclassifiable references wait on.

**Next action:** walk the paired GHI-MD with the user. It carries the full measurements and the open questions. It has had its cold read; the walk settles the reversal and the stable/working question.

**Neighbours, checked before filing and none of them this:** [Reference-integrity checker](https://github.com/nedschorus/nedschorus/issues/42) is the instrument that would host the uniqueness check, and covers links resolving and revision-paths existing, not citation style. [Rationalize the repository layout](https://github.com/nedschorus/nedschorus/issues/224) holds the measured stale-path-after-a-move evidence. [Sort the 60 standing md-drift-lint findings](https://github.com/nedschorus/nedschorus/issues/572) is the live backlog this rule would reduce at source.
