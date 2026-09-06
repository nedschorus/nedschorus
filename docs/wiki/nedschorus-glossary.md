# nedschorus glossary

A list of the phrases and terms of this project approved by the user, in alphabetical order, skills first. Generic SDLC vocabulary is deliberately absent.

- **/cold-read** — a skill used to improve the readability of prose.
- **/ghi-write** — a skill used before any write to a GitHub issue.
- **/handoff** — a skill that hands a session over to a new one.
- **/sanity-check** — a skill used to improve designs.
- **/walk-me-through** — a skill that presents complex material to the user one item or step at a time.
- **adjudicator** — a fresh agent, used to resolve conflicts between agents.
- **agent-instructions** — prompts or MD files that instruct agents. Initial agent instructions are the agent-instructions given to an agent at its session start via the prompt that starts the agent or subagent. In addition, instructions can live in CLAUDE.md, CLAUDE.local.md, the project's appended system-prompt file, the project's memory index, a session-start hook, or the equivalent for non-Claude agents such as AGENTS.md.
- **agent-seat** — a named, long-lived agent identity with its own home directory, git branch and initial agent instructions; context compressed and renewed by a series of reincarnated agents connected by session handoffs from old agent to new agent.
- **Code Prompt Code (aka CPC)** — a program built from both code and prompts.
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
