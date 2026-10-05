# How to choose a name: files, code and project-terms

This page is the full form of CLAUDE.md's naming rule. It covers every name this project invents: file and directory names, script names, the names of functions, classes, constants and variables, and the project-terms and system-terms the glossaries define. Where a file's name or location is set by `docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md`, that page decides the parts it sets, such as a filename suffix or a directory; this page decides how the rest of the name is chosen. Names that something outside this project fixes, such as `CLAUDE.md`, `SKILL.md`, or a flag another program defines, are taken as they are.

## Why names matter so much here

Most readers of this project's names are agents that meet a name with no context. An agent finds a name through `grep`, in a list of files, in a hook's refusal, or in a message from another agent-seat, and it has to act on what the name tells it before it has read anything else. A name that only makes sense to the agent that invented it costs every later reader a search, and a name that misleads costs more: in one study, readers misunderstood code with misleading names more often than code whose names meant nothing at all, and the same holds for language models (Avidan and Feitelson 2017; Wang et al.).

People, and agents, rarely choose the same name for the same thing. Asked to name one thing, two people pick the same word less than one time in five (Furnas et al. 1987), and two developers pick the same identifier about one time in fifteen (Feitelson et al. 2022). So every new name that duplicates an existing one splits the project's vocabulary: a `grep` for one spelling misses the other, and two agents describe one thing in two ways. That is why this page asks you to look before you name, and why the glossaries exist.

## The test every name must pass

A reader who meets the name with no context can tell what it names.

"With no context" means: without the file it is defined in, without the conversation in which it was coined, and without the agent that coined it. If that reader would have to open a file or ask someone to know what the name refers to, the name fails the test, and the fix is to add words until it passes.

You cannot judge this for your own name, because you already know what it means. Judge it by asking what someone who has never seen the thing would guess it is from the name alone. For a new project-term or system-term, the user rules on the name, and a cold read shows how fresh reviewers understood it.

## Step 1: look for an existing name before you make one

If the thing you are naming already has a name in this project, use that name. Do not invent a second one.

Look in three places, in this order:

1. The project glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`, and the system glossary of the system you are working in. The project glossary lists the system glossaries at its top.
2. The SDLC-terms list, `docs/nedschorus-wiki/nedschorus-sdlc-terms.md`. When a standard software-engineering term fits, such as worktree, pull request, or test double, use it with its standard meaning.
3. Your checkout and main. Glob or grep your checkout. Then run `git fetch`, and stop if it fails. Then run `git ls-tree -r --name-only origin/main | grep -i <name>` for a path name, or `git grep -i <name> origin/main` for a name used inside files.

If these checks show that the name you planned is already used for something else, or that a near-identical name exists, choose a more explicit name. Two names that differ only by one letter, by a plural, or by the order of their words (`seat-record` beside `seat-records`, or `review-count` beside `count-review`) are as bad as one name used for two things, because a reader and a `grep` both mix them up.

## Step 2: build the name from three questions

A name that passes the test usually answers three questions by itself:

1. **Which system is it part of?** For example, `gatekeeper`, `cold-read`, `sanity-check`, `handoff`.
2. **What does it act on, or hold?** For example, a check-in request, a review copy, a record.
3. **What does it do, or what is it?** For example, it holds, it spawns, it checks, it ships.

Two names from the main-gatekeeper's build plan show the difference.

- `request-holder` answered only the third question. A reader could not tell which program's requests, or what kind of request. The approved name is `gatekeeper-check-in-request-holder`: `gatekeeper` says which system, `check-in-request` says what it handles, and `holder` says its role, which is to hold the request and its lock until the work ends.
- `spawner` answered only half of the third question: it spawns, but spawns what? The approved name is `gatekeeper-worker-spawner`, which adds the system and the thing it starts.

Existing names in this repository that answer all three: `scripts/branch-conflict-check.py` (acts on: a branch; does: checks it for a conflict), `nc-systems/cold-read/cold-read-record-ship.py` (system: cold-read; acts on: a record; does: ships it), `.claude/hooks/ghi-issue-write-redirect.py` (acts on: a write to a GitHub issue; does: redirects it).

### Order the parts from general to specific

Put the system first, then the thing, then its role or action: `gatekeeper-worker-spawner`, not `worker-spawner-for-the-gatekeeper`; `cold-read-record-ship`, not `ship-cold-read-record`. Names that share a system then sort together in a file listing, and one `grep` for the system's prefix finds them all.

### Use as many words as the test needs

Three to nine parts is normal for a name that travels across files. There is no upper limit set by evidence for names read without context; the studies that favour short names measured local variables inside one function, where the context sits beside the name. Stop adding words when a reader with no context can tell what the name names, or when the next word would only repeat what every name around it already says.

### Common words are fine as one part of a longer name

Words such as `manager`, `handler`, `helper`, `data`, `info`, `record` or `check` say almost nothing alone. As one part of a longer name whose other parts say which one, they are fine: `pull-request-review-data` and `sanity-check-review-copy-handler` say enough. What fails is the bare word, or a two-part name like `seat-manager` that leaves the reader asking what about the seat it manages.

## Step 3: make sure the name tells the truth

A name must not claim something the thing does not do, and must not hide something it does. A script named `sync` that also deletes files misleads; a name that says what it does, such as one ending `-mirror-and-prune`, does not.

Do not put history in a name. Words such as `new-`, `old-`, `-v2`, `-fixed`, `-final` or a trailing number say when or how a thing was written, not what it is, and they become false as soon as the next version arrives. When a thing changes what it does, rename it, and repoint every citation of the old name in the same commit.

Do not abbreviate, apart from abbreviations the project or the industry already uses, such as `pr`, `ghi`, `id` or `url`. An abbreviation a reader has to decode fails the test.

## Step 4: spell the name the same way everywhere

One name has one spelling in prose, in file names and in code. Where a language does not allow a hyphen, use its mechanical equivalent: the project-term `agent-seat` is `agent_seat` in a Python variable or function, `AGENT_SEAT` in a Python constant, and `AgentSeat` in a class name. Proposed, not yet a rule: list a term's code spelling in the glossary entry when code uses it.

Never build a name from parts at run time, for example by joining `"agent"` and `"seat"` in code. A `grep` for the full name then misses the place that uses it.

## Hyphens mark the project's own terms

In prose, a hyphenated phrase marks a project-term or a system-term, such as agent-seat, log-store or cold-read-cell. Do not hyphenate a phrase that is not one. A new project-term, a word with a meaning specific to this project and used by more than one system, is coined only when no SDLC-term fits, and it is proposed to the user before use. A term used by one system alone is a system-term and goes in that system's glossary, also with the user's approval. The glossary page, `docs/nedschorus-wiki/nedschorus-glossary.md`, defines both kinds and lists the system glossaries.

## Exceptions, and why each is one

- **Names for data say what they hold, not what they do.** A file, a record or a variable does nothing; its name answers "what is in it". `walk-minutes` names the file of an approval-walk's rulings; `log-store` names the directory that holds the project's logs.
- **Project-wide names need no system part.** A name that belongs to the whole project, such as `agent-seat` or `ned-box`, has no single system to name, and adding the project's name to it, as in `nedschorus-agent-seat`, adds a word that every name would share and so tells the reader nothing.
- **Standard terms keep their standard names.** `pull request`, `worktree`, `main` and `test double` are already understood by every reader; a longer project-specific name for them would make them harder to recognise, not easier.
- **Names fixed by something outside the project keep their fixed part.** `CLAUDE.md`, `SKILL.md`, `AGENTS.md`, a test framework's `test_` prefix, and the flags another program accepts are set elsewhere. The parts of the name that this project chooses still follow this page.
- **Short-lived local names inside one small function.** A loop index `i`, an exception `error`, or a file handle `f` in a ten-line function has its context on the same screen, and a long name there only adds reading. The test applies to names used beyond the place they are defined: anything another file, another agent, or a `grep` will meet.

## Checklist

1. Did you look in the glossaries, the SDLC-terms list, your checkout and main for an existing name, and use it if one exists?
2. Would a reader with no context tell what the name names?
3. Does it say which system, what it acts on or holds, and what it does or is, unless an exception above applies?
4. Are its parts ordered from the system to the role?
5. Does it differ from every other name by more than a letter, a plural or word order?
6. Does it tell the truth, with no history in it and no abbreviation a reader must decode?
7. Is it spelled the same way in prose, file names and code?
8. If it is a new project-term or system-term, has the user approved it?

## Sources

The research behind this page, with the studies and style guides it draws on and the claims it could not verify: `nedlern@ned-box:/home/nedlern/nedschorus-logs/analysis/2026-10-05-naming-best-practice-research.md`.

- Furnas, Landauer, Gomez and Dumais, "The vocabulary problem in human-system communication", Communications of the ACM, 1987.
- Feitelson et al., "How Developers Choose Names", IEEE Transactions on Software Engineering, 2022: https://arxiv.org/pdf/2103.07487
- Avidan and Feitelson, "Effects of Variable Names on Comprehension", ICPC 2017: https://www.cs.huji.ac.il/w~feit/papers/Names17ICPC.pdf
- Wang et al., "How does naming affect LLMs on code analysis tasks?": https://arxiv.org/html/2307.12488v5
- Hofmeister, Siegmund and Holt, "Shorter identifier names take longer to comprehend", Empirical Software Engineering, 2019: https://link.springer.com/article/10.1007/s10664-018-9621-x
- Deissenböck and Pizka, "Concise and Consistent Naming": https://wwwbroy.in.tum.de/publ/papers/deissenboeck_pizka_identifier_naming.pdf
- Hilton and Hermans, "Naming Guidelines for Professional Programmers", PPIG 2017: https://ppig.org/files/2017-PPIG-28th-hilton.pdf
- Microsoft Writing Style Guide, "Use technical terms carefully": https://learn.microsoft.com/en-us/style-guide/word-choice/use-technical-terms-carefully
- Google Python Style Guide, section 3.16, Naming: https://google.github.io/styleguide/pyguide.html
- Anthropic, "Writing effective tools for agents": https://www.anthropic.com/engineering/writing-tools-for-agents
