#!/usr/bin/env python3
"""The next-step lines a program prints for an agent after one of its commands failed.

Every program that tells an agent "rerun once, then stop and tell the user" takes
the wording from here, so a correction reaches all of them at once.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "failed_command_agent_facing_message_rerun_once_then_stop_and_report_lines_common", <path>)
"""

# Only who is told changes for a subagent: where the line says to stop, it still stops.
SUBAGENT_REPORTS_TO_ITS_DISPATCHER_NOT_THE_USER_SENTENCE = (
    "A subagent reports to the agent that dispatched it, not to the user.")


def agent_instruction_if_rerun_fails_too_stop_and_report_both_runs_line(
        failure_again, program, *, read_by_a_subagent=True, also_not=""):
    """The closing line: when the second run fails too, stop and report both runs' lines.

    failure_again is what the reader sees when the second run fails, such as
    'prints "could not check" again': exit codes differ between programs, and
    some print a failure and exit 0. also_not names work the stop holds back
    that the reader would otherwise go on to, such as "take the next step below".
    Leave the subagent sentence out where no subagent reads the line, as in a
    session's first prompt.
    """
    stop = f"stop, do not {also_not}," if also_not else "stop,"
    line = (f"If the run you made by following a line above {failure_again}, {stop} and tell "
            f"the user, word for word, the lines {program} printed the first time and the "
            f"lines that second run printed.")
    if read_by_a_subagent:
        line += f" {SUBAGENT_REPORTS_TO_ITS_DISPATCHER_NOT_THE_USER_SENTENCE}"
    return line


def git_failure_next_step_lines(rerun, program, *, failure_again,
                                takes_a_branch_commit_or_path, read_by_a_subagent=True,
                                also_not=""):
    """The lines for a git command that failed in a program the agent ran.

    The line about a misspelt name is printed only for a program that takes a
    branch, commit or path from the agent; elsewhere no name of the agent's can
    be wrong.
    """
    lines = [f"If git's error names a lock file, such as .git/index.lock, wait one minute, "
             f"then run {rerun}; do not delete the lock file yourself."]
    if takes_a_branch_commit_or_path:
        lines.append(f"If git's error names a branch, commit or path that does not exist, and "
                     f"you gave that name to {program}, correct it in your command, then run "
                     f"the corrected command.")
    lines += [f"If none of the cases above applies, run {rerun} once more, unchanged.",
              agent_instruction_if_rerun_fails_too_stop_and_report_both_runs_line(
                  failure_again, program, read_by_a_subagent=read_by_a_subagent,
                  also_not=also_not)]
    return "\n".join(lines)


def hook_agent_instruction_if_git_failure_recurs_tell_user_both_outputs_line(when, program):
    """The closing line for a hook, which runs again by itself `when`, such as "at your next Edit"."""
    return (f"Keep this message: if {program} reports a git failure again {when}, whether this "
            f"error or another, tell the user both messages, word for word. "
            f"{SUBAGENT_REPORTS_TO_ITS_DISPATCHER_NOT_THE_USER_SENTENCE}")
