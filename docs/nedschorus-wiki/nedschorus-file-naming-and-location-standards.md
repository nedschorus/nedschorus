# File naming and location standards

The naming and location standards for this project's files. Where a tool this project did not write, such as Claude Code, Git or GitHub, fixes a file's name or location, we follow the tool. These standards cover every other file in the repository. Where a skill or a program names the files it writes differently, this page still sets the pattern, and the migration of GHI [Rationalize the repository layout: group components by owning system under nc-systems/](https://github.com/nedschorus/nedschorus/issues/224) brings each into line. Until it does, a file that a skill's or a program's code reads stays where that code reads it. `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md` says how to choose the words of every name, file names included, and CLAUDE.md points there; this page gives the patterns and locations for each kind of file.

## Terms this page uses

`docs/nedschorus-wiki/nedschorus-glossary.md` defines the project-terms. `.claude/skills/skills-glossary.md`, `docs/design-to-main/design-to-main-glossary.md` and `nc-systems/main-gatekeeper/main-gatekeeper-glossary.md` define the system-terms of the skills, of design-to-main and of the main-gatekeeper. We avoid spaces in directory and file names, using a hyphen, `-`, instead.

- **stem**: a filename without its extension.
- **suffix**: the closing part of a filename stem that marks the file's kind, written with its leading hyphen and without the extension, such as `-draft`, `-test-design` or `-nbd`; a stem need not have one.

## Desired locations or file names for various components

The MD-skills agent-seat moves each file on main that is not where, or not named as, this page says, under GHI [Rationalize the repository layout: group components by owning system under nc-systems/](https://github.com/nedschorus/nedschorus/issues/224), one system per pull request, repointing in the same commit every citation in the repository. A new file goes where this page says. A system gets its own directory under `nc-systems/` in the pull request that adds its first production code; test code alone does not earn one.

A file in a queue directory is named as it will be in its final location, apart from the issue number a GHI-MD gains when its GHI is filed. A GHI-MD moves to its final location through the ghi-write-tool once its cold read is done; any other file moves to it by `git mv` in a pull request once the user approves it.

- **Skill prompt, the agent-instructions a skill's program gives an agent it launches**
  - **Location:** `nc-systems/skills/<skill name>/`, where `<skill name>` is the skill's name without its slash, such as `cold-read`
  - **Naming:** `<skill name>-<prompt name>-prompt.md`, where <prompt name> says what the prompt asks for, such as `cold-read-defect-hunt-prompt.md`.
- **Hook**
  - **Location:** `.claude/hooks/` for a hook that guards which files or GitHub issues an agent may change; every other hook in its system's directory, `nc-systems/<system-name>/`, or in `nc-systems/general-tools/` when it belongs to no system
  - **Naming:** `<what it does>.py`, such as `instruction-file-guard.py` or `ghi-issue-write-hand-typed-gh-command-refusal.py`
- **Tests, test-designs, design-contracts**
  - **Location:** a test goes in a `tests/` subdirectory when the code sits in a directory of its own, such as `nc-systems/main-gatekeeper/tests/` or `scripts/design-to-main/tests/`; beside the script it tests when the script sits loose in `scripts/` or `.claude/hooks/`, for example `scripts/dangling-path-citation-check-test.py`; a program in `nc-systems/general-tools/` has its test in `nc-systems/general-tools/tests/`.
  - **Test file names:** `<name of the program tested>-test.<extension>`, for example `scripts/dangling-path-citation-check-test.py`; when one program has several test files, see "Name a test file after what it tests" in `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md`
  - **Test-design name:** its design's name with `-design.md` replaced by `-test-design.md`
  - **Test-design location:** beside its design
  - **Design-contract Name:** its design's name with `-design.md` replaced by `-contract.md`, beside its design
- **agent-instructions: instructions, initial-agent-instructions and prompts a program appends**
  - **Location:** `docs/agents/` when more than one system uses them, otherwise their system's directory; pending approval, `docs/agents/queue/`
  - **Naming:** `<subject>-instructions.md`; for initial-agent-instructions, `<subject>-first-prompt.md`; for a prompt a program appends, `<subject>-prompt.md`.
- **Wiki page**
  - **Location:** pending approval, `docs/nedschorus-wiki/queue/`; approved, `docs/nedschorus-wiki/`
  - **Naming:** `nedschorus-<subject>.md`, which every page on main follows
- **GHI-MD, an MD file that explains a GitHub issue**
  - **Location:** `docs/issues/`; a GHI-MD that is a design moves as the next entry says
  - **Naming:** `<issue number>-<multi-part-name>.md`
- **Design document, including a GHI-MD that is a design**
  - **Location:** Before its GHI is filed, `docs/issues/queue/`. Once its GHI is filed, `docs/issues/`, where it is refined in place until its code lands; from then it is revised only to fix a flaw found in it, and only after human review, and each merge appends a `**Pinned to what landed:** commit [<sha>]` line naming its commit. When its GHI closes, the design moves, with its test-design and design-contract where it has them, to the `docs/` subdirectory of the directory its code is in, `nc-systems/<system-name>/docs/` or `nc-systems/general-tools/docs/`, and the GHI's link is updated.
  - **Naming:** `<multi-part-name>-design.md` before its GHI is filed; `<issue number>-<multi-part-name>-design.md` once it is filed; `<multi-part-name>-design.md` again once it moves to its code's `docs/`. The `-design` suffix stays in all three, though not every GHI has a design.
- **Other system or subsystem MDs**
  - **Location:** `nc-systems/<system-name>/docs/`, beside the system's `tests/`. A subsystem, which has a subdirectory of its system's directory, keeps its MDs in that subdirectory's `docs/`. A skill keeps only its `SKILL.md` in `.claude/skills/<skill name>/`; the rest of it lives in `nc-systems/skills/<skill name>/`, its MDs other than its prompts in that directory's `docs/`. A document that belongs to no one system stays in the top-level `docs/`, unless it is a design or data for a program in `nc-systems/general-tools/`, which keeps it in that directory's `docs/`.
  - **Naming:** `<system-name>-<subject>.md`; for a skill, `<skill name>-<subject>.md`
- **Program, in Python or shell**
  - **Location:** `nc-systems/<system-name>/` for a system's own, its subsystem's subdirectory for a subsystem's; `nc-systems/general-tools/` for one that belongs to no system
  - **Naming:** `<multi-part-name>.py` or `<multi-part-name>.sh`; a launcher people type as a command, such as `launch-claude-mac`, has no extension
- **Prose a program reads as its data**: a fixed file whose content a program parses, such as the style guide's word table; a prompt, agent-instructions and a GHI-MD keep their own entries above
  - **Location:** where the agents who should read it look: `docs/nedschorus-wiki/` when every agent should read it; otherwise the `docs/` directory of the system whose program reads it, or `nc-systems/general-tools/docs/` when that program belongs to no one system
  - **Naming:** by that location's rule
  - **Pairing:** each program that reads the file names the file in one constant, and the file names, before its data, each program that reads it
- **A `-draft` file of a kind that has no queue**
  - **Location:** `docs/drafts/`
  - **Naming:** `<subject>-draft.md`; a version frozen for reviewers is `<subject>-candidate.md`. A `-draft` or `-candidate` file moves to the log-store's `seats/<agent-seat name>/` when the work it served merges or is dropped. A later candidate of the same subject adds the next number, such as `<subject>-candidate-2.md`.

## Files the user reviews

The user reviews each change to these files that `docs/nedschorus-wiki/nedschorus-which-changes-need-the-users-approval.md` lists and does not except, from a file's first version in its approved location to each later edit; any other change passes the instruction-file guard with a `#pre_approved_change` marker file:

- every MD file in `docs/agents/` and `docs/nedschorus-wiki/`;
- every MD file under `nc-systems/skills/`;
- every design, a file whose name ends `-design.md`, except a test-design;
- every reusable prompt, a file whose name ends `-prompt.md` or `-instructions.md`;
- `CLAUDE.md`, any `CLAUDE.local.md`, and everything under `.claude/` except its working space: `worktrees/`, `jobs/` and `handoffs/`.

The list does not reach the places for documents pending approval, where agents write them freely: any `queue/` directory, such as `docs/agents/queue/`, `docs/issues/queue/` or `docs/nedschorus-wiki/queue/`, `nc-queue/`, and `docs/drafts/`. Test-designs and design-contracts are not on the list, wherever they sit, `nc-systems/skills/` included: design-to-main brings them to the user. Nor are the frozen copies inside `cold-read-records/`, `md-review-records/` and `sanity-check-records/`. `.claude/hooks/instruction-file-guard.py` enforces the list for an agent's file-editing tools; a shell command, `git mv` or a program is not checked.

## Filename suffixes

* `-log`: a record of what a program or agent-session did, in time order.
* `-report`: a finished account written for a reader, such as a reviewer's findings.
* `-capture`: a verbatim copy of something seen, such as terminal output or a web page.
* `-draft`: a document still being written, not yet put to review.
* `-candidate`: a version frozen for reviewers to read.
* `-analysis`: a study of data, with its method and conclusions.

A file with one of the six suffixes above is a log, kept in the log-store and never in git, with two exceptions: a `-draft` or `-candidate` file while it is pending approval, in `docs/drafts/` or a queue directory; and a GHI-MD, which is its GHI's substance even when it ends `-report`, such as `docs/issues/142-draft-md-prompt-research-report.md`. The log-store's `README.md`, `nedlern@ned-box:/home/nedlern/nedschorus-logs/README.md`, names the program or skill that owns each of its directories, and that owner names the files.

One more suffix is not a log suffix: `-nbd`, the end of the name of a file whose whole content is nice-but-dirty, just before any extension, such as `scripts/log-store-session-dialogs-refresh-nbd.py`; no file without the suffix holds nice-but-dirty code. The project glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`, defines -nbd and nice-but-dirty.

