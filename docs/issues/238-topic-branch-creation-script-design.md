# Design: the topic-branch creation script

Issue: [nedschorus#238](https://github.com/nedschorus/nedschorus/issues/238). State as of 2026-09-02: the script is not built, and nothing in this document has been implemented.

**Vocabulary.** A *seat* is a named long-lived agent identity with a home directory at `~/agents/<seat>` — a git worktree of this project (`docs/agents/agent-seat-model.md`). Each seat has a branch named after itself, which its home starts on and returns to only between units of work; while a topic is in progress the home stands on that topic's branch. A *topic branch* is a branch carrying one unit of work, intended to become one pull request — this script creates it, well before it is filed.

**The rule this implements**, restated here so the document stands alone: an ordinary topic branch starts at current `origin/main`, rather than at whatever the working copy happens to be standing on. Stacked work is the one exception, and it is not this script's case — see "What it deliberately does not do". `CLAUDE.md` states the PR process in terms of "current main"; this document uses the remote-tracking ref `origin/main` throughout, because a seat's local `main` is stale or absent. The pull-request skill that would carry the full procedure is proposed in [nedschorus#236](https://github.com/nedschorus/nedschorus/issues/236) and does not exist. This script does not depend on that skill being written.

## The problem

`git checkout -b <name>`, with no start point given, creates the branch at whatever commit the working copy stands on, and moves the copy onto it. So the command that creates topic one leaves the copy standing on topic one, and the same command typed for topic two bases topic two on topic one. The second pull request then contains both topics while its description names one.

Nothing detects that automatically. The extra commits are visible from the moment the branch exists — `git log origin/main..HEAD` shows them locally, and the pull request's commit list shows them once filed — and main's protection requires an approving review, so the mistake is catchable. But catching it depends on a person looking, and the branch's description will say one topic while its commits say two.

Naming the start point explicitly — `git checkout -b <name> origin/main` — prevents it at creation, from anywhere in the checkout. `git switch -c <name> origin/main` and `git branch <name> origin/main` express the same control, as does standing on a branch already at `origin/main` before creating. Every one of them depends on the caller remembering; nothing mechanical enforces any of them today.

**Near-miss, 2026-09-01.** This seat (`reboot-test`) created four topic branches in a row, filed as pull requests #229, #230, #231, #232, naming `origin/main` explicitly on each. Each of the four depended on that argument: the first would have been based on the seat's branch, and each of the other three on its predecessor. The failure did not occur, and the margin was one argument, four times.

## What the script does

`python3 scripts/start-topic-branch.py <topic-name>` from the repository root, or the same by an absolute path from any directory. Every git command runs in the current working directory and inherits git's own root discovery, so a subdirectory works; the script does not resolve a root of its own, and in particular does not use its own file location, which is why running it by absolute path from an unrelated repository acts on that repository (see "Project identity is not checked").

The two git commands that change anything:

1. `git fetch origin`
2. `git checkout -b <topic-name> origin/main`

Rows 1 through 5 of the next section are checked before either command runs; rows 6 through 8 are those commands failing. Of the two, only the checkout creates or switches anything local — the fetch changes remote-tracking refs, which the state guarantee treats separately.

The new branch's start point is `origin/main` by construction: `git checkout -b` with an explicit start point does not consult HEAD when choosing the new branch's commit. Where the caller stands is irrelevant to the *base*. It is not irrelevant to whether the switch can happen — see the overwrite refusals below.

**Why no seat branch is involved.** An earlier draft routed through the seat's own branch: check it out, fast-forward it to main, then create the topic from there. Two facts removed that route, both measured on 2026-09-02 against throwaway repositories:

- Nothing requires it. A repository holds any number of branch refs alongside its one checked-out branch, and git's worktree exclusivity applies only to checking a branch out, not to creating one from a start point. So a topic branch can be created from `origin/main` while standing on a topic branch. (Git refuses checkout for other reasons too — rows 3 through 8 below.)
- It was unsafe. `git merge --ff-only origin/main` does **not** refuse when the current branch is strictly ahead of `origin/main` — it answers "Already up to date" and exits 0, leaving stray commits in place for the next branch to inherit. It refuses on divergence, not on being ahead. The step meant to be the safety net was not one.

Consequence worth stating, because the earlier draft claimed it as a benefit: the seat's own branch does not advance. `scripts/clean-worktrees.py` reports a branch as removable only when no worktree holds it AND it carries nothing `origin/main` lacks, so an unadvanced seat branch is reported only while it is also vacant and merged. Nothing here changes that either way — the earlier draft was wrong to count it as a gain.

## The caller contract

**Exit status** — `0` success; `1` refusal (rows 2 through 8 below); `2` usage error (row 1: wrong argument count, or a first argument beginning with `-`); `3` an unexpected error, meaning the script's own traceback rather than a condition it anticipated. A refusal is an ordinary outcome rather than a crash, but it is nonzero so `&&` chains and calling scripts stop. Exit 3 exists so that a crash is distinguishable from a refusal — an uncaught Python exception would otherwise exit 1 and impersonate one.

**Success**, one line on stdout:

```
<topic-name> created at <sha> (origin/main)
```

`<sha>` is the full object name as `git rev-parse` prints it — 40 hex characters in a SHA-1 repository, 64 in a SHA-256 one — never abbreviated, so the line does not vary with `core.abbrev` or repository size.

**Refusal**, on stderr: one line naming what is wrong, one line naming what to do about it, and then git's own message verbatim when git produced one. Git's messages are frequently multi-line and are not reformatted or truncated — the first two lines are the script's contract, and anything after them is git's. The rows below name their fact in one line; where a row's fact is git's message, the first line summarizes and git's own text follows in full.

**Usage error**, on stderr: the usage line, then a next-action line. Nothing on stdout.

Stdout carries the success line and nothing else — on any nonzero exit it is empty.

Subprocess output is captured, so git's messages appear only where this contract puts them. Capture does not cover authentication: depending on how the caller's environment is configured, git may use a credential helper, an askpass program, fail outright, or write a prompt straight to the terminal. The last case can block the fetch indefinitely, and no refusal row covers a hang. The script sets `GIT_TERMINAL_PROMPT=0` so that an uncached credential fails as a row 6 refusal rather than waiting on input the caller may not be able to see.

## Refusals

Checked in this order. Every check before the fetch is local and cheap; the fetch is the first thing that touches the network.

| # | Condition | Fact reported | Next action |
| --- | --- | --- | --- |
| 1 | Wrong argument count, or first argument begins with `-` (exit 2) | the usage line | pass exactly one topic name |
| 2 | Not inside a git checkout | the working directory | run it from inside the project checkout |
| 3 | `git check-ref-format refs/heads/<name>` rejects the name | the name | see `git help check-ref-format` for the rules |
| 4 | A local branch of that name exists | the branch and its tip | pick another name; if this is the branch you want, check it out from the worktree that is free to hold it |
| 5 | The name and an existing `refs/heads/` ref cannot both exist, because one is a path prefix of the other | both names | pick a name where no existing branch is a slash-separated prefix of it, and it is not a prefix of one |
| 6 | `git fetch origin` fails | git's message | check the network, the remote, or credentials, then retry |
| 7 | No `origin/main` after the fetch | the `origin/*` refs that do exist | check that `origin` is this project's remote |
| 8 | `git checkout -b` fails for any other reason | git's message | read git's message; see the state note below before retrying |

Row 3 reports the name alone: `git check-ref-format` signals rejection through its exit status and prints nothing (measured — zero bytes on stderr), so there is no git message to pass on.

Row 7 reports the refs rather than the configured URL of `origin`. A remote URL can carry a token or password in its authority component, and this fact is printed to stderr and into agent transcripts.

**Row 5 exists because valid names can still be uncreatable.** Measured: with branch `foo` present, `git checkout -b foo/bar origin/main` fails with "cannot lock ref 'refs/heads/foo/bar': 'refs/heads/foo' exists". The inverse fails the same way — with `baz/qux` present, plain `baz` cannot be created. Both names pass `check-ref-format` and neither exists as a branch, so rows 3 and 4 do not catch them.

The collision is between slash-separated path components, not string prefixes: with `foo` present, `foobar` creates without complaint (measured). The row is detected by listing `refs/heads/` and comparing components, before the fetch — git's own error would otherwise surface as row 8, with a message about locking a ref rather than about the name the caller chose.

Rows 4 and 5 consider local branches only. A name that exists solely as `origin/<name>` is created here without objection and collides later, at push time. Accepted: the collision is visible at the push, the fetch has just made the remote refs available for a caller who wants to look, and refusing on remote names would block the ordinary case of recreating a branch whose remote copy is merged but not yet deleted.

**Row 8 is the catch-all**, and it carries the overwrite refusals, which are the ones a caller mid-work will actually hit. Measured, both leave the caller on their original branch with their edits intact and no branch created:

- A **modified tracked file** whose path also differs between HEAD and `origin/main`: "Your local changes to the following files would be overwritten by checkout".
- An **untracked file** whose path exists in `origin/main` but not in HEAD: "The following untracked working tree files would be overwritten by checkout".

Row 8 also covers a locked index, a full or read-only filesystem, and a hook that exits nonzero. Those three do not share the overwrite pair's clean-failure property, which is why the state guarantee below is conditional rather than absolute.

**What uncommitted changes do.** They ride onto the new branch — measured for both a modified tracked file and an untracked file at paths `origin/main` does not track. Two exceptions refuse under row 8, both measured: a modified tracked file whose path differs between HEAD and `origin/main`, and an untracked file at a path `origin/main` tracks.

One case is neither carried nor refused. **An ignored file at a path `origin/main` tracks is silently overwritten** — measured: the checkout succeeds, exit 0, and the file's content is replaced with the version from `origin/main`, with no warning. Ignored files are untracked, so this is inside the population the paragraph above is about, and a seat's home is where scratch files live. Accepted rather than fixed: this is git's ordinary behavior for ignored paths, any check would have to enumerate `origin/main`'s tree against the ignore rules on every run, and a path that is both ignored locally and tracked upstream is a misconfiguration worth noticing on its own. Named here so that a caller who loses a scratch file knows why.

**The state guarantee.** On a refusal from rows 2 through 7, and from row 8's two overwrite cases, HEAD, the working tree, the index, and every branch under `refs/heads/` are exactly as they were.

Row 8's other members do not carry that guarantee, and the design does not pretend otherwise. Measured: a `post-checkout` hook that exits nonzero makes `git checkout -b` exit 1 **after** the branch has been created and checked out — the caller ends on the new branch. A filesystem that fills partway through can likewise leave the working tree partly updated. Row 8's next action therefore points the caller at git's message and at `git status` rather than promising nothing happened.

Refusals 6 through 8 follow the fetch, which does change repository state: remote-tracking refs under `refs/remotes/`, `FETCH_HEAD`, reflogs, and new objects. That is stated rather than hidden — it is not state a caller's work sits on. The `refs/heads/` half of the guarantee assumes `origin` has a conventional fetch refspec; one written to update `refs/heads/` directly would break it, and this project does not use one.

**A branch checked out in another worktree** refuses at row 4, before git's own "already checked out" error. Row 4's next action names the other worktree as the place to go, because a `git checkout` here would fail for that exact reason.

**Project identity is not checked.** Rows 2 and 7 establish a git checkout with an `origin/main`; they do not establish that it is *this* project. Run by an absolute path from inside an unrelated repository that has an `origin/main`, the script creates a branch there and reports success — and the success line names only the branch and the sha, so nothing in the output says which repository it happened in. Accepted rather than overlooked: the check would need a pinned remote URL or a marker file, and this fleet's seats work in one project. Reopen when a seat works in two projects at once; the person to notice is whoever adds a second project to a seat's brief.

## What it deliberately does not do

- **Stacked work.** Work that builds on an unmerged topic must start at that topic, not at main. This script always uses `origin/main`, so that case is done by hand with `git checkout -b <name> <parent-topic>`. The pull request must then say which branch it is stacked on and which pull request must merge first; a machine-readable form for that is #236's to settle. No flag here — a flag invites use when the base should have been main.
- **Committing, pushing, or opening a pull request.** One script, one job.
- **Naming conventions.** `CLAUDE.md` requires explicit multi-part names, checked with glob for path names and grep for names in files, and a more explicit 3-or-4-part name where those return collisions. Whoever chooses the topic name applies that before calling this. The script enforces only git's own ref rules, which are mechanical (rows 3 and 5).

## Where it sits in the code-prompt-code structure

Code-prompt-code (CPC) is this project's design philosophy: a system is built from nodes that are either code or prose instructions to an agent, each type chosen for what it is good at — code for what must be exact and repeatable, prose for what needs judgment or must absorb the unanticipated. The philosophy has no written home yet; [nedschorus#237](https://github.com/nedschorus/nedschorus/issues/237) tracks the page that will define it, and that page governs the term over this paragraph.

This script is a code node. It branches — it classifies conditions and chooses among outcomes — but every branch is decided by a fact the script can read: the arguments it was given, or what git reports. No outcome depends on judgment. The judgment stays with the caller: which topic to start, what to name it, whether the work is stacked.

A second code node is proposed in issue #238 but not designed: a check at pull-request creation that refuses a branch carrying another open pull request's commits unless the pull request declares the dependency. Its mechanism is undecided and its design would be a separate document. Until it exists, this script is a convenience the caller can bypass by typing git directly — the prevention it offers is real but voluntary, and nothing makes it the only path.

## Value across gatekeeper activation

While the main-gatekeeper is dormant, agent-created topic branches are the ordinary way this fleet's work reaches main. One historical exception is on record: the gatekeeper's first live check-in landed commit `b24e376` on 2026-08-18, user-authorized, before main's protection was measured to require a review. The gate has been dormant since, and the PR process in `CLAUDE.md` — branch, pull request, merge-lane review — governs every agent change.

After activation the script has a narrower use. Per `docs/cross-project/main-gatekeeper-design.md`, the gate builds each change in its own private workspace from main, so a caller creates no branch for an ordinary change; the gate opens the pull request, which means it creates that pull request's source branch itself. Two cases still need an agent-created topic branch: the gate's own source, since the gate refuses check-ins touching `scripts/main-gatekeeper.py` (`gatekeeper-source-refused`) for as long as that refusal stands, and stacked work, which the gate's build-from-main shape does not serve either.

## Testing

`scripts/start-topic-branch-test.py`, beside the script. Each case builds its own throwaway fixture — a bare repository as `origin` plus a clone — and runs the script as a subprocess, in the manner of `scripts/main-gatekeeper-test.py`. Nothing further about the structure of the new test file is required here.

**The central case.** `origin/main` is at commit M; the caller stands on a topic branch whose tip is a different commit T. Run the script. Assert exit 0, the success line on stdout naming the new branch and M's full sha, and that the new branch's tip is M and not T. The tips must differ or the assertion proves nothing about base selection.

**Its red witness** — a deliberately broken copy of the script, run to prove the central assertion can fail. The script's checkout is written so the start point is one element of its argument list, and the variant is built by dropping that element, not by editing text: the test imports the script's `checkout_command(name)` helper, checks that `origin/main` is one of the elements it returns, and runs a copy whose helper omits it. Deleting a list element cannot leave an empty argument, which a text substitution could, and the membership check fails loudly if a later edit renames or restructures the helper.

The variant runs against a **freshly built fixture**, not the one the central case just used — that fixture now has the branch created and the caller standing at M, so the mutant could not start from T. Assert the variant's new branch tip is T, and that the run exited 0: the mutant must fail the *base* assertion rather than erroring, or it witnesses nothing about base selection.

**One case per row**, asserting the exit status (2 for row 1, 1 for rows 2 through 8), that stderr's first two lines name the fact and the next action, that stdout is empty, and that HEAD, the current branch's tip, the working tree, the index, and every ref under `refs/heads/` are unchanged. Refs under `refs/remotes/`, `FETCH_HEAD`, and the object store are excluded, per the state guarantee. Row 1 gets two cases, one for each of its conditions. Row 2's case runs in an empty directory that is not a checkout and asserts only exit 2's absence, the message, and that the directory is still not a repository. Row 5 gets both collision directions.

Rows 6 and 8 also assert that git's message survives after the two contract lines, since truncating it is the failure the contract exists to prevent.

**Row 8's three tested members**: the modified-file overwrite, the untracked-file overwrite, and a locked index. The full-filesystem and failing-hook members are named in the design and left untested — the first is impractical to provoke, and the second is covered by the state note rather than the guarantee. The hook case gets one assertion of its own: that after a nonzero `post-checkout` hook the script exits 1 and reports git's message, with no claim that the working copy is unchanged.

**Two cases that uncommitted changes ride along**: a modified tracked file and an untracked file, at paths that exist in `origin/main` with the same content as in HEAD, each asserting exit 0 and that the file's content survives on the new branch. The path must exist in `origin/main` — a tracked file absent there is removed by the checkout, and with a local modification git refuses (measured), which is row 8's case, not this one.

**One case for the ignored-file overwrite**: an ignored file at a path `origin/main` tracks, asserting exit 0 and that its content was replaced. The behavior is accepted, so the test pins it rather than forbidding it — if a later change starts refusing instead, that is a decision to make deliberately.

## Questions the writer could not settle

None blocking implementation. Two decisions are recorded as belonging elsewhere, neither of which changes what this script does: the machine-readable form of a stacked-work declaration, which is #236's to settle when the pull-request skill is written; and the mechanism of the pull-request-creation check, which is proposed in #238 and would need its own design document before anyone builds it.

One behavior is accepted rather than settled, and is recorded above at the place it applies: an ignored file at a path `origin/main` tracks is silently overwritten.
