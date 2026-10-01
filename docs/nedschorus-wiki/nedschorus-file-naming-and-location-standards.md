# File naming and location standards

The naming and location convention for this project's files. Where internal or external systems dictate the name or location of files we follow those dictates. Our standards only cover this project's systems. Our CLAUDE.md has our general naming rules, which include file names. Our skills and scripts may specify their own file names and locations. This document complements, not replaces, those other methods and instructions. 

## Terms this page uses

`docs/nedschorus-wiki/nedschorus-glossary.md` defines the project-terms. `.claude/skills/skills-glossary.md` and `docs/design-to-main/design-to-main-glossary.md` define the system-terms of the skills and of design-to-main. We avoid spaces in directory and file names, using a hyphen, `-`, instead.

- **stem**: a filename without its extension.
- **suffix**, on this page: the last hyphen-separated part of the filename
  stem, written with its hyphen, such as `-draft`, not the extension `.md`.

## Desired locations or file names for various components

A file on main that is not where this page says is moved there by GHI [Rationalize the repository layout: group components by owning system under nc-systems/, and a hook dispatcher](https://github.com/nedschorus/nedschorus/issues/224), one system at a time, each move repointing every citation in the same commit. A new file goes where this page says, creating the directory if needed, unless its system, skill or script names another place.

A file in a queue directory is named as it will be at its home, apart from the issue number a GHI-MD gains when its GHI is filed, so promoting it is a `git mv`.

- **Skill prompt, the text a skill's own reviewer or cell runs**
  - **Location:** `nc-systems/skills/<skill name>/` once `.claude/hooks/instruction-file-guard.py` guards that directory; until then `.claude/skills/<skill name>/prompts/`
  - **Naming:** `<pass>-prompt.md`, named for the pass it drives
- **Hook**
  - **Location:** `.claude/hooks/`
  - **Naming:** `<what it does>.py`, such as `instruction-file-guard.py` or `ghi-issue-write-redirect.py`
- **Tests, test-designs, design-contracts**
  - **Location:** a test goes in a `tests/` subdirectory when the code sits in a directory of its own, such as `nc-systems/main-gatekeeper/tests/` or `scripts/design-to-main/tests/`; beside the script it tests when the script sits loose in `scripts/` or `.claude/hooks/`, for example `scripts/dangling-path-citation-check-test.py`.
  - **Test Names:** `<multi-part-name>-test.<extension>`, for example `scripts/dangling-path-citation-check-test.py`
  - **Test-Design Name:** `<multi-part-name>-test-design.md`
  - **Test-Design Location:** beside its design
  - **Design-contract Name:** its design's name with `-design.md` replaced by `-contract.md`, beside its design
- **agent-instructions kept in `docs/agents/`: instructions and initial-agent-instructions**
  - **Location:** `docs/agents/`; awaiting approval, `docs/agents/queue/`
  - **Naming:** `<subject>-instructions.md` or `<subject>-first-prompt.md`
- **Wiki page**
  - **Location:** awaiting approval, `docs/nedschorus-wiki/queue/`; approved, `docs/nedschorus-wiki/`
  - **Naming:** `nedschorus-<subject>.md`, which every page on main follows
- **GHI-MD, an MD file that explains a GitHub issue**
  - **Location:** `docs/issues/`; a GHI-MD that is a design moves as the next entry says
  - **Naming:** `<issue number>-<multi-part-name>.md`
- **Design document, including a GHI-MD that is a design**
  - **Location:** Before its GHI is filed, `docs/issues/queue/`. Once its GHI is filed, `docs/issues/`, where it is refined in place until its code lands; from then it is revised only to fix a flaw found in it, and only after human review, and each landing appends a pinned line carrying the landing commit. When its code lands, the design moves to the `docs/` subdirectory of the directory its code is in, `nc-systems/<system-name>/docs/` or `nc-systems/general-tools/docs/`, and the GHI's link is updated.
  - **Naming:** `<multi-part-name>-design.md` before its GHI is filed; `<issue number>-<multi-part-name>-design.md` once it is filed; `<multi-part-name>-design.md` again once it moves to its code's `docs/`. The `-design` suffix stays in all three, though not every GHI has a design.
- **Other system or subsystem MDs**
  - **Location:** `nc-systems/<system-name>/docs/`, beside the system's `tests/`. A subsystem, which has a subdirectory of its system's directory, keeps its MDs in that subdirectory's `docs/`. A skill keeps only its `SKILL.md` in `.claude/skills/<skill name>/`; the rest of it lives in `nc-systems/skills/<skill name>/`, its MDs other than its prompts in that directory's `docs/`. Project MDs that belong to no one system stay in the top-level `docs/`, as the entries above say.
  - **Naming:** `<system-name>-<subject>.md`; for a skill, `<skill name>-<subject>.md`
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

A file with one of the six suffixes above is a log, kept in the log-store and never in git, with two exceptions: a draft or candidate while it waits for review, in `docs/drafts/` or a queue directory; and a GHI-MD, which is its GHI's substance even when it ends `-report`, such as `docs/issues/142-draft-md-prompt-research-report.md`. The log-store's `README.md`, `nedlern@ned-box:/home/nedlern/nedschorus-logs/README.md`, names the program or skill that owns each of its directories, and that owner names the files.

