"""Tell an interim subagent task-notification from the one that ends the subagent.

Claude Code sends a <task-notification> each time a background subagent stops.
When the subagent stopped while background work of its own still runs, the
notification is interim: the same task-id notifies again when the subagent
resumes and stops for good, so the last notification for a task-id decides
whether the subagent is still running. Claude Code marks an interim
notification in one of two ways, both seen in transcripts of the same Claude
Code versions: its <note> says the result below may be interim, or its
<result> begins "This agent has not reported yet".

Not a program to run: scripts/handoff-context-threshold-hook.py,
nc-systems/handoff/handoff-write-and-check-supervisor.py and
scripts/handoff-extract-conversation-subagent-tracker-nbd.py load it.
"""

import re

TASK_NOTIFICATION_INTERIM_NOTE_PHRASE = "the result below may be interim"
REPORT_NOT_YET_SENT_PREFIX = "This agent has not reported yet"

_NOTE_PATTERN = re.compile(r"<note>(.*?)</note>", re.S)
_RESULT_PATTERN = re.compile(r"<result>(.*?)</result>", re.S)


def task_notification_is_interim(notification_body: str) -> bool:
    """Return True when one <task-notification> block says its subagent will notify again.

    The body may be the plain text or the JSON-escaped text of a transcript line.
    """
    # A report can quote a <note>; only the harness's own tags precede <result>.
    harness_tags = notification_body.split("<result>", 1)[0]
    note = _NOTE_PATTERN.search(harness_tags)
    if note is not None and TASK_NOTIFICATION_INTERIM_NOTE_PHRASE in note.group(1):
        return True
    result = _RESULT_PATTERN.search(notification_body)
    return result is not None and result.group(1).lstrip().startswith(REPORT_NOT_YET_SENT_PREFIX)
