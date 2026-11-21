---
issue: "[Record each agent-seat's terminal output in the log-store for 7 days, as the user ruled](https://github.com/nedsnodes/nedsnodes/issues/4060)"
---

# Record each agent-seat's terminal output in the log-store for 7 days, as the user ruled

## What is wrong

The handoff-system design, `nn-systems/handoff/handoff.system.design.md`, records this user-ruling under User-rulings: "Each agent-seat's terminal output, on ned-box and on the Mac, is recorded in the log-store and kept 7 days (user-ruled 2026-11-05), because the user steps in more than once a day and nothing else shows what an agent-seat's terminal showed when it stalled." The sentence says the output is recorded, in the present tense, in a design whose front matter says `status: built`; no program found does it:

- `grep -rln "pipe-pane" scripts nn-systems .claude` on main at 55626cb48 found nothing, and `grep -rln "terminal output"` over `docs/nedsnodes-wiki`, `nn-systems`, `scripts` and `.claude` found only that sentence and a line of `docs/nedsnodes-wiki/nedsnodes-file-naming-and-location-standards.md` about the `-capture` suffix.
- The launchers `scripts/launch-claude-ubuntu` and `scripts/launch-claude-mac` mention neither the log-store nor tmux's capture or history settings.
- The log-store, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/`, has no directory for terminal output (listed on 2026-11-20).
- Neither the design's components list nor the handoff-system's nc-architecture-overview, `docs/nedsnodes-wiki/nedsnodes-handoff-architecture-overview.md`, names a part that records terminal output.

A program under a name none of these searches hit could still exist (unverified).

The finding comes from three reviewers of the cold-read-full-run `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/handoff.system.design-2026-11-20-6`; its `cold-read-triage.md`, in that directory beside the reports named here, gives each of these findings the link of the GHI filed from this file: `claude-hunt-deep.md` 33, `claude-hunt-second-strongest-model.md` 42 and `codex-hunt-second-strongest-model.md` 9.

## Why it matters

The user gave the reason with the ruling: when an agent-seat stalls, nothing else shows what its terminal showed. While the recording does not exist, an agent asked why an agent-seat stalled has nothing to read, and the design tells it the record is there.

## Next action

The agent-seat that takes up this GHI first writes a test that fails when an agent-seat's tmux session starts with no recording of its pane, whichever program starts it: the launchers, `scripts/recover-crashed-seats.py`, `scripts/resupervise-seat.py`, or the restart at login. If the test passes on main, the recording exists: it records where in this GHI-MD, in the design and in the nc-architecture-overview, and closes this GHI. If it fails, it builds the recording in one pull request with that test: a recording of each agent-seat's pane on each machine, kept in a log-store directory whose name it checks with the naming page, `docs/nedsnodes-wiki/nedsnodes-how-to-choose-a-name-for-files-code-and-glossary-terms.md`; on the Mac, a local copy shipped to ned-box, since the log-store is there; a scheduled job on each machine, in `nn-systems/general-tools/scheduled-jobs-on-each-machine.json`, that deletes recordings older than 7 days and leaves the file of a pane still open; a test of each; and a line in the design and in the nc-architecture-overview that names the program.
