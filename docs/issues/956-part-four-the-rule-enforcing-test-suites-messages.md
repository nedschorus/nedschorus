---
issue: "[Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956)"
---

# Part four: the messages of the test suites that enforce a repository-wide rule

This document is part four of GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956). The GHI's GHI-MD, `docs/issues/956-every-refusal-and-warning-a-program-hands-an.md`, is part one, and its section "Later parts" lists the parts after it. Part two, `docs/issues/956-part-two-the-git-hooks-messages.md`, covered the git hooks. This part covers what ten test suites print when the repository breaks a rule they check. It shows each such message that leaves the agent a question open, as the agent sees the message, and proposes the exact words to replace it, with the code changes the new words need. None of the proposed wording is built. Four questions in it are the user's to decide; each is marked "Question for the user". The next action is one approval-walk with the user over the proposed texts and the four questions, then one pull request, cut from main, that builds what the user approves, with its test cases.

## What a reader needs first

**Which suites, and which of their messages.** A test suite here is a file named `*-test.py` that `scripts/run-all-test-suites.py` runs. Each of the ten suites below has at least one case that reads the repository itself and fails when the repository breaks a rule that spans files: that no two tracked files share a name, that a list in one file matches the definitions in another, that a design document and the code agree. This part covers only those cases. Most of these suites also test their own checking code on planted examples, called fixture cases; a fixture case fails only when the suite's checking code is wrong, and this part leaves fixture cases out. The suites are:

- `scripts/file-name-collision-warning-hook-test.py`, for its last case, which checks the repository's tracked files; its other cases test the hook program
- `scripts/system-glossaries-listed-on-the-project-glossary-test.py`
- `scripts/pr-reviewer-instructions-copies-test.py`
- `scripts/supervisor-file-names-defined-once-test.py`
- `scripts/walk-file-endings-match-the-skill-test.py`
- `scripts/nedschorus-glossary-alphabetical-order-test.py`
- `nc-systems/cold-read/tests/cold-read-record-names-test.py`
- `scripts/design-to-main/tests/design-to-main-design-names-exist-in-state-tables-test.py`
- `scripts/design-to-main/tests/design-to-main-design-rows-pair-with-state-tables-test.py`
- `scripts/force-push-with-open-pull-request-guard-hook-test.py`, for its two cases that read `.claude/settings.json`

**Who reads the failure.** An agent runs the suites its change can affect before pushing, as CLAUDE.md says: "Before pushing, run only the test suites your change can affect: `python3 scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main`." merge-lane-2 runs the same selection on a pull request's head commit merged onto main. The reader is often an agent whose change broke a rule written in a file the agent has not read, such as a skill, a design or `.claude/settings.json`. So each proposed message says which rule broke, where the rule is written, and how to fix it under each condition that can cause the failure. In the proposed texts, "your change" means everything the reader's branch changes against main, committed or not; when merge-lane-2 reads a failure, "your change" is the pull request it is merging, and merge-lane-2 handles the failure as a finding on that pull request.

**How a failure is printed.** Eight of the ten suites print each case through a `check()` function: `PASS  <case name>`, or `FAIL  <case name>: <detail>`, where the detail can run to several lines. The proposed texts change the detail and keep the case name. The two design-to-main suites use Python's `unittest`: a failed assertion prints the values it compared and then, after a colon, the assertion's own message, if it has one. A case inside a `subTest` also prints the subtest's values in its heading.

**Files the instruction-file guard protects.** `.claude/hooks/instruction-file-guard.py` refuses an Edit or a Write of certain files unless `.walk-approved`, at the root of the agent-session's own checkout, holds an approval. It protects, among others, every file under `.claude/` except `.claude/worktrees/`, `.claude/jobs/` and `.claude/handoffs/`; `CLAUDE.md`; every `.md` file under `docs/agents/`, `docs/nedschorus-wiki/` and `nc-systems/skills/`; and every file whose name ends `-design.md`. Several fixes below land in such a file: `.claude/skills/walk-me-through/SKILL.md`, `.claude/settings.json`, `docs/nedschorus-wiki/nedschorus-glossary.md`, `docs/design-to-main/design-to-main-state-machine-design.md` and `CLAUDE.md`. CLAUDE.md gives two paths for such an edit: "In a file the instruction-file guard protects, fix an obvious error without asking the user first. An edit that changes what an agent or a program is told to do, or what a document decides, is not an obvious error: it goes to the user before you make it". For a fix in a protected file, the proposed texts end with this line, called the guarded-file line below, with `{file}` filled in:

```
{file} is protected by the instruction-file guard: if the fix only corrects an obvious error as CLAUDE.md lists them, write "Obvious fix under CLAUDE.md's standing approval:" and what you are fixing into .walk-approved before the edit; otherwise ask the user to approve the change before you make it.
```

**The four questions.** As in parts one and two, a message is complete when the message says:

1. What was refused or found, naming the file or the command.
2. Why: the rule being enforced, or what goes wrong if the agent goes ahead.
3. What to do instead, as an instruction.
4. Under which condition each instruction applies, when the message gives more than one.

**Where the list comes from.** Part one's audit put these four questions to 139 messages printed by this repository's programs; its report is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/MD-skills/refusal-and-warning-message-audit-2026-10-01.md`. It read these ten suites at the commit [Merge pull request #883 from nedschorus/pull-request-head-test-run-keeps-every-run-of-a-commit-in-the-commits-log](https://github.com/nedschorus/nedschorus/commit/cfd6516f) and flagged 20 of their messages. Every message below was read again from main at the commit [Merge pull request #1075 from nedschorus/ghi-956-edit-ghipairef15a4328a1316b6](https://github.com/nedschorus/nedschorus/commit/c16466b6), and the line numbers are main's at that commit. The rereading found all 20 still open and one more, the phrase assertions of section 17.

## What every failure should tell the agent

Each proposed text keeps the case name and gives a new detail, in this order:

- what was found, as today, with the file named in full where today's text gives only a basename;
- one sentence saying the rule and why it holds, naming the file that writes the rule when one does;
- one line per fix, each opening with the condition it applies under; the conditions of one message do not overlap, so exactly one line applies;
- the guarded-file line, when a fix lands in a protected file.

A rule can also break on main without the reader's change: the suite selection skips a suite whose recorded inputs a pull request did not change, so two pull requests that each pass can break a rule once both have merged. The reader can tell by listing what the branch changes against main, committed or not, with `git diff --name-status $(git merge-base HEAD origin/main)`. Question A below asks what the agent does then.

**Question for the user, A: a rule broken on main, not by the agent's change.** When the files a failure names are not among the files the agent's change touches, the proposal adds one closing line to every message:

```
If your change touched none of the files named above, the failure was already on main: tell the user this message, and leave the fix out of your own pull request.
```

The fix then goes on its own topic branch, as CLAUDE.md requires of a change outside the topic. Recommendation: approve, so that an agent never folds an unrelated fix into its own pull request, and the user hears of a rule main broke.

## The messages, one at a time

### 1. Two tracked files share a name

**When an agent sees this.** An agent adds a second program named `branch-conflict-check.py` under `nc-systems/handoff/` with `git add`, while `scripts/branch-conflict-check.py` exists, and runs the suite.

**What the agent is told today** (`scripts/file-name-collision-warning-hook-test.py:480`; when `git ls-files` exits nonzero or lists no file, the same case prints that error instead, at `:477`):

```
FAIL  no two tracked files in this repository share a name: over 446 names: branch-conflict-check.py: nc-systems/handoff/branch-conflict-check.py, scripts/branch-conflict-check.py
```

```
FAIL  no two tracked files in this repository share a name: git ls-files exited 128 in /Users/el/agents/wt-x: fatal: not a git repository
```

**What the agent cannot tell from the text.** Why two files may not share a name, what to do, and, for the second form, that the repository's names were not checked.

**Proposed text** (`{listing}` and `{error}` are today's details):

```
FAIL  no two tracked files in this repository share a name: {listing}
Two tracked files may not share a basename, compared ignoring case, except SKILL.md, README.md and .gitkeep: the rule is in scripts/file-name-collision-warning-hook.py, because checks that find a moved file search by its name.
If a file your change added or renamed is among those files, rename it by CLAUDE.md's naming rule and update what points at it.
```

```
FAIL  no two tracked files in this repository share a name: {error}
The suite could not list this checkout's tracked files, so it did not check their names.
Fix what the line above reports, then run this suite again.
```

### 2. No paragraph of the project glossary carries the listing paragraph's wording

**When an agent sees this.** An agent rewords the paragraph of `docs/nedschorus-wiki/nedschorus-glossary.md` that lists the system glossaries, or deletes it, so that no paragraph carries the sentence "A new system glossary is listed here when it is created".

**What the agent is told today** (`scripts/system-glossaries-listed-on-the-project-glossary-test.py:168`):

```
FAIL  the project glossary's paragraph listing the system glossaries is located: the paragraph could not be located: no paragraph of docs/nedschorus-wiki/nedschorus-glossary.md carries "A new system glossary is listed here when it is created" — put that wording back in the paragraph above the entries, or set SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR in scripts/system-glossaries-listed-on-the-project-glossary-test.py to wording that paragraph carries
```

**What the agent cannot tell from the text.** Which fix applies when, why the suite needs the paragraph, and that the glossary is protected.

**Proposed text** (`{page}`, `{anchor}` and `{suite}` as today):

```
FAIL  the project glossary's paragraph listing the system glossaries is located: the paragraph could not be located: no paragraph of {page} carries "{anchor}", the wording this suite finds that paragraph by; without the paragraph it cannot check that every system glossary is listed.
If your change reworded or removed that wording by mistake, put it back.
If the new wording is meant to stay, set SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR in {suite} to wording only the listing paragraph carries.
If your change deleted the listing paragraph on purpose, put the question to the user before you go on: the suite needs a paragraph that lists the system glossaries.
{page} is protected by the instruction-file guard: if the fix only corrects an obvious error as CLAUDE.md lists them, write "Obvious fix under CLAUDE.md's standing approval:" and what you are fixing into .walk-approved before the edit; otherwise ask the user to approve the change before you make it.
```

### 3. Several paragraphs carry the listing paragraph's wording

**When an agent sees this.** An agent copies the listing paragraph's sentence into a glossary entry.

**What the agent is told today** (`scripts/system-glossaries-listed-on-the-project-glossary-test.py:175`):

```
FAIL  the project glossary's paragraph listing the system glossaries is located: the paragraph could not be located: 2 paragraphs of docs/nedschorus-wiki/nedschorus-glossary.md carry "A new system glossary is listed here when it is created" — leave that wording in the one paragraph above the entries, or set SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR in scripts/system-glossaries-listed-on-the-project-glossary-test.py to wording only that paragraph carries
```

**What the agent cannot tell from the text.** Which fix applies when, and that the glossary is protected.

**Proposed text** (`{count}` is the number of paragraphs that carry the wording; `{page}`, `{anchor}` and `{suite}` as today):

```
FAIL  the project glossary's paragraph listing the system glossaries is located: the paragraph could not be located: {count} paragraphs of {page} carry "{anchor}", the wording this suite finds the listing paragraph by, so it cannot tell which one lists the system glossaries.
If your change copied that wording into another paragraph by mistake, reword the copy.
If the wording is meant to appear in more than one paragraph, set SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR in {suite} to wording only the listing paragraph carries.
{page} is protected by the instruction-file guard: if the fix only corrects an obvious error as CLAUDE.md lists them, write "Obvious fix under CLAUDE.md's standing approval:" and what you are fixing into .walk-approved before the edit; otherwise ask the user to approve the change before you make it.
```

### 4. The project glossary names a glossary path git does not track

**When an agent sees this.** An agent renames `docs/design-to-main/design-to-main-glossary.md`, and the project glossary still names the old path; or the agent mistypes a path while adding a glossary to the listing paragraph.

**What the agent is told today** (`scripts/system-glossaries-listed-on-the-project-glossary-test.py:280`):

```
FAIL  every glossary path the project glossary names is one git tracks: named but not tracked: ['docs/design-to-main/design-to-main-glossary.md'] — correct each in docs/nedschorus-wiki/nedschorus-glossary.md to a path git tracks, or commit the file it names
```

**What the agent cannot tell from the text.** Why the path must be tracked, what to do for a glossary that was deleted, and that the glossary is protected.

**Proposed text** (`{absent}` and `{page}` as today):

```
FAIL  every glossary path the project glossary names is one git tracks: named but not tracked: {absent}; a path the project glossary names must lead a reader to a glossary in the repository.
If a glossary named there was renamed, or its path is mistyped, correct the path in {page}.
If a glossary named there was deleted, remove it from {page}.
If a glossary named there is new and not yet committed, commit it.
{page} is protected by the instruction-file guard: if the fix only corrects an obvious error as CLAUDE.md lists them, write "Obvious fix under CLAUDE.md's standing approval:" and what you are fixing into .walk-approved before the edit; otherwise ask the user to approve the change before you make it.
```

### 5. A program this suite watches is not where the suite reads

**When an agent sees this.** An agent moves `scripts/recover-crashed-seats.py` to `nc-systems/handoff/tools/recover-crashed-seats.py`.

**What the agent is told today** (`scripts/supervisor-file-names-defined-once-test.py:702`):

```
FAIL  every program that needs these names is among the scripts read: ['recover-crashed-seats.py'] not found under scripts/ or nc-systems/*/ -- a program this suite exists to watch has moved somewhere it does not read, and the cases below now pass on it by finding nothing
```

**What the agent cannot tell from the text.** What to do, and that a deleted or renamed program fails the same way.

**Proposed text** (`{programs}` as today; `{suite}` is the suite's path):

```
FAIL  every program that needs these names is among the scripts read: {programs} not found directly in scripts/ or in an nc-systems/<system>/ directory, the places this suite reads; the cases below cannot check a program they do not read.
If your change moved one of those programs, put it directly in scripts/ or in an nc-systems/<system>/ directory; if it must live deeper, change production_scripts() in {suite} to read that whole directory, not to name the one program.
If your change renamed one of those programs, rename it in PROGRAMS_THAT_NEED_THESE_FILE_NAMES in {suite}.
If your change deleted one of those programs, remove it from PROGRAMS_THAT_NEED_THESE_FILE_NAMES in {suite}.
```

### 6. The suffix constants are not defined in the handoff-supervisor alone

**When an agent sees this.** An agent defines `HANDOFF_FILE_SUFFIX = "-handoff.md"` in `scripts/recover-crashed-seats.py` instead of importing it.

**What the agent is told today** (`scripts/supervisor-file-names-defined-once-test.py:786`):

```
FAIL  the suffix constants are defined in one script: defined in ['handoff-supervisor.py', 'recover-crashed-seats.py'], expected only handoff-supervisor.py
```

**What the agent cannot tell from the text.** Why one script, and what to do.

**Proposed text** (`{defining}` and `{supervisor}` as today; `{defining}` reads "no script" when none defines them):

```
FAIL  the suffix constants are defined in one script: defined in {defining}, expected only {supervisor}; every other script imports them from {supervisor}, so that a renamed suffix changes in one definition.
If a script other than {supervisor} defines one, delete that definition there and import the constant from nc-systems/handoff/{supervisor}.
If {supervisor} no longer defines them, put the definitions back in nc-systems/handoff/{supervisor}.
```

### 7. The /walk-me-through skill names too few file endings

**When an agent sees this.** An agent edits `.claude/skills/walk-me-through/SKILL.md` and writes each walk file's name as `docs/walk/NAME-draft.md` and the like, instead of `docs/walk/<name>-draft.md`.

**What the agent is told today** (`scripts/walk-file-endings-match-the-skill-test.py:64`):

```
FAIL  the skill names the walk files' endings: found only [] in SKILL.md; the pattern this test reads is <name>-<role>.md
```

**What the agent cannot tell from the text.** Why the skill must name the endings, what to do, and that the skill is protected.

**Proposed text** (`{suffixes}` as today; an ending is what follows `<name>` before `.md`, and the walk-document's own ending is empty):

```
FAIL  the skill names the walk files' endings: found only {suffixes} in .claude/skills/walk-me-through/SKILL.md, which decides the endings of an approval-walk's files; this suite reads them from names written as <name>.md and <name>-<ending>.md, and needs at least four.
If your change rewrote those names in the skill, write them again as <name>.md and <name>-<ending>.md.
.claude/skills/walk-me-through/SKILL.md is protected by the instruction-file guard: if the fix only corrects an obvious error as CLAUDE.md lists them, write "Obvious fix under CLAUDE.md's standing approval:" and what you are fixing into .walk-approved before the edit; otherwise ask the user to approve the change before you make it.
```

### 8. cold-read-fast-read.py builds a walk file ending the skill does not name

**When an agent sees this.** An agent changes `WALK_SUGGESTIONS_SUFFIX` in `nc-systems/cold-read/cold-read-fast-read.py` to `-review.md`.

**What the agent is told today** (`scripts/walk-file-endings-match-the-skill-test.py:72`):

```
FAIL  cold-read-fast-read.py WALK_SUGGESTIONS_SUFFIX is an ending the skill names: builds '-review.md', which SKILL.md does not name; the skill decides the endings, so change the skill first or follow it
```

**What the agent cannot tell from the text.** When to change the skill and when to follow it, and that changing the skill is protected.

**Proposed text** (`{constant}` and `{ending}` as today):

```
FAIL  cold-read-fast-read.py {constant} is an ending the skill names: builds {ending}, which .claude/skills/walk-me-through/SKILL.md does not name; the skill decides the endings of an approval-walk's files.
If the new ending was not meant to change the skill, set {constant} in nc-systems/cold-read/cold-read-fast-read.py back to the ending it had.
If the new ending is meant to stay, the skill must name it first: ask the user to approve that change to .claude/skills/walk-me-through/SKILL.md, which the instruction-file guard protects.
```

### 9. walk-files-ship.py ships an ending the skill does not name

**When an agent sees this.** An agent adds a role `-notes` to `WALK_FILE_ROLES` in `scripts/walk-files-ship.py`.

**What the agent is told today** (`scripts/walk-file-endings-match-the-skill-test.py:80`):

```
FAIL  every walk-files-ship.py role suffix is one the skill names: ships ['-notes'], which SKILL.md does not name
```

**What the agent cannot tell from the text.** Why it matters, and what to do.

**Proposed text** (`{unnamed}` as today):

```
FAIL  every walk-files-ship.py role suffix is one the skill names: ships {unnamed}, which .claude/skills/walk-me-through/SKILL.md does not name; the skill decides the endings of an approval-walk's files.
If the new or changed ending was not meant to change the skill, set that role in WALK_FILE_ROLES in scripts/walk-files-ship.py back to what it was, or remove a role your change added.
If the new ending is meant to stay, the skill must name it first: ask the user to approve that change to .claude/skills/walk-me-through/SKILL.md, which the instruction-file guard protects.
```

### 10. cold-read-fast-read.py and walk-files-ship.py disagree on the suggestions file

**When an agent sees this.** `nc-systems/cold-read/cold-read-fast-read.py` writes `-suggestions.md`, and an agent changes the suggestions role in `scripts/walk-files-ship.py` to `-suggestion`.

**What the agent is told today** (`scripts/walk-file-endings-match-the-skill-test.py:86`):

```
FAIL  the fast read's suggestions ending is the shipper's suggestions role: the fast read writes '-suggestions.md' but the shipper's roles are ['-draft', '-suggestion', '', '-minutes', '-dispositions']
```

**What the agent cannot tell from the text.** What goes wrong, and what to do.

**Proposed text** (`{written}` and `{roles}` as today):

```
FAIL  the fast read's suggestions ending is the shipper's suggestions role: the fast read writes {written} but the shipper's roles are {roles}, so scripts/walk-files-ship.py would not ship a walk's suggestions file to the log-store.
Set back whichever of the two your change altered: WALK_SUGGESTIONS_SUFFIX in nc-systems/cold-read/cold-read-fast-read.py, which ends in .md, or the suggestions role in WALK_FILE_ROLES in scripts/walk-files-ship.py, which does not; without its .md, the first must equal the second.
```

### 11. cold-read-record-names.py lacks a name it owns

**When an agent sees this.** An agent renames `fresh_record_directory` in `nc-systems/cold-read/cold-read-record-names.py` to `new_record_directory`.

**What the agent is told today** (`nc-systems/cold-read/tests/cold-read-record-names-test.py:387`):

```
FAIL  the shared module defines every name it owns: cold-read-record-names.py is missing ['fresh_record_directory']
```

**What the agent cannot tell from the text.** Why the module must define the name, and what to do.

**Proposed text** (`{missing}` as today; `{suite}` is the suite's path):

```
FAIL  the shared module defines every name it owns: nc-systems/cold-read/cold-read-record-names.py is missing {missing}, which OWNED_NAMES in {suite} lists as defined only there; the cold-read programs read these names from that module, and a program that reads a missing one fails.
If your change renamed one of those names in the module on purpose, rename it in OWNED_NAMES and in every program under nc-systems/cold-read/ that reads it.
If your change deleted one of those names on purpose and no program under nc-systems/cold-read/ reads it, remove it from OWNED_NAMES.
If your change renamed or deleted one of those names by mistake, put its definition back in the module.
```

### 12. cold-read-record-names.py contains "__main__"

**When an agent sees this.** An agent adds an `if __name__ == "__main__":` block to `nc-systems/cold-read/cold-read-record-names.py` to try a function by hand.

**What the agent is told today** (`nc-systems/cold-read/tests/cold-read-record-names-test.py:407`):

```
FAIL  the shared module has no command-line entry point: cold-read-record-names.py looks runnable; it is imported by five programs and should do nothing on its own
```

**What the agent cannot tell from the text.** What to do, and that the case looks for the text `__main__` anywhere in the file. "five programs" is a count that goes stale.

**Proposed text:**

```
FAIL  the shared module has no command-line entry point: nc-systems/cold-read/cold-read-record-names.py contains the text "__main__"; the module is kept to definitions the cold-read programs import, with no command-line use of its own.
If your change added a command-line entry point to the module, move it into a program file of its own.
If "__main__" appears only in a comment or a docstring, reword that text.
```

### 13. The design names something no code defines

**When an agent sees this.** An agent renames the state `test-design-writing` to `test-design-drafting` in `scripts/design-to-main/design-to-main-state-tables.py`, and the design still names the old one.

**What the agent is told today** (`scripts/design-to-main/tests/design-to-main-design-names-exist-in-state-tables-test.py:213`):

```
AssertionError: Items in the first set but not the second:
'test-design-writing' : backticked in the design, defined by no code and on no list
```

**What the agent cannot tell from the text.** Which design, what to do under each cause, and that the design is protected.

**Proposed message** (the line after the colon, and the lines after it):

```
backticked in docs/design-to-main/design-to-main-state-machine-design.md, defined by no code and on no list of this suite; every name the design writes in backticks must be a name the state machine's code defines.
If the design misspells a name the code defines, correct the design.
If your change renamed or removed the name in scripts/design-to-main/ by mistake, put it back.
If your change renamed or removed the name on purpose, change the design to match.
If the name is spelled as a string in another module of scripts/design-to-main/, add it to MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE in this suite with that module's file name.
If the word is not a name of the state machine, add it with its reason to BACKTICKED_TOKENS_THAT_ARE_NOT_MACHINE_NAMES in this suite.
If you cannot tell whether the design or the code is right, stop and ask the user which is.
docs/design-to-main/design-to-main-state-machine-design.md is protected by the instruction-file guard: if the fix only corrects an obvious error as CLAUDE.md lists them, write "Obvious fix under CLAUDE.md's standing approval:" and what you are fixing into .walk-approved before the edit; otherwise ask the user to approve the change before you make it.
```

**Question for the user, B: a name whose right spelling the agent cannot tell.** The suite holds a list, `KNOWN_MISMATCHES_AWAITING_A_RULING`, for names in the design that no code defines and that await the user's ruling; it is empty, and its comment says entries were placed there by the user's ruling, not to make the suite pass. The proposed last condition has the agent stop and ask the user. The alternative is to let the agent add the name to that list and tell the user, which makes the suite pass while the ruling is pending. Recommendation: stop and ask, as proposed, so that only the user puts a name on the list that awaits the user.

### 14. A name listed as a string in another module is no longer there

**When an agent sees this.** An agent removes the string `"evidence-directory"` from the module that `MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE` names for it.

**What the agent is told today** (`scripts/design-to-main/tests/design-to-main-design-names-exist-in-state-tables-test.py:230`; the assertion has no message, and the subtest heading names the name):

```
AssertionError: False is not true
```

**What the agent cannot tell from the text.** Which file, why the entry matters, and what to do.

**Proposed message** (`{name}` and `{file_name}` from the subtest):

```
{name} is listed in MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE as a string in scripts/design-to-main/{file_name}, and that file no longer spells it; the entry is how this suite accepts a design name the state tables module does not define.
If your change removed the string by mistake, put it back.
If your change renamed the string, give the entry the new name, and change the design's name to match.
If your change moved the string to another module of scripts/design-to-main/, change the entry's file name.
If the state machine no longer has that name, remove the entry, and remove the name from the design.
docs/design-to-main/design-to-main-state-machine-design.md is protected by the instruction-file guard: if the fix only corrects an obvious error as CLAUDE.md lists them, write "Obvious fix under CLAUDE.md's standing approval:" and what you are fixing into .walk-approved before the edit; otherwise ask the user to approve the change before you make it.
```

### 15. A name on one of this suite's exception lists is now defined by the state tables

**When an agent sees this.** An agent adds a state named `contract-review` to `scripts/design-to-main/design-to-main-state-tables.py`, and `contract-review` is on `BACKTICKED_TOKENS_THAT_ARE_NOT_MACHINE_NAMES`.

**What the agent is told today** (`scripts/design-to-main/tests/design-to-main-design-names-exist-in-state-tables-test.py:234` and `:235`; the assertions have no message):

```
AssertionError: Items in the first set but not the second:
'contract-review'
```

**What the agent cannot tell from the text.** Which list, why it matters, and what to do.

**Proposed messages**, for `:234` and `:235`:

```
on BACKTICKED_TOKENS_THAT_ARE_NOT_MACHINE_NAMES in this suite, and now a name the state tables module defines; a name of the state machine must be checked, not exempted.
If your change added that name to the state tables on purpose, remove it from BACKTICKED_TOKENS_THAT_ARE_NOT_MACHINE_NAMES.
If your change added it to the state tables by mistake, remove it from the state tables.
```

```
on MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE in this suite, and now a name the state tables module defines, so the entry is no longer needed.
If your change added that name to the state tables on purpose, remove it from MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE.
If your change added it to the state tables by mistake, remove it from the state tables.
```

### 16. The design's tables and the code's tables disagree

**When an agent sees this.** An agent edits row 24 of section 3.2 of the design, changing its To cell from `test-design-writing` to `implementation-writing`, and leaves `TRANSITION_TABLE` in `scripts/design-to-main/design-to-main-state-tables.py` as it was.

**What the agent is told today** (`scripts/design-to-main/tests/design-to-main-design-rows-pair-with-state-tables-test.py:340`, `:344` and `:349`; the assertions have no message):

```
AssertionError: Lists differ: ["row 24: to-state 'test-design-writing', the To cell's first state 'implementation-writing'"] != []
```

**What the agent cannot tell from the text.** That the two copies are kept in step by hand, which copy decides what, what to do, and that the design is protected.

**Proposed messages.** For `:340`, section 3.2 against `TRANSITION_TABLE`:

```
section 3.2 of docs/design-to-main/design-to-main-state-machine-design.md and TRANSITION_TABLE in scripts/design-to-main/design-to-main-state-tables.py disagree on the rows listed above; both copies are edited by hand, section 3.2 deciding what a transition is and the code what it does.
If your change edited one copy by mistake, undo that edit.
If your change edited a copy on purpose, make the same change in the other copy, so that both say the same.
docs/design-to-main/design-to-main-state-machine-design.md is protected by the instruction-file guard: if the fix only corrects an obvious error as CLAUDE.md lists them, write "Obvious fix under CLAUDE.md's standing approval:" and what you are fixing into .walk-approved before the edit; otherwise ask the user to approve the change before you make it.
```

For `:344`, section 3.1's states and sub-states against `STATE_TABLE`:

```
section 3.1 of docs/design-to-main/design-to-main-state-machine-design.md and STATE_TABLE in scripts/design-to-main/design-to-main-state-tables.py disagree on the states listed above; both copies of the states and their sub-states are edited by hand and must list the same.
```

followed by the same three lines as for `:340`. For `:349`, section 3.1's package column against `STATE_TABLE`'s `package_beyond_standard`:

```
section 3.1's package column in docs/design-to-main/design-to-main-state-machine-design.md and STATE_TABLE's package_beyond_standard in scripts/design-to-main/design-to-main-state-tables.py disagree on the states listed above; the code's text is what a launched agent receives, so the design's column must say the same.
```

followed by the same three lines.

### 17. A phrase the suite's row reading relies on is gone from section 3.2

**When an agent sees this.** An agent rewords the From cells of section 3.2, and no From cell starts with "any reviewing state but " any more.

**What the agent is told today** (`scripts/design-to-main/tests/design-to-main-design-rows-pair-with-state-tables-test.py:361`, `:363` and `:365`). The message at `:361` and `:363` is the phrase alone; the message at `:365` is the destination's key in `TO_CELL_PHRASE_OF_DESTINATION_MARKER`, not the phrase. The audit did not list this message.

```
AssertionError: False is not true : any reviewing state but
```

**What the agent cannot tell from the text.** That the suite reads the cells by this phrase, why its absence matters, and what to do.

**Proposed messages.** `{phrase}` is the phrase, for `:365` the dictionary's value; `{cell}` and `{where}` are, by assertion:

- `:361`: From, "a From cell starting with", and the constant that holds the phrase, `FROM_CELL_PHRASE_ANY_REVIEWING_STATE_BUT` or `FROM_CELL_PHRASE_A_REVIEWING_SUB_STATE_BY_AGENT`;
- `:363`: Trigger, "a Trigger cell containing", and the key of `TRIGGER_CELL_PHRASES_NAMING_VERDICTS`;
- `:365`: To, "a To cell containing", and the value of `TO_CELL_PHRASE_OF_DESTINATION_MARKER`.

```
no row of section 3.2 of docs/design-to-main/design-to-main-state-machine-design.md has {cell} "{phrase}"; this suite reads the rows by that phrase, and a phrase no row uses leaves its reading untested by the design, where a later row could fall into it by accident.
If your change reworded those cells by mistake, put the phrase back.
If the new wording is meant to stay, change {where} in this suite to the new wording.
If no row should use the phrase any more, remove it from {where}, with the code in this suite that reads it.
docs/design-to-main/design-to-main-state-machine-design.md is protected by the instruction-file guard: if the fix only corrects an obvious error as CLAUDE.md lists them, write "Obvious fix under CLAUDE.md's standing approval:" and what you are fixing into .walk-approved before the edit; otherwise ask the user to approve the change before you make it.
```

### 18. The force-push guard is not registered exactly once

**When an agent sees this.** An agent edits `.claude/settings.json` and drops the entry that runs `scripts/force-push-with-open-pull-request-guard-hook.py`, duplicates it, or moves it out of the PreToolUse block whose matcher is `Bash`.

**What the agent is told today** (`scripts/force-push-with-open-pull-request-guard-hook-test.py:857`):

```
FAIL  the guard is wired exactly once as a PreToolUse Bash hook: []
```

**What the agent cannot tell from the text.** Where the guard is registered, why once, what to do, and that the file is protected.

**Proposed text** (`{entries}` as today):

```
FAIL  the guard is wired exactly once as a PreToolUse Bash hook: found {entries}; .claude/settings.json must register scripts/force-push-with-open-pull-request-guard-hook.py exactly once, in the PreToolUse block whose matcher is Bash, so that the guard runs once before each Bash command.
If your change removed, duplicated or moved that entry, put back exactly one entry in that block.
.claude/settings.json is protected by the instruction-file guard: if the fix only corrects an obvious error as CLAUDE.md lists them, write "Obvious fix under CLAUDE.md's standing approval:" and what you are fixing into .walk-approved before the edit; otherwise ask the user to approve the change before you make it.
```

### 19. The force-push guard's registered timeout is not above its budget

**When an agent sees this.** An agent raises `PROBE_BUDGET_SECONDS` in `scripts/force-push-with-open-pull-request-guard-hook.py` from 20 to 40, above the 30 seconds `.claude/settings.json` gives the hook.

**What the agent is told today** (`scripts/force-push-with-open-pull-request-guard-hook-test.py:860`):

```
FAIL  the registered timeout exceeds the guard's probe budget: timeout 30 vs budget 40.0
```

**What the agent cannot tell from the text.** Why the timeout must exceed the budget, and what to do under each cause.

**Proposed text** (`{timeout}` and `{budget}` as today; `{timeout}` is `None` when no entry or no timeout is registered):

```
FAIL  the registered timeout exceeds the guard's probe budget: timeout {timeout} vs budget {budget}; the guard must finish its probes and answer before the harness stops it, so the timeout .claude/settings.json registers for it must be a number above PROBE_BUDGET_SECONDS in scripts/force-push-with-open-pull-request-guard-hook.py.
If the case above also failed, fix that first; this case reads the timeout from the entry that case looks for.
If your change raised PROBE_BUDGET_SECONDS, lower it below the timeout, or ask the user to approve a higher timeout in .claude/settings.json.
If your change lowered, removed or rewrote the timeout in .claude/settings.json, put back a number above the budget.
.claude/settings.json is protected by the instruction-file guard: if the fix only corrects an obvious error as CLAUDE.md lists them, write "Obvious fix under CLAUDE.md's standing approval:" and what you are fixing into .walk-approved before the edit; otherwise ask the user to approve the change before you make it.
```

## Messages left as they are

The audit counted these repository-rule messages complete, and the rereading agrees, apart from the two in `scripts/pr-reviewer-instructions-copies-test.py`, which Questions C and D take up:

- `scripts/system-glossaries-listed-on-the-project-glossary-test.py`: git could not list the glossaries (`:154`), the checkout holds no project glossary (`:252`), no system glossary is tracked (`:262`), nothing was checked (`:270`), and a system glossary is not listed (`:275`).
- `scripts/supervisor-file-names-defined-once-test.py`: the suffix constants are missing from the handoff-supervisor (`:233`), a script composes a file name itself (`:708`), a composing helper is missing (`:717`), and the names the suite hunts are a stale copy (`:750`).
- `scripts/nedschorus-glossary-alphabetical-order-test.py`: the glossary is out of order (`:136`).
- `nc-systems/cold-read/tests/cold-read-record-names-test.py`: a cold-read program keeps its own copy of a name (`:369`), and a program binds a name without loading the module (`:401`).
- `scripts/design-to-main/tests/design-to-main-design-names-exist-in-state-tables-test.py`: a known mismatch is no longer one (`:217`), and a known mismatch is now a string in a module (`:222`).

The rows suite also raises `DesignTableMalformed` when section 3.1 or 3.2 of the design cannot be read as a table at all; neither the audit nor this rereading covers those messages, and a later reading does.

**Question for the user, C: the review-scope copies.** `scripts/pr-reviewer-instructions-copies-test.py:169` fails when CLAUDE.md's review-scope bullet differs from `docs/agents/pr-reviewer-instructions.md`, and ends "The file is the rule's home; make CLAUDE.md's bullet its section again." Both files are protected by the instruction-file guard, and the message does not say so. Recommendation: add the guarded-file line, with `{file}` reading "CLAUDE.md".

**Question for the user, D: the copy that does not say where the rule lives.** `scripts/pr-reviewer-instructions-copies-test.py:174` fails when CLAUDE.md does not name `docs/agents/pr-reviewer-instructions.md` and the suite beside its copy, and says only "the copy must say where the rule lives and what keeps the two identical". It states the rule but gives no instruction. Recommendation: bring it into this part, with this text:

```
FAIL  CLAUDE.md names the file and this test beside its copy: CLAUDE.md's review-scope bullet must name docs/agents/pr-reviewer-instructions.md, where the rule lives, and scripts/pr-reviewer-instructions-copies-test.py, which keeps the two copies identical.
If your change removed either name from that bullet, put it back.
CLAUDE.md is protected by the instruction-file guard: if the fix only corrects an obvious error as CLAUDE.md lists them, write "Obvious fix under CLAUDE.md's standing approval:" and what you are fixing into .walk-approved before the edit; otherwise ask the user to approve the change before you make it.
```

## Code the new texts need

- Each `check()` detail and each assertion message above changes as shown. Six `unittest` assertions that have no message today gain one: `scripts/design-to-main/tests/design-to-main-design-names-exist-in-state-tables-test.py:230`, `:234` and `:235`, and `scripts/design-to-main/tests/design-to-main-design-rows-pair-with-state-tables-test.py:340`, `:344` and `:349`. The three phrase assertions at `:361`, `:363` and `:365` change their message to section 17's.
- The rows suite sets `maxDiff = None` on its class, so that section 16's message follows every disagreeing row: today `unittest` shortens a long list and can replace the comparison with "Diff is N characters long".
- Section 1's second form keeps the error the suite raises, for both of its causes, and adds its two lines after it.
- The guarded-file line and Question A's line, if approved, are each one constant in a module the ten suites import, so that their wording is written once.

## Tests

The pull request adds, for every changed message, a case that makes the message print and checks that its lines are the approved lines. A message built inline at the place where a case checks the real repository moves into a function first, so that both the real case and the new case call it; this applies to `scripts/file-name-collision-warning-hook-test.py:480`, `scripts/supervisor-file-names-defined-once-test.py:702` and `:786`, `scripts/walk-file-endings-match-the-skill-test.py`, `nc-systems/cold-read/tests/cold-read-record-names-test.py:387` and `:407`, the two design-to-main suites, and the force-push suite's two settings cases. The new case calls that function with a planted failing input, not the real repository, so that the real case still checks the repository. The system-glossaries suite already builds its details in `project_glossary_promise_cases`, which its fixture cases call; its fixture cases at `:414` and `:431` assert the text "could not be located", which the proposed texts keep.
