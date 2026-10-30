#!/usr/bin/env python3
"""Hand an agent-facing-message and its situation to two fresh-agents, and check the scripts it names.

Usage:
  scripts/agent-facing-message-ask-two-fresh-agents-next-step-and-check-named-script-flags.py \\
      --message-file MESSAGE --situation-file SITUATION

MESSAGE holds the message exactly as the agent receives it. SITUATION says
what the agent was doing: its goal, the tool call or command that drew the
message, quoted exactly, and the channel the message came through, such as
"the tool call was refused with this message".

Two fresh-agents read both, one on the cold-read-tier `fast` (Claude Sonnet) and
one on `deep` (Claude Opus), each started through
nc-systems/cold-read/cold-read-claude-cell.py from this checkout, at the same
time. That launcher runs `claude -p` in the checkout with hooks off, so each
fresh-agent has CLAUDE.md, the user's CLAUDE.md and the repository to read, as a
real agent does, but only the tools Read, Grep, Glob, Write and WebFetch. A
fresh-agent is told not to act, only to write down what it would do next; this
program prints both answers. It does not carry the answers out, but a
fresh-agent can still write files with its Write tool: whatever the launcher
prints on its error output, its line on files changed outside the report
included, is printed under that fresh-agent's answer.

Then, for each path ending in .py or .sh that the message names, it says
whether the file exists (relative paths from this checkout's top directory),
runs it with --help, and says whether each --flag written after the path, up
to the next backquote, `;`, `|`, `&` or path on the same line, appears in the
--help output. A flag the --help text does not mention is reported as missing
even when argparse would accept an abbreviation of a longer one. A script that
ignores --help does its real work instead; every program in this repository
is required to accept --help, and a script named in a message from outside the
repository is run all the same.

Prints its report on stdout. Exit codes: 0 both fresh-agents answered, whatever
the checks of the named scripts found; 1 a fresh-agent wrote no answer, and the report
gives the launcher's output; 2 MESSAGE or SITUATION could not be read, and no fresh-agent was started;
3 both fresh-agents answered, and the launcher reported files in this checkout changed outside a report.
"""

import argparse
import concurrent.futures
import importlib.util
import pathlib
import re
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROGRAM_PATH = "scripts/agent-facing-message-ask-two-fresh-agents-next-step-and-check-named-script-flags.py"
CLAUDE_CELL_LAUNCHER = REPO_ROOT / "nc-systems/cold-read/cold-read-claude-cell.py"
FOLLOWER_ANSWER_FILE_LABEL_FOR_CELL_FLAG = "agent-facing-message-follower"
FOLLOWER_TIERS = ("fast", "deep")
HELP_TIMEOUT_SECONDS = 60
EXIT_CHECKOUT_CHANGED = 3

_common_spec = importlib.util.spec_from_file_location(
    "cold_read_cell_common", REPO_ROOT / "nc-systems/cold-read/cold-read-cell-common.py")
cell_common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(cell_common)

# Messages this program hands an agent follow
# docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.

FOLLOWER_PROMPT = """You are an agent-session working in the repository at {REPO_ROOT}, in your own worktree. In your real work you can use the tools Bash, Read, Edit, Write, Grep, Glob, TaskList, SendMessage (send a message to another agent-seat by its name), ListAgents (list the agent-seats you can message) and the skills under .claude/skills/.

The file {TARGET_PATH} says what you were doing and gives the message a program handed you. Read it.
You may read any other file, as you would in real work, before you decide.
Do not carry anything out. Change no file except the one named below.

Write to {REPORT_PATH} exactly what you would do next: the exact commands or tool calls, in order, and any message you would send to the user or to another agent-seat, quoted. Write nothing else.
"""

SCRIPT_PATH_PATTERN = re.compile(r"(?<![\w./~-])(?:~?/)?(?:[\w.-]+/)*[\w-][\w.-]*\.(?:py|sh)(?![\w-])")
FLAG_PATTERN = re.compile(r"(?<![\w-])--[A-Za-z][\w-]*")
FLAG_SPAN_END_PATTERN = re.compile(r"[`;|&]")


def scripts_and_flags_named_in_agent_facing_message(message: str) -> dict:
    """Map each script path the message names to the flags written after it, in order of first mention."""
    scripts: dict = {}
    for line in message.splitlines():
        matches = list(SCRIPT_PATH_PATTERN.finditer(line))
        for index, match in enumerate(matches):
            span_end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
            span = line[match.end():span_end]
            stop = FLAG_SPAN_END_PATTERN.search(span)
            if stop:
                span = span[:stop.start()]
            flags = scripts.setdefault(match.group(), [])
            flags.extend(flag for flag in FLAG_PATTERN.findall(span) if flag not in flags)
    return scripts


def named_script_existence_and_flags_in_help_check_report_lines(script: str, flags: list) -> list:
    path = pathlib.Path(script).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.is_file():
        return [f"- `{script}`: NOT FOUND at {path}"]
    interpreter = "bash" if path.suffix == ".sh" else sys.executable
    try:
        completed = subprocess.run(
            [interpreter, str(path), "--help"], cwd=REPO_ROOT, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=HELP_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        return [f"- `{script}`: exists; --help did not finish within {HELP_TIMEOUT_SECONDS} s, "
                "so its flags were not checked"]
    if completed.returncode != 0:
        return [f"- `{script}`: exists; --help exited {completed.returncode}, so its flags "
                f"were not checked. Its output:", "", "```",
                (completed.stdout + completed.stderr).rstrip(), "```"]
    help_text = completed.stdout + completed.stderr
    lines = [f"- `{script}`: exists; --help exited 0"]
    for flag in flags:
        found = re.search(rf"(?<![\w-]){re.escape(flag)}(?![\w-])", help_text)
        lines.append(f"  - `{flag}`: {'in' if found else 'NOT IN'} the --help output")
    return lines


def run_follower(tier: str, target: pathlib.Path, prompt_file: pathlib.Path,
                 report: pathlib.Path) -> tuple:
    """Return whether the follower answered, whether it changed files outside its report, and the report's lines for it."""
    completed = subprocess.run(
        [sys.executable, str(CLAUDE_CELL_LAUNCHER), "--cell", FOLLOWER_ANSWER_FILE_LABEL_FOR_CELL_FLAG,
         "--tier", tier, "--target", str(target), "--report", str(report),
         "--prompt-file", str(prompt_file)],
        cwd=REPO_ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    heading = f"## Fresh-agent on cold-read-tier {tier}"
    if completed.returncode != 0:
        return False, False, [
            heading, "",
            f"FAILED: the fresh-agent on cold-read-tier {tier} wrote no answer, because "
            f"{CLAUDE_CELL_LAUNCHER} exited {completed.returncode}.",
            "The launcher's output is below. Its last line beginning `cold-read-claude-cell: cause:` "
            "names the cause.",
            "If that line names logged-out, account-limit or model-limit: tell the user what the line "
            "says; a subagent tells the agent that dispatched it.",
            f"Otherwise, or when there is no such line: rerun {PROGRAM_PATH} once with the same "
            "--message-file and --situation-file; if a fresh-agent fails again, tell the user the "
            "cause line, or the exit status when there is none.",
            "", "```", (completed.stderr + completed.stdout).rstrip(), "```"]
    lines = [heading, "", report.read_text(encoding="utf-8").rstrip()]
    changed_checkout = cell_common.STRAY_WRITE_PHRASE in completed.stderr
    if completed.stderr.strip():
        lines += ["", "The launcher also printed this on its error output, although it exited 0:",
                  "", "```", completed.stderr.rstrip(), "```"]
    if changed_checkout:
        lines += ["", f"CHECKOUT CHANGED: the launcher names files in {REPO_ROOT} that changed outside "
                  "the fresh-agent's report while it ran.",
                  "Run `git status --short` there and read each file it names; revert only the changes "
                  "the fresh-agent made, because another agent-session working in the checkout may have "
                  "made the rest."]
    return True, changed_checkout, lines


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--message-file", required=True, type=pathlib.Path)
    parser.add_argument("--situation-file", required=True, type=pathlib.Path)
    args = parser.parse_args()
    texts = {}
    for flag, path in (("--message-file", args.message_file), ("--situation-file", args.situation_file)):
        try:
            texts[flag] = path.read_text(encoding="utf-8")
        except OSError as error:
            print(f"FAILED: the file given to {flag} could not be read, so no fresh-agent was "
                  f"started: {error}.\n"
                  f"Rerun {PROGRAM_PATH} with --message-file and --situation-file, "
                  f"{flag} naming a readable text file.",
                  file=sys.stderr)
            return 2
    message, situation = texts["--message-file"], texts["--situation-file"]

    with tempfile.TemporaryDirectory(prefix="agent-facing-message-ask-two-fresh-agents-") as scratch:
        scratch_path = pathlib.Path(scratch)
        target = scratch_path / "situation-and-message.md"
        target.write_text(f"# What you were doing\n\n{situation.rstrip()}\n\n"
                          f"# The message\n\n{message.rstrip()}\n", encoding="utf-8")
        prompt_file = scratch_path / "follower-prompt.md"
        prompt_file.write_text(FOLLOWER_PROMPT.replace("{REPO_ROOT}", str(REPO_ROOT)),
                               encoding="utf-8")
        with concurrent.futures.ThreadPoolExecutor(len(FOLLOWER_TIERS)) as pool:
            follower_results = list(pool.map(
                lambda tier: run_follower(tier, target, prompt_file,
                                          scratch_path / f"{tier}-follower-answer.md"),
                FOLLOWER_TIERS))

    report_lines = []
    for _, _, section in follower_results:
        report_lines += section + [""]
    report_lines += ["## Scripts the message names", ""]
    scripts = scripts_and_flags_named_in_agent_facing_message(message)
    if not scripts:
        report_lines.append("The message names no path ending in .py or .sh.")
    for script, flags in scripts.items():
        report_lines += named_script_existence_and_flags_in_help_check_report_lines(script, flags)
    print("\n".join(report_lines))
    if not all(answered for answered, _, _ in follower_results):
        return 1
    return EXIT_CHECKOUT_CHANGED if any(changed for _, changed, _ in follower_results) else 0


if __name__ == "__main__":
    sys.exit(main())
