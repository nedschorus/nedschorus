# git-gatekeeper: record of its first live check-in

**What this file is.** The payload of the first check-in ever performed by
`scripts/git-gatekeeper.py` against the real repository. Its content is
incidental; its existence is the evidence. The specification is
`docs/cross-project/git-gatekeeper-design.md`.

**Why it exists.** The gate had been built through all five slices and exercised
by a suite of over two hundred cases, but every one of those cases ran against
throwaway repositories. No one had ever run the program end to end against
`nedschorus` itself, so "the gate works" rested on tests rather than on an
observation. This check-in closes that gap: if this file is on `main` and its
commit carries the trailers below, the program's whole path — screening,
construction, trailer stamping, and the push — ran for real.

**When and under what authority.** 2026-08-18, at the merge-lane seat, on the
user's explicit instruction in that seat's own session. The project's standing
rule is that agents do not push to `main`; the interim lane routes work through
pull requests reviewed at the merge-lane seat. This commit is a deliberate,
authorized exception for the purpose of testing the gate, not a change of that
rule. The gate remains dormant, and the interim lane continues.

**What to expect on this commit.** It reaches `main` as a direct push rather
than through a pull request, because pushing straight to `main` is what the gate
does by design — it is the permanent path that pull requests are standing in for.
Two consequences worth recording so a later reader is not misled:

- It is the first commit on `main` to carry a `Gatekeeper-agent:` trailer. Every
  earlier commit predates the gate ever running, so a trailer-absence audit run
  over history before this date will find nothing, and that is expected rather
  than a finding.
- It appears in GitHub's repository activity log as a write to `main` that did
  not arrive by pull request. Any bypass check reading that log will see it. It
  is an authorized exception, and this file is the record explaining it.
