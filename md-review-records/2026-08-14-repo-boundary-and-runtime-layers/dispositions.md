# Dispositions — repo-boundary-and-runtime-layers.md, review of 2026-08-14

Target: `docs/cross-project/repo-boundary-and-runtime-layers.md`, written and reviewed the same day.
Grid: all eight cells returned content. Both defect-hunt cells reported **clean sections: none** — 43 findings from `claude-hunt-good.md`, 40 from `codex-hunt-good.md`, heavily overlapping.

**Verdict, ruled by the user 2026-08-14: hold the document as a draft and finish it after pull request #58 lands.** Not because the findings are unclear, but because the document cannot be made correct before then — see A and G below. Rewriting now would mean doing the component classification twice.

Four claims were spot-checked against the checkout rather than accepted from the reports; results are recorded inline.

## A. The citation is broken on this branch — blocking, and the reason to wait

The document cites `docs/issues/queue/45-session-seat-and-isolation-riders.md § Cloud sessions and claude --teleport` as the evidence for two load-bearing facts. That section exists only on the unmerged branch `seat-launch-first-prompt`. On this branch, cut from main, `grep -c teleport` on that file returns **0**.

So the two facts the whole "case against splitting" rests on are, as far as any reader of main is concerned, unsourced. Raised by `codex-hunt-good` finding 8; verified.

The same branch also supplies the two components the table marks *(pending PR #58)*. Both problems clear when #58 merges and neither can be fixed before.

## B. The component table was built the wrong way — the largest real defect

Rows were classified from filenames, directory placement, and memory. Both reviewers read the actual files and found the classifications do not survive contact with them. Spot-checked:

| File | "nedschorus" occurrences | Verdict |
|---|---|---|
| `.claude/skills/ghi-write/SKILL.md` | 7 | project-specific — row is **wrong** |
| `scripts/git-gatekeeper.py` | 8 | project-specific — row is **wrong** |
| `scripts/md-drift-lint.py` | 0 | genuinely shared — row is right |
| `scripts/handoff-supervisor.py` | 0 | genuinely shared — row is right |

The reviewers' sweeping version — that most of layer 2 is project-specific — overstates it: the picture is mixed. But the method was unsound, so **every row must be re-derived by reading the file**, roughly thirty components. Do this after #58, when the components that arrive with it can be classified in the same pass.

## C. The model and the filing rule contradict each other on concrete files

Found independently by both cells (claude 15, 23; codex 11, 38). The filing rule's first question — *would a different project want this unchanged?* — terminates classification on "no", so every project-specific hook and skill lands in layer 3, while the table files the same files as layer 1. Two halves of one document disagreeing, on named files.

Related and unresolved: the stated deciding criterion for layers ("where it must physically be at the moment it is used") cannot separate layers 2 and 3, since both are files on disk read when wanted. The real layer-3 test in the document is an ownership question, not a location question.

## D. The conclusion changes, and this is the review's most valuable output

If a meaningful share of the supposedly shared machinery is nedschorus-specific *as written*, then the repository split is not blocked on repositories or accounts at all — it is blocked on **parameterising the tools first**. That is a more actionable conclusion than the one the draft reaches, and it only became visible because the reviewers read the files the draft only named.

Carry this into the rewrite as the document's finding rather than as review feedback.

## E. Vocabulary used as if defined

`the walk`, `seat`, `the box` (used at line 3, defined at line 27), `instruction-class`, `walked approval`. Same defect class that dominated the 2026-08-13 review of the seat briefs, so it is a recurring habit rather than a one-off. Note that some of these terms *are* defined in `docs/agents/agent-seat-model.md` — which is itself unmerged in #58, so the fix depends on that landing too.

## F. "Runtime" names two different things

The document defines a runtime as *a place a Claude Code session runs* (three of them), then names layer 1 "Runtime" (a class of component). The title inherits the collision. "Runtime" is exactly the word a future agent greps for, and the hits split between incompatible meanings. Rename one side in the rewrite.

## G. The table claims completeness it does not have

Declared "every component in the repository as of 2026-08-14". Omitted: `README.md`, the root `CLAUDE.md`, `.claude/settings.json` (the file that actually registers the hooks and status line, without which the layer-1 rows do nothing), `entry-manifest.md`, `nc-queue/`, `walk-ledgers/`, `scripts/sanity-checker-attack-experiment.py`, the nine `*-test.py` files, and the document itself. Two included rows describe files not in the repository.

Also: nothing says a new component must be added to the table, or by whom, so it goes stale through ordinary change. And "the manifest" collides with the existing root-level `entry-manifest.md`, against the project's own naming rule — pick an explicit multi-part name.

## H. Overreaching absolutes

The project's own `CLAUDE.md` cautions against absolutes, and the draft is full of them. The ones that do real damage, because arguments rest on them:

- *"A cloud session can reach exactly what is inside the git repository it cloned, and nothing else"* — ignores the network, the container's own tools, and files the session creates. The draft contradicts it two sections later.
- *"Nothing an agent does later can load them"* — false for skills, which load mid-turn on invocation, and which the table itself lists as layer 1. The true claim is narrower: the harness will not re-register a hook or status line mid-session.
- *"A cloud session is bound to one repository"* — true of what teleport requires, not of what a session can read.
- *"Splitting doubles the credential work"* — a single credential scoped to both repositories is the ordinary case, which is the shape `CLAUDE.md` already describes: one program, one credential, one door.
- *"It has no `~/.claude` to install into"* — the intended claim is about persistence and pre-provisioning, not possibility.

## I. Small and certain

`scripts/git-gatekeeper.py` and `scripts/md-drift-lint.py` are mode `-rw-`, not executable. So "a checkout on `PATH`" would not make them runnable by bare name, and the layer-2 definition's `PATH` framing is wrong as written. Verified.

## J. Not the document's to fix

- **The account mapping.** The draft asks which account owns which repository but supplies three identities (two emails, one GitHub login) plus an organisation with no mapping between them, so the question cannot be answered as posed. Restate it precisely; the answer is the user's.
- **Version pinning.** Two facts are pinned to Claude Code 2.1.232 with no re-verification trigger. Decide whether such facts carry an expiry convention — a project-wide question, not this document's.
