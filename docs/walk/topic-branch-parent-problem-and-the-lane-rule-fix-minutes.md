# Minutes: the topic-branch parent problem, and the lane rule fix

Walk document: docs/walk/topic-branch-parent-problem-and-the-lane-rule-fix.md
3 items.

## Item 1 — the near-miss, in the exact commands

processed 2026-09-01 → accepted ("ok - sounds like that should be fixed").
No decision was asked; the item establishes the failure the walk refers to.

Substance: `git checkout -b <name>` creates a branch from HEAD and MOVES the
working copy onto it. So the command that creates topic one leaves you standing
on topic one, and the same command typed for topic two then branches from topic
one rather than main. Last night four topic branches were cut in a row and each
one named `origin/main` explicitly; the short form would have put topic one's
commits inside topic two's pull request with nothing reporting it.

Corrected during discussion: nothing about git's defaults changed and the
worktree is not the cause. The start-point argument has always defaulted to
HEAD. The trap is that the create and the move are one command.

## Item 2 — why a seat is more exposed than an ordinary checkout

processed 2026-09-02 → accepted ("if there is a fix I don't have to").
No decision was asked. Re-presented in full on request, then a question:
whether it is a problem that a seat stays parked on topic x's branch after x's
pull request is opened. Answered — parking loses nothing, since the branch is
already pushed; it is a loaded default, and it misfires two ways. The next
`git checkout -b y` inherits x, and any commit made while parked lands on x,
the branch already under review. The user waived further explanation of the
exposure in favour of the fix, so the story-rewrite the skill offers was not
run.

Substance: an ordinary checkout returns to main between topics, which makes the
short branch command correct. A seat cannot: git allows one branch in one
working copy, and main is held by ~/Projects/nedschorus. That is the only reason
a seat has a branch named after it — stated in handoff-supervisor.py's own
docstring, that an agent's home sits on its own branch only because git refuses
one branch in two working copies.

## Rider answered during item 1 — does the main-gatekeeper fix this or worsen it?

Fixes it, by construction, for ordinary changes. Per
docs/cross-project/main-gatekeeper-design.md: "Ordinary changes use no branches
and no pull requests", and the gate builds its candidate in its own private
workspace starting from main at the computed base, taking only declared paths
from the caller's working copy. Where the caller stands is irrelevant.

Two qualifications, both from that document, and the first NARROWS item 3
rather than cancelling it:

- The pull-request lane survives activation permanently, because the gate
  refuses check-ins touching its own source and that source must still reach
  main. So item 3's rule still applies, to a smaller set of changes.
- It trades this risk for a different one: the declaration is per PATH, not per
  edit, so a stray edit inside a declared file rides into main with it. The
  advisory covers undeclared files, not that.

## Item 3 — presented, revised twice, then re-homed

open 2026-09-02 — the procedure is settled; where it lives changed, and one
question it raises is unanswered.

**First presentation.** Proposed adding to CLAUDE.md's lane rule: "Before
cutting a topic branch, return the seat's home to the seat's own branch and
fast-forward it to main. Cut from there." The user returned four corrections,
all accepted:

1. "Cut" is invented vocabulary. Standard terms: CREATE a topic branch at a BASE
   COMMIT, and switch the working copy onto it. `git checkout -b <name>` does
   both, and with no base commit given it uses wherever the working copy stands.
2. Name `origin/main`, not "main" — the local `main` ref belongs to the other
   working copy and can be stale, so the sequence begins with a fetch.
3. The fast-forward is not unconditionally correct. It is correct when the
   seat's branch carries no commits of its own, and `--ff-only` refuses rather
   than guessing when it does. An unmerged pull request does not affect it: a
   topic's commits live on the topic's branch, not the seat's. The real
   exception is work that BUILDS on an unmerged topic — not a separate topic,
   and wrong to branch from main.
4. "Claude is unreliable" — a sentence of instruction is not a fix. Detection
   and enforcement are needed.

**Revised text**, in the walk document as Item 3 of 3, revised: create every
topic branch from the seat's own branch after fast-forwarding it to current
`origin/main`; work depending on an unmerged topic branches from that topic and
declares the dependency in its pull request. Enforcement named as its own topic:
a script performing the sequence, and a check at `gh pr create` refusing a
branch that carries another open pull request's commits unless the pull request
declares that dependency. The cold read caught a rule conflict in the first
form of that check — it would have refused the stacked branch the rule's own
exception permits — and the declaration is what distinguishes them.

**Ruling: the home changes.** The user ruled the procedure belongs in a
pull-request skill, not CLAUDE.md. Searched: no such skill exists (built skills
are cold-read, ghi-write, handoff, walk-me-through) and no GitHub issue tracks
one, including among the candidate-skill issues #15-#23. It is nonetheless an
already-named component with two responsibilities assigned by landed documents:
the founding plan gives it disposition of durable files ("a durable file reaches
main through a pull request and that is where its fate is decided"), and
docs/issues/142-draft-md-skill-design.md has it invoke `draft-md` for the pull
request description. Both say "once it exists". So two landed designs are
written against a component nothing tracks.

**Consequence: the CLAUDE.md edit is withdrawn.** The lane sentence keeps saying
a topic starts from current main; the procedure lives in the skill. No walked
approval is needed and none was taken — `.walk-approved` was not written.

**Does this conflict with the main-gatekeeper plan?** No. A correction was
required here: the answer is NOT that pull requests largely disappear at
activation. The activation shape the user ruled 2026-08-29 ("14-b is fine. Can
we test it?") is that the GATE OPENS A PULL REQUEST rather than pushing to main,
because main's protection requires an approving review with no account exempt.
Every change reaches main through a reviewed pull request before and after
activation; what changes is who opens it. The founding plan's premise for the
skill's disposition job therefore survives activation intact. Two real
consequences: the branch procedure becomes a minority path, governing only the
gate's own source, which the gate refuses to check in; and issue 142's
assumption that the pull-request skill writes the description of an
AGENT-opened pull request expires.

## Open question carried out of item 3

When the gate opens the pull request, who writes its description, and does the
pull-request skill run before check-in or does the gate invoke `draft-md`
itself? Recorded in nedschorus#236 rather than settled here; #142 needs a
corresponding edit when the gate's check-in interface is built.

## Rulings after item 3, and where they landed

**Where the skill runs.** The user asked whether the gate is the place to run
it when active. It is not: a skill is instructions a session reads, and by the
time the gate holds a request the deliberating session is finished. A gate can
refuse; it cannot deliberate. Division ruled: deliberation in the session,
enforcement at the gate.

**What the gate checks.** User: "If its trivial to detect if the skill has been
run, then the gate should check. That's what gates are good at." Refined and
accepted in this form: the gate checks for the skill's OUTPUT, never for its
execution — a prompt node leaves no trustworthy trace of having run, and any
marker an agent writes to claim it ran is one it can write without running.
Checking execution repeats slice 6's declined review-evidence check. The gate's
existing three-part refusal (named error, facts, next action written for an
agent) carries the pointer back to the skill; `gatekeeper-source-refused` is the
built precedent.

**CPC, and the missing philosophy page.** The user named the project's design
philosophy — code-prompt-code, and the fuller framing that everything is a
state machine whose nodes are code or prompts, each type covering the other's
weakness, either able to invoke the other. Searched: the term is used in commit
4add26d and in ledgers, is listed as undefined in #213's vocabulary sweep item
14, and no philosophy document exists anywhere in the project.

**Filed 2026-09-02, closing the walk's captures:**

- [nedschorus#236](https://github.com/nedschorus/nedschorus/issues/236) — the
  pull-request skill, carrying the branch procedure, the stacked-work
  exception, the disposition and description responsibilities the founding plan
  and #142 already assign it, the output-not-execution rule, and the open
  question above.
- [nedschorus#237](https://github.com/nedschorus/nedschorus/issues/237) — the
  CPC philosophy wiki page, queued for `docs/wiki/queue/`, retiring #213's item
  14 when it lands.
- [nedschorus#238](https://github.com/nedschorus/nedschorus/issues/238) — the
  enforcement: the branch-creation script and the `gh pr create` check.

**The CLAUDE.md edit was withdrawn** and no walked approval was taken;
`.walk-approved` was not written.

## Crash 2026-09-02T17:09Z

The session died without a handoff and was resumed by crash recovery
(nedschorus#120). Nothing was in flight: no background agent, no watched
process, no owed message. All walk files were intact on disk; only the minutes
above were unwritten, and they were reconstructed from the resumed transcript.
Position on resume: item 3 ruled as recorded, awaiting the user's word on
whether to file the pull-request skill's issue through `ghi-write`.

## Session recycle 2026-09-02

The session was recycled and resumed at item 2, which remains presented and
unruled; a recycle is not the user's word, so item 3 was not presented on it.
Item 3's text was corrected in the walk document before presenting, as this
minutes file directed: it now carries the gatekeeper narrowing, names the seat's
home and branch, and drops the claim that the handoff supervisor keeps the seat's
branch current on its own — that fast-forward only runs on a clean tree, and this
walk's own untracked documents keep the tree dirty. The rewritten text was given
the walk's fast-clarify cold read
(docs/walk/topic-branch-parent-problem-and-the-lane-rule-fix-item3-rewrite-suggestions.md);
its remaining questions are edge cases of the proposed rule itself, left for the
user to rule on rather than answered with added qualifiers.

No work was in flight at the recycle.
