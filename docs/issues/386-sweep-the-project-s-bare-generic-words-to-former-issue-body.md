---
issue: "[Sweep the project's bare generic words to project terms, under the 2026-09-15 three-form rule](https://github.com/nedschorus/nedschorus/issues/386)"
---

# Sweep the project's bare generic words to project terms, under the 2026-09-15 three-form rule

## What this is

On 2026-09-15 the user ruled how this project names its own words, and the rule landed in PR [Glossary: project terms are hyphenated phrases, abbreviations or slash names; the seat model's words become headwords; CLAUDE.md says so](https://github.com/nedschorus/nedschorus/pull/384): a word used in a project-specific sense is a project term, a term takes one of three forms (an abbreviation, a skill's slash name, or a hyphenated phrase), every term is in the glossary, and a new term is proposed to him in one message, not walked. This issue tracks the sweep of the tree to that rule. The substance — his verbatim rulings, the rename lists, the terms, the skill route — is the pair document [docs/issues/386-project-term-sweep-rulings-and-open-work.md](https://github.com/nedschorus/nedschorus/blob/main/docs/issues/386-project-term-sweep-rulings-and-open-work.md), landed in PR [GHI-MD for #386: the project-term sweep's five rulings and the work they leave](https://github.com/nedschorus/nedschorus/pull/393).

## Why it matters

The rule made the tree non-compliant the moment it landed: the cold-read skill alone used ten words in a project-specific sense that no glossary entry defined. Mostly the hyphenated forms already existed in the code and the prose dropped them.

## Ruled 2026-09-15, in the MD-skills seat's walk (details in the pair document)

1. **Scope.** In: what is being used or will be used — operative prose, wiki pages, script comments, live designs. Out: git history, walk minutes, cold-read records, the frozen test set, closed issues. An unclear file is judged by that test, not its directory.
2. **`approval-walk`** joins the glossary.
3. **`fresh-reader` and `fresh-agent`** both stay, as two headwords; fresh-agent is the broad term, fresh-reader the narrow.
4. **`NedsChorus (aka NC)`** becomes `NC — this project, NedsChorus`; no rule change.
5. **File names already on main** are not renamed except when already being edited for another reason.

Approved the same evening, in one message each: the seven fresh-reader/fresh-agent sentences, old and new; the seven cold-read terms `cold-read-cell`, `cold-read-record`, `cold-read-grid`, `cold-read-tier`, `cold-read-fast-read`, `cold-read-full-run`, `cold-read-target`; and the file name `finding-dispositions.md` for the triage record both review instruments write, one name for both.

## Ruled 2026-09-16, in the cold-read-research seat's walk of the five seat-brief cold reads (item 1)

1. **`info-agent`** joins the glossary. It is the user's name for the class of agents like ghi-info: "I proposed info-agent. I guess I have a preference for shorter names." The entry, approved as written: "info-agent — a long-lived agent that answers other agents' questions about one domain (the GHIs, PRs, the wiki, one system) and keeps that domain's knowledge current. It is not an agent-seat: a script runs it one question at a time, with no seat-brief and no handoffs, and the user does not talk to it. ghi-info is the first."
2. **"domain-knowledge agent" is renamed to info-agent** in `docs/issues/26-dynamic-agent-team-model.md`, `docs/issues/46-ghi-info-agent-design.md` and the queue note `git show 93bcc041:docs/nedschorus-wiki/queue/26-lifecycle-revision-from-ghi-info.md`. That note was deleted on 2026-09-28 (queue-drain item 13) after its three lifecycle facts were written into `docs/issues/26-dynamic-agent-team-model.md` without the old term, so it needs no rename.
3. **`agent-seat` keeps its glossary definition.** The proposed rename to interactive-agent was declined: "I'm fine with an agent-seat as defined".

Already applied: the ghi seat-brief calls ghi-info an info-agent, landed in PR [Five seat briefs rewritten against current state, with the cold read's fixes and the walk's rulings](https://github.com/nedschorus/nedschorus/pull/454).

## Landed

- PR [GHI-MD for #386: the project-term sweep's five rulings and the work they leave](https://github.com/nedschorus/nedschorus/pull/393): the pair document.
- PR [Glossary: eleven project terms from the 2026-09-15 rulings, and the fresh-reader sentences swept](https://github.com/nedschorus/nedschorus/pull/396): the glossary entries above (approval-walk, fresh-reader, fresh-agent, NC, the seven cold-read terms) and the seven fresh-reader sentences in `.claude/skills/` and `CLAUDE.md`, plus the fast-read script's embedded prompt copy.

- PR [Cold-read reviewers read the glossary, and the terminology reviewer proposes key-terms](https://github.com/nedschorus/nedschorus/pull/533), 883f629: the cold-read reviewers read the glossary. All four prompts read `docs/nedschorus-wiki/nedschorus-glossary.md` before the document; the terminology prompt is rewritten to the user's rulings of 2026-09-18 and 2026-09-19 (a term is any word or short phrase; a project-term is one the glossary lists; a key-term is a term that is or should be a project-term; test (5) is the glossary check; the fixes run glossary name, standard term, the page's own term, then a proposed project-term; a two-meaning term gets one fix per meaning; a definition the glossary also holds is proposed dropped); `terminology.codex.md` is deleted, one prompt for both reviewers; the skill gains step 1, the glossary check, and step 8 is the user's own paragraph routing a proposed term to the glossary, to rejection, or to the new `docs/nedschorus-wiki/nedschorus-sdlc-terms.md`. The glossary gains key-term and SDLC-term. Its own cold-read-full-run found no reviewer proposing a rename of a project-term, which is the failure this work set out to stop; about a hundred findings on untouched text are held by GHI [cold-read skill: about a hundred findings from its 2026-09-19 six-reviewer read await their walk](https://github.com/nedschorus/nedschorus/issues/531). Walk minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-skill-glossary-awareness-minutes.md`.
- PR [sanity-check skill: steps 5 and 6 name claude and codex, not runtimes](https://github.com/nedschorus/nedschorus/pull/535), 4a3c916: the sanity-check skill's steps 5 and 6 name `claude` and `codex` rather than "runtime", after PR [Glossary: a sanity-check-cell runs its attack with claude or with codex](https://github.com/nedschorus/nedschorus/pull/525) did the same for the glossary's sanity-check-cell entry on the user's wording.

## Remaining, at the MD-skills seat

1. **The cold-read skill's prose swept to the seven terms.** Walked section by section and approved by the user 2026-09-16; PR [cold-read skill: sweep its prose to the glossary's project terms](https://github.com/nedschorus/nedschorus/pull/405), at merge-lane.
2. **The cold-read scripts' comments swept**, comments and docstrings only, no code changed: PR [cold-read scripts: sweep comments and docstrings to the glossary's project terms](https://github.com/nedschorus/nedschorus/pull/408), at merge-lane.
3. **`dispositions.md` → `finding-dispositions.md`** in the cold-read skill's step 7, `scripts/cold-read-record-ship.py` and the grid's messages; shipped records on ned-box keep the old name, so the shipper accepts both. The `/sanity-check` skill draft on the cold-read-research seat already writes the new name.
4. **The agent-seat-model page renames** are NOT this seat's: the fleet-restart-at-login-04 seat walked that page with the user on 2026-09-15 (ten items, all ruled) and lands it in one PR with two further glossary terms (handoff-system, retire-seat). One conflict between that walk and the list in the pair document, "a seat's work" → "the agent-seat's subject area" versus leaving the phrase as ordinary prose, is with the user; whichever he rules, the page is done once, by that seat, which reports back here when it lands.
5. **The cold-read skill's step 7 route** for a terminology finding whose fix is a rename beyond the document: four ask-the-user cases become five (text in the pair document). Skill prose: cold read, walk, marker.

## Remaining, not yet assigned to a seat

1. **The 2026-09-16 rulings above.** The info-agent glossary entry and the rename in the three files are not yet made. When the rename lands, the ghi seat-brief's sentence "the class GHI [Dynamic agent-team model: sparring pairs, on-tap domain experts, spy-triaged oversight (design capture; research pending)](https://github.com/nedschorus/nedschorus/issues/26) calls domain-knowledge agents" in `docs/agents/ghi-instructions.md` stops being true and drops that clause.

## Notes

Searched `gh issue list --state all --search "rename project term hyphenated"` at filing: no existing issue. Adjacent but distinct: GHI [Project vocabulary wiki page: define this project's own terms so a zero-context reader can resolve them](https://github.com/nedschorus/nedschorus/issues/213) (the glossary page itself), GHI [update-glossary skill: the editor rules for the nedschorus glossary, taken off the page (user-asked 2026-09-06)](https://github.com/nedschorus/nedschorus/issues/262) (the update-glossary skill's editor rules), GHI [wiki-write skill, and the detect-set-aside-ask hook that enforces it — checking the file, not the tool call](https://github.com/nedschorus/nedschorus/issues/343) (wiki-write skill). `scripts/md-drift-lint.py` flags seven lines in the pair document; merge-lane's reviewer checked all seven and found them false positives (quotes of a declined proposal, of renames not yet applied, and log-store paths that never exist in the repository). Do not "fix" them.
