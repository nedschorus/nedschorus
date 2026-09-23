# Test plan: scripts/merge-gate.sh

Step 2 of the user's ruled build order for task "Bring merge-gate.sh into the
repository" (ruled 2026-08-31): 1 code review first, 2 this test plan against the
cleaned code, 3 update the code if the plan reveals problems, 4 write and run the
tests, 5 update until they pass, 6 only then open the pull request. His reason for
the order: otherwise "you start patching in changing bug by bug (and the resultant
horrible code that generates)."

Suite destination `scripts/merge-gate-test.py`, beside the program it tests, per
the Test row of
[docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md](file:///Users/el/agents/merge-lane-backlog/docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md).

**Where the code under test is.** `scripts/merge-gate.sh` is NOT on main yet; that
is what this build produces. The cleaned program sits on the local branch
`merge-gate-enters-the-repository`. The pre-repository copy every demonstrated
finding was measured against is
`/Users/el/agents/merge-lane/walk-ledgers/merge-gate.sh`, 68 lines, 4183 bytes,
sha256 c348b3c1d67f2a2aeba81c4134a50d509d1c9fbdd3b720405604c1142bb15993, byte
identical to `/home/nedlern/agents/merge-lane-2/walk-ledgers/merge-gate.sh` on
ned-box. Both live in gitignored directories, which is why this build exists.

## What the program is, for a reader who has not seen it

`scripts/merge-gate.sh <pr-number> <expected-head-sha> <reviewed-since-iso8601>`
is run before every merge to main. It exits 0 only if the pull request is
approved, not a draft, in a mergeable state, at the head the caller believes was
reviewed, and carrying no channel activity the caller has not read. Any other
outcome is non-zero with a named reason on stderr.

Its value is entirely in its exit code, so every case below asserts the exit code
first and the message second.

## The two rules this plan is written against

**Oracle and red condition, for every check.** Each case states what is measured
and which reading means fail. A check whose red condition cannot occur proves
nothing. (Rider 1, `docs/issues/18-write-test-plan-riders-and-test-evidence-rules.md`.)

**Fixtures are captured, never typed.** Every fixture representing GitHub's
output is generated from a real API call, with the capture command and the machine
recorded beside it. A stand-in whose answers were typed, copied or inferred from
the code under test proves nothing, because it agrees with the code by
construction. This matters more here than usual: the whole defect class being
fixed — page size, oldest-first ordering, the presence of `updated_at`, the exact
timestamp spelling — is a property of the real API, and a hand-typed fixture would
encode the author's belief about it rather than its behaviour.

## How the stand-in works

The suite puts a `gh` shim earlier on PATH than the real one. The shim matches on
its argument list and prints the captured fixture for that endpoint, exits 0, and
exits non-zero for any call the case did not arrange. HOME is redirected so the
token read hits a fixture file, never the real credential. No case touches GitHub.

Per the 2026-09-16 ruling, running against a stand-in counts as executing the
path, and that evidence is enough to ship; a production problem then becomes an
issue and a fix.

## Fixture capture, to be done before any case is written

All captures are read-only `gh api` calls. Record each command and the machine in
a capture note beside the fixtures.

| Fixture | Captured from | Why this source |
|---|---|---|
| A pull request's `--json headRefOid,mergeStateStatus,reviewDecision,isDraft` | a real merged pull request in this repository | the exact field spelling and value vocabulary |
| A review channel with an APPROVED review | the same | `commit_id`, `submitted_at`, `user.login`, `id` shapes |
| An inline comment carrying `updated_at` later than `created_at` | a real edited comment, located by querying for one | F6's oracle; a typed fixture would beg the question |
| A channel of more than 30 items, to prove paging | see below | F1's regression case |

**The pagination fixture has no source in this repository, which the plan must
state rather than hide.** Measured 2026-09-22 across thirteen pull requests here:
the largest inline channel is 22, the largest review channel 11, the largest issue
channel 2. Nothing reaches 30. So the >30 fixture comes from one of:

1. a public repository's pull request whose channel exceeds 30, captured
   read-only — this proves what the real API does and is preferred; or
2. the organisation's own probe repository, `nedschorus/ghi-api-probes` — private,
   named in the main-gatekeeper design's credential section as the organisation's
   second repository — which exists for exactly this, with a note saying the
   fixture is a sandbox capture and therefore proves what the sandbox does.

Option 2 requires more than thirty writes under the user's GitHub account and is
NOT taken without his word. If option 1 yields no suitable channel, the pagination
case is reported as un-captured rather than typed, and the plan says so.

## Cases

Exit codes: 0 pass, 1 the gate refuses, 2 the gate could not run. The distinction
exists because this fleet's near-miss shape is a gate that could not run being
read as a gate that passed. A malformed argument is 2, not 1: the gate never
reached a judgement.

**The comparison is strictly greater than SINCE, and GitHub's timestamps carry
whole seconds.** An item stamped exactly SINCE is therefore NOT counted as new.
That is deliberate — SINCE is normally copied from the approving review's own
`submitted_at`, and counting that review's own second would refuse every merge it
authorises. E10 below pins the boundary so a later change cannot move it silently.

### A. The pass case

| # | Case | Oracle | Red condition |
|---|---|---|---|
| A1 | Everything in order | exit code, and stdout's pinned merge command | exit non-zero, or the printed `--match-head-commit` sha is not the approving review's `commit_id` |

A1 is the control. If it ever fails, every refusal case below is meaningless,
because a suite where nothing can pass proves only that the program refuses.

### B. The seven demonstrated false passes — each must now refuse

These are the regression cases. Each was demonstrated against the pre-repository
copy by an independent reviewer on 2026-09-22 under a stubbed `gh`.

| # | Finding | Arrangement | Oracle | Red condition |
|---|---|---|---|---|
| B1 | F1, no pagination | a channel of >30 items with a new comment beyond the 30th | exit code | exit 0 — the gate passed while unread activity existed. THIS CASE CANNOT PASS WITHOUT `--paginate`, which is what makes it a regression test rather than decoration |
| B2 | F1, the pin truncated | an APPROVED review at index 32 | exit code and message | exit 1 saying "no APPROVED review found" — a false REFUSAL naming the wrong cause |
| B3 | F2, SINCE unbounded | SINCE later than the approving review's `submitted_at` | exit code | exit 0 — "since now" made all three activity checks no-ops |
| B4 | F3, offset timestamp | SINCE in a valid RFC 3339 spelling carrying a positive offset | exit code | exit 0, which is what the string comparison produced. The cleaned code refuses the format before any channel is read, so the assertion is **exit 2** with the format reason — the same class as D2 and D3, because a malformed argument means the gate could not run, not that it judged and refused. A deliberate false refusal, cheap to correct at the call site |
| B5 | WITHDRAWN with F4 | F4 was ruled out by the user 2026-09-23; the two live-chain cases replace this row (see "Built 2026-09-23") | — | — |
| B6 | F5, merge account's later findings | a COMMENTED review by the merge account after SINCE | exit code | exit 0 — that account's findings were excluded unconditionally and read by nobody |
| B7 | F6, edited comment | a comment created before SINCE and edited after it to add a finding | exit code | exit 0 — `created_at` alone missed it |

F7, `UNSTABLE` on the merge-state allow-list, is deliberately NOT given a case.
It was never demonstrated as a false pass and may be intended. Changing it is the
user's ruling, not this rebuild's. Recorded here so the next reader knows it was
seen and left.

### C. The credential path

| # | Case | Oracle | Red condition |
|---|---|---|---|
| C1 | Token file missing | exit code and message | exit 0 or 1. Must be 2: `export GH_TOKEN=$(cat …)` returned export's status, swallowing cat's failure; GH_TOKEN was then empty, which gh treats as unset, falling back to the stored credential — on this Mac the account that AUTHORS these pull requests |
| C2 | Token file empty | exit code | anything but 2 |

### D. False refusals that named the wrong cause

Each was demonstrated. The oracle is the MESSAGE, not just the code: a refusal
that names the wrong cause sends a reader to fix something that is not broken.

| # | Case | Oracle | Red condition |
|---|---|---|---|
| D1 | `jq` absent from PATH | exit code and message | a refusal saying "head moved" — jq missing made `head` empty and the comparison failed. Must be 2, naming jq |
| D2 | Abbreviated EXPECTED | message | a refusal saying "head moved": the head had not moved, the caller passed a short sha. Must be 2, naming the format |
| D3 | EXPECTED not hex | message | anything naming a move rather than a format |

### E. The refusal paths that were already correct

Written because the rebuild must not break them, and because each has a real red
condition.

| # | Case | Oracle | Red condition |
|---|---|---|---|
| E1 | No approving review at all | exit code | exit 0 |
| E2 | Head moved from EXPECTED | exit code and both shas in the message | exit 0, or a message naming only one sha |
| E3 | Approval covers a sha that is not the head | exit code | exit 0 — this is the pin's whole purpose |
| E4 | Draft pull request | exit code | exit 0 |
| E5 | reviewDecision not APPROVED | exit code | exit 0 |
| E6 | mergeStateStatus DIRTY | exit code | exit 0 |
| E7 | New inline comment since SINCE | exit code and count | exit 0, or a count that is not the number arranged |
| E8 | New issue comment since SINCE | exit code and count | exit 0, or a wrong count |
| E9 | `gh` exits non-zero, a rate limit or an HTTP 5xx | exit code | exit 0 — must fail closed |
| E10 | An item stamped EXACTLY SINCE | exit code | exit 1. The boundary is strictly greater-than; an item at the same second as SINCE is not new activity, and counting it would refuse every merge the approval authorises |

### F. The three cases the review named as ones nobody would otherwise write

| # | Case | Oracle | Red condition |
|---|---|---|---|
| F-a | A refusal cannot be swallowed by a wrapper | the exit code observed by a caller that invokes the gate the way the merge lane does | the wrapper exits 0 while the gate inside exited non-zero. Drawn from a real near-miss on 2026-09-22: a three-interpreter sweep whose WRAPPER exited 0 while every sweep inside exited 3, because a stale lock was held by a dead pid, caught only because inner exit codes were printed |
| F-b | `mergeable` has three values and UNKNOWN is common | — **NO CASE IS WRITTEN TODAY.** The gate reads `mergeStateStatus`, not `mergeable`, so there is no code path to test. This row is a standing note for whoever adds such a check later: it must poll past UNKNOWN. Measured 2026-09-22: eight of nine open pull requests read UNKNOWN, one genuinely conflicting by `git merge-tree` | — |
| F-c | Pagination | B1 above is this case | — |

## Mutation check on the suite itself

Rider 1 turned on the harness: a suite that cannot report a failure it would
detect proves nothing. After the cases pass, mutate the cleaned program once per
fix — remove `--paginate`, remove the SINCE bound, restore the unconditional
merge-account exclusion, drop `updated_at` — and confirm the matching case goes
red by name.

Three rules the project learned on 2026-09-21 and this run must follow:

- **Commit the change before mutating it.** `git checkout --` restores a file as
  of the last commit, so mutating uncommitted work discards the fix with the
  mutation and every mutation after the first measures pristine code.
- **Assert the mutation applied.** A replacement that silently matches nothing
  produces the same clean green as a guard that failed to fire.
- **Run an unmutated control after the mutations, not only before,** and state its
  count. A control at the end proves the tree was restored.

## What this plan does not cover, said plainly

- No case runs against the real GitHub API. Every case is a stand-in run, which
  the 2026-09-16 ruling accepts as evidence to ship.
- The pagination fixture's source is unresolved until a capture is attempted; the
  plan refuses to let it be typed. **If no capture can be made**, B1 and B2 do not
  silently vanish: the suite emits a visible SKIP line naming the missing fixture
  and the whole run reports that the worst finding's regression test did not run.
  The project's idiom for this is the visible SKIP in `scripts/clean-worktrees-test.py`.
  A suite that quietly omits its most important case is the failure this whole
  rebuild exists to stop.
- F7 is untested by decision, not by oversight.

## Built 2026-09-23: what changed against this plan

- **The pagination fixtures were captured, read-only, from public repositories.**
  pytorch/pytorch pull request 114309 has 54 inline comments, 53 issue comments
  and 51 reviews; 190902 has 42 reviews, with the head's approval at index 41 and
  an older one at 23. Each is stored as gh printed it with `--paginate`, and again
  without, so the stand-in serves what gh serves in each case. No write to any
  repository was made, and `ghi-api-probes` was not used.
- **B2's capture differs from the plan's wording.** The first page of 190902 holds
  an older approval of another commit rather than no approval, so the unpaginated
  gate would pin the wrong commit rather than report no approval. The case
  asserts the pin is the head's approval.
- **E8 is B1's issue-channel case,** which asserts the exact count.
- **F4 was withdrawn.** The merge lane's chain on ned-box posts its own approval
  as `ned-review-merge`, sets reviewed-since to that review's time, and then runs
  the gate, so F4 refused most real merges. The user ruled it out 2026-09-23.
  Two live-chain cases, built from pull requests 665 and 667 as the chain gated
  them, assert the gate passes them and replace B5; a mutation re-adding the
  filter turns 665 red.
- **F2's bound includes the merge account's own latest review** (fix round,
  2026-09-23, merge-lane-2's review of PR 691). On a pull request the merge
  account opened, mac-claude approves and the merge account then posts a
  COMMENTED review; bounded by the pin alone the gate refused that flow at every
  reviewed-since. A live-chain case built from PR 687 passes, a mutation back to
  the pin-only bound turns it red, and two more 687 cases hold F2 and F5.
- **The mutation check runs inside the suite**, against a mutated copy in a
  scratch directory. The file under test is never modified, so the
  commit-before-mutating rule holds by construction. The control runs after the
  mutations.
