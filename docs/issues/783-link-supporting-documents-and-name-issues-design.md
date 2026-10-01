---
issue: "[An issue has one GHI-MD and many supporting documents, and the GHI write tool cannot tell them apart](https://github.com/nedschorus/nedschorus/issues/783)"
status: design
---

# How the ghi-write-tool names an issue and links its GHI-MD and supporting files

This design says how the ghi-write-tool, `scripts/ghi-issue-write.py`, tells an issue's one GHI-MD from the issue's supporting files, how the issue and its GHI-MD are named, and how the issue's body links both. It replaces this issue's earlier GHI-MD, `docs/issues/783-an-issue-has-one-ghi-md-and-many.md`, which stated the problem only; the pull request that lands this design removes that file (§ Getting there, step 0).

§ The user-rulings lists what the user has decided. The mechanics that carry those decisions out are this design's own; the user reviewed the choices among them in two approval-walks, and § Open questions lists what is still his to decide.

The problem, in one paragraph. The tool treats every file named `<number>-*` directly in `docs/issues/`, or directly in a system's directory under `nc-systems/`, as the issue's GHI-MD. So the tool cannot tell an issue's GHI-MD from the issue's other files, never links a supporting file stored anywhere else, and can link a file shared by several issues from one of those issues at most. The tool also cuts the words of an issue's file name from the first eight words of the file's first heading, which the user called a bad name.

## The user-rulings

Each approval-walk's walk-minutes are in the log-store at `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/<walk name>-minutes.md`.

- **One GHI-MD per issue; other material in supporting files.** Walk SKILL-ghi-write-2026-09-29-3, item 1.2 (user-ruled 2026-09-29): "Each GHI should only have one GHI-MD - the GHI that replaces the normal GHI description, often with a design document. But GHis may need other supporting material, say data or notes or something. We don't want to pile all documents associated with a GHI into one file. Those other files may be MDs, but there are not THE ghi.md, they are supporting MDs." And: "Issue body should link all supporting docs, whereever they might be. Multiple issues could link to the same supporting docs. One issue could link to many supporting docs." In these quotations "the GHI that replaces the normal GHI description" and "THE ghi.md" mean the GHI-MD.
- **The GHI-MD is the master document.** Walk 783-an-issue-has-one-ghi-md-and-many-2026-09-29, item 1 (user-ruled 2026-09-30): "The ghi-MD is the design, the master, the overview. It is not a note or supporting file." Here "the design" means the issue's master document, whatever the file is called; a GHI-MD is a design document in the sense of the [file-naming page](https://github.com/nedschorus/nedschorus/blob/main/docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md) only when it is one.
- **The naming rule.** Walk 783-an-issue-has-one-ghi-md-and-many-2026-09-29, item 2 (user-ruled 2026-09-30), and the ruling recorded in the same walk-minutes that settled its conflict with walk open-questions-concerns-and-recommendations-2026-09-30, item 4:
  - a GHI-MD's name is the part of its file name between the leading `<number>-` and `.md`; the file is `<number>-<name>.md`;
  - the name is 3 to 9 lowercase words joined by hyphens, verb first when the issue is work to do;
  - the name names the work in full words, without abbreviations, and carries no status, ruling, date, provenance or path;
  - the issue's title is the name, not the first heading; the first heading is free text;
  - the tool checks a name when an issue is filed (and, by item 5 of the approval-walk on this design, when edit-GHI changes it); the date and file-path check that PR [GHI titles name the work](https://github.com/nedschorus/nedschorus/pull/829) put on the first heading moves to the name;
  - a GHI-MD that is a design document keeps the `-design` suffix, which counts as one of the name's words;
  - a name is not changed unless the user asks (walk SKILL-ghi-write-2026-09-29-4, 2026-09-30: "once we title a GHI and MD, I would not change it, unless the user specifically asks for a change").
- **One name change for the open issues.** Walk 783-an-issue-has-one-ghi-md-and-many-2026-09-29, item 3 (user-ruled 2026-09-30): only names cut off mid-thought are replaced, each new name replacing both the file name and the title, proposed in one table; every other open issue keeps its name and takes it as its title, in the same pass.
- **What the body links, found without a hand-kept list.** The same approval-walk, item 4 (user-ruled 2026-09-30, "seems like we should automate these, assuming automation is easy"): the body links the GHI-MD first, then every file on main that names the issue, anywhere in the repository; files only on an unmerged branch and files in the log-store are not linked; the tool writes the line that names the issue, and the bodies are rebuilt after each merge. This replaces the user-ruling of 2026-09-19 in walk ghi-info-design-write-path-becomes-link-only, which linked "one link per file matching `docs/issues/<number>-*`, globbed at every write, never curated", and keeps its "never curated".
- **The rulings of the approval-walk on this design.** Walk 783-ghi-md-names-and-supporting-document-links-design-2026-09-30-2 (user-ruled 2026-10-01, "y" to each):
  - each issue has a marker, `ghi-<number>-<16 random hexadecimal characters>`, kept in its GHI-MD's front matter; the tool finds an issue's supporting files by searching the contents and the names of the files on main for the marker; any text file carries it anywhere in its content, any file can carry it in its name, and an image's embedded metadata may carry it but is not relied on (item 2, after the user's proposal: "What if each GHI has a GUID, and we insert that guid into any file or place that we need to 'find' to include in the GHI file list?", and "I think it would help if the GHI# prepended the guid");
  - the rebuild after a merge covers closed issues too (item 3);
  - one pull request migrates the files and carries the tool change (item 4);
  - edit-GHI checks a changed name as filing does (item 5);
  - an issue's title changes only after the merge that changes its GHI-MD's name (item 6);
  - the two new operations are `mark-supporting-document` and `relink-and-retitle-issues` (item 7);
  - the word is "name", not "slug" (item 8);
  - the name table flags a kept name that breaks the naming rule, and the user decides each (item 9).
- **The Markdown label.** Walk ghi-md-reconciliation-disagreements-2026-09-30 (user-ruled 2026-10-01): "can we say supports-issues: not just supports. That is too ambiguous." The same walk, item 1: the GHI-MD of GHI [main-gatekeeper — the single check-in gate (design: nc-systems/main-gatekeeper/main-gatekeeper-design.md)](https://github.com/nedschorus/nedschorus/issues/3) is its specification, `nc-systems/main-gatekeeper/main-gatekeeper-design.md`; its move into a `docs/` directory waits for the migration of GHI [Rationalize the repository layout](https://github.com/nedschorus/nedschorus/issues/224), where the user ruled main-gatekeeper is brought into line "rather than by a third move".

## What the tool does today

Measured on origin/main, 2026-10-01.

- **Which files belong to an issue.** `ghi_md_paths_for_issue` lists the files on main whose file name begins `<number>-` and which sit directly in `docs/issues/` or directly in `nc-systems/<system>/`, and, since commits c0582dc3 and fcefed36 (the MD-skills seat, walk ghi-224-migration-order-and-open-questions-2026-09-30, item 3), a landed design: a file under `nc-systems/` in a `docs/` directory, named `*-design.md` with no number, whose `issue:` front-matter line names the issue (`landed_design_relative_path`, `issue_number_in_frontmatter`). `writable_relative_path` accepts the same three places. Any other file is never found, and a file serves one issue at most.
- **The body.** `links_body` writes one link per file found, sorted by full path, each labelled with the file's base name, and nothing else.
- **The file name.** create-GHI names the landed file `docs/issues/<number>-<slug>.md`, where `slug`, today's code's word for what this design calls the name, is the first heading's first eight words (`SLUG_WORD_LIMIT = 8`).
- **The title.** create-GHI files the issue under the file's first heading. edit-GHI retitles the issue from the first heading only when the edit changed that heading and the issue has one filed file (`title_follows_heading_in_this_edit`). A first heading about to become a title is refused when it carries a date or a file path.
- **The `issue:` line.** create-GHI and edit-GHI write an `issue:` line into the front matter of the file they land, citing the issue by its title as a link. The fifteen GHI-MDs reconciled under walk 783-an-issue-has-one-ghi-md-and-many-2026-09-29, item 1, landed on 2026-10-01; their sixteen `-former-issue-body.md` files are still on main, waiting for one pull request that deletes them. Some closed issues' files carry no `issue:` line, such as `docs/issues/8-adversarial-package-review.md`.
- **Designs moved out.** Four designs sit directly in a system's directory with no number and no `issue:` line: `nc-systems/cold-read/cold-read-design.md`, `nc-systems/cold-read/cold-read-grid-cell-failure-handling-design.md`, `nc-systems/handoff/handoff-design.md` and `nc-systems/main-gatekeeper/main-gatekeeper-design.md`. The tool finds none of them for any issue. No design sits yet in a `docs/` directory.
- **A move that renames.** edit-GHI finds the path a moved file came from by the file's base name. A file moved and renamed is not matched: the tool lands it as a new file, leaves main's old copy, and tells the author to land the removal.

## The design

### One GHI-MD per issue, found by its `issue:` line

The tool takes as an issue's GHI-MD the file on main whose front-matter `issue:` line links that issue, in a place a GHI-MD may sit (§ Where a GHI-MD may sit). This generalises what the tool already does for a landed design, `issue_number_in_frontmatter`, to every place. create-GHI and edit-GHI write the line, as they do today. The tool reads the issue number from the link's URL, and only from a URL of this repository, `https://github.com/nedschorus/nedschorus/issues/<number>`; a line linking anywhere else counts as no `issue:` line, and the tool reports it.

- **None found.** The tool reports that the issue has no GHI-MD on main and leaves the title alone. The body is handled in § What the body links.
- **More than one found.** The tool reports every path, links each one first in path order, and leaves the title alone. Nothing is guessed.
- **An `issue:` line outside the places a GHI-MD may sit**, such as a copy under `docs/drafts/`. The file is not taken as the GHI-MD; the tool reports the path.

When a file given to create-GHI or edit-GHI carries a number at the start of its file name and an `issue:` line linking a different issue, the operation stops with a hard-block, exit 64, naming both numbers and telling the author to correct the wrong one. A scan of main that meets such a file uses the `issue:` line, reports the mismatch, and carries on.

edit-GHI takes the issue number from the given file's `issue:` line only. A file with no `issue:` line is refused, exit 64, with instructions: a supporting file lands in an ordinary pull request, and the rebuild after the merge updates the bodies; a new master document for an issue replaces the GHI-MD through an edit of the GHI-MD. So edit-GHI never turns a supporting file into a second GHI-MD.

create-GHI refuses, exit 64, a file that already carries an `issue:` line: the file is filed, and edit-GHI is the operation for it. Today's refusal text, which tells an author to file material as a new issue by copying it under a name with no number, also tells the author to remove the `issue:` line and the `issue-marker:` line from the copy.

### The issue marker

Each issue has one marker, `ghi-<number>-<16 random hexadecimal characters>`, such as `ghi-783-7f3a9c2e41b8d605`. The number shows a reader which issue the marker names; the random part makes the marker unique, so a search for it matches nothing but the files that carry it on purpose.

- **Where it is kept.** The GHI-MD's front matter carries it on an `issue-marker:` line beside the `issue:` line. create-GHI makes the marker when it files the issue and writes both lines. A GHI-MD keeps its marker when it moves or is renamed.
- **Which marker is the issue's.** The one on its GHI-MD's `issue-marker:` line; when main holds several GHI-MDs for the issue, each one's marker. When the issue has no GHI-MD on main, the marker is read from the last GHI-MD main held for it, found in main's history, so a deleted GHI-MD's supporting files stay linked; an issue that never had a GHI-MD has no marker. A string of the marker's form whose random part differs from the issue's marker, or whose issue has no marker, is not the issue's marker: the tool reports each file carrying it and does not link the file.
- **Data, not a citation.** The marker is read by the tool. CLAUDE.md's rule against citing an issue by a bare number or GUID does not reach it; a writer who means to cite an issue links it by title, and never writes its marker in prose.

### Supporting files and how they carry the marker

A supporting file is any file on main, other than the issue's GHI-MD, that carries the issue's marker in its content or in its name. A file can carry several issues' markers, and an issue can have many supporting files.

- **A Markdown file** carries the markers on a front-matter line, in a front-matter block `mark-supporting-document` creates when the file has none, `supports-issues: ghi-783-7f3a9c2e41b8d605, ghi-790-0c1d2e3f40516273`. A GHI-MD can carry a `supports-issues:` line naming other issues, and is then a supporting file of those issues; a GHI-MD whose `supports-issues:` line names its own issue is linked once, as the GHI-MD.
- **Another text file** carries the marker anywhere in its content. `mark-supporting-document` writes it as a comment line, `supports-issues: ghi-783-…`, at the top of the file, after a `#!` line when there is one, in the file type's comment form: `#` for Python, shell, YAML and TOML, `//` for JavaScript and TypeScript, `<!-- -->` for HTML and XML.
- **Any file, a binary one included,** can carry the marker in its name, such as `ghi-783-7f3a9c2e41b8d605-answer-times.png`. The author puts it there when choosing the name.
- **An image's embedded metadata** may carry the marker for a reader. The search does not rely on it: `git grep` skips binary files by default, and many image tools compress or strip metadata when they save, so a file carrying the marker in its metadata alone may never be found. A file carrying it in both its name and its metadata is found by its name.
- **A file that can carry the marker in neither place**, such as a JSON file whose format another program fixes and whose name the author does not choose, is not linked; the GHI-MD names it in its text.

A copy of a file carries the marker and is linked too, as a copy of a file's `issue:` line would be. A file in `docs/issues/queue/` or `docs/issues/archived/` is linked when it carries the marker, and not otherwise.

The tool writes the marker. `mark-supporting-document <path> <number>…` looks up each issue's marker on its GHI-MD's `issue-marker:` line on main, and writes it into the file at `<path>` in the author's checkout, in the form for the file's type; `mark-supporting-document --remove <path> <number>…` takes the named issues' markers out, and takes the line out when none is left; at least one number is required either way. The operation:
- refuses a number whose issue has no GHI-MD with an `issue-marker:` line, and a number that names a pull request or nothing;
- reports a marker already present, or already absent, and changes nothing for it;
- refuses, exit 64, a binary file, telling the author to carry the marker in the file's name; a text file whose type has no comment form the operation knows, such as JSON, with the same instruction or the GHI-MD's text as the alternative; a Markdown file whose front matter opens with `---` and never closes; a `supports-issues:` line in any form but markers separated by commas; and a file another program or agent reads as instructions: a `SKILL.md`, `CLAUDE.md`, `CLAUDE.local.md`, an `-instructions.md` or `-prompt.md` file, and any file `.claude/hooks/instruction-file-guard.py` guards. The GHI-MD cites such a file in its text instead.

The operation renames nothing and lands nothing: the author commits the changed file with the rest of the work, because a new supporting file usually lands in the author's own pull request. Which issues a file supports is the author's call.

### Names and titles

- **The author gives the name.** The author writes the GHI-MD as `<name>.md`, and create-GHI lands it as `docs/issues/<number>-<name>.md`. The tool no longer cuts a name from the first heading, and `SLUG_WORD_LIMIT` goes.
- **The checks.** create-GHI refuses, with a hard-block, exit 64, a name that:
  - is not 3 to 9 words;
  - is not lowercase letters and digits joined by single hyphens;
  - has a first word made only of digits, such as `2026-summary-of-reviews`, which the tool would read as an issue number; `3d-graphics-export` passes;
  - carries a date, by the check PR [GHI titles name the work](https://github.com/nedschorus/nedschorus/pull/829) built for the first heading, which moves to the name; a file path cannot pass the character check;
  - is already the name of a GHI-MD on main, or the title of another issue, open or closed.
  The refusal says which check failed and how to fix the name. edit-GHI runs the same checks when the GHI-MD's name differs from its name on main, and none when the name is unchanged. Two filings in flight at once that choose the same name are not caught.
- **What a program cannot check.** That the name names the work in full words, without abbreviations, status, ruling or provenance, is the author's to meet; the /ghi-write skill says so. A name changes only when the user asks for it; the skill says so too, because nothing in a file records whether the user asked.
- **The title is the name, set on main.** create-GHI files the issue under the name. After that, only `relink-and-retitle-issues` sets the title, from the name of the GHI-MD on main, when the two differ. edit-GHI does not set the title, so an edit whose pull request is closed unmerged leaves the title as it was. The `issue:` line cites the issue under its title; a GHI-MD renamed in a merged pull request keeps the old title as the text of its `issue:` line until the next edit-GHI run rewrites the line; the tool reads only the line's URL, so nothing breaks meanwhile.
- **The first heading is free text.** It no longer sets the title, so `heading_changed_in_this_edit`, `title_follows_heading_in_this_edit`, `issue_title_after_this_edit` and `sync_title_on_heading_change` go, and `refuse_heading_with_date_or_file_path` becomes the name's date check. `validate` and `validate_edit` still require a first heading, because a GHI-MD opens with one; their refusal says so instead of calling the heading the title. `refuse_if_filing_is_in_flight` compares the source's name, not its first heading, with the titles of issues still being filed.

### What the body links

The body of a link-only-GHI is, in order:

1. the link to the GHI-MD, found as above;
2. one link per supporting file, every file on main other than the GHI-MD that carries the issue's marker in its content or its name, sorted by path.

Each link's text is the file's path in the repository, so two files with the same base name in different directories are told apart. Nothing else is in the body, and nothing is kept by hand: the list is computed from main at every write. Not linked: a file only on an unmerged branch, whose link would not open, and a file in the log-store on ned-box, which GitHub cannot link; the GHI-MD cites either kind in its text.

The tool finds both kinds of file from origin/main with two reads: `git grep` for front-matter `issue:` lines and for the marker in file contents, and `git ls-tree -r --name-only` for the marker in file names. A Markdown file's `supports-issues:` line counts only in its front-matter block, so a document that quotes such a line in its text is not taken for a supporting file of that issue unless the quoted marker is the issue's real one, which a writer has no reason to quote.

The tool writes the body only over a body it wrote, its list of links or create-GHI's placeholder, as `relink_body_from_main` does today, and leaves a prose body as it stands. When no GHI-MD is on main:
- a placeholder body stays, because the filing has not finished and its GHI-MD is still on a pull request;
- a list of links is rebuilt from the supporting files alone, so a dead link to a deleted GHI-MD drops out, and the tool reports that the issue has no GHI-MD;
- when there is no supporting file either, the body is left as it stands and the tool reports it, so no body is written empty.

### Rebuilding after every merge

A new operation, `relink-and-retitle-issues`, rebuilds the body and sets the title of each issue it is given, open or closed, as the user ruled; § Open questions, question 1, asks about one side effect for closed issues. It has three forms:
- `relink-and-retitle-issues <number>…` for named issues;
- `relink-and-retitle-issues --after-merge <pull request number>` for every issue one merged pull request touched. It asks GitHub for the pull request's merge commit, fetches origin/main, reads the merge's changes against its first parent, renames included, and collects every issue linked by an `issue:` line or named by a marker in any changed file's content or name, in the version before the merge and in the version after. The marker's number names the issue, so no lookup is needed to collect it. A supporting file that was added, changed, moved, renamed or deleted brings each issue it named, or now names, into the run;
- `relink-and-retitle-issues --all-open` for every open issue.

Each run is idempotent: an issue whose body and title already match is left untouched. The title is set whether the body is links or prose. A number that names no issue of this repository is reported and skipped, and the run carries on with the rest.

merge-lane-2 runs `relink-and-retitle-issues --after-merge <pull request number>` directly after the `gh pr merge` command that `scripts/merge-gate.sh` prints. `scripts/merge-gate.sh` only checks and prints that command, so the rebuild is a new step after it, not inside it. When the rebuild cannot run, for example because the network is down, merge-lane-2 records the pull request in its ledger and reruns the same command before its next merge. A merge made any other way, such as by the user on GitHub, gets no rebuild; merge-lane-2 runs `--all-open` when it learns of one. When main-gatekeeper becomes the only way a change reaches main, main-gatekeeper runs the same command after each merge; this design hands that requirement to GHI [main-gatekeeper — the single check-in gate (design: nc-systems/main-gatekeeper/main-gatekeeper-design.md)](https://github.com/nedschorus/nedschorus/issues/3).

Before the build starts, the agent that builds this design asks merge-lane-2 to confirm that its GitHub account can edit issue titles and bodies; if the account cannot, the build stops and asks the user.

create-GHI, rerun by an author on a landed GHI-MD whose issue body the rebuild has already turned into links, reports that the filing is finished and exits 0, instead of refusing the file as already filed. The /ghi-write skill's rerun after a merge becomes a fallback for when the rebuild did not run.

### Moves, renames and deletions

- **A GHI-MD moves or is renamed.** Its `issue:` and `issue-marker:` lines move with it, so the tool finds the file at its new path. edit-GHI, given a file whose `issue:` line links an issue whose GHI-MD main holds at a different path, looks at that other path in the author's checkout:
  - the file is gone from the checkout: the author moved or renamed the GHI-MD, and edit-GHI removes main's old copy in the same commit;
  - the file is still in the checkout: two files carry the line, and edit-GHI refuses, exit 64, telling the author to remove the `issue:` and `issue-marker:` lines from the copy, or to delete the original if the GHI-MD is moving.
  When main holds more than one file with that issue's `issue:` line, edit-GHI removes nothing and reports every path.
- **A supporting file moves, is renamed or is deleted.** The rebuild after the merge rebuilds the body of every issue whose marker the file carried. A marker in the file's content moves with it; a file that carried the marker in its name keeps it only if the new name keeps it, which the author sees to. A deleted file drops out of the body.
- **A GHI-MD is deleted.** The rebuild follows § What the body links: the body keeps the supporting files' links, and the tool reports that the issue has no GHI-MD. The title stays.

### Where a GHI-MD may sit

A GHI-MD sits directly in `docs/issues/` from filing until its code lands, and then where the file-naming page puts a design whose code has landed: the `docs/` directory of the directory its code is in, at any depth under `nc-systems/`. The tool already accepts a landed design there when it is named `*-design.md` with no number (`landed_design_relative_path`); the build keeps that predicate and also accepts a GHI-MD there that is not a design, since a GHI-MD that moves with its code is not always one. `writable_relative_path` still accepts `nc-systems/<system>/` directly, where the four designs moved out so far sit, so main-gatekeeper's specification, `nc-systems/main-gatekeeper/main-gatekeeper-design.md`, is found there by its `issue:` line until the repository-layout migration moves it. A move keeps both front-matter lines, and so the file stays the issue's GHI-MD.

A landed design is revised only to fix a flaw found in it, and only after human review (the file-naming page, as changed by PR [A landed design is revised only to fix a flaw, after human review](https://github.com/nedschorus/nedschorus/pull/860)). The tool does not enforce that; the /ghi-write skill says it for edit-GHI on a landed design.

## Getting there

The new tool leaves an issue's title alone and reports while the issue has more than one file with an `issue:` line, so the work below leaves each issue with exactly one.

0. **This design lands.** Through today's edit-GHI, which lands it as a new file of this issue and leaves the earlier GHI-MD, `docs/issues/783-an-issue-has-one-ghi-md-and-many.md`, in place; its removal is landed by hand in the same change, as today's edit-GHI tells the author to.
1. **The old descriptions go.** The fifteen reconciled GHI-MDs have landed. One pull request deletes the sixteen `-former-issue-body.md` files and repoints every citation of them on main, such as line 17 of `docs/issues/39-memory-drain-at-reincarnation.md`; edit-GHI is then rerun on each of the fifteen GHI-MDs, which rebuilds each body from main. main-gatekeeper's former issue body goes in the same pull request once its specification, merged with that body's decisions, has had the user's review and landed.
2. **The name table.** A subagent lists every open issue in one table: its current name, a proposed new name where the current one is cut off mid-thought, and a flag on any kept name that breaks the naming rule, such as `neds-notes`, two words, or a name carrying a status. The user approves or changes each row.
3. **The build.** One pull request, atomic under CLAUDE.md, carrying:
   - the tool changes above, with their tests;
   - the migration of the files it reads, written by a script that uses the tool's own front-matter code:
     - every GHI-MD on main, of an open or a closed issue, gets an `issue-marker:` line with a new marker; a numbered file that is the only file of its issue and has no `issue:` line gets that line too;
     - every other numbered file directly in `docs/issues/` gets a `supports-issues:` line with its issue's marker, so no link drops out of a body when the tool stops selecting files by the number at the start of their file names; main-gatekeeper's four supporting files likewise: `docs/issues/3-main-gatekeeper-build-slice-plan.md`, `docs/issues/3-credential-work-measured-state-and-rulings.md`, `docs/issues/3-dismiss-stale-reviews-experiment-design.md` and `docs/issues/3-slice-6-review-evidence-not-built.md`;
     - the renames in the approved table, with every citation of an old path on main repointed, as the file-naming page requires of a move;
     - every open issue's `issue:` line rewritten to cite the issue under its name;
   - the changes in § What the build changes outside the tool.
   After it merges, merge-lane-2 runs `relink-and-retitle-issues --all-open`, which sets every open issue's title to its name and rebuilds every open body. Closed issues are rebuilt when a later merge touches them.

Prose elsewhere that cites an issue by its old title keeps that text; its links still open.

## What the build changes outside the tool

The exact new wording of each change is written in the build and put to the user in an approval-walk; this section says what changes.

- **`.claude/hooks/ghi-issue-write-redirect.py`, and its tests in `.claude/hooks/ghi-issue-write-redirect-test.py`.** The refusals that point at "the issue's GHI-MD, docs/issues/<number>-*.md" point at the file whose `issue:` line links the issue. The title refusal tells the agent: to change an issue's title, ask the user for a change of the GHI-MD's name. The create refusal stops calling the first heading the issue's title. The docstring's account of titles following headings goes.
- **`.claude/skills/ghi-write/SKILL.md`.**
  - The `File:` bullet under How to do it gains the naming line approved in item 2 of walk 783-an-issue-has-one-ghi-md-and-many-2026-09-29, with the naming rule's content: "Name the GHI-MD for the outcome in 3 to 9 lowercase words joined by hyphens, verb first when it is work to do, such as `build-meta-walk-skill`, in full words, without abbreviations, and with no status, ruling, date, provenance or path; write it as `<name>.md`; create-GHI lands it as `<number>-<name>.md`, and the issue's title is the name."
  - Step 4's sentence "The first heading becomes the issue's title…" becomes a sentence saying that the name becomes the title and the first heading is free text.
  - New sentences: change a GHI-MD's name only when the user asks for it; revise a landed design only to fix a flaw, after human review; cite an issue by its title and link, never by writing its marker.
  - The `Edit:` bullet's "A changed first heading retitles the issue, unless other files are named with the issue's number." comes out, and so does any sentence that says the tool links only files named `<number>-…`.
  - A line on `mark-supporting-document` goes in, and the rerun after a merge becomes the fallback to `relink-and-retitle-issues`.
- **The file-naming page.** The GHI-MD entry gains the naming rule, the title matching the name, and the marker; the design entry says a moved design keeps its `issue:` and `issue-marker:` lines.
- **`docs/nedschorus-wiki/nedschorus-glossary.md`.** The ghi-write-tool entry lists the two new operations beside create-GHI and edit-GHI.
- **`nc-systems/cold-read/cold-read-fast-read.py`**, the program that runs a cold-read-fast-read, is unchanged: a GHI-MD that is a design document keeps the `-design` suffix, which the program already reads.

Two changes do not go in the build's pull request:
- **`docs/issues/46-ghi-info-agent-design.md` § The GHI write path**, which the tool's docstring names as its authority, is a GHI-MD, so its pointer to this design, for the body, the title and where a GHI-MD may sit, lands through edit-GHI after the build.
- **merge-lane-2's instructions** are in its machine-local, uncommitted `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/CLAUDE.local.md`. The `relink-and-retitle-issues --after-merge` step goes in there, with the user's approval, when the build merges.

## Open questions

1. **Closed issues' titles.** The user ruled that the rebuild covers closed issues. The name table covers open issues only, so a later merge that touches a closed issue would retitle it to its file's name, which for most closed issues is the first eight words cut from an old title, the bad name the user ruled against. The choices: (a) the rebuild sets a closed issue's links only and leaves its title; (b) the name table also covers closed issues; (c) closed issues take their cut names. Recommendation: (a), because a closed issue's title is its record, and renaming every closed issue is a large table for little gain.

## Search receipt

ghi-info, asked on 2026-09-29 with `--include-closed` whether any issue covers how the ghi-write-tool chooses the files an issue's body links, how it tells the GHI-MD from other files named for the issue, or how it links documents stored elsewhere or shared, named four issues and said none covers this directly:
- GHI [Build ghi-write (step-1 founding skill): trigger on creating or revising a GHI; enforce edit-don't-comment-or-duplicate](https://github.com/nedschorus/nedschorus/issues/13), closed;
- GHI [Walk the live ghi-write skill: close order, pair sequence, and the user's comment-rule wording](https://github.com/nedschorus/nedschorus/issues/340), closed;
- GHI [ghi-write follow-ups from PR #332: the full re-review it did not get, and how to retrofit an oversize issue into a GHI-MD](https://github.com/nedschorus/nedschorus/issues/345), closed as not planned;
- GHI [Cite files by name, not by path](https://github.com/nedschorus/nedschorus/issues/610), open, on how any document names another file; related, not the same matter.
