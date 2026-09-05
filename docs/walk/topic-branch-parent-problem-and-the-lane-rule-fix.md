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

Nobody would have been told. The merge lane would have received a pull request
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
a time, and `main` is already checked out in this machine's main copy of the
repository, at `~/Projects/nedschorus`. A seat's home is a separate working
copy, so it is refused `main` outright.

That is the actual reason each seat was given a branch named after itself. The
handoff supervisor states it plainly in its own source: an agent's home sits on
its own branch only because git refuses one branch in two working copies, and
nobody chose a long-lived personal branch.

So a seat has no safe place to stand between topics. Once its first topic is
done it is standing on that topic, and the short form of the branch command
becomes wrong — silently.

No decision here either.

---

## Item 3 of 3, revised: The fix — a base the seat can always create from

Proposed addition to the lane rule in `CLAUDE.md`:

> Create every topic branch from the seat's own branch, after fast-forwarding
> that branch to current `origin/main`. Work that depends on an unmerged topic
> is not a new topic: branch it from that topic and say so in its pull request.

The seat's home is this working copy, `~/agents/reboot-test`; its own branch is
`reboot-test`. In commands:

```
git fetch origin
git checkout reboot-test
git merge --ff-only origin/main
git checkout -b <topic-name>
```

The rule today says only that a topic starts from current main. It does not say
where the working copy stands when the branch is created, and `git checkout -b`
uses wherever it stands as the base commit. So correctness rests on naming
`origin/main` by hand every time.

`--ff-only` is the safety. The seat's branch holds no work of its own, so the
fast-forward normally succeeds; a refusal means something is on that branch that
should not be — stop and look. An open pull request does not affect it: a
topic's commits live on the topic's own branch, never on the seat's.

How much this governs. While the git-gatekeeper is dormant, every change reaches
main this way, so the rule covers all of them. Once the gate runs it builds each
change in its own private workspace from main, and most changes need no branch
at all. One pull-request lane survives permanently: the gate refuses to check in
its own source, `scripts/git-gatekeeper.py`, which must still reach main.

The rule states the intent; it does not enforce it. The enforcement — a script
that performs the sequence, and a check at `gh pr create` that refuses a branch
carrying another open pull request's commits unless the pull request declares
that dependency — becomes its own topic.

Approving here lets me make the `CLAUDE.md` edit.
