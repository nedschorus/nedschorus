# checkout-freshness catch-up reports instead of merging

Pair document for [nedschorus#324](https://github.com/nedschorus/nedschorus/issues/324).
The issue carries the summary and the next action; this document carries the
design, the decisions, and the occurrence log.

## The defect, in one example

A seat pushes its branch and announces the head to the merge lane, which
commissions a reviewer against that exact commit. The seat keeps working. At
the end of its next turn the Stop hook `scripts/checkout-freshness-catch-up.py`
finds the branch behind `origin/main` and merges main into it. The tree now
holds a merge commit on top of the reviewed head. Nothing is pushed yet, but
the next habitual `git push` moves the head under the running review, and the
reviewer's work is thrown away. The gate cannot merge a wrong commit — it pins
to the approved one — so the cost is a wasted review round, reachable without
anyone deciding to push anything new.

## Ruled 2026-09-14

**The hook never merges into the working branch.** It reports instead. The
reference checkout's `--ff-only` refresh stays; it produced no occurrence and
is what keeps each machine's `~/Projects/nedschorus` current.

**The report is for the agent's knowledge, not a prompt to act.** The response
stays with the agent: new work is cut from `origin/main`; a frozen head is
never merged into; otherwise carry on.

The user's framing: *"Shouldn't it only do something if there is something to
do?"* and *"let's have a smarter, better system."* The provenance is recorded
on the issue: the mandate is his, the wording an agent's, the approval one
letter.

## What the hook did between the two rulings (built 2026-09-15 morning; superseded the same day for the session path — see the walk section below; the reference-checkout behaviour stands)

At every turn end, for the session's own checkout:

1. Fetch `origin`, throttled by the stamp (unchanged).
2. Count `behind` and `ahead` against `origin/main` (unchanged) and record
   them in the stamp for the status line.
3. If behind, gather three more facts and **report them on the display**:
   - **own commits** — `rev-list --count --no-merges origin/main..HEAD`, the
     branch's own work as distinct from catch-up merges it may carry. The
     2026-09-14 measurement (`supervisor-assumed-alive-says-only-what-is-kept`,
     3 ahead, 0 own) is exactly this distinction.
   - **head state** — `unpushed` (no `origin/<branch>`), `pushed` and equal to
     `origin/<branch>` (frozen), or `pushed-with-local-commits` with the count
     not on the remote; `detached` for a detached HEAD.
   - the tip of `origin/main`, so a moved main is a new fact.
4. Print the line only when those facts differ from what the stamp last
   reported. The same facts at the next turn end are silent.

The line reads, for example:

```
catch-up: my-branch is 6 behind origin/main — 2 own commit(s), 2 ahead counting merges; head pushed and equal to origin/my-branch (frozen: a fix is a new commit on top, never an amend or a merge). Not merged (ruled 2026-09-14): new work starts from origin/main, and a frozen head is never moved.
```

The stamp gains `own`, `head_state`, `last_reported` and a `last_action` of
`reported, not merged (ruled 2026-09-14)`.

## Decisions taken in the build

1. **Display only, never a block.** The decision:block channel (ruled
   2026-08-17 for attention states) had two states: a landed merge and a
   failed conflict abort. With no merge there are none, so the channel, its
   emitter and its latch are removed. The hook now never costs the agent a
   turn. A consequence: the half of
   [nedschorus#334](https://github.com/nedschorus/nedschorus/issues/334) in
   which the block overwrote a `claude -p` answer cannot happen any more.
2. **Report on change only.** With no merge, "behind" stays nonzero for the
   life of a review; a line repeating it at every turn end is the "does
   something when there is nothing to do" the ruling answered. The status
   line still shows `⇣N` from the stamp regardless — and that segment is
   painted as a fault colour, which a persistent, normal "behind" now makes
   less apt; not changed here.
3. **Head state from git alone.** The ruling's wording says "frozen under an
   open pull request". CLAUDE.md freezes a head the moment it is pushed,
   because that is when review is commissioned, so "pushed and equal to
   origin/<branch>" is the fact the rule keys on. Asking GitHub for the pull
   request at every turn end needs `gh` and the network and can hang or
   prompt; it is not done. A stale `origin/<branch>` after the remote branch
   is deleted reads as "pushed" until the next prune, which is the safe
   direction.
4. **The dirty-tree and in-progress blockers stay for the reference
   fast-forward only.** The session path has nothing left for them to block.

## Walked and ruled 2026-09-15: rebase the never-pushed, tell the pushed, alert only on misbehaviour

Walk: `docs/walk/keeping-branches-current-telling-and-rebase` (gitignored; the
minutes are the record of the exchange, this section is the record of the
rulings). Eight items, all ruled. What was built:

**1. A never-pushed branch is rebased by the hook itself, at turn end.** No
`origin/<branch>` exists, so nobody has the commits and no review is running.
`git rebase --no-autostash origin/main`; skip if the tree has uncommitted
tracked changes or a git operation in progress; on conflict, `git rebase
--abort`, verify no rebase state remains, and name the conflicting files. The
agent is told at its next turn what happened: on success, which files moved
under it and to rerun the suites for what it touched; on a skip or conflict,
why, and the by-hand steps. A success is always told; a skip or conflict is
told once per key but attempted every turn end, so it goes the moment the
tree is clean.

This is not the merge the 2026-09-14 ruling removed. That merge landed
MERGE COMMITS on FROZEN heads — pushed, with a review running — nine times in
five days. This is a REBASE of heads NOBODY ELSE HAS: no review to disturb,
no merge commit created, the pushed-head rule untouched. The 2026-08-13
objection to rewriting files under a running agent is answered by the
telling channel, which did not exist then. The user's question that settled
it: "I don't see how postponing that process helps" — and it does not; the
launch sync already hands the same reconciliation to the agent at launch, so
doing it at turn end for the one safe case only closes the window between
launches.

**2. A pushed branch is never moved.** Any pushed state — equal to the
remote, local commits on top, behind its own remote, or diverged. The agent
is told, once per update of main: how far behind, the stale files by name
grouped by why they matter, and:

> This branch is pushed, so its review may be running. Do not rebase, merge or amend it. A fix for this topic is a new commit on top, pushed once. Start your next topic with `git checkout -b <name> origin/main`.

The user asked, of that line, whether anything reaches main unreviewed. No:
rebase pulls main down into a branch; push goes to the branch's own remote;
the only road into main is a reviewed pull request under branch protection.

**3. The user hears only misbehaviour.** "I dont want to have to pay
attention to details like this. If the agents are doing the wrong thing, or
not doing the right thing, that's when I probably need to be told." The
routine display line is gone. The hook's `systemMessage` carries three things
and nothing else, each once per distinct finding:

- a merge commit from main on a working branch (the thing #324 removed),
  detected by testing each merge's second parent for being on `origin/main`,
  so a merge of another topic branch is not flagged;
- a pushed head whose history was rewritten — `origin/<branch>` no longer an
  ancestor of `HEAD` — an amend or rebase after a push, a fifth head state
  `diverged-from-remote`;
- the reference checkout unable to fast-forward, because someone left work
  where none belongs (a peer seat's finding the same day: the Mac reference
  sat 22 behind with one uncommitted edit, silently). Reported once per
  reason, not per turn: this check runs at every turn end off local refs, and
  the line had always repeated — to plain stdout nobody read — which as the
  user's line would have been the noise this ruling removed.

The detectors run every turn BEFORE the drift path: a branch that merged main
into itself is 0 behind, exactly where a drift-first design returns early.

**4. The repeat record.** `last_told` = branch, main's tip, and whether the
head is pushed. Nothing else. The session id was dropped: two sessions in one
checkout evicted each other's record and were told every turn (the author
did it to himself, testing against the live checkout). "Pushed" is in the
key because the advice flips at a push, and a seat told to rebase that pushed
instead must hear the new advice. Main's tip is in it because "not more than
once per pushed PR or whatever else updates main" is a cap, not a reduction
below it — keyed any coarser, a file that goes stale an hour into a session is
never mentioned. A pushed head changing shape without main moving (behind its
remote; diverged) is not re-told until main next moves; the stamp records the
state and the user line, where there is one, fires regardless.

**5. What is said is computed, never asserted.** The first draft ended with
"your tests, hooks, skills and documents here are older than main"; the user
asked "are you sure ... or are you just saying that?" Just saying it: in the
author's own twelve-commit gap, ten scripts and four documents had moved and
zero hooks and zero skills had. `obsolete_files_by_category()` runs
`git diff --name-only HEAD...origin/main` — three dots, from the merge base,
or the branch's own work reads as something main changed — and names the
files under "your standing instructions", "skills you run under", "hooks and
wiring that run on your work", "scripts your tests run against", "documents
you may cite", four per group then a count. A failed fetch is named in the
message. When the listing cannot be built the clause is dropped, not guessed.

**6. Channel.** One Stop hook, one JSON object: `hookSpecificOutput.
additionalContext` to the agent, `systemMessage` to the user, never a
`decision`. A second hook on `UserPromptSubmit`, with a guarded settings edit,
was built and removed the same day on the false premise that a Stop hook
cannot reach the agent. It can; plain stdout cannot. `.claude/settings.json`
is untouched.

**Why not on idle.** There is an idle hook — `Notification`, `idle_prompt` —
but the harness discards the fields that would speak to the agent; it alerts
the user. Between turns no agent is listening; anything left there is read at
the next turn, as the user observed.

## Next, proposed and not built: warn on the obsolete FILE, not the branch

The line above is orientation — it tells a seat that it is behind, in general.
The user asked the better question: "is there any easy way to tell if any agent
has read or edited an obsolete file — that would be a good place to say
something useful" (2026-09-15). It is easy, and it is better.

`git diff --name-only HEAD...origin/main` already gives the exact set of paths
main has moved that this checkout has not; the telling computes it for the
category counts. Computed once per turn and cached against main's tip, every
file touch is then a set-membership test costing nothing.

A `PostToolUse` hook matching `Read|Edit|Write` receives `tool_input.file_path`
(absolute, for all three tools) and can return
`hookSpecificOutput.additionalContext`, which IS added to the agent's context —
the same mechanism the Stop hook now uses. Plain stdout on those events does
NOT reach the agent; only the JSON field does. Checked against the hooks
reference rather than assumed, because assuming a channel's reach is the
mistake this issue is a record of.

Why it is still wanted, even with the telling capped at main's tip: it is
earned. It fires only when an agent actually touches a file main has changed,
and it names that file at the moment of the touch rather than at the moment of
the last telling. The edit case has real teeth — editing a file main has
already moved is how a conflict is made, or how a fix that landed yesterday
gets written twice — whereas being behind in general costs nothing at merge
under branch protection. The two do different jobs: the drift line orients a
seat when it arrives and when main moves; the file warning catches it in the
act.

Not built: it is a separate topic and needs a `.claude/settings.json` edit,
which the instruction-file guard protects.

## The ghi-info checkout: answered (b), built 2026-09-15

The ghi-info checkout on ned-box sits on a branch named `ghi-info` with zero
commits of its own, and this hook's merge was the only thing keeping it
current (#334: it sat 225 commits behind before 2026-09-11). Under the ruling
as built it is reported and left where it is. Two candidates were put to the
user:

- (a) the hook fast-forwards a branch whose own-commit count is zero — no
  merge commit, nothing authored, but it does move the working branch, which
  the ruling's words forbid;
- (b) `scripts/ghi-info-ask.py` refreshes that checkout itself with
  `git merge --ff-only origin/main` before each ask, keeping the hook's rule
  absolute and putting the refresh in the one caller that knows the answer is
  program-consumed.

**The user ruled (b) on 2026-09-15**, the recommendation. What it buys: the
hook's "never move a working branch" stays absolute with no exception carved
into it, and the refresh happens where the need actually is — ghi-info cites
the pair documents and wiki pages, and reads them off that disk, so a stale
checkout is stale answers about the designs the issues point at.

Built as `fast_forward_seat_checkout()`, called by the lock holder at the top
of the ask, before the mirror refresh or any `claude` turn:

- **Only under the lock.** A contended ask publishes into a throwaway mirror
  precisely so it cannot disturb the holder; swapping the checkout's files
  beneath the holder's running `claude` would undo that.
- **Never merges.** `--ff-only`. ghi-info commits its own document-side link
  repairs, so a checkout carrying a commit main does not have is a real state:
  it is reported and left alone, exactly as the hook now does.
- **Never fails an ask.** A dirty tree, an unreachable origin, a refused
  fast-forward, a seat that is not a checkout at all — each is one stderr line
  and the ask proceeds against what is on disk. A caller cannot distinguish an
  ask that failed here from one where the box was down, so failing would send
  it down the ghi-write fallback ladder for a reason that does not warrant it.
- **Not** `fast_forward_reference_checkout` from the hook: that one requires
  the checkout to be parked on main and treats any other branch as a blocker,
  which is the guarantee a REFERENCE copy needs. This checkout is on its own
  branch. Loosening that function for this caller would weaken it where it
  matters, so this is a second, narrower one.

This closes the remaining half of
[nedschorus#334](https://github.com/nedschorus/nedschorus/issues/334).

## Occurrence log

The merges the old behaviour made onto frozen or finished heads, from the
`fleet-restart-at-login` seat alone:

| when | branch | state of the head |
|---|---|---|
| 2026-09-11 | `restart-live-seats-at-login-run-log` | #320 open, awaiting its reviewer |
| 2026-09-11 | the same | after #320 merged |
| 2026-09-11 | `restart-live-seats-at-login-report-matches-the-run-log` | #323 open at `d70e3d7`, minutes after the push |
| 2026-09-11 | `supervisor-liveness-by-process-identity` | #328 open at `a82b49e`, reviewer running |
| 2026-09-11 | the same | on top of an unpushed fix commit the lane had asked for as one commit |
| 2026-09-14 | `restart-live-seats-at-login-launch-step-and-mac-launchagent` | #354 open at `a3d85a0`, reviewer commissioned |
| 2026-09-14 | `launch-agent-installer-resolves-paths-and-offer-hint-names-handoff-dir` | after #355 merged, remote branch deleted |
| 2026-09-15 | `restart-live-seats-at-login-restarts-whatever-was-live-at-the-stop` | #370 open at `4b5ce50`, reviewer running |
| 2026-09-15 | the same | after #370 merged |

None was pushed. Nine in five days on one seat is the rate.
