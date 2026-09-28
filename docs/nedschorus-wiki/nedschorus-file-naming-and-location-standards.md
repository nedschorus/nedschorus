# File naming and location standards

The naming and location convention for this project's files. Where internal or external systems dictate the name or location of files we follow those dictates. Our standards only cover this project's systems. Our CLAUDE.md has our general naming rules, which include file names. Our skills and scripts may specify their own file names and locations. This document complements, not replaces, those other methods and instructions. 

## Terms this page uses

`docs/nedschorus-wiki/nedschorus-glossary.md` defines the project-terms. `.claude/skills/skills-glossary.md` and `docs/design-to-main/design-to-main-glossary.md` define the system-terms of the skills and of design-to-main. We avoid spaces in directory and file names, using a hyphen, `-`, instead.

- **stem**: a filename without its extension.
- **suffix**, on this page: the last hyphen-separated part of the filename
  stem, written with its hyphen, such as `-draft`, not the extension `.md`.

## Desired locations or file names for various components

Files already on main stay where they are until GHI [Rationalize the repository layout: group components by owning system under nc-systems/, and a hook dispatcher](https://github.com/nedschorus/nedschorus/issues/224) moves them; a new file goes where this page says, creating the directory if needed, except a skill prompt, which stays in `.claude/skills/<skill name>/prompts/` until `.claude/hooks/instruction-file-guard.py` covers `nc-systems/skills/`.

A file in a queue directory is named as it will be at its home, apart from the issue number a GHI-MD gains when its GHI is filed, so promoting it is a `git mv`.

- **Skill prompt, the text a skill's own reviewer or cell runs**
  - **Location:** `nc-systems/skills/<skill name>/`
  - **Naming:** `<pass>-prompt.md`, named for the pass it drives
- **Hook**
  - **Location:** `.claude/hooks/`
  - **Naming:** `<what it guards>.py`
- **Tests, test-designs, component-contracts**
  - **Location:** a test goes in a `tests/` subdirectory when the code sits in a directory of its own, such as `nc-systems/main-gatekeeper/tests/` or `scripts/design-to-main/tests/`; beside the script it tests when the script sits loose in `scripts/` or `.claude/hooks/`, for example `scripts/dangling-path-citation-check-test.py`.
  - **Test Names:** `<multi-part-name>-test.<extension>`, for example `scripts/dangling-path-citation-check-test.py`
  - **Test-Design Name:** `<multi-part-name>-test-design.md`
  - **Test-Design Location:** beside its design
  - **Component-contract Name:** its design's name with `-design.md` replaced by `-contract.md`, beside its design
- **agent-instructions kept in `docs/agents/`: instructions, initial-agent-instructions, adversarial prompt**
  - **Location:** `docs/agents/`; awaiting approval, `docs/agents/queue/`
  - **Naming:** `<subject>-instructions.md`, `<subject>-first-prompt.md`, or `<subject>-adversarial-prompt.md`
- **Wiki page**
  - **Location:** awaiting approval, `docs/nedschorus-wiki/queue/`; approved, `docs/nedschorus-wiki/`
  - **Naming:** `nedschorus-<subject>.md`, which every page on main follows
- **GHI-MD, an MD file that explains a GitHub issue**
  - **Location:** `docs/issues/`; a GHI-MD that is a design moves as the next entry says
  - **Naming:** `<issue number>-<multi-part-name>.md`
- **Design document, including a GHI-MD that is a design**
  - **Location:** Before its GHI is filed, `docs/issues/queue/`. Once its GHI is filed, `docs/issues/`, where it is refined in place until its code lands; from then it is not refined again, and each landing appends a pinned line carrying the landing commit. When that code has its own directory on main, the design moves there and the GHI's link is updated; a design whose code is a single script stays in `docs/issues/`.
  - **Naming:** `<multi-part-name>-design.md` before its GHI is filed; `<issue number>-<multi-part-name>-design.md` once it is filed; `<multi-part-name>-design.md` again once it moves beside its code. The `-design` suffix stays in all three, though not every GHI has a design.
- **Other system or subsystem MDs**
  - **Location:** `nc-systems/<system-name>/`, with a subsystem in a subdirectory of its system's directory. A skill keeps only its `SKILL.md` in `.claude/skills/<skill name>/`; the rest of it lives in `nc-systems/skills/<skill name>/`.
  - **Naming:** `<subject>.md`
- **Program, in Python or shell**
  - **Location:** `nc-systems/<system-name>/` for a system's own; `nc-systems/general-tools/` for one that belongs to no system
  - **Naming:** `<multi-part-name>.py` or `<multi-part-name>.sh`; a launcher people type as a command, such as `launch-claude-mac`, has no extension
- **Draft of a kind that has no queue**
  - **Location:** `docs/drafts/`
  - **Naming:** `<subject>-draft.md`; a version frozen for reviewers is `<subject>-candidate.md`. Candidates move to the log-store's `seats/<seat name>/` once the work they served has landed on main. 

## Filename suffixes

* `-log`: a record of what a program or session did, in time order.
* `-report`: a finished account written for a reader, such as a reviewer's findings.
* `-capture`: a verbatim copy of something seen, such as terminal output or a web page.
* `-draft`: a document still being written, not yet put to review.
* `-candidate`: a version frozen for reviewers to read.
* `-analysis`: a study of data, with its method and conclusions.

Most files with these suffixes are kept in the log-store rather than in git; a draft in a queue directory, and a report that belongs to a GHI, are committed. The log-store's `README.md` names the program or skill that owns each of its directories, and that owner names the files.

