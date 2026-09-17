# nedschorus glossary

A list of the phrases and terms of this project approved by the user, in alphabetical order, skills first. Generic SDLC vocabulary is deliberately absent.

Every project-specific term should be listed here; a term this page does not list is not a project term, at least not yet. If a term should be added to this list, ask the user to review it. A word needs a defined term only where this project does something unexpected with it or gives it a meaning that would be hard to guess; otherwise it stays ordinary prose. A defined term takes one of three forms: an abbreviation such as GHI, a skill's slash name such as /handoff, or a hyphenated phrase such as agent-seat. The hyphens mark a phrase as a defined term with a project meaning, so a reader knows to look it up here and an ordinary word keeps its ordinary meaning (user-ruled 2026-09-15).

- **/cold-read** — a skill used to improve the readability of prose.
- **/ghi-write** — a skill used before any write to a GitHub issue.
- **/handoff** — a skill that hands a session over to a new one.
- **/sanity-check** — a skill used to improve designs.
- **/walk-me-through** — a skill that presents complex material to the user one item or step at a time.
- **agent-arbitrator** — a fresh-agent, used to resolve conflicts between agents.
- **agent-instructions** — prompts or MD files that instruct agents. Initial agent instructions are the agent-instructions given to an agent at its session start via the prompt that starts the agent or subagent. In addition, instructions can live in CLAUDE.md, CLAUDE.local.md, the project's appended system-prompt file, the project's memory index, a session-start hook, or the equivalent for non-Claude agents such as AGENTS.md.
- **agent-seat** — a named, long-lived agent identity with its own worktree, seat-branch and seat-brief; context compressed and renewed by a series of agent-sessions connected by session-handoffs from old agent to new agent.
- **agent-session** — one running conversation occupying an agent-seat. Agent-sessions end and are replaced; the agent-seat persists.
- **approval-walk** — presenting material to the user one item at a time for a decision, conducted by the /walk-me-through skill; its outcomes are recorded in walk-minutes and its approvals are walked-approvals.
- **build-slice** — one numbered increment of a build plan, built and merged on its own.
- **C-numbers** — `C1`, `C3`, `C7`…, the identifiers of the main-gatekeeper's credential rulings, defined in `docs/cross-project/main-gatekeeper-design.md` § The credential and enforcement.
- **code-prompt-code (aka CPC)** — a program built from both code and prompts.
- **cold-read-cell** — one reviewer model reading one cold-read-target under one prompt; a cold-read-full-run is six of them.
- **cold-read-fast-read** — the one-reviewer pass that precedes a cold-read-full-run, run by `scripts/cold-read-fast-read.py`.
- **cold-read-full-run** — the six-cold-read-cell run of the /cold-read skill, launched by the cold-read-grid.
- **cold-read-grid** — the program `scripts/cold-read-grid.py` that launches the six cold-read-cells of a cold-read-full-run.
- **cold-read-pass** — the reviewer prompt a cold-read-cell runs, named for its prompt file: defect-hunt, terminology, restate, fast-clarify.
- **cold-read-record** — the directory holding one run's reports, its frozen cold-read-target and its dispositions; shipped to the log-store.
- **cold-read-target** — the document under review, frozen into the cold-read-record at launch.
- **cold-read-tier** — which model a cold-read-cell runs, and at what effort.
- **component-consumer** — anything that invokes a component or reads what it leaves; the parties a component-contract makes promises to. Defined in the design-to-main glossary.
- **coverage-type** — the word on an implementation or a test saying what kind of thing it is: `script`, `prompt`, `script-and-prompt`; a test may also be `no-tests` with a reason. Defined in the design-to-main glossary.
- **design-to-main** — the workflow that takes an approved design to code, tests and a submission to the gate; its design and its own glossary are in `docs/design-to-main/`. Terms that belong to it alone are defined there, not here.
- **fresh-agent** — a minimal-context agent: one that has read only its agent-instructions, the documents selected for it to read, and (recursively) the documents linked from the selected documents.
- **fresh-reader** — a fresh-agent, or a person, reading a document with no context beyond the document and what it links. This project's durable documents, wiki pages, skills and designs, the documents of lasting value, are written for fresh-readers rather than for the user, to enable parallelism and increase reliability.
- **GHI** — GitHub issue
- **GHI-MD** — the MD file used to explain a GitHub issue.
- **handoff-supervisor** — the program `scripts/handoff-supervisor.py`, one per agent-seat, that launches an agent-session, replaces it when it writes a session-handoff, and exits when it ends without one.
- **hard-block** — a hook refusal with no override, often accompanied by additional context given to teach the agent the preferred behavior. There are three types of hook blocks: hard-block, soft-block and user-block.
- **log-store** — the directory on ned-box, `/home/nedlern/nedschorus-logs/`, holding the byproducts of the work that are not the system, cold-read records first.
- **main-gatekeeper** — the program that will be the only way a change reaches main. Until it is live, changes reach main by PR through merge-lane.
- **merge-lane** — the agent-seat on the user's Mac that reviews and merges PRs until the main-gatekeeper is live.
- **NC** — this project, NedsChorus.
- **objection-overruled** — the record of a review objection that the user overruled.
- **reincarnate-seat** — the handoff-supervisor replacing an agent-session with a fresh one that continues from the session-handoff; triggered when the agent writes a session-handoff, usually because the Stop hook `scripts/handoff-context-threshold-hook.py` asked it to as context ran low.
- **sanity-check-attack** — one stance the /sanity-check instrument takes on a document, run as its own prompt: the cut-attack (what should be deleted), the mechanization-attack (which English instruction should be code), the fresh-eyes-attack (an independent design built from the problem alone).
- **sanity-check-cell** — one fresh agent running one sanity-check-attack on one runtime; a run is six.
- **sanity-check-record** — the directory one /sanity-check run leaves behind, `sanity-check-records/<date>-<target-stem>/`, holding its reports; kept as a log.
- **sanity-check-request** — the file the requesting agent writes for the fresh-eyes-attack: a problem statement plus off-limits and read-first lists, passed to the runner as `--problem-statement`.
- **seat-branch** — the long-lived git branch of one agent-seat, named for the seat, that the handoff-supervisor's launcher creates; its agent-sessions work on topic-branches cut from main.
- **seat-brief** — `docs/agents/<seat>-instructions.md`, what an agent-seat's occupant reads to learn its job. Seat-briefs vary in shape; read yours for what it says.
- **session-handoff** — the act of transferring the key context and state of one agent-session to the next, and the file that carries it, `~/.claude/handoffs/<seat>-handoff.md`, on the seat's machine only and never committed.
- **soft-block** — a hook refusal the agent can override by including a reason why the override is needed.  Usually accompanied by additional context given to teach the agent the desired behavior.  
- **topic-branch** — a branch cut from current main for one change, PR'd when its tests pass; not a seat-branch.
- **user-block** — a hook refusal that can only be cleared by the user.
- **user-ruling** — a decision by the user, recorded where it applies in the form (user-ruled YYYY-MM-DD).
- **walk-minutes** — the document the /walk-me-through skill uses to record the outcome of each item of a walk.
- **walked-approval** — the user's approval given item by item through a /walk-me-through walk, not one yes to a bundle; recorded by quoting his words into `.walk-approved` at the root of the session's own checkout, which `.claude/hooks/instruction-file-guard.py` consumes for the single write it approves.
