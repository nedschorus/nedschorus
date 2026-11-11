#!/usr/bin/env python3
"""Tests for unvalidated-negative-result-check.py.

The firings of the sorted table are replayed with the machines' answers of their day put
in: the dash-named directories, rg missing on ned-box before it was installed, and the grep
arguments the agent's grep refused. A stand-in for the agent's grep gives the refusals the
fixture records, because the test sandbox holds no claude binary; where the real one runs,
the last section checks the record against it, and prints a SKIP line where it does not.
Each of the 16 firings with a cause must name that cause; every NOISE firing, and the 5
SELF-CAUGHT firings that have none of the three causes, must stay silent.

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

CHECK_SCRIPT = pathlib.Path(__file__).resolve().with_name("unvalidated-negative-result-check.py")
FIXTURE = CHECK_SCRIPT.with_name("unvalidated-negative-result-check-fixtures") \
    / "firings-classified-by-hand-as-real-self-caught-or-noise-2026-10-01.json"

SCRATCH = pathlib.Path(tempfile.mkdtemp(prefix="unvalidated-negative-result-check-test-"))
atexit.register(shutil.rmtree, SCRATCH, ignore_errors=True)

_spec = importlib.util.spec_from_file_location("unvalidated_negative_result_check", CHECK_SCRIPT)
check_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_module)

GLOB_DASH_NAME = check_module.GLOB_DASH_NAME
PATTERN_TOO_COMPLEX = check_module.PATTERN_TOO_COMPLEX
PROGRAM_MISSING = check_module.PROGRAM_MISSING
SIGNAL_OF_SHAPE = {"S1": GLOB_DASH_NAME, "S2": PATTERN_TOO_COMPLEX, "S3": PROGRAM_MISSING}

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
        return
    failures.append(case_name)
    print(f"FAIL  {case_name}")
    if detail:
        print(f"      {detail}")


DASH_NAMED_ENTRIES = ["-Users-el-agents-merge-lane", "-Users-el-agents-reboot-test",
                      "-home-nedlern-agents-merge-lane-2"]
PLAIN_ENTRIES = ["README.md", "docs", "scripts", "a.jsonl"]

REFUSED_IN_THESE_TESTS = [["-oE", ".{0,180}(a|b).{0,180}"], ["-oE", "--", ".{0,180}(a|b).{0,180}"],
                          ["-o", "-e", ".{0,180}(a|b).{0,180}", "-E"],
                          ["-oE", "--regexp=.{0,180}(a|b).{0,180}.*"],
                          ["-oE", "-e.{0,180}(a|b).{0,180}.*"]]
firings = json.loads(FIXTURE.read_text(encoding="utf-8"))["firings"]
REFUSALS_FILE = SCRATCH / "arguments-the-agents-grep-refuses.json"
REFUSALS_FILE.write_text(json.dumps(
    REFUSED_IN_THESE_TESTS
    + [arguments for firing in firings for arguments in firing["arguments_the_agents_grep_refuses"]]))
STAND_IN_AGENTS_GREP = SCRATCH / "stand-in-agents-grep"
STAND_IN_AGENTS_GREP.write_text(
    f"#!{sys.executable}\n"
    "import json, sys\n"
    f"leading = {len(check_module.AGENTS_GREP_LEADING_OPTIONS)}\n"
    f"refused = json.load(open({str(REFUSALS_FILE)!r}))\n"
    "if sys.argv[1 + leading:-1] in refused:\n"
    "    sys.stderr.write('ugrep: error: error at position 9\\n  exceeds complexity limits\\n')\n"
    "    sys.exit(2)\n"
    "sys.exit(1)\n")
STAND_IN_AGENTS_GREP.chmod(0o755)


def machines_with_the_stand_in_agents_grep():
    """Machines answering for real, but with the stand-in as the agent's grep."""
    return check_module.Machines(environment={"CLAUDE_CODE_EXECPATH": str(STAND_IN_AGENTS_GREP)})

RIPGREP_INSTALLED_ON_NED_BOX = "2026-10-01T17:44"


class MachinesOfTheDay(check_module.Machines):
    """The answers each machine gave on the day of one firing."""

    def __init__(self, machine="mac", timestamp="2026-10-02", missing=()):
        super().__init__(runner=self.refuse_other_programs,
                         environment={"CLAUDE_CODE_EXECPATH": str(STAND_IN_AGENTS_GREP)})
        self.machine = machine
        self.timestamp = timestamp
        self.missing = set(missing)
        self.asked = []

    @staticmethod
    def refuse_other_programs(argv, **keywords):
        if argv[0] != "ugrep":
            raise AssertionError(f"the test machines ran {argv}")
        return subprocess.run(argv, **keywords)

    def on_ned_box(self, host):
        return "ned-box" in host if host else self.machine == "ned-box"

    def directory_entries(self, host, directory):
        self.asked.append(("entries", host, directory))
        if directory.endswith((".claude/projects", "transcripts/mac/projects")):
            return DASH_NAMED_ENTRIES
        return PLAIN_ENTRIES

    def program_installed(self, host, program):
        self.asked.append(("installed", host, program))
        if (host, program) in self.missing:
            return False
        return not (program == "rg" and self.on_ned_box(host)
                    and self.timestamp < RIPGREP_INSTALLED_ON_NED_BOX)


def judge(command, cwd="/work", output="", exit_code=0, machines=None):
    return check_module.judge_command_result(command, cwd, output, exit_code,
                                             machines or MachinesOfTheDay())


# --------------------------------------------- the firings of the sorted table

check("the fixture holds the 83 sorted firings", len(firings) == 83, len(firings))
verdicts = {}
for firing in firings:
    verdicts[firing["id"]] = judge(
        firing["command"], firing["cwd"], firing["output"], firing["exit_code"],
        MachinesOfTheDay(firing["machine"], firing["timestamp"]))

for firing in firings:
    verdict = verdicts[firing["id"]]
    label = f"{firing['id']} ({firing['verdict']}, {firing['shape'] or firing['noise_class'] or '-'})"
    if firing["shape"]:
        check(f"{label} fires and names its cause, {SIGNAL_OF_SHAPE[firing['shape']]}",
              set(verdict.signals) == {SIGNAL_OF_SHAPE[firing["shape"]]},
              f"signals {verdict.signals} unchecked {verdict.unchecked}")
    else:
        check(f"{label} stays silent",
              not verdict.fires and not verdict.unchecked,
              f"signals {verdict.signals} unchecked {verdict.unchecked}")

fired = [firing for firing in firings if verdicts[firing["id"]].fires]
check("16 firings in all: 4 REAL, 12 SELF-CAUGHT, 0 NOISE",
      len(fired) == 16
      and sum(firing["verdict"] == "REAL" for firing in fired) == 4
      and sum(firing["verdict"] == "SELF-CAUGHT" for firing in fired) == 12,
      [firing["id"] for firing in fired])

# The REAL firings G046 and G047 hold only because rg was missing on ned-box that day.
g046 = next(firing for firing in firings if firing["id"] == "G046")
check("G046 is silent once rg is installed on ned-box",
      not judge(g046["command"], g046["cwd"], g046["output"], 0,
                MachinesOfTheDay("mac", "2026-10-02")).fires)


# ------------------------------------------------------- near misses, cause S1

PROJECTS = "/home/nedlern/.claude/projects"
check("S1 fires on a dash-named directory's relative glob",
      judge(f"cd {PROJECTS} && grep -l x */*.jsonl").signals == [GLOB_DASH_NAME])
for near_miss in (f"cd {PROJECTS} && grep -l x -- */*.jsonl",
                  f"cd {PROJECTS} && grep -l x '*/*.jsonl'",
                  f"cd {PROJECTS} && grep -l x {PROJECTS}/*/*.jsonl",
                  f"cd {PROJECTS} && grep -l x ./*/*.jsonl",
                  "cd /work/docs && grep -l x */*.md",
                  "cd \"$DIR\" && grep -l x */*.jsonl",
                  f"cd {PROJECTS} && for f in */*.jsonl; do grep -l x \"$f\"; done"):
    check(f"S1 stays silent: {near_miss}", not judge(near_miss).fires)
check("S1 reads a cwd that is itself dash-named, with no cd",
      judge("grep -l x */*.jsonl", cwd=PROJECTS).signals == [GLOB_DASH_NAME])
check("S1 keeps a substitution's cd inside it",
      not judge(f"echo $(cd {PROJECTS}); grep -l x */*.jsonl").fires)
check("S1 reads ls feeding a search, which the leading-dash guard does not read",
      judge(f"cd {PROJECTS} && ls -d *merge-lane*/ | xargs grep -l x").signals
      == [GLOB_DASH_NAME])
remote = MachinesOfTheDay()
check("S1 reads a command ssh runs, in the directory it cds into there",
      judge("ssh nedlern@ned-box 'cd ~/.claude/projects && grep -l x */*.jsonl'",
            machines=remote).signals == [GLOB_DASH_NAME]
      and ("entries", "nedlern@ned-box", "~/.claude/projects") in remote.asked, remote.asked)
check("S1 reads ssh's destination past an option that takes a value",
      judge("ssh -p 22 nedlern@ned-box 'cd ~/.claude/projects && grep -l x */*.jsonl'",
            machines=remote).signals == [GLOB_DASH_NAME])


# ------------------------------------------------------- near misses, cause S2

check("S2 fires on a bare grep whose pattern the agent's grep refuses",
      judge("grep -oE '.{0,180}(a|b).{0,180}' notes.md").signals == [PATTERN_TOO_COMPLEX])
check("S2 fires with the refused pattern given after --",
      judge("grep -oE -- '.{0,180}(a|b).{0,180}' notes.md").signals == [PATTERN_TOO_COMPLEX])
check("S2 fires with the refused pattern given by -e",
      judge("grep -o -e '.{0,180}(a|b).{0,180}' -E notes.md").signals == [PATTERN_TOO_COMPLEX])
for near_miss in ("grep -oE '.{0,80}link-type' notes.md",
                  "xargs grep -oE '.{0,180}(a|b).{0,180}' < list",
                  "command grep -oE '.{0,180}(a|b).{0,180}' notes.md",
                  "/usr/bin/grep -oE '.{0,180}(a|b).{0,180}' notes.md",
                  "grep -zoE '.{0,180}(a|b).{0,180}' notes.md",
                  "ssh nedlern@ned-box \"grep -oE '.{0,180}(a|b).{0,180}' notes.md\""):
    check(f"S2 stays silent: {near_miss}", not judge(near_miss).fires,
          judge(near_miss).signals)
check("S2 leaves the file names out of the probe",
      check_module.agents_grep_options_and_patterns_without_file_names(check_module.Placed(
          None, "/work", ["grep", "-rn", "--include", "*.md", "-A", "2", "needle", "docs",
                          "notes.md"], 0), MachinesOfTheDay(), [])
      == ["-rn", "--include", "*.md", "-A", "2", "needle"])


def probes_of(command, cwd="/work", machines=None, unchecked=None):
    return [check_module.agents_grep_options_and_patterns_without_file_names(
                placed, machines or MachinesOfTheDay(), [] if unchecked is None else unchecked)
            for placed in check_module.split_into_simple_commands_with_the_machine_and_directory_each_runs_in(
                command, cwd)
            if placed.program == "grep"]


dash_glob_grep = f"cd {PROJECTS} && grep -l needle -r -Users-el-agents-*/ 2>/dev/null"
check("S2 leaves an unquoted glob that expanded to names beginning with - out of the probe, "
      "and keeps a quoted one",
      probes_of(dash_glob_grep + " '-x*'") == [["-l", "needle", "-r", "-x*"]],
      probes_of(dash_glob_grep + " '-x*'"))
check("S2 keeps in the probe a dash-led unquoted glob that matched no name, which grep read "
      "as an option",
      probes_of("grep -l needle -r -Users-el-agents-*/") == [["-l", "needle", "-r", "-Users-el-agents-*/"]],
      probes_of("grep -l needle -r -Users-el-agents-*/"))
check("S2 keeps in the probe an option, or an option's value, that holds an unquoted glob "
      "character",
      probes_of("grep -rn --include=*.md --include -foo* --regexp=foo.*bar -efoo.*bar docs")
      == [["-rn", "--include=*.md", "--include", "-foo*", "--regexp=foo.*bar", "-efoo.*bar"]],
      probes_of("grep -rn --include=*.md --include -foo* --regexp=foo.*bar -efoo.*bar docs"))
check("S2 keeps in the probe an unquoted pattern that does not begin with -",
      probes_of("grep -c foo.*bar notes.md") == [["-c", "foo.*bar"]],
      probes_of("grep -c foo.*bar notes.md"))
for partly_unquoted in ("grep -oE --regexp='.{0,180}(a|b).{0,180}'.* notes.md",
                        "grep -oE -e'.{0,180}(a|b).{0,180}'.* notes.md"):
    check(f"S2 fires with the refused pattern given partly unquoted through an option: "
          f"{partly_unquoted}",
          judge(partly_unquoted).signals == [PATTERN_TOO_COMPLEX], judge(partly_unquoted).signals)


class MachinesWhoseDirectoryCannotBeListed(MachinesOfTheDay):
    def directory_entries(self, host, directory):
        self.asked.append(("entries", host, directory))
        raise check_module.MachineStateQueryGotNoAnswer(f"listing {directory} failed")


unlisted = judge("grep -oE --regexp='.{0,180}(a|b).{0,180}'.* notes.md",
                 machines=MachinesWhoseDirectoryCannotBeListed())
check("a directory that cannot be listed keeps the dash-led word in the probe, and is "
      "reported once",
      unlisted.signals == [PATTERN_TOO_COMPLEX] and len(unlisted.unchecked) == 1
      and "listing /work failed" in unlisted.unchecked[0],
      f"signals {unlisted.signals} unchecked {unlisted.unchecked}")
unlisted_unchecked = []
unlisted_probes = probes_of("grep -c -x* /tmp/n*.md foo.*bar",
                            machines=MachinesWhoseDirectoryCannotBeListed(),
                            unchecked=unlisted_unchecked)
check("the probe asks whether a word expanded only for a word that begins with -",
      unlisted_probes == [["-c", "-x*", "/tmp/n*.md"]] and len(unlisted_unchecked) == 1
      and "`-x*`" in unlisted_unchecked[0],
      f"{unlisted_probes} unchecked {unlisted_unchecked}")


class MachinesWhoseGrepRejectsUnknownOptions(MachinesOfTheDay):
    """The real agent's grep reads an argument beginning with - as an option, and exits 2
    without its refusal on one it does not know."""

    @staticmethod
    def refuse_other_programs(argv, **keywords):
        if argv[0] == "ugrep" and any(argument.startswith("-U") for argument in argv[1:]):
            return subprocess.CompletedProcess(argv, 2, "", "ugrep: invalid option -U\n")
        return MachinesOfTheDay.refuse_other_programs(argv, **keywords)


dash_glob_verdict = judge(dash_glob_grep, machines=MachinesWhoseGrepRejectsUnknownOptions())
check("S1 alone speaks on a dash-led glob, with no unchecked S2 line from the probe",
      dash_glob_verdict.signals == [GLOB_DASH_NAME] and dash_glob_verdict.unchecked == [],
      f"signals {dash_glob_verdict.signals} unchecked {dash_glob_verdict.unchecked}")


# ------------------------------------------------------- near misses, cause S3

missing_fd = MachinesOfTheDay(missing={(None, "fd")})
check("S3 fires on a search program missing on this machine",
      judge("fd needle docs", machines=missing_fd).signals == [PROGRAM_MISSING])
check("S3 stays silent when the program is installed", not judge("fd needle docs").fires)
check("S3 asks once per program and machine",
      judge("rg a docs; rg b docs", machines=MachinesOfTheDay(
          missing={(None, "rg")})).signals == [PROGRAM_MISSING])


# ------------------------------------------------- what makes the check apply

check("a result that is not empty is not judged",
      not judge(f"cd {PROJECTS} && grep -l x */*.jsonl", output="a.jsonl\n").applicable)
check("a command with no search is not judged",
      not judge(f"cd {PROJECTS} && ls */*.jsonl").applicable)
check("a failed command's diagnostics alone are an empty result",
      judge(f"cd {PROJECTS} && grep -l x */*.jsonl", exit_code=2,
            output="grep: invalid option -- 'U'\n").signals == [GLOB_DASH_NAME])
check("grep -c counts that are all zero are an empty result",
      check_module.empty_shape_of("a.md:0\nb.md:0") == "zero-count-lines"
      and check_module.empty_shape_of("a.md:0\nb.md:3") is None)


# ------------------------------------------------- the questions to a machine

class Answer:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def runner_answering(*answers):
    calls = []

    def runner(argv, **keywords):
        calls.append(argv)
        answer = answers[min(len(calls), len(answers)) - 1]
        if isinstance(answer, Exception):
            raise answer
        return answer
    return runner, calls


runner, calls = runner_answering(Answer(0, "-a\nb\n"))
machines = check_module.Machines(runner=runner)
check("a remote listing is asked over ssh, its ~ left to the remote shell",
      machines.directory_entries("nedlern@ned-box", "~/x y") == ["-a", "b"]
      and calls[0][-2:] == ["nedlern@ned-box", "ls -A -- \"$HOME\"/'x y'"], calls)
machines.directory_entries("nedlern@ned-box", "~/x y")
check("an answer is kept, so the question is asked once", len(calls) == 1, calls)

for answer, expected in ((Answer(0, "/usr/bin/rg\n"), True), (Answer(1), False)):
    runner, _ = runner_answering(answer)
    check(f"command -v exiting {answer.returncode} over ssh means installed is {expected}",
          check_module.Machines(runner=runner).program_installed("h", "rg") is expected)

for what, ask_it in (
        ("a remote listing", lambda m: m.directory_entries("h", "/d")),
        ("a remote program question", lambda m: m.program_installed("h", "rg"))):
    for failure in (Answer(255, stderr="connect to host h: refused"),
                    Answer(-15, stderr="killed by a signal"),
                    subprocess.TimeoutExpired("x", 15), OSError("no such file")):
        runner, calls = runner_answering(failure)
        machines = check_module.Machines(runner=runner)
        raised = []
        for _ in range(2):
            try:
                ask_it(machines)
            except check_module.MachineStateQueryGotNoAnswer as error:
                raised.append(str(error))
        named = (f"exited {failure.returncode}" in raised[0] if isinstance(failure, Answer)
                 else raised[0].startswith("ssh could not run")) if raised else False
        check(f"{what} that fails ({type(failure).__name__} "
              f"{getattr(failure, 'returncode', '')}) raises MachineStateQueryGotNoAnswer, "
              f"once asked, saying how it failed",
              len(raised) == 2 and len(calls) == 1 and named, f"{raised} {calls}")

try:
    check_module.Machines().directory_entries(None, str(SCRATCH / "absent"))
    check("a local listing of a missing directory raises MachineStateQueryGotNoAnswer", False)
except check_module.MachineStateQueryGotNoAnswer:
    check("a local listing of a missing directory raises MachineStateQueryGotNoAnswer", True)

dash_directory = SCRATCH / "projects"
(dash_directory / "-Users-el-agents-x").mkdir(parents=True)
(dash_directory / "-Users-el-agents-x" / "a.jsonl").write_text("needle\n")
check("a local listing reads the directory",
      check_module.Machines().directory_entries(None, str(dash_directory))
      == ["-Users-el-agents-x"])
check("a local program question finds an installed program and not an absent one",
      check_module.Machines().program_installed(None, "sh")
      and not check_module.Machines().program_installed(None, "no-such-program-here"))

for answer, expected in ((Answer(0), False), (Answer(1), False),
                         (Answer(2, stderr="ugrep: error at position 9\n  exceeds complexity limits"), True)):
    runner, _ = runner_answering(answer)
    check(f"the agent's grep exiting {answer.returncode} means refuses is {expected}",
          check_module.Machines(runner=runner, environment={
              "CLAUDE_CODE_EXECPATH": str(STAND_IN_AGENTS_GREP)}).agents_grep_refuses(["x"], None)
          is expected)

for failure in (Answer(-15), Answer(2, stderr="ugrep: error: invalid option -Q"), Answer(137)):
    runner, _ = runner_answering(failure)
    unanswered = check_module.judge_command_result(
        "grep -oE '.{0,180}(a|b).{0,180}' notes.md", str(SCRATCH), "", 0,
        check_module.Machines(runner=runner,
                              environment={"CLAUDE_CODE_EXECPATH": str(STAND_IN_AGENTS_GREP)}))
    check(f"the agent's grep exiting {failure.returncode} without its refusal leaves S2 unchecked "
          f"and says how it exited",
          not unanswered.fires and len(unanswered.unchecked) == 1
          and f"exited {failure.returncode}" in unanswered.unchecked[0], unanswered.unchecked)

no_agents_grep = check_module.Machines(environment={"HOME": str(SCRATCH)})
verdict = check_module.judge_command_result(
    "grep -oE '.{0,180}(a|b).{0,180}' notes.md", str(SCRATCH), "", 0, no_agents_grep)
check("an agent's grep that cannot be found leaves S2 unchecked and says so",
      not verdict.fires and len(verdict.unchecked) == 1
      and "was not found" in verdict.unchecked[0], verdict.unchecked)
home_with_claude = SCRATCH / "home-with-claude"
(home_with_claude / ".local" / "bin").mkdir(parents=True)
(home_with_claude / ".local" / "bin" / "claude").symlink_to(STAND_IN_AGENTS_GREP)
check("the agent's grep is found through $CLAUDE_CODE_EXECPATH first",
      check_module.Machines(environment={"CLAUDE_CODE_EXECPATH": str(STAND_IN_AGENTS_GREP),
                                         "HOME": str(SCRATCH)}).agents_grep()
      == str(STAND_IN_AGENTS_GREP))
check("the agent's grep is found at ~/.local/bin/claude without $CLAUDE_CODE_EXECPATH",
      check_module.Machines(environment={"HOME": str(home_with_claude)}).agents_grep()
      == str(home_with_claude / ".local" / "bin" / "claude"))

failed_listing = check_module.judge_command_result(
    "grep -l x */*.jsonl", str(SCRATCH / "absent"), "", 0, machines_with_the_stand_in_agents_grep())
check("a listing that fails leaves S1 unchecked and says which glob",
      not failed_listing.fires and len(failed_listing.unchecked) == 1
      and "`*/*.jsonl`" in failed_listing.unchecked[0], failed_listing.unchecked)
two_globs = check_module.judge_command_result(
    "grep -l x */*.jsonl *.md", str(SCRATCH / "absent"), "", 0,
    machines_with_the_stand_in_agents_grep())
check("a listing that fails is reported once, not once per glob in the command",
      sum("to a name beginning with -" in line for line in two_globs.unchecked) == 1,
      two_globs.unchecked)


class LocalFdMissing(check_module.Machines):
    def program_installed(self, host, program):
        if host is None:
            return program != "fd"
        return super().program_installed(host, program)


runner, _ = runner_answering(Answer(255, stderr="refused"))
after_failed_ssh = check_module.judge_command_result(
    "ssh h 'rg x docs'; fd y docs", "/work", "", 0, LocalFdMissing(runner=runner))
check("a program question that fails does not stop the check asking about the next",
      after_failed_ssh.signals == [PROGRAM_MISSING] and len(after_failed_ssh.unchecked) == 1,
      f"{after_failed_ssh.signals} {after_failed_ssh.unchecked}")
runner, _ = runner_answering(Answer(255, stderr="refused"))
failed_ssh = check_module.judge_command_result(
    "ssh h 'rg x docs'", "/work", "", 0, check_module.Machines(runner=runner))
check("an ssh that fails leaves S3 unchecked and says which program",
      not failed_ssh.fires and len(failed_ssh.unchecked) == 1
      and "whether rg is installed on h" in failed_ssh.unchecked[0], failed_ssh.unchecked)


# --------------------------------------------------------------- the hook mode

def hook(payload, machines=None):
    out = io.StringIO()
    code = check_module.unvalidated_negative_result_warning_post_tool_use_hook(
        io.StringIO(payload if isinstance(payload, str) else json.dumps(payload)), out,
        machines or MachinesOfTheDay())
    return code, out.getvalue()


firing_command = f"cd {PROJECTS} && grep -l x */*.jsonl 2>/dev/null"
code, out = hook({"hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": "/work",
                  "tool_input": {"command": firing_command},
                  "tool_response": {"stdout": "", "stderr": "", "interrupted": False}})
context = json.loads(out)["hookSpecificOutput"] if out else {}
check("a PostToolUse payload that fires gives the warning as additionalContext",
      code == 0 and context.get("hookEventName") == "PostToolUse"
      and "names beginning with -" in context.get("additionalContext", ""), out)
code, out = hook({"hook_event_name": "PostToolUseFailure", "tool_name": "Bash",
                  "cwd": "/work", "tool_input": {"command": f"cd {PROJECTS} && grep -l x */*.jsonl"},
                  "error": "Exit code 2\ngrep: invalid option -- 'U'\n"})
context = json.loads(out)["hookSpecificOutput"] if out else {}
check("a PostToolUseFailure payload is read from its Exit code line",
      code == 0 and context.get("hookEventName") == "PostToolUseFailure"
      and "names beginning with -" in context.get("additionalContext", ""), out)
for case, payload in (
        ("a payload that is not JSON", "{"),
        ("a tool that is not Bash", {"tool_name": "Read", "tool_input": {}}),
        ("an interrupted command", {"tool_name": "Bash", "cwd": "/work",
                                    "tool_input": {"command": firing_command},
                                    "tool_response": {"stdout": "", "interrupted": True}}),
        ("a failure that was an abort", {"hook_event_name": "PostToolUseFailure",
                                         "tool_name": "Bash", "is_interrupt": True,
                                         "tool_input": {"command": firing_command},
                                         "error": "Exit code 1\n"}),
        ("a failure with no Exit code line", {"hook_event_name": "PostToolUseFailure",
                                              "tool_name": "Bash", "error": "timed out",
                                              "tool_input": {"command": firing_command}}),
        ("a search that found something", {"tool_name": "Bash", "cwd": "/work",
                                           "tool_input": {"command": firing_command},
                                           "tool_response": {"stdout": "a.jsonl\n"}})):
    check(f"the hook says nothing for {case}", hook(payload) == (0, ""), hook(payload))

real_simple_commands = check_module.shell_reader.simple_commands


def unreadable(*_arguments, **_keywords):
    raise check_module.shell_reader.ShellCommandUnreadable("a reader failure this case made")


check_module.shell_reader.simple_commands = unreadable
try:
    code, out = hook({"tool_name": "Bash", "cwd": "/work",
                      "tool_input": {"command": firing_command},
                      "tool_response": {"stdout": ""}})
finally:
    check_module.shell_reader.simple_commands = real_simple_commands
check("a command the shell reader cannot read is said to be unchecked",
      code == 0 and "could not read this command" in out
      and "a reader failure this case made" in out, out)


# ------------------------------------------------------------ the command line

def run_main(*arguments, machines=None):
    out = io.StringIO()
    code = check_module.main(list(arguments), stdout=out,
                             machines=machines or MachinesOfTheDay())
    return code, out.getvalue()


code, out = run_main("--command", "grep -l x */*.jsonl", "--cwd", PROJECTS)
check("a firing command exits 1 and prints its instruction",
      code == 1 and "with ./ in front of the glob" in out, f"{code} {out!r}")
code, out = run_main("--command", "grep -l x docs", "--cwd", "/work")
check("a silent command exits 0 and says nothing to report",
      code == 0 and "nothing to report" in out, f"{code} {out!r}")
code, out = run_main("--command", "grep -l x */*.jsonl", "--cwd", str(SCRATCH / "absent"),
                     machines=machines_with_the_stand_in_agents_grep())
check("a cause that could not be checked exits 3 and says what",
      code == 3 and "could not check" in out, f"{code} {out!r}")
output_file = SCRATCH / "output.txt"
output_file.write_text("a.jsonl\n")
code, out = run_main("--command", "grep -l x */*.jsonl", "--cwd", PROJECTS,
                     "--output-file", str(output_file), "--json")
check("--output-file and --json report a result that is not empty as not applicable",
      code == 0 and json.loads(out)["applicable"] is False, f"{code} {out!r}")
finished = subprocess.run([sys.executable, str(CHECK_SCRIPT), "--command", "x",
                           "--transcripts", str(SCRATCH)], capture_output=True, text=True)
check("two modes at once is a bad invocation",
      finished.returncode == 2 and "exactly one of" in finished.stderr, finished.stderr)

transcripts = SCRATCH / "transcripts" / "project"
transcripts.mkdir(parents=True)
records = [
    {"cwd": PROJECTS, "message": {"content": [
        {"type": "tool_use", "name": "Bash", "id": "t1",
         "input": {"command": "grep -l x */*.jsonl 2>/dev/null"}}]}},
    {"toolUseResult": {"stdout": "", "stderr": ""}, "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t1"}]}},
    {"cwd": "/work", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "id": "t2",
         "input": {"command": "grep -l x docs"}}]}},
    {"toolUseResult": "Error: Exit code 1\n", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t2"}]}},
]
(transcripts / "s.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")
code, out = run_main("--transcripts", str(SCRATCH / "transcripts"))
check("the measurement counts recorded runs and the ones that fire",
      code == 0 and "pairs           : 2" in out and "fired           : 1" in out
      and GLOB_DASH_NAME in out, out)
check_module.shell_reader.simple_commands = unreadable
try:
    code, out = run_main("--transcripts", str(SCRATCH / "transcripts"))
finally:
    check_module.shell_reader.simple_commands = real_simple_commands
check("the measurement counts each run the shell reader cannot read as unreadable",
      code == 0 and "unreadable      : 2" in out and "fired           : 0" in out, out)
check_module.shell_reader.simple_commands = unreadable
try:
    code, out = run_main("--command", "grep -l x docs", "--cwd", "/work")
finally:
    check_module.shell_reader.simple_commands = real_simple_commands
check("a command the shell reader cannot read exits 3 on the command line",
      code == 3, f"{code} {out!r}")


# --------------------------------------- the record against the real agent's grep

try:
    real_machines = check_module.Machines()
    real_machines.agents_grep()
except check_module.MachineStateQueryGotNoAnswer as error:
    print(f"SKIP  [this machine cannot run it] the fixture's refusals checked against the "
          f"real agent's grep: {error}")
else:
    def real_agents_grep_answer(arguments):
        try:
            return real_machines.agents_grep_refuses(arguments, None)
        except check_module.MachineStateQueryGotNoAnswer:
            return None

    for firing in firings:
        # The directories are the day's, as recorded; only the grep is this machine's.
        answers = [(arguments, real_agents_grep_answer(arguments))
                   for command in check_module.split_into_simple_commands_with_the_machine_and_directory_each_runs_in(
                       firing["command"], firing["cwd"])
                   if (arguments := check_module.agents_grep_options_and_patterns_without_file_names(
                       command, MachinesOfTheDay(firing["machine"], firing["timestamp"]), []))]
        refused = [arguments for arguments, answer in answers if answer]
        unanswered = [arguments for arguments, answer in answers if answer is None]
        check(f"{firing['id']}: the real agent's grep answers every probe and refuses what the "
              f"fixture records",
              refused == firing["arguments_the_agents_grep_refuses"] and unanswered == [],
              f"{refused} unanswered {unanswered}")


if failures:
    print(f"\n{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("\nall cases passed")
