# Part three: the messages of the merge gate

This document is part three of GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956). The GHI's GHI-MD, `docs/issues/956-every-refusal-and-warning-a-program-hands-an.md`, is part one; part two, `docs/issues/956-part-two-the-git-hooks-messages.md`, covered the git hooks. This part covers every message `scripts/merge-gate.sh` prints. It shows each message that leaves its reader a question open, as the reader sees the message, and proposes the exact words to replace it, with the code changes the new words need. None of the proposed wording is built. The next action is a check by merge-lane-2 that the texts fit how it uses the program, then a cold-read-full-run of this document, then one approval-walk with the user, then one pull request, cut from main, that builds what the user approves, with its test cases.

## What a reader needs first

**What the merge gate does.** `scripts/merge-gate.sh` decides whether a pull request may be merged. It is called as `scripts/merge-gate.sh <pull request number> <expected head commit, 40 characters> <reviewed-since, YYYY-MM-DDTHH:MM:SSZ>`. It reads the pull request's state, its reviews, its inline comments and its issue comments from GitHub, as the merge account `ned-review-merge`, with the token in `$HOME/.config/nedschorus/ned-review-merge.token`. It passes only when the newest approving review covers the current head commit, GitHub reports the pull request approved and mergeable, and no review or comment has arrived after reviewed-since. When it passes, it prints the exact `gh pr merge` command to run, pinned to the approved commit with `--match-head-commit`.

**Who reads its messages.** Only merge-lane-2 runs the gate, and not directly: a wrapper program calls it with the pull request number, the full head commit and the review's `submitted_at`, and calls it again while GitHub reports the mergeStateStatus `UNKNOWN`. The wrapper lives in a scratch directory today; merge-lane-2 has an open task to move it into the repository. When the gate passes, merge-lane-2 copies the printed merge command and runs it as given. The two refusals merge-lane-2 meets in practice are a standing `CHANGES_REQUESTED` review, which it dismisses with a reason before running the gate again, and comments or reviews newer than reviewed-since, which it reads before running the gate again.

**Two kinds of message.** Every message is one line on stderr, with one of two prefixes, and the exit status says which:

- `GATE REFUSED (#<number>): ` with exit status 1: the gate ran and the pull request must not be merged now.
- `GATE COULD NOT RUN: ` with exit status 2: the gate could not decide, because of how it was called or because it could not read or parse an answer. The header of `scripts/merge-gate.sh` keeps the two apart because the fleet's worst near-misses were a gate that could not run being read as a gate that passed.

When `gh` or `jq` fails, the program it ran prints its own error on stderr just above the gate's line, because the gate captures only their standard output.

**The four questions.** As in parts one and two, a message is complete when the message says:

1. What was refused or found, naming the file or the command.
2. Why: the rule being enforced, or what goes wrong if the agent goes ahead.
3. What to do instead, as an instruction.
4. Under which condition each instruction applies, when the message gives more than one.

**When to tell the user.** A message tells merge-lane-2 to tell the user only for a failure merge-lane-2 cannot fix itself: the merge account's token, a tool missing from the machine, or a read or parse that keeps failing.

**Where the list comes from.** Part one's audit, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/MD-skills/refusal-and-warning-message-audit-2026-10-01.md`, found 27 messages from the merge gate, 20 of them missing an instruction or a reason. Every message below was read again from main at the commit [Merge pull request #1075 from nedschorus/ghi-956-edit-ghipairef15a4328a1316b6](https://github.com/nedschorus/nedschorus/commit/c16466b6), and the line numbers are main's at that commit. The program prints 27 distinct failure texts, as the audit counted: 12 `GATE COULD NOT RUN` texts, one of which is printed from four places, and 15 `GATE REFUSED` texts. It prints three lines on a pass.

## The messages, one at a time

In the examples, the pull request is 1074, its head commit is `0d55173b2c4e8a9f1b6d3e7a5c9f2b4d8e1a6c3f`, and reviewed-since is `2026-10-05T15:58:12Z`.

### Calling the gate

#### 1. Wrong number of arguments

**When merge-lane-2 sees this.** The wrapper calls the gate with two arguments, or four.

**Today** (`scripts/merge-gate.sh:139`):

```
GATE COULD NOT RUN: usage: merge-gate.sh <pr-number> <expected-head-sha> <reviewed-since-iso8601>
```

**What the reader cannot tell from the text.** How many arguments it passed, what each argument must hold, and that the fix is in the call.

**Proposed text** (`{count}` is the number of arguments given):

```
GATE COULD NOT RUN: merge-gate.sh takes exactly three arguments and was given {count}.
Call it as: scripts/merge-gate.sh <pull request number> <the full 40-character head commit the review covered> <the review's submitted_at, as GitHub returns it>
```

#### 2 and 3. The expected head commit is not a full commit hash

**When merge-lane-2 sees this.** The call passes `0d55173b`, a short hash, or a value with capital letters.

**Today** (`scripts/merge-gate.sh:148` and `:150`):

```
GATE COULD NOT RUN: expected-head-sha is not a full 40-character hex sha: 0d55173b-
GATE COULD NOT RUN: expected-head-sha is 8 characters, not 40: 0d55173b
```

**What the reader cannot tell from the text.** Where to get the full hash.

**Proposed text** (each keeps its first line as today, and gains a second):

```
GATE COULD NOT RUN: expected-head-sha is not a full 40-character hex sha: {value}
Pass the full commit hash in lower case, as the review's commit_id records it, then run the gate again.
```

```
GATE COULD NOT RUN: expected-head-sha is {length} characters, not 40: {value}
Pass the full commit hash in lower case, as the review's commit_id records it, then run the gate again.
```

#### 4. reviewed-since is not in GitHub's form

**When merge-lane-2 sees this.** The call passes `2026-10-05T15:58:12+00:00` or `2026-10-05T15:58:12.000Z`.

**Today** (`scripts/merge-gate.sh:154`):

```
GATE COULD NOT RUN: reviewed-since must be exactly YYYY-MM-DDTHH:MM:SSZ, the form GitHub returns: 2026-10-05T15:58:12+00:00
```

**What the reader cannot tell from the text.** What to pass instead. The form is strict because the gate compares times only in that form; a time with an offset once counted too few comments and passed.

**Proposed text:**

```
GATE COULD NOT RUN: reviewed-since must be exactly YYYY-MM-DDTHH:MM:SSZ, the form GitHub returns: {value}
Pass the review's submitted_at exactly as GitHub returns it, then run the gate again.
```

### The machine

#### 5. jq is not on PATH

**Today** (`scripts/merge-gate.sh:142`), complete by the audit:

```
GATE COULD NOT RUN: jq is not on PATH. Put jq on PATH, then rerun the gate.
```

**What the reader cannot tell from the text.** What to do when jq is not installed at all.

**Proposed text:**

```
GATE COULD NOT RUN: jq is not on PATH. Put jq on PATH, then rerun the gate.
If jq is not installed on this machine, tell the user this message.
```

#### 6. gh is not on PATH

**Today** (`scripts/merge-gate.sh:143`):

```
GATE COULD NOT RUN: gh is not on PATH
```

**What the reader cannot tell from the text.** What to do.

**Proposed text:**

```
GATE COULD NOT RUN: gh is not on PATH. Put gh on PATH, then rerun the gate.
If gh is not installed on this machine, tell the user this message.
```

#### 7 and 8. The merge account's token

**When merge-lane-2 sees this.** `$HOME/.config/nedschorus/ned-review-merge.token` cannot be read, or is empty.

**Today** (`scripts/merge-gate.sh:162` and `:163`):

```
GATE COULD NOT RUN: could not read the merge account's token at /home/nedlern/.config/nedschorus/ned-review-merge.token
GATE COULD NOT RUN: the token file /home/nedlern/.config/nedschorus/ned-review-merge.token is empty
```

**What the reader cannot tell from the text.** Why the gate needs this token rather than the credential gh already has, and what to do. Without the token, gh falls back to its stored credential, which on the Mac is the account that authors the pull requests. Only the user manages the token.

**Proposed text** (each keeps its first line, and gains two):

```
GATE COULD NOT RUN: could not read the merge account's token at {path}
The gate reads GitHub as the merge account, ned-review-merge; without this token gh would use its stored credential, which may be another account.
Tell the user this message: only the user can restore the token.
```

```
GATE COULD NOT RUN: the token file {path} is empty
The gate reads GitHub as the merge account, ned-review-merge; without this token gh would use its stored credential, which may be another account.
Tell the user this message: only the user can restore the token.
```

### Reading and parsing GitHub's answers

#### 9 to 12. A channel could not be read

**When merge-lane-2 sees this.** A `gh` call fails: GitHub does not answer, the token is refused, or the pull request number does not exist. gh's own error is printed just above.

**Today** (`scripts/merge-gate.sh:167`, `:180`, `:219` and `:221`):

```
GATE REFUSED (#1074): could not read pull request state
GATE REFUSED (#1074): could not read the review channel for the approving commit
GATE REFUSED (#1074): could not read the inline comment channel
GATE REFUSED (#1074): could not read the issue comment channel
```

**What the reader cannot tell from the text.** That gh's error is above, what to do, and when to tell the user. These four exit 1, as refusals, although the gate could not read its input; see "Questions for merge-lane-2".

**Proposed text** (each keeps its first line, and gains three):

```
GATE REFUSED (#{pr}): could not read the issue comment channel
gh's error is just above this line.
Run the gate again.
If it fails the same way again, tell the user this message and gh's error.
```

The other three take the same three lines after their own first line.

#### 13 to 16. A channel could not be parsed, or a time could not be compared

**When merge-lane-2 sees this.** `jq` fails on what GitHub returned, for example because a page was cut off. jq's own error is printed just above.

**Today** (`scripts/merge-gate.sh:185`, `:200`, `:233` and `:252` print the first; `:203`, `:241` and `:245` the others):

```
GATE COULD NOT RUN: could not parse the review channel
GATE COULD NOT RUN: could not compare reviewed-since against 2026-10-05T15:58:12Z
GATE COULD NOT RUN: could not parse the inline comment channel
GATE COULD NOT RUN: could not parse the issue comment channel
```

**What the reader cannot tell from the text.** The same as messages 9 to 12.

**Proposed text** (each keeps its first line, and gains three):

```
GATE COULD NOT RUN: could not parse the review channel
jq's error is just above this line.
Run the gate again.
If it fails the same way again, tell the user this message and jq's error.
```

The other three take the same three lines after their own first line.

### The approval

#### 17. No approving review

**When merge-lane-2 sees this.** Pull request 1074 has reviews, but none with the state `APPROVED`.

**Today** (`scripts/merge-gate.sh:186`):

```
GATE REFUSED (#1074): no APPROVED review found
```

**What the reader cannot tell from the text.** Why, and what to do. The gate merges only the commit an approval covers. GitHub refuses an approval from a pull request's author, so when the merge account opened the pull request, another account must approve it.

**Proposed text:**

```
GATE REFUSED (#{pr}): no APPROVED review found; the gate merges only a commit an approving review covers.
If the head commit's review found no defect, approve the head commit, then run the gate again.
If the merge account opened this pull request, GitHub refuses its approval: have the commissioned reviewer approve the head commit, then run the gate again.
```

#### 18. The approval records no commit

**When merge-lane-2 sees this.** The newest approving review's `commit_id` is empty, which GitHub is not known to do.

**Today** (`scripts/merge-gate.sh:192`):

```
GATE REFUSED (#1074): the approving review records no commit_id to pin to
```

**What the reader cannot tell from the text.** What to do.

**Proposed text:**

```
GATE REFUSED (#{pr}): the approving review records no commit_id to pin to, so the gate cannot tell which commit it approved.
Tell the user this message, with the approving review's link.
```

#### 19. reviewed-since is later than the gate allows

**Today** (`scripts/merge-gate.sh:204`), complete by the audit:

```
GATE REFUSED (#1074): reviewed-since 2026-10-05T16:30:00Z is later than 2026-10-05T15:58:12Z, the approval or the merge account's own latest review. Rerun with a reviewed-since no later than 2026-10-05T15:58:12Z.
```

**What the reader cannot tell from the text.** Why the bound exists: a reviewed-since of "now" would count no comment as new. The proposal adds the reason to the first sentence and leaves the instruction as it is:

```
GATE REFUSED (#{pr}): reviewed-since {since} is later than {bound}, the approval or the merge account's own latest review; a later reviewed-since would hide comments nobody has read. Rerun with a reviewed-since no later than {bound}.
```

### The head commit and GitHub's state

#### 20. The head commit moved

**When merge-lane-2 sees this.** The author pushed a commit after the review was commissioned: the call names `0d55173b…`, and the head is now `9a1c…`.

**Today** (`scripts/merge-gate.sh:206`):

```
GATE REFUSED (#1074): head moved: reviewed 0d55173b2c4e8a9f1b6d3e7a5c9f2b4d8e1a6c3f, now 9a1c4e2b7d8f3a6c5e1b9d2f4a7c8e3b6d1f5a2c
```

**What the reader cannot tell from the text.** What to do.

**Proposed text:**

```
GATE REFUSED (#{pr}): head moved: reviewed {expected}, now {head}; no review has covered the commits pushed since.
Review the new head commit, then run the gate again with {head} as the expected head commit.
```

#### 21. The approval covers an older commit

**Today** (`scripts/merge-gate.sh:208`), complete by the audit; left as it is:

```
GATE REFUSED (#1074): the approval covers 0d55173b2c4e8a9f1b6d3e7a5c9f2b4d8e1a6c3f but the head is now 9a1c4e2b7d8f3a6c5e1b9d2f4a7c8e3b6d1f5a2c. Review and approve 9a1c4e2b7d8f3a6c5e1b9d2f4a7c8e3b6d1f5a2c before merging.
```

#### 22. The pull request is a draft

**Today** (`scripts/merge-gate.sh:209`):

```
GATE REFUSED (#1074): pull request is a draft
```

**What the reader cannot tell from the text.** Why, and what to do. A draft is one its author has said is not finished.

**Proposed text:**

```
GATE REFUSED (#{pr}): pull request is a draft, which its author has marked as not ready to merge.
Ask the pull request's author whether it is ready; once the author marks it ready for review, run the gate again.
```

#### 23. GitHub's review decision is not APPROVED

**When merge-lane-2 sees this.** Most often, an earlier review by mac-claude requested changes, and that review still stands although the findings were fixed: GitHub reports `CHANGES_REQUESTED` until the review is dismissed.

**Today** (`scripts/merge-gate.sh:210`):

```
GATE REFUSED (#1074): reviewDecision is CHANGES_REQUESTED, not APPROVED
```

**What the reader cannot tell from the text.** What to do for each value.

**Proposed text** (the second and third lines depend on the value):

```
GATE REFUSED (#{pr}): reviewDecision is {decision}, not APPROVED: GitHub will not count this pull request as approved.
```

then, for `CHANGES_REQUESTED`:

```
A review requesting changes still stands.
If its findings have been fixed or answered, dismiss that review with a reason that says so, then run the gate again; otherwise, do not merge.
```

and for any other value, such as `REVIEW_REQUIRED`:

```
A review the branch's rules require is missing: get that review, then run the gate again.
```

#### 24. GitHub's merge state does not allow a merge

**When merge-lane-2 sees this.** GitHub reports a mergeStateStatus other than `CLEAN`, `UNSTABLE` or `HAS_HOOKS`. The wrapper already calls the gate again while the value is `UNKNOWN`.

**Today** (`scripts/merge-gate.sh:213`):

```
GATE REFUSED (#1074): mergeStateStatus is DIRTY
```

**What the reader cannot tell from the text.** What the value means and what to do.

**Proposed text** (the second line depends on the value):

```
GATE REFUSED (#{pr}): mergeStateStatus is {merge_state}; GitHub allows the merge only when it is CLEAN, UNSTABLE or HAS_HOOKS.
```

then one of:

```
UNKNOWN: GitHub has not finished computing it; run the gate again in a minute.
DIRTY: the branch conflicts with main; tell the pull request's author to clear the conflict, then run the gate again on the new head commit.
BEHIND: the branch is behind main and the branch's rules require it to be up to date; tell the pull request's author, then run the gate again on the new head commit.
BLOCKED: a required check or review is missing; read the pull request's checks on GitHub before running the gate again.
For any other value, read the pull request on GitHub before running the gate again.
```

### New activity since reviewed-since

#### 25 to 27. New comments or reviews

**When merge-lane-2 sees this.** After the review it read, someone posted an inline comment, an issue comment or a review: for example, the author answering a finding.

**Today** (`scripts/merge-gate.sh:254`, `:255` and `:256`):

```
GATE REFUSED (#1074): 2 NEW inline comment(s) since 2026-10-05T15:58:12Z -- read them before merging
GATE REFUSED (#1074): 1 NEW issue comment(s) since 2026-10-05T15:58:12Z -- read them before merging
GATE REFUSED (#1074): 1 NEW review(s) since 2026-10-05T15:58:12Z -- read them before merging
```

**What the reader cannot tell from the text.** What to do after reading them. The gate counts an item as new until reviewed-since is at or after it, and reviewed-since may be no later than the approval or the merge account's own latest review. So reading the items is not enough on its own: to move reviewed-since past them, the merge account records that it read them in a review of its own.

**Proposed text** (each keeps its first line, and gains two):

```
GATE REFUSED (#{pr}): {count} NEW inline comment(s) since {since} -- read them before merging
If they raise a finding, do not merge until it is fixed or answered.
If they raise none, post a review as the merge account saying you read them, then run the gate again with that review's submitted_at as reviewed-since.
```

The other two take the same two lines after their own first line.

### The pass

**Today** (`scripts/merge-gate.sh:258`, `:261` and `:262`), complete by the audit; left as it is:

```
gate passed (#1074): approved commit 0d55173b2c4e8a9f1b6d3e7a5c9f2b4d8e1a6c3f by mac-claude at 2026-10-05T15:58:12Z, APPROVED, CLEAN, no new channel activity since 2026-10-05T15:58:12Z
MERGE WITH THIS EXACT COMMAND:
  gh pr merge 1074 --repo nedschorus/nedschorus --merge --delete-branch --match-head-commit 0d55173b2c4e8a9f1b6d3e7a5c9f2b4d8e1a6c3f
```

## Code the new texts need

- `fail()` and `cannot()` print one line today. The new texts have several lines, so each call passes its extra lines, and both functions print every line to stderr before exiting with the same status as today.
- Message 1 fills `{count}` from `$#`.
- Message 23 chooses its lines by whether `reviewDecision` is `CHANGES_REQUESTED`; message 24 chooses its line by the value of `mergeStateStatus`.
- No exit status changes.

## Tests

`scripts/merge-gate-test.py` runs the gate against a stand-in for `gh` and asserts each case's exit status and phrases in stderr. The pull request changes the phrases its cases assert where a text changes, and adds cases for what no case covers today: the argument count in message 1, every line added to messages 2 to 27, both forms of message 23, and each value message 24 names.

## Questions for merge-lane-2

1. Messages 9 to 12 exit 1, `GATE REFUSED`, although the gate could not read GitHub. Should they become `GATE COULD NOT RUN` with exit 2? That changes what the wrapper sees, which is why this document leaves it as it is.
2. Messages 25 to 27: does merge-lane-2 move reviewed-since past new items by posting a review of its own, as the proposed text says, or in another way?
3. Message 24: is `BEHIND` reachable, that is, do the branch's rules on main require an up-to-date branch?
4. The prefix `GATE REFUSED (#1074)` names the pull request by bare number. It is left as it is, since the wrapper may match on it; say if it does not.
