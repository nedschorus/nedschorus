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

Codex keeps a memory store under `~/.codex/` that every Codex process on the
machine shares. It reads accumulated notes into a new session, and its memory
pipeline writes fresh ones from saved sessions. Both directions are wrong for
a review cell:

  - READING. A cell is commissioned to be naive -- to judge the change in
    front of it, not to carry forward what Codex concluded reviewing this
    project before. On 2026-08-23 that store held a task group named
    "NedsChorus NC toolchain / constrained adversarial review and Phase-1
    phasing checks", with sections "Reusable knowledge" and "Failures and how
    to do differently": Codex's own standing conclusions about this
    repository's work, which a fresh cell would inherit.
  - WRITING. These cells are automation; the store is the user's personal
    one, kept for his interactive Codex. Automated review runs should not be
    depositing findings in it.

`--disable memories` is per-invocation. `codex exec --help` on codex-cli
0.147.0 documents it as "Disable a feature (repeatable). Equivalent to `-c
features.<name>=false`" -- a config override for this process only, writing
nothing to disk and leaving the user's own interactive Codex untouched.
Verified on codex-cli 0.147.0 (2026-08-23): `codex features list` reports
`memories ... true`, `codex --disable memories features list` reports it
`false`, and on the exec path an unknown name is refused ("Error: Unknown
feature flag") while `memories` passes that check. Parent placement, beside
--sandbox above; the nested `review` parser also accepts --disable, but one
placement for both flags is easier to read.

Exit codes: 0 the review ran and wrote the report -- WHICH SAYS NOTHING
ABOUT THE VERDICT: codex exits 0 while reporting defects, so a gate must
read the report, never this exit code (measured 2026-08-19, PR #102's
review). 2 bad invocation. Anything else is codex exec's own failure,
passed through -- and a failed run writes no report, so absence of the
report file is detectable and must never be read as a clean review.

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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
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
        return 2

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
        return 2
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
        return 2
    # A pre-existing file at the output path must not survive into the
    # post-run checks: after this, a file that exists is provably this run's.
    output_path.unlink(missing_ok=True)
    scope_flag = ["--base", subject_sha] if arguments.base else ["--commit", subject_sha]
    command = [
        "codex", "exec",
        "--sandbox", "read-only",       # parent level; the nested parser rejects it
        "--disable", "memories",        # naive cell, and no writes to the shared store
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
