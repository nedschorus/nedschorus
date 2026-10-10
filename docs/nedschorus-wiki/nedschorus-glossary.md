# nedschorus glossary

A list of the phrases and terms of this project approved by the user, in alphabetical order, skills first. Generic SDLC vocabulary is deliberately absent.

Every project-term should be listed here; a term this page does not list is not a project-term, at least not yet. A term used by one system or subsystem alone is a system-term, not a project-term: it is defined in that system's own glossary, so when this page does not list a term, look in the glossary of the system whose files you are in. Each term has one entry, in the glossary of the widest scope that uses it: a term more than one system uses is defined here and in no system glossary. If a term should be added to this list, ask the user to review it. A word needs a project-term only where this project does something unexpected with it or gives it a meaning that would be hard to guess; otherwise it stays ordinary prose. A project-term takes one of four forms: an abbreviation such as GHI, a skill's slash name such as /handoff, a hyphenated phrase such as agent-seat, or a filename suffix such as -draft. The hyphens mark a phrase as a project-term or a system-term with a meaning this project gives it, so a reader knows to look it up, here or in that system's glossary, and an ordinary word keeps its ordinary meaning.

A term used by one system alone is defined in that system's glossary, not here. The system glossaries are `.claude/skills/skills-glossary.md`, the terms the skills alone use, `docs/design-to-main/design-to-main-glossary.md`, the terms of the design-to-main workflow, and `nc-systems/main-gatekeeper/main-gatekeeper-glossary.md`, the terms of the main-gatekeeper. A new system glossary is listed here when it is created; `scripts/system-glossaries-listed-on-the-project-glossary-test.py` fails until it is listed.

- **/cold-read** — a skill used to improve the readability of prose.
- **/explain** — a skill that re-explains a message the user could not follow, so he can understand the message without the agent-session's context.
- **/ghi-write** — a skill used before any write to a GitHub issue.
- **/handoff** — a skill that hands a session over to a new one.
- **/pull-request-review-write** — a skill used before writing or revising a review on a pull request.
- **/sanity-check** — a skill used to improve designs.
- **/walk-me-through** — a skill that presents complex material to the user one item or step at a time.
- **-draft** — the filename suffix of a document still being written and not yet put to review, such as `docs/drafts/<subject>-draft.md`.
- **agent-arbitrator** — a fresh-agent, used to resolve conflicts between agents.
- **agent-binary** — the installed program a cold-read-cell or a sanity-check-cell runs its model through, `claude` or `codex`.
- **agent-home** — the directory an agent-seat works in, `~/agents/<seat name>` on the agent-seat's machine: a git worktree on the agent-seat's seat-branch.
- **agent-instructions** — prompts or Markdown files that instruct agents, wherever an agent reads them, such as CLAUDE.md, a skill, a seat-brief or AGENTS.md.
- **agent-seat** — a named, long-lived agent identity with its own worktree, seat-branch and seat-brief, held by a series of agent-sessions joined by session-handoffs.
- **agent-session** — one running conversation occupying an agent-seat. Agent-sessions end and are replaced; the agent-seat persists.
- **approval-walk** — presenting material to the user one item at a time, under /walk-me-through, for a decision on each item; its outcomes are recorded in walk-minutes.
- **approved-by-walk** — approved by the user item by item in an approval-walk, not by one yes to a bundle.
- **build-slice** — one numbered increment of a build plan, built and merged on its own.
- **C-numbers** — the identifiers `C1`, `C2` … of the main-gatekeeper's decisions on the credential that pushes to main, defined in `nc-systems/main-gatekeeper/main-gatekeeper-design.md` § The credential and enforcement.
- **code-prompt-code (aka CPC)** — a program built from both code and prompts.
- **conversation-tail** — the verbatim tail of an agent-session's dialog, `~/.claude/handoffs/<seat>-dialog-NNNN.md`, which the handoff-supervisor writes when it replaces the agent-session, for the successor to read first.
- **create-GHI** — the ghi-write-tool operation that files a new GHI for a GHI-MD that has none, refusing when an open GHI already covers the same ground.
- **design-contract** — the file beside a design listing what the component promises its component-consumers, one testable clause per observable effect.
- **design-to-main** — the workflow that takes an approved design to code, tests and a pull request; its design and its own glossary are in `docs/design-to-main/`.
- **edit-GHI** — the ghi-write-tool operation that merges an edit of a filed GHI-MD into main and updates the GHI from main.
- **fix-round** — one cycle of a pull request answering review findings, written by a forked subagent that inherits the author's full context, as one commit on top of the frozen-head.
- **fresh-agent** — a minimal-context agent: one that has read only its agent-instructions, the documents selected for it to read, and (recursively) the documents linked from the selected documents.
- **fresh-reader** — a fresh-agent, or a person, reading a document with no context beyond the document and what it links.
- **frozen-head** — a pull request's head commit once pushed, which is never amended or force-pushed; a fix is a new commit on top.
- **GHI** — GitHub issue
- **ghi-info** — the GHI knowledge agent, which an agent asks, with `scripts/ghi-info-ask.py`, which issues to read before filing or editing an issue.
- **GHI-MD** — the MD file used to explain a GitHub issue.
- **ghi-write-tool** — `scripts/ghi-issue-write.py`, the program whose operations are create-GHI and edit-GHI.
- **hand-merge** — a merge of main into a conflicting pull-request branch, with each conflict resolved by hand and nothing else changed, pushed on top of the frozen-head.
- **handoff-supervisor** — the program `nc-systems/handoff/handoff-supervisor.py`, one per agent-seat, that launches an agent-session, replaces it when it writes a session-handoff, and exits when it ends without one.
- **handoff-system** — the subsystem that replaces an agent-session with a fresh one, which continues from the session-handoff the old agent-session wrote. Overview: `docs/nedschorus-wiki/nedschorus-handoff-system-overview.md`.
- **hard-block** — a refusal that nothing overrides.
- **ID-type** — the kind of thing an identifier names, and the word written before its name in a citation: `GHI` for a GitHub issue, `PR` for a pull request, agent-seat for an agent-seat, and the ordinary word for a commit, task or session.
- **initial-agent-instructions** — the agent-instructions in the prompt that starts an agent or a subagent.
- **link-only-GHI** — a GHI whose body is only links to its GHI-MD and supporting documents; the GHI-MD holds the text.
- **log-store** — the directory on ned-box, `/home/nedlern/nedschorus-logs/`, holding the byproducts of the work that are not the system, cold-read records first.
- **main-gatekeeper** — the program that will be the only way a change reaches main. Until it is live, changes reach main by PR through merge-lane.
- **merge-lane** — the role that reviews and merges every PR into main, held by the agent-seat merge-lane-2 on ned-box.
- **NC** — this project, NedsChorus.
- **project-term** — a name with a meaning specific to this project and used by more than one of its systems or subsystems, listed in this glossary: an abbreviation such as GHI, a skill's slash name such as /handoff, or a hyphenated phrase such as agent-seat, or a filename suffix such as -draft, whose leading hyphen marks it as a project-term. A word this glossary does not list is not a project-term; a term one system uses alone is a system-term.
- **proposed-improvements-or-changes-file** — a file beside a GHI-MD or an architecture overview, named `<document name>-proposed-improvements-or-changes-<source>-<date>.md`, in which one reviewer records changes it proposes to that document or to what the document describes; GHI [Proposed improvements or changes to a GHI are handled by agents first, and reach the user only when they need him](https://github.com/nedschorus/nedschorus/issues/1132) says how its entries are settled.
- **queue-drain** — the procedure that empties the queue directories and `docs/drafts/`, promoting, archiving or deleting each item; its issue is GHI [Queue drain procedure — the review process that empties the wiki queue, the pair queue, nc-queue, docs/drafts and the draft-label issue queue](https://github.com/nedschorus/nedschorus/issues/24).
- **reincarnate-seat** — the handoff-supervisor replacing an agent-session with a fresh one that continues from the session-handoff, usually when the agent-session's context runs low.
- **retire-seat** — to end an agent-seat for good so its name can be freed or reused; distinct from pausing it. The steps are in `docs/nedschorus-wiki/nedschorus-agent-seat-model.md`.
- **SDLC-term** — a standard term of software engineering or of another computing field, such as operating systems, networking or databases, used with its standard meaning, as `flock` is; `docs/nedschorus-wiki/nedschorus-sdlc-terms.md` lists those this project relies on.
- **seat-branch** — the long-lived git branch of one agent-seat, named for the agent-seat, that the handoff-supervisor's launcher creates; its agent-sessions work on topic branches cut from main.
- **seat-brief** — the `CLAUDE.local.md` at the root of an agent-seat's checkout, which git does not track: the file an agent-seat's occupant reads to learn its job.
- **session-handoff** — the act of transferring the key context and state of one agent-session to the next, and the file that carries it, `~/.claude/handoffs/<seat>-handoff.md`, on the agent-seat's machine only and never committed.
- **soft-block** — a refusal the agent clears by writing its own reasoning into the marker the refusal names.
- **system-term** — a term used by one system or subsystem alone, defined in that system's own glossary rather than here; a term used by more than one is a project-term, defined here and in no system glossary. The system glossaries are listed at the top of this page.
- **test-design** — the document, written from a design and its design-contract, listing one requirement per promise a test must observe, each with the coverage-type of the test that will cover it.
- **user-block** — a refusal that only the user's approval, quoted into the marker the refusal names, clears.
- **user-ruling** — a decision by the user, recorded where it applies in the form (user-ruled YYYY-MM-DD).
- **work-snapshot** — a git commit, kept under `refs/work-snapshots/` and never on a branch, that copies one worktree's uncommitted changes so they survive a crash.
