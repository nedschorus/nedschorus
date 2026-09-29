---
issue: "[An issue has one GHI-MD and many supporting documents, and the GHI write tool cannot tell them apart](https://github.com/nedschorus/nedschorus/issues/783)"
---

# An issue has one GHI-MD and many supporting documents, and the GHI write tool cannot tell them apart

## The ruling

The user ruled on 2026-09-29, in item 1.2 of the walk SKILL-ghi-write-2026-09-29-3 (minutes at nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/SKILL-ghi-write-2026-09-29-3-minutes.md):

> "Each GHI should only have one GHI-MD - the GHI that replaces the normal GHI description, often with a design document. But GHis may need other supporting material, say data or notes or something. We don't want to pile all documents associated with a GHI into one file. Those other files may be MDs, but there are not THE ghi.md, they are supporting MDs."

> "Issue body should link all supporting docs, whereever they might be. Multiple issues could link to the same supporting docs. One issue could link to many supporting docs. I don't think supporting MD needs to be a glossary item."

So an issue has exactly one GHI-MD, its description. Its other files are supporting documents, which need not be MDs: the ruling names data and notes. The issue's body links the GHI-MD and every supporting document, wherever each one lives, and one document can support several issues.

## What the tool does today

`scripts/ghi-issue-write.py`, the ghi-write-tool, knows an issue's files only by their names:

- `ghi_md_paths_for_issue` (scripts/ghi-issue-write.py:935) returns every file named `<number>-*` directly in `docs/issues/` or directly in a system's directory under `nc-systems/`, and treats each one as a filed GHI-MD.
- `links_body` (scripts/ghi-issue-write.py:477) makes the issue's body "one link per filed GHI-MD, in filename order, and nothing else", from that list.
- The list follows the user's ruling of 2026-09-19 in the walk ghi-info-design-write-path-becomes-link-only (minutes at nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-info-design-write-path-becomes-link-only-minutes.md), quoted at scripts/ghi-issue-write.py:949-950: step 5 "writes a computed list: one link per file matching `docs/issues/<number>-*`, globbed at every write, never curated".
- `sync_title_on_heading_change` (scripts/ghi-issue-write.py:1671) retitles an issue from its GHI-MD's first heading. When the list holds more than one file it leaves the title alone (lines 1699-1703), because "nothing says which one names it".

## Where the tool and the ruling part

1. **The tool cannot tell the GHI-MD from its supporting documents.** On 2026-09-29, 16 of the 70 open issues had more than one file named for them: 3, 4, 9, 10, 18, 26, 30, 32, 39, 45, 46, 116, 142, 238, 386 and 603. GHI [Build ghi-info — the GHI knowledge agent](https://github.com/nedschorus/nedschorus/issues/46) has two, `46-ghi-info-agent-design.md` and `46-build-ghi-info-the-ghi-knowledge-agent-former-issue-body.md`, and issue 3 has five. Nothing records which file is an issue's GHI-MD, so the tool never retitles these 16 issues.
2. **A supporting document the tool does not find is never linked.** A file stored anywhere else, or named for no issue, stays out of the body. A design whose name does not begin with the issue's number is one such file, wherever it sits.
3. **A document shared by several issues can be linked from one of them at most.** A file name carries one number.

"Wherever they might be" and "Multiple issues could link to the same supporting docs" cannot both hold for a list computed from one number in a file name. For supporting documents, the ruling of 2026-09-29 replaces the ruling of 2026-09-19. Whether the GHI-MD itself is still found by its name is a question for the design.

## Other places that use "GHI-MD" for every file named for an issue

- `.claude/hooks/ghi-issue-write-redirect.py:192`, in the refusal of a hand-typed title edit: "If the issue has more than one GHI-MD, or its GHI-MD's first heading already reads the title you want, stop and tell the user."
- `links_body`'s docstring and the name `ghi_md_paths_for_issue`.
- The glossary's link-only-GHI entry. Item 7 of the same walk approved changing "the links to its GHI-MDs" to "the links to its GHI-MD and its supporting documents", in a pull request of its own.
- The /ghi-write skill, `.claude/skills/ghi-write/SKILL.md`. The same walk approved the sentence "Every GHI is a link-only-GHI: its text is its one GHI-MD, and its body is the links to that file and to its supporting documents, wherever they live, and nothing else (user-ruled 2026-09-15 and 2026-09-29). Today the ghi-write-tool links only files named `<number>-…` beside the GHI-MD." Its last sentence comes out when the tool change this issue asks for lands.

## A question already with the user

Should edit-GHI retitle an issue to match its GHI-MD's first heading when the heading did not change? It was raised in the review of PR [The GHI redirect hook refuses a hand-typed gh issue edit --title](https://github.com/nedschorus/nedschorus/pull/771). Once each of the 16 issues has a known GHI-MD, its title may not match that file's heading.

## What is needed

This issue states the problem. How the tool finds an issue's GHI-MD and its supporting documents is the design's to decide, walked with the user, then built. It needs:

- a way to tell an issue's GHI-MD from its supporting documents;
- a way for the body to link supporting documents wherever they live, and to link a document shared by several issues from each of them;
- for each of the 16 issues with several files today, which file is its GHI-MD; its other files become its supporting documents;
- what the bodies of the issues that link a shared supporting document do when that document moves;
- the tool, the hook's refusal line and the skill's interim sentence brought into line with the ruling.

The next action is to draft that design and walk it with the user.

## Search receipt

ghi-info, asked on 2026-09-29 with `--include-closed` whether any issue covers how the ghi-write-tool chooses the files an issue's body links, how it tells the GHI-MD from other files named for the issue, or how it links documents stored elsewhere or shared, named four issues and said none covers this directly:
- GHI [Build ghi-write (step-1 founding skill): trigger on creating or revising a GHI; enforce edit-don't-comment-or-duplicate](https://github.com/nedschorus/nedschorus/issues/13), closed;
- GHI [Walk the live ghi-write skill: close order, pair sequence, and the user's comment-rule wording](https://github.com/nedschorus/nedschorus/issues/340), closed;
- GHI [ghi-write follow-ups from PR #332: the full re-review it did not get, and how to retrofit an oversize issue into a GHI-MD](https://github.com/nedschorus/nedschorus/issues/345), closed as not planned;
- GHI [Cite files by name, not by path](https://github.com/nedschorus/nedschorus/issues/610), open, on how any document names another file; related, not the same matter.
