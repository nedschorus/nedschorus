#!/usr/bin/env python3
"""Run one Claude cold-read-cell against a cold-read-target.

One invocation = one cold-read-cell — the twin of the Codex cold-read-cell
launcher (nc-systems/cold-read/cold-read-codex-cell.py). Everything the two do apart
from invoking their model lives in nc-systems/cold-read/cold-read-cell-common.py and is
imported by both, so the legs cannot drift. Read that file for the report
contract, the write-detection rule, and why the reviewer writes a file rather
than answering in chat.

Usage:
  nc-systems/cold-read/cold-read-claude-cell.py --cell restate --tier second \\
      --target docs/drafts/foo.md \\
      --report cold-read-records/foo-2026-01-01/claude-restate-second.md

The reviewer writes its findings to --report. This program prints progress
to stderr and nothing to stdout.

Exit codes: 0 a model produced a report; 1 every model in the cold-read-tier's
chain failed to produce one; 64 this program refused the invocation and never
launched a model, naming its own fix. 64 rather than the conventional 2 for the
reason written beside EXIT_BAD_INVOCATION in nc-systems/cold-read/cold-read-cell-common.py,
which both cold-read-cells share.

WHY A CLAUDE COLD-READ-CELL'S STAMP CARRIES NO `tokens=` FIELD. Every stamp
records `duration_s=` (user-ruled 2026-08-25), and Codex cold-read-cells also
record `tokens=` because the Codex CLI prints a total. The Claude CLI prints
no equivalent, so there is no figure to record and the field is omitted rather
than filled with a zero -- an omitted field reads as "not reported", a zero
would read as "this cold-read-cell cost nothing". If the CLI starts printing a
"tokens used" line, the shared parser in nc-systems/cold-read/cold-read-cell-common.py picks
it up with no change here.
"""

import importlib.util
import json
import pathlib
import sys

_common_spec = importlib.util.spec_from_file_location(
    "cold_read_cell_common", pathlib.Path(__file__).with_name("cold-read-cell-common.py")
)
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)

PROGRAM = "cold-read-claude-cell"

# No fallback: each tier must use its pinned model rather than silently substitute a weaker reviewer.
TIER_TO_CLAUDE_MODEL_CHAIN = {
    "deep": ("claude-opus-5-5",),
    "second": ("claude-fable-5-1",),
}

# Pin effort so results do not depend on the machine's default.
TIER_TO_REASONING_EFFORT = {
    "deep": "xhigh",
    "second": "max",
}

# Write is needed for the report; WebFetch lets the reviewer inspect linked pages.
ALLOWED_TOOLS = "Read,Grep,Glob,Write,WebFetch"

# --allowedTools adds permissions under auto mode; explicitly deny both Bash and Monitor
# to remove shell access, including access to keychain credentials.
DISALLOWED_TOOLS = "Bash,Monitor"

# Disable hooks without disabling CLAUDE.md: hooks can block reports or rebase the reviewed checkout.
# Read deny patterns need // for absolute paths; authentication happens outside model tools.
CREDENTIAL_READ_DENY_RULES = (
    [f"Read(~/{directory.relative_to(pathlib.Path.home())}/**)"
     for directory in common.CREDENTIAL_DIRECTORIES]
    + [f"Read(//**/{pattern})" for pattern in common.CREDENTIAL_FILE_NAME_PATTERNS]
    + [f"Read(/{path})" for path in common.reviewer_program_login_files()]
)
SETTINGS = json.dumps({"disableAllHooks": True,
                       "permissions": {"deny": CREDENTIAL_READ_DENY_RULES}})


def invocation_builder(effort: str):
    """Return a callback yielding model argv and prompt input for the shared runner."""
    # Pass the prompt on stdin: variadic --allowedTools can swallow a trailing positional argument.
    def build_invocation(model: str, prompt: str):
        command = [
            "claude", "-p",
            "--model", model,
            "--effort", effort,
            "--output-format", "text",
            "--allowedTools", ALLOWED_TOOLS,
            "--disallowedTools", DISALLOWED_TOOLS,
            "--settings", SETTINGS,
        ]
        return command, prompt
    return build_invocation


def model_family_name(model: str) -> str:
    """Return the family name used by Claude's model-limit messages."""
    parts = model.split("-")
    return parts[1].capitalize() if len(parts) > 1 and parts[1] else model


# Match the CLI's failure messages at line starts; model-limit prefixes use the current model family.
def recognised_failure_texts_for_model(model: str) -> list:
    family = model_family_name(model)
    return [
        common.RecognisedFailureText(
            "account-limit", "You've hit your session limit",
            common.DETAIL_IS_REST_OF_LINE),
        common.RecognisedFailureText(
            "model-limit", f"You've reached your {family} limit", family),
        common.RecognisedFailureText(
            "logged-out", "Not logged in", common.DETAIL_IS_WHOLE_LINE),
    ]


def main() -> int:
    return common.run_cell(
        program=PROGRAM, runtime="claude", description=__doc__,
        model_help="explicit Claude model id; overrides the tier mapping",
        tier_to_model_chain=TIER_TO_CLAUDE_MODEL_CHAIN,
        tier_to_effort=TIER_TO_REASONING_EFFORT,
        invocation_builder=invocation_builder,
        recognised_failure_texts_for_model=recognised_failure_texts_for_model,
    )


if __name__ == "__main__":
    sys.exit(main())
