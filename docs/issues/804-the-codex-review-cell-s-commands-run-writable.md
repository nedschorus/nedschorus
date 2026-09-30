---
issue: "[The Codex review cell's commands run writable and without credential denials, because `codex exec review` drops the cell's permission profile](https://github.com/nedschorus/nedschorus/issues/804)"
---

# The Codex review cell's commands run writable and without credential denials, because `codex exec review` drops the cell's permission profile

Agent-filed by merge-lane-2 on 2026-09-30, from a reproduced finding. The reproduction is first; what it causes, what is not yet known, the workaround in use and the next action follow it.

## Reproduction

Measured on ned-box with codex-cli 0.156.0, on main at `805c0936`, on 2026-09-30.

`scripts/code-review-codex-cell.py` runs `codex exec` with the permission profile `code-review-no-credentials`. That profile extends `:read-only` and denies every credential path. It is built by `codex_credential_denying_permission_profile_arguments` in `nc-systems/cold-read/cold-read-cell-common.py`. Then it runs `review`. Each command the reviewing model runs goes through a `codex-linux-sandbox` child, whose `--permission-profile` argument is the policy that command actually gets.

1. **The review's commands get a different profile.** While the cell ran over PR [Every git the locator runs ignores a caller's GIT_COMMON_DIR](https://github.com/nedschorus/nedschorus/pull/802) at its head, at 2026-09-30T01:37:28Z:
   - The parent `codex exec` carried `default_permissions="code-review-no-credentials"`, `extends=":read-only"`, and a filesystem table of seven `"deny"` entries, read from `/proc/<pid>/cmdline`.
   - Its `codex-linux-sandbox` child carried this `--permission-profile`, in full: root `read`; the reviewed checkout `write`; `slash_tmp` `write`; `tmpdir` `write`; the checkout's `.git`, `.agents` and `.codex` `read`; network `restricted`. It has no deny entry.
   - Its `bwrap` child ran `--bind /tmp /tmp` and then `--tmpfs /tmp/.git`, which mounts over a path it first creates on the real disk.
   - The same profile shape appeared on the run over PR [The older lost-file tool's deletion stamp is read at the top level too](https://github.com/nedschorus/nedschorus/pull/803), at 01:31:26Z.
2. **The same arguments under `codex sandbox` get the profile.** A scratch HOME held two canary credentials, `.config/nedschorus/canary.token` and `.ssh/id_canary`, and CODEX_HOME was a scratch directory. The builder's output for `code-review-no-credentials` extending `:read-only` was passed to `codex sandbox`, with `-P code-review-no-credentials`, running `sleep 3`, a `cat` of each canary, and a `touch` under `/tmp`:
   - The child's `--permission-profile` held both deny entries and root `read`, and nothing writable.
   - Both canaries returned `Permission denied`.
   - The `touch` returned `Read-only file system`.
   - No `/tmp/.git`, `/tmp/.codex` or `/tmp/.agents` appeared.
3. **The same arguments under plain `codex exec` get the profile, with no `-P`.** `codex exec` takes no `-P`, and the cell passes none. The same builder output, for `code-review-no-credentials` extending `:read-only`, went to `codex exec --disable memories`, without `review`, in a scratch repository, with a prompt asking for one command, `sleep 6; touch /tmp/code-review-exec-control-probe`:
   - The child's `--permission-profile` held all seven deny entries, root `read` and `minimal` `read`, and nothing writable.
   - The probe file was not written.
   - The only difference from the cell's invocation is the `review` subcommand and its arguments.

To see step 1 again, run the cell over any pull request, and read the sandbox child's profile while a review command runs:

```sh
python3 scripts/code-review-codex-cell.py --base <merge base> --repo <detached worktree at the head> --output <report file>
# in a second shell, started before or while it runs; a sandbox child can live for under a second, so this waits for one.
# The brackets keep pgrep from matching a shell whose own command line holds this text, as an agent's `bash -c` does.
until pid=$(pgrep -n -f '[c]odex-linux-sandbox'); do sleep 0.1; done
tr '\0' '\n' < "/proc/$pid/cmdline" | grep -A1 -- '--permission-profile'
```

## What it causes

- **`/tmp/.git` exists while a review command runs, and the guard in `.claude/hooks/instruction-file-guard.py` treats `/tmp` as the root of a checkout, so it judges every path under `/tmp` to be inside that checkout.** `/tmp/.codex` and `/tmp/.agents` appear with it; only `/tmp/.git` matters to the guard. `enclosing_repository_root` (`.claude/hooks/instruction-file-guard.py:141`) returns the nearest ancestor whose `.git` exists, and an empty directory counts. On 2026-09-30, main's full test run at `a5bd5941` failed exactly one suite, `.claude/hooks/instruction-file-guard-test.py`. The four failing cases were "a one-off prompt outside any checkout passes", "no-checkout session falls back to the target's repository marker", "the fallback marker is consumed" and "a notebook write under .claude/ is blocked through notebook_path". After `/tmp/.git`, `/tmp/.codex` and `/tmp/.agents`, all three empty, were removed, the same suite passed every case. The directories last as long as the command: 0.23 s for a short one, 18 s for one at 01:37:28Z. Any seat's guard check, or any guard test, that runs in that window sees the wrong root.
- **The reviewing model's commands can read credential files.** The deny entries the cell passes are not in the profile its commands run under. PR [The sanity check's Codex cells and the Codex code reviewer never open a credential file](https://github.com/nedschorus/nedschorus/pull/795) added them; the cell's docstring cites the user's ruling for it (2026-09-29, "y" to item 8 of the walk what-a-cold-read-reviewer-may-read-2026-09-28, whose record is `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/what-a-cold-read-reviewer-may-read-2026-09-28.md`). The merge review's re-run check on that PR measured `codex sandbox`, not `codex exec review`, so it did not reach this path.
- **The reviewed checkout and `/tmp` are writable**, where the cell's docstring says the review is read-only. The docstring says that placing the sandbox at the parent level was verified on codex-cli 0.147.0; ned-box now runs 0.156.0.

The cold-read Codex cell is not affected in the same way. It extends `:workspace` and makes `/tmp` read-only on Linux, after this seat's review 5346166603 (2026-09-29) on PR [Cold-read reviewers never open a credential file, and each launcher enforces it](https://github.com/nedschorus/nedschorus/pull/765) found the same `/tmp/.git` from that cell. `codex exec` without `review` applied that profile, as measured then and recorded in `nc-systems/cold-read/cold-read-codex-cell.py`'s docstring.

## Not yet known

- **Why `review` drops the profile.** Steps 1 and 3 differ only by the `review` subcommand. Whether `review` runs its commands under the machine's default sandbox configuration, or under a policy of its own, has not been measured.
- **Why the directories were left behind once.** At 2026-09-30T00:42:06Z the three directories appeared during a Codex review cell run over PR [The grid test compares against frozen_target_path() instead of rebuilding the path](https://github.com/nedschorus/nedschorus/pull/801). They were still present at 00:50:48Z, when no Codex process was running, until merge-lane-2 removed them. Every other appearance measured so far was gone within a minute: the five a watcher timed, between 01:31Z and 01:38Z, lasted from 0.23 s to 18 s, and one at 00:16:24Z was gone within 50 s. The leftover has been seen once and is not reproduced.

## Workaround in use

- merge-lane-2 does not run the Codex review cell on a pull request that touches a credential path, as before PR 795.
- On other pull requests, the seat's review subagent runs the Codex cell only after its full test run has finished, so the directories' brief appearances cannot land inside that run.
- When the directories are left behind, as at 00:42Z, this seat removes them with `rmdir /tmp/.git /tmp/.codex /tmp/.agents`, which removes only empty directories.
- Nothing protects other seats on ned-box: a guard check any seat makes while a review command runs can still misjudge a path under `/tmp`.

## Next action

None on this issue: it closes as completed once this edit merges. Its build is done (see Outcome). A follow-up pull request from cold-read-research fixes the three non-blocking findings that PR 809's review left on the cell's re-check recipes. Whether `enclosing_repository_root` should skip a `.git` directory with no entries in it is a question waiting on the user, kept on cold-read-research's task list.

## Outcome

Fixed on 2026-09-30 by PR [The Codex review cell's commands run under its credential-denying profile](https://github.com/nedschorus/nedschorus/pull/809), merged at `0b62d776`.

- **Cause: argument order.** `codex exec review` runs the review in a child thread, and every command the reviewing model runs belongs to that thread. On codex-cli 0.156.0 the child drops a permission profile placed before `review`. It then runs under the default the checkout gets without one:
  - `:workspace` for a project Codex trusts, on ned-box;
  - `:read-only` for one it does not, on ned-box;
  - workspace-write on the Mac, from its config's `sandbox_mode`.

  The same profile, passed as the builder's `-c` configuration overrides but placed after `review`, does reach the child. `review`'s own parser rejects `--sandbox`, and `-p`, the config-profile flag of `codex exec`.
- **Fix.** `scripts/code-review-codex-cell.py` now places the builder's profile overrides after `review`. The shared builder in `nc-systems/cold-read/cold-read-cell-common.py` is unchanged. The cell's docstring says where the profile goes and how to re-check it after a Codex upgrade.
- **Measured, both machines, codex-cli 0.156.0.** Each run had a scratch HOME holding canary credentials. With the profile before `review`, the reviewer read both canaries and wrote under `/tmp` and in the checkout. With it after `review`:
  - both reads and both writes were refused;
  - no `/tmp/.git` appeared;
  - the review still wrote its report.

  merge-lane-2 then ran the `/proc` capture twice on the merged head, over a scratch repository on ned-box. Every `codex-linux-sandbox` child of the review held the builder's seven deny entries, root `read` and no `write` entry, and `/tmp/.git` never appeared.
- **Not yet known, now moot.** Why the directories were once left behind was not investigated. With the profile after `review`, the review's commands no longer create them.
- **Workaround.** Skipping the Codex review cell on pull requests that touch a credential path is no longer needed.
- **Not built.** The second guard, `enclosing_repository_root` skipping an empty `.git`, is a question for the user. It is on cold-read-research's task list, not in this issue.
