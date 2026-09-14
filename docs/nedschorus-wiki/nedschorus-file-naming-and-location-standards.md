# File naming and location standards

Where the kinds of file this project has named live, what each is called, and,
where a rule is written down in more than one place, which writing governs.
A kind of file with no row here has no rule; the page does not claim to be
complete, and the last section lists what is known to be unsettled.

The standards are scattered, and this page maps them without moving them: the
general naming rule sits in the project's root `CLAUDE.md`; four skills each
name their own files; several names are constants in scripts, some defined in
more than one script; and some conventions are only what the existing files
do. The note under "Working files the scripts and skills create" lists the
names defined more than once.

## Terms this page uses

The project glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`, defines
agent-seat, design-to-main, GHI-MD, handoff-supervisor, log-store, session
handoff, walk minutes and the four skills named below. Six more words come
from the cold-read scripts and are used here in their sense:

- **cold-read grid**: `scripts/cold-read-grid.py`, which runs six fresh
  reviewers over one document and saves their reports in a dated directory.
- **fast read**: `scripts/cold-read-fast-read.py`, one cheap reviewer run
  before the grid.
- **record**: the dated directory one cold-read run leaves under
  `cold-read-records/`, with everything the run produced.
- **target**: the document a cold read is run against; its **stem** is its
  filename without the extension.
- **pass**: which reviewer prompt a grid cell ran, `defect-hunt` or
  `terminology`; **tier**: which model it ran on, `good` or `floor`;
  **runtime**: which program ran it, `claude` or `codex`. The tier names are
  ruled misleading and due to change (task at the MD-skills seat).
- **genre**: the grid's word for the three filename endings it refuses; it is
  about reviewability only and is not the "Type" column of the first table.
- **suffix**, on this page: the last hyphen-separated part of the filename
  stem, such as `-draft`, not the extension `.md`.

## The one general rule

The project's root `CLAUDE.md` is the authority. Its naming bullet is quoted
here whole, and nowhere paraphrased, because a paraphrase is the copy that
drifts:

> When creating or inventing names, for directories, file names, globals,
> functions, classes, scripts, section headings, and other names likely to be
> grepped, use explicit, clear and precise multi-part names. Check newly
> invented names with glob (for path names) or grep (for names in files). If
> these checks return collisions or ambiguity, choose a more explicit name,
> with 3 or 4 parts, not 1 or 2. If the thing you are naming already has a
> name in the project, use the existing name instead of inventing a new one.

## How to read the tables

Every row names an **authority**, or says there is none:

- A script and a name in it means that constant or function decides the
  value. The tables show the value so the page can be read on its own; the
  value on this page is a copy, and where the two disagree the script is
  right and this page is stale.
- A prose file means the prose decides the value and the code that uses it
  carries a copy by hand: no program reads a value out of these documents, so
  a change to the prose must be chased into every copy the note below lists.
- **practice** means there is no written rule. The cell states what the
  existing files do, and says so where they disagree with each other.

The rule behind citing rather than repeating is stated in
`scripts/cold-read-grid.py`, above its list of refused genres:

> ONE list, here, because the rule is one rule: a second copy somewhere else is
> how two instruments come to disagree about what a genre is.

Where a value is defined in more than one place today, the row says so and the
note under the second table lists the places. None of those definitions wins
over the others: there is no tie-break if they diverge, and that is the
defect the note records.

In every table the Location column holds the directory and the Naming column
holds the filename pattern.

## Repository directories by document type

| Type | Location | Naming | Authority |
|---|---|---|---|
| Project instruction file | repository root | `CLAUDE.md` | Claude Code |
| Per-seat identity file | repository root of the seat's checkout, never committed | `CLAUDE.local.md` | `CLAUDE.md` |
| Hook wiring | `.claude/` | `settings.json` | Claude Code |
| Skill | `.claude/skills/<skill name>/` | `SKILL.md`; the directory is named for the skill, and the `name:` in its frontmatter agrees with it | practice |
| Skill prompt, the text a skill's own reviewer or cell runs | `.claude/skills/<skill name>/prompts/` | `<pass>.md`, named for the pass it drives; `defect-hunt.md`, `terminology.md`, `restate.md`, `fast-clarify.md` exist | practice |
| Hook | `.claude/hooks/` | `<what it guards>.py`, hyphenated | practice, mixed: three hooks are hyphenated and named for what they guard; the shared module `guard_approval_marker.py` is neither |
| Test | beside the thing it tests, in the same directory | the stem plus `-test`, before the extension: `scripts/cold-read-grid-test.py`, `.claude/hooks/instruction-file-guard-test.py` | practice |
| Standing instructions for a designed agent or a seat | `docs/agents/` | `<subject>-instructions.md` | practice |
| Prompt text handed to an agent verbatim: a seat's or agent's first prompt, a sanity-check attack prompt, the appended system prompt | `docs/agents/` | `<subject>-first-prompt.md`, `<subject>-<attack>-attack-prompt.md`, `seat-session-appended-system-prompt.md` | practice |
| Wiki page | `docs/nedschorus-wiki/` | `nedschorus-<subject>.md` on two of the five tracked pages; the other three carry no prefix | practice, mixed |
| GHI-MD, the document paired with a GitHub issue | `docs/issues/` | `<issue number>-<name>.md` | practice; what a GHI-MD is and when one is written is `.claude/skills/ghi-write/SKILL.md` |
| Design document | `docs/issues/` when paired with an issue; `docs/design-to-main/` for design-to-main's own | `<issue number>-<name>-design.md`; `-design` also appears in `docs/drafts/` and `docs/design-to-main/` | practice |
| Design-to-main's own documents: the state machine's design, its glossary, and its scripts under `scripts/design-to-main/` | `docs/design-to-main/` | `design-to-main-<subject>.md` | glossary entry design-to-main; practice for the names |
| Python script | `scripts/`, or `scripts/design-to-main/` for that subsystem's | `<multi-part-name>.py`, noun-led as often as verb-led: `cold-read-grid.py`, `handoff-supervisor.py`, `restart-live-seats-at-login.py` | practice |
| Launcher and shell script | `scripts/` | no extension for the three launchers (`launch-claude-mac`, `launch-claude-ubuntu`, `open-iterm-window-running-command`); `.sh` for two shell scripts | practice |
| Queued material, not yet at its home | `docs/nedschorus-wiki/queue/` for wiki-bound doctrine; `docs/issues/queue/` for issue-bound documents; `docs/agents/queue/` for agent instructions; `docs/designs/queue/` for designs before code, named though not yet created | as the file will be named at its home, so the drain is a move | `.claude/skills/ghi-write/SKILL.md` step 2; the drain is nedschorus#24 |
| Requested note awaiting its first walk | `nc-queue/`, then `nc-queue/archived/` once walked | `<YYYY-MM-DD>-<slug>.md` | `nc-queue/README.md` |
| Draft of a kind that has no queue | `docs/drafts/` | `<subject>-draft.md` in every tracked case; the untracked working copies there also use `-candidate`, dated stamps and `-r2`, `-r3` | practice |

A draft of a kind that has a queue goes to the queue, not to `docs/drafts/`;
a `-draft.md` in `docs/walk/` is one of a walk's four files, not an unplaced
draft.

**Unsettled.** Test designs and design contracts have neither a directory nor
a suffix. `.claude/skills/cold-read/SKILL.md` step 1 names both as types that
need a full cold read, but nothing says what file is one, so an agent cannot
tell from a path whether that rule applies. See the last section.

## Working files the scripts and skills create

| File or directory | Location | Naming | Authority |
|---|---|---|---|
| Cold-read record directory | `cold-read-records/` | `<YYYY-MM-DD>-<target stem>`; the date is the local date of the machine that ran it, and the stem alone does not tell two same-named targets apart, so every skill's record is `<date>-SKILL` | `scripts/cold-read-grid.py`, `make_record_dir`, under `RECORDS_DIR`; defined again elsewhere, see the note below |
| Same directory, on a same-day collision | as above | `-2`, `-3` appended, counting up, no cap in the code; the fast read and the grid share this rule, so on one day the first to run takes the bare name and the next takes `-2` | `scripts/cold-read-grid.py`, `make_record_dir`; defined again elsewhere, see the note below |
| Frozen copy of the target | inside the record directory | `target/<repository path>`; for a target outside the checkout, which both instruments accept, `target/` plus the absolute path without its leading slash | `scripts/cold-read-grid.py`, `frozen_target_path`; defined again in the fast read, see the note below |
| Reviewer report | inside the record directory | `<record directory name>--<runtime>-<pass token>-<tier>.md`, the pass token being `hunt` for `defect-hunt`; six names are possible, `hunt-good`, `hunt-floor` and `terminology-good` under each runtime, and a failed cell leaves its name absent. A report's own name ends in `-good` or `-floor`, never `-report`, so the grid does not refuse it | `scripts/cold-read-grid.py`, `cell_report_path`; the set of cells is `GRID_CELL_ROSTER` |
| Reference check | inside the record directory | `<record directory name>--reference-check.md` | `scripts/cold-read-grid.py` |
| A cell's stderr | inside the record directory, kept | `<report name>.stderr.log` | `scripts/cold-read-grid.py` |
| Dispositions of the reviewers' findings | inside the record directory | `dispositions.md` | `.claude/skills/cold-read/SKILL.md` step 7; spelled again in the grid's closing text and in the log-store README |
| Fast read of a walk draft | `docs/walk/` | `<walk name>-suggestions.md`, the fast read's report under the name the walk-me-through skill reads | `scripts/cold-read-fast-read.py`, and the walk skill states it too, see the note below |
| Fast read of anything else | `cold-read-records/<YYYY-MM-DD>-<target stem>/` | `<target stem>-fast-read.md`, beside `<target stem>-with-sentence-ids.md`, the marked copy the reviewer read | `scripts/cold-read-fast-read.py` |
| Restater-judge run | `cold-read-records/` | `<YYYY-MM-DD>-restater-judge-<restater class>`, the one record kind not named for a target | `scripts/cold-read-restater-judge-runner.py` |
| Walk files, four by the walk's close | `docs/walk/` | `<walk name>-draft.md` first, then `-suggestions.md`, then `<walk name>.md`, then `-minutes.md` | `.claude/skills/walk-me-through/SKILL.md`; the fast read hard-codes `-draft.md` and `-suggestions.md`, see the note below |
| Next-step file, written by the handoff skill | `~/.claude/handoffs/` | `<seat name>-next-step-<YYYYMMDD-HHMMSS>.md`; the seat name is the `--agent` value the supervisor runs under | `.claude/skills/handoff/SKILL.md` |
| The supervisor's own files | `~/.claude/handoffs/` by default, or the directory its `--handoff-dir` names | `<seat name>-handoff.md`, `<seat name>-handoff-<NNNN>.md`, `<seat name>-dialog-<NNNN>.md` and its `-complete.md` companion, `<seat name>-supervisor.lock`, `<seat name>-supervisor-state.json` | `scripts/handoff-supervisor.py`, the path properties around its `state_path`; the dialog files are written by `scripts/handoff-extract-conversation.py`; the state suffix is defined again elsewhere, see the note below |

**More than one definition today.** `RECORDS_DIR` is defined in four scripts:
`scripts/cold-read-grid.py`, `scripts/cold-read-record-ship.py`,
`scripts/cold-read-fast-read.py` and `scripts/cold-read-restater-judge-runner.py`.
The same-day collision rule is coded in the same three that create records.
`FROZEN_TARGET_DIRECTORY_NAME` and the frozen-path rule are in the grid and
the fast read. `SUPERVISOR_STATE_FILE_SUFFIX` is in `scripts/handoff-supervisor.py`
and `scripts/restart-live-seats-at-login.py`, and the supervisor composes the
path from a literal besides. The walk files' `-draft.md` and `-suggestions.md`
are stated in the walk skill and hard-coded in the fast read. Within each set
the definitions agree now, and no shared constant or test keeps them the
same. None is the authority over the others, which is the defect: there is no
tie-break if they diverge. `RECORDS_DIR` is also a two-part name that a grep
confuses with `RECORDS_DIRECTORY_NAME` in `scripts/sanity-check-attacks.py`,
which is a different instrument's constant.

## Filename suffixes an instrument reads

The last suffix on the stem is the one an instrument obeys, because each
instrument tests only what the stem ends with: `-test-log` is refused as a
log, `-draft-design` is not a walk draft.

| Suffix | Effect | Authority |
|---|---|---|
| `-log`, `-report`, `-capture` | the cold-read grid refuses the document: it prints the refusal to whoever ran it, exits 2 and creates no record. The fast read makes no such check, so such a document gets its fast read and is then refused by the grid. If the document should be reviewed, the refusal text says to rename it out of the genre or amend nedschorus#152 | `scripts/cold-read-grid.py`, `UNREVIEWABLE_TARGET_GENRE_SUFFIXES`, whose comment defines the three together as documents that only record what happened |
| `-draft`, in `docs/walk/` only | routes the fast read's report to `-suggestions.md` beside the draft | `scripts/cold-read-fast-read.py`, `WALK_DRAFT_SUFFIX` |

The grid checks only the three suffixes of the first row. A stem ending in
any other suffix is not a genre to it: the document passes the check and is
reviewed like any other.

Two more suffixes are practice and no instrument reads them: `-test` marks a
test beside the thing it tests, and `-design` marks a design document
wherever it sits.

## What is never committed

Logs live in the log-store. The project's root `CLAUDE.md` defines both, and
is quoted here whole rather than paraphrased:

> Logs — the byproducts of the work that are not the system, cold-read
> records first — live on ned-box in the log-store
> `/home/nedlern/nedschorus-logs/`, never in the repository; cite a file
> there as `nedlern@ned-box:/home/nedlern/nedschorus-logs/<path>`, the scp
> form, which works from either machine.

The two machines are the user's Mac and ned-box. The citation form is a path,
not a command: it resolves from either machine and is what `scp` takes as its
remote operand. "Never in the repository" means never committed: a gitignored
directory under the checkout, such as `cold-read-records/` or `docs/walk/`, is
where logs are made before they are shipped.

The log-store's kinds are written into its own `README.md` by
`scripts/cold-read-record-ship.py`, whose `STORE_README` is the authority:
`cold-read-records/`, `walk/`, `transcripts/`, `seats/`. A fifth kind,
`analysis/`, was ruled into being on 2026-09-14 and is not yet in that README.

- **Cold-read records** reach the store because the grid and the fast read
  each run the shipper when the run ends, and the shipper is add-only. The
  local directory is kept afterwards, not deleted, because the records are
  useful for analysis later (`.claude/skills/cold-read/SKILL.md` step 7). The
  comment above `cold-read-records/` in `.gitignore` says the opposite and is
  stale. Every entry there is a dated directory except
  `stub-runs-not-reviews/`, which holds the grid's test-run targets.
- **Walk files** are shipped by hand at the walk's close, that is when the last
  item is ruled, by the agent running the walk. The four files go flat into
  the store's `walk/`, never into a subdirectory of `walk/`, named
  explicitly rather than by a glob, because one walk's name can be a prefix
  of another's. A walk name is used once; the local copies stay in
  `docs/walk/`.

      scp docs/walk/<walk name>.md docs/walk/<walk name>-draft.md \
          docs/walk/<walk name>-suggestions.md docs/walk/<walk name>-minutes.md \
          nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/

- An **analysis** is a study across records of the numbers the instruments
  produce, such as findings counts, coverage and durations, written to answer
  a question; a review is of one document and lives in that document's
  record. An analysis lives in the log-store under `analysis/`, named
  `<YYYY-MM-DD>-<subject>-analysis.md` as the two there are named
  (`2026-08-30-criterion-tag-effectiveness-analysis.md` and
  `2026-08-30-restate-vs-stumble-location-analysis.md`), and not in the
  repository (user-ruled 2026-09-14: analyses "seem about as useful as other
  logs, which are useful occassionally [sic], but should not clutter up
  main").

## What is unsettled

Listed so a reader knows these are open rather than missing. Each is a
decision for the user, tracked at the MD-skills seat.

- Where a test design or a design contract goes, and what marks one; and
  whether the document types that need a full cold read, listed in
  `.claude/skills/cold-read/SKILL.md` step 1, should be recognized by
  directory, by suffix, or by both, and where that list then lives so the
  skill's prose and the grid's code do not each carry a copy.
- Which of the repeated definitions listed under the second table survives
  when they are reduced to one each.
- Whether the wiki's `nedschorus-` prefix is the rule, given that three of
  five pages lack it.
- Whether `-candidate` is a second draft suffix or a stray.
- Whether kept record directories, and `docs/walk/`, need a retention limit
  as they accumulate; until ruled, everything is kept.
