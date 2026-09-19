---
status: design; its cold-read-full-run of 2026-09-16 is triaged, and the user's review of that cold-read-full-run closed on 2026-09-17 with eleven rulings, all applied here; tracked in issue [cold-read grid: retry a failed cold-read-cell once, report its cause, and name a runtime that is down](https://github.com/nedschorus/nedschorus/issues/413)
design-as-of: 2026-09-17
---

# cold-read-grid: what happens when a cold-read-cell fails

The design for issue [cold-read grid: retry a failed cold-read-cell once, report its cause, and name a runtime that is down](https://github.com/nedschorus/nedschorus/issues/413). It changes how `scripts/cold-read-grid.py` handles a cold-read-cell that ends without a report. The cold-read-grid retries the cold-read-cell once and names the cause of each failed attempt. It prints one line when every cold-read-cell of an agent-cli is absent for the same agent-cli-wide cause, and closes every run that finishes with one closing text built from what landed. It carries out the user-ruling of 2026-09-11, whose seven points are quoted in the sections they govern, and his direction of 2026-09-14. The sequence he set on 2026-09-14 is this design, its cold-read-full-run, his review of that cold-read-full-run, and only then code. That review closed on 2026-09-17, and its rulings are in this text.

Terms are the glossary's (`docs/nedschorus-wiki/nedschorus-glossary.md`), plus these:

- An **agent-cli** is the command-line tool a cold-read-cell drives, `claude` or `codex`, recorded as `runtime=` in each report's provenance stamp. The user adopted the name on 2026-09-16; its glossary entry and the sweep of the existing files are their own changes, and the stamp field keeps its spelling.
- A **cold-read-cell program** is the launcher script that runs one cold-read-cell: `scripts/cold-read-claude-cell.py` or `scripts/cold-read-codex-cell.py`, both built on `scripts/cold-read-cell-common.py`.
- An **attempt** is one launch of a cold-read-cell program. A retry is the second attempt of the same cold-read-cell, not a seventh cold-read-cell, and every count in this design is of cold-read-cells, never of attempts.
- A report has **landed** when its cold-read-cell program exited 0 and the report file is non-empty, today's test (`scripts/cold-read-grid.py` lines 428-432).
- A cold-read-cell is **absent** when its retry also ended without a landed report.
- The **set** is the reports one cold-read-full-run writes into its cold-read-record.
- **The skill** is /cold-read, whose text is `.claude/skills/cold-read/SKILL.md`.
- The **fixture rule** is the user-ruling of 2026-09-02, recorded in issue [Candidate skill: write-test-plan — consequence-ranked test plan with observable oracles and traceability (likely FIRST build)](https://github.com/nedschorus/nedschorus/issues/18): a fixture standing for an external system's output is generated from the real command's output, with the capture command and the machine recorded beside it.

## 1. What happens today

Facts from origin/main at ad9bfca. Line numbers are that commit's.

- **No retry.** Each cold-read-cell program tries the model chain for its tier, and every chain holds a single model (`scripts/cold-read-claude-cell.py` lines 110-113, `scripts/cold-read-codex-cell.py` lines 108-111). So a failed model ends the program at once with exit 1, and the `FELL BACK:` line cannot fire. The program exits 64 instead when it refuses its own invocation, before any agent-cli starts.
- **No cause.** A cold-read-cell program that exits non-zero gets `FAILED (exit N): <report file name> (stderr kept: <log>)`, with N the program's exit status. One that exits 0 without a landed report gets `FAILED (exit 0, no report): <report file name> — the cell reported success without writing a review; treat as failed and rerun (stderr kept: <log>)` (`scripts/cold-read-grid.py` lines 496-501, issue [md-review-grid reports eight reviews saved when eight cells produced nothing](https://github.com/nedschorus/nedschorus/issues/164)). The cold-read-grid's only look at the error is a bare substring test for `401` or `Not logged in` in the log's last 2,000 characters (lines 503-506), which no test covers.
- **No grouping.** On 2026-09-10 the Claude account's session limit failed all three Claude cold-read-cells within seconds, in each of eight cold-read-records. The cold-read-grid printed three unrelated `FAILED` lines and the Opus stop text. When all three Codex cold-read-cells fail, it prints "All six reviews are complete".
- **Opus is special.** The closing text has three branches (lines 591-643). `TARGET_CHANGED_INSTRUCTIONS` prints when the cold-read-target changed during the run. Otherwise `OPUS_ABSENT_INSTRUCTIONS` ("Stop here … Wait for Opus to come back") prints when either Opus cold-read-cell failed, and `COMPLETION_INSTRUCTIONS` in every other case. A `NOTE:` line then names the failed cold-read-cells. Its wording depends on Opus in two places, the Opus-absent note and the clause "Wait for Opus to come back before that run." on the target-changed note, and it has a separate Fable-only wording. The user rejected this on 2026-09-11: "why is opus special? I don't think it should be."
- **No timeout.** Neither the cold-read-grid's `Popen` nor the cold-read-cell program's `subprocess.run` has one. The cold-read-grid polls every 5 seconds until all six exit.
- **The cold-read-fast-read already retries.** `scripts/cold-read-fast-read.py` runs its one cold-read-cell through `scripts/cold-read-agy-cell.py`, agent-cli `agy`, and retries it once when it fails, except on exit 64, because "the same invocation would be refused the same way". Its test drives the retry with a stub that fails a set number of first attempts (`fail_first_attempts` in `scripts/cold-read-fast-read-test.py`). The `agy` agent-cli is outside this design.

## 2. The rule every part of this design keeps

**A cause changes what the cold-read-grid reports, never what the cold-read-grid decides.** What it decides is whether a cold-read-cell is retried, whether it is absent, which variant of the closing text prints, and the exit code. Those depend only on whether a report landed, on which attempt it was, and on whether the cold-read-target changed during the run. What a cause changes is what gets reported: the `RETRYING:` and `FAILED` lines, whether a `AGENT-CLI DOWN:` line prints, what the "Tell the user" sentence names, and what the marker on each report says.

The reason is that causes are read from text, and text can mislead. A cold-read-cell program's log holds the agent-cli's own messages beside the model's text. The Claude limit messages of section 4 arrive on the `claude` agent-cli's standard output, which on a failed attempt also carries whatever the model printed. The Codex agent-cli writes the model's text onto its standard error (`scripts/cold-read-grid.py` lines 449-457, issue [cold-read grid: FELL BACK and STRAY WRITE markers fire on text that is not the cell's — two false positives measured 2026-09-02](https://github.com/nedschorus/nedschorus/issues/244)). A model reviewing a document that quotes a limit message could print that message at the start of a line.

If a misread cause could skip a retry or change the exit code, that would be a defect. Here it can do less, but not nothing: a misread cause can print a false `AGENT-CLI DOWN:` line and put a false cause into the "Tell the user" sentence the agent passes to the user. Two things keep that rare and checkable. Each agent-cli's recognised texts are matched only in that agent-cli's own output (section 4), so Codex output, for which no text is recognised yet, cannot be misread at all. And every cause the user hears carries the path of the kept log it came from (section 6).

## 3. Retry once, in the cold-read-grid

The user-ruling of 2026-09-11, point 1: "Every failed cell is retried once, automatically, with the SAME model. No cell is special."

When an attempt ends without a landed report, the cold-read-grid relaunches the same cold-read-cell once, with the same model and the same arguments, at once, while the other cold-read-cells keep running. There is no delay and no change of model. A retry that also ends without a landed report is not retried again.

- The retry lives in the cold-read-grid, not inside the cold-read-cell program. The cold-read-grid is what sees the first failure and can report it, and one relaunch there covers both agent-clis and every attempt that ends with the program exiting. It does not cover a cold-read-cell that never exits (section 11), or a report that lands with the wrong text in it (section 10). It does cover a cold-read-cell program the cold-read-grid cannot start at all, which today raises out of `Popen` and ends the whole run: the cold-read-grid catches that error, writes it to the attempt's log as the attempt's only content, and counts it as a failed attempt, so the retry runs as for any other failure. Its cause is `program-unstartable`, named by the cold-read-grid because no program ran to name it, with the error text as the detail; it is not agent-cli-wide, since it says nothing about the agent-cli.
- Exit 64 is retried too, unlike in the cold-read-fast-read, because point 1 covers every failed cold-read-cell and a refused relaunch costs seconds.
- Before the relaunch, the cold-read-grid lifts the `STRAY WRITE:` and `WRITE CHECK DID NOT RUN:` lines from the first attempt's log and prints them, as it does today for a landed report. The cold-read-cell program checks for stray writes on its failing path too (`report_stray_writes` in `scripts/cold-read-cell-common.py`). The retry takes its own baseline after the first attempt's write, so without this step a stray write by a failed first attempt would never be reported.
- It then renames the first attempt's log to `<report file name>.attempt-1.stderr.log`, and the retry writes `<report file name>.attempt-2.stderr.log`. `<report file name>` includes the `.md`, as the log is named today (line 375), as in `2026-09-16-foo--claude-hunt-good.md.attempt-1.stderr.log`. A cold-read-cell that is not retried keeps today's single `<report file name>.stderr.log`.
- At the first failure the cold-read-grid prints `RETRYING: <cold-read-cell name> — <cause> (first attempt's log kept: <log>)`. `<cold-read-cell name>` is the agent-cli, pass token and tier the report's file name ends with, as in `claude-hunt-good`. `<cause>` is `<class> — <detail>` (section 4).
- A retry that lands prints `saved:` as today, and its attempt-2 log is lifted and deleted as any landed report's log is today. The attempt-1 log is kept and ships with the cold-read-record, since it records a failure that happened.
- A retry that fails prints `FAILED (exit N): <cold-read-cell name> — <cause> (stderr kept: <log>)`, with N the cold-read-cell program's exit status and the second attempt's cause. Both logs are kept and ship with the cold-read-record. Every `FAILED` line takes this one form, the exit-0 case included, so today's "treat as failed and rerun" wording goes. The line keeps its `FAILED (exit` opening, so the skill's Monitor still catches it. The cold-read-cell is now absent, and its cause from here on is the second attempt's, even when the first attempt's differed. This carries out point 2: "A cell that fails twice is reported absent at the moment of its second failure, with its exit code and the tail of its error."

**The handoff's wait grows with the run.** The context-threshold hook, `scripts/handoff-context-threshold-hook.py`, holds a session-handoff while a background task runs, but only for 30 minutes by default (`DEFAULT_BACKGROUND_TASK_WAIT_MINUTES`), and it measured cold-read-grid runs at 8 to 27 minutes. A retry after a late failure makes a run longer, so the same pull request as the retry raises that default to 75 minutes and updates the test that pins it. Without that, a session hands off while its own cold-read-full-run is still going, and the cold-read-grid dies with it.

A retry is not suppressed for a cause a retry cannot fix, such as a logged-out agent-cli. Point 1 retries every failed cold-read-cell, and suppressing a retry would make the cause decide what the cold-read-grid does, which section 2 forbids.

## 4. Naming the cause

The cold-read-cell program, not the cold-read-grid, names the cause of its own failed attempt. It holds the agent-cli's exit status, standard output and standard error separately, before it writes them to its log. As the last line of a failed attempt it prints one status line to its standard error, which the cold-read-grid captures in the attempt's log:

`<program>: cause: <class> — <detail>`

`<program>` is the cold-read-cell program's name, as in `cold-read-claude-cell`. The cold-read-grid finds the line with `cell_status_line`, the function of issue [cold-read grid: FELL BACK and STRAY WRITE markers fire on text that is not the cell's — two false positives measured 2026-09-02](https://github.com/nedschorus/nedschorus/issues/244) that accepts a line only when it starts with a cold-read-cell program's name. It takes the last such line in the log, because model text echoed earlier in the log could hold a quoted one.

When the log holds no cause line, the cold-read-grid names the cause from what it sees. A cold-read-cell program that never started gets `program-unstartable` (section 3). One that exited 0 without a landed report gets `no-report`. Any other gets `exit-N`, with N the program's own exit status and the log's last non-empty line as the detail. That covers 64 for a refused invocation, a Python traceback, and a signal, which Python reports as a negative number.

The classes, tested in this order; the first that matches names the cause. The first three are recognised in the agent-cli's output. A line matches only by how it starts, never by text found somewhere inside it, the same rule issue [cold-read grid: FELL BACK and STRAY WRITE markers fire on text that is not the cell's — two false positives measured 2026-09-02](https://github.com/nedschorus/nedschorus/issues/244) applies to status lines, and once a line matches by its start the rest of that line is the detail. Each agent-cli's texts are matched only in that agent-cli's output. The matching function lives in `scripts/cold-read-cell-common.py`, and each cold-read-cell program passes it its own agent-cli's texts. The next three come from the program's own branches and exit status, not from agent-cli text, and the last two are the cold-read-grid's own, named when no program ran to name a cause or when the program left none.

| class | recognised by | detail | what clears it | agent-cli-wide |
|---|---|---|---|---|
| `account-limit` | `claude` only: an output line starting "You've hit your session limit" | the rest of the line, as in "resets 8:50pm (America/Los_Angeles)" | the reset time passing | yes |
| `model-limit` | `claude` only: an output line starting "You've reached your " followed by the attempt's model family name and " limit", as in "You've reached your Fable limit." for `claude-fable-5-1` | the model family name | the reset, or the user's usage settings | no, that model only |
| `logged-out` | `claude` and `codex`: the line each agent-cli prints when it has no credentials, captured before this class is built (below); the `codex` line after its leading tracing-logger timestamp | the matched line | the user logs in | yes |
| `agent-cli-missing` | the program's `OSError` handler ran when it started the agent-cli (`run_model_chain` in `scripts/cold-read-cell-common.py`) | the error text, which says whether the binary was not found or would not run | the user installs or repairs the agent-cli | yes |
| `no-report` | the agent-cli exited 0 but no report verified (the program's existing exit-0 branch) | "no report written" | nothing the user does; the retry is the remedy | no |
| `program-unstartable` | the cold-read-grid's own `OSError` handler ran when it started the cold-read-cell program | the error text | the user repairs the checkout | no |
| `exit-N` | anything else; N is the agent-cli's exit status, as in `exit-2` | the last non-empty line of the agent-cli's standard error, or of its standard output when standard error is empty, cut to 120 characters | unknown; the kept log says | no |

Agent-cli-wide means that this cause on one cold-read-cell predicts the same failure for every cold-read-cell of that agent-cli.

No recognised text is guessed. Every text the table recognises must be a real one, captured from an agent-cli, because the tests in section 8 are built from them. The two limit texts were found in the log-store's kept cold-read-cell logs on 2026-09-16. Each is line 2 of its log, on the `claude` agent-cli's standard output.

No logged-out text exists in the log-store, so the agent building this captures one before writing that class. It runs each agent-cli once on ned-box, with an empty configuration directory, so the run fails for want of credentials without touching the real login: `CLAUDE_CONFIG_DIR=$(mktemp -d) claude -p "say hi"` and `CODEX_HOME=$(mktemp -d) codex exec "say hi"`. It records the command, the machine and the output beside the fixture, as the fixture rule requires. If either command does anything but exit non-zero with a message, the builder stops for that agent-cli rather than inventing a text, and that agent-cli's logged-out failure lands as `exit-N` until a real one is captured from a run's log. Today's bare substring test for "401" and "Not logged in" is removed, not carried forward. Codex has no recognised texts either, because none has been captured, so a Codex quota failure lands as `exit-N` until a real one is captured and added. On 2026-09-18 the Codex logged-out line was captured, and it is recognised after the leading timestamp the Codex tracing logger puts on every line, the one exception to column-0 matching the user ruled on 2026-09-18 (walk skill-sentences-and-shipper-questions-2026-09-18, item 4); a Codex quota failure still lands as `exit-N`.

## 5. Saying once that an agent-cli is down

The user's direction of 2026-09-14: "If opus is down, claude is down, so that should be reported."

When a cold-read-cell becomes absent with an agent-cli-wide class, and every other cold-read-cell of its agent-cli has either landed or is absent with the same class, the cold-read-grid prints one line:

`AGENT-CLI DOWN: claude — account-limit — resets 8:50pm (America/Los_Angeles); 3 reports absent`

The detail is that of the last of them to become absent. Each agent-cli's line prints once, when its condition is met, so when both agent-clis are down the lines appear in the order the agent-clis went down. The closing text restates the line in a form that does not start with `AGENT-CLI DOWN:` (section 6), so the skill's Monitor sees each one once.

It does not print that line in two cases:

- **A model limit is not the agent-cli being down.** On 2026-09-11 the Fable cold-read-cell failed on "You've reached your Fable limit" while both Opus cold-read-cells landed. That is one absent report, class `model-limit`, reported as such. Because `model-limit` is not agent-cli-wide, no `AGENT-CLI DOWN:` line prints even when every Claude cold-read-cell fails with it; each is listed as absent.
- **Absent reports with different or unrecognised causes are listed one by one** in the closing text. Three `exit-N` failures on one agent-cli are three facts the cold-read-grid cannot join into one.

The rule counts cold-read-cells, not models, so it holds when the cold-read-cells the cold-read-grid launches change. Today Opus runs two of the three Claude cold-read-cells.

## 6. The closing text

The user-ruling of 2026-09-11, point 3: "One closing text for every run, replacing the Opus-absent and Fable-only branches: which cells are absent and why, triage what landed with judgments provisional, record the absences in `dispositions.md`, and pass an error the user could fix to the user at once." Point 4: "A report set missing a cell after its retry is VALID AND INCOMPLETE. The run is not void."

`OPUS_ABSENT_INSTRUCTIONS`, the Opus-absent and Fable-only wordings of the `NOTE:` line, and the "Wait for Opus to come back before that run." clause are all removed. The `NOTE:` line itself is replaced by the list of absent reports below.

Every run that finishes closes with one closing text, in one of four variants. A run whose cold-read-grid process dies, or whose cold-read-cell hangs, never closes (sections 10 and 11).

- **The cold-read-target changed:** today's `TARGET_CHANGED_INSTRUCTIONS`, whatever else happened, because a set read against a document that changed during the run is not valid. After it come the absent reports, the agent-cli-down lines and the "Tell the user now" sentence, when there are any.
- **All six landed:** today's `COMPLETION_INSTRUCTIONS`, whose first sentence becomes "All six reports landed in {record_dir}, one file per reviewer."
- **Some landed:** "{k} of {n} reports landed in {record_dir}. The set is valid and incomplete: triage the reports that landed." Then the absent reports and the agent-cli-down lines. Then the rest of `COMPLETION_INSTRUCTIONS` after its first sentence, with "until you have read all six" becoming "until you have read every report that landed", and one sentence added: "Record each absent report and its cause in dispositions.md."
- **None landed:** "No report landed in {record_dir}, so there is nothing to triage." Then the absent reports and the agent-cli-down lines, and: "Start a new cold-read-full-run once the causes above that the user can clear are cleared, or at once if none of them is."

`{n}` is the number of cold-read-cells launched, six today. Valid, in the user's word, means the reports that landed are triaged as the review that was asked for. It is the opposite of today's Opus-absent text, "this is not the review that was asked for", and only a changed cold-read-target makes a set not valid.

Each absent report is one line: `- <cold-read-cell name>: <class> — <detail> (log: <attempt-2 log path>)`. An agent-cli-down line reads `- claude is down: account-limit — resets 8:50pm (America/Los_Angeles); 3 reports absent`.

When any absent report's class is `logged-out`, `agent-cli-missing`, `account-limit` or `model-limit`, the closing text ends with one sentence: "Tell the user: <causes>." It is the last sentence, after "Start a new cold-read-full-run …" when that prints, and it is omitted when no absent report has one of those classes. One cause reads `<agent-cli> <class> — <detail> (log: <path>)`. Absent reports with the same agent-cli and class share one cause, which takes the detail and log of the last of them to become absent. Causes are joined by semicolons. A Codex quota failure, which lands as `exit-N` (section 4), is not among them.

Because a cause can be misread (section 2), each carries the path of the kept log it came from, so the user can check it. This carries out the user's words of 2026-09-11, "what failed and why … should be reported asap, in case it's something the user can fix", as he settled them on 2026-09-16: "the word now or immediately is the wrong word, we report when we report". The `RETRYING:` and `FAILED` lines show each cause to the agent as it happens, and the closing text carries the cause to the user when the run ends.

**Exit codes do not change.** 0 means all six landed. 1 means at least one report is absent, including all six. 3 means the cold-read-target changed, whatever else happened. An agent reads the closing text rather than the exit code, and anything that checks only the exit code today keeps working.

## 7. The marker on every report

The user-ruling of 2026-09-11, point 5: "a marker line naming the absent cells and their errors goes at the top of every report in the record directory, so a later reader of the record sees what was not looked at."

When a report is absent, the cold-read-grid writes one marker line into every `.md` file in the cold-read-record: the reports that landed, and the reference-check file. It uses the mechanism that writes the target-changed marker today (`mark_reports_target_changed`, `scripts/cold-read-grid.py` lines 296-338). That mechanism puts the line after the provenance stamp when there is one, so the stamp stays the first line, and at the top otherwise; this is the top the ruling means.

`<!-- INCOMPLETE SET: 2 of 6 reports absent — claude-hunt-good (account-limit — resets 8:50pm (America/Los_Angeles)), claude-terminology-good (account-limit — resets 8:50pm (America/Los_Angeles)) -->`

When the cold-read-target also changed, both markers are written, the target-changed marker first.

A reader who opens one report in the log-store months later then knows the set it belongs to had absent reports, and which ones, without the closing text that has scrolled away.

## 8. Tests

The user-ruling of 2026-09-11, point 6: "The tests that pin the Opus-absent and Fable-only branches are rewritten to pin the single path", the one closing text of section 6.

In `scripts/cold-read-grid-test.py`, every check on the old closing text is rewritten to pin the four variants of section 6. These are the scenarios `checkout-opus-absent`, `checkout-terminology-opus-absent` and `checkout-fable-absent`. They also include `checkout-terminology-codex-absent`, which expects "All six reviews are complete" and "Rerun them singly" after a run with one Codex cold-read-cell absent; `checkout-changed-and-failed`, which expects the `NOTE:` line; and `checkout-stray-write` and `checkout-stray-write-elsewhere`, which check for "All six reviews are complete".

The stub agent-cli the tests use (`STUB_MODEL_RUNTIME`, lines 166-213) keeps no state between launches, so it gains per-attempt behaviour. A counter file lets it fail a set number of first attempts, or print different output on each attempt, as `fail_first_attempts` does in `scripts/cold-read-fast-read-test.py`. New cases:

- A cold-read-cell fails once and lands on retry. Expect `RETRYING:`, then `saved:`, the all-six variant, exit 0, the attempt-1 log kept and the attempt-2 log deleted.
- A cold-read-cell's first attempt writes a file outside its report and fails, and the retry lands. Expect the `STRAY WRITE:` line.
- A cold-read-cell fails both attempts. Expect `RETRYING:`, then `FAILED` with the cause, the some-landed variant, the marker in all six `.md` files of the cold-read-record, and exit 1.
- All three Claude cold-read-cells fail both attempts with `account-limit`. Expect one `AGENT-CLI DOWN:` line with the reset text, its restatement in the closing text without that prefix, and the reset text in the "Tell the user" sentence.
- All three Claude cold-read-cells fail both attempts with `model-limit`. Expect no `AGENT-CLI DOWN:` line, and three absent reports listed.
- All three Claude cold-read-cells fail their first attempt with `account-limit`. Two fail their retry the same way, and one fails its retry with `exit-1`. Expect `RETRYING:` naming `account-limit` three times, the third `FAILED` naming `exit-1`, and no `AGENT-CLI DOWN:` line.
- Three Codex cold-read-cells fail both attempts with `exit-N`. Expect no `AGENT-CLI DOWN:` line, three absent reports listed, and no "Tell the user" sentence.
- All six fail both attempts. Expect the none-landed variant and exit 1.
- One copied cold-read-cell program has its execute permission removed, so the cold-read-grid cannot start it. Expect `RETRYING:` and then `FAILED` naming `program-unstartable`, the other five cold-read-cells unaffected, the some-landed variant and exit 1, rather than the run ending.
- The cold-read-target changes during a run that has an absent report. Expect the target-changed variant, then the absent report, both markers with the target-changed marker first, and exit 3.
- **A Codex attempt's output holds "You've hit your session limit" at the start of a line, and the attempt fails with exit 1.** Expect the class `exit-1`, since no Codex text matches that phrase (the one Codex text recognised is its own logged-out line). Also expect a run otherwise the same as that failure without the line: the same retry, closing text and exit code.

The classifier gets its own cases in `scripts/cold-read-cell-common-test.py`. The inputs for the two limit classes are the real lines from the log-store. Each fixture records the log file and line, the command that produced it, which is the cold-read-grid's launch of `scripts/cold-read-claude-cell.py`, and the machine the run was on:

- the session limit: line 2 of `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-10-design-to-main-test-writing-agent-instructions/2026-09-10-design-to-main-test-writing-agent-instructions--claude-hunt-good.md.stderr.log`, run on the Mac;
- the Fable limit: line 2 of `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-11-SKILL-2/2026-09-11-SKILL-2--claude-hunt-floor.md.stderr.log`, run on the Mac.

The `logged-out` input is the capture of section 4. `agent-cli-missing`, `no-report` and `exit-N` come from the program's own branches and need no captured text.

## 9. The skill text that changes with it

This is skill text, so before it is merged it takes the skill's own route: a cold-read-fast-read, a cold-read-full-run, and an approval-walk with the user. It is merged in the same pull request as the code it describes.

- **Step 5's Monitor list** gains `RETRYING:` and `AGENT-CLI DOWN:` (printed as `AGENT-CLI DOWN:`, below), and "the one marker of the seven that carries no colon" becomes "of the nine". `RETRYING:` means a first attempt failed and the cold-read-cell is being relaunched, which needs no action. `AGENT-CLI DOWN:` means every cold-read-cell of that agent-cli is absent for one agent-cli-wide cause. The `FAILED` sentence changes to say a cold-read-cell is absent only after its retry failed.
- **Step 6's last sentence**, today "When a cold-read-cell fails, the script's closing text says whether to wait, to carry on, or to rerun that cold-read-cell alone; follow it.", becomes the sentence of the user-ruling of 2026-09-11, point 7, in today's terms and with his wording of 2026-09-17: "When a cold-read-cell fails, the script's closing text names it and its error; pass an error the user could fix to the user, and triage the reports that landed unless the closing text says the cold-read-target changed."

## 10. Not in this design

- **issue [A Stop hook's report inside a claude -p review cell displaces the cell's report: two of three claude cells lost tonight](https://github.com/nedschorus/nedschorus/issues/397)**, a Stop hook firing inside a `claude -p` reviewer, which gives the reviewer another turn so that its reply to the hook is saved in place of its review. It was found in `scripts/sanity-check-attacks.py`, and reaches the cold-read-grid only if its `claude` cold-read-cells run with the project's hooks. Where it happens a report lands, so there is nothing to retry. Its fix for the sanity-check runner is pull request [Sanity-check runner: keep project hooks out of claude cells, refuse a saved text that is not a report](https://github.com/nedschorus/nedschorus/pull/417).
- **The cold-read-grid process dying** with the agent-session that launched it (`nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-14-nedschorus-file-naming-and-location-standards-2/`). No code in the cold-read-grid can survive its own death. What this design does about it is in section 3.
- **Cross-model fallback.** Ruled out: point 1 retries with the same model.

## 11. No timeout per cold-read-cell

None exists. A cold-read-cell that hangs holds the closing text back indefinitely, and it is never retried, because it never exits. No hang has been seen: the failures on record all ended with an exit, and the one run that never closed died with its agent-session rather than hanging. The user ruled on 2026-09-17 that this design adds no timeout, and that one is added if a hang is ever seen. For scale, the slowest cold-read-cell of this design's own cold-read-full-run took 1,864 seconds, 31 minutes.

## 12. Order of work

The code follows two changes queued against the same scripts, in this order. First, pull request [cold-read scripts: sweep comments and docstrings to the glossary's project terms](https://github.com/nedschorus/nedschorus/pull/408), which rewrites comments throughout `scripts/cold-read-grid.py`. Second, the fixes to the cold-read scripts found by the 2026-09-11 cold-read-full-run of the skill, listed under "Verifiable code defects" in that run's `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-11-SKILL-2/dispositions.md`. Three of those fixes are in `scripts/cold-read-grid.py`, and the user ruled on 2026-09-14 that they are merged before this code. They are the MD-skills agent-seat's task 68, not yet an issue. The skill text of section 9 is merged in the same pull request as the code it describes.
