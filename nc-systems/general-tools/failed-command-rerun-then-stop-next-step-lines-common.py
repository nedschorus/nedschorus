#!/usr/bin/env python3
"""The next-step lines a program prints for an agent after one of its commands failed.

Every program that tells an agent "rerun once, then stop and tell the user" takes
the wording from here, so a correction reaches all of them at once.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "failed_command_rerun_then_stop_next_step_lines_common", <path>)
"""

# Only who is told changes for a subagent: it still stops.
SUBAGENT_TELLS_ITS_DISPATCHER_SENTENCE = (
    "A subagent tells the agent that dispatched it, not the user.")


def rerun_then_stop_line(rerun, program, *, failure="fails again",
                         error_included="git's error"):
    """The closing line: when the rerun fails too, stop and report what both runs printed."""
    included = f", {error_included} included" if error_included else ""
    return (f"If {rerun} {failure}, stop, and tell the user what {program} printed and what "
            f"the rerun printed{included}. {SUBAGENT_TELLS_ITS_DISPATCHER_SENTENCE}")


def git_failure_next_step_lines(rerun, program, *, agent_gave_the_names=True):
    """The lines for a git command that failed in a program the agent ran.

    Leave out the line about a misspelt name when the agent gave the program no
    branch, commit or path, as when a supervisor runs between sessions.
    """
    lines = [f"If git's error names a lock file, such as .git/index.lock, wait one minute, "
             f"then run {rerun}; do not delete the lock file yourself."]
    if agent_gave_the_names:
        lines.append(f"If git's error names a branch, commit or path that does not exist, and "
                     f"you gave that name to {program}, correct it in your command, then run "
                     f"the corrected command.")
    lines += [f"In any other case, run {rerun} once more.", rerun_then_stop_line(rerun, program)]
    return "\n".join(lines)


def same_failure_again_line(when, program):
    """The closing line for a hook, which runs again by itself `when`, such as "at your next Edit"."""
    return (f"If the same failure is reported again {when}, tell the user what {program} "
            f"printed both times, git's error included. {SUBAGENT_TELLS_ITS_DISPATCHER_SENTENCE}")
