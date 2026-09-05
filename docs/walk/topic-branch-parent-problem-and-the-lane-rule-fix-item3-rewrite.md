# Item 3 of 3, revised: The fix — a base the seat can always create from

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
