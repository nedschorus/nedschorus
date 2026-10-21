#!/usr/bin/env python3
"""The next-step lines a program prints for an agent after one of its commands failed.

Every program that tells an agent "rerun once, then stop and tell the user" takes
the wording from here, so a correction reaches all of them at once.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "failed_command_agent_facing_message_rerun_once_then_stop_and_report_lines_common", <path>)
"""

# Named before the report, so a subagent does not act on "tell the user" first.
THE_USER_OR_A_SUBAGENTS_DISPATCHER = (
    "the user, or, if you are a subagent, the agent that dispatched you,")


def agent_instruction_if_rerun_fails_too_stop_and_report_both_runs_line(
        failure_marker=None, *, rerun_fails_when=None, lines_to_report=None,
        rerun_name="the rerun", read_by_a_subagent=True,
        next_step_to_skip_when_the_rerun_fails_too=None):
    """The closing line: when the rerun fails too, stop and report what both runs printed.

    failure_marker is text the failure's own line contains, such as "could not
    check": exit codes differ between programs, and some print a failure and
    exit 0, so the reader is given text to look for. Where no such text exists,
    pass rerun_fails_when and lines_to_report instead.
    next_step_to_skip_when_the_rerun_fails_too names work the stop holds back
    that the reader would otherwise go on to. Leave out the subagent clause
    where no subagent reads the line, as in a session's first prompt.
    """
    if failure_marker is not None:
        rerun_fails_when = f'prints a line containing "{failure_marker}" again'
        lines_to_report = f'the line containing "{failure_marker}" from each run'
    stop = (f"stop, do not {next_step_to_skip_when_the_rerun_fails_too},"
            if next_step_to_skip_when_the_rerun_fails_too else "stop,")
    who = THE_USER_OR_A_SUBAGENTS_DISPATCHER if read_by_a_subagent else "the user"
    return (f"If {rerun_name} {rerun_fails_when}, {stop} and tell {who} word for word, "
            f"{lines_to_report}.")


def git_failure_next_step_lines(rerun, program, *, include_the_misspelt_branch_commit_or_path_line,
                                failure_marker=None, rerun_fails_when=None,
                                lines_to_report=None, read_by_a_subagent=True,
                                next_step_to_skip_when_the_rerun_fails_too=None):
    """The lines for a git command that failed in a program the agent ran.

    Include the misspelt-name line only for a program that takes a branch,
    commit or path on its command line; elsewhere no name of the agent's can
    be wrong.
    """
    lines = [f"If git's error names a lock file, such as .git/index.lock, wait one minute, "
             f"then run exactly {rerun}; do not delete the lock file yourself."]
    if include_the_misspelt_branch_commit_or_path_line:
        lines += [f"If a branch, commit or path you gave {program} on its command line is "
                  f"misspelt or does not exist, correct it in your command, then run the "
                  f"corrected command.",
                  f"If neither applies, run exactly {rerun} once more."]
        rerun_name = "the rerun, or the corrected command,"
    else:
        lines.append(f"If git's error names no lock file, run exactly {rerun} once more.")
        rerun_name = "the rerun"
    lines.append(agent_instruction_if_rerun_fails_too_stop_and_report_both_runs_line(
        failure_marker, rerun_fails_when=rerun_fails_when, lines_to_report=lines_to_report,
        rerun_name=rerun_name, read_by_a_subagent=read_by_a_subagent,
        next_step_to_skip_when_the_rerun_fails_too=next_step_to_skip_when_the_rerun_fails_too))
    return "\n".join(lines)


def hook_agent_instruction_if_git_failure_recurs_tell_user_both_outputs_line(when, program):
    """The closing line for a hook, which runs again by itself `when`, such as "at your next Edit".

    program is the prefix the hook's lines start with, so the reader can match
    the next report to this one.
    """
    return (f'If a line starting "{program}" reports a git failure again {when}, whether this '
            f"error or another, tell {THE_USER_OR_A_SUBAGENTS_DISPATCHER} word for word, every "
            f"line of this message and of the new one, before you go on. If the check finds no "
            f"git failure then, this failure needs no report.")
