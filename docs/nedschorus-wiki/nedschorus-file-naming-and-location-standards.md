# File naming and location standards

Where the kinds of file this project has named live, what each is called, and,
where a rule is written down in more than one place, which writing governs.
A kind of file with no row here has no rule; the page does not claim to be
complete, and the last section lists what is known to be unsettled.

The standards are scattered, and this page maps them without moving them: the
general naming rule sits in the project's root `CLAUDE.md`; four skills,
/cold-read, /ghi-write, /handoff and /walk-me-through, each name their own
files; several names are constants in scripts, each now with one
definition and a test that keeps it that way; and some conventions are only
what the existing files do. The note under "Working files the scripts and
skills create" names those single homes, and the few names still written in
more than one place.

## Terms this page uses

The project glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`, defines
these project terms, which this page uses and does not restate: agent-seat,
agent-session, approval-walk, design-to-main, GHI-MD, handoff-supervisor,
log-store, seat-brief, session-handoff, walk-minutes; cold-read-cell,
cold-read-fast-read, cold-read-full-run, cold-read-grid, cold-read-pass,
cold-read-record, cold-read-target, cold-read-tier; agent-binary, the installed
program a cold-read-cell runs its model through, `claude` or `codex`, adopted
2026-09-18 in place of agent-cli; and the skills /cold-read, /ghi-write,
/handoff and /walk-me-through. The cold-read-tier values are
`deep` and `second`, renamed from `good` and `floor` on the user's ruling of
2026-09-20 because the old names no longer described the models in them.

A few more words are used here in a sense of this page's own:

- **stem**: a filename without its extension.
- the cold-read-grid's code calls `-log`, `-report` and `-capture` genre
  suffixes. This page calls them the name endings the cold-read-grid
  refuses. They are about reviewability only, and are not the "Type"
  column of the first table.
- **suffix**, on this page: the last hyphen-separated part of the filename
  stem, such as `-draft`, not the extension `.md`.

## The one general rule

The project's root `CLAUDE.md` is the authority. Its naming bullet is quoted
here whole, and nowhere paraphrased, because a paraphrase is the copy that
drifts:

> When creating or inventing names, for directories, file names, globals,
> functions, classes, scripts, and other names likely to be grepped, use
> explicit, clear and precise multi-part names. Check newly invented names
> with glob (for path names) or grep (for names in files). If these checks
> return collisions or ambiguity, choose a more explicit name, with 3 or 4
> parts, not 1 or 2. If the thing you are naming already has a name in the
> project, use the existing name instead of inventing a new one.

The other half of the naming rule sits in the same file's glossary bullet,
and is quoted here whole for the same reason:

> If you need to coin a new term, a word with a meaning specific to this
> project, propose it to the user. A hyphenated phrase marks a project-term
> or a system-term; do not hyphenate a phrase that is not one.

One ruling on how far that rule reaches is written outside `CLAUDE.md`, in
`docs/issues/386-project-term-sweep-rulings-and-open-work.md`, ruling 5,
"File names already on main" (user-ruled 2026-09-15):

> the naming rule binds new file names only. An existing file is renamed only
> when someone is already editing it for another reason. No full rename of
> existing files.

## How to read the tables

The values in these tables were copied from the scripts and documents the
Decided by column names, as they stood on main at commit `986bc31` on
2026-09-20. They may be stale: where a value here and its source disagree,
the source is right, and `git log 986bc31..origin/main -- <path>` lists every
change to that source since this page last looked.

Every row names what decided the value, or says nothing did:

- A script and a name in it means that constant or function decides the
  value. The tables show the value so the page can be read on its own.
- A prose file means the prose decides the value and the code that uses it
  carries a copy by hand: no program reads a value out of these documents, so
  a change to the prose must be chased into every copy the note below lists.
- **no written rule** means exactly that: nothing decides the value. The
  cell states what the existing files do, and says so where they disagree
  with each other.

The rule behind citing rather than repeating is stated in
`scripts/cold-read-grid.py`, above its list of the name endings it refuses:

> ONE list, here, because the rule is one rule: a second copy somewhere else is
> how two instruments come to disagree about what a genre is.

Where a value is defined in more than one place today, the row says so and the
note under the second table lists the places.

In every table the Location column holds the directory and the Naming column
holds the filename pattern.

## Repository directories by document type

| Type | Location | Naming | Decided by |
|---|---|---|---|
| Project instruction file | repository root | `CLAUDE.md` | Claude Code |
| Identity file of an agent-seat | repository root of the agent-seat's checkout, never committed | `CLAUDE.local.md` | `CLAUDE.md` |
| Hook wiring | `.claude/` | `settings.json` | Claude Code |
| Skill | `.claude/skills/<skill name>/` | `SKILL.md`; the directory is named for the skill, and the `name:` in its frontmatter agrees with it | no written rule |
| Skill prompt, the text a skill's own reviewer or cell runs | `.claude/skills/<skill name>/prompts/` | `<pass>.md`, named for the pass it drives; `defect-hunt.md`, `terminology.md`, `restate.md`, `fast-clarify.md` exist | no written rule |
| Hook | `.claude/hooks/` | `<what it guards>.py`, hyphenated | no written rule, mixed: three hooks are hyphenated and named for what they guard; the shared module `guard_approval_marker.py` is neither. Existing names stand: a file is renamed, if at all, only when it is already being edited for another reason (the ruling under "The one general rule") |
| Test | beside the thing it tests, in the same directory; a subsystem or system with its own directory puts its tests in a `tests/` subdirectory of it instead, `scripts/design-to-main/tests/` and `nc-systems/main-gatekeeper/tests/` | the stem plus `-test`, before the extension: `scripts/cold-read-grid-test.py`, `.claude/hooks/instruction-file-guard-test.py`; a launcher with no extension gets `-test.py`: `scripts/launch-claude-mac-test.py` | no written rule; for design-to-main's tests, `docs/design-to-main/design-to-main-state-machine-design.md` §9, which puts a component's tests in a `tests/` subdirectory of its directory |
| Standing instructions for a designed agent, or an agent-seat's seat-brief | `docs/agents/` | `<subject>-instructions.md` | `docs/nedschorus-wiki/nedschorus-agent-seat-model.md`, which says an agent-seat's brief lives under `docs/agents`, for a seat-brief; no written rule for a designed agent's |
| Prompt text handed to an agent verbatim: an agent-seat's or agent's first prompt, a sanity-check attack prompt, the appended system prompt | `docs/agents/` | `<subject>-first-prompt.md`, `<subject>-<attack>-attack-prompt.md`, `seat-session-appended-system-prompt.md` | no written rule |
| Wiki page | `docs/nedschorus-wiki/` | `nedschorus-<subject>.md`, which all seven pages on main follow | user-ruled 2026-09-19, for new pages and existing ones alike; the four unprefixed pages were renamed and every citation in the tree swept (PR 541). This narrows the no-full-rename ruling under "The one general rule" for this directory |
| GHI-MD, the document paired with a GitHub issue | `docs/issues/` | `<issue number>-<name>.md` | no written rule; what a GHI-MD is and when one is written is `.claude/skills/ghi-write/SKILL.md` |
| Design document | its issue's GHI-MD in `docs/issues/`, where it is written and refined in place; `docs/design-to-main/` for design-to-main's own; `nc-systems/<system>/` once a system's code starts and the design moves beside it, `nc-systems/main-gatekeeper/main-gatekeeper-design.md` | `<issue number>-<name>.md` as the GHI-MD, so a design carries no ending of its own; `<issue number>-<name>-design.md` is the older form still on main, and `-design` also appears in `docs/drafts/` and `docs/design-to-main/` | user-ruled 2026-09-18, in `.claude/skills/ghi-write/SKILL.md` and `docs/nedschorus-wiki/queue/where-designs-live-and-how-sibling-drift-is-caught.md`: "A design is written in its issue's GHI-MD and refined in place; design-to-main adds the component-contract beside it, and both move into the component's directory when code starts" |
| Design-to-main's own documents: the state machine's design, its glossary, and its scripts under `scripts/design-to-main/` | `docs/design-to-main/` | `design-to-main-<subject>.md` | glossary entry design-to-main; no written rule for the names |
| Python script | `scripts/`; `scripts/design-to-main/` for that subsystem's; `nc-systems/<system>/` for a system kept whole in one directory with its design, record and tests, as the main-gatekeeper has been since 2026-09-19 | `<multi-part-name>.py`, noun-led as often as verb-led: `cold-read-grid.py`, `handoff-supervisor.py`, `restart-live-seats-at-login.py` | no written rule |
| Launcher and shell script | `scripts/` | no extension for the three launchers (`launch-claude-mac`, `launch-claude-ubuntu`, `open-iterm-window-running-command`); `.sh` for two shell scripts | no written rule |
| Queued material, not yet at its home | `docs/nedschorus-wiki/queue/` for wiki-bound doctrine; `docs/issues/queue/` for pair-bound documents; `docs/agents/queue/` for agent-instructions. A design does not queue: since 2026-09-18 it is written in its issue's GHI-MD | as the file will be named at its home, so the drain is a move | `.claude/skills/ghi-write/SKILL.md` step 2; the drain is nedschorus#24 |
| Requested note awaiting its first approval-walk | `nc-queue/`, then `nc-queue/archived/` once walked | `<YYYY-MM-DD>-<slug>.md` | `nc-queue/README.md` |
| Draft of a kind that has no queue | `docs/drafts/` | `<subject>-draft.md` in most tracked cases; `cold-read-tooling-design.md` and the five files under `claude-builtin-code-review-reverse-engineering/` do not use it. `-candidate` marks a version put to the user for review, as against an agent's own draft: a candidate lives untracked in `docs/drafts/` while he reads it, and goes to the log-store's `seats/` kind once the work it served has landed. A seat's other untracked working copies there also use dated stamps and `-r2`, `-r3`, and go the same way | `-candidate` user-ruled 2026-09-19; no written rule for the rest |

A draft of a kind that has a queue goes to the queue, not to `docs/drafts/`;
a `-draft.md` in `docs/walk/` is one of an approval-walk's four files, not an
unplaced draft.

**Unsettled.** Test designs and design contracts have neither a directory nor
a suffix. `.claude/skills/cold-read/SKILL.md` step 1 names both as types that
need a cold-read-full-run, but nothing says what file is one, so an agent cannot
tell from a path whether that rule applies. See the last section.

## Working files the scripts and skills create

| File or directory | Location | Naming | Decided by |
|---|---|---|---|
| Cold-read-record directory | `cold-read-records/` | `<file stem>-<YYYY-MM-DD>`, and `SKILL-<skill name>-<YYYY-MM-DD>` for a skill, whose stem is always `SKILL` and whose name is its directory's, so `.claude/skills/cold-read/SKILL.md` gets `SKILL-cold-read-<date>`; the document comes first so every read of one document sits together in a listing, and the date is the local date of the machine that ran it. Ruled 2026-09-18, replacing a date-first form; two documents with the same stem in different directories, read on one day, come out as `-2` of each other, and the record's `target/` shows which was which | `scripts/cold-read-record-names.py`, `record_directory_name_for_target` and `record_name_for_target`, under its `RECORDS_DIR`; the four programs that create or find cold-read-records import it |
| Same directory, on a same-day collision | as above | `-2`, `-3` appended, counting up, no cap in the code; the cold-read-fast-read and the cold-read-grid share this rule, so on one day the first to run takes the bare name and the next takes `-2` | `scripts/cold-read-record-names.py`, `fresh_record_directory`, which every one of those programs calls |
| Frozen copy of the cold-read-target | inside the cold-read-record | `target/<repository path>`; for a cold-read-target outside the checkout, which both instruments accept, `target/` plus the absolute path without its leading slash | `scripts/cold-read-record-names.py`, `FROZEN_TARGET_DIRECTORY_NAME`, with the path built under it in `frozen_target_path` in the same module, which the cold-read-grid and `scripts/cold-read-fast-read.py` both call. The cold-read-target is resolved before it is made relative, so one document reached by two spellings freezes at one path (user-ruled 2026-09-20) |
| Reviewer report | inside the cold-read-record | `<agent-binary>-<pass token>-<tier>.md`, the pass token being `hunt` for `defect-hunt`; six names are possible, `hunt-deep`, `hunt-second` and `terminology-deep` under each of `claude` and `codex`, and an absent cold-read-cell leaves its name absent. The file says which agent ran which pass and nothing else; the directory says which read (user-ruled 2026-09-18, replacing a name that repeated the record's). A report's own name ends in `-deep` or `-second`, never `-report`, so the cold-read-grid does not refuse it. The two cold-read-tiers were `good` and `floor` until the user renamed them 2026-09-20 (walk `docs/walk/md-skills-seat-open-decisions-2026-09-20.md`, item 5); cold-read-records already in the log-store keep their old file names, so both spellings are found there | `scripts/cold-read-grid.py`, `cell_report_path`; the set of cold-read-cells is `GRID_CELL_ROSTER` |
| Reference check | inside the cold-read-record | `reference-check.md` | `scripts/cold-read-grid.py` |
| A cold-read-cell's stderr | inside the cold-read-record, kept only for an attempt that produced no report: the cold-read-grid deletes the log of an attempt that succeeded | `<report name>.attempt-1.stderr.log` for the first attempt and `.attempt-2.stderr.log` for the retry, since every failed cold-read-cell is retried once (nedschorus#413) | `scripts/cold-read-grid.py` |
| Triage of the reviewers' findings | inside the cold-read-record | `triage.md` (user-ruled 2026-09-18, replacing `dispositions.md`, which now names a walk's fifth file instead) | `.claude/skills/cold-read/SKILL.md`; spelled again in the cold-read-grid's closing text and in the log-store README |
| Cold-read-fast-read of an approval-walk draft | `docs/walk/` | `<walk name>-suggestions.md`, the cold-read-fast-read's report under the name /walk-me-through reads | `.claude/skills/walk-me-through/SKILL.md` names the ending; `scripts/cold-read-fast-read.py` builds it, and `scripts/walk-file-endings-match-the-skill-test.py` holds the two together |
| Cold-read-fast-read of anything else | `cold-read-records/<file stem>-<YYYY-MM-DD>/`, the same record name the cold-read-grid uses | `fast-read.md`, beside `<target stem>-with-sentence-ids.md`, the marked copy the reviewer read; a skill's is `cold-read-records/SKILL-cold-read-<date>/fast-read.md` beside `SKILL-with-sentence-ids.md` | `scripts/cold-read-record-names.py`, `record_name_for_target` for the directory, which `scripts/cold-read-fast-read.py` imports |
| Restater-judge run | `cold-read-records/` | `<YYYY-MM-DD>-restater-judge-<restater class>`, the one cold-read-record kind not named for a cold-read-target | `scripts/cold-read-restater-judge-runner.py` |
| Approval-walk files, four by the approval-walk's close and five for an approval-walk that rules on a cold-read-full-run | `docs/walk/` | `<walk name>-draft.md` first, then `-suggestions.md`, then `<walk name>.md`, then `-minutes.md`, and for a cold-read approval-walk `-dispositions.md` at its close. The approval-walk that rules on a cold-read-full-run is named after that cold-read-record, so its files sit under the record's name (user-ruled 2026-09-18) | `.claude/skills/walk-me-through/SKILL.md` decides the endings, with `.claude/skills/cold-read/SKILL.md` for the fifth file; `WALK_FILE_ROLES` in `scripts/walk-files-ship.py` and the two endings in `scripts/cold-read-fast-read.py` are held to the skill's text by `scripts/walk-file-endings-match-the-skill-test.py` |
| Next-step file, written by /handoff | `~/.claude/handoffs/` | `<seat name>-next-step-<YYYYMMDD-HHMMSS>.md`, which /handoff gives as the expression `~/.claude/handoffs/$(basename "$PWD")-next-step-$(date +%Y%m%d-%H%M%S).md`, to be run rather than composed; the seat name is the working directory's name, the agent-seat name the handoff-supervisor watches | `.claude/skills/handoff/SKILL.md` step 1; the same name is the default `--agent` of `scripts/handoff-write-and-check-supervisor.py`, `default_agent_name` |
| The handoff-supervisor's own files | `~/.claude/handoffs/` by default, or the directory its `--handoff-dir` names | `<seat name>-handoff.md`, `<seat name>-handoff-<NNNN>.md`, `<seat name>-dialog-<NNNN>.md` and its `-complete.md` companion, `<seat name>-supervisor.lock`, `<seat name>-supervisor-state.json`. Of the numbered files it keeps the two newest generations of `-handoff-<NNNN>.md` and of `-dialog-<NNNN>.md`, a `-complete.md` companion counting as part of its generation, and deletes the older ones | `scripts/handoff-supervisor.py`: the state and lock names through `supervisor_state_path()` and `supervisor_lock_path()` over `SUPERVISOR_STATE_FILE_SUFFIX` and `SUPERVISOR_LOCK_FILE_SUFFIX`, and the generations through `prune_old_generations` with `GENERATIONS_KEPT`; the dialog files are written by `scripts/handoff-extract-conversation.py`; the handoff file's own name through `handoff_file_path()` and `handoff_file_paths()` over `HANDOFF_FILE_SUFFIX` |
| Retired session-handoff, moved there by hand when an agent-seat is retired | `~/.claude/handoffs/retired/`, created if needed | `<seat name>-handoff-<YYYY-MM-DD>.md`; if that name exists, `-2`, `-3` before `.md`, never onto an existing archive | `docs/nedschorus-wiki/nedschorus-agent-seat-model.md`, "Pausing and retiring a seat", step 2 |

**One definition each, and the guards that hold them there.** Four sets of
repeated names were reduced to one definition apiece, three on 2026-09-19 and
the handoff file's on 2026-09-20 (user-ruled on both days), each with a test
that a second definition does not come back:

- What a cold-read-record is called lives in
  `scripts/cold-read-record-names.py`, a module and nothing else, imported by
  the four programs that create or find cold-read-records. Seven places had
  carried their own `RECORDS_DIR`, `FROZEN_TARGET_DIRECTORY_NAME`, or copies
  of the naming and same-day-collision rules. The copies had a stated reason
  — that a program cannot be imported — and a module answers it. The path
  built under the frozen copy's directory, `frozen_target_path`, moved into
  the same module on 2026-09-20 (user-ruled): it was defined in each
  launcher and the two disagreed over whether to resolve the
  cold-read-target first, and the resolving version was kept. Guard:
  `scripts/cold-read-record-names-test.py`.
- The supervisor's state and lock file names are
  `SUPERVISOR_STATE_FILE_SUFFIX` and `SUPERVISOR_LOCK_FILE_SUFFIX` in
  `scripts/handoff-supervisor.py`, reached through `supervisor_state_path()`
  and `supervisor_lock_path()`. Eleven production sites across five scripts
  had built those names by hand, two of them inside the file that defines the
  constants. Guard: `scripts/supervisor-file-names-defined-once-test.py`.
- The handoff file's name is `HANDOFF_FILE_SUFFIX` in
  `scripts/handoff-supervisor.py`, reached through `handoff_file_path()` for one
  seat's and `handoff_file_paths()` for every seat's in a directory. Eight
  production sites across four scripts had built it by hand, one of them a
  local `suffix` variable that also globbed with it. Guard: the same
  `scripts/supervisor-file-names-defined-once-test.py`, which covers all three
  of the supervisor's names. The helper is `handoff_file_path`, not
  `handoff_path`: that name is already the `SupervisorSettings` property the
  supervisor reads the path through.
- The approval-walk files' endings are decided by
  `.claude/skills/walk-me-through/SKILL.md`. Prose cannot be imported, so the
  tie-break is a test rather than a constant, and it runs one way only: a
  program may not build an ending the skill does not name, though the skill
  may name an ending no program builds yet. Guard:
  `scripts/walk-file-endings-match-the-skill-test.py`.

**What is still written more than once.** The glossary restates two file names
in prose, `docs/agents/<seat>-instructions.md` under seat-brief and
`~/.claude/handoffs/<seat>-handoff.md` under session-handoff. The writings in
each set agree today, and nothing keeps them agreeing; none is the authority
over the others, which is the defect. `RECORDS_DIR` is also a two-part name a
grep confuses with `RECORDS_DIRECTORY_NAME` in
`scripts/sanity-check-attacks.py`, a different instrument's constant.

Each of those guards carries a list of what it does not catch. That list is
not documentation of the guard: it is the instrument that tests it. Across
the eight pull requests this consolidation took on 2026-09-19, every review
finding landed on the guards and none on the consolidation itself.

## Filename suffixes an instrument reads

The last suffix on the stem is the one an instrument obeys, because each
instrument tests only what the stem ends with: `-test-log` is refused as a
log, `-draft-design` is not an approval-walk draft.

| Suffix | Effect | Decided by |
|---|---|---|
| `-log`, `-report`, `-capture` | the cold-read-grid refuses the document: it prints the refusal to whoever ran it, exits 2 and creates no cold-read-record. The cold-read-fast-read makes no such check, so such a document gets its cold-read-fast-read and is then refused by the cold-read-grid. If the document should be reviewed, the refusal text says to rename it out of those endings or amend nedschorus#152 | `scripts/cold-read-grid.py`, `UNREVIEWABLE_TARGET_GENRE_SUFFIXES`, whose comment defines the three together as documents that only record what happened |
| `-draft`, in `docs/walk/` only | routes the cold-read-fast-read's report to `-suggestions.md` beside the draft | `scripts/cold-read-fast-read.py`, `WALK_DRAFT_SUFFIX` |

The cold-read-grid checks only the three suffixes of the first row. A stem
ending in any other suffix is not one of them: the document passes the
check and is reviewed like any other.

Two more suffixes follow no written rule and no instrument reads them: `-test` marks a
test, beside the thing it tests or in a `tests/` subdirectory, and `-design`
marks a design document wherever it sits.

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
`cold-read-records/`, `sanity-check-records/`, `walk/`, `transcripts/`,
`seats/`. A sixth kind, `analysis/`, was ruled into being on 2026-09-14, and
the directory exists in the log-store, but it is not in that README.

- **Cold-read-records** reach the log-store because the cold-read-grid and
  the cold-read-fast-read each run the shipper when the run ends, and the
  shipper is add-only. The local directory is kept afterwards, not deleted,
  because the cold-read-records are useful for analysis later
  (`.claude/skills/cold-read/SKILL.md` step 7). The
  comment above `cold-read-records/` in `.gitignore` says the opposite and is
  stale. Every entry there is a dated directory except
  `stub-runs-not-reviews/`, which holds the cold-read-grid's test-run
  cold-read-targets.
- **Approval-walk files** are shipped by `scripts/walk-files-ship.py <walk
  name>`, which the /walk-me-through skill's Closing section runs at the
  approval-walk's close, that is when the last item is ruled, and again
  whenever an approval-walk is reopened and closed. The files go flat into
  the log-store's `walk/`, never into a subdirectory of it, and the program
  builds the five paths from the name rather than globbing `docs/walk/<walk
  name>*`, because one approval-walk's name can be a prefix of another's. Its
  one line ends with the minutes' citation, and a line opening `FAILED` or
  `REFUSED` is shown to the user as it is. The draft, the suggestions and the
  walk text are add-only, refused by name if a later run offers different
  bytes; the minutes and the dispositions are replaced, each displaced copy's
  sha256 announced on stderr (user-ruled 2026-09-18, because both are updated
  after the close). The local copies stay in `docs/walk/`.

- **A seat's shared files** go to `seats/<agent-seat name>/`, the one kind
  organized by producer rather than by kind, through
  `scripts/seat-shared-file-ship.py`, which prints the citation to paste. It
  holds what one agent-seat must share and no other kind covers: a
  measurement output, a survey, a scratch report another agent-seat is asked
  to read, and a seat's drafts once the work they served has landed. A seat
  replaces its own files there, unlike the records beside them, which are
  add-only (user-ruled 2026-09-09).
- An **analysis** is a study across records of the numbers the instruments
  produce, such as findings counts, coverage and durations, written to answer
  a question; a review is of one document and lives in that document's
  cold-read-record. An analysis lives in the log-store under `analysis/`,
  named `<YYYY-MM-DD>-<subject>-analysis.md` as the three there are named
  (`2026-08-30-criterion-tag-effectiveness-analysis.md`,
  `2026-08-30-restate-vs-stumble-location-analysis.md` and
  `2026-09-15-cold-read-grid-union-and-effort-analysis.md`, which
  `scripts/cold-read-claude-cell.py` and `scripts/cold-read-codex-cell.py`
  cite), and not in the repository (user-ruled 2026-09-14: analyses "seem
  about as useful as other logs, which are useful occassionally [sic], but
  should not clutter up main").

## What is unsettled

Listed so a reader knows these are open rather than missing. Each is a
decision for the user, tracked at the MD-skills agent-seat.

- Where a test design goes, and what marks one. Where a design itself goes
  was ruled on 2026-09-18, and design-to-main's component-contract goes
  beside it; a test design was not named in that ruling.
- Whether `.claude/skills/cold-read/SKILL.md`'s "design contract" and
  design-to-main's `component-contract` are one document under two names.
- Whether the document types that need a cold-read-full-run, listed in
  `.claude/skills/cold-read/SKILL.md`, should be recognized by directory, by
  suffix, or by both, and where that list then lives so the skill's prose and
  the cold-read-grid's code do not each carry a copy.
- Whether kept cold-read-records, and `docs/walk/`, need a retention limit
  as they accumulate; until ruled, everything is kept.
