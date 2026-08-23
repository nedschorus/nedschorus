#!/usr/bin/env python3
"""Run Codex's built-in code review over a git range, pinned and captured.

One cell of the merge lane's review: `codex exec review` is Codex's own
diff reviewer (finding rubric, P0-P3 priorities, changed-line locations).
This wrapper exists so invoking it is a committed, reviewable program
rather than a shell line in one seat's transcript, and so the pins that
must not drift are pinned:

  - model and reasoning effort, explicit (the tier convention of
    scripts/md-review-codex-cell.py: good = gpt-5.6-sol at xhigh);
  - the sandbox, read-only AT THE PARENT LEVEL -- this machine's Codex
    config defaults to workspace-write, so a reviewer that forgets this
    flag can write (the nested `review` parser rejects --sandbox; parent
    placement is the accepted form, verified on codex-cli 0.147.0);
  - the base, as a SHA the caller resolved -- `--base origin/main` drifts
    under a moving remote, so the review's subject is recorded exactly;
  - the output, captured to a file the caller names;
  - Codex's own memory store, OFF for this process (`--disable memories`) --
    see WHY THE CODEX MEMORY STORE IS OFF FOR REVIEW CELLS below.

What this deliberately does not do: accept custom review instructions.
On codex-cli 0.147.0 a [PROMPT] is mutually exclusive with --base and
switches to custom-review mode, losing the built-in rubric (measured
2026-08-19). Durable repository review rules belong in AGENTS.md per
Codex's documented mechanism; merge-decision checks belong to the
deferred pr-merge-decision component (nedschorus#105).

WHY THE CODEX MEMORY STORE IS OFF FOR REVIEW CELLS -- the one explanation
for every `codex exec` this repository launches; the other two sites
(scripts/md-review-codex-cell.py, scripts/sanity-check-attacks.py) pass the
same flag and point here.

Codex keeps a memory store under `~/.codex/` that Codex processes on this
machine share. When the feature is on, a session reads accumulated notes in,
and the memory pipeline writes fresh ones out of saved sessions. Whether it
is on by default is machine state that MOVES -- see the drift note below --
which is the whole reason this is pinned per invocation. Both directions are
unwanted for a review cell:

  - READING, which is the measured half. A cell is commissioned to be naive
    -- to judge the change in front of it, not to carry forward what Codex
    concluded reviewing this project before. On 2026-08-23 that store held a
    task group named "NedsChorus NC toolchain / constrained adversarial
    review and Phase-1 phasing checks", with sections "Reusable knowledge"
    and "Failures and how to do differently": Codex's own standing
    conclusions about this repository's work. Those notes were not merely
    sitting in the store, they were reaching the cells -- pull request #150's
    reviewer recovered the injected `role: developer` message headed
    `## Memory`, 37,535 characters, from THIS script's own review run on
    pull request #102, and found the block in 73 of 98 `codex exec` sessions
    across 2026-08-17 to 08-23, 61 of them under `--sandbox read-only`.
    (Repeating that measurement: `codex exec review` writes TWO session
    files, a parent wrapper without the block and a child reviewer thread
    with it, so a naive per-file scan undercounts.)
  - WRITING, which is a hazard to close rather than one observed happening,
    and this flag is not proven to close it. These cells are automation and
    the store is the user's personal one, kept for his interactive Codex;
    automated review runs should not be depositing findings in it. What the
    flag does about that is unestablished: it turns the feature off inside
    the cell process, but the cell still writes a session rollout file under
    `~/.codex/sessions/`, that persisted file is what the memory pipeline
    ingests later, and no per-session record of the flag was found in the
    sampled `session_meta` records. Whether the pipeline ingests a
    memories-disabled session anyway is unmeasured. `--ephemeral` -- "Run
    without persisting session files to disk" -- is the flag that removes
    the pipeline's input, and it is deliberately NOT used here: this
    script's transcript is the forensic record behind a merge decision, and
    the pull request #102 reproduction above was read out of one.
    (Measured on the store 2026-08-23, which is why the writing half claims
    no more than this: of the 129 sessions the pipeline has ever ingested,
    none has originator `codex_exec` -- the mode this script uses -- none
    comes from `~/agents/`, and ingestion had been idle since 2026-08-15.)

`--disable memories` is per-invocation. `codex exec --help` on codex-cli
0.147.0 documents it as "Disable a feature (repeatable). Equivalent to `-c
features.<name>=false`" -- a config override that applies to this
process only; it edits no config file and leaves the user's own interactive
Codex untouched. It does not stop the session itself being persisted: see
the WRITING bullet above for what that leaves open.
What is verified on codex-cli 0.147.0, and still reproduces: the feature name
is validated, so acceptance means something -- `--disable bogus-not-a-feature`
is refused with "Error: Unknown feature flag" both at the top level and on the
`codex exec review` path, while `memories` passes that check. Under the flag,
`codex --disable memories features list` reports `memories ... false`.

THE MACHINE DEFAULT DRIFTS, which is why the flag is on the command line
rather than left to machine state. Earlier on 2026-08-23 a bare
`codex features list` on this Mac reported `memories ... true`, so the flag
produced a visible true-to-false flip; by that evening the bare command
reported `false` on the same codex-cli 0.147.0, with no local override in
play (`~/.codex/config.toml`'s `[features]` holds only `js_repl = false`).
Pull request #150's round-2 reviewer bracketed the move to that afternoon:
a 14:14 session carries the memory block, four sessions between 15:46 and
15:51 do not. The cause was not established -- a config key, a CLI override
and persistence of `--disable` were each eliminated, and no explanation is
asserted here. So the flag today pins a state the machine may already be in;
what it guarantees is that the cell does not depend on which way the default
happens to be pointing.

Parent placement, beside --sandbox above; the nested `review` parser also
accepts --disable, but one placement for both flags is easier to read.

The scope of that guarantee is these three committed launchers, not the
machine. A seat that types `codex exec` by hand gets whatever the machine
default is at that moment: on 2026-08-20 that meant the memory block, and two
such sessions with cwd=/Users/el/agents/merge-lane were found carrying it. So
a review is memory-free because it went through one of these scripts, not
because it ran on this Mac.

EXIT CODES -- two layers produce them, and telling them apart is the point.
This wrapper must never spend, on its own refusals, a code that `codex exec`
also produces: otherwise "you invoked this wrapper wrongly" and "this
wrapper invoked codex wrongly" arrive as the same number, and the second is
a defect in this repository's code.

  0      codex ran and a report was written -- and NOTHING MORE. See WHAT
         EXIT 0 DOES NOT PROMISE below before gating on it.
  64     this wrapper refused the invocation and never launched codex: a
         --repo that is not a checkout, a --base/--commit that does not
         resolve, an --output that is not a regular file, or a command-line
         error argparse caught (missing or unknown option). 64 is
         sysexits.h's EX_USAGE, "command line usage error", and it is used
         here rather than the conventional 2 because it sits outside every
         band codex plausibly returns: clap pins its own usage errors at 2,
         codex's runtime failures at 1, a Rust panic is 101, a signal is
         128+N.
  1      the review failed and no report survives -- codex could not be
         launched or timed out, or codex exited 0 having written nothing.
         Either layer can produce it; the stderr line says which.
  other  codex exec's own exit code, passed through unchanged. A passed-
         through 2 specifically means CODEX REJECTED THE COMMAND THIS
         SCRIPT COMPOSED, which is a defect here rather than a caller's
         typo (measured on codex-cli 0.147.0, 2026-08-23: `codex exec
         --no-such-flag review` and `codex exec review --no-such-flag` both
         exit 2, while every non-parsing failure probed the same day --
         unknown feature name, missing working directory, `review` outside
         a git repository, an unusable model id, a rejected config
         override -- exits 1).

Once codex has been launched, every failure path deletes any report it may
have left behind, so from there a report file exists if and only if the run
succeeded: its absence is detectable, and must never be read as a clean
review. A 64 refusal is the one gap in that, and by construction: it happens
before the pre-run delete, so a stale report from an EARLIER run survives it
untouched. A caller reusing one --output path across runs therefore has to
read the exit code, not merely look for the file.

WHAT EXIT 0 DOES NOT PROMISE -- why a gate must read the report and never
this exit code. Two things, both measured rather than assumed:

  - Not the verdict. codex exits 0 while reporting defects (measured
    2026-08-19 on pull request #102's review), so a gate reading the exit
    code alone passes every change that was reviewed at all.
  - Not that a review happened. `codex exec review` exits 0 when it
    reviewed NOTHING, and says so only in the report body. Measured
    2026-08-23 on codex-cli 0.147.0, through this script:

        scripts/code-review-codex-cell.py --base HEAD --output R.md --repo .

    ran 20 seconds, exited 0, and wrote R.md -- provenance header and all
    -- holding one sentence: "HEAD equals the specified merge-base commit,
    and `git diff <sha>` is empty, so there are no changes to review."
    Every check this script makes passed: codex exited 0, a non-empty
    report exists. A caller whose base is wrong gets a stamped report of a
    review that never ran.

    Probed directly against codex the same day with a base that does not
    exist at all (`codex exec --sandbox read-only --disable memories review
    --base no-such-ref-xyz-123 -m gpt-5.6-sol ...`): 25 seconds, a real
    model call, a correct diagnosis -- "no merge base or diff could be
    produced" -- and exit 0. That route cannot arrive through this script,
    whose `git rev-parse --verify` refuses an unresolvable base before
    codex is launched; it is recorded because it shows the behavior belongs
    to codex and is not an artifact of the empty diff.

Usage:
  scripts/code-review-codex-cell.py --base <SHA> --output <FILE> [--repo DIR]
  scripts/code-review-codex-cell.py --commit <SHA> --output <FILE> [--repo DIR]
"""

import argparse
import pathlib
import subprocess
import sys

# One place to update as models change, matching md-review-codex-cell.py's
# good tier (user-picked 2026-08-03; xhigh "OK for codex" same date).
CODEX_MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "xhigh"
REVIEW_TIMEOUT_SECONDS = 1800

# This script's own refusals, kept off every code `codex exec` produces so a
# passed-through code stays readable as codex's. sysexits.h's EX_USAGE; the
# reasoning is in EXIT CODES above.
EXIT_BAD_INVOCATION = 64


class BadInvocationArgumentParser(argparse.ArgumentParser):
    """argparse's own command-line errors join EXIT_BAD_INVOCATION.

    argparse exits 2 on a missing or unknown option, and 2 is also what
    `codex exec` returns when IT rejects a command line -- so leaving the
    default in place would keep the two layers indistinguishable for the
    commonest bad invocation there is, a mistyped flag. Usage text and
    message are argparse's, unchanged; only the exit code moves.
    """

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_BAD_INVOCATION, f"{self.prog}: error: {message}\n")


def main(argv=None) -> int:
    parser = BadInvocationArgumentParser(
        description="Codex built-in code review over a git range, pinned and captured.",
        epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--base", help="review the diff from this SHA to the worktree's HEAD")
    scope.add_argument("--commit", help="review the changes introduced by this one commit")
    parser.add_argument("--output", required=True, help="file the final review report is written to")
    parser.add_argument("--repo", default=".", help="the checkout to review in (default: current directory)")
    parser.add_argument("--model", default=CODEX_MODEL, help="explicit Codex model id override")
    arguments = parser.parse_args(argv)

    repo = pathlib.Path(arguments.repo).resolve()
    if not (repo / ".git").exists():
        print(f"code-review-codex-cell: {repo} is not a checkout", file=sys.stderr)
        return EXIT_BAD_INVOCATION

    # The subject must be a resolved SHA, not a moving ref: record exactly
    # what was reviewed, so the report can be tied to it later.
    subject = arguments.base or arguments.commit
    resolved = subprocess.run(
        ["git", "rev-parse", "--verify", f"{subject}^{{commit}}"],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    if resolved.returncode != 0:
        print(f"code-review-codex-cell: {subject} does not resolve to a commit in {repo}",
              file=sys.stderr)
        return EXIT_BAD_INVOCATION
    subject_sha = resolved.stdout.strip()

    # Resolved, because codex runs with cwd=repo: a relative path would name
    # one file on the caller's side and a different one on codex's side, and
    # a stale caller-side file would then be stamped as this run's review.
    output_path = pathlib.Path(arguments.output).resolve()
    # --output names a file, and the delete below removes whatever already
    # sits there. os.unlink cannot remove a directory (IsADirectoryError on
    # Linux, PermissionError on macOS), so an --output that is a directory --
    # or any other non-regular file -- is a bad invocation, reported like the
    # --repo and --base/--commit ones above rather than thrown as a traceback.
    if output_path.exists() and not output_path.is_file():
        print(f"code-review-codex-cell: {output_path} exists and is not a regular file; "
              "--output names the file the report is written to", file=sys.stderr)
        return EXIT_BAD_INVOCATION
    # A pre-existing file at the output path must not survive into the
    # post-run checks: after this, a file that exists is provably this run's.
    output_path.unlink(missing_ok=True)
    scope_flag = ["--base", subject_sha] if arguments.base else ["--commit", subject_sha]
    command = [
        "codex", "exec",
        "--sandbox", "read-only",       # parent level; the nested parser rejects it
        "--disable", "memories",        # a naive cell, not one carrying earlier reviews
        "review",
        *scope_flag,
        "-m", arguments.model,
        "-c", f"model_reasoning_effort={REASONING_EFFORT}",
        "--output-last-message", str(output_path),
    ]
    try:
        # stderr is captured, not discarded: on failure its tail is the only
        # explanation anyone gets. On success it stays unprinted.
        completed = subprocess.run(
            command, cwd=repo, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            timeout=REVIEW_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        # A timeout can fire after codex has already written the file, so the
        # unlink belongs here too: every failure path leaves no report, which
        # is what lets absence be read as failure.
        output_path.unlink(missing_ok=True)
        print(f"code-review-codex-cell: codex could not run: {type(error).__name__}: {error}",
              file=sys.stderr)
        return 1

    def stderr_tail():
        lines = (completed.stderr or "").strip().splitlines()
        for line in lines[-10:]:
            print(f"  codex: {line}", file=sys.stderr)

    if completed.returncode != 0:
        # Codex may have written the report before dying; remove it so a
        # report file exists if and only if the run succeeded — an
        # existence-checking caller must never trust a partial report.
        output_path.unlink(missing_ok=True)
        print(f"code-review-codex-cell: codex exec review failed (exit {completed.returncode}); "
              "no report survives a failed run", file=sys.stderr)
        stderr_tail()
        return completed.returncode
    if not output_path.is_file() or not output_path.read_text(encoding="utf-8").strip():
        # A run that "succeeded" without a report is a silent absence, and
        # absence must never read as a clean review. An empty file is
        # removed for the same invariant: a report exists iff the run
        # succeeded.
        output_path.unlink(missing_ok=True)
        print("code-review-codex-cell: codex exited 0 but wrote no report; treat as failed",
              file=sys.stderr)
        stderr_tail()
        return 1

    # Provenance header, so a report read later is pinned to its inputs
    # (the md-review cells' convention, user-required 2026-08-04).
    report = output_path.read_text(encoding="utf-8")
    kind = "base" if arguments.base else "commit"
    output_path.write_text(
        f"<!-- provenance: runtime=codex-exec-review model={arguments.model} "
        f"effort={REASONING_EFFORT} {kind}={subject_sha} repo={repo} -->\n" + report,
        encoding="utf-8",
    )
    print(f"code-review-codex-cell: report written to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
