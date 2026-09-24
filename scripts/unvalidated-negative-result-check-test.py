#!/usr/bin/env python3
"""Tests for unvalidated-negative-result-check.py.

Every signal is tested as a pair, the positive first: the command with the
fault fires, and the same command with the fault removed is silent. A check
that cannot be made to fire on a case known to be wrong is worth nothing, and
a check that fires on everything is worth less; both halves are the test.

The four fixtures are replayed here too, controls and all, because the
fixtures are the reason this program exists and a change that stops one of
them firing is the regression that matters.

Every corpus and transcript the suite makes lives under one scratch directory
of its own, removed when the suite exits, and the measurement case reads only
that directory: reading the system temp directory would count other programs'
.jsonl files.

Run: python3 scripts/unvalidated-negative-result-check-test.py
"""

import atexit
import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

CHECK_SCRIPT = pathlib.Path(__file__).resolve().with_name(
    "unvalidated-negative-result-check.py")
CHECKOUT_ROOT = CHECK_SCRIPT.parent.parent

SUITE_SCRATCH = pathlib.Path(tempfile.mkdtemp(
    prefix="unvalidated-negative-result-check-test-"))
atexit.register(shutil.rmtree, SUITE_SCRATCH, ignore_errors=True)
TRANSCRIPTS_ROOT = SUITE_SCRATCH / "transcripts"

_spec = importlib.util.spec_from_file_location(
    "unvalidated_negative_result_check", CHECK_SCRIPT)
check_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_module)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
        return
    failures.append(case_name)
    print(f"FAIL  {case_name}")
    if detail:
        print(f"      {detail}")


def judge(command, **keywords):
    return check_module.judge_command_result(command, **keywords)


# ---------------------------------------------------------------- the gate

check("a search whose result is empty is judged",
      judge("grep -n needle haystack.txt", exit_code=1, stdout="").applicable)
check("a search that found something is not judged",
      not judge("grep -n needle haystack.txt", exit_code=0,
                stdout="4:needle\n").applicable)
check("a command with no search stage is not judged",
      not judge("cp a b", exit_code=0, stdout="", stderr="cp: no such file"
                ).applicable,
      "without this gate every ordinary command with a quiet stdout fires")
check("git grep counts as a search stage",
      judge("git grep -n needle main", exit_code=1, stdout="").applicable)
check("git log --grep counts as a search stage",
      judge("git log --grep=needle --oneline", exit_code=0, stdout="").applicable)
check("git log -S with its pattern attached counts as a search stage",
      judge("git log -Sneedle --oneline", exit_code=0, stdout="").applicable
      and judge("git log -Gneedle --oneline", exit_code=0, stdout="").applicable,
      "-Sneedle is how the pickaxe is usually written; no word boundary "
      "follows the S")

check("a bare 0 is an empty result",
      check_module.empty_shape_of("0\n") == "zero-count")
check("count lines with a zero among them are an empty result",
      check_module.empty_shape_of("a.md:0\nb.md:12\n") == "zero-count-lines")
check("count lines with no zero are not an empty result",
      check_module.empty_shape_of("a.md:3\nb.md:12\n") is None)
check("the paths a count result called empty are read back",
      check_module.zero_counted_inputs("a.md:0\nb.md:12\nc.md:0\n")
      == ["a.md", "c.md"])


# ------------------------------------------------- truncation, failure 2

truncated = judge("sed -n '14p' CLAUDE.md | cut -c1-220 | grep -n 'phrase'",
                  exit_code=1, stdout="")
check("a cut -c stage ahead of the search fires",
      "truncating-stage-upstream-of-the-search" in truncated.signals,
      str(truncated.signals))
check("the same search with the cut removed is silent",
      not judge("sed -n '14p' CLAUDE.md | grep -n 'phrase'", exit_code=1,
                stdout="").fires)
check("a truncating stage after the search does not fire",
      "truncating-stage-upstream-of-the-search" not in
      judge("grep -n 'phrase' CLAUDE.md | cut -c1-220", exit_code=1,
            stdout="").signals,
      "it truncates the answer, not the question")
check("head -c ahead of the search fires",
      "truncating-stage-upstream-of-the-search" in
      judge("cat big.md | head -c 500 | grep needle", exit_code=1,
            stdout="").signals)
check("tail -n ahead of the search fires, as head -n does",
      "truncating-stage-upstream-of-the-search" in
      judge("cat big.md | tail -n 50 | grep needle", exit_code=1,
            stdout="").signals)
check("tail -n after the search does not fire",
      "truncating-stage-upstream-of-the-search" not in
      judge("grep needle big.md | tail -n 5", exit_code=1, stdout="").signals)
check("cut -f, which keeps whole fields, does not fire",
      "truncating-stage-upstream-of-the-search" not in
      judge("cat rows.tsv | cut -f2 | grep needle", exit_code=1,
            stdout="").signals)


# ------------------------------------------ discarded stderr, failure 3

discarded = judge("grep -rn needle docs/ 2>/dev/null", exit_code=1, stdout="")
check("a search that discards its stderr fires",
      "stderr-discarded-by-the-search-stage" in discarded.signals,
      str(discarded.signals))
check("the same search keeping its stderr is silent",
      not judge("grep -rn needle docs/", exit_code=1, stdout="").fires)
check("a search FOR the text 2>/dev/null is not read as discarding stderr",
      not judge("grep -n '2>/dev/null' notes.md", exit_code=1,
                stdout="").fires,
      "a quoted pattern is the thing searched for, not a redirect")

remote = judge("ssh nedlern@ned-box 'rg -n needle ~/agents' 2>/dev/null | head -5",
               exit_code=0, stdout="")
check("a search run over ssh is judged through the ssh stage",
      "stderr-discarded-by-the-search-stage" in remote.signals,
      str(remote.signals))
check("the same remote search keeping its stderr is silent",
      not judge("ssh nedlern@ned-box 'rg -n needle ~/agents'", exit_code=0,
                stdout="").fires)
check("the remote command inside ssh is found",
      check_module.remote_command_of(
          "ssh nedlern@ned-box 'rg -n needle ~/agents' 2>/dev/null")
      == "rg -n needle ~/agents")


# ----------------------------------------------- a missing search program

not_found = judge("rg -n needle .", exit_code=127,
                  stdout="bash: line 1: rg: command not found\n",
                  stderr_was_captured=False)
check("a merged result saying the program was not found fires",
      "search-program-missing-on-this-machine" in not_found.signals,
      "a transcript merges the streams for a non-zero command, so the "
      "not-found line arrives on stdout and the gate must see past it")
check("a merged result holding real matches is silent",
      not judge("rg -n needle .", exit_code=1,
                stdout="notes.md:4:needle\n",
                stderr_was_captured=False).fires)
check("zsh's form of the not-found line fires too",
      "search-program-missing-on-this-machine" in
      judge("rg -n needle .", exit_code=127,
            stdout="zsh:1: command not found: rg\n",
            stderr_was_captured=False).signals)
missing_path = judge("grep -rn needle missing/", exit_code=2, stdout="",
                     stderr="grep: missing/: No such file or directory\n")
check("a missing path is reported as a failed search, not a missing program",
      "search-program-missing-on-this-machine" not in missing_path.signals
      and "exit-status-reports-an-error-not-an-absence" in missing_path.signals,
      f"{missing_path.signals}: grep is installed; telling the agent to "
      f"install it is a wrong instruction")
check("a not-found line naming a program outside the search's pipeline is "
      "silent",
      not judge("grep -n needle notes.md; frobnicate", exit_code=127,
                stdout="bash: line 1: frobnicate: command not found\n",
                stderr_was_captured=False).fires)
check("a program off PATH but present as a shell function does not fire",
      not judge("rg -n needle .", exit_code=1, stdout="").fires,
      "measured 2026-09-23: Claude Code installs `rg` as a shell function on "
      "the user's Mac, so shutil.which('rg') is None while rg searches "
      "perfectly; PATH is not evidence of absence and is not consulted")


# --------------------------------------------------------- exit statuses

check("grep's 2, which means it errored, fires",
      "exit-status-reports-an-error-not-an-absence" in
      judge("grep -rn needle missing-directory/", exit_code=2,
            stdout="").signals)
check("grep's 1, which means no match, is silent",
      not judge("grep -rn needle docs/", exit_code=1, stdout="").fires,
      "1 is a clean no-match and must not fire, or every search fires")
check("ssh's 255, which means the connection failed, fires",
      "exit-status-reports-an-error-not-an-absence" in
      judge("ssh nedlern@ned-box 'grep -rn needle agents'", exit_code=255,
            stdout="").signals)
check("a later command's error status is not blamed on the search",
      not judge("grep -n needle notes.md; ls missing", exit_code=2,
                stdout="ls: cannot access 'missing': No such file or "
                       "directory\n",
                stderr_was_captured=False).fires,
      "the status of `a; b` is b's, and grep ran fine and found nothing")
check("the search's own error status fires after a cd",
      "exit-status-reports-an-error-not-an-absence" in
      judge("cd docs && grep -rn needle missing/", exit_code=2,
            stdout="grep: missing/: No such file or directory\n",
            stderr_was_captured=False).signals)


# ------------------------------------------------------ stderr and stdout

check("stderr written while stdout was empty fires",
      "stderr-written-while-stdout-was-empty" in
      judge("grep -rn needle docs/", exit_code=0, stdout="",
            stderr="grep: docs/: No such file or directory\n").signals)
check("a stderr holding only the harness's cwd note is silent",
      not judge("grep -rn needle docs/", exit_code=0, stdout="",
                stderr="\nShell cwd was reset to /Users/el/agents/merge-lane"
                ).fires,
      "measured 2026-09-23: twelve empty search results had anything at all "
      "on stderr, and in all twelve it was this note, which is the harness "
      "talking rather than the search failing")


# ---------------------------- a swallowed exit status, alone, is not enough

swallowed = judge("grep -n needle notes.md | head -12", exit_code=0, stdout="",
                  stderr="", stderr_was_captured=True)
check("a swallowed exit status alone does not fire when stderr was empty",
      not swallowed.fires and
      check_module.CORROBORATING_ONLY in swallowed.corroboration,
      "measured 2026-09-23: this was the only signal on 39 of 67 firings, and "
      "in every one stderr was recorded and empty, which proves no error")
check("a swallowed exit status fires when stderr was not captured",
      check_module.CORROBORATING_ONLY in
      judge("grep -n needle notes.md | head -12", exit_code=0, stdout="",
            stderr="", stderr_was_captured=False).signals)
check("a swallowed exit status alone is silent when the streams were merged",
      not judge("grep -n needle notes.md | head", exit_code=1, stdout="",
                stderr_was_captured=False).fires,
      "a merged empty output already proves an empty stderr, so the same "
      "reasoning applies as when stderr was captured")
check("a swallowed exit status is reported beside a signal that does fire",
      check_module.CORROBORATING_ONLY in
      judge("grep -n needle notes.md 2>/dev/null | head -12", exit_code=0,
            stdout="", stderr="").signals)
check("PIPESTATUS recovers the status, so it does not fire",
      check_module.CORROBORATING_ONLY not in
      judge("grep -n needle notes.md | head -12; echo ${PIPESTATUS[0]}",
            exit_code=0, stdout="", stderr="",
            stderr_was_captured=False).signals)


# ------------------------------------------------- the weakened control run

def in_a_scratch_corpus(files):
    directory = tempfile.mkdtemp(prefix="control-corpus-", dir=SUITE_SCRATCH)
    for name, body in files.items():
        path = pathlib.Path(directory) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return directory


corpus = in_a_scratch_corpus({
    "composed.py": 'MODULE = with_name("handoff-supervisor.py")\n',
    "quiet.md": "nothing to see\n",
})
over_specific = judge('grep -rn "scripts/handoff-supervisor.py" .',
                      exit_code=1, stdout="", control_corpus_root=corpus)
check("a path pattern the corpus only holds by its last segment fires",
      "weakened-pattern-control-run-found-matches" in over_specific.signals,
      str(over_specific.signals))
check("the control names the weakened pattern it ran",
      over_specific.control and
      over_specific.control["pattern"] == "handoff-supervisor.py",
      str(over_specific.control))
check("a pattern the corpus really does not hold is silent",
      not judge('grep -rn "no-such-string-anywhere" .', exit_code=1,
                stdout="", control_corpus_root=corpus).fires)

anchored_corpus = in_a_scratch_corpus({
    "one.md": "### 1. a finding\n### 2. another\n",
    "two.md": "**1.** a finding written another way\n**2.** and another\n",
})
anchored = judge("grep -c '^### [0-9]\\+\\.' one.md two.md", exit_code=0,
                 stdout="one.md:2\ntwo.md:0\n",
                 control_corpus_root=anchored_corpus)
check("an input counted zero that the weakened pattern matches fires",
      "weakened-pattern-control-run-found-matches" in anchored.signals,
      str(anchored.signals))
check("the same count with no zero among it is not judged at all",
      not judge("grep -c '^### [0-9]\\+\\.' one.md two.md", exit_code=0,
                stdout="one.md:2\ntwo.md:3\n",
                control_corpus_root=anchored_corpus).applicable)

absolute_corpus = in_a_scratch_corpus({
    "one.md": "### 1. a finding\n",
    "two.md": "**1.** a finding written another way\n",
})
try:
    absolute_outcome = judge(
        f"grep -c '^### [0-9]\\+\\.' {absolute_corpus}/*.md", exit_code=0,
        stdout=f"{absolute_corpus}/one.md:1\n{absolute_corpus}/two.md:0\n",
        control_corpus_root=absolute_corpus).signals
except Exception as error:  # the failure this case exists to catch
    absolute_outcome = f"raised {error!r}"
check("a control over an absolute glob expands it and fires",
      "weakened-pattern-control-run-found-matches" in absolute_outcome,
      f"{absolute_outcome}: the log-store is cited by its absolute path, so "
      f"failure 1's real shape is an absolute glob")

for cleanup in ("find ./build/sub -name '*.tmp' -delete",
                "find ./build/sub -name '*.tmp' -exec rm {} +",
                "fd 'build/one' -x rm"):
    cleanup_corpus = in_a_scratch_corpus({
        "sub/one.tmp": "", "sub/two.tmp": "", "one-x": "",
    })
    judge(cleanup, exit_code=0, stdout="", control_corpus_root=cleanup_corpus)
    check(f"a control run never carries out the action of: {cleanup}",
          all((pathlib.Path(cleanup_corpus) / name).exists()
              for name in ("sub/one.tmp", "sub/two.tmp", "one-x")),
          str(sorted(str(path.relative_to(cleanup_corpus))
                     for path in pathlib.Path(cleanup_corpus).rglob("*"))))

piped_corpus = in_a_scratch_corpus({
    "notes.txt": "nothing here\n", "other.txt": "needle\n",
})
piped = judge('cat notes.txt | grep -rn "x/needle"', exit_code=1, stdout="",
              control_corpus_root=piped_corpus)
check("a search fed by a pipe is never re-run over the corpus",
      piped.control is None and
      "weakened-pattern-control-run-found-matches" not in piped.signals,
      f"{piped.control}: it read the pipe, so a re-run over the corpus "
      f"searches files the original never read")

check("the control refuses a command carrying a pipe",
      check_module.run_control("grep -rn 'a/b' . | head", "a/b", corpus, [])
      is None,
      "only a bare read-only search is ever re-run")
check("the control refuses a command carrying a redirect",
      check_module.run_control("grep -rn 'a/b' . > out.txt", "a/b", corpus, [])
      is None)
check("a path pattern weakens to its last segment",
      ("last path segment", "handoff-supervisor.py") in
      check_module.weaken_pattern("scripts/handoff-supervisor.py"))
check("an anchored pattern weakens to an unanchored one",
      ("unanchored", "needle") in check_module.weaken_pattern("^needle$"))
check("a literal head before a regex element is dropped",
      any(name == "literal head dropped"
          for name, _ in check_module.weaken_pattern("^### [0-9]\\+\\.")))


# --------------------------------------------- reading a session transcript

def transcript_holding(records, root=TRANSCRIPTS_ROOT, where="project"):
    """Write the records as one transcript under root/where; return its path."""
    directory = pathlib.Path(root) / where
    directory.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8",
        dir=directory)
    for record in records:
        handle.write(json.dumps(record) + "\n")
    handle.close()
    return handle.name


def assistant_bash(tool_id, command):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tool_id, "name": "Bash",
         "input": {"command": command}}]}}


def result_block(tool_id, tool_use_result):
    return {"type": "user", "toolUseResult": tool_use_result,
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": tool_id, "content": ""}]}}


exit_zero_shape = transcript_holding([
    assistant_bash("t1", "grep -n needle notes.md"),
    result_block("t1", {"stdout": "", "stderr": "grep: notes.md: No such file",
                        "interrupted": False, "isImage": False,
                        "noOutputExpected": False}),
])
pairs = list(check_module.bash_pairs_in_transcript(exit_zero_shape))
check("an exit-0 pair is read with its two streams apart",
      pairs == [("grep -n needle notes.md", 0, "",
                 "grep: notes.md: No such file")],
      str(pairs))

exit_nonzero_shape = transcript_holding([
    assistant_bash("t2", "grep -rn needle missing/"),
    result_block("t2", "Error: Exit code 2\ngrep: missing/: No such file"),
])
pairs = list(check_module.bash_pairs_in_transcript(exit_nonzero_shape))
check("a non-zero pair is read with its status and its merged output",
      pairs == [("grep -rn needle missing/", 2,
                 "grep: missing/: No such file", "")],
      str(pairs))

refusal_shape = transcript_holding([
    assistant_bash("t3", "grep -rn needle ."),
    result_block("t3", "Error: Permission for this action was denied"),
])
check("a refusal, which never ran, is not a pair",
      list(check_module.bash_pairs_in_transcript(refusal_shape)) == [],
      "a command that never ran has no result to trust or distrust")

background_shape = transcript_holding([
    assistant_bash("t4", "grep -rn needle ."),
    result_block("t4", {"stdout": "", "stderr": "", "backgroundTaskId": "abc",
                        "interrupted": False, "isImage": False,
                        "noOutputExpected": False}),
])
check("a backgrounded command is not a pair",
      list(check_module.bash_pairs_in_transcript(background_shape)) == [],
      "its empty stdout is the launch, not the search")

measured_root = SUITE_SCRATCH / "measured-transcripts"
transcript_holding([
    assistant_bash("m1", "rg -n needle ."),
    result_block("m1", "Error: Exit code 127\nbash: line 1: rg: command not found"),
    assistant_bash("m2", "grep -rn needle missing/"),
    result_block("m2", "Error: Exit code 2\n"
                       "grep: missing/: No such file or directory"),
], root=measured_root)
transcript_holding([
    assistant_bash("m3", "grep -n needle notes.md"),
    result_block("m3", {"stdout": "", "stderr": "", "interrupted": False,
                        "isImage": False, "noOutputExpected": False}),
], root=measured_root, where="project/session-one/subagents")


def funnel(measurement):
    return {key: measurement.get(key) for key in (
        "pairs", "from_subagents", "search_shaped", "empty", "fired")}


measurement = check_module.measure_transcripts(
    [str(measured_root)], limit=None, top=3, out=io.StringIO())
check("the measurement reads subagent transcripts",
      measurement["pairs"] == 3 and measurement.get("from_subagents") == 1,
      f"{funnel(measurement)}: review cells and reviewers are subagents, and "
      f"they run most of this fleet's searches")
check("the measurement judges a failure whose merged output is only error lines",
      measurement["empty"] == 3 and measurement["fired"] == 2,
      f"{funnel(measurement)}: a transcript merges the streams of a non-zero "
      f"command, so failure 3's shape has a stdout that is not empty")
limited = check_module.measure_transcripts(
    [str(measured_root)], limit=1, top=3, out=io.StringIO())
check("--limit stops the replay at that many pairs across transcripts",
      limited["pairs"] == 1, str(funnel(limited)))


# ------------------------------------------------------- the four fixtures

fixtures = check_module.load_fixtures(check_module.default_fixtures_directory())
check("all four recorded failures are present as fixtures",
      len(fixtures) == 4, f"{len(fixtures)} fixtures")
for fixture in fixtures:
    for field in ("case", "provenance", "command", "stdout", "must_fire"):
        check(f"the fixture {os.path.basename(fixture['fixture_path'])} "
              f"carries its {field}", field in fixture)

_results, every_one_fired = check_module.replay_fixtures(
    check_module.default_fixtures_directory(), run_control=True,
    checkout_root=CHECKOUT_ROOT, out=io.StringIO())
check("every recorded failure fires when replayed", every_one_fired,
      "; ".join(f"{fixture['case']}: {verdict.signals}"
                for fixture, verdict in _results if not verdict.fires))
for fixture, verdict in _results:
    check(f"the check hands an agent an instruction for: {fixture['case'][:60]}",
          bool(verdict.instructions), str(verdict.signals))


# ------------------------------------------------ the program at the command line

def run_program(*arguments):
    finished = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), *arguments],
        capture_output=True, text=True, cwd=str(CHECKOUT_ROOT))
    return finished.returncode, finished.stdout, finished.stderr


code, out, _err = run_program("--command", "grep -rn needle docs/ 2>/dev/null",
                              "--exit-code", "1")
check("a firing command exits 1 and prints its instructions",
      code == 1 and "2>/dev/null" in out, f"{code} {out!r}")

code, out, _err = run_program("--command", "grep -rn needle docs/",
                              "--exit-code", "1")
check("a clean command exits 0 and says nothing to report",
      code == 0 and "nothing to report" in out, f"{code} {out!r}")

code, out, _err = run_program("--replay-fixtures", "--run-control",
                              "--control-corpus-root", str(CHECKOUT_ROOT))
check("the fixture replay exits 0 while every fixture fires",
      code == 0 and "4 of 4 fixtures fired" in out, f"{code} {out[-300:]!r}")

code, _out, err = run_program("--command", "grep x", "--replay-fixtures")
check("two modes at once is a bad invocation, not a silent default",
      code == 2 and "exactly one of" in err, f"{code} {err!r}")

code, _out, err = run_program("--replay-fixtures", "/no/such/fixtures")
check("a fixtures directory that does not exist is a bad invocation",
      code == 2, f"{code} {err!r}")


# ------------------------------------------------ what a control never runs

for refused_stage in ("find . -name 'x/needle'",
                      "fd 'x/needle' -x rm",
                      "rg --pre ./decompress 'x/needle' .",
                      "ugrep --filter='*:cat' 'x/needle' .",
                      "git grep -O 'x/needle'",
                      "git grep --open-files-in-pager=vim 'x/needle'"):
    check(f"a control run is refused for: {refused_stage}",
          check_module.control_refusal(refused_stage) is not None)
check("a control run is allowed for a bare grep",
      check_module.control_refusal("grep -rn 'x/needle' .") is None)


if failures:
    print(f"\n{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("\nall cases passed")
