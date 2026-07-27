> **Carried from nedlern 2026-07-27; PENDING THE BOSS'S REVIEW — not landed
> content.** Original path `docs/working/trigger-first-instruction-delivery-scan-first-pass.md`
> at nedlern main. Pair: [nedschorus#30](https://github.com/nedschorus/nedschorus/issues/30).
> Provenance, corrected 2026-07-27 (same session): this file crossed on
> AGENT JUDGMENT (wiki recommended, new-vp executed), beyond the boss's
> named scope — he directed moving "1972 and its MD file," which is the
> design document, and never named this scan. An earlier version of this
> note said "boss-directed," which was false for this file. Under his
> nothing-enters-nedschorus-without-my-review ruling it awaits his review;
> he may strike it.
> Porting caveat (wiki, 2026-07-27): every row below is classified against
> NEDLERN's enforcement inventory (its 73-line CLAUDE.md, its hooks, its
> rules files), so the per-row verdicts (39 trigger-candidate / 21 kernel /
> 7 borderline) do NOT port to NC, whose content and enforcement differ.
> What may port is the METHOD, plus reasoning on individual rows whose
> underlying rule survives — using it is a re-derivation, not a skim.
> Links to sibling files that were not carried (e.g. the thoughts file
> named as "prompt of record") are dead here by design.

# CLAUDE.md trigger-point scan

> Review note (wiki, 2026-07-18): Fable-subagent output, reviewed before commit — row quotes spot-checked verbatim against CLAUDE.md; every cited hook, rules file, and script verified present on disk; the auto-read-before-write staleness inject, mail-pull Stop-hook delivery, SessionStart comms card (incl. its "Full semantics: your doctrine file" closing pointer), and handoff-pickup inject additionally corroborated by live observation in the reviewing session. One typo fixed (a stray CJK glyph in the row-40 false-fires note). Prompt of record: [trigger-first-instruction-delivery-thoughts.md](trigger-first-instruction-delivery-thoughts.md).

Source: `/Users/el/Projects/nedlern-wiki/CLAUDE.md` (73 lines, read in full 2026-07-18).
Enforcement inventory consulted: `.claude/settings.json` (hook wiring), `.claude/hooks/` (34 scripts), `.claude/rules/` (4 file-path rule files, production example `wiki-editing.md` with a `paths:` frontmatter matcher on `docs/wiki/**/*.md`), `config/comms-card/multi-claude.md` (SessionStart injection via `comms-card-inject.sh`, fires on startup AND resume AND post-compact).

**Row count: 67. Verdict tally: 39 TRIGGER-CANDIDATE / 21 KERNEL / 7 BORDERLINE.**

Frequency scale: every-turn / most-sessions / occasional (some sessions, a few times) / rare (many sessions never hit it).
Assumed retention model: an injected instruction holds ~100k tokens; injector spaces re-delivery of the same payload to ~50k–100k tokens since last injection. "Spacing handles it" below refers to this.

Key observed facts vs inference: hook coverage claims below are **observed** (read from hook source and settings.json). Frequency claims are **inference** from CLAUDE.md's own content, the repo's recent-commit subjects (reviews, replay QA, handoffs, postal traffic), and the hook inventory (a repo that ships a softener-guard and a mail-pull hook demonstrably has regular postal traffic; a repo with branch-policy CI and a merge wrapper demonstrably has regular commits and occasional merges). Uncertainty is marked per-row.

---

## Section: Operating mode (lines 3–7)

| # | Quote (operative clause) | Frequency | Signal | Verdict |
|---|---|---|---|---|
| 1 | "Optimize for correctness and long-term quality over speed. There is no deadline — when the right fix is disruptive … make it anyway" | every-turn — governs every decision about how much to invest; a working session makes such tradeoffs continuously | none — governs everything | KERNEL |
| 2 | "You are an action-biased nedlern agent: pick and execute, don't narrate or stand by" | every-turn — shapes every response's default posture | none — governs everything | KERNEL |
| 3 | "Disagree with evidence" | every-turn — conversational register, applies whenever the boss or a peer asserts anything | none — internal judgment | KERNEL |
| 4 | "no apologies" | every-turn register; the temptation is a training-default reflex that can fire any turn | partial — a Stop-hook regex on apology phrases could catch emitted violations post-hoc, but the rule must already be loaded to prevent them | KERNEL (note: a Stop-hook backstop `\b(sorry|I apologize|my apologies)\b` is cheap recidivism insurance, same design as postal-softener-guard, but it supplements the kernel line rather than replacing it) |
| 5 | "a menu of options handed to the boss is deferral, not progress — decide it yourself when the call is yours" | most-sessions — the temptation recurs whenever a decision point is reached in interactive work | fuzzy — option-menu prose patterns ("Option A/B", "which would you prefer") are matchable but the decide-vs-escalate line is judgment | KERNEL |
| 6 | "when the remaining steps' order is immaterial, continue through them without asking" | most-sessions — same decision-point family as row 5 | fuzzy — "which should I do first?" phrasing is matchable but rare verbatim | KERNEL |
| 7 | "The boss can make mistakes — push back on bad ideas, push back hard on terrible ones" | occasional — only when the boss proposes something wrong | none — evaluating idea quality is internal judgment; no observable pre-condition | KERNEL (infrequent but undetectable) |
| 8 | "Offload execution-mass work (code, tests, dogged hunts, research, web search) to CDX peers … keep your own context for judgment" | most-sessions — the offload decision arises whenever bulk work appears | weak — no crisp pre-signal for "about to do bulk work myself"; a long streak of Edit/Bash calls is only visible after the offload moment passed | KERNEL |
| 9 | "When uncertain about your lane, check your briefing first, ask second" | occasional — fires on internal uncertainty | none — internal state, unobservable | KERNEL |
| 10 | "Parallelize independent tasks; don't batch them" | most-sessions — dispatch decisions recur through any working session | none — "these tasks are independent" is a judgment the harness cannot see before dispatch | KERNEL |
| 11 | "For design- or architecture-level changes (schemas, routing, protocols, doctrine), lead with a plan even when told 'fix'" | occasional — most sessions do routine work; design-level changes are a minority | partial — some design surfaces are path-identifiable (migrations, `*.schema.*`, `docs/wiki/**` doctrine, `.claude/settings.json`), but "architecture-level" is broader than any path set | BORDERLINE — settled by: enumerate the repo's actual design-level surfaces and measure what fraction of past design changes touched a path-matchable file; if >~80%, a file-path rule carries it, else KERNEL |
| 12 | "Root-cause, never patch the symptom. Two signs you stopped too shallow: the fix is a guard/retry/reset/restart/clear-cache, or you can't say what changed" | occasional — only investigation/debugging sessions need it; many sessions (reviews, comms, doc work) never do | UserPromptSubmit debugging vocabulary; Stop-hook shallow-fix vocabulary in agent output | TRIGGER-CANDIDATE |
| 13 | "Before continuing, state: (1) what you ruled out, (2) which decision that moved, (3) the cheap check … (4) which other open hypotheses it removed" | occasional — same investigation moment as row 12 | same as row 12 | TRIGGER-CANDIDATE |
| 14 | "Evidence-backed closure is a valid completion: showing the problem does not exist on current code, or is already fixed, ends the task" | occasional — same investigation moment | same as row 12 | TRIGGER-CANDIDATE |
| 15 | "'Real but not worth fixing' is a priority call: bring it to the boss with the evidence; never self-close on cost" | occasional — same investigation moment | same as row 12 | TRIGGER-CANDIDATE |
| 16 | "Context/window budget is the boss's to manage … Don't self-throttle, truncate, or wrap up early to conserve context" | occasional — the temptation only arises deep in a long session under token pressure; short sessions never need it | token pressure is observable: session JSONL size (a file a Monitor can watch); wrap-up prose is Stop-matchable | TRIGGER-CANDIDATE |

### Trigger specs — Operating mode

**Rows 12–15 (the hard-problem-method paragraph — one shared trigger, one shared payload).** This is the largest contiguous block in CLAUDE.md (~340 words) and is dead weight in every non-investigation session.
- trigger-spec: UserPromptSubmit, prompt regex `(?i)\b(bug|broken|regression|root.?cause|why (does|is|did)|investigate|repro|debug|intermittent|flaky|fail(s|ing|ed) (on|in|when))\b`; PLUS a Stop-hook backstop scanning the agent's own output for shallow-fix vocabulary: `(?i)\b(as a workaround|added a (guard|retry)|restart(ed|ing)? (the|it) (fixed|resolved)|clear(ed|ing) the cache|reset it and)\b`.
- false-fires: the UserPromptSubmit regex fires on casual mentions of bugs ("the bug we fixed yesterday") — inference: perhaps 1–3 extra fires per session in a mixed session; tolerable with 50k spacing. The Stop backstop fires on discussing someone else's workaround — rarer.
- misses: investigations the agent starts on its own initiative (noticed an anomaly mid-task, no user prompt used the vocabulary). The Stop-hook backstop closes most of this: the shallow-fix phrases appear in the agent's own narration when it is about to stop too shallow, which is exactly the moment the rule exists for. Residual miss: a silent shallow fix narrated in neutral words — accepted.
- payload: rows 12–15 verbatim as one block + pointer to `docs/wiki/operations/hard-problem-method.md`.

**Row 16 (context budget).**
- trigger-spec: Monitor watching the current session JSONL under `~/.claude/projects/-Users-el-Projects-nedlern*/` for size crossing ~400KB increments (proxy for token pressure), injecting the one-liner; PLUS Stop hook, output regex `(?i)\b(conserve|save|running (low|out) of|short on) (context|tokens|the window)|wrap(ping)? up (early|to)\b`.
- false-fires: the Monitor threshold fires in every long session whether or not the agent is self-throttling — but the injection is one sentence and long sessions are exactly the at-risk population; tolerable. Stop regex fires on legitimate compaction discussions with the boss — rare, tolerable.
- misses: silent self-throttling with no phrase emitted; the Monitor half covers this by firing on pressure itself, not on the symptom.
- payload: row 16 verbatim, nothing else.

---

## Section: Soft block (lines 9–11)

| # | Quote | Frequency | Signal | Verdict |
|---|---|---|---|---|
| 17 | "When one fires, either comply with the suggested alternative OR articulate a 3-part override … via `NEDLERN_DEVIATION_REQUEST=<reason>`" | rare — needed only in the turn after a soft block fires; most sessions hit zero or one block | already hook-delivered at fire time — **observed**: block teach messages in `no-raw-gh-pr-merge.sh` and `no-gh-pr-review-approve.sh` name the `NEDLERN_DEVIATION_REQUEST` bypass and the sanctioned alternative in the message the agent receives | TRIGGER-CANDIDATE |
| 18 | "Workarounds that dodge the block silently (env wrappers, shell tricks, `--no-verify`) defeat the pattern — the sanctioned override is `NEDLERN_DEVIATION_REQUEST`, not a workaround" | rare — same moment as row 17 (temptation exists only after a block) | already hook-delivered at fire time, same messages | TRIGGER-CANDIDATE |

### Trigger specs — Soft block

**Rows 17–18.**
- trigger-spec: existing hooks — the teach message of every soft-block script (`no-raw-gh-pr-merge.sh`, `no-gh-pr-review-approve.sh`, `protected-paths.sh`, `worktree-effect-guard.sh`, `cross-worktree-guard.sh`, block text centralized in `.claude/hooks/block-messages.md`). Audit action, not new config: verify each block message carries BOTH the comply-or-override instruction AND the anti-workaround sentence (observed present in the two hooks read; **inferred** for the others — the audit is the cheap check).
- false-fires: none — the message is only ever delivered when a block actually fires.
- misses: an agent that never sees a block never learns the pattern exists, so it cannot recognize a block as a block. Mitigation: keep ONE kernel sentence ("soft blocks teach at fire time; follow the message they print") and drop the mechanics (override syntax, workaround ban, wiki pointer) from the kernel. Net: 3 lines shrink to a clause.
- payload: already in the block messages; no injection payload needed.

---

## Section: Wiki (lines 13–16)

| # | Quote | Frequency | Signal | Verdict |
|---|---|---|---|---|
| 19 | "Read [agent-onboarding-reading.md] and every must-read it lists, yourself, in full, every session start, before substantive work" | once per session, at a known instant — after session start the line never fires again | SessionStart — the rule's moment IS the SessionStart event | TRIGGER-CANDIDATE |
| 20 | "The wiki holds doctrine, operating rules, and non-obvious system behavior … It is not a mirror of the code" | occasional — needed when writing or judging wiki content; sessions that never touch the wiki never need it | file-path — wiki files being read/edited; **observed** production mechanism exists (`.claude/rules/wiki-editing.md`, `paths: docs/wiki/**/*.md`) | TRIGGER-CANDIDATE |
| 21 | "A commit needs a companion wiki update (same PR) only when it changes that non-obvious system behavior or doctrine" | occasional — relevant at commit/PR-assembly moments, and only for behavior-changing commits | PreToolUse on `git commit` / `gh pr create` | TRIGGER-CANDIDATE |
| 22 | "Working drafts in `docs/working/` are scratch, not doctrine — do not cite them as authoritative" | rare — only when a `docs/working/` file enters context | file-path — a Read/Edit under `docs/working/` is the exact pre-condition | TRIGGER-CANDIDATE |

### Trigger specs — Wiki

**Row 19.**
- trigger-spec: SessionStart injection (this is not merely the priming half — the rule is session-start-scoped, so SessionStart is the entire delivery). Concretely: append the directive to the existing `comms-card-inject.sh` output or a sibling SessionStart hook with `matcher: ""`.
- false-fires: none; fires exactly when the rule applies.
- misses: none — there is no other moment the rule matters. (Post-compact resume is covered: **observed**, `comms-card-inject.sh` fires on `startup|resume|compact` sources.)
- payload: the rule verbatim.

**Row 20.**
- trigger-spec: File-path rule injection — extend the existing `.claude/rules/wiki-editing.md` (paths already `docs/wiki/**/*.md`) with the scope sentence.
- false-fires: fires on every wiki-file edit including trivial typo fixes — the file already fires there; adding one sentence is marginal.
- misses: the decision "should this even BE a wiki page?" can happen before any wiki file is opened (e.g., while writing a PR). Row 21's commit-time trigger backstops that moment.
- payload: the two scope sentences + pointer to `docs/wiki/operations/wiki-update-criteria.md`.

**Row 21.**
- trigger-spec: PreToolUse, tool=Bash, command regex `\bgit commit\b|\bgh pr create\b`, spaced re-delivery.
- false-fires: every commit — commits are frequent in coding sessions (inference: 3–15/session from the atomic-commit rule and recent history density). Spacing at 50k–100k tokens reduces this to ~1–2 injections per session; tolerable for a two-sentence payload.
- misses: none material — a companion wiki update is only ever owed at commit/PR time.
- payload: row 21 verbatim + `wiki-update-criteria.md` pointer (shared injection with rows 26, 30 — one commit-moment card).

**Row 22.**
- trigger-spec: File-path rule injection — new `.claude/rules/working-drafts.md` with `paths: docs/working/**`.
- false-fires: fires when legitimately writing a design doc in `docs/working/` (the intended workflow per line 27) — the reminder "this is scratch, don't cite it" is harmless there; low volume.
- misses: citing a `docs/working/` path from memory without reading it this session. Rare; the cite-without-read backstop (row 35) also covers it.
- payload: the rule verbatim, one line.

---

## Section: Git (lines 18–22)

| # | Quote | Frequency | Signal | Verdict |
|---|---|---|---|---|
| 23 | "Use `scripts/nedlern-sync` instead of raw rebase or pull --rebase" | occasional — sync moments a few times per working session at most | PreToolUse Bash, exact command vocabulary | TRIGGER-CANDIDATE |
| 24 | "Use `scripts/nedlern-push` instead of raw `git push` from worktrees" | occasional — push moments follow commits, several per coding session | PreToolUse Bash, exact command vocabulary | TRIGGER-CANDIDATE |
| 25 | "Don't overwrite a file that changed since you read it. On Edit/Write the auto-read-before-write hook re-reads the file and injects a staleness diff … read that diff and reconcile" | occasional — matters only when origin/main advanced a file mid-session | already hook-delivered at fire time — **observed**: `auto-read-before-write.sh` wired PreToolUse on Edit\|Write in settings.json; the injected diff arrives exactly at the moment of need | TRIGGER-CANDIDATE |
| 26 | "For edits made outside Edit/Write (a shell `perl -pi`, heredoc, etc.), first run `git log -1 -- <file>` and re-read if it moved" | rare — shell-side in-place edits are the exception path | PreToolUse Bash, in-place-edit command vocabulary | TRIGGER-CANDIDATE |
| 27 | "Edit/Write **repo** files using absolute paths rooted at `$CLAUDE_PROJECT_DIR`. Cross-worktree paths are blocked by `scripts/cross-worktree-guard.sh`" | occasional — the violation moment is a wrong-path Edit/Write | already hook-delivered at fire time — **observed**: `cross-worktree-guard.sh` wired PreToolUse on Edit\|Write\|Bash | TRIGGER-CANDIDATE |
| 28 | "Before merging a PR, read the branch-policy findings comment that CI auto-posts on it" | rare-to-occasional — merges are less frequent than commits; many sessions merge nothing | PreToolUse Bash, merge command vocabulary | TRIGGER-CANDIDATE |

### Trigger specs — Git

**Row 23.**
- trigger-spec: PreToolUse, tool=Bash, command regex `\bgit (pull|rebase)\b` (nudge with teach message naming `scripts/nedlern-sync`, styled like the existing soft blocks; no existing hook covers this — **observed** absence in `.claude/hooks/`).
- false-fires: `git pull` inside quoted strings or discussion of the command in a commit message body — rare; tolerable.
- misses: none — the raw command is the entire violation surface.
- payload: the rule, one line.

**Row 24.**
- trigger-spec: PreToolUse, tool=Bash, command regex `\bgit push\b` (excluding `scripts/nedlern-push` invocations: negative check for `nedlern-push` in the same command string).
- false-fires: essentially none beyond mentions-in-strings.
- misses: none.
- payload: the rule, one line.

**Rows 25, 27 (already-delivered pair).**
- trigger-spec: existing hooks — `auto-read-before-write.sh` (row 25) and `cross-worktree-guard.sh` (row 27). Verify their emitted messages carry the reconcile instruction (row 25) and the absolute-path instruction (row 27); then the kernel lines can shrink to nothing or a clause. Row 25's shell-edit escape hatch is row 26's separate trigger.
- false-fires / misses: n/a — fire exactly at the violation.
- payload: already in the hook output.

**Row 26.**
- trigger-spec: PreToolUse, tool=Bash, command regex `\b(perl|sed)\s+-[A-Za-z]*i\b|\bawk -i inplace\b|>{1,2}\s*\$?CLAUDE_PROJECT_DIR|tee\s+(-a\s+)?/Users/el/Projects/nedlern` — in-place editors unconditionally; redirect/tee only when targeting repo paths.
- false-fires: `sed -i` on scratchpad files — moderate; tolerable for a one-line payload. Bare `> file` with relative paths is not reliably matchable — accepted.
- misses: heredoc writes to repo files via relative path. Backstop: PostToolUse same regex family delivers the correction for the next occurrence; also `undo-guard.sh` (**observed**, PostToolUse Edit|Write|Bash) already watches for content-loss patterns post-hoc.
- payload: the rule, one line.

**Row 28.**
- trigger-spec: PreToolUse, tool=Bash, command regex `\b(nedlern-pr-merge|gh pr merge)\b`.
- false-fires: none of note — the command class is the moment.
- misses: none. (Alternative with zero hook cost: print the reminder from inside `scripts/nedlern-pr-merge` itself; but that script is out of scope for this scan's seven surfaces — the PreToolUse spec stands on its own.)
- payload: row 28 verbatim, bundled with row 39's merge-path rule (same trigger).

---

## Section: Rules (lines 24–39)

| # | Quote | Frequency | Signal | Verdict |
|---|---|---|---|---|
| 29 | "Commit after every atomic change set … Don't leave finished work uncommitted, and don't bundle unrelated changes" | most-sessions, many moments — commit discipline shapes work continuously in any coding session | detectable at idle: Stop hook running `git status --porcelain` (dirty tree at idle = the exact failure state) | BORDERLINE — frequency argues KERNEL for coding sessions, but the failure state is perfectly machine-visible. Settled by: count sessions where the dirty-tree-at-Stop condition would have fired usefully vs noise (WIP mid-turn stops); if the Stop+status check is mostly signal, move it out |
| 30 | "Include your session ID in commit messages (from `scripts/session-id.sh --short`)" | per-commit — useless at every non-commit moment | PreToolUse `git commit`; plus **observed** CI backstop (branch-policy findings flag missing trailers, line 22) | TRIGGER-CANDIDATE |
| 31 | "Fix issues discussed this turn. Context is highest now. NOT: defer to next session" | every-turn-adjacent — the deferral temptation can attach to any discussed issue | fuzzy — deferral phrases ("next session", "follow up later") are matchable but the decisive moment is internal | KERNEL (a Stop-hook regex `(?i)\b(next session|in a (later\|future) session|defer (this\|that) to)\b` is a cheap backstop, but the rule must pre-load to work) |
| 32 | "Do, don't file. … A GHI or task has two co-equal triggers: (a) work you genuinely cannot do now … (b) large or multi-session work you ARE actively doing … Complex work gets a design doc" | occasional — needed exactly when about to file a GHI or task | PreToolUse on issue/task creation commands | TRIGGER-CANDIDATE |
| 33 | "If code changes, that change must be covered by a test plan and tested" | most coding sessions — but the moment is diffuse (shapes planning, not one tool call) | partial — commit-time (PreToolUse `git commit`) is a reliable last-line moment; the planning moment is not machine-visible | BORDERLINE — settled by: whether a commit-time reminder is early enough to change behavior (it catches untested commits before push) or whether the rule must shape the work plan itself (kernel). Lean: commit-time card carries it |
| 34 | "Grep the entire project when looking for anything. Narrow with `glob` or `type`, not by restricting path" | occasional — searches happen in most sessions but path-restricted ones are the minority | PreToolUse on the Grep tool with a `path` input parameter set to a repo subdirectory | TRIGGER-CANDIDATE |
| 35 | "If you cite a source, you must read it first" | occasional — citation moments cluster in doc/review/GHI writing | Stop-hook cross-check of cited paths/links against the session read log — **observed** substrate exists: `scripts/read-tracker.sh` runs PostToolUse on Read | TRIGGER-CANDIDATE (heaviest custom logic of the set; flag as such) |
| 36 | "NOT: delete untracked or unknown files/content without confirming. DO: flag + preserve" | rare — deletion of unknown content is an exceptional moment | PreToolUse Bash, deletion command vocabulary; **observed** partial existing coverage: `undo-guard.sh` PostToolUse detects destructive outcomes | TRIGGER-CANDIDATE |
| 37 | "DO: clean up evidently-obsolete content … without confirming. Confirm-before-delete applies to *unknown* or *plausibly-active* state, not *known-obsolete*" | rare — same deletion moment as row 36 | same as row 36 | TRIGGER-CANDIDATE |
| 38 | "Confirm before deleting agents/worktrees, changing GitHub settings, or modifying git hooks" | rare — these are exceptional administrative actions | PreToolUse Bash, exact command vocabulary; **observed** partial existing coverage: `.claude/rules/permissions-changes.md` fires on `.claude/hooks/` and `scripts/git-hooks/` edits | TRIGGER-CANDIDATE |
| 39 | "merge in-lane PRs … via `scripts/nedlern-pr-merge <PR#>`, the **only** path that runs the review gate. The hook blocks **only** `gh pr merge --delete-branch` … a bare `gh pr merge --squash` … silently bypasses the gate. Use the tool anyway" | rare-to-occasional — merge moments only | PreToolUse Bash `gh pr merge` — **observed** gap in existing hook: `no-raw-gh-pr-merge.sh` source confirms it matches only delete-branch variants and explicitly allows bare `--squash` | TRIGGER-CANDIDATE |
| 40 | "Post reviews as a `gh pr comment` carrying a `Reviewed-by: <agent>` trailer; BLOCK with `Disposition: …`; clear a block by APPENDING … never by editing" | occasional — review sessions only; one of the longest lines in the file | PreToolUse Bash on review-command vocabulary; **observed** partial existing coverage: `no-gh-pr-review-approve.sh` teaches the trailer convention when `gh pr review --approve` is attempted | TRIGGER-CANDIDATE |
| 41 | "NOT: ask permission to update wiki/MD content where you have evidence of staleness. DO: edit and ship" | occasional — staleness discoveries happen in some sessions | fuzzy — the failure is an ask-permission sentence in output ("should I update…?"); phrase regexes over-fire on legitimate scope questions | BORDERLINE — settled by: trial a Stop-hook regex `(?i)\b(should I|want me to|shall I) (update|fix|edit|correct)\b` on historical transcripts and measure precision; if >~50%, ship as backstop and drop the kernel line |
| 42 | "Observations are not output: when you notice something wrong, fix it now … or complain to the owner … — never just narrate it" | most-sessions — noticing-something-wrong happens routinely | fuzzy — "worth noting"/"worth surfacing" phrases are weak proxies for a judgment failure | KERNEL |
| 43 | "NOT: handle tasks outside your role in your own context window. DO: delegate via postal" | occasional — but role-fit of incoming work is pure judgment | none — no observable pre-condition distinguishes in-lane from out-of-lane work | KERNEL |
| 44 | "Independent tasks: start immediately. NOT: batch, defer, or block on a dispatched task. DO: parallelize" | most-sessions — duplicate in substance of row 10 (line 5's parallelize clause restated in ## Rules) | none | KERNEL (note for the restructuring effort: rows 10 and 44 are one rule stated twice; deduplication is free budget, though quality judgments are out of this scan's scope) |

### Trigger specs — Rules

**Row 30 (session ID in commits) + rows 21, 33 as a single commit-moment card.**
- trigger-spec: PreToolUse, tool=Bash, command regex `\bgit commit\b`; spaced. One injected card carrying: session-ID trailer instruction (row 30), companion-wiki-update criterion (row 21), test-plan check (row 33 if its BORDERLINE resolves this way).
- false-fires: every commit; spacing reduces to ~1–2 per session.
- misses: commits via `git commit` inside a script — rare; the **observed** CI branch-policy check backstops missing trailers at PR time.
- payload: the three rules verbatim, ~60 words.

**Row 32 (do, don't file).**
- trigger-spec: PreToolUse, tool=Bash, command regex `\bgh issue create\b`; plus PreToolUse on the task tool if TaskCreate is a matchable tool name in this harness (**uncertain** — TaskCreate appears in CLAUDE.md as a tool name; if it is, add `tool=TaskCreate, matcher: any`).
- false-fires: legitimate coordination-record GHIs (trigger (b)) — the payload itself says those are fine, so the reminder is self-disambiguating; volume low.
- misses: capture-instead-of-doing that never reaches a filing command (mental deferral) — that variant is row 31's kernel territory.
- payload: row 32 verbatim.

**Row 34 (grep whole project).**
- trigger-spec: PreToolUse, tool=Grep, input-JSON regex on the `path` field: fires when `path` is present and points below the repo root (i.e., matches `nedlern-wiki/.+`), injecting "search repo-wide; narrow with glob/type, not path".
- false-fires: deliberate narrow greps where the location is certain — moderate (inference: maybe a third of greps); a one-line reminder is tolerable, and spacing caps volume.
- misses: path-restricted `grep`/`rg` run via Bash instead of the Grep tool. Second pattern closes it: PreToolUse, tool=Bash, command regex `\b(grep|rg)\b.*\s(docs|scripts|src|\.claude)/`.
- payload: the rule, one line.

**Row 35 (cite = read first).**
- trigger-spec: Stop hook running a script that (a) extracts repo paths, wiki links, and `file://` URIs from the agent's final message, (b) diffs them against the read log maintained by `scripts/read-tracker.sh`, (c) injects "you cited X without reading it this session — read before citing" on a miss. Post-hoc delivery is acceptable per the repeat-actions principle; a wrong citation in chat is correctable next turn.
- false-fires: citations of files read before the read-tracker's log window (post-compact continuity) — **uncertain**, depends on read-tracker log lifetime; needs a session-scoped log to be precise. This is the highest-complexity candidate; if the log plumbing is unreliable, demote to BORDERLINE.
- misses: citations of URLs (unverifiable against a local read log) and quotes-from-memory — accepted; the highest-damage case (committed docs citing dead repo paths) is separately covered by the memory entry's `git ls-tree` habit.
- payload: the rule + the specific uncited path detected.

**Rows 36–38 (deletion/administrative bundle — one trigger family).**
- trigger-spec: PreToolUse, tool=Bash, command regex `\brm\s+(-[A-Za-z]*\s+)?|\bgit clean\b|\bgit checkout --\b|\bgit restore\b|\bgit worktree remove\b|\bgh repo edit\b|\bgh api\b.*(settings|protection)` — one hook, payload selected by which alternative matched: unknown-content rule (36) + known-obsolete license (37) for the file-deletion class; confirm-first rule (38) for the worktree/settings/hooks class. Git-hook edits already covered by the **observed** `.claude/rules/permissions-changes.md` file-path rule.
- false-fires: `rm` on scratchpad/temp files — frequent in absolute terms. Mitigation in the matcher: fire only when the argument string references the repo root or `~/Projects`; scratchpad paths (`/private/tmp/claude-501/...`) excluded. Residual over-fire low.
- misses: deletion via `find -delete`, `xargs rm` — add `\bfind\b.*-delete|\bxargs\b.*\brm\b` to the regex. Post-hoc, **observed** `undo-guard.sh` already detects destructive outcomes as a backstop.
- payload: rows 36+37 as one card (they are two halves of one decision rule), or row 38 alone, per match class.

**Rows 39–40 + 28 (merge/review protocol bundle).**
- trigger-spec: two matchers. (a) Merge moment: PreToolUse, tool=Bash, command regex `\bgh pr merge\b` — extend the **observed** `no-raw-gh-pr-merge.sh` (currently delete-branch-only by design) with a non-blocking teach branch for bare merges, or add a sibling nudge hook; payload = rows 39+28. (b) Review moment: PreToolUse, tool=Bash, command regex `\bgh pr (review|comment)\b` — payload = row 40's trailer protocol + `trailer-as-audit.md` pointer. The `--approve` case is **already hook-delivered** (`no-gh-pr-review-approve.sh` teaches the full trailer convention at the failed-approve moment).
- false-fires: (b) fires on non-review `gh pr comment` uses (status notes on PRs) — moderate; the trailer protocol is relevant context there too (a comment on a PR may need a trailer), so over-fire isnear-harmless. Volume: review-heavy sessions could hit spacing caps — acceptable.
- misses: composing a review in a body file before any `gh` command — the PreToolUse fires at post time, before the comment lands, which is still in time to fix the trailer. No gap.
- payload: as above; these are two of the three longest lines in CLAUDE.md (~120 words combined) — large kernel savings.

---

## Section: Agent Comms (lines 41–54)

Context for this whole section (**observed**): `config/comms-card/multi-claude.md` is injected at EVERY SessionStart (startup/resume/compact) and already carries the close-out-on-the-wire rule, the no-softeners rule, deference rules, and a compact tier gloss ("T0 none · T1 at a clean stop … T3 bypasses the busy gate. Full semantics: your doctrine file"). The SessionStart priming half of a dual delivery therefore already exists in production for most of this section; the specs below add the moment-of-use half. Note: the card's closing pointer "Full semantics: your doctrine file" currently assumes the tier table stays in CLAUDE.md — if the table moves to injection, that pointer must move with it (flagged for the restructuring effort).

| # | Quote | Frequency | Signal | Verdict |
|---|---|---|---|---|
| 45 | "Cross-agent asks: comply in their lane; push back with evidence in yours; ask when ambiguous" | occasional — needed at mail-arrival moments | mail arrival is machine-visible: PostToolUse on `mcp__postal__check_mail`; Stop-hook mail delivery (**observed**: `mail-pull.sh`) | TRIGGER-CANDIDATE |
| 46 | "Questions route to agents, not the boss. … bring the boss only what only the boss can decide" | most-sessions — the ask-the-boss temptation attaches to any open question in interactive work | fuzzy — question-to-boss prose is not reliably distinguishable from legitimate boss-only asks | KERNEL |
| 47 | "Postal attention tiers run T0–T3 … [full four-bullet tier table]" | occasional — needed only when composing a postal send; the table is ~110 words of kernel | PreToolUse on postal send tools — exact | TRIGGER-CANDIDATE |
| 48 | "Default to T1 if unsure — defaulting to needs-a-response fails safe" | occasional — same send moment | same as row 47 | TRIGGER-CANDIDATE |
| 49 | "Close out on the wire — the deliverable closes the loop, not an ACK. … Use `respond_packed`/`respond` (ACK-only) solely when you cannot complete the work … A message that already has `in_reply_to` set is response-exempt" | occasional — reply-composition moments | PreToolUse on `mcp__postal__respond`/`respond_packed`/`send_to_agent`; SessionStart card already primes the principle (**observed**) | TRIGGER-CANDIDATE |
| 50 | "Check mail every response cycle" | every-cycle nominally — but the function is already mechanized | already hook-delivered — **observed**: `mail-pull.sh` on Stop surfaces this agent's undelivered mail automatically at idle (pull-only delivery, delivered-once semantics) | TRIGGER-CANDIDATE |
| 51 | "NOT: append urgency softeners ('no urgency' / 'no rush' / 'reply when convenient') to postal sends; the tier IS the urgency signal" | occasional — send moments only | already hook-delivered — **observed**: `postal-softener-guard.py` PostToolUse on all postal send tools, emits a reminder on every violation; card also primes ("no body softeners") | TRIGGER-CANDIDATE |
| 52 | "When you promise to do something later … open a TaskCreate — anchor it to the source msg_id" | occasional — promise moments are sparse and textual | fuzzy — promise phrasing ("I'll … later", "will follow up") over-fires badly on ordinary future-tense prose | BORDERLINE — settled by: precision test of a promise-phrase regex restricted to postal send bodies only (PostToolUse on send tools, regex over the message field); if precision is acceptable there, ship as PostToolUse backstop |
| 53 | "A peer who hands you work is often blocked on you … Do it now, or tell them you're deferring and why" | occasional — mail-arrival moments | same mail-arrival signal as row 45 | TRIGGER-CANDIDATE |
| 54 | "Answer where the ask came from. Return a peer-requested deliverable through the channel that peer can see … NEVER the user chat" | occasional — peer close-out moments | mail-arrival primes it; the violation moment (writing to chat instead) is not directly matchable, but the card primes and arrival-injection re-primes | TRIGGER-CANDIDATE |

### Trigger specs — Agent Comms

**Rows 47–48 (tier table — the single largest clean win by token count).**
- trigger-spec: PreToolUse, tool regex `mcp__postal__send_to_agent|mcp__postal__respond|mcp__postal__respond_packed`, matcher: any input; spaced re-delivery. SessionStart priming already exists (card's one-line tier gloss).
- false-fires: none — the send moment is exactly when tier choice happens.
- misses: none. Postal-heavy roles (dispatcher-adjacent) hit the spacing cap, which is the intended behavior.
- payload: the full tier table (rows 47+48 verbatim). Kernel keeps nothing, or only the card's one-line gloss.

**Rows 45, 53, 54 (mail-arrival bundle).**
- trigger-spec: PostToolUse, tool regex `mcp__postal__check_mail`, matcher: any result with ≥1 message; PLUS the same payload appended to the Stop-hook mail delivery path (`mail-pull.sh` already injects surfaced mail — **observed**; appending a protocol footer to its injection is a payload change, not new infrastructure).
- false-fires: empty-inbox checks excluded by the ≥1-message condition; effectively none.
- misses: none — all inbound work arrives via these two paths.
- payload: rows 45+53+54 as one ~50-word card ("comply/push-back/ask · sender may be blocked on you — do now or say you're deferring · answer on the wire, never user chat").
- note: rows 49/54 overlap the SessionStart card's close-out paragraph (**observed**), so this is a dual delivery: card primes at session start, arrival-injection refreshes at the moment of need.

**Row 49 (close-out / ACK discipline).**
- trigger-spec: PreToolUse, tool regex `mcp__postal__respond|mcp__postal__respond_packed` — inject "ACK-only is for defer/blocked; the deliverable closes the loop; say why and what happens next" exactly when an ACK-only tool is about to run. The `in_reply_to`-exempt clause rides in the mail-arrival bundle above.
- false-fires: legitimate defer-ACKs — the payload explicitly licenses them; self-disambiguating.
- misses: closing out via chat summary (no postal tool runs at all) — covered by the mail-arrival bundle's "answer on the wire" line plus row 53's do-now framing.
- payload: the respond-tool clause of row 49 + `inter-llm-communication.md` pointer.

**Row 50 (check mail).**
- trigger-spec: existing hook — `mail-pull.sh` on Stop. The kernel line's function (never miss mail) is carried mechanically; delivery is automatic at idle. Residual value of the kernel line: prompting a mid-turn `check_mail` during very long turns — **uncertain** whether that matters in practice; if it does, keep a clause, else drop the line entirely.
- false-fires / misses: n/a.
- payload: none needed.

**Row 51 (softeners).**
- trigger-spec: existing hook — `postal-softener-guard.py` (PostToolUse, all postal send tools, both runtimes per its header). Reminder-on-violation keeps firing until the habit dies, which its own docstring states was the design intent because the text-only ban "demonstrably does not hold." The kernel line is the weakest of the three deliveries (card + hook + kernel); it can drop.
- false-fires / misses: per the hook's own docstring, false positives are designed-harmless.
- payload: none needed.

---

## Section: Tone and style (lines 56–66)

| # | Quote | Frequency | Signal | Verdict |
|---|---|---|---|---|
| 55 | "Clear and complete. Write so a reader without your current context understands it" | every-turn — governs all written output | none — governs everything | KERNEL |
| 56 | "Do not condense. Do not sacrifice clarity or completeness to reduce word count" | every-turn | none | KERNEL |
| 57 | "Do not use a single word if that word introduces ambiguity … Avoid words with broad meanings like 'task'" | every-turn — register | none | KERNEL |
| 58 | "Name directories, files, functions, variables, enums, arguments, headings, and test-case labels … complete, self-documenting, and easy to grep … one shared token" | coding/authoring sessions — naming moments cluster where files and symbols are created; absent from comms/review-only sessions | file-path — code/doc files being written; Write-tool file creation | TRIGGER-CANDIDATE |
| 59 | "Applies to all written output — wiki pages, reviews, commit messages, postal messages, handoffs" | every-turn — scope modifier of rows 55–57 | none | KERNEL |
| 60 | "In conversation with the boss, stay clear, precise, and complete … do not mirror that brevity. Honor explicit format requests" | every boss-facing turn in interactive sessions | none — governs the whole conversation | KERNEL |
| 61 | "Default to small increments with the boss: one file / ~300 words / one item at a time … never a bulk dump" | every boss-facing turn | none | KERNEL |
| 62 | "PR/GHI/file/SHA references in conversation: include the full clickable URL or absolute path … Pair every numbered artifact … with a self-documenting handle … never a bare number" | most-sessions, many times — reference-bearing turns are routine in this repo's conversations | crisp post-hoc detector exists: Stop-hook regex for bare `#\d+` not inside a markdown link, bare repo-relative filenames | BORDERLINE — frequency argues KERNEL; the detector is unusually crisp for a register rule. Settled by: count reference-bearing turns per typical session from transcripts; if most turns carry references, KERNEL + Stop backstop; if references cluster in a few turns, move fully to Stop-hook delivery. Backstop spec regardless: Stop hook, output regex `(?<!\]\()(?<!\w)#\d{2,5}\b` and `(?<!/)\b[\w-]+\.(md\|sh\|py)\b(?!\))` heuristics, inject the rule on first violation per spacing window |
| 63 | "File paths in conversation must point to a readable local file at reference time. If the file lives only on an unmerged PR branch … materialize it first: `git show origin/<branch>:<path> > /tmp/…`" | rare — branch-only-file references arise mainly in review sessions | crisp post-hoc: paths in output are mechanically verifiable against the filesystem | TRIGGER-CANDIDATE |

### Trigger specs — Tone and style

**Row 58 (naming rules).**
- trigger-spec: File-path rule injection — new `.claude/rules/code-editing.md` with `paths: ["**/*.py", "**/*.sh", "**/*.ts", "**/*.js", "scripts/**"]`, carrying the naming rule + `naming-rules.md` pointer (shares the rules file with row 64's code-quality payload — same paths, same moment).
- false-fires: fires on trivial one-line code edits where naming is moot — the production wiki-editing.md precedent shows this volume is acceptable.
- misses: naming of headings/test-case labels in markdown, and of new directories created via Bash `mkdir`. Partial closure: the wiki-editing rules file can carry a one-line naming clause for headings; `mkdir` misses are accepted (rare, low harm).
- payload: row 58 verbatim + pointer.

**Row 63 (readable-at-reference-time paths).**
- trigger-spec: Stop hook script — extract absolute paths and `file://` URIs from the agent's final message, `stat` each; on a nonexistent path, inject the materialize-first instruction with the offending path named. Post-hoc is acceptable: the correction lands while the conversation is still live and the path can be re-sent.
- false-fires: paths quoted as examples or historical references — moderate; mitigate by only firing on `file://` URIs and paths presented as "read this" links (heuristic: path on its own line or in a markdown link). Residual over-fire tolerable at this rarity.
- misses: a path that exists locally but holds stale content (right file, wrong version) — undetectable; accepted.
- payload: row 63 verbatim including the `git show origin/<branch>:<path>` recipe.

---

## Section: Code quality (line 68)

| # | Quote | Frequency | Signal | Verdict |
|---|---|---|---|---|
| 64 | "When writing or patching code: detect emergent state machines … prefer structural fixes … handle every fallible op explicitly … never swallow an error" | coding sessions only — zero relevance in comms/review/doc sessions; within a coding session, continuous | file-path — code files being edited; the production file-path-rule mechanism fits exactly | TRIGGER-CANDIDATE |

### Trigger spec — Code quality

**Row 64.**
- trigger-spec: File-path rule injection — same `.claude/rules/code-editing.md` as row 58, `paths: ["**/*.py", "**/*.sh", "**/*.ts", "**/*.js", "scripts/**", ".claude/hooks/**"]`.
- false-fires: config-only edits to matched extensions (a JSON-in-.py constant tweak) — harmless.
- misses: code written inline in Bash heredocs — accepted (rare for substantive code in this repo; hooks and scripts live in files).
- payload: row 64 verbatim + `code-quality.md` pointer.

---

## Section: External consults & session recovery (lines 70–72)

| # | Quote | Frequency | Signal | Verdict |
|---|---|---|---|---|
| 65 | "External-consult MCP = `sonnet` (`mcp__sonnet__*`)" | rare — consult sessions only | weak — the "I want an external consult" moment is internal; the MCP tool listing itself may make the fact discoverable without any injection | BORDERLINE — settled by: check whether the harness's tool listing (deferred-tool names visible in-session, **observed** in this session's own environment) is sufficient for an agent to find `mcp__sonnet__*` unaided; if yes, the line can simply drop with no trigger needed |
| 66 | "auth failure → ask the boss to log into the upstream desktop client" | rare — only at a sonnet auth failure | crisp — the failure is in the tool result | TRIGGER-CANDIDATE |
| 67 | "For context beyond your handoff, read your own + predecessor same-role session transcripts (`~/.claude/projects/…*.jsonl`; predecessor id in handoff front-matter)" | rare — session-recovery moments (post-handoff pickup, post-compact gaps) | SessionStart — **observed**: `handoff-pickup-inject.sh` already fires on `startup\|clear` and injects the handoff; this rule belongs in that payload | TRIGGER-CANDIDATE |

### Trigger specs — External consults & session recovery

**Row 66.**
- trigger-spec: PostToolUse, tool regex `mcp__sonnet__.*`, output regex `(?i)\b(auth|unauthoriz|401|403|not logged in|login required|credential)\b` — inject "ask the boss to log into the upstream desktop client." (A `vet-log.py` PostToolUse hook already exists on this matcher — **observed** — so the matcher pattern is proven; this adds a second hook or extends the payload.)
- false-fires: consult responses that discuss auth as subject matter — rare; tolerable.
- misses: none of note.
- payload: the clause verbatim.

**Row 67.**
- trigger-spec: SessionStart — extend the existing `handoff-pickup-inject.sh` payload with the transcript-recovery instruction (priming half); UserPromptSubmit backstop, prompt regex `(?i)\b(predecessor|previous session|last session|what happened (before|earlier)|transcript)\b` for mid-session recovery moments.
- false-fires: UserPromptSubmit regex fires on casual references to previous sessions — low volume, one-line payload.
- misses: an agent that needs deep context but never phrases it — the SessionStart half covers the common case (recovery need is highest at pickup).
- payload: row 67 verbatim + the two Detail pointers from line 72 (`codex-consultation-log.md`, `session-log-review.md`).

---

## Completion gate

Every rule-bearing line of CLAUDE.md (lines 3–72; line 1 is the title, line 11/72 pointer sentences are folded into their parent rules' payloads, line 34/35's wiki links likewise) appears above as a row with a verdict. Rows: **67**. Tally: **39 TRIGGER-CANDIDATE, 21 KERNEL, 7 BORDERLINE** (39+21+7=67).

## Ranked TRIGGER-CANDIDATEs (strongest first, by kernel-tokens-freed × trigger-crispness × infrastructure-already-exists)

1. Rows 47–48 — tier table → PreToolUse on postal send tools; ~110 words freed, zero false-fires, SessionStart card already primes.
2. Rows 51, 50 — softeners + check-mail → already hook-delivered (`postal-softener-guard.py`, `mail-pull.sh`); kernel lines can drop outright.
3. Rows 25, 27 — staleness-diff + cross-worktree paths → already hook-delivered (`auto-read-before-write.sh`, `cross-worktree-guard.sh`); two Git bullets shrink to clauses.
4. Rows 12–15 — hard-problem-method paragraph → UserPromptSubmit debugging-vocab + Stop shallow-fix backstop; largest contiguous block (~340 words) freed from every non-investigation session.
5. Rows 39–40 + 28 — merge/review protocol → extend `no-raw-gh-pr-merge.sh` to all `gh pr merge` + PreToolUse on `gh pr (review|comment)`; ~120 words of the file's densest lines, existing hooks half-cover it.
6. Rows 17–18 — soft-block override protocol → already delivered by every block's teach message; audit `block-messages.md` for coverage, then keep one kernel clause.
7. Row 64 + 58 — code-quality + naming → one new `.claude/rules/code-editing.md` file-path rule; production mechanism proven by `wiki-editing.md`.
8. Rows 45+53+54 — mail-arrival protocol bundle → PostToolUse on `check_mail` + footer on `mail-pull.sh` delivery; dual delivery with the existing SessionStart card.
9. Rows 23, 24, 26 — nedlern-sync / nedlern-push / shell-edit staleness → three exact-vocabulary PreToolUse Bash matchers, near-zero false-fires.
10. Row 22 — docs/working is scratch → file-path rule on `docs/working/**`; the crispest single-line win in the file.
