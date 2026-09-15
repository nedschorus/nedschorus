---
name: sanity-check
description: Give a design, a specification, a skill or a plan its sanity-check after its cold read has passed. Three sanity-check-attacks, each run by two fresh sanity-check-cells, ask what should be cut, which English instructions should be code, and what an independent designer would build from the problem alone. Run it by deliberate decision, never automatically, and never on a record of what happened.
---

# sanity-check

## When used

After the document's full cold read has passed and its findings have landed, and before the document lands on main. Confirm the cold read first: a cold-read-record for the document's current text exists, or you run /cold-read now. Only by a deliberate decision, yours or the user's: never wired into automation, and a revision of an already-checked document earns no automatic rerun. Never on a record, a document that only reports what happened. A pull request carrying a design, specification, skill or plan with no sign of a past sanity-check may have one suggested, as a note, never as a gate. A run is six sanity-check-cells, three attacks on two runtimes, each a full model run at high effort taking tens of minutes; say so when you suggest it.

## The words

A **sanity-check-attack** is one stance the instrument takes on the document: the cut-attack asks what should be deleted, the mechanization-attack asks which English instruction should be code, and the fresh-eyes-attack builds an independent design from the problem alone. A **sanity-check-cell** is one fresh agent running one attack on one runtime. A **sanity-check-request** is the file you write for the fresh-eyes-attack: a problem statement plus off-limits and read-first lists. A **sanity-check-record** is the directory one run leaves behind. All four are glossary headwords.

## What to do

1. Read the runner's manual: `scripts/sanity-check-attacks.py --print requester`. It is the operating-rules home; this skill does not repeat it.
2. Write the sanity-check-request exactly as the manual's last section says: the problem statement extracted from the document's current text at a named commit, plus the off-limits and read-first lists. State what the system must accomplish, never how the document does it, and leave out every name the document coined. Save it outside the worktree, in your session scratchpad, so the runner's write detector never sees it. Without it the fresh-eyes-attack is skipped, loudly.
3. Run `scripts/sanity-check-attacks.py --target <path> [--context <path> ...] --problem-statement <request>` as a background task. `--context` names the documents the target cites that a reader needs open beside it. Arm a Monitor, the harness's watch tool, on its output, as /cold-read does, for these lines: `saved:` means a report landed and can be read now. `FAILED:` means a cell produced no report; the runner's closing text says whether to rerun that attack alone with `--attack`. `SKIPPED:` means the fresh-eyes-attack had no request. `WARNING:` means either a quoted span was found in no tracked file, which you check against git history and the web, or a cell modified the worktree, which you inspect and revert before triage. `LEAK-WARNING` means your request contains a name the document coined; a hit on the off-limits paths is expected and needs nothing, a hit elsewhere you follow up. While the run is in progress, change nothing in the worktree, the sanity-check-record included: the write detector cannot tell your edit from a cell's.
4. Reports land in the sanity-check-record, `sanity-check-records/<date>-<target-stem>/`, gitignored, one per cell, each opening with a provenance line that names the commit the cell read. Read each as it arrives, and keep your judgments provisional until all six have reported or failed. When a cell has failed for good, triage its attack from the report you have and say so in `dispositions.md`.
5. Triage. Follow up every warning. Settle a hedged claim about code by reading the code. Merge the two runtimes' reports for each attack, because the same finding from both is one finding. A cut-attack finding names text to delete and why nothing depends on it; a mechanization-attack finding names an English step and the code that should replace it; the prompts say what each returns. For the fresh-eyes-attack, compare the fresh design and the original on their merits: a substantive difference is a question; a failure mode the fresh design handles and the original never addresses is a finding; the stronger parts of either can feed a best-of-both proposal. Findings are design changes, and none is applied without the user's ruling.
6. Walk the surviving findings with /walk-me-through (`.claude/skills/walk-me-through/`), one at a time, most important first. You answer each finding with a fix you propose, not a rewording, and the user rules on it (user-ruled 2026-09-04, recorded on https://github.com/nedschorus/nedschorus/issues/263). Record every warning and every finding you set aside, with the reason, in `dispositions.md` beside the reports; it has no fixed form beyond that. Triage is complete when every warning and every finding has been ruled on or set aside with a stated reason.
7. Keep the sanity-check-record after the work it served lands: review records are logs (user-ruled 2026-08-25). The runner's manual still says to delete it; the ruling is later and governs.
8. Commit the ruled changes on the topic branch, and name the sanity-check-record's directory in the pull request description, as cold-read records are named.

## The user's bar for a reviewer

From the walk of 2026-08-10: "asking to simplify is like asking to optimize without context." Name the axis a finding is judged on. This project's axis is simple-to-operate over simple-to-build; mechanical guarantees over trained habit; a detector with no consumer is cost without value; never trade a deterministic script for probabilistic agent behavior.

## What it is not

It is not the cold read. /cold-read reviews prose for a fresh reader; this instrument attacks what the document does. They are separate instruments by ruling (2026-08-17), and this one runs second. The attack prompts are `docs/agents/sanity-checker-<attack>-attack-prompt.md`; the runner takes any number of attacks, so the fourth planned on https://github.com/nedschorus/nedschorus/issues/121 needs no change here.
