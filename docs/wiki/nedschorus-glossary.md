# nedschorus glossary

A list of the phrases and terms of this project approved by the user, in alphabetical order, skills first. Generic SDLC vocabulary is deliberately absent.

- **/cold-read** — a skill used to improve the readability of prose.
- **/ghi-write** — a skill used before any write to a GitHub issue.
- **/handoff** — a skill that hands a session over to a new one.
- **/sanity-check** — a skill used to improve designs.
- **/walk-me-through** — a skill that presents complex material to the user one item or step at a time.
- **agent-instructions** — prompts or MD files that instruct agents. Initial agent instructions are the agent-instructions given to an agent at its session start via the prompt that starts the agent or subagent. In addition, instructions can live in CLAUDE.md, CLAUDE.local.md, the project's appended system-prompt file, the project's memory index, a session-start hook, or the equivalent for non-Claude agents such as AGENTS.md.
- **agent-seat** — a named, long-lived agent identity with its own home directory, git branch and initial agent instructions; context compressed and renewed by a series of reincarnated agents connected by session handoffs from old agent to new agent.
- **arbitrator** — a fresh agent, used to resolve conflicts between agents.
- **Code Prompt Code (aka CPC)** — a program built from both code and prompts.
- **component-consumer** — anything that invokes a component or reads what it leaves; the parties a component-contract makes promises to. Defined in the design-to-main glossary.
- **coverage-type** — the word on an implementation or a test saying what kind of thing it is: `script`, `prompt`, `script-and-prompt`; a test may also be `no-tests` with a reason. Defined in the design-to-main glossary.
- **design-to-main** — the workflow that takes an approved design to code, tests and a submission to the gate; its design and its own glossary are in `docs/design-to-main/`. Terms that belong to it alone are defined there, not here.
- **fresh reader or fresh agent** — A minimal context agent, an agent that has read only its agent-instructions, the documents selected for it to read, and (recursively) the documents linked from the selected documents. This project's durable documents, wiki pages, skills and designs, the documents of lasting value, are written for minimal context fresh agents rather than for the user, to enable parallelism and increase reliability.
- **GHI** — GitHub issue
- **GHI-MD** — the MD file used to explain a GitHub issue.
- **handoff-supervisor** — the program, one per agent-seat, that launches a session and reincarnates it when the session hands off.
- **hard-block** — a hook refusal with no override, often accompanied by additional context given to teach the agent the preferred behavior. There are three types of hook blocks: hard-block, soft-block and user-block.
- **main-gatekeeper** — the program that will be the only way a change reaches main. Until it is live, changes reach main by PR through merge-lane.
- **merge-lane** — the agent-seat on the user's Mac that reviews and merges PRs until the main-gatekeeper is live.
- **NedsChorus (aka NC)** — this project.
- **reincarnate** — to replace a running session with a new one that continues from the session handoff.
- **review objection overruled by user** — the record of a review objection that the user overruled.
- **session handoff** — the act of transferring the key context and state of one LLM session to the next, and the file that carries it.
- **soft-block** — a hook refusal the agent can override by including a reason why the override is needed.  Usually accompanied by additional context given to teach the agent the desired behavior.  
- **user-block** — a hook refusal that can only be cleared by the user.
- **user ruling** — a decision by the user, recorded where it applies in the form (user-ruled YYYY-MM-DD).
- **walk minutes** — the document the /walk-me-through skill uses to record the outcome of each item of a walk.
