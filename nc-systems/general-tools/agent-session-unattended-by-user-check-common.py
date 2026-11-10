#!/usr/bin/env python3
"""Whether a user attends this agent-session, read from two environment variables.

No user attends an agent-session when either holds:
- NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER is set, to any non-empty
  value: a program of this project started the agent-session and reads its
  answer itself, as scripts/ghi-guide-agent-ask.py does;
- CLAUDE_CODE_SESSION_ATTENDED is "0": Claude Code sets it so for a headless
  `claude -p` run, and to "1" for an interactive agent-session.

A missing CLAUDE_CODE_SESSION_ATTENDED counts as attended, so a hook speaks
rather than stays silent when Claude Code says nothing. Hooks that speak only
to a user, or claim what only a user should see, ask this module instead of
reading the two variables themselves, so that a change in how Claude Code
marks a headless agent-session is made here once. Load it by file path, as
nc-systems/skills/walk-me-through/walk-me-through-pending-user-alerts-claim-and-insert-as-approval-walk-items-user-prompt-submit-hook.py
does. It reads only the mapping it is given and cannot fail on one.
"""

SESSION_ATTENDED_VARIABLE = "CLAUDE_CODE_SESSION_ATTENDED"
SESSION_UNATTENDED_VALUE = "0"
REINCARNATION_OWNED_BY_CALLER_VARIABLE = "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER"
AGENT_SESSION_ATTENDANCE_ENVIRONMENT_VARIABLES = (
    SESSION_ATTENDED_VARIABLE,
    REINCARNATION_OWNED_BY_CALLER_VARIABLE,
)


def agent_session_unattended_by_user(environment):
    """True when the environment mapping marks an agent-session no user attends."""
    return bool(environment.get(REINCARNATION_OWNED_BY_CALLER_VARIABLE)
                or environment.get(SESSION_ATTENDED_VARIABLE) == SESSION_UNATTENDED_VALUE)


def environment_without_agent_session_attendance_variables(environment):
    """A copy of the environment mapping without the two variables, for a test to add its own."""
    return {name: value for name, value in environment.items()
            if name not in AGENT_SESSION_ATTENDANCE_ENVIRONMENT_VARIABLES}
