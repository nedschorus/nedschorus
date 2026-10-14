# How to write an identifier

This file is the project's citation rule in full. Every identifier you
show him carries its ID-type and a name he can read, and where it has a link, it
is a link. A number may appear, but never alone. Look names and links up: `gh pr
view <n> --json title,url`, `gh issue view <n> --json title,url`, `git log -1
--format=%s <sha>`, and `gh browse <sha> --no-browser` for a pushed commit. When
a lookup fails, write the ID-type, what the thing is in your own words, and the
bare identifier, and say you could not find its title. The hashes, numbers and
dates inside these templates are examples; put the real ones in their place.

**An identifier with a link: ID-type, name, link.**
- A pull request: `PR [<title>](<URL>)`. A pull request not yet created: "the
  pull request that will <what it will do>".
- A GitHub issue: `GHI [<title>](<URL>)`.
- A commit: `commit [<subject line>](<URL>)`. A commit not yet pushed:
  `commit 40b5ee7 ("<subject line>"), not yet pushed, on branch <name>`.
- A file on the Mac: `the file [<what it is>](file://<absolute path>)`. A
  file on ned-box, the log-store included: what it is, then
  `nedlern@ned-box:<absolute path>`, the form scp reads from either machine. Do
  not cite a scratchpad file; ship the scratchpad file to the log-store and
  cite the log-store copy. A GHI-MD is a file like any other.
- A skill: `/<name>` and what it does, linked to its `SKILL.md` by absolute path.
- A wiki page, or an approval-walk's document: its title, linked.

**An identifier with a name but no link of its own: ID-type and name.**
- A task: `task #244, "<subject>"`.
- An approval-walk item: `item 4 of 10 of the "<walk name>" walk — "<item
  heading>"`. Always name the approval-walk; two approval-walks can be live at once. Link the
  walk-document when you can.
- A finding: `finding 3 of "<which report>" — "<one-line summary>"`, the report
  linked when you can.
- A table row: `row 19 of "<which table>" — "<the row's own text>"`.
- A user-ruling: what was ruled, then `ruled 2026-09-15 at "<which walk or
  file>"`, linked when that approval-walk or file has a link.
- An agent-seat or an agent-session, with its ID-type: "the merge-lane-backlog agent-seat",
  "agent-session merge-lane-backlog-24 of the merge-lane-backlog agent-seat", never the bare
  name.

**An identifier with no title of its own: make its ID-type plain.**
- A review or a comment: never its bare id. Write `review on PR [<title>](<URL>)`,
  `comment on PR [<title>](<URL>)` or `comment on GHI [<title>](<URL>)`, the URL
  being the comment's own: it ends `#pullrequestreview-<id>`,
  `#discussion_r<id>` or `#issuecomment-<id>`.
- A branch: `branch <name>`; write `origin/<name>` only for a branch pushed there.
- A model: its vendor model id, such as `gpt-6-astra`. A nickname you cannot
  match to a vendor model id is "the model nicknamed <x>".
- Anything else, such as a code symbol or an environment variable: its kind in
  words, "the environment variable `GH_TOKEN`".

**Do not show at all**, unless he asks about one: the ids Claude Code gives
background shells and subagents, except when the id names the thing you are
deleting; subagent output paths; scratchpad paths; timestamps written as raw
epoch milliseconds; the branch names Claude Code generates for its own
temporary worktrees; files a program is still writing, such as `.partial`
files.
