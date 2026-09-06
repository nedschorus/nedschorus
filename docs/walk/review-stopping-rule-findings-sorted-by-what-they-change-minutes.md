# Minutes: the review stopping rule — findings sorted by what they change

Walk document: docs/walk/review-stopping-rule-findings-sorted-by-what-they-change.md
7 items. Opened 2026-09-02.

What this walk is about, for someone who has not read it: the user approved a
rule for when a code-review loop ends — a round that changes no line of code or
test closes it — then asked to have the rule, its sorting of findings, and the
place of nits walked one item at a time. This walk replaces a narrower nit-only
walk that was opened by mistake and moved to docs/walk/superseded/.

## Item 1 — the problem the rule solves

processed 2026-09-02 → next ("y"). No decision was asked. Substance: without a
stopping rule a prose-driven review loop never ends, because each fix is new
text with new defects and prose has no pass/fail oracle; code and tests do, and
the rule is built on that. Evidence cited: the +10/-65 deletion pull request
that drew four rounds over five hours, recorded in CLAUDE.md.

## Item 2 — the rule

processed 2026-09-02 → accepted ("y"). The rule as adopted: a review round
ends the loop when it produces no finding that changes a line of code or a
line of test. A finding is a report with a failure scenario; a report with none
is a nit and does not count. Code is what CLAUDE.md's review-scope rule calls
code, embedded command and code blocks included. Lines changed are counted,
not effort or importance; test lines count the same as code lines; the volume
of commentary and the movement of documents do not count.

## Item 3 — contract findings

open 2026-09-03 — presented; the reopen-both-designs half is uncontested; the
cold-read half is pending a measurement campaign the discussion produced.

Presented 2026-09-02 with the recommendation "reopens both designs and earns
one cold read". The user asked whether a full cold read is proportionate for
small contract changes, proposing a medium read with a threshold (5 lines / 5%)
for the full cold-read run, and ruling that cold reads are for English only, never code.

Side conclusions the discussion produced, all recorded here:

- Three cold-read tiers ARE ruled (MD-skills seat, 2026-08-30/31), found by
  grepping the transcripts at the user's direction: fast = fast-clarify, terra
  low effort, one cell; medium = one good-tier pass + D4, ruled but unpackaged
  (its REWRITING ambition died by measurement — three passes worse than one,
  no configuration reached the user's 35% hand-cut bar — its REVIEW half
  survived); slow = the full cold-read run.
- An independent deduplication of today's three cold-read rounds on the 238 design
  (one fresh agent per round, then Gemini placed by three more) measured unique
  defects per cell: claude-good 34, codex-good 24, codex-floor 21, claude-floor
  1, gemini-3.6-flash 1 (trivial). Best three cells = the full run minus one unsure
  cluster; no two-cell subset holds coverage (loses 10–26%); the ruled
  one-pass medium loses 30–45%. Conclusion: claude-floor is the cold-read run's one
  dead cell; a medium/slow distinction by cell subset does not survive the
  data; the 5-line threshold has no tier to select and was withdrawn.
- Gemini 3.6 Flash as a defect-hunt cell: 19 findings, all real, 17 distinct,
  1 new and trivial; strict subset of claude-good each round; 77–111 s.
- Caveat on all of the above: one document, three rounds; "unique" counts
  distinct defects, not their weight; no ground-truth adjudication of
  true/false positives was done.

The user then asked for a proper campaign: per-cell model + effort + time;
Fable 5.1 added as a hunter; tiers defined by recall — full >90%, faster >75%,
fastest >50% at defects-per-minute — with precision (few false positives) as
the criterion; try max effort when hunting.

DELEGATED 2026-09-03. The user ruled that product quality is the goal and the
assigned agent reads the top combinations' results qualitatively — numbers
shortlist, the reading decides — which keeps METHOD.md §1's ruling rather than
reversing it. Campaign brief:
docs/issues/queue/cold-read-tier-roster-campaign-brief.md. A new Mac seat,
`cold-read-research`, was launched with
docs/agents/cold-read-research-first-prompt.md (the fifth interactive seat —
the user's ceiling). Ground truth for target 4 written to each 238 round's
record directory as dedup-clusters.md with target-snapshot.md. Item 3's
cold-read composition stays open until that seat reports; the walk continues
past it.

## Item 4 — implementation findings

not yet presented.

## Item 5 — prose findings

not yet presented.

## Item 6 — nits and the labelling guard

not yet presented.

## Item 7 — the two guards, and the summary

not yet presented.

## Restart 2026-09-03

The user asked to restart the walk at item 1 ("let's restart the walk at 1"),
after a seat reincarnation and a detour on the context-reincarnation threshold (ruled: 50%
stays) and the launcher passthrough defect (fixed, pull request #245, merged).
Items 1 and 2 are re-presented; their earlier outcomes above stand unless the
user rules otherwise on re-presentation. Item 3's cold-read composition remains
delegated to the cold-read-research campaign.

## Item 1 (re-presented 2026-09-03) — rider: the PR-review graph

Re-presented → next. On this item the user set a direction ("I've had a change
of heart"): the process the stopping rule runs inside. As stated by the user:
an agent, coder 1, is given a component design X to code. If the coder finds
the design seriously flawed, it writes X-coder1-design-issues.md, passes it to
the agent that commissioned it (the originator), and stops. If the design has
nits or minor issues, it notes them in X-coder1-design-nits.md and continues.
Code reviewer 1 is then handed the design and the code (whether it also gets
the notes was left as a question). If the review passes, done; more likely it
produces findings and a design-code loop runs. The test design and test code
form a second loop that works the same way. The user called this the basic
design for the PR-review graph and asked for an assessment. Assessment and
outcome recorded below once given.

## Superseded 2026-09-03

Assessment given on the PR-review graph: it is the process the stopping rule
runs inside, not a change to the rule; the walk's finding classes are its edge
rules. Sharpenings proposed: the coder's "seriously flawed" is the contract
test with a failure scenario per entry; the reviewer receives the nits file;
the reviewer has the same back edge to the originator; the coder's stop check
runs before the test loop, then test code and code in parallel, then a code
review that runs the tests; the originator arbitrates contract-versus-
implementation disagreements. Asked whether to write it up as a design after
the walk or fold it in; the user answered with a third option — a walk of the
graph itself ("/walk-me-through this").

This walk is SUPERSEDED by
docs/walk/pr-review-graph-coder-reviewer-originator-loops.md. Carried
forward: item 1 (next) and item 2 (accepted) stand; item 3's first half —
a contract finding reopens both designs — stands, and its cold-read
composition stays delegated to the cold-read-research campaign; items 4–7
were never presented and are re-presented as the new walk's items 5 and 6.
The files stay in place because the handoff and the campaign brief cite this
minutes path.
