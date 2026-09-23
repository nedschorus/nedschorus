#!/usr/bin/env python3
"""Decide whether a search's empty result is evidence of absence.

THE DEFECT. A command runs, finds nothing, and the agent reads "nothing" as
"there is nothing" when it means "this could not have found anything". The
project's name for the claim is the unvalidated-negative: a negative result is
evidence only once that same check has been seen to return a positive. The rule
was drafted 2026-09-21 after eight of them in one evening across three seats,
and the user ruled this program's shape on 2026-09-23: "Can't you just rerun
some old stuff that didn't work and see if it works? If so, dispatch a subagent
to fix and then measure, don't wait." So: build the check, replay the known
failures through it, and measure the noise on transcripts that already exist,
rather than recording for a day first.

THE FOUR FAILURES THIS WAS BUILT AGAINST, each measured by a seat of this fleet
in the two days before 2026-09-23, and each written down under
scripts/unvalidated-negative-result-check-fixtures/ before any of this was
written:

  1. A counter read six cold-read reports and reported 72 findings; the true
     number was 176. Three whole reports, one of them 17 KB, counted as empty,
     because the reviewers had numbered their findings in four markdown shapes
     and the counter's pattern knew one. The record is
     nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-15-handoff-system-overview-3/;
     the fixture corpus here is that record's finding-heading lines, in the
     shapes the reviewers used, and reproduces the failure at 33 counted out of
     173. Caught by weakened-pattern-control-run-found-matches.
  2. A seat grepped a file for a phrase, saw no match, and concluded the phrase
     was absent. Its pipeline piped through `cut -c1-220`, so it had searched a
     truncation of a one-paragraph line. Reading the file whole reversed the
     conclusion. Caught by truncating-stage-upstream-of-the-search.
  3. A search run over ned-box returned empty three times because `rg` is not
     installed there; `rg: command not found` went to stderr, the pipeline
     discarded it, and the empty stdout was read as a clean result. Caught by
     stderr-discarded-by-the-search-stage, and, wherever the not-found line
     survives into the result, by search-program-missing-on-this-machine and
     exit-status-reports-an-error-not-an-absence. The same shape is in
     the fleet's own transcripts as `timeout: command not found` (for instance
     `timeout 540 python3 scripts/git-gatekeeper-test.py 2>&1 | tail -15;
     echo "exit=${PIPESTATUS[0]}"`, which printed the not-found line and
     `exit=` and was read as a test run).
  4. A file move was checked by searching the codebase for the old path
     `scripts/handoff-supervisor.py`. The search printed nothing, the move was
     declared clean and merged, and two references broke -- they are composed
     at run time as `Path(__file__).with_name("handoff-supervisor.py")`, which
     holds no folder for a path search to match. One of them broke crash
     recovery on ned-box. Caught by
     weakened-pattern-control-run-found-matches.

WHAT IS CHECKABLE AND WHAT IS A GUESS. Every signal below is decided from
evidence, not from a reading of intent: an exit status, a stream that was
written, a stage that appears ahead of the search in the same pipeline, or a
second search actually run. One candidate signal was dropped for being a guess
dressed as a check -- a PATH probe for the search program -- and the reason is
under search-program-missing-on-this-machine. The one signal that runs
anything is the control run, and it runs only a read-only weakened copy of the
same search; it is off unless --run-control is given.

THE GATE, applied before any signal. A pair is judged only when the command
contains a search stage (the grep family, rg, ag, ack, fd, find, `git grep`,
`git log --grep/-S/-G`) AND the result is empty-shaped: no output at all, a
bare `0`, or `grep -c` count lines of which at least one is zero. Without the
gate the noise measurement is meaningless, because thousands of ordinary
`cp`/`mkdir`/`git add` pairs write stderr with an empty stdout.

THE SIGNALS.

  search-program-missing-on-this-machine
      the result says the program was not found: `command not found` in what it
      printed, or an exit status of 127. Read off the result, never off PATH.
      A PATH probe was tried first and dropped on the measurement of
      2026-09-23: on the user's Mac `rg` is not a binary on PATH at all but a
      shell function that Claude Code installs in its shell snapshot, so
      `shutil.which("rg")` returns None while `rg` searches perfectly. A signal
      that reports a working program as missing is the defect this file is
      about, committed by the checker, so PATH is not evidence of absence here.
  exit-status-reports-an-error-not-an-absence
      the exit status is one that means failure rather than no-match: grep's 2,
      126, 127, or ssh's 255. grep's 1 means no match and is not this signal.
  stderr-written-while-stdout-was-empty
      stdout empty, stderr not. Computable only where the two streams were kept
      apart, which for a session transcript means an exit-0 pair.
  stderr-discarded-by-the-search-stage
      the search stage carries `2>/dev/null` or `2>&-`, so an error and a clean
      no-match print the same nothing.
  search-exit-status-discarded-by-a-later-stage
      the search is upstream of a pipe, or is followed by `; echo ...`/`|| true`,
      and neither `pipefail` nor `PIPESTATUS` recovers its status. Corroborating
      only: it never fires on its own where the search's stderr was observable
      and empty, because an empty stderr is the proof that grep did not error.
      The measurement made that rule: it was the only signal on 39 of 67
      firings in the first pass, every one of them with an empty stderr
      recorded beside it, and admitting it alone would have made three firings
      in four wrong.
  truncating-stage-upstream-of-the-search
      `cut -c`/`cut -b`, `head -c`, `head -n`, or `fold -w` stands ahead of the
      search in the same pipeline, so the search read a cut-down input. A
      truncating stage AFTER the search is not this signal; it truncates the
      answer, not the question.
  weakened-pattern-control-run-found-matches
      a weakened copy of the same search, actually run over the same corpus,
      matched where the original did not. Three weakenings, each derived from
      the pattern and each tied to one of the four failures: a pattern holding
      `/` is weakened to its last segment (failure 4); an anchored pattern is
      unanchored; a pattern that is a literal head followed by a regex element
      loses the literal head (failure 1). The control is refused for any
      command carrying shell punctuation -- a pipe, a redirect, `;`, `&&`,
      backticks or `$(` -- so nothing but a bare read-only search is ever run.

MEASURED NOISE, 2026-09-23, on transcripts that already existed -- nothing was
recorded for it and nothing waited a day. 29,694 Bash command/result pairs
(27,937 on the Mac under ~/.claude/projects, 1,757 on ned-box under
/home/nedlern/.claude/projects), which is roughly two months of this fleet's
work. The funnel:

  29,694 pairs replayed
  11,117 carried a search stage
     124 of those returned an empty result
      24 fired

That is 0.81 firings per thousand commands, about one every day or two at this
fleet's rate -- not the hundreds a day that would argue against ever wiring it.
Per signal, counting a pair once per signal it raised:

      24  stderr-discarded-by-the-search-stage           (4 of them alone)
      19  search-exit-status-discarded-by-a-later-stage  (0 alone, by the rule
              above)
       1  exit-status-reports-an-error-not-an-absence    (0 alone)

Of the 24, one is proven rather than judged: a ned-box `grep -rn "settings.local"
... 2>/dev/null` that exited 2, so grep errored and the pipeline discarded the
reason. About four are noise of one kind -- the complaint is formally right and
the negative was true anyway. One of those was checked at its own commit: a
2026-09-02 grep for four seat-name spellings across
scripts/handoff-supervisor.py and scripts/clean-worktrees.py, its stderr sent
to /dev/null, at a commit where both files existed and neither held any of the
four.

THE GATE IS NARROW, and this is the measurement's other result. 10,385
search-shaped commands on the Mac produced only 89 empty results, because this
fleet writes compound commands -- `echo "==="; grep ...; echo` -- and a search's
own emptiness is invisible inside one. The check sees a search only where the
search is the whole command. Widening it means attributing output to stages,
which is not built here.

The control run is not exercised by this measurement: the corpora those
commands searched are gone, and re-running thousands of searches is not a
measurement. Its upper bound is 26 -- the empty results bare enough for a
control to have been derived from them, 18 on the Mac and 8 on ned-box.

NOT WIRED TO ANYTHING. This ships as a program with its tests. Whether it fires
automatically -- in a hook, in the cold-read grid, in a reviewer's brief -- is a
separate decision for the user, to be made after reading the measurement.

USAGE.

  unvalidated-negative-result-check.py --command CMD [--exit-code N]
      [--stdout-file PATH] [--stderr-file PATH] [--stderr-not-captured]
      [--run-control]
      judge one command and its result; prints the instructions it would hand
      an agent. Pass --stderr-not-captured when the two streams were merged
      before you saw them, or an empty stderr is read as proof of no error.

  unvalidated-negative-result-check.py --replay-fixtures [DIR] [--run-control]
      judge every fixture in the directory (default: the fixtures directory
      beside this file) and report, per fixture, whether the check fired. A
      fixture that does not fire is this program failing its own rule, and the
      exit status says so.

  unvalidated-negative-result-check.py --transcripts DIR [--transcripts DIR ...]
      [--limit N] [--top N]
      extract every Bash command/result pair from the session transcripts under
      those directories, run the check over them, and print the funnel, the
      per-signal tally and the commands that fire most often. Controls are never
      run in this mode: the corpora those commands searched are gone.

EXIT STATUS. 0 when the check did not fire (--command) or when every fixture
fired (--replay-fixtures) or when the measurement ran (--transcripts); 1 when
the check fired (--command) or a fixture did not fire (--replay-fixtures);
2 for a bad invocation.

FIXTURE FORMAT. One JSON object per file in the fixtures directory:
  case                 short name of the failure
  provenance           where the command and its result come from
  command              the command as it was run
  exit_code            its exit status, or null when it was not recorded
  stdout, stderr       what it printed
  ran_on_this_machine  false for a command that ran elsewhere, such as over ssh
  control_corpus_root  a directory, relative to the checkout, to run the
                       control run in; absent when no control applies
  must_fire            true for every fixture here
"""

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

PROGRAM = "unvalidated-negative-result-check"

EXIT_QUIET = 0
EXIT_FIRED = 1
EXIT_BAD_INVOCATION = 2

FIXTURES_DIRECTORY_NAME = "unvalidated-negative-result-check-fixtures"

# The programs whose empty output an agent reads as "there is nothing".
SEARCH_PROGRAMS = frozenset({
    "grep", "egrep", "fgrep", "zgrep", "rg", "ripgrep", "ag", "ack", "fd",
    "find", "ugrep",
})

# Stages that cut the input down before the search reads it. The lookahead
# after each flag letter, rather than \b, is deliberate: `cut -c1-220` -- the
# stage that hid failure 2 -- has no word boundary between the `c` and the `1`.
TRUNCATING_STAGE = re.compile(
    r"^(?:cut\s+(?:[^|]*\s)?-[cb](?=[\d\s'\"-])"
    r"|head\s+(?:[^|]*\s)?-[cn](?=[\d\s'\"])"
    r"|head\s+-\d"
    r"|head\s*$"
    r"|fold\s+(?:[^|]*\s)?-w(?=[\d\s'\"]))")

STDERR_DISCARDED = re.compile(r"2>\s*/dev/null|2>&-|2>\s*&\s*-")

# Exit statuses that mean the search failed, not that it found nothing. grep's
# 1 is a clean no-match and is deliberately absent.
ERROR_EXIT_STATUSES = frozenset({2, 126, 127, 255})

COMMAND_NOT_FOUND = re.compile(
    r"(?:^|\n|:\s*)(?:command not found|[^\n:]*:\s*command not found"
    r"|No such file or directory)", re.IGNORECASE)

# What a failed search prints instead of results. A session transcript merges
# the two streams for any command that exited non-zero, so without this a
# search that printed only `rg: command not found` has a stdout that is not
# empty, the gate turns it away, and the very failure this program was built
# for -- failure 3, a missing search program -- goes unjudged. Applied only to
# a non-zero result, where the merge is what happened and a matched line is
# not what is being read.
DIAGNOSTIC_LINE = re.compile(
    r"^(?:[^\s:]+:\s*)?(?:line \d+:\s*)?[^\n]*?"
    r"(?:command not found|No such file or directory|Permission denied"
    r"|Is a directory|cannot open|unrecognized option|invalid option"
    r"|unknown option|Connection refused|Could not resolve hostname"
    r"|Operation timed out|fatal: |^usage: |^Usage: )", re.IGNORECASE)


def split_diagnostics(text):
    """(what the search printed as results, what it printed as complaints)."""
    results = []
    diagnostics = []
    for line in (text or "").splitlines():
        (diagnostics if DIAGNOSTIC_LINE.match(line) else results).append(line)
    return "\n".join(results), "\n".join(diagnostics)

COUNT_LINE = re.compile(r"^(?P<path>.*):(?P<count>\d+)$")

# Lines the harness writes on stderr that are not the command's error output.
# Measured 2026-09-23 over the Mac's transcripts: twelve empty search results
# had anything at all on stderr, and in all twelve that stderr was this note
# and nothing else. Without this the signal reports the harness talking, not a
# search that failed.
HARNESS_NOTE_ON_STDERR = re.compile(r"^\s*Shell cwd was reset to \S+\s*$")

# A signal that is real but not sufficient on its own. Measured 2026-09-23 over
# 27,900 recorded Bash pairs: a swallowed exit status was the only signal on 39
# of 67 firings, and in every one of them the search's stderr was recorded
# separately and was empty -- which is the proof that grep did not error, and
# so that the empty result is a clean no-match. Reported as corroboration, and
# firing only where stderr was not observable.
CORROBORATING_ONLY = "search-exit-status-discarded-by-a-later-stage"

# A pattern's regex elements, for the control run's third weakening.
REGEX_ELEMENT = re.compile(r"\[[^\]]+\]|\\\+|\\\*|\\\{|\.\*|\.\+|\\d|\\w|\\s|\+|\*")

SHELL_PUNCTUATION_THAT_REFUSES_A_CONTROL = re.compile(r"[|;&<>`]|\$\(")


class Verdict:
    """What the check decided about one command and its result."""

    def __init__(self, applicable, empty_kind=None, signals=None,
                 instructions=None, control=None, reason=None,
                 corroboration=None):
        self.applicable = applicable
        self.empty_kind = empty_kind
        self.signals = signals or []
        self.instructions = instructions or []
        self.control = control
        self.reason = reason
        self.corroboration = corroboration or []

    @property
    def fires(self):
        return bool(self.signals)

    def as_dict(self):
        return {
            "applicable": self.applicable,
            "empty_kind": self.empty_kind,
            "signals": list(self.signals),
            "instructions": list(self.instructions),
            "control": self.control,
            "reason": self.reason,
            "corroboration": list(self.corroboration),
        }


# ---------------------------------------------------------------- the shell

def split_on_top_level(text, separators):
    """Split text on those separators, ignoring ones inside quotes.

    Heredoc bodies and `$(...)` are not parsed: a command built around them is
    not a bare search, and every signal that matters for one is read off the
    result rather than the text.
    """
    parts = []
    current = []
    quote = None
    index = 0
    while index < len(text):
        character = text[index]
        if quote:
            current.append(character)
            if character == "\\" and quote == '"' and index + 1 < len(text):
                index += 1
                current.append(text[index])
            elif character == quote:
                quote = None
            index += 1
            continue
        if character in "'\"":
            quote = character
            current.append(character)
            index += 1
            continue
        matched = None
        for separator in separators:
            if text.startswith(separator, index):
                matched = separator
                break
        if matched:
            parts.append("".join(current))
            current = []
            index += len(matched)
            continue
        current.append(character)
        index += 1
    parts.append("".join(current))
    return parts


REMOTE_COMMAND = re.compile(r"""(?:^|\s)(?:'([^']*)'|"((?:[^"\\]|\\.)*)")""")


def remote_command_of(stage):
    """The command an `ssh host '...'` stage runs on the other machine.

    Half this fleet's searches run over ssh, and a search that could not have
    found anything is no better for being remote: failure 3 was exactly this
    shape. The remote command is the longest quoted argument.
    """
    if stage_program(stage) != "ssh":
        return None
    quoted = [group for match in REMOTE_COMMAND.finditer(stage)
              for group in match.groups() if group]
    if not quoted:
        return None
    return max(quoted, key=len)


def pipelines_of(command, _depth=0):
    """Every pipeline in the command, as Pipeline records, in order.

    A pipeline run on another machine through ssh is returned too, carrying the
    ssh stage that launched it, so a remote search is judged by the whole
    command: the remote pipeline's own stages and the local redirections and
    stages that surround them.
    """
    segments = split_on_top_level(command, ["&&", "||", ";", "\n"])
    pipelines = []
    for segment in segments:
        if not segment.strip():
            continue
        stages = [stage.strip() for stage in split_on_top_level(segment, ["|"])
                  if stage.strip()]
        if not stages:
            continue
        pipelines.append({"stages": stages, "carrier": None,
                          "carrier_stages": None, "carrier_index": None})
        if _depth:
            continue
        for index, stage in enumerate(stages):
            remote = remote_command_of(stage)
            if not remote:
                continue
            for inner in pipelines_of(remote, _depth=1):
                pipelines.append({"stages": inner["stages"], "carrier": stage,
                                  "carrier_stages": stages,
                                  "carrier_index": index})
    return pipelines


def stage_program(stage):
    """The program a stage runs, with leading env assignments and `sudo` skipped."""
    tokens = stage.split()
    for token in tokens:
        if "=" in token and not token.startswith("-") and "/" not in token.split("=")[0]:
            continue
        if token in ("sudo", "command", "env", "nohup", "exec", "time", "then",
                     "do", "!", "{", "("):
            continue
        return token.lstrip("(").rstrip(")")
    return ""


def search_stages_of(command, pipelines=None):
    """(pipeline index, stage index, stage text, program) for every search stage."""
    if pipelines is None:
        pipelines = pipelines_of(command)
    found = []
    for pipeline_index, pipeline in enumerate(pipelines):
        for stage_index, stage in enumerate(pipeline["stages"]):
            program = stage_program(stage)
            base = os.path.basename(program)
            if base in SEARCH_PROGRAMS:
                found.append((pipeline_index, stage_index, stage, base))
            elif base == "git" and re.search(
                    r"\bgit\s+(?:-[^\s]+\s+)*(?:grep\b|log\b[^|]*(?:--grep|-S|-G)\b)",
                    stage):
                found.append((pipeline_index, stage_index, stage, "git"))
    return found


def runs_on_another_machine(command):
    """Whether the command hands the work to ssh, so this machine's PATH says nothing."""
    return bool(re.search(r"(?:^|[\s;&|(])ssh\s", command))


# ------------------------------------------------------------- the emptiness

def empty_shape_of(stdout):
    """How the result is empty, or None when it is not.

    Three shapes, because a search reports absence in three ways:
      no-output          nothing on stdout at all
      zero-count         a bare 0, from `grep -c` over one input
      zero-count-lines   `path:0` lines from `grep -c` over several inputs, at
                         least one of them zero. This is the shape that hid
                         failure 1: the whole result is not empty, one input's
                         share of it is.
    """
    text = (stdout or "").strip()
    if not text:
        return "no-output"
    if text == "0":
        return "zero-count"
    lines = [line for line in text.splitlines() if line.strip()]
    matches = [COUNT_LINE.match(line) for line in lines]
    if matches and all(matches) and any(int(m.group("count")) == 0 for m in matches):
        return "zero-count-lines"
    return None


def zero_counted_inputs(stdout):
    """The paths a `path:0` result counted as empty."""
    paths = []
    for line in (stdout or "").splitlines():
        match = COUNT_LINE.match(line.strip())
        if match and int(match.group("count")) == 0:
            paths.append(match.group("path"))
    return paths


# ---------------------------------------------------------- the control run

def weaken_pattern(pattern):
    """Weaker forms of a search pattern, strongest first, each with its name.

    A weakening keeps what the search was looking for and drops what pinned it
    to one shape. Each is tied to a failure this program was built against.
    """
    weakenings = []
    stripped = pattern
    if "/" in stripped and not stripped.endswith("/"):
        # Failure 4: a reference composed at run time holds no folder.
        last_segment = stripped.rsplit("/", 1)[1]
        if last_segment and last_segment != stripped:
            weakenings.append(("last path segment", last_segment))
    unanchored = stripped
    if unanchored.startswith("^"):
        unanchored = unanchored[1:]
    if unanchored.endswith("$") and not unanchored.endswith("\\$"):
        unanchored = unanchored[:-1]
    if unanchored != stripped and unanchored:
        weakenings.append(("unanchored", unanchored))
    # Failure 1: a literal head pins the shape around the thing being counted.
    element = REGEX_ELEMENT.search(unanchored)
    if element and element.start() > 0:
        tail = unanchored[element.start():]
        if tail and tail != unanchored:
            weakenings.append(("literal head dropped", tail))
    return weakenings


def search_pattern_and_rest(stage):
    """(pattern, tokens) for a bare search stage, or (None, None).

    Only a stage this program can take apart with certainty returns a pattern:
    the first non-flag token after the program, with `-e PATTERN` honoured.
    """
    try:
        import shlex
        tokens = shlex.split(stage)
    except ValueError:
        return None, None
    if not tokens:
        return None, None
    start = 1
    if os.path.basename(tokens[0]) == "git":
        if len(tokens) < 2 or tokens[1] != "grep":
            return None, None
        start = 2
    elif os.path.basename(tokens[0]) not in SEARCH_PROGRAMS:
        return None, None
    index = start
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            index += 1
            break
        if token in ("-e", "--regexp", "--include", "--exclude", "-f", "--file",
                     "--glob", "-g", "-m", "--max-count", "-A", "-B", "-C",
                     "--type", "-t"):
            if token in ("-e", "--regexp") and index + 1 < len(tokens):
                return tokens[index + 1], tokens
            index += 2
            continue
        if token.startswith("-") and token != "-":
            index += 1
            continue
        return token, tokens
    return None, None


def run_control(stage, pattern, corpus_root, zero_inputs):
    """Run weakened copies of a bare search and report the first that matches.

    Refuses anything but a bare read-only search: a stage carrying a pipe, a
    redirect, `;`, `&&`, backticks or `$(` is never run.
    """
    if SHELL_PUNCTUATION_THAT_REFUSES_A_CONTROL.search(stage):
        return None
    try:
        import shlex
        tokens = shlex.split(stage)
    except ValueError:
        return None
    if not tokens or pattern not in tokens:
        return None
    program = os.path.basename(tokens[0])
    if program not in SEARCH_PROGRAMS and not (
            program == "git" and len(tokens) > 1 and tokens[1] == "grep"):
        return None
    for name, weaker in weaken_pattern(pattern):
        control_tokens = []
        for token in tokens:
            if token == pattern:
                control_tokens.append(weaker)
            elif any(character in token for character in "*?["):
                # The shell expanded this before the original ran; expand it
                # the same way so the control reads the same corpus.
                expanded = sorted(str(match) for match in
                                  pathlib.Path(corpus_root).glob(token))
                control_tokens.extend(
                    [os.path.relpath(match, corpus_root) for match in expanded]
                    or [token])
            else:
                control_tokens.append(token)
        try:
            finished = subprocess.run(
                control_tokens, cwd=corpus_root, capture_output=True, text=True,
                timeout=60)
        except (OSError, subprocess.SubprocessError):
            continue
        control_shape = empty_shape_of(finished.stdout)
        if control_shape is None:
            return {
                "weakening": name,
                "pattern": weaker,
                "command": " ".join(control_tokens),
                "matched": finished.stdout.strip().splitlines()[:5],
            }
        if control_shape == "zero-count-lines" and zero_inputs:
            control_zero = set(zero_counted_inputs(finished.stdout))
            recovered = [path for path in zero_inputs if path not in control_zero]
            if recovered:
                return {
                    "weakening": name,
                    "pattern": weaker,
                    "command": " ".join(control_tokens),
                    "matched": [f"{path}: counted 0 by the original, matched by "
                                f"the weakened search" for path in recovered[:5]],
                }
    return None


# ------------------------------------------------------------------ the check

def meaningful_stderr(stderr):
    """What the command itself wrote to stderr, the harness's own notes removed."""
    lines = [line for line in (stderr or "").splitlines()
             if line.strip() and not HARNESS_NOTE_ON_STDERR.match(line)]
    return "\n".join(lines)


def judge_command_result(command, exit_code=None, stdout="", stderr="",
                         ran_on_this_machine=True, control_corpus_root=None,
                         stderr_was_captured=True):
    """Whether this empty result is evidence of absence, and why not.

    stderr_was_captured says whether the caller has the search's stderr as its
    own stream. Where it does, and that stream is empty, the search printed no
    error and the empty stdout is a clean no-match: a swallowed exit status
    then adds nothing, and is reported as corroboration rather than fired on.
    Where the two streams were merged before the caller saw them -- a non-zero
    result in a session transcript, or `2>&1` in the command -- an empty stdout
    already proves an empty stderr, so the same holds.
    """
    pipelines = pipelines_of(command)
    searches = search_stages_of(command, pipelines)
    if not searches:
        return Verdict(False, reason="no search stage in the command")

    streams_were_merged = not stderr_was_captured and bool(exit_code)
    if streams_were_merged:
        results_text, merged_diagnostics = split_diagnostics(stdout)
    else:
        results_text, merged_diagnostics = stdout, ""
    empty_kind = empty_shape_of(results_text)
    if empty_kind is None:
        return Verdict(False, reason="the result is not empty")

    signals = []
    instructions = []
    combined_output = f"{stdout or ''}\n{stderr or ''}"

    for pipeline_index, stage_index, stage, program in searches:
        pipeline = pipelines[pipeline_index]
        stages = pipeline["stages"]
        carrier = pipeline["carrier"]

        if STDERR_DISCARDED.search(stage) or (
                carrier and STDERR_DISCARDED.search(carrier)):
            signals.append("stderr-discarded-by-the-search-stage")
            instructions.append(
                "Re-run without `2>/dev/null` before reporting absence: the "
                "search's stderr was discarded, so an error and a clean "
                "no-match printed the same nothing.")

        for earlier in stages[:stage_index]:
            if TRUNCATING_STAGE.match(earlier):
                signals.append("truncating-stage-upstream-of-the-search")
                instructions.append(
                    f"Search the whole input before reporting absence: "
                    f"`{earlier.strip()}` cut the input down ahead of the "
                    f"search, so the search read a truncation.")
                break

        later_stages = list(stages[stage_index + 1:])
        if carrier is not None and not later_stages:
            # The remote search is the last thing ssh ran, so ssh's own status
            # is the one the local pipeline goes on to swallow.
            later_stages = list(
                pipeline["carrier_stages"][pipeline["carrier_index"] + 1:])
        swallowed = bool(later_stages)
        if not swallowed:
            tail = command[command.find(stage) + len(stage):]
            if re.match(r"\s*(?:;|&&)\s*(?:echo|true|:)\b", tail) or \
                    re.match(r"\s*\|\|\s*(?:true|:|echo)\b", tail):
                swallowed = True
        if swallowed and "pipefail" not in command and "PIPESTATUS" not in command:
            signals.append("search-exit-status-discarded-by-a-later-stage")
            instructions.append(
                "Read the search's own exit status with `${PIPESTATUS[0]}` or "
                "`set -o pipefail`, then re-run: a later stage replaced it, and "
                "grep's 1 for no match and 2 for an error are now both 0.")

    if exit_code is not None and exit_code in ERROR_EXIT_STATUSES:
        signals.append("exit-status-reports-an-error-not-an-absence")
        instructions.append(
            f"Fix what exit status {exit_code} reports and re-run before "
            f"reporting absence: that status means the search failed, not that "
            f"it found nothing.")
    if COMMAND_NOT_FOUND.search(combined_output):
        signals.append("search-program-missing-on-this-machine")
        instructions.append(
            "Install the program the output says was not found, then re-run: a "
            "search whose program is missing prints the same nothing as a "
            "search that found nothing.")
    own_stderr = meaningful_stderr(stderr) or merged_diagnostics
    if (exit_code == 0 or exit_code is None) and own_stderr and \
            not (stdout or "").strip():
        signals.append("stderr-written-while-stdout-was-empty")
        instructions.append(
            "Read stderr before reporting absence: this search wrote to stderr "
            "and nothing to stdout, which is what an error looks like.")

    control = None
    if control_corpus_root is not None:
        for pipeline_index, _, stage, _ in searches:
            if pipelines[pipeline_index]["carrier"] is not None:
                # It ran on another machine; this one's files are not its corpus.
                continue
            pattern, _tokens = search_pattern_and_rest(stage)
            if not pattern:
                continue
            control = run_control(stage, pattern, control_corpus_root,
                                  zero_counted_inputs(stdout))
            if control:
                signals.append("weakened-pattern-control-run-found-matches")
                instructions.append(
                    f"Search for `{control['pattern']}` and read what it "
                    f"returns before reporting absence: the same search "
                    f"weakened to that pattern matched where this one did not.")
                break

    ordered = []
    for signal in signals:
        if signal not in ordered:
            ordered.append(signal)
    seen_instructions = []
    for instruction in instructions:
        if instruction not in seen_instructions:
            seen_instructions.append(instruction)

    stderr_observable = (stderr_was_captured or "2>&1" in command
                         or streams_were_merged)
    if ordered == [CORROBORATING_ONLY] and stderr_observable and not own_stderr:
        return Verdict(True, empty_kind=empty_kind, signals=[],
                       corroboration=ordered,
                       reason="the search's exit status was swallowed, but its "
                              "stderr was empty, so it did not error")
    return Verdict(True, empty_kind=empty_kind, signals=ordered,
                   instructions=seen_instructions, control=control)


# ------------------------------------------------------------- the transcripts

EXIT_CODE_IN_RESULT = re.compile(r"^Error: Exit code (\d+)\n?")
NOT_AN_EXECUTION = (
    "Error: Permission", "Error: Blocked:", "User rejected tool use",
    "InputValidationError:", "[Request interrupted", "Error: This session is",
    "Error: claude-",
)


def bash_pairs_in_transcript(path):
    """Every (command, exit_code, stdout, stderr) the transcript recorded for Bash.

    A session transcript is JSONL, one object per line. A Bash call is a
    tool_use block named Bash in an assistant message; its result is the
    tool_result block carrying the same id, and the sibling `toolUseResult`
    holds what ran. That field has two shapes, and both are parsed here:
      a dict, for an exit-0 run, with stdout and stderr kept apart;
      a string opening `Error: Exit code N`, for a non-zero run, with the two
      streams already merged -- which is why stderr-written-while-stdout-was-empty
      is computable only on the first shape.
    Anything else in that field is the harness refusing, blocking or
    interrupting rather than a command running, and is skipped, as are
    background and timed-out runs, whose emptiness is not a search result.
    """
    commands = {}
    try:
        handle = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            content = (record.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and block.get("name") == "Bash":
                    commands[block.get("id")] = (block.get("input") or {}).get(
                        "command", "")
                elif block.get("type") == "tool_result" and \
                        block.get("tool_use_id") in commands:
                    command = commands.pop(block["tool_use_id"])
                    result = record.get("toolUseResult")
                    if isinstance(result, dict):
                        if result.get("backgroundTaskId") or \
                                result.get("interrupted") or \
                                result.get("timedOutAfterMs"):
                            continue
                        yield (command, 0, result.get("stdout") or "",
                               result.get("stderr") or "")
                    elif isinstance(result, str):
                        if result.startswith(NOT_AN_EXECUTION):
                            continue
                        match = EXIT_CODE_IN_RESULT.match(result)
                        if not match:
                            continue
                        yield (command, int(match.group(1)),
                               result[match.end():], "")


def transcripts_under(directory):
    root = pathlib.Path(directory)
    if not root.is_dir():
        return []
    return sorted(root.glob("*/*.jsonl")) + sorted(root.glob("*.jsonl"))


def measure_transcripts(directories, limit=None, top=10, out=sys.stdout):
    """Run the check over recorded pairs and print the funnel and the tally."""
    total = 0
    search_shaped = 0
    empty = 0
    fired = 0
    by_signal = {}
    by_signal_alone = {}
    by_command = {}
    by_empty_kind = {}
    examples = {}
    for directory in directories:
        for transcript in transcripts_under(directory):
            for command, exit_code, stdout, stderr in bash_pairs_in_transcript(
                    transcript):
                total += 1
                if limit is not None and total > limit:
                    break
                if not search_stages_of(command):
                    continue
                search_shaped += 1
                if empty_shape_of(stdout) is None:
                    continue
                empty += 1
                verdict = judge_command_result(
                    command, exit_code=exit_code, stdout=stdout, stderr=stderr,
                    ran_on_this_machine=False, control_corpus_root=None,
                    stderr_was_captured=(exit_code == 0))
                if not verdict.fires:
                    continue
                fired += 1
                by_empty_kind[verdict.empty_kind] = by_empty_kind.get(
                    verdict.empty_kind, 0) + 1
                for signal in verdict.signals:
                    by_signal[signal] = by_signal.get(signal, 0) + 1
                    examples.setdefault(signal, []).append(command[:200])
                if len(verdict.signals) == 1:
                    only = verdict.signals[0]
                    by_signal_alone[only] = by_signal_alone.get(only, 0) + 1
                head = " ".join(command.split())[:80]
                by_command[head] = by_command.get(head, 0) + 1

    print(f"{PROGRAM}: measurement over recorded Bash pairs", file=out)
    print(f"  transcript directories : {len(directories)}", file=out)
    print(f"  pairs replayed         : {total}", file=out)
    print(f"  with a search stage    : {search_shaped}", file=out)
    print(f"  and an empty result    : {empty}", file=out)
    print(f"  the check fired on     : {fired}", file=out)
    if empty:
        print(f"  firing rate over empty search results: "
              f"{100.0 * fired / empty:.1f}%", file=out)
    print("  empty shapes that fired:", file=out)
    for kind, count in sorted(by_empty_kind.items(), key=lambda kv: -kv[1]):
        print(f"    {count:6d}  {kind}", file=out)
    print("  signals (a pair can raise several):", file=out)
    for signal, count in sorted(by_signal.items(), key=lambda kv: -kv[1]):
        alone = by_signal_alone.get(signal, 0)
        print(f"    {count:6d}  ({alone} alone)  {signal}", file=out)
    print(f"  the {top} commands that fire most often:", file=out)
    for head, count in sorted(by_command.items(), key=lambda kv: -kv[1])[:top]:
        print(f"    {count:6d}  {head}", file=out)
    return {
        "pairs": total, "search_shaped": search_shaped, "empty": empty,
        "fired": fired, "by_signal": by_signal, "by_signal_alone": by_signal_alone,
        "by_command": by_command, "examples": examples,
        "by_empty_kind": by_empty_kind,
    }


# ---------------------------------------------------------------- the fixtures

def default_fixtures_directory():
    return pathlib.Path(__file__).resolve().with_name(FIXTURES_DIRECTORY_NAME)


def load_fixtures(directory):
    fixtures = []
    for path in sorted(pathlib.Path(directory).glob("*.json")):
        with open(path, encoding="utf-8") as handle:
            fixture = json.load(handle)
        fixture["fixture_path"] = str(path)
        fixtures.append(fixture)
    return fixtures


def replay_fixtures(directory, run_control=False, checkout_root=None, out=sys.stdout):
    """Judge every fixture and report whether the check fired on each."""
    fixtures = load_fixtures(directory)
    if not fixtures:
        print(f"{PROGRAM}: no fixtures in {directory}", file=out)
        return [], False
    if checkout_root is None:
        checkout_root = pathlib.Path(__file__).resolve().parent.parent
    results = []
    every_one_fired = True
    for fixture in fixtures:
        corpus = None
        if run_control and fixture.get("control_corpus_root"):
            corpus = str(pathlib.Path(checkout_root) /
                         fixture["control_corpus_root"])
        verdict = judge_command_result(
            fixture["command"],
            exit_code=fixture.get("exit_code"),
            stdout=fixture.get("stdout", ""),
            stderr=fixture.get("stderr", ""),
            ran_on_this_machine=fixture.get("ran_on_this_machine", True),
            control_corpus_root=corpus)
        results.append((fixture, verdict))
        fired = verdict.fires
        if fixture.get("must_fire", True) and not fired:
            every_one_fired = False
        print(f"{'FIRED  ' if fired else 'SILENT '} {fixture['case']}", file=out)
        print(f"    command: {' '.join(fixture['command'].split())[:150]}", file=out)
        print(f"    result : exit={fixture.get('exit_code')} "
              f"stdout={_short(fixture.get('stdout', ''))} "
              f"stderr={_short(fixture.get('stderr', ''))}", file=out)
        print(f"    signals: {', '.join(verdict.signals) or '(none)'}", file=out)
        for instruction in verdict.instructions:
            print(f"      > {instruction}", file=out)
        if verdict.control:
            print(f"    control: {verdict.control['command']}", file=out)
            for line in verdict.control["matched"]:
                print(f"      + {line}", file=out)
        print("", file=out)
    print(f"{PROGRAM}: {sum(1 for _, v in results if v.fires)} of {len(results)} "
          f"fixtures fired", file=out)
    return results, every_one_fired


def _short(text, width=60):
    one_line = " ".join((text or "").split())
    if len(one_line) <= width:
        return repr(one_line)
    return repr(one_line[:width] + "...")


# --------------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Decide whether a search's empty result is evidence of absence.")
    parser.add_argument("--command")
    parser.add_argument("--exit-code", type=int)
    parser.add_argument("--stdout-file")
    parser.add_argument("--stderr-file")
    parser.add_argument("--stderr-not-captured", action="store_true",
                        help="stderr was not kept as its own stream, so an "
                             "empty one is no proof the search did not error")
    parser.add_argument("--ran-elsewhere", action="store_true",
                        help="the command ran on another machine, so this "
                             "machine's PATH says nothing about it")
    parser.add_argument("--run-control", action="store_true")
    parser.add_argument("--control-corpus-root")
    parser.add_argument("--replay-fixtures", nargs="?", const="",
                        metavar="DIR")
    parser.add_argument("--transcripts", action="append", default=[],
                        metavar="DIR")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args(argv)

    modes = [bool(arguments.command), arguments.replay_fixtures is not None,
             bool(arguments.transcripts)]
    if sum(modes) != 1:
        print(f"{PROGRAM}: give exactly one of --command, --replay-fixtures, "
              f"--transcripts", file=sys.stderr)
        return EXIT_BAD_INVOCATION

    if arguments.transcripts:
        measure_transcripts(arguments.transcripts, limit=arguments.limit,
                            top=arguments.top)
        return EXIT_QUIET

    if arguments.replay_fixtures is not None:
        directory = arguments.replay_fixtures or default_fixtures_directory()
        if not pathlib.Path(directory).is_dir():
            print(f"{PROGRAM}: {directory} is not a directory", file=sys.stderr)
            return EXIT_BAD_INVOCATION
        _results, every_one_fired = replay_fixtures(
            directory, run_control=arguments.run_control,
            checkout_root=arguments.control_corpus_root)
        return EXIT_QUIET if every_one_fired else EXIT_FIRED

    stdout = _read_or_empty(arguments.stdout_file)
    stderr = _read_or_empty(arguments.stderr_file)
    corpus = None
    if arguments.run_control:
        corpus = arguments.control_corpus_root or os.getcwd()
    verdict = judge_command_result(
        arguments.command, exit_code=arguments.exit_code, stdout=stdout,
        stderr=stderr, ran_on_this_machine=not arguments.ran_elsewhere,
        control_corpus_root=corpus,
        stderr_was_captured=not arguments.stderr_not_captured)
    if arguments.json:
        print(json.dumps(verdict.as_dict(), indent=2))
    elif verdict.fires:
        print(f"{PROGRAM}: this empty result is not evidence of absence.")
        for instruction in verdict.instructions:
            print(instruction)
    else:
        print(f"{PROGRAM}: nothing to report "
              f"({verdict.reason or 'no signal fired'}).")
    return EXIT_FIRED if verdict.fires else EXIT_QUIET


def _read_or_empty(path):
    if not path:
        return ""
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


if __name__ == "__main__":
    sys.exit(main())
