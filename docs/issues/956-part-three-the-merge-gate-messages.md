# Part three: the messages of the merge gate

This document is part three of GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956). The GHI's GHI-MD, `docs/issues/956-every-refusal-and-warning-a-program-hands-an.md`, is part one; part two, `docs/issues/956-part-two-the-git-hooks-messages.md`, covered the git hooks. This part covers every message `scripts/merge-gate.sh` prints. It shows each failure message as merge-lane-2 sees it, proposes the exact words to replace it, and lists the code changes the new words need. None of the proposed wording is built. merge-lane-2 has answered four questions about how it uses the gate, and those answers are folded in below. The next action is one approval-walk with the user, then one pull request, cut from main, that builds what the user approves, with its test cases.

## What a reader needs first

**What the merge gate does.** `scripts/merge-gate.sh` decides whether a pull request may be merged now, and when it may, prints the command that merges it. The gate merges nothing itself. It is called as `scripts/merge-gate.sh <pull request number> <expected head commit, 40 characters> <reviewed-since, YYYY-MM-DDTHH:MM:SSZ>`. It reads GitHub as the merge account, the GitHub account `ned-review-merge`, with that account's token from `$HOME/.config/nedschorus/ned-review-merge.token`. It reads the pull request's head commit, draft flag, review decision and merge state, then three lists of items: the reviews, the inline comments on the diff, and the issue comments, which are the comments in the pull request's conversation. It pins to the newest approving review, the pin: the commit the pin records must be the current head commit. GitHub's review decision must be `APPROVED`, and GitHub's merge state must be one the gate allows. And no review other than the pin, and no comment, may have been posted or edited after reviewed-since.

**reviewed-since.** reviewed-since is the time up to which someone has read the pull request's reviews and comments. The gate accepts a reviewed-since no later than the bound: the later of the pin's `submitted_at` and the merge account's own latest submitted review. The bound exists because a reviewed-since of "now" would count no comment as new. In practice merge-lane-2 reads the reviews and comments, then posts a review of its own as the merge account, an approval or a comment, and passes that review's `submitted_at` as reviewed-since.

**The accounts.** `mac-claude` is the GitHub account the Mac's agent-seats use: it opens their pull requests and posts the independent reviews merge-lane-2 commissions. GitHub refuses an approval from a pull request's author, so on a pull request mac-claude opened, the merge account approves, and on a pull request the merge account opened, mac-claude approves.

**Who reads its messages.** merge-lane-2 runs the gate through the merge seat's wrapper, a script that is not yet in the repository; merge-lane-2 has an open task to move it there. The wrapper exports the merge account's token as `GH_TOKEN` and passes the pull request number, the full head commit and reviewed-since. It runs the gate again, at most 8 times 5 seconds apart, while the gate's output contains "mergeStateStatus is UNKNOWN", and stops on every other nonzero exit status. When the gate passes, the wrapper takes the line after "MERGE WITH THIS EXACT COMMAND:", requires it to be exactly the merge command, and runs it with the same `GH_TOKEN`, so the merge runs as the merge account. `scripts/merge-gate-test.py` also runs the gate, against a test double for `gh`, and asserts phrases of its messages. Those two texts the wrapper matches, "mergeStateStatus is UNKNOWN" and the line "MERGE WITH THIS EXACT COMMAND:" with the command line after it, stay exactly as they are.

**What the gate prints.** Today every failure is one line on stderr, with one of two prefixes, and the exit status matches the prefix:

- `GATE REFUSED (#<number>): ` with exit status 1: the gate read everything and the pull request must not be merged now.
- `GATE COULD NOT RUN: ` with exit status 2: the gate could not decide, because of how it was called, because a tool or the token is missing, or because it could not read or parse what GitHub returned. The two are kept apart because a gate that could not run must never be read as a gate that passed.

Four messages break that rule today: messages 9 to 12, which report a failed read from GitHub, print `GATE REFUSED` and exit 1. The proposal moves them to `GATE COULD NOT RUN` with exit 2; merge-lane-2 confirmed that its wrapper stops on either status, so the change breaks nothing.

A pass prints three lines on stdout and exits 0. The proposed failure texts are several lines each; the first line of each keeps its prefix.

When `gh` or `jq` fails, its own error, if it prints one, appears on stderr just above the gate's line, because the gate captures only their standard output.

**The four questions.** As in parts one and two, a message is complete when the message says:

1. What was refused or found, naming the file or the command.
2. Why: the rule being enforced, or what goes wrong if the agent goes ahead.
3. What to do instead, as an instruction.
4. Under which condition each instruction applies, when the message gives more than one.

**When to tell the user.** A message tells merge-lane-2 to tell the user only when merge-lane-2 cannot clear the failure itself: the token, a tool missing from the machine, a read or a parse that fails again on one rerun, or a state the gate does not expect.

**Where the list comes from.** Part one's audit, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/MD-skills/refusal-and-warning-message-audit-2026-10-01.md`, counted 27 distinct failure texts from the merge gate and found 7 of them complete. Every message below was read again from main at the commit [Merge pull request #1075 from nedschorus/ghi-956-edit-ghipairef15a4328a1316b6](https://github.com/nedschorus/nedschorus/commit/c16466b6), and the line numbers are main's at that commit. There are still 27: 12 `GATE COULD NOT RUN` texts, one of them printed from four places, and 15 `GATE REFUSED` texts. This document proposes new text for 26 of them, including ones the audit counted complete, where reading them against merge-lane-2's use found a gap; it adds one message, 28, for a parse the gate does not check today.

## The messages, one at a time

In the examples, the pull request is 1074, the expected head commit is `0d55173b2c4e8a9f1b6d3e7a5c9f2b4d8e1a6c3f`, and reviewed-since is `2026-10-05T15:58:12Z`, except where an example says otherwise.

### Calling the gate

#### 1. Wrong number of arguments

**When merge-lane-2 sees this.** The wrapper calls the gate with two arguments, or four.

**Today** (`scripts/merge-gate.sh:139`):

```
GATE COULD NOT RUN: usage: merge-gate.sh <pr-number> <expected-head-sha> <reviewed-since-iso8601>
```

**What the reader cannot tell from the text.** How many arguments it passed, and what each must hold.

**Proposed text** (`{count}` is the number of arguments given):

```
GATE COULD NOT RUN: merge-gate.sh takes exactly three arguments and was given {count}.
Call it as: scripts/merge-gate.sh <pull request number> <the head commit, all 40 characters> <reviewed-since: the submitted_at of your latest review as the merge account, or of the pin if that is later>
```

#### 2 and 3. The expected head commit is not a full commit hash

**When merge-lane-2 sees this.** Message 2: the value holds a character other than `0-9` and `a-f`, such as a capital letter, `0D55173B…`. Message 3: the value is a short hash, such as `0d55173b`.

**Today** (`scripts/merge-gate.sh:148` and `:150`):

```
GATE COULD NOT RUN: expected-head-sha is not a full 40-character hex sha: 0D55173B2C4E8A9F1B6D3E7A5C9F2B4D8E1A6C3F
GATE COULD NOT RUN: expected-head-sha is 8 characters, not 40: 0d55173b
```

**What the reader cannot tell from the text.** Where to get the full hash.

**Proposed text** (each keeps its first line, and gains a second):

```
GATE COULD NOT RUN: expected-head-sha is not a full 40-character hex sha: {value}
Pass the head commit's full hash in lower case, as gh pr view {pr} --json headRefOid --jq .headRefOid prints it, then run the gate again.
```

```
GATE COULD NOT RUN: expected-head-sha is {length} characters, not 40: {value}
Pass the head commit's full hash in lower case, as gh pr view {pr} --json headRefOid --jq .headRefOid prints it, then run the gate again.
```

#### 4. reviewed-since is not a time in GitHub's form

**When merge-lane-2 sees this.** The call passes `2026-10-05T15:58:12+00:00`, `2026-10-05T15:58:12.000Z`, or a value of the right shape that is no real time, such as `2026-13-05T15:58:12Z`.

**Today** (`scripts/merge-gate.sh:154`):

```
GATE COULD NOT RUN: reviewed-since must be exactly YYYY-MM-DDTHH:MM:SSZ, the form GitHub returns: 2026-10-05T15:58:12+00:00
```

Today a value of the right shape that is no real time passes this check, and fails later as message 14.

**What the reader cannot tell from the text.** What to pass instead. The form is strict because the gate compares times only in that form; a time with an offset once counted too few comments and passed.

**Proposed text** (the check also refuses a value that is no real time; see "Code the new texts need"):

```
GATE COULD NOT RUN: reviewed-since must be a real time in exactly the form YYYY-MM-DDTHH:MM:SSZ, which GitHub returns: {value}
Pass the review's submitted_at exactly as GitHub returns it, then run the gate again.
```

### The machine

#### 5. jq is not on PATH

**Today** (`scripts/merge-gate.sh:142`):

```
GATE COULD NOT RUN: jq is not on PATH. Put jq on PATH, then rerun the gate.
```

**What the reader cannot tell from the text.** What to do when jq is not installed on the machine at all.

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

**What the reader cannot tell from the text.** Why the gate stops rather than reading GitHub with the credential `gh` already holds, and what to do. Without the token, `gh` would read as its stored account, which on ned-box is `ubuntu-claude`, not the merge account, so the gate refuses to run. Only the user manages the token.

**Proposed text** (each keeps its first line, and gains two):

```
GATE COULD NOT RUN: could not read the merge account's token at {path}
The gate reads GitHub only as the merge account, ned-review-merge, and stops rather than read as gh's stored account.
Tell the user this message: only the user can restore the token.
```

```
GATE COULD NOT RUN: the token file {path} is empty
The gate reads GitHub only as the merge account, ned-review-merge, and stops rather than read as gh's stored account.
Tell the user this message: only the user can restore the token.
```

### Reading and parsing what GitHub returned

#### 9 to 12. A list could not be read

**When merge-lane-2 sees this.** A `gh` call exits nonzero: GitHub does not answer, the token is refused, a later page of a list fails, or the pull request number does not exist (message 9 only).

**Today** (`scripts/merge-gate.sh:167`, `:180`, `:219` and `:221`), exit status 1:

```
GATE REFUSED (#1074): could not read pull request state
GATE REFUSED (#1074): could not read the review channel for the approving commit
GATE REFUSED (#1074): could not read the inline comment channel
GATE REFUSED (#1074): could not read the issue comment channel
```

**What the reader cannot tell from the text.** That the gate could not run, though it says it refused; where gh's error is; what to do; and when to tell the user.

**Proposed text** (each moves to `GATE COULD NOT RUN` with exit status 2; message 9 gains one more line):

```
GATE COULD NOT RUN: could not read pull request {pr}'s state; any error gh printed is just above this line.
If gh's error says the pull request was not found, check the number you passed, then run the gate again.
Otherwise run the gate again once; if it fails the same way, tell the user this message and gh's error.
```

```
GATE COULD NOT RUN: could not read the issue comments of pull request {pr}; any error gh printed is just above this line.
Run the gate again once; if it fails the same way, tell the user this message and gh's error.
```

Messages 10 and 11 take the second form, naming the reviews and the inline comments.

#### 13 to 16. A list could not be parsed, or a time could not be compared

**When merge-lane-2 sees this.** `jq` exits nonzero on what `gh` returned, or on the times it compares. jq's own error, if it prints one, is just above.

**Today** (`scripts/merge-gate.sh:185`, `:200`, `:233` and `:252` print the first; `:203`, `:241` and `:245` the others):

```
GATE COULD NOT RUN: could not parse the review channel
GATE COULD NOT RUN: could not compare reviewed-since against 2026-10-05T15:58:12Z
GATE COULD NOT RUN: could not parse the inline comment channel
GATE COULD NOT RUN: could not parse the issue comment channel
```

**What the reader cannot tell from the text.** Where jq's error is, what to do, and when to tell the user.

**Proposed text** (each keeps its first line, and gains two):

```
GATE COULD NOT RUN: could not parse the review channel
Any error jq printed is just above this line.
Run the gate again once; if it fails the same way, tell the user this message and jq's error.
```

The other three take the same two lines after their own first line.

#### 28. The pull request's state could not be parsed (new)

**When merge-lane-2 would see this.** `gh pr view` succeeds but returns something jq cannot parse. Today the four reads at `scripts/merge-gate.sh:170-173` go unchecked, the head commit reads empty, and the gate refuses with message 20, "head moved", which names the wrong cause.

**Proposed text:**

```
GATE COULD NOT RUN: could not parse pull request {pr}'s state
Any error jq printed is just above this line.
Run the gate again once; if it fails the same way, tell the user this message and jq's error.
```

### The pin

#### 17. No approving review

**When merge-lane-2 sees this.** Pull request 1074 has no review with the state `APPROVED`, because it has no reviews yet or none approves.

**Today** (`scripts/merge-gate.sh:186`):

```
GATE REFUSED (#1074): no APPROVED review found
```

**What the reader cannot tell from the text.** Why, and what to do in each case.

**Proposed text:**

```
GATE REFUSED (#{pr}): no APPROVED review found; the gate prints a merge command only for a commit an approving review covers.
If the head commit has not been reviewed yet, commission its review, and run the gate again once the head commit is approved.
If its review found a defect, do not merge until the defect is fixed and the new head commit is approved.
If its review found no defect, approve the head commit as an account other than the pull request's author: the merge account, or mac-claude when the merge account opened the pull request. Then run the gate again.
```

#### 18. The pin records no commit

**When merge-lane-2 sees this.** The pin's `commit_id` is empty, which GitHub is not known to do.

**Today** (`scripts/merge-gate.sh:192`):

```
GATE REFUSED (#1074): the approving review records no commit_id to pin to
```

**What the reader cannot tell from the text.** Which review, and what to do.

**Proposed text** (`{review_link}` is the pin's link, `https://github.com/nedschorus/nedschorus/pull/{pr}#pullrequestreview-{id}`, built from the id the gate already holds):

```
GATE REFUSED (#{pr}): the approving review {review_link} records no commit_id, so the gate cannot tell which commit it approved.
Do not merge. Tell the user this message.
```

#### 19. reviewed-since is later than the bound

**When merge-lane-2 sees this.** The call passes reviewed-since `2026-10-05T16:30:00Z`, and the bound is `2026-10-05T15:58:12Z`.

**Today** (`scripts/merge-gate.sh:204`):

```
GATE REFUSED (#1074): reviewed-since 2026-10-05T16:30:00Z is later than 2026-10-05T15:58:12Z, the approval or the merge account's own latest review. Rerun with a reviewed-since no later than 2026-10-05T15:58:12Z.
```

**What the reader cannot tell from the text.** Why the bound exists, and that a later bound needs a review of its own.

**Proposed text:**

```
GATE REFUSED (#{pr}): reviewed-since {since} is later than {bound}, the later of the pin and the merge account's own latest review; the gate accepts a reviewed-since only up to a review that records someone read the pull request.
Run the gate again with a reviewed-since no later than {bound}.
If you have read the pull request after {bound}, post a review as the merge account saying so, then run the gate again with that review's submitted_at.
```

### The head commit and GitHub's state

#### 20. The head commit moved

**When merge-lane-2 sees this.** The call names `0d55173b…`, and the head commit is now `9a1c4e2b…`: the author pushed after the review was commissioned, or the call passed an old or a wrong hash.

**Today** (`scripts/merge-gate.sh:206`):

```
GATE REFUSED (#1074): head moved: reviewed 0d55173b2c4e8a9f1b6d3e7a5c9f2b4d8e1a6c3f, now 9a1c4e2b7d8f3a6c5e1b9d2f4a7c8e3b6d1f5a2c
```

**What the reader cannot tell from the text.** What to do.

**Proposed text:**

```
GATE REFUSED (#{pr}): head moved: you passed {expected}, and the head commit is now {head}.
If an approving review covers {head}, run the gate again with {head} as the expected head commit and a reviewed-since from after you read that review.
Otherwise, have {head} reviewed and approved, then run the gate again the same way.
```

#### 21. The pin covers an older commit

**When merge-lane-2 sees this.** The call names the current head commit, `9a1c4e2b…`, but the newest approval covers `0d55173b…`.

**Today** (`scripts/merge-gate.sh:208`):

```
GATE REFUSED (#1074): the approval covers 0d55173b2c4e8a9f1b6d3e7a5c9f2b4d8e1a6c3f but the head is now 9a1c4e2b7d8f3a6c5e1b9d2f4a7c8e3b6d1f5a2c. Review and approve 9a1c4e2b7d8f3a6c5e1b9d2f4a7c8e3b6d1f5a2c before merging.
```

**What the reader cannot tell from the text.** Which account may approve: the merge account cannot approve a pull request it opened.

**Proposed text:**

```
GATE REFUSED (#{pr}): the approval covers {approved} but the head commit is now {head}.
Have {head} reviewed, and approved by an account other than the pull request's author, then run the gate again.
```

#### 22. The pull request is a draft

**Today** (`scripts/merge-gate.sh:209`):

```
GATE REFUSED (#1074): pull request is a draft
```

**What the reader cannot tell from the text.** Why, what to do, and when to stop.

**Proposed text:**

```
GATE REFUSED (#{pr}): pull request is a draft pull request, which its author has marked as not ready to merge.
Ask the pull request's author whether it is ready, through the pull request's agent-seat or on the pull request.
Until the author marks it ready for review, do not merge it; then run the gate again.
```

#### 23. GitHub's review decision is not APPROVED

**When merge-lane-2 sees this.** Most often, an earlier review requested changes and still stands. GitHub reports `CHANGES_REQUESTED` until that review is dismissed, or until the same reviewer approves.

**Today** (`scripts/merge-gate.sh:210`):

```
GATE REFUSED (#1074): reviewDecision is CHANGES_REQUESTED, not APPROVED
```

**What the reader cannot tell from the text.** What to do for each value.

**Proposed text.** The first line is:

```
GATE REFUSED (#{pr}): reviewDecision is {decision}, not APPROVED, so GitHub does not count this pull request as approved.
```

For `CHANGES_REQUESTED`, these lines follow:

```
A review requesting changes still stands.
If its findings have been fixed, or answered with a reason that shows they do not hold, dismiss that review with a reason naming the fix or the answer, then run the gate again.
Otherwise, do not merge.
```

For `REVIEW_REQUIRED`:

```
GitHub's rules on main require an approving review it has not counted: get one, then run the gate again.
```

For any other value, including an empty one:

```
Read the pull request on GitHub; if it shows no reason a merge is refused, tell the user this message.
```

#### 24. GitHub's merge state is not one the gate allows

**When merge-lane-2 sees this.** GitHub reports a mergeStateStatus other than `CLEAN`, `UNSTABLE` or `HAS_HOOKS`, the three values the gate allows.

**Today** (`scripts/merge-gate.sh:213`):

```
GATE REFUSED (#1074): mergeStateStatus is DIRTY
```

**What the reader cannot tell from the text.** What the value means and what to do.

**Proposed text.** The first line stays exactly as today, because the wrapper retries on its text when the value is `UNKNOWN`:

```
GATE REFUSED (#{pr}): mergeStateStatus is {merge_state}
```

Then one line, by value:

```
UNKNOWN: GitHub has not computed it, or the pull request is already merged or closed. If the pull request is open, run the gate again in a minute; if it still reads UNKNOWN five minutes later, tell the user this message.
DIRTY: the branch conflicts with main. Tell the pull request's author; the author clears the conflict as CLAUDE.md says, and the new head commit then needs its own approving review.
BEHIND: the branch is behind main. Tell the user this message.
BLOCKED: a branch rule on main blocks the merge, such as a required check that failed or is still running. Read the pull request's checks on GitHub: if one is running, run the gate again when it finishes; if one failed, tell the pull request's author; if you find no cause, tell the user this message.
For any other value, read the pull request on GitHub; if you find no cause, tell the user this message.
```

### New activity since reviewed-since

#### 25 to 27. Comments or reviews posted or edited since reviewed-since

**When merge-lane-2 sees this.** After reviewed-since, someone posted or edited an inline comment, an issue comment or a review: for example, the author answering a finding, or a reviewer editing a comment to add one. The gate checks the inline comments, then the issue comments, then the reviews, and stops at the first that has any, so a message names only one of the three.

**Today** (`scripts/merge-gate.sh:254`, `:255` and `:256`):

```
GATE REFUSED (#1074): 2 NEW inline comment(s) since 2026-10-05T15:58:12Z -- read them before merging
GATE REFUSED (#1074): 1 NEW issue comment(s) since 2026-10-05T15:58:12Z -- read them before merging
GATE REFUSED (#1074): 1 NEW review(s) since 2026-10-05T15:58:12Z -- read them before merging
```

**What the reader cannot tell from the text.** That an edit counts, that the other two lists may hold items too, and what to do after reading. Reading alone does not clear the refusal: reviewed-since moves only up to a review that records the reading, as message 19 says.

**Proposed text** (each changes "NEW" in its first line to "posted or edited", and gains three lines):

```
GATE REFUSED (#{pr}): {count} inline comment(s) posted or edited since {since} -- read them before merging
Read everything posted or edited since {since}: the inline comments, the issue comments and the reviews.
If any raises a finding, do not merge until the finding is fixed, or answered with a reason that shows it does not hold; a fix moves the head commit, which then needs its own approving review.
When nothing is left open, post a review as the merge account saying what you read, check that nothing was posted between your reading and that review; if something was, read it and repeat from the first line. Then run the gate again with the review's submitted_at as reviewed-since.
```

The other two take the same three lines after their own first line.

### The pass

**Today** (`scripts/merge-gate.sh:258`, `:261` and `:262`), on stdout, exit status 0:

```
gate passed (#1074): approved commit 0d55173b2c4e8a9f1b6d3e7a5c9f2b4d8e1a6c3f by mac-claude at 2026-10-05T15:58:12Z, APPROVED, CLEAN, no new channel activity since 2026-10-05T15:58:12Z
MERGE WITH THIS EXACT COMMAND:
  gh pr merge 1074 --repo nedschorus/nedschorus --merge --delete-branch --match-head-commit 0d55173b2c4e8a9f1b6d3e7a5c9f2b4d8e1a6c3f
```

**What the reader cannot tell from the text.** That the merge command must run as the merge account. The gate exports the token only inside its own process; the merge seat's wrapper exports it too, so its merges run as `ned-review-merge`, but an agent that ran the printed command in another shell would merge as `gh`'s stored account there.

**Proposed text.** The three lines stay exactly as they are, because the wrapper finds the line "MERGE WITH THIS EXACT COMMAND:" and takes the line after it as the command; one line is added after them:

```
Run that command with GH_TOKEN set to the merge account's token, {token_file}, so the merge runs as ned-review-merge.
```

## Code the new texts need

- `fail()` and `cannot()` print one line today. Each call passes its extra lines, and both functions print every line to stderr, then exit with their status as today.
- Messages 9 to 12 call `cannot()` instead of `fail()`, so they exit 2.
- The four reads of the pull request's state at `:170-173` are checked, and a failure calls `cannot()` with message 28.
- The reviewed-since check at `:152-155` also runs `jq` with `fromdateiso8601` on the value, so a value of the right shape that is no real time is refused there as message 4.
- Message 1 fills `{count}` from `$#`; message 18 builds its link from `approval_id`; message 23 chooses its lines by `reviewDecision`; message 24 chooses its line by `mergeStateStatus`.
- The pass gains one line after the merge command, filling `{token_file}` from `$TOKEN_FILE`.
- No other exit status changes, and the three pass lines and the line "mergeStateStatus is {merge_state}" do not change.

## Tests

`scripts/merge-gate-test.py` runs the gate against a test double for `gh` that replays captured GitHub responses, and asserts each case's exit status and phrases of its output. The pull request:

- changes the asserted phrases where a first line changes, and asserts each added line of messages 1 to 28 in at least one case;
- changes the cases for messages 9 to 12 from asserting a refusal, exit status 1, to asserting that the gate could not run, exit status 2;
- adds cases for message 1's count, message 28, a reviewed-since that is no real time, both forms of message 23 for which a capture exists, and the `UNKNOWN`, `DIRTY` and `BLOCKED` lines of message 24, which have captures; `BEHIND` has none, and the suite's rule is that no fixture is typed, so `BEHIND` gets no case;
- updates the source text its mutations quote, so each mutation still finds its target: `TOKEN_BLOCK`, which the mutation "the token read with export's status" replaces, and the two read checks the mutations "without the inline comment channel's read check" and "without the issue comment channel's read check" quote, which change from `fail` to `cannot`.
