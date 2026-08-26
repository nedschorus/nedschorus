# The cold read — design of a code-prompt-code system

Status: design, revised 2026-08-25 from the 2026-08-05 encode plan (that plan is fully built; its text is in git history at `git show 9d78cf8:docs/drafts/cold-read-tooling-design.md`). Everything this document says about the built instrument is a pointer to code, which is the normative description; what it carries is what code cannot: the rulings and their reasons, the two modes, the triage protocol, the hooks that are proposed and not built, and the questions still open. Rulings are stamped with their date; unstamped proposals are the author's and bind nothing until the user rules.

## What the cold read is

A cold read gives one document to reviewers who know nothing but its text, and collects what each sentence made them think it meant and what defects they found. It exists because the documents this project writes are read by agents with no history — a skill, a wiki page, a design, an issue body, a pull-request description — and the author is the worst judge of whether such a reader will understand the text, having watched every sentence form. The instrument was called `md-review` until 2026-08-25, when the user renamed it: "the md-review is misnamed. I think it should be called cold-read."

The user's description of the shape this design follows (2026-08-25): "a interwining of code and prompts — which is a complex, non obvious and very powerful combo, but one agents are not familiar with and not trained to handle. Yes — we need to handle combos with care." He named the shape code-prompt-code. In one sentence: a script composes the prompt from a fixed template plus the facts of this run, launches one agent per cell, and checks the agent's answer mechanically — so the agent does only the judgment in the middle, and the code does the setup, the delivery and the checking.

## The three layers, and who owns what

| Layer | What it does | Where it lives |
|---|---|---|
| Code, before | Refuses an unreviewable target; freezes the target by fingerprint; creates the run's record directory; runs the reference pre-pass; composes eight prompts from two templates; launches eight cells across two runtimes, two passes and two tiers | `scripts/cold-read-grid.py`, `scripts/cold-read-cell-common.py`, the two cell launchers |
| Prompt | The reviewer's judgment: restate every sentence (restate pass), or find defects in nine classes and quote each (defect-hunt pass) | `.claude/skills/cold-read/prompts/restate.md`, `defect-hunt.md` |
| Code, after | Checks that the report was written, and only the report; recovers a report written to the wrong place; announces a model fallback; stamps provenance and cost; checks the target did not change; keeps the record | the same scripts |
| Skill text | What the commissioning agent does with eight reports: the triage protocol, in the mode the document calls for | `.claude/skills/cold-read/SKILL.md` |
| The user | Rules, in the open mode; is reached by one question at a time in the closed mode | — |

The dividing rule: anything with one right answer is code. A rule that an agent must obey the same way every time — write to this path, write nothing else, do not change the target, name the model that actually ran — is enforced by the script, never requested by the prompt alone; the prompt still says it, so the reviewer knows, but the script is what makes it true. Judgment stays with an agent: what a sentence means, whether a passage is defective, whether two findings are the same defect, which fixes need a ruling. Rulings stay with the user.

## Two modes, set by who reads the result

The user's words (2026-08-25): "we discussed cold-read both as an open ended skill (for some things) and a self contained or loop skill for other things I generally don't want to read (PR descriptions, initial GHIs, maybe some other stuff). But we certainly left that ambiguous or contradictory, so we should fix that."

**Open cold read** — the user will read or rule on the document: a skill, a wiki page, a design, a plan, notes compiled for his review. The findings are walked with him under the triage protocol below.

**Closed cold read** — the user will not read the document; an agent is about to post it for other readers. Two kinds of text are closed today: a pull-request description, and an issue body or comment an agent files. The commissioning agent applies the findings itself, then posts. The user ruled the principle for issue bodies on 2026-08-25 ("I often say make a GHI, which will write MD type text, and I have not been reviewing that text or even md-reviewing it, so that text should be automatically MD reviewed") and the PR case the same day, as a standing rule of the MD-skills session: every text an agent writes for a naive reader is cold-read before it posts, PR descriptions included. The first closed read ran on PR #167's description that afternoon: thirteen findings applied before it posted.

Proposed, not ruled: the test governs the list. A PR description or agent-filed issue comment is closed unless the user has said he will read that particular one; any document not on the list is open — when in doubt, the user sees it.

The reviewers' prompts are the same in both modes. The mode changes what the commissioning agent does with the reports, not what the reviewers are asked; the defect-hunt prompt's bar — explain each finding "completely enough that the author can fix it without asking you anything" — serves both. One difference is known and accepted as a proposal: a PR description's real reader has the diff beside it, so a closed-read reviewer may flag as undefined a term the diff defines; on 2026-08-25 such findings were still worth applying ("the two runtimes" had no antecedent even with the diff in view).

## The triage protocol — both modes

The user's description of what the good agents do, which this protocol writes down (2026-08-25, his words):

> they report their simple or quick fixes for me to approve as a batch (or not), then if there are hard things to fix, things that don't make sense, design flaws or big problems, I'd present them next, probably one at a time, as they can actual change the md in a way that requires a rewrite, then go down the line from big to small, but batch up points or items or changes that are about the same concept or problem or idea or thing. They present the reported problem and their proposed solution (which could be to ignore the reported problem — which I usually reject as usually simple wording changes, clause removal or de-conflating should be done — ignoring problems is asking for future problems — which I don't think we stress enough to agents — they don't have theory of mind so they are bad at this)

1. **The reports are data.** Eight reviewers agreeing is weight, not a verdict, and one reviewer alone can be right ("if a bunch of agents complain that is not 100% truth, but it is data" — user, 2026-08-25). A reviewer's misreading is evidence about the text, not about the reviewer: the author knowing what a sentence meant is not evidence that a reader will, and an agent's own confidence that "the reader will get it" is the judgment agents make worst.
2. **Quick fixes first, as one batch.** A wording change, a clause removed, two ideas separated, a missing antecedent supplied, a broken reference repaired. In the open mode the batch is presented for approval, applied so he sees it as one step; in the closed mode it is applied.
3. **Hard items next, one at a time, biggest first.** A finding that changes what the text rules, a contradiction that needs a rewrite, a case the text does not cover. Items about the same concept are batched as one item. Each is presented as the reported problem and the proposed solution.
4. **"Ignore" is a proposal, never a default.** In the open mode it goes to the user like any other proposal, and he usually rejects it. In the closed mode there is no one to reject it, so it is not available: a finding is either fixed or brought to the user as one question, and the loop goes on without waiting for the answer — the post is not held; his answer is applied as an edit when it comes. Every disposition is written in the run's dispositions file, so a record of what was not fixed and why exists whether or not he was there.
5. **The closed loop is bounded.** After the fixes are applied the read runs again on the changed text; it stops when a round applies nothing, or after the second round — one stubborn ambiguity must not run the loop without end.
6. **When a round changed anything in the open mode, the agent opens the file for him** (`open <path>`, which the Mac hands to Typora) and says in one line what changed, before asking him to push it (user-ruled 2026-08-25, walk item 5c).

## Hooks — where a cold read is triggered, and by what

Today every cold read is started by an agent deciding to start one. The rulings above make three of them automatic, and automation here means a hook: a program that runs at the moment the text is about to leave the agent's hands and refuses to let it go unread. All four below are proposed and not built; each names the ruling it enacts. Rulings live in the entries; nothing here is a build order.

1. **Issue bodies and comments** — ruled 2026-08-25 (the GHI words above). Interim: a step in the ghi-write skill, before its file and edit commands. When nedschorus#46's write tool (`scripts/ghi-issue-write.py`, not yet built) exists, the tool itself refuses a body file with no cold-read record whose fingerprint matches the file.
2. **Pull-request descriptions** — the standing rule of 2026-08-25. A PreToolUse hook on Bash (the same mechanism as `scripts/synthetic-keystroke-guard-hook.py`, registered in `.claude/settings.json`) that recognizes `gh pr create` and `gh pr edit` with `--body-file`, and denies the command unless a cold-read record exists for that file with a fingerprint matching its current content, printing the command that produces one. The same hook covers `gh issue create` and `gh issue edit --body-file`, which closes hook 1 by code before the write tool exists. Candidate name: `.claude/hooks/cold-read-gate-hook.py` (no collision as of 2026-08-25).
3. **The push gate** — ruled 2026-08-25 (walk item 5c, part 1): a document lands on main only if the hash of its reviewed content — body plus prose frontmatter fields, script-written fields stripped — equals the hash the last record stamped; mismatch or no record means a full cold read now, without asking. Its permanent home is the git-gatekeeper's check-in; while the gate is dormant, the PR hook above checks each MD file in the PR's diff the same way.
4. **The pre-user gate** — the single zero-context read that walk-me-through and draft-md already require before proposed instruction text reaches the user: one fresh reader, no conversation history, handed only the text plus CLAUDE.md, asked what it means, where it stumbles, and what situation it leaves without a rule. Today each agent composes that prompt by hand, a repeatable task with one right answer. Proposed: a fixed prompt and a record, kept the way grid records are kept — a separate surface for a separate moment, not a reduction of the eight-cell grid, which the user kept whole on 2026-08-25 ("I'm happy with the 8 attacks or cells"). Measured 2026-08-25 on the two-modes skill draft: one Sonnet reader at high effort, about seven minutes and 33,000 tokens, nine stumbles and five uncovered cases found.

## What the code enforces today

Each row is a rule the script makes true; the script's own comments and tests carry the mechanism.

| Rule | Enforced in | Since |
|---|---|---|
| A target whose name ends in `-log`, `-report` or `-capture` is refused, naming the rule (nedschorus#152) | `cold-read-grid.py`, `UNREVIEWABLE_TARGET_GENRE_SUFFIXES` | 5d2acae |
| The target is fingerprinted before launch and after the last cell; a change marks every report and exits 3 | `cold-read-grid.py`, `target_fingerprint` | 5d2acae |
| The reviewer writes its report to a file; chat output is discarded; a missing or empty report is a failed cell, never a stub | `cold-read-cell-common.py` | PR #167 (closes #164) |
| Every file of a run carries the run's name; a report found under its exact name elsewhere in `cold-read-records/` is recovered and announced; a concurrent run's report can never match | `cold-read-cell-common.py`, `recover_near_miss_report` | 0763751 |
| A model fallback is printed on the grid's output (`FELL BACK:`), not only inside the stamp | `cold-read-grid.py` | 9d78cf8 |
| A cell that changed any file other than its report is reported (`STRAY WRITE:`), on both runtimes | `cold-read-cell-common.py` | PR #167; both runtimes pinned by test at 5d2acae |
| The stamp carries duration, and tokens for Codex cells | `cold-read-cell-common.py` | 5d2acae |
| Records are kept, never committed; one directory per run | `cold-read-grid.py`, `.gitignore` | user-ruled 2026-08-14, 2026-08-25 |
| Path references in the target are checked before launch (`--reference-check.md`) | `cold-read-grid.py`, `reference_integrity_pre_pass` | 2026-08-05 |

Known defect in the last row (found twice on 2026-08-25 by triagers of the compiled notes): the pre-pass reads metric triples such as `15/14/15`, `~`-prefixed home paths, dotted names such as `CLAUDE.local.md` and date ranges such as `2026-08-17/18` as paths and reports them unresolved. A fix is owed; it is not ruled.

## What is carried by prompt and skill text, not code

- The two reviewer prompts. Ruled and landed 2026-08-05, revised through PR #167; unchanged by this design. They are the judgment layer and are reviewed by the instrument itself in composed form (`compose_prompt`), never as a hand-made approximation.
- The mode and the triage protocol above — skill text, because they instruct the commissioning agent, whose work is judgment.
- The Monitor line list the skill hands the agent (`saved:`, `FAILED`, `STRAY WRITE:`, `FELL BACK:`, `RECOVERED:`, `TARGET CHANGED DURING RUN:`) — skill text today; the grid could print the watch command itself, which was proposed to the user on 2026-08-25 and is not ruled.

## The merge — the largest step still done by hand

Turning eight reports into one list of distinct findings is done by the commissioning agent reading eight files. Measured 2026-08-24/25: a blind comparer doing exactly this took 10–20 minutes and 130,000–230,000 tokens per set. nedschorus#166 commissions the mechanical half — extract every numbered finding with its quoted passage, group by passage, present the groups with each cell's wording and count — and leaves the judgment half, "are these the same defect", with the agent. Its design gets its own cold read before the build; this document only places it: it is code-after, and it changes nothing in the triage protocol.

## Records

One directory per run under `cold-read-records/`, named `<date>-<target stem>` with a counter for a second run of the same target in a day; every file inside carries that name as a prefix. Kept, gitignored, never committed: "they are not temp, their primary utility lasts about 60 minutes, and we could purge them probably without ill effect, but like other logs, they are useful for analysis as we are seeing" (user, 2026-08-25). The run's dispositions file, `<run>--dispositions.md`, is where every finding's fate is written, in both modes.

## Measured costs

- One eight-cell grid: about eight minutes of wall-clock, all cells running at once (2026-08-24, six grids).
- One blind comparison of two eight-report sets: about sixteen minutes and 250,000 subagent tokens (2026-08-24).
- One single-reader zero-context read: about seven minutes and 33,000 tokens (2026-08-25).
- Per-cell tokens and duration are in every stamp since 5d2acae; no per-grid total is computed yet.

## Open questions for the user

1. Whether the readership test governs the closed list, or the list is fixed (proposed: the test governs).
2. Whether a closed read that raises a user-only question posts without waiting for the answer (proposed: it posts; the answer is applied as an edit).
3. Whether the reviewer prompts stay one text for both modes (proposed: yes).
4. Which commands the PR/issue hook guards, and whether it also carries the push gate while the gatekeeper is dormant.
5. Whether the pre-user gate gets its fixed prompt and record.
6. The reference pre-pass noise, and whether the grid prints its own Monitor command.

## Not covered here

The sanity-check is a separate instrument with its own runner and prompts (`scripts/sanity-check-attacks.py`); the merged report has its own design under nedschorus#166; which document types get which treatment is walk item 6 of the consolidated MD-pipeline walk, unwalked as of 2026-08-25.
