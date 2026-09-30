#!/usr/bin/env python3
r"""Run Codex's built-in code review over a git range, pinned and captured.

One cell of merge-lane's review: `codex exec review` is Codex's own
diff reviewer (finding rubric, P0-P3 priorities, changed-line locations).
This wrapper exists so invoking it is a committed, reviewable program
rather than a shell line in one seat's transcript, and so the pins that
must not drift are pinned:

  - model and reasoning effort, explicit (the tier convention of
    nc-systems/cold-read/cold-read-codex-cell.py: `deep` = gpt-6-sol at xhigh);
  - the sandbox, read-only and denying every credential file, placed AFTER
    `review`, because the review's commands drop a profile placed before it
    -- see WHERE THE PERMISSION PROFILE GOES below, which also says how to
    re-check it after a Codex upgrade. It is a permission profile extending
    Codex's `:read-only`, not `--sandbox read-only`, because the profile
    also denies every credential file (user-ruled 2026-09-29, item 8 of the
    walk what-a-cold-read-reviewer-may-read-2026-09-28, "y"); Codex refuses
    the two together. The profile comes from the builder the cold-read Codex
    cell uses, codex_credential_denying_permission_profile_arguments in
    nc-systems/cold-read/cold-read-cell-common.py;
  - the base, as a SHA the caller resolved -- `--base origin/main` drifts
    under a moving remote, so the review's subject is recorded exactly;
  - the output, captured to a file the caller names;
  - Codex's own memory store, OFF for this process (`--disable memories`) --
    see WHY THE CODEX MEMORY STORE IS OFF FOR REVIEW CELLS below.

What this deliberately does not do: accept custom review instructions.
On codex-cli 0.147.0 a [PROMPT] is mutually exclusive with --base and
switches to custom-review mode, losing the built-in rubric (measured
2026-08-19). Durable repository review rules belong in CLAUDE.md, the
single rules home both runtimes read: Codex reaches it through AGENTS.md,
which is a pointer at CLAUDE.md rather than a second home; merge-decision
checks belong to the deferred pr-merge-decision component
(nedschorus#105).

WHERE THE PERMISSION PROFILE GOES, AND HOW TO RE-CHECK IT AFTER A CODEX
UPGRADE. `codex exec review` runs the review in a child thread, and every
command the reviewing model runs belongs to that thread. On codex-cli
0.156.0 the child drops a permission profile placed before `review`. The
parser accepts it there, and the child runs under the default the checkout
would get without it: on ned-box `:workspace` for a project Codex trusts,
which makes the checkout, /tmp and $TMPDIR writable, and `:read-only` for
one it does not; on the Mac, whose Codex config sets `sandbox_mode =
"workspace-write"`, workspace-write. None of them denies a credential file.
The same `-c` overrides placed after `review` reach the child. `review`'s
own parser takes `-c` and rejects `--sandbox` and `-p` (exit 2, both
machines). Until 2026-09-30 this docstring said the parent placement was
verified on codex-cli 0.147.0; that established only that the parser
accepted it.

Measured 2026-09-30 on codex-cli 0.156.0, on both machines, for GHI 804
("The Codex review cell's commands run writable and without credential
denials, because `codex exec review` drops the cell's permission profile",
docs/issues/804-the-codex-review-cell-s-commands-run-writable.md). Each run
had a scratch HOME holding two canary credentials,
`.config/nedschorus/canary.token` and `.ssh/id_canary`, and a scratch
CODEX_HOME whose config.toml trusted the scratch repository and, on the
Mac, also carried the Mac config's `sandbox_mode = "workspace-write"` and
`approval_policy = "never"`. Each ran this cell's command as a built-in
review of one commit in a scratch repository whose AGENTS.md told the
reviewer to `cat` both canaries and `touch` a file under /tmp and one in
the checkout:

  - Profile before `review`: the reviewer read both canaries and wrote
    both files, on both machines. On ned-box the `--permission-profile` of
    its `codex-linux-sandbox` child held root `read`; the checkout,
    `slash_tmp` and `tmpdir` `write`; and no deny entry. /tmp/.git,
    /tmp/.codex and /tmp/.agents appeared while its commands ran.
  - Profile after `review`: both reads and both writes were refused
    ("Permission denied" and "Read-only file system" on ned-box, "Operation
    not permitted" on the Mac), nothing appeared under /tmp, and the review
    still wrote its report. The child's `--permission-profile` held a deny
    entry for each credential path, root `read`, and nothing writable.

One other parent-level override was measured, and it does reach the
child: on ned-box, `-c model_reasoning_effort=high` placed before `review`
became the child's effort. `--disable memories` stays at the parent level
on the strength of that one measurement; whether the memories switch itself
reaches the child has not been measured.

To re-check on ned-box, read the `--permission-profile` of every
`codex-linux-sandbox` child of this run while it runs. Pick the children by
ancestry, not by `pgrep -n`, which takes the newest one on the whole
machine: another Codex run -- a cold-read Codex cell, or the sanity check's
attacks, both `:workspace` -- often overlaps a review on ned-box, and its
child carries "write" entries. Nor by `--command-cwd`: the review's own
children can run with `--command-cwd /`. Keep only the outer stage, whose
ancestry reaches the cell with no `bwrap` or `codex-linux-sandbox` in
between: each child execs `bwrap`, which starts a second
`codex-linux-sandbox` inside the sandbox, and the reviewing model can run
`codex-linux-sandbox` itself, with any profile it likes, as it did
unprompted in two of three runs on a diff that named it. And poll fast: a
child keeps the name `codex-linux-sandbox` only until it execs `bwrap`,
about 15 ms, and a shell loop that ran one `ps` per ancestor per poll
caught none of a review's children while another Codex run was live (both
measured on ned-box, 2026-09-30). So a Python loop reads /proc in one
pass, with no subprocess, about 5 ms per pass and 5 ms apart, keeps each
outer child it catches, and takes the flag's value from the child's own
argv, before the `--` that starts the command, which can itself contain
the flag's name:

    python3 scripts/code-review-codex-cell.py --base <merge base> --repo <detached worktree at the head> --output <report file> &
    python3 -c 'if 1:
        import os, sys, time
        cell = sys.argv[1]
        def read(path):
            try:
                with open(path, "rb") as f: return f.read()
            except OSError: return b""
        def name(pid): return os.path.basename(read(f"/proc/{pid}/cmdline").split(b"\0")[0])
        def stat(pid):  # the fields after the command name: state, ppid, ...
            return read(f"/proc/{pid}/stat").rpartition(b")")[2].split()
        def parent(pid): return (stat(pid)[1:2] or [b""])[0].decode()
        seen, profiles = set(), set()
        while stat(cell) and stat(cell)[0] != b"Z":
            for pid in filter(str.isdigit, os.listdir("/proc")):
                argv = read(f"/proc/{pid}/cmdline").split(b"\0")
                if pid in seen or os.path.basename(argv[0]) != b"codex-linux-sandbox": continue
                p, nested = parent(pid), False
                while p not in ("", "0", "1", cell):
                    nested = nested or name(p) in (b"bwrap", b"codex-linux-sandbox")
                    p = parent(p)
                if p != cell or nested: continue
                seen.add(pid)
                flags = argv[:argv.index(b"--")] if b"--" in argv else argv
                i = flags.index(b"--permission-profile") + 1 if b"--permission-profile" in flags else 0
                profiles.add(flags[i].decode() if 0 < i < len(flags) else "(no --permission-profile)")
            time.sleep(0.005)
        print("sandbox children of this run:", len(seen))
        for profile in sorted(profiles): print(profile)' "$!"

Each profile it prints must hold a "deny" entry for each credential path
the builder lists, root "read", and no "write" entry. One or two shapes
appear during one review, the second also carrying `minimal` `read`; each is
this cell's profile. A "write" entry, no "deny" entry, or "(no
--permission-profile)" means the child has dropped the profile again. The
count should not be 0: in each of those three runs, 16 children started
before the model ran any command. A count of 0 means the capture missed
them; run it again.

To re-check on either machine, the Mac included, which has no /proc: the
child thread records the profile it ran under in its session file. A run
leaves two rollouts under `$CODEX_HOME/sessions/` (default
~/.codex/sessions/), and only the child's has a `turn_context` record,
whose `cwd` is the reviewed checkout. Every Codex run on the machine shares
that directory, and overlapping runs are common, so pick the rollout by
that `cwd` and by the run's start, not by recency:

    repo=$(cd <detached worktree at the head> && pwd -P); started=$(mktemp)
    python3 scripts/code-review-codex-cell.py --base <merge base> --repo "$repo" --output <report file>
    find "${CODEX_HOME:-$HOME/.codex}/sessions" -name 'rollout-*.jsonl' -newer "$started" -exec grep -h '"type":"turn_context"' {} + \
      | grep -F "\"cwd\":\"$repo\"" | grep -o '"active_permission_profile":{[^}]*}' | sed 's/^"active_permission_profile"://' | sort -u

It must print `{"id":"code-review-no-credentials","extends":":read-only"}`,
and nothing else.
With the profile before `review` it printed `{"id":":workspace"}` on
ned-box, and nothing on the Mac, whose child recorded a workspace-write
`sandbox_policy` instead.

WHY THE CODEX MEMORY STORE IS OFF FOR REVIEW CELLS -- the one explanation
for every `codex exec` this repository launches; the other two sites
(nc-systems/cold-read/cold-read-codex-cell.py, scripts/sanity-check-attacks.py) pass the
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

Parent placement. The nested `review` parser also accepts --disable. The
parent placement is kept because the one other parent-level override
measured, `model_reasoning_effort`, does reach the review's child thread;
whether this switch does has not been measured (WHERE THE PERMISSION
PROFILE GOES, above).

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
         codex's runtime failures at 1, a Rust panic is 101, and a codex
         killed by a signal surfaces from this program in the 192-255 band
         (see the row below). 64 is outside all four.
  1      the review failed and no report survives -- codex could not be
         launched or timed out, or codex exited 0 having written nothing.
         Either layer can produce it; the stderr line says which.
  other  codex exec's own exit code. A passed-through 2 specifically means
         CODEX REJECTED THE COMMAND THIS SCRIPT COMPOSED, which is a defect
         here rather than a caller's typo (measured on codex-cli 0.147.0,
         2026-08-23: `codex exec --no-such-flag review` and `codex exec
         review --no-such-flag` both exit 2, while every non-parsing failure
         probed the same day -- unknown feature name, missing working
         directory, `review` outside a git repository, an unusable model id,
         a rejected config override -- exits 1).

         UNCHANGED FOR AN ORDINARY EXIT, TRANSFORMED FOR A SIGNAL, and the
         difference is worth knowing before you match on a number. Python
         reports a signal death as a NEGATIVE returncode (-9 for SIGKILL),
         and this program hands that straight to sys.exit, which takes it
         modulo 256. So a codex killed by SIGKILL leaves this program with
         247, and SIGTERM with 241 -- not the 137/143 a shell would report
         for the same deaths. Measured, not derived. Nothing here needs the
         distinction today: both land in 192-255, well clear of 64, 1 and 2,
         so every code this program spends stays unambiguous. It is written
         down because "passed through unchanged" read as a promise that the
         number a caller sees is the number a shell would show, and for a
         signal it is not.

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
import importlib.util
import pathlib
import subprocess
import sys

_common_spec = importlib.util.spec_from_file_location(
    "cold_read_cell_common",
    pathlib.Path(__file__).resolve().parent.parent
    / "nc-systems" / "cold-read" / "cold-read-cell-common.py")
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)

# The reviewer's permission profile, as it appears in its session.
CREDENTIAL_DENYING_PERMISSION_PROFILE = "code-review-no-credentials"

# One place to update as models change, matching cold-read-codex-cell.py's
# `deep` tier (user-picked 2026-08-03; xhigh "OK for codex" same date;
# moved from gpt-5.6-sol to gpt-6-sol 2026-09-22 along with that tier).
CODEX_MODEL = "gpt-6-sol"
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
        "--disable", "memories",        # a naive cell, not one carrying earlier reviews
        "review",
        # Read-only and no credential file, AFTER `review`: the review's
        # commands run in a child thread that drops a profile placed before
        # it. See WHERE THE PERMISSION PROFILE GOES in the docstring.
        *common.codex_credential_denying_permission_profile_arguments(
            CREDENTIAL_DENYING_PERMISSION_PROFILE, ":read-only"),
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
    # (the cold-read cells' convention, user-required 2026-08-04).
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
