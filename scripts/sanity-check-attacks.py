#!/usr/bin/env python3
"""Run a sanity-check: independent audits, each on both runtimes, over one document.

The sanity-check is this project's second review instrument, separate from
the cold read (`nc-systems/cold-read/cold-read-grid.py`, the prose-and-clarity review) and
never part of it. Three audits, each in its own
fresh context:

- **cut** — what here should be deleted.
- **mechanization** — what English instruction here should become code.
- **fresh-eyes** — an independent, competitive design built from the review
  request alone — a problem statement plus reading lists — never from the
  design. The agent is instructed not to read the existing design,
  its implementation, or its records, but may research the best approach
  independently — this repository, the internet, reputable repositories on
  GitHub. Isolation is instructed, not enforced, and checked, best-effort, two ways:
  the agent's report lists everything it consulted and discloses anything
  off-limits it strayed into (self-reported), and the runner scans what the
  requester sends — the problem statement, and the instruction files the
  CLIs inject on their own (conventional paths, not a proven enumeration) —
  for the design's coined names, printing a LEAK-WARNING per hit. The
  agent returns a five-section report — sketch, hard parts, late
  discoveries, assumptions, what it consulted — and triage compares the
  original and the fresh design on their merits: a substantive difference
  becomes a question, a worry, trap, or real failure mode the fresh design
  raises that the original never addresses is a candidate finding, and the
  stronger parts of either can feed a best-of-both proposal; every adoption
  is reviewed and ruled on
  by the user, one item at a time.

Prompts: `docs/agents/sanity-checker-<audit>-attack-prompt.md`. Each file is
split at its `<!-- SANITY-CHECK-PROMPT-BODY -->` line: above it a header for
maintainers that the runner never sends to a review agent, below it the
prompt itself. The
runner refuses to start unless every prompt it will use carries exactly one
such line with `## Your assignment` directly below it, so a broken boundary
fails before any model cost is spent.

Operating rules:

- Both runtimes on every audit — the claude CLI (claude-fable-5-1, falling
  back to claude-opus-5 when Fable produces no review) and
  gpt-6.1-sol (the codex CLI), at xhigh reasoning effort. Each audit
  therefore runs as two review agents, one per runtime, named
  `<audit>-<runtime>` in this runner's output. The claude CLI runs with
  `--setting-sources user`, so this repository's hooks, CLAUDE.md and skills
  are never loaded into a claude agent (nedschorus#397).
- Run it only by deliberate decision — never wire it into automation. A
  revision of an already-sanity-checked document earns no automatic rerun. Run it after the cold read has passed, not before. It
  applies only to actionable (work-directing) MDs — designs, specs, skills,
  plans — never records (documents that only report what happened).
  "the cold read passed" is the natural moment to ask
  whether a document deserves its sanity-check; a PR carrying an actionable MD with
  no sign of a past sanity-check may have one suggested — a note, never a gate.
- The requesting agent triages: follows up the warnings described below,
  settles hedged claims about code by reading the code, merges the runtimes' reports, and
  presents the surviving findings to the user one at a time for his ruling
  (the walk-me-through skill). Findings are design changes; none is applied
  without the user's ruling. Triage is complete when every warning and every
  finding has either been brought to the user for a ruling or been set aside
  with a stated reason.
- The review agents read a copy, not the checkout. When a run starts, the
  runner makes a local clone of the repository at the checkout's last commit
  (under `~/.cache/nedschorus-sanity-check-review-copies/`, with the whole
  history and no remote pointing back at the checkout), every agent runs in
  it, and the runner removes it when the run ends, a run that fails and a
  run a stop signal ends included (WHEN A RUN IS STOPPED, below). So the
  reviewed text is exactly that commit, and the
  requester may keep working in the checkout while the agents run. The target
  and every `--context` document must be committed: one that differs from the
  last commit, or that git does not track, is refused before any agent
  launches. Each is named to the agents by its repository-relative path,
  whatever form it was passed in, because an agent resolves that name inside
  the copy; a path that resolves outside the checkout is refused.
- Reports land in `sanity-check-records/<date>-<target-stem>/` (suffixed -2,
  -3, ... claimed by creation, so a same-day second pass never overwrites
  earlier reports; for a skill, whose file is always `SKILL.md`, the stem is
  `<skill directory>-SKILL`). Beside them the runner saves everything it
  printed, as `sanity-check-run.log`, and the request the fresh-eyes agents
  were given, as `sanity-check-request.md`. The record is gitignored, and
  shipped to the log-store on ned-box by
  `scripts/sanity-check-record-ship.py`, which this runner calls when the run
  ends. They are logs, kept and citable, not deleted when the work they served
  lands (user-ruled 2026-08-25, and 2026-09-15 for this kind). Ship again
  after writing `finding-dispositions.md` and the add-only copy sends only
  that file; a file already in the store whose content differs is refused, so
  finish the triage before shipping it rather than editing it afterwards.
- Each review agent is given a scratch directory of its own, made by the
  runner in the review copy at the record's own path,
  `sanity-check-records/<date>-<target-stem>/scratch/<audit>-<runtime>/`, and
  named to that agent in its prompt: working notes, drafts, anything it needs.
  When the agents are done the runner moves the scratch directories into the
  record, before the copy is removed. It replaces the bare "write no files" the prompts used to
  carry (user-ruled 2026-08-29) — agents need working space, and a sanctioned
  place for it is worth more than a prohibition the tooling cannot enforce. An
  agent's report is still its reply, never a file: nothing in scratch is read
  as findings, so scratch is archived as-is with the run record, never
  triaged, and shipped to the log-store beside the reports.

Usage:

  scripts/sanity-check-attacks.py --target <path> [--context <path> ...]
      [--problem-statement <path>] [--attack <name> ...] [--runtime <name> ...]
      [--print <surface>]

`--context` names companion documents the reading audits receive alongside
the target. `--attack` (repeatable; default all three) runs a subset — the fresh-eyes
second pass is `--attack fresh-eyes --problem-statement <variant>`, and a
failed audit reruns without repeating the others. `--runtime` (repeatable,
`claude` or `codex`; default both) does the same for runtimes: a rerun of the
one agent that failed is this run's command with `--attack <audit> --runtime
<runtime>` as its only `--attack` and `--runtime`, and the runner prints that
command whole under the agent's `FAILED:` line when a rerun is what the
failure calls for (see below).

`--print` writes a review surface to stdout instead of running: `cut`,
`mechanization`, or `fresh-eyes` prints that audit's assembled prompt — body plus the review request: for
the reading audits the request names the target and context paths, for
fresh-eyes it is the problem-statement file; `requester` prints the requesting agent's manual —
this docstring followed by the fresh-eyes requester section — and needs no
other arguments.

Running a sanity-check, and reading its output:

- Run it as a background task and arm a Monitor (the harness's watch tool)
  on its output; it prints a status line per review agent as each finishes —
  `saved: <path>`, `FAILED: <audit>-<runtime> — <cause class> — <detail>`, or
  `SKIPPED:` — plus `RETRYING: <audit>-<runtime> — <cause class> — <detail>`
  when it launches an agent a second time, and the warning lines described
  below. Exit 0 when every launched agent saved; 1 when any launched agent
  failed (a skipped agent is not launched); 2 when the invocation itself is
  unusable — a missing file, a broken prompt boundary, a bad flag. A run that
  SIGTERM, SIGINT or SIGHUP ends is ended by that signal, after the steps
  under WHEN A RUN IS STOPPED. A run in which every launched agent failed
  still ships its record, which then holds the run's log and no report, and
  prints the `record:` line and the record's path.
- An agent that saves no report is launched once more by the runner, with the
  same prompt, in the same copy, unless the cause is one only the user can
  clear or the launch timed out. The cause classes: `logged-out`,
  `agent-binary-missing`, `account-limit` and `model-limit`, which only the
  user can clear and which are never relaunched; `timeout`, the launch cut off
  after an hour, never relaunched, because the same launch would cost the same
  hour; `exit-<code>`, any other failed launch, whose detail is the last line
  the CLI wrote; `no-report`, an exit of 0 with nothing written; and
  `not-a-report`, an exit of 0 with text lacking a section the audit's prompt
  requires — on 2026-09-15, a claude agent's reply to a hook's note
  (nedschorus#397) — where the refused text is printed in the run's output
  and nothing is saved for it. A CLI's own words are printed above the lines
  about its launch: all of a claude launch's, the last 20 lines of a codex
  launch's.
- Under a `FAILED:` line the runner prints what to do next, and the
  requesting agent does that. The `FAILED:` line carries `(relaunched once)`
  when the agent was launched twice. When only the user can clear the cause: tell
  the user what the line says, and after the user has cleared the cause run
  the command printed there, which runs that one agent again into a new
  record directory. For every other failure: triage that audit from the other
  runtime's report when a run saved one, and write in finding-dispositions.md
  that the audit is unreviewed when none did. A report saved by an agent's
  second launch carries `relaunched_after=<cause class>` in its provenance
  line.
- Without `--problem-statement` the fresh-eyes agents print `SKIPPED`, loudly,
  never silently — that audit works from the problem statement alone.
- Cut and mechanization reports get a quote scan: every quoted span of four
  or more words is searched for across the tracked files, and a span found in
  none prints `WARNING: <audit>-<runtime> quote found in no tracked file: ...` — triage
  information, never a gate; a quote may legitimately come from git history
  or the web.
- Fresh-eyes runs print `LEAK-WARNING` lines — the requester-input scan
  described above, one per line a coined name appears on, naming the line's
  number and text. Expect hits on every run: the off-limits list must name
  the design's paths to forbid them, and those paths are coined names; the
  line shows whether a hit is that list.
- Every review agent may reach the internet to check facts, and every one may
  write: claude agents carry web tools plus Write, codex agents run under a
  permission profile that writes where workspace-write did, with network on,
  and denies every credential file. Where they may write is instructed, not
  enforced — each prompt names that agent's scratch directory and confines it
  there. Withholding the tools was never the protection it looked like: on
  2026-08-21 a claude agent wrote a file to the worktree while carrying no
  write tools at all (nedschorus#161) — so the check below runs after every agent
  that completes, on both runtimes: a write to the review copy outside the
  agents' scratch directories is reported as
  `WARNING: the review copy was modified outside the cells' scratch
  directories, seen when <audit>-<runtime> finished: <paths>`. The agents
  share one copy and one baseline, so the check cannot tell which agent
  wrote: the line names the agent whose completion ran the check that saw the
  write, and every agent that completes after it sees the same write and
  prints the line again under its own name. The write is harmless to the
  checkout, and is thrown away with the copy; the warning says some agent of
  the run did not keep to its instructions.
- What the write detector sees, and what it does not. It compares the review
  copy against a baseline taken before the agents launched: everything git
  reports as dirty or untracked, plus the copy's record directory
  (`sanity-check-records/`), which git reports in no form because it is
  gitignored. This run's `scratch/` inside it, where each agent is told to
  work, is exempt: a write there is the sanctioned behaviour and is never
  reported, however git labels it. Because it compares rather than watches, a
  write made and undone before the comparison runs leaves nothing to find.
  Writes to other ignored paths in the copy are not detected — enumerating
  every ignored file to catch a rare write was ruled out (user, 2026-08-23).
  The requester's own checkout is not watched: the agents run in the copy, and
  the requester may work in the checkout meanwhile. A report path the runner
  finds already occupied when it writes the report is reported as
  `WARNING: <audit>-<runtime> found a stray write at its own report path and
  overwrote it: <path>`. The largest gap is an agent that does not complete:
  one that times out, cannot be launched, or exits non-zero returns before
  the comparison runs, so an agent that wrote a file and then failed is never
  checked. Closing that gap is a change of behaviour beyond what the user has
  ruled, and sits with him.
- WHY THE RUNNER DECIDES THE RELAUNCH (user-ruled 2026-10-01, walk
  SKILL-sanity-check-2026-09-30-2, item 2, "y"). The /sanity-check skill used
  to tell the requesting agent to rerun a failed agent once, whatever the
  cause. The user asked "doesn't it matter why a cell fails?", and of a
  revision that had the agent judge the cause, "I don't think the agents will
  magically know when to rerun." What was on record that day: one
  sanity-check rerun (2026-09-15), which saved its reports only because the
  requester had first removed the cause; and one cold-read retry
  (`SKILL-cold-read-2026-09-18-2`, a codex cell, "Selected model is at
  capacity"), which the cold-read-grid's identical relaunch cleared. So a
  second launch helps when the cause was the provider's and has passed, and
  nothing in a requester's hands tells that case from the others. The runner
  therefore launches once more itself, except where the cause is known to
  outlast a relaunch: the classes only the user can clear
  (USER_CLEARABLE_CAUSE_CLASSES in
  nc-systems/cold-read/cold-read-cell-common.py), which also reach the user by
  the printed instruction, and a timeout. The classification is read from the
  CLI's own output, matched only at the start of a line and only on a launch
  that failed; a launch whose text misleads it is told to the user, who can
  see the line. The cold-read-grid relaunches whatever the cause and uses the
  class for its report alone; here the class decides, because a relaunch of a
  logged-out CLI is a wasted launch and its failure sends the audit to triage
  with one report. The instructions do not depend on which agent finished
  first, or on whether this run launched the other runtime: a rerun of one
  agent is a run that launched one runtime, and the other runtime's report is
  then in the first run's record.
- WHEN A RUN IS STOPPED. The /sanity-check skill starts this runner as a
  background task, and a seat's handoff ends that seat's background tasks, so
  a run is ended from outside in ordinary use. Until review of the pull
  request that introduced the review copy measured it, SIGTERM or SIGHUP
  ended the runner at once: the copy, a whole checkout, stayed under
  `~/.cache` for good, one more for each such run, and the agents ran on to
  their own end with nobody left to save what they wrote. On SIGTERM, SIGINT
  or SIGHUP the runner now stops every process under it (the agent-binaries
  and whatever they started: SIGTERM, then SIGKILL after 10 seconds), launches
  nothing more — no second launch of an agent that ended this way, and no
  next model of the claude chain; before this, SIGINT sent to the whole
  process group, as Ctrl-C at a terminal sends it, relaunched the agents it
  had just ended — moves the agents' scratch directories into the record,
  removes the copy, and prints one `STOPPED:` line saying which signal ended
  the run, that the same command is to be run again, and where the reports
  the run had saved and its log are. It then ships the record, as any run
  does when it ends, printing the `record:` line, and ends by the same
  signal; a run killed outright while it ships has already stopped its agents
  and removed its copy, and its record stays on disk. No agent-binary starts
  a review once the stop is under way: a cell's thread reads the stop and
  starts its agent-binary under one lock, the lock the handler takes to mark
  the run stopped, so every agent-binary is in the process table the handler
  then reads. The one later start is the `--version` probe of a cell saving
  its report, for the report's provenance line; it reads the version and
  exits. A signal that arrives after every cell has finished, each having
  saved its report or said why it could not, stopped nothing: the runner
  finishes the run's closing steps, prints what a finished run prints, with
  no `STOPPED:` line, and ends by the signal. A cell still running when the
  signal arrives makes the run a stopped run, whatever its calls return
  afterwards. SIGKILL, and a
  machine that stops, cannot be answered, so each run, before it makes its
  own copy, removes the copies no live run owns and prints `removed: a review
  copy an earlier run left behind, <path>` for each. A copy is a live run's
  while that run holds the lock on the owner file beside the copy's
  directory, `<directory>.owner`, which the operating system releases when
  the process ends however it ends; so two runs at once never remove each
  other's copy. An agent whose runner was killed outright still runs to its
  own end, in a copy the next run removes from under it.
- Each saved report opens with a provenance line: runtime, model, effort,
  the reviewing CLI's version (measured by this runner, not self-reported),
  audit, target, and the commit the review copy holds and its state, so
  quotes can be checked against the commit the agent read — `clean` unless
  something in the copy differed from that commit when the agents launched,
  which `dirty(N)` would report.
"""

import argparse
import concurrent.futures
import contextlib
import datetime
import fcntl
import hashlib
import os
import pathlib
import re
import shlex
import shutil
import signal
import subprocess
import sys
import importlib.util
import tempfile
import threading
import time
import typing

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RECORDS_DIRECTORY_NAME = "sanity-check-records"
RECORDS_ROOT = REPO_ROOT / RECORDS_DIRECTORY_NAME
# The record reaches the log-store by program, not by an agent remembering to
# run one (nedschorus#392), the way nc-systems/cold-read/cold-read-grid.py ships its own.
RECORD_SHIPPER = REPO_ROOT / "scripts" / "sanity-check-record-ship.py"
_common_spec = importlib.util.spec_from_file_location(
    "cold_read_cell_common", REPO_ROOT / "nc-systems" / "cold-read" / "cold-read-cell-common.py")
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)
# The Codex cells' permission profile, as it appears in their sessions.
CODEX_CREDENTIAL_DENYING_PERMISSION_PROFILE = "sanity-check-no-credentials"


def _cold_read_cell_program(file_name: str):
    """One of the cold read's two cell programs, loaded as a module for the
    one thing this runner takes from it: the texts its agent-binary prints
    when a launch fails for a reason the agent-binary can name."""
    spec = importlib.util.spec_from_file_location(
        pathlib.Path(file_name).stem.replace("-", "_"),
        REPO_ROOT / "nc-systems" / "cold-read" / file_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# What each agent-binary prints when a launch fails for a reason it can name
# (logged out, a usage limit), per runtime: a function from the model to the
# texts, which common.classify_failed_attempt matches against the start of
# each line the agent-binary wrote. Each text was captured from a real run and
# is kept, with its source, beside the cold-read cell that met it; taken from
# there, not copied, so a text added for one instrument is recognised by both.
RECOGNISED_FAILURE_TEXTS_FOR_MODEL = {
    "claude": _cold_read_cell_program(
        "cold-read-claude-cell.py").recognised_failure_texts_for_model,
    "codex": _cold_read_cell_program(
        "cold-read-codex-cell.py").recognised_failure_texts_for_model,
}

# The signals that end a run early and that this runner answers by stopping
# its agents and removing its review copy: see WHEN A RUN IS STOPPED in the
# module docstring. SIGKILL cannot be answered; the next run removes the copy
# a killed run left (remove_review_copies_no_live_run_owns).
RUN_STOP_SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
# How long the stopped agents' processes are given to end on SIGTERM before
# they are sent SIGKILL.
STOPPED_PROCESS_GRACE_SECONDS = 10.0
# Set by the first stop signal, and read by every thread before it launches an
# agent-binary: a cell stopped with its run is not relaunched, and the claude
# chain does not go on to its next model.
RUN_STOPPED = threading.Event()
# The cells whose run_cell has returned: each saved its report or printed why
# it could not. stop_run_on_signal copies it into CELLS_FINISHED_AT_THE_STOP
# when the stop comes.
CELLS_FINISHED = set()
# The cells that had finished when the stop signal came, or None while the run
# is not stopped. A stopped run ends as a finished run only when every cell is
# in it. Decided at the signal, so no child's exit code is read: an
# agent-binary or a version probe a signal ended may exit 0 (the npm codex
# wrapper does), and a cell that had not finished when the signal came is
# counted as ended by the stop whatever its calls returned.
CELLS_FINISHED_AT_THE_STOP = None
# Held while a cell's thread reads RUN_STOPPED and starts an agent-binary, and
# by the stop handler while it sets RUN_STOPPED: see
# run_agent_binary_unless_run_stopped. Re-entrant, so a handler that runs on a
# thread already holding it cannot wait on itself; in a run the main thread,
# which runs the handler, launches no agent-binary and never holds it.
AGENT_BINARY_LAUNCH_LOCK = threading.RLock()
# The name of the file beside a review copy's directory whose lock says a
# live run owns that copy: see claim_review_copy_directory.
REVIEW_COPY_OWNER_FILE_SUFFIX = ".owner"

# The line a cell prints when its first launch produced no report and the
# runner launches it once more: `RETRYING: <cell> — <cause class> — <detail>`.
# The cold-read-grid's word for the same event. It is not a `WARNING:`.
RETRYING_PREFIX = "RETRYING:"
# Two cause classes of this runner's own, beside the ones
# common.classify_failed_attempt names: a launch cut off at
# CELL_TIMEOUT_SECONDS, and a launch that exited 0 with text lacking a section
# its attack's prompt requires (ATTACK_REPORT_REQUIRED_PHRASES).
CAUSE_CLASS_TIMEOUT = "timeout"
CAUSE_CLASS_NOT_A_REPORT = "not-a-report"
# How much of a Codex launch's own output is printed when the launch fails or
# times out: its last lines. The Codex CLI writes its whole session to its
# standard error, the model's text included, so the whole stream would bury
# the run's log; the cause it names is at the end. The classification reads
# the whole stream, whatever is printed.
CODEX_FAILED_LAUNCH_PRINTED_TAIL_LINES = 20

# The sanctioned working space, one directory per cell, inside the run's own
# record directory: <record dir>/scratch/<audit>-<runtime>/. See
# cell_scratch_dir for why it lives there and why it is per cell.
CELL_SCRATCH_DIRECTORY_NAME = "scratch"

# Where each run's copy of the reviewed commit is made, and removed
# again when the run ends: see review_copy_of_commit. Outside the checkout, so
# the requester's own work there is never a cell's; and outside /tmp, which the
# Codex cells' permission profile makes read-only on Linux, where the copy must
# stay writable for the scratch directories inside it.
REVIEW_COPIES_ROOT = pathlib.Path.home() / ".cache" / "nedschorus-sanity-check-review-copies"

# What the run saves in its record beside the reports: everything it printed,
# and the request the fresh-eyes cells were given. Both used to be copied in by
# hand, when an agent remembered (nedschorus#412, item 3).
SANITY_CHECK_RUN_LOG_FILE_NAME = "sanity-check-run.log"
SANITY_CHECK_REQUEST_COPY_FILE_NAME = "sanity-check-request.md"

# Ignored paths the write detector watches, repo-relative. `git status` reports
# no ignored path in any form, so a cell writing to one was invisible however
# the porcelain was parsed; the record directory is the ignored path that
# matters, because the runner writes every cell's report there and triage then
# reads those reports against each other — a cell overwriting a finished report
# corrupts the comparison and the run still looked clean (raised as an inline
# P2 on PR #98, fixed 2026-08-23). Watching the whole ignore list instead —
# `git status --ignored` — was ruled out (user, 2026-08-23): it enumerates and
# fingerprints every ignored file in the repository, one subprocess each, to
# catch a rare write. Writes to other ignored paths (ghi-mirror/,
# cold-read-records/, __pycache__/) are therefore still undetected; the test
# file asserts that limit rather than leaving it to be discovered. Each entry
# is a literal path — a directory, walked, or a single file — never a glob
# pattern: git's ignore syntax is not interpreted here. Since the cells run in
# a review copy (review_copy_of_commit), the watched record directory is the
# copy's, which holds the cells' scratch directories and nothing the runner
# writes; the reports land in the requester's checkout, outside the copy.
IGNORED_PATHS_WATCHED_FOR_WRITES = (RECORDS_DIRECTORY_NAME,)

# git's own porcelain code for an ignored entry, carried as the status half of
# a watched ignored path's snapshot entry. It marks the entries that exist for
# write detection alone and belong to no commit — see reviewed_revision.
IGNORED_PATH_STATUS_CODE = "!!"

# The claude runtime's chain, tried in order until one produces a review.
# "claude-fable-5" is obsolete (user, 2026-09-04: "fable 5 is now obsolete.
# 5.1 is current"), and Fable is sometimes unavailable (user, 2026-09-11:
# "sometimes fable is not available, so it should fall back to opus in that
# case"), so Opus 5 stands behind it and ends the chain.
#
# WHAT COUNTS AS A FAILURE WORTH FALLING BACK FROM follows the house chain,
# run_model_chain in nc-systems/cold-read/cold-read-cell-common.py: a model that exits
# non-zero, cannot be launched at all, or exits 0 having written nothing are
# one event — no review was produced — so the chain advances on all three.
# That module is not imported here: it is built around the cold-read cell's
# command line and report file, and this runner has neither.
CLAUDE_MODEL_CHAIN = ("claude-fable-5-1", "claude-opus-5")
# gpt-6-sol from 2026-09-22 and gpt-6.1-sol since 2026-10-01, matching
# cold-read-codex-cell.py's `deep` tier; the id needs codex-cli 0.159.1 or
# later.
CODEX_MODEL = "gpt-6.1-sol"
# xhigh for both runtimes: user calibration 2026-08-03 for codex, confirmed
# for both by the 2026-08-17 tier probe (max earned neither slot).
REASONING_EFFORT = "xhigh"
CELL_TIMEOUT_SECONDS = 3600

# The prompt files' header/body boundary, and the heading the body must open
# with — checked at startup, so a broken boundary fails before any model cost.
PROMPT_BODY_MARKER = "<!-- SANITY-CHECK-PROMPT-BODY -->"
PROMPT_BODY_FIRST_LINE = "## Your assignment"

# The token each prompt body carries where its cell's scratch directory goes;
# the runner substitutes the real path when it assembles that cell's prompt.
# Every prompt body must carry exactly one — checked in prompt_body, so a
# prompt that stopped naming its scratch directory fails before model cost
# rather than launching a cell that was never told where it may write.
PROMPT_SCRATCH_DIRECTORY_PLACEHOLDER = "SANITY-CHECK-SCRATCH-DIRECTORY-PATH"

ATTACKS = ("cut", "mechanization", "fresh-eyes")
RUNTIMES = ("claude", "codex")

ATTACK_PROMPT_FILES = {
    "cut": REPO_ROOT / "docs/agents/sanity-checker-cut-attack-prompt.md",
    "mechanization": REPO_ROOT / "docs/agents/sanity-checker-mechanization-attack-prompt.md",
    "fresh-eyes": REPO_ROOT / "docs/agents/sanity-checker-fresh-eyes-attack-prompt.md",
}

# What every genuine report of an attack contains, matched case-insensitively
# anywhere in the captured text; a text missing any of them is refused, never
# saved. The prompts are the source: each phrase names a section its prompt
# requires — cut's Questions and leanness certification, mechanization's
# prompts-to-code table and its coverage list, fresh-eyes's five sections — and
# a test pins every phrase to its prompt's body. The smallest phrase each
# section's reports carry, not heading syntax, which the models reshape.
# This check was rejected on 2026-08-19 with the condition "reopen on the
# first observed miss". The miss came on 2026-09-15: two claude cells saved a
# reply to a Stop hook's note in place of their reviews, and the runner
# printed `saved:` for both (nedschorus#397).
ATTACK_REPORT_REQUIRED_PHRASES = {
    "cut": ("questions", "leanness"),
    "mechanization": ("prompts-to-code", "coverage"),
    "fresh-eyes": ("sketch", "hard parts", "late discoveries", "assumptions",
                   "consulted"),
}


# Hyphenations that are ordinary English or repo-wide convention, not names a
# design coined — the coined-name scan skips them. Anything else that hits is
# printed; triage judges false positives (the scan reports, never gates).
GENERIC_HYPHENATED_WORDS = {
    "read-only", "zero-context", "one-line", "built-in", "fine-grained",
    "high-level", "low-level", "long-running", "machine-readable",
    "human-readable", "re-run", "so-called", "non-empty", "well-designed",
    "open-ended", "side-effect", "side-effects", "trade-off", "trade-offs",
    "one-off", "end-to-end", "up-to-date", "auto-filled", "auto-posted",
    "hand-made", "judgment-written", "long-lived", "near-perfect",
    "per-commit", "what-and-why", "work-in-progress",
}


def prompt_body(attack: str) -> str:
    """The prompt below the file's body marker, its scratch placeholder intact.

    The marker is a line no ordinary edit produces. The boundary was the first
    `---` line until 2026-08-19, and `---` is ordinary markdown punctuation: a
    horizontal rule added to the header, or one written inside a code fence,
    silently moved the split and shipped header text to the cells in place of
    their instructions. It also forced a YAML-frontmatter special case, since
    frontmatter is delimited by `---` too. A marker that collides with nothing
    needs neither the special case nor an editor's memory (user-ruled
    2026-08-19, on the first live check of the cut prompt, where five of six
    cells raised the old boundary independently).

    The scratch placeholder is checked here for the same reason and in the same
    place: every cell is given a scratch directory, and a body that no longer
    names one would send a cell out with a directory it was never told about
    and no sanctioned place to write. Counted in the body alone, never the
    header — a header that explains the token must not be mistaken for a body
    that carries it, the same distinction the marker search makes.
    """
    path = ATTACK_PROMPT_FILES[attack]
    lines = path.read_text(encoding="utf-8").splitlines()
    # A line that IS the marker, not a line that spells it inside a sentence.
    # No shipped header spells it any more: commit "prompt headers: the
    # marker-split sentence cut from all three (user-ruled 2026-08-22)",
    # 70a813b, left them saying "everything below the marker", which names
    # the marker without carrying it. The strict equality is what makes
    # either wording harmless, and the test keeps the mistakable case alive
    # from a synthetic header.
    marker_lines = [i for i, line in enumerate(lines)
                    if line.strip() == PROMPT_BODY_MARKER]
    if len(marker_lines) != 1:
        print(f"attack prompt needs exactly one {PROMPT_BODY_MARKER} line, "
              f"found {len(marker_lines)}: {path}", file=sys.stderr)
        raise SystemExit(2)
    body = "\n".join(lines[marker_lines[0] + 1:]).strip()
    first_line = body.split("\n", 1)[0].strip()
    if first_line != PROMPT_BODY_FIRST_LINE:
        print(f"attack prompt body must open with {PROMPT_BODY_FIRST_LINE!r}, "
              f"found {first_line!r}: {path}", file=sys.stderr)
        raise SystemExit(2)
    placeholder_count = body.count(PROMPT_SCRATCH_DIRECTORY_PLACEHOLDER)
    if placeholder_count != 1:
        print(f"attack prompt body needs exactly one "
              f"{PROMPT_SCRATCH_DIRECTORY_PLACEHOLDER} placeholder, found "
              f"{placeholder_count}: {path}", file=sys.stderr)
        raise SystemExit(2)
    return body


def coined_names(target_path: pathlib.Path) -> set:
    """The design's coined names: backticked spans plus multi-part invented
    names (hyphenated tokens), minus ordinary-English hyphenations."""
    text = target_path.read_text(encoding="utf-8")
    names = set()
    for span in re.findall(r"`([^`\n]+)`", text):
        span = span.strip()
        # A plain lowercase word is vocabulary, not coinage: the project's
        # naming rule makes invented names multi-part, so single words
        # (`main`, `none`, `status`) only produce scan noise.
        # Bare punctuation (`---`) is markdown, not a coinage.
        if (len(span) >= 3 and " " not in span and not span.isdigit()
                and any(ch.isalnum() for ch in span)
                and not (span.isalpha() and span.islower())):
            names.add(span)
    for token in re.findall(r"[A-Za-z]\w*(?:-\w+)+", text):
        if token.lower() not in GENERIC_HYPHENATED_WORDS:
            names.add(token)
    return names


LEAK_WARNING_LINE_CHARACTERS = 160


def leak_scan(design_names: set, text: str, where: str) -> None:
    """Print a LEAK-WARNING per line of text a design name appears on. Report,
    never gate: a leaked name means the sketch can no longer independently
    confirm that part of the design — the requester weighs it at triage.

    Each warning names the line it matched, number and text, because the
    request's off-limits list must name the design's own paths, so every run
    has expected hits: one run printed 22 warnings naming only the file, and
    telling those from a real leak meant searching the file by hand
    (nedschorus#412, item 6)."""
    lines = text.splitlines()
    for name in sorted(design_names):
        pattern = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])", re.IGNORECASE)
        for number, line in enumerate(lines, start=1):
            if pattern.search(line):
                print(f"LEAK-WARNING: design name `{name}` appears in {where}, "
                      f"line {number}: {line.strip()[:LEAK_WARNING_LINE_CHARACTERS]}",
                      flush=True)


def injected_instruction_files(checkout: pathlib.Path = None) -> list:
    """Instruction files the cell CLIs load on their own — the leak channel a
    2026-08-17 canary exposed (a cell disclosed that the injected project
    CLAUDE.md carried the design's thesis). Conventional paths, not a verified
    enumeration; the report scan is the catch-all behind this. The project's
    files are the ones in `checkout`, the review copy the cells run in."""
    home = pathlib.Path.home()
    checkout = checkout or REPO_ROOT
    candidates = [
        checkout / "CLAUDE.md",
        checkout / "CLAUDE.local.md",
        checkout / "AGENTS.md",
        home / ".claude" / "CLAUDE.md",
        home / ".claude" / "CLAUDE.local.md",
        home / ".codex" / "AGENTS.md",
    ]
    return [path for path in candidates if path.is_file()]


def assemble_prompt(attack: str, target: str, context: list,
                    problem_statement: pathlib.Path,
                    scratch_directory: str) -> str:
    # Data only below the rule: every instruction lives in the prompt MDs,
    # which get a cold read; nothing reviewable hides here (user-ruled
    # 2026-08-17). The scratch path is substituted into the body for the same
    # reason: the sentence granting the working space is in the MD where it
    # can be reviewed, and only the path — data, and different for every cell
    # — comes from here. Absolute, not repo-relative: a cell resolves it the
    # same wherever its own working directory ends up.
    body = prompt_body(attack).replace(PROMPT_SCRATCH_DIRECTORY_PLACEHOLDER,
                                       scratch_directory)
    if attack == "fresh-eyes":
        problem = problem_statement.read_text(encoding="utf-8")
        return body + "\n\n---\n\n" + problem
    request_lines = [f"Document under review: `{target}`"]
    if context:
        request_lines.append("Context documents:")
        request_lines.extend(f"- {path}" for path in context)
    return body + "\n\n---\n\n" + "\n".join(request_lines)


def run_claude(prompt: str, checkout: pathlib.Path = None) -> tuple:
    # Returns (exit code, review text, model, failed attempts, cause): the
    # cause is None when a model produced a review, and otherwise the
    # (class, detail) of the chain's last attempt, from
    # common.classify_failed_attempt, which is what run_cell decides the
    # relaunch on and prints on the cell's RETRYING: and FAILED: lines. The
    # last attempt's, as the cold-read-grid takes the last cause line of a
    # cell's log: a limit on the first model that the second model survives
    # is a fallback, not the cell's failure.
    # Runs in `checkout`, the review copy, so every path the cell resolves is
    # the reviewed commit's (see review_copy_of_commit).
    # Every cell may check facts on the internet (user-ruled 2026-08-18);
    # isolation and write discipline are instructed in the prompts and
    # checked (leak scan; worktree check), never enforced here. Write joined
    # the tool set on 2026-08-29, when the cells gained a sanctioned scratch
    # directory: the prompt now names a place to put notes and drafts, so the
    # tool that place needs is here. Withholding it never was the protection
    # it looked like — a claude cell wrote to the worktree on 2026-08-21 with
    # no write tool at all (nedschorus#161), which is why run_cell's worktree
    # check runs for claude cells too, not only codex's.
    failed_attempts = []
    last_cause = None
    for model in CLAUDE_MODEL_CHAIN:
        if RUN_STOPPED.is_set():
            # The run was stopped: the chain does not go on to a model whose
            # review nobody is left to save.
            break
        recognised_texts = RECOGNISED_FAILURE_TEXTS_FOR_MODEL["claude"](model)
        command = [
            "claude", "-p",
            "--model", model,
            "--effort", REASONING_EFFORT,
            "--output-format", "text",
            "--allowedTools", "Read,Grep,Glob,WebSearch,WebFetch,Write",
            # User settings only: this repository's .claude/settings.json wires
            # Stop hooks, and on 2026-09-15 checkout-freshness-catch-up.py spoke
            # inside two cells as origin/main moved; each cell answered the
            # note, and the answer, captured as the final message, was saved in
            # place of the review (nedschorus#397). The flag also keeps out the
            # project's CLAUDE.md, skills and write guards (measured
            # 2026-09-16); the write detector in run_cell covers the guards.
            "--setting-sources", "user",
        ]
        try:
            # Decoded as UTF-8 with undecodable bytes replaced, never raised
            # on: see run_codex.
            completed = run_agent_binary_unless_run_stopped(
                command, input=prompt, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=checkout or REPO_ROOT, text=True, encoding="utf-8",
                errors="replace", timeout=CELL_TIMEOUT_SECONDS,
            )
        except OSError as error:
            # A CLI that will not launch is one failed attempt, not the end of
            # the run. run_cell's own OSError handler still covers the codex
            # runtime, which has no chain to advance.
            failed_attempts.append(f"{model}({type(error).__name__})")
            print(f"WARNING: {model} could not be run: {error}", flush=True)
            last_cause = common.classify_failed_attempt(
                stdout="", stderr="", exit_code=None, recognised_texts=(),
                start_error=str(error))
            continue
        # The runtime's own words survive every ending, the house chain's rule
        # (BOTH STREAMS ARE CAPTURED, in run_model_chain,
        # nc-systems/cold-read/cold-read-cell-common.py). A CLI that is logged out or out of
        # credits explains itself on one of these streams and nowhere else, so
        # discarding them leaves "WARNING: <model> failed (exit 1)" as the whole
        # account of why -- the 54-byte cold-read log of 2026-08-23, which is
        # what taught the house chain to capture both. It is worse here than it
        # was there: the chain continues past a failed attempt, so a run whose
        # first model is logged out still saves a report, and that one line is
        # the only trace of the degradation in the output. Re-emitted before any
        # branch below, so no ending drops them. This program's log is its
        # stdout -- the review itself is returned to run_cell, never printed --
        # so the runtime's words go there too, and not to stderr as in the
        # house tool, whose log is the other stream.
        if completed is None or RUN_STOPPED.is_set():
            # The run was stopped: this model was never started, or its launch
            # ended because stop_processes_this_run_started ended it. Not a
            # failure of the model's, and not one to warn of.
            break
        if completed.stderr:
            print(completed.stderr, end="", flush=True)
        if completed.returncode != 0:
            failed_attempts.append(f"{model}(exit{completed.returncode})")
            if completed.stdout:
                print(completed.stdout, flush=True)
            print(f"WARNING: {model} failed (exit {completed.returncode})", flush=True)
            last_cause = common.classify_failed_attempt(
                stdout=completed.stdout or "", stderr=completed.stderr or "",
                exit_code=completed.returncode, recognised_texts=recognised_texts)
            continue
        if not completed.stdout.strip():
            # Exiting 0 with nothing to show is the ending that looks most like
            # success to a caller reading only the exit code, and the report it
            # would save is an empty review carrying a provenance stamp.
            failed_attempts.append(f"{model}(no-report)")
            print(f"WARNING: {model} exited 0 but produced no review", flush=True)
            last_cause = common.classify_failed_attempt(
                stdout="", stderr=completed.stderr or "", exit_code=0,
                recognised_texts=recognised_texts)
            continue
        return 0, completed.stdout, model, "+".join(failed_attempts), None
    return 1, "", "", "+".join(failed_attempts), last_cause


def run_agent_binary_unless_run_stopped(command: list, input: str = None,
                                        timeout: float = None, **popen_keywords):
    """subprocess.run for an agent-binary, started only while the run is not
    stopped: the CompletedProcess, or None when RUN_STOPPED was set first and
    nothing was started. `popen_keywords` are subprocess.Popen's.

    RUN_STOPPED is read and the agent-binary started under
    AGENT_BINARY_LAUNCH_LOCK, and stop_run_on_signal sets RUN_STOPPED under
    the same lock. So every agent-binary was started before the run was
    marked stopped, and is in the process table when
    stop_processes_this_run_started reads it; once that function has frozen
    it, it can start nothing more. Before this, a thread that had read
    RUN_STOPPED unset could launch after the handler's last look at the
    table: the agent-binary was killed alone, the child it then started held
    its pipes, and the run waited for that child with every stop signal
    ignored, its review copy left behind (found in review of the pull request
    that introduced the review copy). The wait after the start is outside the
    lock and is subprocess.run's own: on a timeout the agent-binary is killed
    and TimeoutExpired raised with the streams it had written."""
    with AGENT_BINARY_LAUNCH_LOCK:
        if RUN_STOPPED.is_set():
            return None
        if input is not None:
            popen_keywords["stdin"] = subprocess.PIPE
        process = subprocess.Popen(command, **popen_keywords)
    with process:
        try:
            stdout, stderr = process.communicate(input, timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise
        except BaseException:
            process.kill()
            raise
        return subprocess.CompletedProcess(command, process.poll(), stdout, stderr)


def last_lines_of_stream(text: str, line_count: int) -> str:
    """The last `line_count` non-empty lines of a stream an agent-binary
    wrote, each ending its line, or "" when it wrote nothing."""
    lines = [line for line in text.splitlines() if line.strip()]
    return "".join(line + "\n" for line in lines[-line_count:])


def run_codex(prompt: str, checkout: pathlib.Path = None) -> tuple:
    # Returns what run_claude returns: (exit code, review text, model, failed
    # attempts, cause), the cause None when the launch produced its last
    # message and otherwise the (class, detail) of the failed launch.
    # `-C checkout`, the review copy: the directory the cell reads, and the
    # root its profile lets it write under, where its scratch directory is.
    # workspace-write plus network: the cells may reach the internet and
    # GitHub to check facts (user-ruled 2026-08-18; the read-only sandbox
    # blocks even DNS, measured that day). Disk writes are possible here and
    # confined by the prompt to the cell's own scratch directory; run_cell's
    # worktree check detects strays outside it — containment over prevention,
    # the house doctrine. Both come from a permission profile extending
    # `:workspace` with network on, which also denies every credential file
    # (user-ruled 2026-09-29, item 8 of the walk
    # what-a-cold-read-reviewer-may-read-2026-09-28, "y"): the builder the
    # cold-read Codex cell uses, in nc-systems/cold-read/cold-read-cell-common.py.
    last_message_path = pathlib.Path(tempfile.mkstemp(suffix=".md", prefix="attack-cell-")[1])
    command = [
        "codex", "exec",
        *common.codex_credential_denying_permission_profile_arguments(
            CODEX_CREDENTIAL_DENYING_PERMISSION_PROFILE, ":workspace", network=True),
        # Codex's machine-wide memory store off for this cell: an audit cell
        # must be naive, not carrying forward what Codex concluded reviewing
        # this project before, and these automated runs should not deposit
        # findings in the user's personal store. The full reasoning, the
        # verification, and what the flag leaves open are written once in
        # scripts/code-review-codex-cell.py's docstring, under the heading
        # WHY THE CODEX MEMORY STORE IS OFF FOR REVIEW CELLS
        "--disable", "memories",
        "-C", str(checkout or REPO_ROOT),
        "--output-last-message", str(last_message_path),
        "-m", CODEX_MODEL,
        "-c", f"model_reasoning_effort={REASONING_EFFORT}",
        prompt,
    ]
    try:
        # Both streams are captured, where they used to go to DEVNULL: a Codex
        # launch that is logged out, or whose model is at capacity, says so on
        # its standard error and nowhere else, and with the streams discarded
        # every failed Codex launch was `exit 1` and nothing more, so the
        # runner could neither name the cause nor decide the relaunch on it.
        # The review itself still comes from --output-last-message.
        # Decoded as UTF-8 with undecodable bytes replaced, never raised on,
        # and the last message read the same way. A Codex session's streams
        # hold everything the model and its tools wrote, and with the default
        # decoding one byte that is not UTF-8 in them ended the whole run in a
        # UnicodeDecodeError traceback, with this cell's finished report lost
        # and the record not shipped (found in review of the pull request that
        # began capturing them; no real session with such a byte is on
        # record). A replaced byte costs one character of a log line; and the
        # encoding is named, so a run started where the locale is not UTF-8
        # reads the review as the CLI wrote it.
        completed = run_agent_binary_unless_run_stopped(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
            errors="replace", timeout=CELL_TIMEOUT_SECONDS,
        )
        if completed is None:
            # The run was stopped before codex could start: see run_claude.
            return 1, "", CODEX_MODEL, "", None
        if RUN_STOPPED.is_set():
            # Ended because the run was stopped, whatever its exit code: see
            # run_claude. An agent-binary that answers SIGTERM by exiting 0
            # would otherwise have what it had written so far saved as its
            # report.
            return 1, "", CODEX_MODEL, "", None
        if completed.returncode != 0:
            for stream in (completed.stderr, completed.stdout):
                print(last_lines_of_stream(
                    stream or "", CODEX_FAILED_LAUNCH_PRINTED_TAIL_LINES),
                    end="", flush=True)
            cause = common.classify_failed_attempt(
                stdout=completed.stdout or "", stderr=completed.stderr or "",
                exit_code=completed.returncode,
                recognised_texts=RECOGNISED_FAILURE_TEXTS_FOR_MODEL["codex"](CODEX_MODEL))
            return completed.returncode, "", CODEX_MODEL, "", cause
        return (0, last_message_path.read_text(encoding="utf-8", errors="replace"),
                CODEX_MODEL, "", None)
    finally:
        last_message_path.unlink(missing_ok=True)


def captured_stream_as_text(captured) -> str:
    """A stream a runtime wrote, as text, in whichever form it was handed back.

    subprocess.TimeoutExpired carries what the child had written before it was
    cut off, and CPython raises it before the decoding step, so a call that
    asked for text still gets bytes (measured on 3.13, 2026-09-17); a stream
    that was never piped, and a piped one the child wrote nothing to, arrive
    as None. Undecodable bytes are replaced, never raised on: a runtime cut off
    partway through a character must not turn a timeout into a crash.
    """
    if captured is None:
        return ""
    if isinstance(captured, bytes):
        return captured.decode("utf-8", errors="replace")
    return captured


def blob_fingerprint(data: bytes) -> str:
    """git's blob hash for a byte string: sha1 over git's header for a blob of
    that size, its NUL terminator, and the bytes.

    The same value `git hash-object` prints for a file holding those bytes,
    which is how the ledger's record of what it wrote stays comparable with a
    snapshot's record of what is on disk (verified 2026-08-23; the repository
    sets no .gitattributes and no core.autocrlf, so no clean filter stands
    between the two). Raw bytes are also the right input for a write detector:
    a rewrite that a filter would normalize away is still a write.
    """
    digest = hashlib.sha1()
    digest.update(b"blob %d\0" % len(data))
    digest.update(data)
    return digest.hexdigest()


def file_fingerprint(file_path: pathlib.Path) -> str:
    """git's blob hash of a file's current contents, or "absent".

    Read in chunks rather than whole: this runs once per dirty or watched path
    on every snapshot, and a file a cell wrote can be any size.
    """
    if not file_path.is_file():
        return "absent"
    digest = hashlib.sha1()
    digest.update(b"blob %d\0" % file_path.stat().st_size)
    with open(file_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_status_code_for_path(file_path: pathlib.Path,
                             repo_root: pathlib.Path) -> str:
    """The two-character status git gives one path, or the ignored code when
    git says nothing about it — the entry worktree_snapshot would record.

    Asked once per report the runner writes, so the ledger records what git
    actually says rather than assuming the record directory is still ignored.
    Where that ignore rule is absent — an older revision, or a worktree whose
    .gitignore has been edited — git calls each report `??`, and a ledger
    entry claiming `!!` made every later cell's check name the runner's own
    report as a worktree modification (chatgpt-codex-connector, P2 on PR #147).
    """
    completed = subprocess.run(
        ["git", "status", "--porcelain", "-z", "-uall", "--", str(file_path)],
        cwd=repo_root, stdout=subprocess.PIPE, text=True, check=False,
    )
    entry = completed.stdout.split("\0")[0]
    return entry[:2] if entry else IGNORED_PATH_STATUS_CODE


def path_watched_as_ignored(path: str) -> bool:
    """Whether a repo-relative path lies under a watched ignored path."""
    return any(path == watched or path.startswith(watched + "/")
               for watched in IGNORED_PATHS_WATCHED_FOR_WRITES)


def worktree_snapshot(repo_root: pathlib.Path = REPO_ROOT) -> dict:
    """Path -> (index/worktree status, content fingerprint) for every file git
    sees as dirty or untracked, plus every file under
    IGNORED_PATHS_WATCHED_FOR_WRITES. Both halves are needed, because each
    catches what the other misses. A file already modified before the run keeps its
    ` M` line when a cell rewrites it, so a label alone misses that write
    (Codex finding on PR #98); staging a file changes its status without
    changing its bytes, so a fingerprint alone misses `git add` (found by
    `codex exec review` on PR #102, where the fingerprint-only version was a
    regression against the label comparison it replaced).

    The paths come from `--porcelain -z -uall`, because plain porcelain hides
    writes two ways (both found reviewing PR #102, both silent by
    construction). Without `-z`, git C-quotes a non-ASCII pathname, and the
    unquoted result names no file on disk, so it fingerprints as "absent"
    before and after a cell rewrites it. Without `-uall`, git collapses a
    wholly-untracked directory into one `dir/` entry, so every file a cell
    writes underneath it is invisible.

    None of that reaches an ignored path, which git reports in no form at all,
    and the runner's own record directory is ignored — so the watched ignored
    paths are walked separately and added on top. Their entries carry git's
    ignored status code in place of a porcelain label, and a path git already
    reported keeps the entry git gave it, so a file force-added under a watched
    path still shows its real status and a `git add` there is still visible.
    """
    completed = subprocess.run(
        ["git", "status", "--porcelain", "-z", "-uall"], cwd=repo_root,
        stdout=subprocess.PIPE, text=True, check=False,
    )
    snapshot = {}
    fields = completed.stdout.split("\0")
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if not entry:
            continue
        status, path = entry[:2], entry[3:]
        # Under -z a rename or copy carries its origin path as the following
        # field instead of as ` -> origin` inside this one; skipping it keeps
        # the walk aligned with the entries that follow.
        if status[0] in ("R", "C"):
            index += 1
        snapshot[path] = (status, file_fingerprint(repo_root / path))
    for watched in IGNORED_PATHS_WATCHED_FOR_WRITES:
        watched_root = repo_root / watched
        candidates = (sorted(watched_root.rglob("*")) if watched_root.is_dir()
                      else [watched_root])
        for file_path in candidates:
            if not file_path.is_file():
                continue
            path = file_path.relative_to(repo_root).as_posix()
            if path not in snapshot:
                snapshot[path] = (IGNORED_PATH_STATUS_CODE,
                                  file_fingerprint(file_path))
    return snapshot


QUOTE_MINIMUM_WORDS = 4


# Typographic quotation marks and apostrophes, folded to their straight forms
# before a quote is compared with its source: a model writing ’ for the
# document's ' is quoting it faithfully. One run's replay found 16 of 24
# "quote found in no tracked file" warnings were exactly that
# (nedschorus#412, item 4).
TYPOGRAPHIC_QUOTES_FOLDED = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
})


def normalized_for_quote_match(text: str) -> str:
    """Whitespace, markdown emphasis and the curl of a quotation mark vary
    freely between a quote and its source; both sides are compared with them
    normalized away."""
    text = text.translate(TYPOGRAPHIC_QUOTES_FOLDED)
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", text)).strip()


def tracked_files_corpus(checkout: pathlib.Path = None) -> tuple:
    """Every tracked text file's content, normalized, one entry per file, read
    from `checkout`, the review copy, so quotes are checked against the text
    the cells read. Built once per run, before the cells launch."""
    checkout = checkout or REPO_ROOT
    listed = subprocess.run(
        ["git", "ls-files"], cwd=checkout,
        stdout=subprocess.PIPE, text=True, check=False,
    )
    pieces = []
    for name in listed.stdout.splitlines():
        path = checkout / name
        try:
            pieces.append(normalized_for_quote_match(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    # One entry per file, never concatenated: a joined corpus would let a quote
    # match across a file boundary (cold-read finding, verified by construction).
    return tuple(pieces)


def quote_scan(corpus: tuple, report: str, cell: str) -> None:
    """Print a WARNING per quoted span in a report that appears in no tracked
    file. A quote is a search string: found anywhere, it is verbatim; found
    nowhere, it is the one failure that matters — words that exist in no file.
    No attribution convention is asked of the cells (user-ruled 2026-08-19).
    Information for triage, never a gate: a quote may legitimately come from
    git history or the web, and the warning says where it was not found."""
    for match in re.finditer(r'"([^"\n]+)"|\u201c([^\u201d\n]+)\u201d', report):
        quote = match.group(1) or match.group(2)
        for fragment in re.split(r"\.\.\.|\u2026", quote):
            fragment = fragment.strip().rstrip("?.!,;:")
            if len(fragment.split()) < QUOTE_MINIMUM_WORDS:
                continue
            normalized = normalized_for_quote_match(fragment)
            if not any(normalized in file_text for file_text in corpus):
                print(f'WARNING: {cell} quote found in no tracked file: '
                      f'"{fragment[:60]}"', flush=True)


def missing_report_phrases(attack: str, text: str) -> list:
    """The phrases in ATTACK_REPORT_REQUIRED_PHRASES[attack] that text lacks,
    matched case-insensitively. Empty means the text has the shape of that
    attack's report; anything else means it is not one — a gate, unlike the
    quote scan: a text saved as a review that is not one is lost silently."""
    lowered = text.lower()
    return [phrase for phrase in ATTACK_REPORT_REQUIRED_PHRASES[attack]
            if phrase not in lowered]


CLI_VERSION_CACHE = {}


def runtime_cli_version(runtime: str) -> str:
    """The reviewing CLI's version, measured by this runner, once per runtime.

    In each report's provenance line because nedschorus#161's second instance
    leaned on the cells' self-reported CLI versions for a cross-version fact;
    the runner measures it instead. Spaces become hyphens so the value stays
    one token in the space-separated provenance line. "unknown" on any probe
    failure: a version probe must never fail a review cell, and "unknown" is
    a visible answer, not a silent one.
    """
    if runtime not in CLI_VERSION_CACHE:
        binary = "claude" if runtime == "claude" else "codex"
        try:
            completed = subprocess.run(
                [binary, "--version"], stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, check=False, timeout=60,
            )
            lines = (completed.stdout or "").strip().splitlines()
            measured = (
                lines[0].strip().replace(" ", "-")
                if completed.returncode == 0 and lines and lines[0].strip()
                else "unknown"
            )
        except (OSError, subprocess.TimeoutExpired):
            measured = "unknown"
        # A probe the stop may have ended is not cached as the runtime's version.
        if RUN_STOPPED.is_set():
            return measured
        CLI_VERSION_CACHE[runtime] = measured
    return CLI_VERSION_CACHE[runtime]


def provenance_line(runtime: str, model: str, attack: str, target: str,
                    fresh_eyes: bool, revision: str,
                    fallback_from: str = "", relaunched_after: str = "") -> str:
    """The provenance comment a saved report opens with — one line, one token
    per fact, so a later reader can check quotes against exactly what ran.

    `model=` names the model that actually produced the text below it, and
    `fallback_from=` appears only when an earlier model in a chain produced
    no review, so a degraded cell is visible in the record and not only in
    the run's output. Both follow the cold-read cells' stamp
    (stamp_provenance in nc-systems/cold-read/cold-read-cell-common.py), and so does the
    order of the line's first four fields: `runtime=`, `model=`,
    `fallback_from=` when present, `effort=`. After those the two stamps
    differ: `cli=`, `attack=` and `isolation=` are this runner's own;
    `target=` is in both but is not last here as it is there; and the
    checkout is recorded differently: the cold-read stamp writes
    `checkout=<hash>`, with `-dirty` appended when the tree is dirty, where
    this line writes `commit=<hash>` and `worktree=clean|dirty(N)` (see
    reviewed_revision).

    `relaunched_after=` appears only on a report saved by a cell's second
    launch, and carries the cause class of the first launch's failure (see
    run_cell), for the reason `fallback_from=` exists: a report that took two
    launches says so in the record and not only in the run's log.
    `fallback_from=` beside it names the failed models of the launch that
    saved the report, never the first launch's.
    """
    fallback_note = f"fallback_from={fallback_from} " if fallback_from else ""
    relaunch_note = f"relaunched_after={relaunched_after} " if relaunched_after else ""
    return (
        f"<!-- provenance: runtime={runtime} model={model} {fallback_note}"
        f"effort={REASONING_EFFORT} "
        f"cli={runtime_cli_version(runtime)} {relaunch_note}"
        f"attack={attack} target={target} "
        f"isolation={'instructed-not-enforced' if fresh_eyes else 'repository-read-only'} "
        f"{revision} -->"
    )


def reviewed_revision(baseline: dict, checkout: pathlib.Path = None) -> str:
    """The revision each report describes, for its provenance line.

    Cells read `checkout`, the review copy of one commit, which is clean when
    the run starts; `worktree=dirty(N)` would say N paths differed from the
    commit, and the commit would not reproduce what the cell saw.
    Recorded by the runner rather than asked of the reviewer: the machine holds
    this fact exactly, and a document moves under a walk — every quote in the
    first live check's reports pointed at a version that no longer existed
    before the walk on them finished (user-ruled 2026-08-19).
    """
    completed = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=checkout or REPO_ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False,
    )
    commit = completed.stdout.strip() or "unknown"
    # Watched ignored paths sit in the snapshot for write detection alone. They
    # belong to no commit, so a record directory left over from an earlier run
    # must not report the text the cell read as dirty.
    differing = [path for path, (status, _) in baseline.items()
                 if status != IGNORED_PATH_STATUS_CODE]
    worktree = "clean" if not differing else f"dirty({len(differing)})"
    return f"commit={commit} worktree={worktree}"


def stray_paths(baseline: dict, now: dict) -> list:
    """Paths whose status or fingerprint changed while the cells ran — a cell
    writing to the worktree, which its prompt forbids on either runtime.
    Compared over the union of both snapshots, so a file that appears,
    changes, or disappears all count (Codex finding on PR #98)."""
    return sorted(path for path in set(now) | set(baseline)
                  if now.get(path) != baseline.get(path))


class RunnerReportWriteLedger:
    """The reports this run wrote itself: path -> snapshot entry, in the shape
    worktree_snapshot records.

    The runner writes every cell's report into RECORDS_ROOT, which the write
    detector watches, so without this the first report written would be named
    as a stray by every cell that finished after it — a warning on every
    ordinary run, which teaches its readers to ignore the warning that matters.
    The ledger holds each report's fingerprint rather than exempting its path:
    a cell overwriting a finished report is precisely the write the watch
    exists to catch, and a path exemption would excuse it.

    In a run the ledger watches the review copy while the reports land in the
    requester's checkout, outside it, so write_report records nothing and only
    answers whether the report path was occupied. The bookkeeping below is
    for a ledger whose checkout is the one the reports land in.

    main() runs the cells concurrently, so one cell's report write and another
    cell's stray snapshot can interleave. The lock keeps a snapshot from
    reading a report mid-write, and makes each report's fingerprint recorded
    before any snapshot that could see the file.

    The ledger also holds the record directory this run owns, because two runs
    can overlap in one worktree — a case fresh_record_dir is built for — and
    the watch is repo-wide while a ledger is per-invocation. Without that,
    each run named the other run's reports as its own cells' stray writes
    (PR #147 finding 1).
    """

    # git's shapes for a path it has never had in the index. Another live run
    # only ever creates files under the record root; it never modifies or
    # stages an existing one. So these are the statuses an entry may carry and
    # still be excused as somebody else's legitimate work — a ` M` or `A `
    # there is nobody's routine business and stays reported.
    NEW_TO_GIT_STATUS_CODES = (IGNORED_PATH_STATUS_CODE, "??")

    def __init__(self, own_record_dir: pathlib.Path = None,
                 repo_root: pathlib.Path = None) -> None:
        # The checkout the detector watches: in a run, the review copy the
        # cells read, which is where a cell's write lands (see
        # review_copy_of_commit). The requester's own checkout is not watched;
        # the requester may keep working in it while the cells run.
        self._repo_root = repo_root or REPO_ROOT
        self._own_record_dir = own_record_dir
        self._writes = {}
        self._lock = threading.Lock()

    def write_report(self, out_path: pathlib.Path, text: str,
                     repo_root: pathlib.Path = None) -> bool:
        """Write one cell's report, record it as this runner's own work, and
        answer whether the path was already occupied.

        Occupied means a stray write that this report has just erased: the
        record directory is claimed by mkdir when the run starts and only this
        ledger writes reports into it, so anything already at the path arrived
        during this run from somewhere else. Until PR #147 the runner's write
        simply repaired such a file and recorded the repair as its own work,
        and the cell's write was reported nowhere.

        The bytes are written, not the string, so the fingerprint recorded is
        of exactly what landed on disk on any platform.
        """
        repo_root = repo_root or self._repo_root
        data = text.encode("utf-8")
        with self._lock:
            occupied = out_path.exists()
            out_path.write_bytes(data)
            try:
                path = out_path.relative_to(repo_root).as_posix()
            except ValueError:
                # A record root outside the watched checkout is a path the
                # detector never looks at, so there is nothing to account for:
                # in a run, every report, since the reports land in the
                # requester's checkout and the detector watches the copy.
                return occupied
            # git's own word on the path, and the fingerprint of the text
            # handed in rather than of the file just written: a cell writing
            # between the write and the hash would otherwise have its content
            # recorded as the runner's own (PR #147 finding 3).
            self._writes[path] = (git_status_code_for_path(out_path, repo_root),
                                  blob_fingerprint(data))
            return occupied

    def stray_paths_since(self, baseline: dict,
                          repo_root: pathlib.Path = None) -> list:
        """Paths changed since baseline that this run can account for — its own
        reports excepted, another live run's reports left out of it.

        Under a watched ignored path this run accounts for what was on disk
        when it started, what its own ledger wrote, and everything inside the
        record directory it owns except its scratch subtree, where the cells
        are told to work. A file that merely appears elsewhere under
        the record root is what a second invocation of this runner
        legitimately creates, and from here the two are indistinguishable.
        Everything git reports outside those paths is compared in full, as
        before.
        """
        repo_root = repo_root or self._repo_root
        with self._lock:
            expected = {**baseline, **self._writes}
            own_dir = self._own_record_directory(repo_root)
            # The subtree holding every cell's sanctioned working space; None
            # when this run has no record directory inside the repository.
            scratch_root = (None if own_dir is None
                            else f"{own_dir}/{CELL_SCRATCH_DIRECTORY_NAME}")
            now = {path: entry
                   for path, entry in worktree_snapshot(repo_root).items()
                   if self._reportable_by_this_run(path, entry, expected,
                                                   own_dir, scratch_root)}
            return stray_paths(expected, now)

    def _own_record_directory(self, repo_root: pathlib.Path):
        """This run's record directory, repo-relative, or None when it has
        none or it lies outside the repository."""
        if self._own_record_dir is None:
            return None
        try:
            return self._own_record_dir.relative_to(repo_root).as_posix()
        except ValueError:
            return None

    @staticmethod
    def _reportable_by_this_run(path: str, entry: tuple, expected: dict,
                                own_dir: str, scratch_root: str) -> bool:
        # This run's scratch subtree, exempt whatever git says about the path:
        # every cell is given a directory under it and told to keep its notes
        # and drafts there, so a write there is the behaviour the prompt asked
        # for, not a stray (user-ruled 2026-08-29). Only this run's scratch —
        # an earlier run's leftover scratch was on disk at the start, sits in
        # the baseline, and is compared like any other file.
        if scratch_root is not None and path.startswith(scratch_root + "/"):
            return False
        if path in expected or not path_watched_as_ignored(path):
            return True
        if own_dir is not None and (path == own_dir
                                    or path.startswith(own_dir + "/")):
            return True
        return entry[0] not in RunnerReportWriteLedger.NEW_TO_GIT_STATUS_CODES


def record_directory_target_stem(target: pathlib.Path) -> str:
    """The target's part of its record directory's name: the file's stem, and
    for a skill its directory's name before it. Every skill's file is
    `SKILL.md`, so two skills checked on one day were told apart only by a
    `-2` suffix (nedschorus#412, item 7)."""
    if target.stem == "SKILL":
        return f"{target.parent.name}-{target.stem}"
    return target.stem


def repository_relative_review_path(path: str, repo_root: pathlib.Path):
    """`path`, a `--target` or `--context` argument, as the repository-relative
    name the cells are given, or None when it resolves outside `repo_root`.

    The cells run in a copy of the last commit and resolve a relative name
    inside that copy. A name passed on as written would send them elsewhere:
    an absolute path inside the checkout names the requester's live file,
    which the copy exists to keep the cells away from, and it passed every
    check until a cold read of the skill found it (2026-10-01). So the name
    is the resolved file's place under the resolved root: `.` and `..`
    segments are folded, a checkout reached through a symbolic link (macOS's
    /tmp) still counts as this checkout, and a symbolic link inside the
    checkout is named by the file it leads to, which the copy holds too. A
    path that leaves the checkout, through `..` or through a symbolic link,
    has no name in the copy."""
    try:
        return (repo_root / path).resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None


def uncommitted_review_paths(paths: list, repo_root: pathlib.Path) -> list:
    """The paths among these that differ from the checkout's last commit, that
    git does not track, or that lie outside the checkout: the cells read a
    copy of that commit, so for these they would read a text the requester
    did not mean, or none at all. Returned as given."""
    root = repo_root.resolve()
    git_names = {}
    for path in paths:
        try:
            git_names[path] = (repo_root / path).resolve().relative_to(root).as_posix()
        except ValueError:
            git_names[path] = None
    inside = sorted({name for name in git_names.values() if name is not None})
    tracked, changed = set(), set()
    if inside:
        listed = subprocess.run(
            ["git", "ls-files", "-z", "--", *inside], cwd=repo_root,
            stdout=subprocess.PIPE, text=True, check=False)
        tracked = set(filter(None, listed.stdout.split("\0")))
        status = subprocess.run(
            ["git", "status", "--porcelain", "-z", "-uall", "--", *inside],
            cwd=repo_root, stdout=subprocess.PIPE, text=True, check=False)
        fields = status.stdout.split("\0")
        index = 0
        while index < len(fields):
            entry = fields[index]
            index += 1
            if not entry:
                continue
            # A rename's origin path follows as its own field, as in
            # worktree_snapshot.
            if entry[0] in ("R", "C"):
                index += 1
            changed.add(entry[3:])
    return [path for path, name in git_names.items()
            if name is None or name not in tracked or name in changed]


@contextlib.contextmanager
def review_copy_of_commit(commit: str, record_name: str,
                          repo_root: pathlib.Path):
    """A copy of `repo_root`'s repository at `commit`, made for one run and
    removed when the run ends, a run that fails included: the checkout every
    cell reads and works in.

    The cells used to read the requester's live checkout for the tens of
    minutes a run takes. So the requester could change nothing while they ran
    (the write detector could not tell the requester's edit from a cell's), a
    text edited mid-run was not the text the provenance line named, and a
    cell's stray write landed in the checkout itself (nedschorus#161). In a
    copy of the commit the reviewed text is exactly that commit, the
    requester's checkout is free for its own work again, and a cell's write
    lands in the copy, where the detector reports it and the removal throws
    it away (user-ruled 2026-09-30, walk
    open-questions-concerns-and-recommendations-2026-09-30, item 2, "Y").

    A clone, not a `git worktree`: a worktree shares the repository's refs,
    config and stash, which every session's checkout shares too, so a cell
    running `git stash` or `git checkout -b` in it would change the live
    repository. `--local` hardlinks the object store where it can, so the
    copy has the whole history in about a third of a second (measured on
    this repository, 2026-09-30), a commit on no branch included. The clone
    names the live checkout as its `origin` remote, the one way left from the
    copy back into it, so the remote is removed; the live repository's own
    `origin/*` refs are fetched in by path instead, so `origin/main` in the
    copy means what it means in the checkout. Made under REVIEW_COPIES_ROOT,
    in a directory of its own named for the record.
    """
    REVIEW_COPIES_ROOT.mkdir(parents=True, exist_ok=True)
    remove_review_copies_no_live_run_owns()
    holder, owner_file = claim_review_copy_directory(record_name)
    checkout = holder / "checkout"
    steps = (
        (["git", "clone", "--quiet", "--local", "--no-checkout",
          str(repo_root), str(checkout)], repo_root),
        (["git", "remote", "remove", "origin"], checkout),
        (["git", "fetch", "--quiet", "--no-tags", str(repo_root),
          "+refs/remotes/origin/*:refs/remotes/origin/*"], checkout),
        (["git", "checkout", "--quiet", "--detach", commit], checkout),
    )
    # One try from the claim on, so the copy is removed however the run ends:
    # a git step that fails, a run that raises, and a run a stop signal ends
    # while the copy is still being made.
    try:
        for command, cwd in steps:
            step = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                  check=False)
            if step.returncode != 0:
                raise RuntimeError(f"{' '.join(command[:2])} failed: {step.stderr.strip()}")
        yield checkout
    finally:
        remove_directory_whatever_signal_arrives(holder)
        if holder.exists():
            # The owner file stays, unlocked once this run ends, so the next
            # run tries the removal again.
            print(review_copy_not_removed_line(holder),
                  flush=True)
        else:
            holder.with_name(holder.name + REVIEW_COPY_OWNER_FILE_SUFFIX).unlink(
                missing_ok=True)
        owner_file.close()


def review_copy_not_removed_line(holder: pathlib.Path) -> str:
    """The line a run prints when a review copy's removal leaves it in place.
    The copy's owner file stays, and its lock is released when this run ends,
    so the next run's remove_review_copies_no_live_run_owns removes the copy;
    the requesting agent has nothing to do."""
    return (f"WARNING: the review copy could not be removed: {holder}. "
            f"Leave it; the next sanity-check run removes it.")


def remove_directory_whatever_signal_arrives(directory: pathlib.Path) -> None:
    """Remove `directory`, to the end: a stop signal that arrives partway is
    raised again only after the removal has run through. The first stop signal
    makes every later one do nothing, so the second pass is not interrupted."""
    try:
        shutil.rmtree(directory, ignore_errors=True)
    except RunStoppedBySignal:
        shutil.rmtree(directory, ignore_errors=True)
        raise


def claim_review_copy_directory(record_name: str) -> tuple:
    """A new, empty directory under REVIEW_COPIES_ROOT for one run's review
    copy, and the open owner file beside it, locked for as long as this run
    lives: (directory, owner file).

    The lock is what tells a live run's copy from one a dead run left behind
    (remove_review_copies_no_live_run_owns). The operating system drops it
    when the process ends, however it ends, SIGKILL included, so no run has to
    reach a line of its own for its copy to become removable; and two runs at
    once each hold their own, so neither removes the other's. The owner file
    is made and locked before the directory exists, so a directory with no
    owner file is never a live run's. Another run may lock and remove an owner
    file in the moment between its creation and this run's lock; the lock
    would then be on a file no path names, so the file's identity is checked
    under the lock and the claim starts again with a new name. The file's text
    names the process, for a person reading the directory."""
    while True:
        descriptor, owner_name = tempfile.mkstemp(
            prefix=f"{record_name}-", suffix=REVIEW_COPY_OWNER_FILE_SUFFIX,
            dir=REVIEW_COPIES_ROOT)
        owner_file = os.fdopen(descriptor, "w", encoding="utf-8")
        fcntl.flock(owner_file.fileno(), fcntl.LOCK_EX)
        holder = pathlib.Path(owner_name[:-len(REVIEW_COPY_OWNER_FILE_SUFFIX)])
        try:
            still_named = (os.stat(owner_name).st_ino
                           == os.fstat(owner_file.fileno()).st_ino)
            if still_named:
                holder.mkdir()
        except FileNotFoundError:
            still_named = False
        except FileExistsError:
            # A directory of that name with no owner file until now: a copy
            # left by a runner older than owner files. Leave it to the next
            # run's removal and take another name.
            pathlib.Path(owner_name).unlink(missing_ok=True)
            still_named = False
        if still_named:
            owner_file.write(f"process {os.getpid()}, started "
                             f"{datetime.datetime.now().isoformat(timespec='seconds')}\n")
            owner_file.flush()
            return holder, owner_file
        owner_file.close()


def remove_review_copies_no_live_run_owns() -> list:
    """Remove every review copy under REVIEW_COPIES_ROOT that no live run
    owns, and return the directories removed.

    A run removes its own copy when it ends, and a run ended by SIGTERM,
    SIGINT or SIGHUP does too (see WHEN A RUN IS STOPPED in the module
    docstring). A run ended by SIGKILL, or by the machine stopping, cannot:
    its copy, a whole checkout, would stay for good, one more for each such
    run, which review of the pull request that introduced the copy measured.
    So each run, before it makes its own copy, removes the ones left behind.
    A copy is a live run's while that run holds the lock on its owner file
    (claim_review_copy_directory); a lock this function can take means the
    owner is gone. A directory with no owner file was made before copies had
    owners, by a runner that never reached main, and is removed too. An owner
    file with no directory is what a run killed between the two leaves, and is
    removed when its lock can be taken. Two runs starting together may both
    try one dead copy: one takes the lock and removes it, the other finds the
    lock held and leaves it alone.
    """
    removed = []
    for holder in sorted(path for path in REVIEW_COPIES_ROOT.iterdir() if path.is_dir()):
        owner_path = holder.with_name(holder.name + REVIEW_COPY_OWNER_FILE_SUFFIX)
        owner_file = lock_owner_file_no_live_run_holds(owner_path)
        if owner_file is None and owner_path.exists():
            continue
        if not holder.is_dir():
            # Its own run removed it, and its owner file, since this function
            # listed the directory: nothing was left behind.
            if owner_file is not None:
                owner_file.close()
            continue
        remove_directory_whatever_signal_arrives(holder)
        if holder.exists():
            print(review_copy_not_removed_line(holder),
                  flush=True)
        else:
            removed.append(holder)
            print(f"removed: a review copy an earlier run left behind, {holder}",
                  flush=True)
            owner_path.unlink(missing_ok=True)
        if owner_file is not None:
            owner_file.close()
    for owner_path in sorted(REVIEW_COPIES_ROOT.glob("*" + REVIEW_COPY_OWNER_FILE_SUFFIX)):
        if owner_path.with_name(owner_path.name[:-len(REVIEW_COPY_OWNER_FILE_SUFFIX)]).exists():
            continue
        owner_file = lock_owner_file_no_live_run_holds(owner_path)
        if owner_file is not None:
            owner_path.unlink(missing_ok=True)
            owner_file.close()
    return removed


def lock_owner_file_no_live_run_holds(owner_path: pathlib.Path):
    """The owner file at `owner_path`, open and locked by this process, when
    no live run holds its lock; None when a live run does, when the file is
    not there, or when the path came to name another file while this function
    waited for nothing: the lock is asked for without waiting."""
    try:
        owner_file = open(owner_path, "r+", encoding="utf-8")
    except OSError:
        return None
    try:
        fcntl.flock(owner_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if os.stat(owner_path).st_ino == os.fstat(owner_file.fileno()).st_ino:
            return owner_file
    except OSError:
        pass
    owner_file.close()
    return None


def processes_under_this_one() -> dict:
    """{pid: parent pid} for every process on the machine but the `ps` that
    listed them, from one `ps` call (the same flags on macOS and Linux); {}
    when ps cannot be run.

    The `ps` that lists the processes is left out because it is a child of the
    process that asks, and stop_processes_this_run_started walks the asking
    process's own children: each reading would hand it one more child, the
    reader of that reading, and the walk would never end."""
    try:
        with subprocess.Popen(["ps", "-A", "-o", "pid=", "-o", "ppid="],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              text=True) as listing:
            listed, _ = listing.communicate()
            reader = listing.pid
    except OSError:
        return {}
    parents = {}
    for line in listed.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0].isdigit() and fields[1].isdigit():
            parents[int(fields[0])] = int(fields[1])
    parents.pop(reader, None)
    return parents


class RunStoppedBySignal(BaseException):
    """A stop signal ended this run: raised in the main thread by
    stop_run_on_signal, after the agents' processes were stopped, so that
    every `finally` and context manager between the run and main() does its
    work, the review copy's removal among them. A BaseException, so that no
    `except Exception` on the way takes it for an error of its own."""

    def __init__(self, signal_number: int) -> None:
        super().__init__(signal_number)
        self.signal_number = signal_number


def stop_processes_this_run_started() -> None:
    """Stop every process under this one: the agent-binaries of the cells in
    flight, whatever they started, and a git or shipper call of the runner's
    own. Prints nothing: it runs inside a signal handler, where the main
    thread may hold the run log's lock.

    This process's whole tree is stopped this way: frozen top-down with
    SIGSTOP, re-reading the process table after each level, so a process
    cannot start another while the tree is collected; then SIGTERM and SIGCONT to all, so each can end on
    its own terms; then SIGKILL to whatever is left after the grace. The
    cells' threads reap the agent-binaries they launched; what those started
    is reaped by init.
    """
    this_process = os.getpid()
    frozen, tried, parents_collected = [], {this_process}, {this_process}
    while True:
        frontier = [pid for pid, parent in processes_under_this_one().items()
                    if parent in parents_collected and pid not in tried]
        if not frontier:
            break
        for pid in frontier:
            tried.add(pid)
            try:
                os.kill(pid, signal.SIGSTOP)
            except (ProcessLookupError, PermissionError):
                continue
            frozen.append(pid)
            parents_collected.add(pid)
    for signal_number in (signal.SIGTERM, signal.SIGCONT):
        for pid in frozen:
            try:
                os.kill(pid, signal_number)
            except (ProcessLookupError, PermissionError):
                pass

    def still_running(pid: int) -> bool:
        # A process that has ended and that nobody has reaped yet is still in
        # the table; `ps` says so, and a signal to it would say nothing.
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                               capture_output=True, text=True, check=False)
        return not state.stdout.strip().startswith("Z")

    deadline = time.monotonic() + STOPPED_PROCESS_GRACE_SECONDS
    while time.monotonic() < deadline and any(still_running(pid) for pid in frozen):
        time.sleep(0.1)
    # SIGKILL to what is left, and to whatever is under this process now that
    # was not frozen: a process a frozen one started after SIGCONT, or a git
    # call a cell's thread made after the first reading. No agent-binary
    # starts a review after RUN_STOPPED is set
    # (run_agent_binary_unless_run_stopped); a cell saving its report may
    # still run the `--version` probe (runtime_cli_version), which exits on
    # its own.
    table = processes_under_this_one()
    under_this_process, grew = {this_process}, True
    while grew:
        found = {pid for pid, parent in table.items() if parent in under_this_process}
        grew = not found <= under_this_process
        under_this_process |= found
    for pid in set(frozen) | (under_this_process - {this_process}):
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def stop_signal_after_the_first_does_nothing(_signal_number: int, _frame) -> None:
    """The handler a stop signal meets once the run is already stopping: it
    does nothing, so the stopping and the removal of the review copy are not
    cut short.

    A handler set from Python and not SIG_IGN, because an ignored disposition
    survives exec and a handled one does not. The stop handler waits for
    AGENT_BINARY_LAUNCH_LOCK, and a cell's thread may be starting an
    agent-binary under that lock in the same moment; with SIG_IGN that
    agent-binary started with SIGTERM, SIGINT and SIGHUP ignored, so the
    SIGTERM that stops it did nothing, and it and whatever it started ran on
    until the SIGKILL after STOPPED_PROCESS_GRACE_SECONDS. A handled
    disposition is reset to the default by exec, so the agent-binary can end
    on the SIGTERM."""


def stop_run_on_signal(signal_number: int, _frame) -> None:
    """The handler main() installs for RUN_STOP_SIGNALS while a run is under
    way: see WHEN A RUN IS STOPPED in the module docstring. Every later stop
    signal does nothing from here on (stop_signal_after_the_first_does_nothing),
    so the stopping and the removal of the review copy are not themselves cut
    short."""
    for number in RUN_STOP_SIGNALS:
        signal.signal(number, stop_signal_after_the_first_does_nothing)
    # Under the lock a cell's thread holds from reading RUN_STOPPED to
    # starting its agent-binary: see run_agent_binary_unless_run_stopped.
    global CELLS_FINISHED_AT_THE_STOP
    # Copied before the wait for the lock: a cell that finishes during that
    # wait was still running when the signal came.
    CELLS_FINISHED_AT_THE_STOP = frozenset(CELLS_FINISHED)
    with AGENT_BINARY_LAUNCH_LOCK:
        RUN_STOPPED.set()
    stop_processes_this_run_started()
    raise RunStoppedBySignal(signal_number)


class RunOutputCopiedToRecordLog:
    """This run's standard output, also written to SANITY_CHECK_RUN_LOG_FILE_NAME in its
    record, so a later reader can see every warning the run printed; an agent
    used to copy it there by hand, when it remembered (nedschorus#412, item 3).

    It stands in for sys.stdout from the start of a run. What is printed
    before the record directory exists — the SKIPPED and LEAK-WARNING lines —
    is held and written when `attach` names the file. `detach` closes the file
    before the record is shipped, so the copy in the log-store is the whole
    log and the add-only shipper finds it unchanged when the dispositions file
    is shipped after it. The cells print from several threads; the lock keeps
    the file's writes whole.
    """

    def __init__(self, stream) -> None:
        self.stream = stream
        # The record directory, once `attach` has named the log in it: what a
        # run stopped by a signal names in its STOPPED line, and ships.
        self.record_directory = None
        # None until every cell has ended, then how many reports the run
        # saved; also set when a stop signal ended no cell. Such a stop has
        # stopped no agent, and main() ends the run as a finished run ends.
        self.reports_saved_once_cells_ended = None
        self._held = []
        self._file = None
        self._lock = threading.Lock()

    def write(self, text: str) -> int:
        self.stream.write(text)
        with self._lock:
            if self._file is not None:
                self._file.write(text)
            elif self._held is not None:
                self._held.append(text)
        return len(text)

    def flush(self) -> None:
        self.stream.flush()
        with self._lock:
            if self._file is not None:
                self._file.flush()

    def attach(self, log_path: pathlib.Path) -> None:
        with self._lock:
            self.record_directory = log_path.parent
            self._file = open(log_path, "w", encoding="utf-8")
            self._file.write("".join(self._held))
            self._held = None

    def detach(self) -> None:
        with self._lock:
            if self._file is not None:
                self._file.close()
            self._file = None
            self._held = None


def fresh_record_dir(target_stem: str) -> pathlib.Path:
    """A record directory this run owns alone: the date-stem name, suffixed
    -2, -3, ... when that name is taken — a same-day second pass or re-run
    never overwrites earlier reports (Codex finding on PR #98).

    The directory is claimed by creating it, not by testing first and creating
    after: two runs starting together on the same target and date both pass a
    look-then-create test and return the same path, and the second overwrites
    the first (found by `codex exec review` on PR #102)."""
    base = RECORDS_ROOT / f"{datetime.date.today().isoformat()}-{target_stem}"
    counter = 1
    while True:
        out_dir = base if counter == 1 else pathlib.Path(f"{base}-{counter}")
        try:
            out_dir.mkdir(parents=True)
            return out_dir
        except FileExistsError:
            counter += 1


def cell_scratch_dir(out_dir: pathlib.Path, cell: str) -> pathlib.Path:
    """One cell's sanctioned working space, created here:
    `<record dir>/scratch/<audit>-<runtime>/`.

    A review agent's deliverable is its reply, but an agent working a document
    still needs somewhere to put notes and drafts. The prompts used to answer
    that with a prohibition — "write no files" — which the agents did not
    reliably keep (nedschorus#161) and the write detector then reported. A
    sanctioned directory replaces the prohibition (user-ruled 2026-08-29): the
    path is substituted into that cell's prompt, the detector exempts the
    subtree, and nothing here is ever read as findings.

    Inside the run's record directory rather than a temporary one, so it is
    archived with the run and disposed of when the record is — no second
    lifetime to manage. Per cell rather than per run, so two cells writing at
    once cannot overwrite each other's notes; the exemption is of the whole
    subtree, because the detector's checks are per run and cannot tell which
    cell is asking.
    """
    scratch = out_dir / CELL_SCRATCH_DIRECTORY_NAME / cell
    scratch.mkdir(parents=True, exist_ok=True)
    return scratch


class FailedLaunch(typing.NamedTuple):
    """One launch of a cell that saved no report: the cause class and detail
    its lines carry, and the claude chain's attempts when there were any."""

    cause_class: str
    detail: str
    attempts: str = ""


def launch_cell_once(cell: str, attack: str, runtime: str, prompt: str,
                     target: str, out_dir: pathlib.Path, baseline_status: dict,
                     corpus: tuple, report_ledger: RunnerReportWriteLedger,
                     checkout: pathlib.Path, relaunched_after: str = ""):
    """Launch one cell once, and save its report when it wrote one. Returns
    None when the report was saved, and the FailedLaunch otherwise; prints the
    agent-binary's own words and the launch's warnings, and neither the
    RETRYING: nor the FAILED: line, which are run_cell's."""
    fresh_eyes = attack == "fresh-eyes"
    runner = run_claude if runtime == "claude" else run_codex
    try:
        # A runner may return the four values this runner's launchers returned
        # before a failed launch carried its cause; the test file's stand-ins
        # do. The cause is then read off the exit code alone.
        code, output, model, fallback_from, *cause = runner(prompt, checkout)
    except subprocess.TimeoutExpired as timeout:
        # What the runtime wrote before it was cut off, printed before the
        # cell's FAILED line, both streams in run_claude's order: every other
        # ending keeps a failed runtime's words, and this one dropped them. The
        # exception holds the streams of the attempt that timed out and no
        # other — run_claude prints each earlier failed attempt's words as that
        # attempt ends, so they are already out and are not repeated here. A
        # codex cell's streams hold its whole session, so only their last
        # lines are printed, as for a codex launch that failed. Each piece
        # ends its own line, because a stream cut off mid-write rarely does,
        # and the FAILED line must still start one. The cell still fails:
        # whether a timeout should fall back to the chain's next model is not
        # decided here.
        for stream in (timeout.stderr, timeout.stdout):
            words = captured_stream_as_text(stream)
            if runtime == "codex":
                words = last_lines_of_stream(words, CODEX_FAILED_LAUNCH_PRINTED_TAIL_LINES)
            if words:
                print(words, end="" if words.endswith("\n") else "\n", flush=True)
        return FailedLaunch(CAUSE_CLASS_TIMEOUT, f"after {CELL_TIMEOUT_SECONDS}s")
    except OSError as exc:
        # A missing or unexecutable CLI fails this cell, never the whole run.
        return FailedLaunch(*common.classify_failed_attempt(
            stdout="", stderr="", exit_code=None, recognised_texts=(),
            start_error=str(exc)))
    if code != 0:
        # The attempts, when there were several: a claude cell whose whole
        # chain failed exits 1 for every reason, so the exit code alone says
        # nothing about which models were tried or how they ended.
        cause_class, detail = (cause[0] if cause and cause[0]
                               else (f"exit-{code}", "no output"))
        return FailedLaunch(cause_class, detail, fallback_from)
    stray = report_ledger.stray_paths_since(baseline_status)
    if stray:
        print(f"WARNING: the review copy was modified outside the cells' scratch "
              f"directories, seen when {cell} finished: {', '.join(stray)}",
              flush=True)
    # After the worktree check, so a cell that ran to the end has its writes
    # compared whatever it returned; before the quote scan and the write, so a
    # text that is not a report raises no warnings to triage, never lands as a
    # report, and is printed so the runtime's words survive (nedschorus#397).
    missing = missing_report_phrases(attack, output)
    if missing:
        print(output, flush=True)
        return FailedLaunch(CAUSE_CLASS_NOT_A_REPORT,
                            f"the text it returned lacks {', '.join(missing)}")
    if not fresh_eyes:
        quote_scan(corpus, output, cell)
    revision = reviewed_revision(baseline_status, checkout)
    out_path = out_dir / f"{cell}.md"
    # Through the ledger, not straight to disk: the report lands in a directory
    # the write detector watches, and the ledger is what tells this write from
    # a cell's.
    overwrote_stray_write = report_ledger.write_report(
        out_path,
        provenance_line(runtime, model, attack, target, fresh_eyes, revision,
                        fallback_from, relaunched_after)
        + "\n\n" + output,
    )
    if overwrote_stray_write:
        print(f"WARNING: {cell} found a stray write at its own report path and "
              f"overwrote it: {out_path}", flush=True)
    print(f"saved: {out_path}", flush=True)
    return None


def failed_launch_is_relaunched(cause_class: str) -> bool:
    """Whether the runner launches a cell a second time after a first launch
    that failed for this cause (see WHY THE RUNNER DECIDES THE RELAUNCH in
    the module docstring): not when only the user can clear the cause, and not
    after a timeout."""
    return (cause_class not in common.USER_CLEARABLE_CAUSE_CLASSES
            and cause_class != CAUSE_CLASS_TIMEOUT)


def rerun_command_for_cell(attack: str, runtime: str, target: str, context: list,
                           problem_statement: pathlib.Path) -> str:
    """The command that runs this one cell again, as one line a shell takes
    as it stands: this run's target, every context document and the
    sanity-check-request when one was passed, with the cell's attack and
    runtime as the only `--attack` and `--runtime`. Both flags are repeatable,
    so a command that kept the first run's would run more than the one cell.
    The program and the request are named by absolute path and the documents
    by their repository-relative names, which the program resolves against its
    own checkout, so the line works from any directory."""
    command = [str(pathlib.Path(__file__).resolve()), "--target", target]
    for path in context:
        command += ["--context", path]
    if problem_statement is not None:
        command += ["--problem-statement", str(problem_statement.resolve())]
    command += ["--attack", attack, "--runtime", runtime]
    return shlex.join(command)


def failed_cell_lines(attack: str, runtime: str, failure: FailedLaunch,
                      relaunched: bool, rerun_command: str) -> list:
    """The lines a cell that saved no report ends on: its FAILED: line, and
    under it what the requesting agent does next. The lines after the first
    are instructions and nothing else; why each is what it is stands in the
    module docstring, under WHY THE RUNNER DECIDES THE RELAUNCH."""
    cell = f"{attack}-{runtime}"
    separator = common.CAUSE_SEPARATOR
    failed = f"FAILED: {cell}{separator}{failure.cause_class}{separator}{failure.detail}"
    if relaunched:
        failed += " (relaunched once)"
    if failure.attempts:
        failed += f" (models tried: {failure.attempts})"
    if failure.cause_class in common.USER_CLEARABLE_CAUSE_CLASSES:
        return [
            failed,
            "Tell the user what the FAILED line above says.",
            "After the user has cleared the cause, run the command on the next line.",
            rerun_command,
        ]
    other_cell = "-".join((attack, *(name for name in RUNTIMES if name != runtime)))
    return [
        failed,
        f"When a run of this sanity-check saved {other_cell}'s report, triage "
        f"the {attack}-attack from that report.",
        f"When no run of this sanity-check saved a report of the {attack}-attack, "
        f"write in finding-dispositions.md that the {attack}-attack is unreviewed.",
    ]


def run_cell(attack: str, runtime: str, target: str, context: list,
             problem_statement: pathlib.Path, out_dir: pathlib.Path,
             baseline_status: dict, corpus: tuple,
             report_ledger: RunnerReportWriteLedger,
             checkout: pathlib.Path = None,
             scratch_record_dir: pathlib.Path = None) -> tuple:
    """Run one cell in `checkout`, the review copy, with its scratch directory
    under `scratch_record_dir`, the copy's record directory; returns
    (cell_name, ok). The report is written to `out_dir`, the record in the
    requester's checkout. Without a copy, both fall back to the requester's
    checkout and `out_dir`.

    A first launch that saves no report is followed by one more, with the same
    prompt, in the same copy and the same scratch directory, unless
    failed_launch_is_relaunched says the cause is not one a second launch can
    clear. A cell that ends with no report prints failed_cell_lines."""
    cell = f"{attack}-{runtime}"
    checkout = checkout or REPO_ROOT
    prompt = assemble_prompt(attack, target, context, problem_statement,
                             str(cell_scratch_dir(scratch_record_dir or out_dir, cell)))

    def launch(relaunched_after: str = ""):
        return launch_cell_once(cell, attack, runtime, prompt, target, out_dir,
                                baseline_status, corpus, report_ledger, checkout,
                                relaunched_after)

    if RUN_STOPPED.is_set():
        return cell, False
    failure = launch()
    if failure is None:
        CELLS_FINISHED.add(cell)
        return cell, True
    if RUN_STOPPED.is_set():
        # The launch ended because the run was stopped. No second launch, and
        # none of the lines a failed cell ends on: they tell the requesting
        # agent how to go on with this run's reports, and the run's STOPPED
        # line says what a stopped run calls for instead.
        return cell, False
    relaunched = failed_launch_is_relaunched(failure.cause_class)
    if relaunched:
        separator = common.CAUSE_SEPARATOR
        print(f"{RETRYING_PREFIX} {cell}{separator}{failure.cause_class}"
              f"{separator}{failure.detail}", flush=True)
        failure = launch(relaunched_after=failure.cause_class)
        if failure is None:
            CELLS_FINISHED.add(cell)
            return cell, True
        if RUN_STOPPED.is_set():
            return cell, False
    # One write, so that another cell's lines, printed from its own thread,
    # cannot land between this cell's FAILED line and the instructions that
    # say "the FAILED line above".
    lines = failed_cell_lines(
        attack, runtime, failure, relaunched,
        rerun_command_for_cell(attack, runtime, target, context, problem_statement))
    sys.stdout.write("".join(line + "\n" for line in lines))
    sys.stdout.flush()
    CELLS_FINISHED.add(cell)
    return cell, False


def ship_record(record_dir: pathlib.Path) -> str:
    """Run the shipper on this run's record and return its one line, or a
    FAILED line of this program's own when the shipper could not run.

    Never raises, and never changes the run's exit code: the shipper's outcome
    is reported, not enforced (nedschorus#392; the same shape as
    nc-systems/cold-read/cold-read-grid.py's ship_record). A sanity check that found
    something and could not reach ned-box has still found it, and the record
    stays on disk for a later run.
    """
    try:
        completed = subprocess.run(
            [sys.executable, str(RECORD_SHIPPER), str(record_dir)],
            capture_output=True, text=True, check=False)
    except OSError as error:
        return f"FAILED: the shipper could not be run ({error}); the record stays on disk."
    sys.stderr.write(completed.stderr)
    line = completed.stdout.strip().splitlines()
    return line[0] if line else (
        f"FAILED: the shipper printed nothing (exit {completed.returncode}); "
        f"the record stays on disk.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--target", default=None,
                        help="path of the document under review, inside this "
                             "checkout (required except with --print requester "
                             "or fresh-eyes)")
    parser.add_argument("--context", action="append", default=[],
                        help="context document, inside this checkout (repeatable)")
    parser.add_argument("--problem-statement", type=pathlib.Path, default=None,
                        help="review-request file for the fresh-eyes audit; "
                             "without it the fresh-eyes agents are SKIPPED, loudly")
    parser.add_argument("--attack", action="append", choices=list(ATTACKS), default=None,
                        help="run only this audit (repeatable); default: all three")
    parser.add_argument("--runtime", action="append", choices=list(RUNTIMES), default=None,
                        help="run only this runtime's agents (repeatable); default: both")
    parser.add_argument("--print", dest="print_surface",
                        choices=list(ATTACKS) + ["requester"], default=None,
                        help="print a review surface to stdout instead of running: "
                             "an audit's assembled prompt, or the requester manual")
    args = parser.parse_args()

    if args.print_surface == "requester":
        fresh_eyes_text = ATTACK_PROMPT_FILES["fresh-eyes"].read_text(encoding="utf-8")
        heading = "## Writing the problem statement"
        start = fresh_eyes_text.find(heading)
        # Bounded by the marker on a line of its own, so a sentence that
        # spelled it could not end this section early. No shipped header
        # spells it today; the newlines are what makes that independent of
        # how the headers are worded.
        end = fresh_eyes_text.find("\n" + PROMPT_BODY_MARKER + "\n")
        if start == -1 or end == -1 or start >= end:
            print("requester section not found in the fresh-eyes prompt", file=sys.stderr)
            return 2
        section = fresh_eyes_text[start:end].strip()
        # The section's closing sentence points at the marker and body below
        # it, which this surface deliberately omits — printed here it would
        # dangle (cold-read finding).
        tail_start = section.rfind("\n\nEverything below the marker")
        if tail_start != -1:
            section = section[:tail_start].rstrip()
        print("# The requesting agent's manual\n")
        print("## The runner's operating rules (its docstring)\n")
        print(__doc__.strip())
        print()
        print(section)
        return 0

    if args.target is None and args.print_surface != "fresh-eyes":
        parser.error("--target is required except with --print requester or fresh-eyes")

    if args.target is not None:
        # Before anything uses them: the prompt, the provenance line, the
        # record's name and the uncommitted-changes refusal all take the
        # repository-relative name.
        passed = [args.target, *args.context]
        relative = [repository_relative_review_path(path, REPO_ROOT) for path in passed]
        outside = [path for path, name in zip(passed, relative) if name is None]
        if outside:
            for path in outside:
                print(f"{path} resolves outside this checkout, {REPO_ROOT}: pass a "
                      f"file inside it, then rerun this command.", file=sys.stderr)
            return 2
        args.target, args.context = relative[0], relative[1:]
        target_path = REPO_ROOT / args.target
        if not target_path.is_file():
            print(f"target not found: {args.target}", file=sys.stderr)
            return 2
        missing_context = [path for path in args.context
                           if not (REPO_ROOT / path).is_file()]
        if missing_context:
            print(f"context not found: {', '.join(missing_context)}", file=sys.stderr)
            return 2
    if args.problem_statement and not args.problem_statement.is_file():
        print(f"problem statement not found: {args.problem_statement}", file=sys.stderr)
        return 2

    if args.print_surface:
        if args.print_surface == "fresh-eyes" and args.problem_statement is None:
            print("--print fresh-eyes needs --problem-statement", file=sys.stderr)
            return 2
        # A print surface is per audit while a scratch directory is per cell,
        # so the shape is shown with its varying parts left as names: a real
        # path would claim one runtime's directory for both of the audit's
        # cells, and a reader would take it for the literal path.
        illustrative_scratch = (RECORDS_ROOT / "<date>-<target-stem>"
                                / CELL_SCRATCH_DIRECTORY_NAME
                                / f"{args.print_surface}-<runtime>")
        print(assemble_prompt(args.print_surface, args.target, args.context,
                              args.problem_statement, str(illustrative_scratch)))
        return 0

    # Everything the run prints from here is also kept for its record.
    run_log = RunOutputCopiedToRecordLog(sys.stdout)
    sys.stdout = run_log
    # Signal handlers can be set from the main thread alone; a caller running
    # main() on another thread gets the run without them.
    handlers_before = {}
    if threading.current_thread() is threading.main_thread():
        handlers_before = {number: signal.signal(number, stop_run_on_signal)
                           for number in RUN_STOP_SIGNALS}
    stopped_by = None
    try:
        return run_cells_in_review_copy(args, target_path, run_log)
    except RunStoppedBySignal as stopped:
        stopped_by = stopped.signal_number
        saved = run_log.reports_saved_once_cells_ended
        if saved is not None:
            # Every cell had finished before the signal came, so the run ends
            # as a finished run: a STOPPED line would have the agent rerun
            # cells whose reports are all saved. The record is shipped again
            # in case the signal cut its shipping short.
            run_log.detach()
            if saved:
                print_run_completion(run_log.record_directory)
            else:
                print_completion_of_run_that_saved_no_report(run_log.record_directory)
        else:
            print(run_stopped_line(stopped_by, run_log.record_directory), flush=True)
            # Closed before the record is shipped, as at the end of any run;
            # and shipped while later stop signals still do nothing, after the
            # agents are stopped and the review copy is removed, so a run that
            # is killed outright while it ships has already done what must not
            # be left.
            run_log.detach()
            if run_log.record_directory is not None:
                print(f"record: {ship_record(run_log.record_directory)}", flush=True)
    finally:
        run_log.detach()
        sys.stdout = run_log.stream
        for number, handler in handlers_before.items():
            # None is what signal.signal returns for a handler that was not
            # set from Python, and it cannot be set back.
            if handler is not None:
                signal.signal(number, handler)
    # The run ends as a process that signal ended does, so whatever started it
    # reads the ending it asked for: the agents are stopped, the review copy
    # is removed and the log is closed by now.
    sys.stdout.flush()
    signal.signal(stopped_by, signal.SIG_DFL)
    os.kill(os.getpid(), stopped_by)
    return 128 + stopped_by


def run_stopped_line(signal_number: int, record_directory) -> str:
    """The line a run a stop signal ended prints before it ships its record:
    what happened, as the condition, and what the requesting agent does about
    it."""
    name = signal.Signals(signal_number).name
    line = (f"STOPPED: {name} ended this run before it had finished, and the "
            f"runner stopped its agents. Run the same command again for the "
            f"reports this run did not save.")
    if record_directory is not None:
        line += (f" The reports it saved, and this log, are in {record_directory}.")
    return line


def run_cells_in_review_copy(args, target_path: pathlib.Path, run_log: RunOutputCopiedToRecordLog) -> int:
    """main()'s run, once the invocation is known to be usable: the cells in a
    review copy of the checkout's last commit, the reports and the run's log
    in its record, the record shipped. Returns the exit code."""
    attacks = tuple(dict.fromkeys(args.attack)) if args.attack else ATTACKS
    runtimes = tuple(dict.fromkeys(args.runtime)) if args.runtime else RUNTIMES
    cells = []
    for attack in attacks:
        if attack == "fresh-eyes" and args.problem_statement is None:
            for runtime in runtimes:
                print(f"SKIPPED: {attack}-{runtime} (no --problem-statement)", flush=True)
            continue
        for runtime in runtimes:
            cells.append((attack, runtime))

    # Validate every prompt this run will use before any cell launches, so a
    # broken boundary fails before model cost — as documented; until 2026-08-21
    # validation ran lazily inside each cell (cold-read finding, verified).
    for attack in dict.fromkeys(cell_attack for cell_attack, _ in cells):
        prompt_body(attack)

    if not cells:
        print("sanity-check wrote no reports: every agent above failed or was "
              "skipped; there is nothing to triage.", flush=True)
        return 0

    # The cells read a copy of the last commit, so a target or context
    # document that differs from it would be reviewed as it was, not as it is.
    uncommitted = uncommitted_review_paths([args.target, *args.context], REPO_ROOT)
    if uncommitted:
        for path in uncommitted:
            print(f"{path} differs from the last commit or is not tracked: "
                  f"commit it, then rerun this command.", file=sys.stderr)
        return 2
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if head.returncode != 0:
        print(f"Run this from a git checkout that has a commit: "
              f"{head.stderr.strip()}", file=sys.stderr)
        return 2

    stem = record_directory_target_stem(target_path)
    ok = True
    saved_count = 0
    with contextlib.ExitStack() as copy_lifetime:
        try:
            checkout = copy_lifetime.enter_context(
                review_copy_of_commit(head.stdout.strip(), stem, REPO_ROOT))
        except RuntimeError as error:
            print(f"Fix what git names, then rerun this command: {error}",
                  file=sys.stderr)
            return 2

        if args.problem_statement and any(a == "fresh-eyes" for a, _ in cells):
            design_names = coined_names(checkout / args.target)
            leak_scan(design_names, args.problem_statement.read_text(encoding="utf-8"),
                      f"the problem statement ({args.problem_statement})")
            for path in injected_instruction_files(checkout):
                leak_scan(design_names, path.read_text(encoding="utf-8"),
                          f"an injected instruction file ({path})")

        # Claimed only after validation and only when an agent will launch: a
        # refused startup or an all-skipped run must not burn a -N suffix.
        out_dir = fresh_record_dir(stem)
        run_log.attach(out_dir / SANITY_CHECK_RUN_LOG_FILE_NAME)
        if args.problem_statement and any(a == "fresh-eyes" for a, _ in cells):
            shutil.copyfile(args.problem_statement, out_dir / SANITY_CHECK_REQUEST_COPY_FILE_NAME)
        # The cells' scratch directories are made in the copy, where the cells
        # may write, under the record directory's own name; they join the
        # record when the cells are done, before the copy is removed.
        copy_record_dir = checkout / RECORDS_DIRECTORY_NAME / out_dir.name

        baseline_status = worktree_snapshot(checkout)
        corpus = tracked_files_corpus(checkout)
        report_ledger = RunnerReportWriteLedger(copy_record_dir, checkout)
        CELLS_FINISHED.clear()
        global CELLS_FINISHED_AT_THE_STOP
        CELLS_FINISHED_AT_THE_STOP = None
        futures = []
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(cells)) as pool:
                futures = [
                    pool.submit(run_cell, attack, runtime, args.target, args.context,
                                args.problem_statement, out_dir, baseline_status, corpus,
                                report_ledger, checkout, copy_record_dir)
                    for attack, runtime in cells
                ]
                for future in concurrent.futures.as_completed(futures):
                    _, cell_ok = future.result()
                    ok = ok and cell_ok
                    saved_count += 1 if cell_ok else 0
                run_log.reports_saved_once_cells_ended = saved_count
        except RunStoppedBySignal:
            # A stop that came after every cell had finished, saving its
            # report or saying why it could not, cut nothing short: that run
            # ends as a finished run ends, never with a STOPPED line telling
            # the agent to run the whole command again. Any cell still
            # running when the signal came makes it a stopped run, whatever
            # the cell's calls returned afterwards.
            if (run_log.reports_saved_once_cells_ended is None
                    and len(futures) == len(cells)
                    and CELLS_FINISHED_AT_THE_STOP is not None
                    and {f"{attack}-{runtime}" for attack, runtime in cells}
                        <= CELLS_FINISHED_AT_THE_STOP
                    and all(future.done() and future.exception() is None
                            for future in futures)):
                run_log.reports_saved_once_cells_ended = sum(
                    1 for future in futures if future.result()[1])
            raise
        finally:
            # However the cells' part ended, a run a stop signal ended
            # included: what the cells left in their scratch directories is
            # part of the record, and the copy that holds it is removed next.
            scratch = copy_record_dir / CELL_SCRATCH_DIRECTORY_NAME
            if scratch.is_dir():
                shutil.move(str(scratch), str(out_dir / CELL_SCRATCH_DIRECTORY_NAME))
    # Closed before the record is shipped, so the log-store gets the whole log.
    run_log.detach()

    if saved_count:
        print_run_completion(out_dir)
    else:
        print_completion_of_run_that_saved_no_report(out_dir)
    return 0 if ok else 1


def print_completion_of_run_that_saved_no_report(out_dir: pathlib.Path, ship=None) -> None:
    """Ship the record of a run whose every launched agent failed, and say
    where its log is.

    Such a run used to ship nothing and name its record nowhere, so the
    requesting agent could not find the log the run had just saved, the one
    place that keeps each FAILED: line and the lines under it; found in review
    of the pull request that gave the record its log. The record is a log like
    any other run's (see print_run_completion), and the shipper takes a record
    that holds no report. `ship` is the shipper to call, for the test.
    """
    ship = ship or ship_record
    print(f"record: {ship(out_dir)}", flush=True)
    print("sanity-check wrote no reports: every agent above failed or was "
          "skipped; there is nothing to triage. Do what the lines under each "
          f"FAILED: line above say; this run's log, which keeps them, is in {out_dir}.",
          flush=True)


def print_run_completion(out_dir: pathlib.Path, ship=None) -> None:
    """Ship this run's record and say what the requesting agent does next.

    The shipping is the program's, not the agent's (nedschorus#392): the record
    is a log, and a log that reaches the store only when someone remembers to
    push it is a log that is sometimes lost. `ship` is the shipper to call, for
    the test; the default is this module's ship_record.
    """
    ship = ship or ship_record
    print(f"record: {ship(out_dir)}", flush=True)
    print(
            f"sanity-check complete: reports in {out_dir}. Triage each report "
            "(follow up the warnings above, settle hedged claims about code by "
            "reading the code, merge the "
            "runtimes), then present the surviving findings to the user one at a "
            "time for his ruling (the walk-me-through skill). "
            "The record was shipped to the log-store when this run ended (the "
            "`record:` line above says whether it arrived); once "
            "finding-dispositions.md is written, run "
            f"`scripts/sanity-check-record-ship.py {out_dir}` so it joins the "
            "reports there. Leave the record directory in place: these are logs, "
            "kept, not deleted when the work they served lands. A file already in "
            "the store whose content differs is refused rather than replaced, so "
            "ship a dispositions file once it is finished.",
        flush=True,
    )


if __name__ == "__main__":
    sys.exit(main())
