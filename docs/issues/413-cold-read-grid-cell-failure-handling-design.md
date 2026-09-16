---
status: design, not yet cold-read or reviewed; tracked in nedschorus#413
design-as-of: 2026-09-16
---

# cold-read-grid: what happens when a cold-read-cell fails

The design for [nedschorus#413](https://github.com/nedschorus/nedschorus/issues/413). It changes how `scripts/cold-read-grid.py` handles a cold-read-cell that produces no review: it retries the cold-read-cell once, says why it failed, says so once when a whole runtime is down, and closes every run with one text. It follows the user's rulings of 2026-09-11 and 2026-09-14, quoted in the issue. The sequence he set is this design, its cold read, his review of that cold read, and only then code.

Terms are the glossary's (`docs/nedschorus-wiki/nedschorus-glossary.md`). A runtime is the command-line tool a cold-read-cell drives, `claude` or `codex`. "The skill" is `.claude/skills/cold-read/SKILL.md`. The fixture rule of 2026-09-02, cited below, is recorded in [nedschorus#18](https://github.com/nedschorus/nedschorus/issues/18): a fixture standing for an external system's output is generated from the real command's output, with the capture command and the machine recorded beside it.

## 1. What happens today

Facts from origin/main at 4640351. Line numbers are that commit's.

- **No retry.** Each cold-read-cell tries one model once. Every model chain in `scripts/cold-read-claude-cell.py` (lines 110-113) and `scripts/cold-read-codex-cell.py` (lines 108-111) holds a single model, so a failure exits 1 at once and the `FELL BACK:` line cannot fire.
- **No cause.** The grid prints `FAILED (exit N): <name> (stderr kept: <log>)`. Its only look at the error is a bare substring test for `401` or `Not logged in` in the log's last 2,000 characters (`scripts/cold-read-grid.py` lines 503-506), which no test covers.
- **No grouping.** On 2026-09-10 the Claude account's session limit failed all three Claude cold-read-cells within seconds, in each of eight cold-read-records. The grid printed three unrelated `FAILED` lines and the Opus stop text. When all three Codex cold-read-cells fail, it prints "All six reviews are complete".
- **Opus is special.** The closing text is `OPUS_ABSENT_INSTRUCTIONS` ("Stop here … Wait for Opus to come back") when either Opus cold-read-cell failed, `COMPLETION_INSTRUCTIONS` otherwise, with a separate Fable-only note (lines 591-643). The user rejected this on 2026-09-11: "why is opus special? I don't think it should be."
- **No timeout.** Neither the grid's `Popen` nor the cold-read-cell's `subprocess.run` has one. The grid polls every 5 seconds until all six exit.

## 2. The rule every part of this design keeps

**A cause changes what the grid says, never what it does.** Whether a cold-read-cell is retried, whether it counts as absent, whether the set is valid, and the exit code depend only on whether a report landed. The cause decides the wording of a line and nothing else.

The reason is that causes are read from text, and text lies. A cold-read-cell's log mixes the runtime's own error lines with the model's output, and the Codex runtime echoes the document under review into its log. A search of the kept Codex logs in the log-store on 2026-09-16 found no Codex quota message at all, but many lines of quoted documents. This design quotes "You've hit your session limit" itself. When the grid cold-reads this design, a failed cold-read-cell's log may carry that sentence without the account being out of anything. If a misread cause could skip a retry or void a set, that would be a defect. Because it can only mislabel a line, it is a wording error the kept log corrects.

## 3. Retry once, in the grid

When a cold-read-cell exits without a report, the grid relaunches the same cold-read-cell once, with the same model and the same arguments, at once, while the other cold-read-cells keep running. No cold-read-cell is special, and there is no delay and no change of model.

- The retry lives in the grid, not inside the cold-read-cell. The grid is what sees the first failure and can report it, and one relaunch there covers both runtimes and every way of failing, including a runtime that cannot be started.
- The first attempt's log is renamed to `<report name>.attempt-1.stderr.log` before the relaunch, so the second attempt cannot overwrite it. The log always exists by then: the grid opens it when it launches the cold-read-cell program, which always starts, and a runtime that cannot be started is reported by that program into the log. Both logs are shipped with the cold-read-record.
- The grid prints, at the first failure, `RETRYING: <name> — <cause> (first attempt's log kept: <log>)`.
- A retry that lands its report prints `saved:` as today. The first attempt's log is kept, since it records a failure that happened.
- A retry that fails prints `FAILED (exit N): <name> — <cause> (stderr kept: <log>)`, with the second attempt's cause. The line keeps its present opening, so the skill's Monitor still catches it. The cold-read-cell is now absent, and its cause from here on is the second attempt's, even when the first attempt's differed.

A retry is not suppressed for a cause a retry cannot fix, such as a logged-out runtime. The ruling says every failed cold-read-cell is retried, a retry against a logged-out runtime fails in seconds, and suppressing it would make the cause decide what the grid does, which section 2 forbids.

## 4. Naming the cause

The cold-read-cell program (`scripts/cold-read-claude-cell.py` or `scripts/cold-read-codex-cell.py`), not the grid, classifies its own failure, because it holds the runtime's exit status and output separately from anything the grid sees. On a failed attempt it prints one status line to its own standard error, which the grid captures in the attempt's log:

`<program>: cause: <class> — <detail>`

`<program>` is the cold-read-cell program's name, as in `cold-read-claude-cell`. The grid finds the line by the prefix rule of [#244](https://github.com/nedschorus/nedschorus/issues/244), the `cell_status_line` function, which accepts a line only when it starts with the program's name. The same rule of reading a line by its start governs the cold-read-cell program's own reading of the runtime's output, below.

The classes, and what recognises each. Every recognised text must be a real one, captured from a runtime, because the fixture tests in section 8 are built from them. The two limit lines below were found in the log-store's 82 kept cold-read-cell logs on 2026-09-16, each at the start of its own line.

| class | recognised by | whose to fix | runtime-wide |
|---|---|---|---|
| `account-limit` | a runtime output line starting "You've hit your session limit"; the detail carries the reset time when the line gives one ("resets 8:50pm") | wait for the reset | yes |
| `model-limit` | a runtime output line starting "You've reached your" whose next words name a model and the word "limit", as in "You've reached your Fable limit."; the detail names the model | wait, or the user's usage settings | no, that model only |
| `logged-out` | the line each runtime prints when it has no credentials, captured before this class is built (see below) | the user logs in | yes |
| `runtime-missing` | the runtime binary could not be started (the cold-read-cell's `FileNotFoundError` token) | the user installs it | yes |
| `no-report` | the runtime exited 0 but no report was found (the existing `no-report` token) | nobody; a model misbehaved | no |
| `exit-N` | anything else | unknown; the kept log says | no |

Matching runs only on the runtime's output on a failed attempt, and a line qualifies only by how it starts, never by text found somewhere inside it, as #244 requires. Once a line qualifies by its start, the rest of that same line may be read for detail, such as a reset time or a model name.

Nothing is guessed. No logged-out text exists in the log-store, so the build captures one before writing that class. The agent building this runs each runtime by hand, once, with an empty configuration directory, which fails for want of credentials without touching the real login, and records the command, the machine and the output beside the fixture, as the 2026-09-02 fixture rule requires. Today's grid tests for "401" and "Not logged in" anywhere in the log's tail. That bare substring test is removed, not carried forward. Codex has no recognised limit texts either, because none has been captured, so a Codex quota failure lands as `exit-N` until a real one is captured and added.

## 5. Saying once that a runtime is down

The user's point of 2026-09-14: "If opus is down, claude is down, so that should be reported."

When every cold-read-cell of one runtime is absent after its retry, and all of them failed their second attempt with the same runtime-wide class, the grid prints one line:

`RUNTIME DOWN: claude — account-limit, resets 8:50pm; 3 of 6 reviews lost`

It prints the line when the last of that runtime's cold-read-cells becomes absent. When the cold-read-cells report different reset times, the line gives the latest one. When none reports a time, the line gives none. When both runtimes are down, the grid prints one line for each, Claude first, in the order the roster launches them.

It does not print that line in two cases, both real:

- **A model limit is not the runtime being down.** On 2026-09-11 the Fable cold-read-cell failed on "You've reached your Fable limit" while both Opus cold-read-cells succeeded. That is one absent review with class `model-limit`, reported as such.
- **Absent reviews with different or unrecognised causes are not called an outage.** They are listed one by one in the closing text. Three `exit-N` failures on one runtime are three facts the grid cannot join into one.

The rule counts cold-read-cells, not models, so it holds when the roster changes. Today Opus runs two of the three Claude cold-read-cells.

## 6. One closing text

The two Opus branches and the Fable-only note are removed. The target-changed text keeps its precedence, because a document that moved during the run voids the set whatever else happened. Otherwise every run closes with one text, filled in from what landed:

- **All six landed:** "All six reviews landed in {record_dir}. The set is complete." Then the triage instructions as today.
- **Some landed:** "{k} of 6 reviews landed in {record_dir}. The set is valid and incomplete: triage the reports that landed." Then the absent reviews, then any `RUNTIME DOWN` lines.
- **None landed:** "No review landed in {record_dir}, so there is nothing to triage." Then the absent reviews, then any `RUNTIME DOWN` lines, and: "Start a new cold-read-full-run when the cause is cleared."

Each absent review is one line: `- <name>: <class> — <detail> (log: <path>)`.

In every case with an absence, the text ends with the causes the user can act on, gathered into one sentence: "Tell the user now: <causes>." The classes that go there are `logged-out`, `runtime-missing`, `account-limit` and `model-limit`, with the reset time where there is one. A cause shared by several cold-read-cells is named once, as `<runtime> <class> — <detail> (log: <path of one of them>)`, and causes are joined by semicolons. Because a cause can be misread (section 2), each carries the path of a kept log it came from, so the user can check it. This carries out his words of 2026-09-11: "what failed and why … should be reported asap, in case it's something the user can fix". The `RETRYING:` and `FAILED` lines already surface each cause as it happens. The closing sentence makes sure the agent passes it on.

**Exit codes do not change.** 0 means complete. 1 means at least one review is absent, including all six. 3 means the target changed. An agent reads the closing text, not the code, and anything that tests the code today keeps working.

## 7. The marker on every report

When the set is incomplete, the grid writes one line at the top of every report that landed, by the mechanism that already writes the target-changed marker (`scripts/cold-read-grid.py` lines 296-338):

`<!-- INCOMPLETE SET: 2 of 6 reviews absent — claude-hunt-good (account-limit, resets 8:50pm), claude-terminology-good (account-limit) -->`

A reader who opens one report in the log-store months later then knows the set it belongs to was missing reviews, and which ones, without the closing text that has scrolled away.

## 8. Tests

The Opus-absent and Fable-only tests in `scripts/cold-read-grid-test.py` are rewritten to pin the single path. New cases, each against the stub runtime the grid tests already use:

- A cold-read-cell fails once and lands on retry. Expect `RETRYING:`, then `saved:`, a complete set, exit 0, and the first attempt's log kept.
- A cold-read-cell fails twice. Expect `RETRYING:` and `FAILED` with the cause, the valid-and-incomplete text, the marker on the five reports, and exit 1.
- All three Claude cold-read-cells fail with `account-limit`. Expect the `RUNTIME DOWN` line with the reset time, and the reset in the "Tell the user now" sentence.
- The Fable cold-read-cell fails with `model-limit` and the others land. Expect no `RUNTIME DOWN` line.
- A cold-read-cell fails with `account-limit`, then its retry fails with `exit-1`. Expect `RETRYING:` naming the first cause and `FAILED` naming the second, and no `RUNTIME DOWN` line from that cold-read-cell.
- Three Codex cold-read-cells fail with `exit-N`. Expect no `RUNTIME DOWN` line, and three absences listed.
- All six fail. Expect the none-landed text and exit 1.
- **A document under review quotes "You've hit your session limit" on a line of its own, and a Codex cold-read-cell echoes it, then fails with `exit 1`.** Expect the retry to happen and the set's validity to be unchanged. The label may read `account-limit`. That label is what section 2 accepts, and the test pins that nothing else moves.

The classifier gets its own cases in `scripts/cold-read-cell-common-test.py`. Their inputs are the real lines captured from the log-store, per the 2026-09-02 fixture rule, each citing the cold-read-record it came from: `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-10-design-to-main-test-writing-agent-instructions/` for the session limit, and `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-11-SKILL-2/` for the Fable limit.

## 9. The skill text that changes with it

These are operative prose, walked with the user before they land:

- **Step 5's Monitor list** gains `RETRYING:` and `RUNTIME DOWN:`. The `FAILED` sentence changes to say a cold-read-cell is absent only after its retry failed.
- **Step 6's last sentence**, today "When a cold-read-cell fails, the script's closing text says whether to wait, to carry on, or to rerun that cold-read-cell alone; follow it.", becomes the sentence the user approved on 2026-09-11: "When a cold-read-cell fails, the script's closing text names it and its error; pass an error the user could fix to the user at once, and triage the reports that landed."

## 10. Not in this design

- **[#397](https://github.com/nedschorus/nedschorus/issues/397)**, a Stop hook that displaces a claude cold-read-cell's report so a failure looks like success. The grid sees a report and has nothing to retry. That is its own issue.
- **The grid process dying** with the agent-session that launched it (`nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-14-nedschorus-file-naming-and-location-standards-2/`). No code in the grid can survive its own death. The cause is covered by the context-threshold hook, `scripts/handoff-context-threshold-hook.py`, which now waits for a running background task before it hands the agent-session off.
- **Cross-model fallback.** It is ruled out: a retry uses the same model.

## 11. Open questions for the user

1. **A time limit per cold-read-cell.** None exists, so a cold-read-cell that hangs holds the closing text back indefinitely. This seat knows of no hang. The failures it has seen all ended with an exit, and the one run that never closed died with its agent-session rather than hanging. So this design adds none, and asks: should a cold-read-cell running past some limit be killed and treated as a failure, and at what limit?
2. **The cold-read-fast-read.** It runs the same cold-read-cell code for one reviewer, and step 2 of the skill says "If it prints FAILED, tell the user and stop." Should it retry once too? The recommendation is yes: it is one relaunch, and a fast read lost to a passing error costs the whole revision cycle it gates.

## 12. Order of work

The code follows two things already queued against the same file. First, [pull request #408](https://github.com/nedschorus/nedschorus/pull/408), which rewrites comments throughout `scripts/cold-read-grid.py`. Second, the fixes to the cold-read scripts found by the 2026-09-11 cold read (the MD-skills seat's task 68, not yet an issue), which the user ruled land before this code. The skill text in section 9 lands in the same pull request as the code it describes.
