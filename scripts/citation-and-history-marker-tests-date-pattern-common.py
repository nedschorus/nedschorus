"""The date patterns the three tests that keep dates out of agent-facing text share.

scripts/standing-instructions-carry-no-citations-test.py,
scripts/registered-hook-messages-carry-no-citations-test.py and
scripts/code-comments-carry-no-history-markers-test.py each load this module
by its file path for their "date" marker, so a form of date that one of them
finds, the other two find too. The module is not run on its own.
"""
import re

# A date, a timestamp such as `YYYY-MM-DDThh:mm:ssZ`, or a range of days such as
# `YYYY-MM-DD/DD` or `YYYY-MM-DD-DD`. The optional group takes a timestamp's time
# or a range's last day into the date, so the lookahead judges what follows the
# whole date, and leaves out a path or file name that starts with a date, such as
# `YYYY-MM-DD-minutes.md`, `logs/YYYY-MM-DD/` or `YYYY-MM-DDThh:mm:ssZ.log`. The
# group is atomic: a failed lookahead must not shorten a timestamp to an earlier
# colon, which would report the start of a timestamped file name as a date.
_DATE_TIME_OR_RANGE_AND_WHAT_MAY_FOLLOW = (r"\d{4}-[01]\d-[0-3]\d"
                                         r"(?>T[\d:]+(?:\.\d+)?Z?|[/-]\d\d?)?(?![\w/-]|\.\w)")

# For comments and messages: a date at the end of a name, such as a walk named
# `x-YYYY-MM-DD`, is a citation there, so it is found.
DATE_MARKER_PATTERN = re.compile(r"\b" + _DATE_TIME_OR_RANGE_AND_WHAT_MAY_FOLLOW)

# For standing instructions, where a path or file name such as `x-YYYY-MM-DD.md`
# is a pointer an agent may follow: a date joined to a name is left out too.
DATE_MARKER_PATTERN_OUTSIDE_PATH_AND_FILE_NAMES = re.compile(
    r"(?<![\w/.-])" + _DATE_TIME_OR_RANGE_AND_WHAT_MAY_FOLLOW)
