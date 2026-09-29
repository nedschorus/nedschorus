---
issue: "[pull-request skill: how a change reaches main — durable-file disposition, the description, and topic-branch creation](https://github.com/nedschorus/nedschorus/issues/236)"
---

# pull-request skill: how a change reaches main — durable-file disposition, the description, and topic-branch creation

## Problem

Two landed documents assign work to a "pull-request skill" that does not exist,
each saying "once it exists":

- `docs/cross-project/nedschorus-founding-plan.md` gives it disposition of
  durable files: `ghi-write` disposes an issue, and the pull-request skill
  disposes a durable file, "because a durable file reaches main through a pull
  request and that is where its fate is decided."
- `docs/issues/142-draft-md-skill-design.md` has it invoke `draft-md` to write
  the pull request description, and repeats the disposition assignment.

Searched and NOT FOUND: `gh issue list --state all --limit 100` searched for
"pull request skill", "philosophy OR code-prompt OR CPC", and "branch base
commit worktree" — no issue covers this skill, including among the candidate
skill issues GHI [Candidate skill: define-work — bounded work-definition spec before ambiguous or substantial work](https://github.com/nedschorus/nedschorus/issues/15)-GHI [Candidate skill: eval-agent-change — baseline-vs-candidate A/B with trigger cases and raw-count reporting](https://github.com/nedschorus/nedschorus/issues/23). Built skills are cold-read, ghi-write, handoff,
walk-me-through (`ls .claude/skills/`). So two designs are written against a
component nothing tracks.

A second gap, found while walking the branch problem (below), is that nothing
says how an agent creates a topic branch. That procedure belongs in this skill.

## What the skill owns

Getting a change to main. Four parts:

1. **Disposition of a durable file** — revise an existing document on the
   subject (the default) or write a new one. Assigned by the founding plan.
2. **The pull request description** — invoking `draft-md`. Assigned by GHI [Build draft-md: the drafting-stage skill run before md-review (user-ruled 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/142).
3. **Creating the topic branch**, which nothing currently covers:

   > Create every topic branch from the seat's own branch, after
   > fast-forwarding that branch to current `origin/main`. Work that depends on
   > an unmerged topic is not a new topic: branch it from that topic and say so
   > in its pull request.

   In commands: `git fetch origin`; `git checkout <seat-branch>`;
   `git merge --ff-only origin/main`; `git checkout -b <topic-name>`.

   Why: `git checkout -b <name>` creates the branch at whatever commit the
   working copy stands on and moves the copy onto it. So the command that
   creates topic one leaves the copy standing on topic one, and the same
   command typed for topic two bases topic two on topic one — putting one
   topic's commits inside another's pull request with nothing reporting it.
   A seat cannot stand on main between topics, because git allows one branch in
   one working copy and main is held by the machine's main checkout. The seat's
   own branch is the substitute. `--ff-only` is the safety: the seat's branch
   carries no work of its own, so a refusal means something is there that
   should not be. Near-miss on 2026-09-01: four topic branches were created in
   a row and each named `origin/main` explicitly; the short form would have
   produced the failure.
4. **Recording the outcome on the issue the pull request finishes**, which
   nothing in the path to main triggers today:

   > A pull request that finishes an issue also edits that issue's GHI-MD, in
   > the same pull request. The edit adds an `## Outcome` section saying what
   > was done and by which pull request, and sets `## Next action` to none.
   > So when "Closes" closes the issue at merge, its text already says what
   > happened.

   This is the completion edit `.claude/skills/ghi-write/SKILL.md` already
   requires — "Completion is an edit too: record the outcome in the GHI-MD,
   then close the issue with its reason" — given the moment that triggers it.
   Ruled by the user on 2026-09-29, in walk
   open-items-this-seat-holds-2026-09-24, item 14, with his word "y". The item
   said: "Nothing in the path to main says 'the issue this pull request
   finishes now gets its outcome'", and recommended adding that duty to this
   skill.

   Why: finished work gets recorded somewhere, a commit message or a design's
   header, but not on the issue, so a reader who trusts the issue acts on a
   picture weeks stale.

   - The open-issue sweep walked on 2026-09-21
     (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/open-issue-sweep-into-piles.md`,
     items 1 and 3) found ten GHIs whose finished work their own text never
     recorded: eight finished and still open, and two still open whose landed
     half was invisible on the GHI.
   - Two more since. GHI [The handoff-supervisor resumes a session that died without a handoff, instead of stopping the seat](https://github.com/nedschorus/nedschorus/issues/613)
     was built by PR [The handoff-supervisor resumes a session that died without a handoff](https://github.com/nedschorus/nedschorus/pull/651),
     merged 2026-09-22, and closed only on 2026-09-29. GHI [recover-crashed-seats.py: the six changes ruled 2026-09-02 — exit record, process-identity liveness, parking marker, verified restart, by-hand resume, window](https://github.com/nedschorus/nedschorus/issues/242)
     says in its opening paragraph that change 6 is built — PR [recover-crashed-seats: --open-iterm-window-per-seat launches a recovered seat attached, in its own window](https://github.com/nedschorus/nedschorus/pull/319),
     merged 2026-09-11 — yet its numbered list still gives change 6 without
     "Done".
   - On 2026-09-29, PR [A recovered seat's supervisor runs from the reference clone, not from the checkout the recovery ran from](https://github.com/nedschorus/nedschorus/pull/778)
     closed GHI [recover-crashed-seats: a recovered seat's supervisor runs from whichever checkout the recovery was run from, and stops at its next handoff once that checkout is removed](https://github.com/nedschorus/nedschorus/issues/659)
     automatically through its "Closes" line. It changed only the two
     scripts, so the closed issue's GHI-MD still said under `## Next action`
     that the user decides. Its Outcome was added by hand afterwards, in PR
     [GHI-MD edit for issue 659: recover-crashed-seats: a recovered seat's supervisor runs from whichever checkout the recovery was run from, and stops at its next handoff once that checkout is removed](https://github.com/nedschorus/nedschorus/pull/780),
     still open when this was written.

## Architecture: code-prompt-code

The skill is a state machine whose nodes are code or prompts (see the
philosophy issue this is filed alongside). Deliberation is prose — which
document a change disposes, what the description says. The mechanical branch
sequence is a script. Enforcement is at the gate, which is code.

**The gate checks for the skill's OUTPUT, never for its execution.** A skill
leaves no artifact proving it ran, and any marker an agent writes to say it ran
is one the agent can write without running it. Checking execution was
considered and declined — it repeats the mistake of slice 6's review-evidence
check, designed and then not built
(`docs/issues/3-slice-6-review-evidence-not-built.md`). Checking output is
cheap and honest: a declared durable document whose issue pointer is `none`, or
whose description is empty, refuses on facts the gate already holds. An agent
that produces correct output without the skill passes, which is correct — the
gate's job is that main receives complete work, not that a procedure was
obeyed.

The refusal already has the right shape. Per
`docs/cross-project/git-gatekeeper-design.md`, every refusal carries the named
error, the specific facts, and "the exact next action, written for an agent" —
and `gatekeeper-source-refused` is the built precedent, naming the
pull-request lane as its next action. The new refusal names the document and
says to run this skill and resubmit.

## Interaction with the git-gatekeeper

No conflict. The activation shape ruled 2026-08-29 is that **the gate opens a
pull request rather than pushing to main**, because main's protection requires
an approving review with no account exempt. So every change reaches main
through a reviewed pull request before and after activation; what changes is
who opens it. The founding plan's premise for this skill's disposition job
survives activation intact.

Two consequences:

- The branch procedure becomes a minority path. After activation an agent
  creates a branch only for `scripts/git-gatekeeper.py`, which the gate refuses
  to check in (`gatekeeper-source-refused`). Everything else goes through the
  gate with no branch, and where the caller stands is irrelevant.
- **GHI [Build draft-md: the drafting-stage skill run before md-review (user-ruled 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/142)'s assumption expires.** It assigns this skill the description of an
  agent-opened pull request. After activation the gate opens it, so either the
  skill runs before check-in and hands the gate a description, or the gate
  invokes `draft-md` itself. Resolved when the gate's check-in interface is
  built; GHI [Build draft-md: the drafting-stage skill run before md-review (user-ruled 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/142) needs a corresponding edit then.

## Next action

Do not build the skill yet. The boot-set rule (founding plan, resolved
2026-07-24) is that a skill is pulled when a real task exposes the decision it
encodes. Build the enforcement first — filed separately as the branch-sequence
script and the `gh pr create` check — which has value while the gate is dormant
and keeps it afterward for the lane that survives.


## Name (added 2026-09-05)

The user calls the entry point to this workflow **/push**: "a missing skill used to initiate the design to main workflow" (his words on the vocabulary page, `docs/wiki/queue/213-project-vocabulary.md`). GHI [Four small skills the user named on the vocabulary page: /save, /push, /save-MD, /save-MD-as-draft (name open)](https://github.com/nedschorus/nedschorus/issues/256) records that name with three other small skills he asked for; this issue stays the design home.


## Scope, and the attribution block (user-ruled 2026-09-13)

Keep it small: "a one-off ... tied directly to the PR-gate, so it's not like the
others."

It also owns the commit attribution block, quoted verbatim into any writing
agent's brief — the block reaches a session only through a harness message and
appears nowhere in this repository. Seen failing two ways: a thin brief
(`4b536d6`), and the harness sending a reduced block mid-session.

**Checked 2026-09-19, at the user's direction, whether the gatekeeper has taken
this over: not yet, and the rule stands.** The gatekeeper writes a five-line
trailer at check-in — `Gatekeeper-origin` (the session id from
`CLAUDE_CODE_SESSION_ID`), agent, digest, import, issue — in
`nc-systems/main-gatekeeper/main-gatekeeper.py`. It never writes the
`Co-Authored-By` model line, it stamps only at check-in rather than on every
commit and pull request description, and `CLAUDE.md` still routes merges
through the merge-lane seat "until the gatekeeper activates". The single
overlapping fact is session identity, recorded for a different purpose at a
different moment. **It does become transitional later:** [issue
GHI [Deferred: main-gatekeeper activation shape 2 — a reviewer attached to the gate and an approving identity of its own](https://github.com/nedschorus/nedschorus/issues/357) describes the
activation shape where the gate opens the pull request "with attribution
computed", and GHI [Topic-branch base enforcement: a branch-creation script and a gh pr create check that refuses an undeclared carry of another PR's commits](https://github.com/nedschorus/nedschorus/issues/238)
records the user's 2026-09-18 ruling that the gate stamps a `Claude-Session`
trailer on both the commit and the pull request it composes. So this section is
re-examined when GHI [main-gatekeeper — the single check-in gate (design: nc-systems/main-gatekeeper/main-gatekeeper-design.md)](https://github.com/nedschorus/nedschorus/issues/3)'s
slice has the gate composing pull requests, not before.
