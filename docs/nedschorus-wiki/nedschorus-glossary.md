# nedschorus glossary

A list of the phrases and terms of this project approved by the user, in alphabetical order, skills first. Generic SDLC vocabulary is deliberately absent.

Every project-specific term is listed here; a term this page does not list is not a project term. A term made from ordinary words is a hyphenated phrase, never a bare generic word: agent-seat, not seat. The hyphens mark it as a defined term with a project meaning, so a reader knows to look it up here and an ordinary word keeps its ordinary meaning (user-ruled 2026-09-15).

- **/cold-read** — a skill used to improve the readability of prose.
- **/ghi-write** — a skill used before any write to a GitHub issue.
- **/handoff** — a skill that hands a session over to a new one.
- **/sanity-check** — a skill used to improve designs.
- **/walk-me-through** — a skill that presents complex material to the user one item or step at a time.
- **agent-arbitrator** — a fresh agent, used to resolve conflicts between agents.
- **agent-instructions** — prompts or MD files that instruct agents. Initial agent instructions are the agent-instructions given to an agent at its session start via the prompt that starts the agent or subagent. In addition, instructions can live in CLAUDE.md, CLAUDE.local.md, the project's appended system-prompt file, the project's memory index, a session-start hook, or the equivalent for non-Claude agents such as AGENTS.md.
- **agent-seat** — a named, long-lived agent identity with its own worktree, seat-branch and seat-brief; context compressed and renewed by a series of agent-sessions connected by session-handoffs from old agent to new agent.
- **agent-session** — one running conversation occupying an agent-seat. Agent-sessions end and are replaced; the agent-seat persists.
- **build-slice** — one numbered increment of a build plan, built and merged on its own.
- **C-numbers** — `C1`, `C3`, `C7`…, the identifiers of the main-gatekeeper's credential rulings, defined in `docs/cross-project/main-gatekeeper-design.md` § The credential and enforcement.
- **code-prompt-code (aka CPC)** — a program built from both code and prompts.
- **component-consumer** — anything that invokes a component or reads what it leaves; the parties a component-contract makes promises to. Defined in the design-to-main glossary.
- **coverage-type** — the word on an implementation or a test saying what kind of thing it is: `script`, `prompt`, `script-and-prompt`; a test may also be `no-tests` with a reason. Defined in the design-to-main glossary.
- **design-to-main** — the workflow that takes an approved design to code, tests and a submission to the gate; its design and its own glossary are in `docs/design-to-main/`. Terms that belong to it alone are defined there, not here.
- **fresh reader or fresh agent** — A minimal context agent, an agent that has read only its agent-instructions, the documents selected for it to read, and (recursively) the documents linked from the selected documents. This project's durable documents, wiki pages, skills and designs, the documents of lasting value, are written for minimal context fresh agents rather than for the user, to enable parallelism and increase reliability.
- **GHI** — GitHub issue
- **GHI-MD** — the MD file used to explain a GitHub issue.
- **handoff-supervisor** — the program `scripts/handoff-supervisor.py`, one per agent-seat, that launches an agent-session, replaces it when it writes a session-handoff, and exits when it ends without one.
- **hard-block** — a hook refusal with no override, often accompanied by additional context given to teach the agent the preferred behavior. There are three types of hook blocks: hard-block, soft-block and user-block.
- **log-store** — the directory on ned-box, `/home/nedlern/nedschorus-logs/`, holding the byproducts of the work that are not the system, cold-read records first.
- **main-gatekeeper** — the program that will be the only way a change reaches main. Until it is live, changes reach main by PR through merge-lane.
- **merge-lane** — the agent-seat on the user's Mac that reviews and merges PRs until the main-gatekeeper is live.
- **NedsChorus (aka NC)** — this project.
- **objection-overruled** — the record of a review objection that the user overruled.
- **reincarnate-seat** — the handoff-supervisor replacing an agent-session with a fresh one that continues from the session-handoff; triggered when the agent writes a session-handoff, usually because the Stop hook `scripts/handoff-context-threshold-hook.py` asked it to as context ran low.
- **seat-branch** — the long-lived git branch of one agent-seat, named for the seat, that the handoff-supervisor's launcher creates; its agent-sessions work on topic-branches cut from main.
- **seat-brief** — `docs/agents/<seat>-instructions.md`, what an agent-seat's occupant reads to learn its job. Seat-briefs vary in shape; read yours for what it says.
- **session-handoff** — the act of transferring the key context and state of one agent-session to the next, and the file that carries it, `~/.claude/handoffs/<seat>-handoff.md`, on the seat's machine only and never committed.
- **soft-block** — a hook refusal the agent can override by including a reason why the override is needed.  Usually accompanied by additional context given to teach the agent the desired behavior.  
- **topic-branch** — a branch cut from current main for one change, PR'd when its tests pass; not a seat-branch.
- **user-block** — a hook refusal that can only be cleared by the user.
- **user-ruling** — a decision by the user, recorded where it applies in the form (user-ruled YYYY-MM-DD).
- **walk-minutes** — the document the /walk-me-through skill uses to record the outcome of each item of a walk.
- **walked-approval** — the user's approval given item by item through a /walk-me-through walk, not one yes to a bundle; recorded by quoting his words into `.walk-approved` at the root of the session's own checkout, which `.claude/hooks/instruction-file-guard.py` consumes for the single write it approves.
