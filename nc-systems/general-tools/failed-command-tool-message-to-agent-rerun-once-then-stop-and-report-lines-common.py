#!/usr/bin/env python3
"""The next-step lines a program prints for an agent after one of its commands failed.

Every program that tells an agent "rerun once, then stop and tell the user" takes
the wording from here, so a correction reaches all of them at once. A file-edit
hook also takes from here the command its lines tell the agent to rerun, and the
printer that puts its message where the agent reads it.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "failed_command_tool_message_to_agent_rerun_once_then_stop_and_report_lines_common", <path>)
"""

import json
import re
import shlex
from pathlib import Path

# Named before the report, so a subagent does not act on "tell the user" first.
REPORT_RECIPIENT_PHRASE_USER_OR_DISPATCHING_AGENT = (
    "the user, or, if you are a subagent, the agent that dispatched you,")


# git words a lock it cannot take, of the index or of a ref, "Unable to create '<path>.lock': <reason>",
# and does not escape a quote inside the path.
_GIT_ERROR_LOCK_FILE_PATH = re.compile(r"Unable to create '(.*\.lock)': ")


def git_error_names_a_lock_file_wait_then_rerun_line_or_none(git_error, then_run):
    """The line for a git error that names a lock file, or None when git_error names none.

    git fails at once on another process's lock file instead of waiting for it.
    """
    lock_file = _GIT_ERROR_LOCK_FILE_PATH.search(git_error)
    if lock_file is None:
        return None
    path = lock_file.group(1)
    # Claude Code refuses a Bash call that starts with a long plain sleep, but runs this bounded poll.
    wait = f"i=0; while [ -e {shlex.quote(path)} ] && [ $i -lt 30 ]; do sleep 2; i=$((i+1)); done"
    return (f"Git's error names the lock file {path}: do not delete the lock file yourself, "
            f"because a git command still running may hold it; wait up to one minute for git to "
            f"remove it by running `{wait}` (Claude Code refuses a plain `sleep 60`), "
            f"then run {then_run}, whether or not the lock file is gone.")


def agent_instruction_if_rerun_fails_too_stop_and_report_both_runs_line(
        text_the_failure_line_contains=None, *, rerun_fails_when=None,
        which_lines_to_quote_in_the_report=None,
        phrase_a_stop_message_uses_for_the_command_the_agent_reruns="the rerun",
        read_by_a_subagent=True,
        next_step_to_skip_when_the_rerun_fails_too=None):
    """The closing line: when the rerun fails too, stop and report what both runs printed.

    text_the_failure_line_contains is text the failure's own line contains, such as "could not
    check": exit codes differ between programs, and some print a failure and
    exit 0, so the reader is given text to look for. Where no such text exists,
    pass rerun_fails_when and which_lines_to_quote_in_the_report instead; any other
    mix of the three raises TypeError.
    next_step_to_skip_when_the_rerun_fails_too names work the stop holds back
    that the reader would otherwise go on to. Leave out the subagent clause
    where no subagent reads the line, as in a session's first prompt.
    """
    free_text = (rerun_fails_when, which_lines_to_quote_in_the_report)
    if (None in free_text) if text_the_failure_line_contains is None else free_text != (None, None):
        raise TypeError(
            "pass either text_the_failure_line_contains alone, or both rerun_fails_when "
            "and which_lines_to_quote_in_the_report")
    if text_the_failure_line_contains is not None:
        rerun_fails_when = f'prints a line containing "{text_the_failure_line_contains}" again'
        which_lines_to_quote_in_the_report = (
            f'the line containing "{text_the_failure_line_contains}" from the command that printed '
            f'this message and from {phrase_a_stop_message_uses_for_the_command_the_agent_reruns.rstrip(",")}')
    stop = (f"stop, do not {next_step_to_skip_when_the_rerun_fails_too},"
            if next_step_to_skip_when_the_rerun_fails_too else "stop,")
    who = REPORT_RECIPIENT_PHRASE_USER_OR_DISPATCHING_AGENT if read_by_a_subagent else "the user"
    return (f"If {phrase_a_stop_message_uses_for_the_command_the_agent_reruns} "
            f"{rerun_fails_when}, {stop} and tell {who} word for word, "
            f"{which_lines_to_quote_in_the_report}.")


def git_failure_next_step_lines(rerun, program=None, *,
                                git_error_line_shown_in_tool_message_to_agent_checked_for_lock_file_path,
                                text_the_failure_line_contains=None,
                                rerun_fails_when=None, which_lines_to_quote_in_the_report=None,
                                read_by_a_subagent=True, next_step_to_skip_when_the_rerun_fails_too=None):
    """The lines for a git command that failed in a program the agent ran.

    rerun is the command the agent runs again, written out in full; the lines put it between
    backticks, so the words after it are not read as more arguments.
    Pass program, the name the misspelt-name line gives the program, only when
    the git command that failed ran on a branch, commit or path the agent gave
    on the command line and the program had not already checked it: the
    misspelt-name line is included exactly when program is given.
    git_error_line_shown_in_tool_message_to_agent_checked_for_lock_file_path is
    git's error as the message prints it; the lines give the lock-file step
    exactly when it names a lock file.
    """
    lock_file_line = git_error_names_a_lock_file_wait_then_rerun_line_or_none(
        git_error_line_shown_in_tool_message_to_agent_checked_for_lock_file_path, f"exactly `{rerun}`")
    phrase_a_stop_message_uses_for_the_command_the_agent_reruns = "the rerun"
    if lock_file_line is not None:
        lines = [lock_file_line]
    elif program is not None:
        lines = [f"If a branch, commit or path you gave {program} on its command line is "
                 f"misspelt or does not exist, correct it in your command, then run the "
                 f"corrected command.",
                 f"Otherwise, run exactly `{rerun}` once more."]
        phrase_a_stop_message_uses_for_the_command_the_agent_reruns = "the rerun, or the corrected command,"
    else:
        lines = [f"Run exactly `{rerun}` once more."]
    lines.append(agent_instruction_if_rerun_fails_too_stop_and_report_both_runs_line(
        text_the_failure_line_contains, rerun_fails_when=rerun_fails_when,
        which_lines_to_quote_in_the_report=which_lines_to_quote_in_the_report,
        phrase_a_stop_message_uses_for_the_command_the_agent_reruns=(
            phrase_a_stop_message_uses_for_the_command_the_agent_reruns),
        read_by_a_subagent=read_by_a_subagent,
        next_step_to_skip_when_the_rerun_fails_too=next_step_to_skip_when_the_rerun_fails_too))
    return "\n".join(lines)


def hook_agent_instruction_if_git_failure_recurs_tell_user_both_outputs_line(when, program):
    """The closing line for a hook, which runs again by itself `when`, such as "at your next Edit".

    program is the prefix the hook's lines start with, so the reader can match
    the next report to this one.
    """
    return (f'If a line starting "{program}" reports a git failure again {when}, whether this '
            f"error or another, tell {REPORT_RECIPIENT_PHRASE_USER_OR_DISPATCHING_AGENT} "
            f"word for word, every line of this message and of the new one, before you go on. "
            f"If the check finds no git failure then, this failure needs no report.")


def hook_agent_instruction_if_rerun_command_reports_git_failure_tell_user_both_outputs_line(program):
    """The closing line for a hook whose message ends with a command that reruns the hook.

    The command prints the hook's JSON, so the reader looks inside its
    additionalContext field for program, the prefix the hook's lines start with.
    """
    return (f"If the command on the line above prints JSON whose hookSpecificOutput.additionalContext "
            f'field starts with "{program}" and reports a git failure, whether this error or another, '
            f"tell {REPORT_RECIPIENT_PHRASE_USER_OR_DISPATCHING_AGENT} word for word, every line of "
            f"this message and of that field, before you go on. If the command prints nothing, or JSON "
            f"whose field reports no git failure, the git failure above needs no report.")


def file_edit_hook_shell_command_that_runs_the_hook_on_one_file_as_claude_code_would(
        hook_script_path: Path, working_directory, file_path: str) -> str:
    """A shell command that runs the hook at hook_script_path on file_path as Claude Code would."""
    payload = json.dumps({"cwd": str(working_directory), "tool_input": {"file_path": file_path}})
    return f"printf '%s\\n' {shlex.quote(payload)} | python3 {shlex.quote(str(hook_script_path))}"


def post_tool_use_hook_additional_context_print_for_agent(text) -> None:
    """Print text as additionalContext, which the agent reads next when the hook exits 0.

    A git failure takes this channel too: Claude Code records the stderr of a
    PostToolUse exit 1 in the transcript but never passes it to the model.
    """
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": text,
    }}, ensure_ascii=False))
