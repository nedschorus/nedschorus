# Walk: the topic-branch parent problem, and the one-sentence lane rule fix

Subject: what actually goes wrong when a seat starts its next topic branch, and
the single sentence that would prevent it.

3 items.

---

## Item 1 of 3: The near-miss, in the exact commands

Last night this seat produced four pull requests in a row. After opening the
first one, the working copy was left standing on that first topic's branch,
`launcher-update-step-drop-misleading-warning`.

To start the second topic I typed:

```
git checkout -b launch-claude-mac-update-step-resolves-the-seats-claude origin/main
```

Naming `origin/main` at the end is what made it correct. Had I typed the
ordinary short form instead:

```
git checkout -b launch-claude-mac-update-step-resolves-the-seats-claude
```

git would have started the new branch from wherever the working copy was
standing — which was topic one. The second pull request would then have
contained topic one's commits as well as its own.

Nobody would have been told. Merge-lane would have received a pull request
holding two topics while its description described one. If topic one had been
rejected or reworked, its rejected code would have travelled into main inside
the second pull request.

I typed the long form four times out of four. That is the whole of what stood
between last night and that outcome.

No decision here. This item exists so the rest of the walk has a concrete
failure to refer to.

---

## Item 2 of 3: Why a seat is more exposed to this than an ordinary checkout

In an ordinary repository you finish a piece of work, switch back to the main
branch, and start the next piece from there. Standing on main is what makes the
short `git checkout -b <name>` correct — the new branch inherits main, which is
what you want.

An agent seat cannot do that. Git allows one branch in only one working copy at
a time, and `main` is already checked out in the machine's reference copy at
`~/Projects/nedschorus`. A seat's home is a separate working copy, so it is
refused `main` outright.

That is the actual reason each seat was given a branch named after itself. The
handoff supervisor states it plainly in its own source: an agent's home sits on
its own branch only because git refuses one branch in two working copies, and
nobody chose a long-lived personal branch.

So a seat has no safe place to stand between topics. Once its first topic is
done it is standing on that topic, and the short form of the branch command
becomes wrong — silently.

No decision here either.

---

## Item 3 of 3: The fix — give the seat somewhere safe to stand

The current rule in `CLAUDE.md` says a topic starts on a branch cut from
current main. It says nothing about where the working copy should be standing
when you do that, so the burden falls on remembering to name `origin/main`
every single time.

Proposed addition, one sentence:

> When a topic's pull request is opened, return the seat's home to the seat's
> own branch, fast-forwarded to main; cut every topic from there.

That makes the seat's own branch do the job `main` does in an ordinary
checkout: the place you stand between pieces of work. Four consequences follow,
none of them requiring new machinery:

- The short `git checkout -b <name>` becomes correct by default. The dangerous
  command stops being dangerous.
- The handoff supervisor already fast-forwards a seat's branch between
  sessions when the tree is clean, so it stays current on its own.
- The seat's branch stops being reported as removable by
  `scripts/clean-worktrees.py`, which currently flags it because nothing is
  standing on it.
- Nothing constrains how many topics you hand a seat, and no extra working
  copies are created.

One boundary worth stating: deleting merged topic branches needs no rule. Pull
request 233 landed tooling that reports them at every launch, with the command
to remove them.

`CLAUDE.md` is an agent-instructions file, so this is a proposal. Approving it here is
the walked approval that would let me make the edit.
