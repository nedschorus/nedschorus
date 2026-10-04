#!/usr/bin/env python3
"""Run one Codex cold-read-cell against a cold-read-target.

One invocation = one cold-read-cell — the twin of the Claude cold-read-cell
launcher (nc-systems/cold-read/cold-read-claude-cell.py). Everything the two do apart
from invoking their model lives in nc-systems/cold-read/cold-read-cell-common.py and is
imported by both, so the legs cannot drift. Read that file for the report
contract, the write-detection rule, and why the reviewer writes a file rather
than answering in chat.

Usage:
  nc-systems/cold-read/cold-read-codex-cell.py --cell restate --tier second \\
      --target docs/cross-project/foo.md \\
      --report cold-read-records/foo-2026-01-01/codex-restate-second.md

The reviewer writes its findings to --report. This program prints progress
to stderr and nothing to stdout.

Exit codes: 0 a model produced a report; 1 every model in the cold-read-tier's
chain failed to produce one -- which covers every way `codex exec` itself can
fail, AND the case where codex never started at all because the binary is not
on PATH. That last one is worth naming rather than leaving implied: an
unlaunchable codex raises OSError, and left uncaught that would be a
traceback exiting 1 as well, so the same number would mean both "the chain
was tried and nothing produced a review" and "this program crashed". The
common module catches it, names the model and the error on stderr, and lets
the chain advance, so a 1 from here always means the first thing and the
stderr line says which models failed how;
64 this program refused the invocation and never launched codex (a target
that is not a file, a report path that is not a file, a missing prompt
template, or a command-line error argparse caught). 64 rather than the
conventional 2 because `codex exec` ITSELF exits 2 when it rejects a command
line, so a 2 out of this program would not say which layer refused.

CODEX'S OWN EXIT CODE IS NO LONGER PASSED THROUGH, and that changed with the
move to a report file. A failed model is now a model the chain falls back
from, so what the caller needs from the exit code is whether any model
produced a review, not which one failed how. The code codex returned, and
codex's own words, go to this program's stderr -- which the cold-read-grid keeps
whenever a cold-read-cell fails, and which is where a defect in the command this
program composes is diagnosed. The measurements behind the choice of 64, and
what an exit 0 from `codex exec` does and does not promise, are written once
in scripts/code-review-codex-cell.py's docstring under the heading
EXIT CODES

WHY THE SANDBOX IS NO LONGER READ-ONLY. This cold-read-cell used to run
`--sandbox read-only` and take the review out through
`--output-last-message`. Both legs captured only the model's final message,
and text written before a tool call is discarded by that capture (measured
2026-08-23), so a reviewer that interleaved reading and writing shipped its
closing line and none of its findings. The reviewer now writes its report
itself, which needs write access. Per the user's ruling the same day, writes
are detected rather than blocked: the report goes under the gitignored
cold-read-records/ tree, where `git status` cannot see it, and the shared
module names any other path whose content changed while the reviewer ran. It
compares content rather than the list of paths git calls dirty because a
cold-read-target is usually a draft that has not landed: the tree is
already dirty when the run starts, so "dirty afterwards too" says nothing,
while "this file holds something else now" says the reviewer wrote it
(nedschorus#167).

WHY A PERMISSION PROFILE, NOT `--sandbox workspace-write`. No reviewer opens
a credential file (user-ruled 2026-09-28; the rule and why are beside
CREDENTIAL_DIRECTORIES in nc-systems/cold-read/cold-read-cell-common.py).
`--sandbox workspace-write` lets a reviewer read anything, so the cell runs
under a named permission profile instead: it extends Codex's `:workspace`
profile, which writes where workspace-write did, and denies the credential
directories and file names. Codex refuses the two together, so `--sandbox`
is gone. Measured 2026-09-28 with canary files, on both machines: under
workspace-write the reviewer read all three canaries; under the profile it
read none, still read README.md, and wrote its report. Codex expands a deny
pattern with ripgrep before it starts on Linux, and aborts when any
directory under the pattern's prefix is unreadable (ned-box's home holds
one), so on Linux the profile lists the files credential_files_found_now()
finds; on macOS it takes the patterns. Only credential directories that
exist are listed: Codex on Linux turns a missing one into an empty file on
the real disk. The reviewer programs' login files that exist are denied
too, Codex's own `~/.codex/auth.json` included: the Codex CLI reads its login
outside the profile, which governs only the model's commands, and a cell
denying it still answered, on both machines (user-ruled and measured
2026-09-29). The profile switches network access on, which it denies by
default: a web page the document links to is part of what the reviewer
reads, and the reviewer fetches it itself (user-ruled 2026-09-29, items 3
and 5 of the walk what-a-cold-read-reviewer-may-read-2026-09-28). Measured
that day on both machines: the reviewer fetched a public GitHub issue page,
HTTP 200, and still could not read a credential canary. The cell also sets
`web_search="live"`: Codex's own web tool otherwise answers from a cache, and
on the Mac it answered "Cache miss" for a page a document linked in 2 of 3
cells, while with the setting it fetched the page in 2 of 2, as ned-box did
without it (measured 2026-09-29; user-ruled 2026-09-30, item 6 of the walk
open-questions-concerns-and-recommendations-2026-09-30). Rechecked on the Mac
after the change, 2026-09-30: a cell barred from curl fetched a GitHub issue
page with the web tool and read the title the issue had been given that day.

WHY /tmp IS READ-ONLY IN THE PROFILE ON LINUX, AND ONLY THERE. `:workspace`
makes /tmp and $TMPDIR writable roots, and Codex's Linux sandbox mounts its
protected names `.git`, `.codex` and `.agents` read-only inside every
writable root, creating any that are missing on the real disk. `/tmp/.git`
then made every seat's instruction-file guard take /tmp for a checkout
(review 5346166603, 2026-09-29: three of the guard's test cases failed on
ned-box). On Linux the profile sets `:slash_tmp` and `:tmpdir` to read, as
the old sandbox mode never created them. On macOS it leaves them writable:
the Mac's sandbox makes no mount points, and there a read-only $TMPDIR broke
every shell here-document, since zsh writes one to a temp file ("can't
create temp file for here document: operation not permitted", measured
2026-09-29 through this cell). Codex reviewers write here-documents: 52 of
4,813 tool calls in the Mac's Codex sessions that name cold-read-records
since 2026-09-01, 14 of them writing into that directory. On ned-box, bash
5.3 and dash ran both a small and a 100 KB here-document under the
read-only profile. Measured 2026-09-29 on ned-box with `codex exec` running a
shell command in a scratch repository, and with this cell against canary
files in a scratch checkout: nothing appeared under /tmp, and the reviewer
still wrote its report. The checkout itself is still a writable root, so a
Codex cold read on Linux can leave empty `.codex` and `.agents` directories
at the checkout's root (seen once, in the scratch repository, not in the
checkout); git ignores empty directories, and nothing reads them.

WHY THE CODEX MEMORY STORE IS OFF FOR REVIEW CELLS: written once, in
scripts/code-review-codex-cell.py's docstring, under that heading.

WHAT THE CODEX CLI TELLS US ABOUT COST, and where it goes (user-ruled
2026-08-25). This CLI ends a run with a line of the form "tokens used:
12,345" on stderr, and it is the only place a cold-read-cell's token cost is
stated by anyone. The shared module captures stderr, parses that line, and
stamps `tokens=` into the report's provenance line -- see `parse_tokens_used`
in nc-systems/cold-read/cold-read-cell-common.py, which is where the pattern lives so
this launcher keeps its single job of building an invocation. If a future
CLI version reworks or drops that line, the field simply goes absent from
the stamps: an absent field reads as "not reported", which is the truth, and
nothing else in the cold-read-cell depends on it.
"""

import importlib.util
import pathlib
import sys

_common_spec = importlib.util.spec_from_file_location(
    "cold_read_cell_common", pathlib.Path(__file__).with_name("cold-read-cell-common.py")
)
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)

PROGRAM = "cold-read-codex-cell"

# Use version-prefixed model IDs; gpt-6.1-sol requires codex-cli 0.159.1 or later.
TIER_TO_CODEX_MODEL_CHAIN = {
    "deep": ("gpt-6.1-sol",),
    "second": ("gpt-6-luna",),
}

# Pin effort so machine-local Codex defaults cannot change review behavior.
TIER_TO_REASONING_EFFORT = {
    "deep": "xhigh",
    "second": "xhigh",
}


CREDENTIAL_DENYING_PERMISSION_PROFILE = "cold-read-no-credentials"


def credential_denying_permission_profile_arguments(platform: str = sys.platform) -> list:
    """Return shared permission-profile overrides denying credential paths."""
    return common.codex_credential_denying_permission_profile_arguments(
        CREDENTIAL_DENYING_PERMISSION_PROFILE, ":workspace", platform, network=True)


def invocation_builder(effort: str):
    """Return a callback producing (argv, stdin text) for each model and prompt."""
    # Codex takes a positional prompt; None tells the runner to close stdin explicitly.
    def build_invocation(model: str, prompt: str):
        command = [
            "codex", "exec",
            *credential_denying_permission_profile_arguments(),
            "--disable", "memories",
            "-C", str(common.REPO_ROOT),
        ]
        if model:
            command += ["-m", model]
        command += ["-c", f"model_reasoning_effort={effort}"]
        command += ["-c", 'web_search="live"']
        command.append(prompt)
        return command, None
    return build_invocation


# The tracing logger may prefix a timestamp; the URL suffix varies.
# Unrecognized quota failures remain exit-N until a captured CLI message defines a signature.
def recognised_failure_texts_for_model(model: str) -> list:
    del model
    return [
        common.RecognisedFailureText(
            "logged-out",
            "ERROR codex_api::endpoint::responses_websocket: failed to connect to "
            "websocket: HTTP error: 401 Unauthorized",
            common.DETAIL_IS_WHOLE_LINE),
    ]


def main() -> int:
    return common.run_cell(
        program=PROGRAM, runtime="codex", description=__doc__,
        model_help="explicit Codex model id; overrides the tier mapping",
        tier_to_model_chain=TIER_TO_CODEX_MODEL_CHAIN,
        tier_to_effort=TIER_TO_REASONING_EFFORT,
        invocation_builder=invocation_builder,
        recognised_failure_texts_for_model=recognised_failure_texts_for_model,
    )


if __name__ == "__main__":
    sys.exit(main())
