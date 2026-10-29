---
issue: "[Approval-walk item page publisher copying linked files into the page as timestamped copies, so short repository and log-store paths open on the iPad](https://github.com/nedschorus/nedschorus/issues/2168)"
---

# Approval-walk item page publisher copying linked files into the page as timestamped copies, so short repository and log-store paths open on the iPad

The user approved filing this GHI on 2026-10-28 as item 5.2.1.1 of ned-box-helper's approval-walk `ned-box-helper-open-items-2026-10-27`. Nothing is built yet. The next action is to answer the open questions at the end with the user, then write the program.

Sources: the walk-document, `nedlern@ned-box:/home/nedlern/agents/ned-box-helper/docs/walk/ned-box-helper-open-items-2026-10-27.md`, section "Item 5.2.1.1", and its walk-minutes beside it, `nedlern@ned-box:/home/nedlern/agents/ned-box-helper/docs/walk/ned-box-helper-open-items-2026-10-27-minutes.md`, lines 122 to 142. Neither file is on main yet; both reach the log-store when the approval-walk closes.

## Why

An agent publishes each approval-walk item as a private claude.ai Artifact page, as the walk-me-through skill says ([`.claude/skills/walk-me-through/SKILL.md` line 32](https://github.com/nedschorus/nedschorus/blob/5b53a6b9810db6156b0f6d2512ebae33071c8492/.claude/skills/walk-me-through/SKILL.md#L32)). Today the agent builds each item page itself. `~/.claude/CLAUDE.md` asks that a file linked for the user be written as a `file:///Volumes/nedhome/...` link, and such a link opens only on the Mac.

The user, 2026-10-28, on item 5.2.1: "I looked at 5.2.1. There are two links to other files on my iPad. When I click on the what looks like a blue hyperlink, nothing happens. I guess they could become artifact-like things that would be clickable. I do like clickable links, but I don't want to mess up. I don't want to mess up all the conventions and prompts and labels to make links clickable in a few places. And I think we've already tried to reduce that by giving most files unique names and making it so that files can be quoted by name and not by a full path. But now I'm thinking maybe we can even make it simpler by just changing the artifact creation of walk items to be a bit smarter. So maybe that's a new GHI."

For item 5.2.1, ned-box-helper then copied the two files into its page by hand, and they opened on the iPad.

The user, 2026-10-28, answering the first version of item 5.2.1.1: "I'm looking at your item. My initial reaction is that this is a case where we could use some more code prompt code, that the code, we could have agents consistently write the links or the file or the paths, I guess, in short form. I'm not sure what the right word is. And then we could have the code prompt code expand that to whatever form is needed. I would tend to keep the normal combo stuff short because I almost always I'm increasingly doing everything in walks, and the walk HTML version, the code prompt code could make it so everything was clickable in the way we were just talking about before, which is that I'm not quite sure, but maybe there's a copy that the web server can serve up or something like that. So maybe I'm a bit confused, so we might have to discuss this some more. But that's what I'm thinking."

## What the program does

As item 5.2.1.1 (version 2) proposed and the user approved:

- It is one program that every agent runs to publish an approval-walk item. It is code alone: it needs no prompt.
- In the walk-document, the agent writes a file in short form: its path in the repository or the log-store, such as `nc-systems/handoff/handoff-design.md`.
- The program finds each such file, refusing and naming any it cannot find.
- It copies each file into the item page's artifact as a page of its own, and turns the short form into a link to that copy.
- The walk-document and the walk-minutes keep the short form.

The walk-minutes add that the program is a step the walk-runner could later run.

The case against, from the item: a copy is frozen when published. The user, on that: "So if the links from the walks are read-only, that's a simple solution".

## The visible timestamp on each copy

The user, 2026-10-28 at 21:56Z, approving the item (transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-ned-box-helper/329c61e9-768b-4f49-ba30-e96248b687b8.jsonl`): "Approve. My one comment is, I think it would, it might be useful, or I think it would be useful for copies that I see by clicking on items in a walk, or copies of files, that is. Perhaps to have in their header a time information that reflects the time that the original file was created, a time and date in, for me, in California time, my in local time. Because as you say, these are frozen, and that way if I am paying attention and I am looking at something, I can check very easily when it was frozen, just in case I somehow blunder upon something that's old. And with Code Prompt Code, that should be very easy. So anyway, so I'm thinking that's, if we do have frozen copies, that they should be timestamped in a visible way, which should be pretty easy."

So each copy shows, in its header, a date and time in Pacific time. ned-box-helper has since added such a header by hand to the two copies on item 5.2.1's page.

## Open questions (added by ned-box-helper's subagent that filed this GHI, not from the user)

Everything in this section is the filing subagent's, not the user's; the item and the user's words above do not settle any of it.

1. **Which time the header shows.** The user's words name two times: "the time that the original file was created" and "when it was frozen". Should the header show the time the copy was made, the time the original file last changed, or both?
2. **Which version of a repository file is copied.** The copy of `nc-systems/handoff/handoff-design.md` on item 5.2.1's page was taken from a branch, not main. Should the program copy a repository file from the publishing agent-seat's checkout, or from main?
3. **Who publishes the page.** Only an agent can call Claude Code's Artifact tool, so a program that is "code alone" cannot publish a claude.ai page by itself. Does the program build the page and its copied files, and the agent then publish them with the Artifact tool?
4. **How the program recognises a short form.** The item gives a repository example only. How is a log-store path written in short form, and how does the program tell a file path from other text in backticks, such as a branch name or a command, so that it does not refuse on them?
5. **Files that are not Markdown.** How is a copied Python script, JSON Lines transcript or other non-Markdown file shown as a page that reads well on an iPad?
6. **Republishing.** When an item changes and its page is republished as version 2, 3 and so on, does the program take new copies with new times?
7. **The walk-runner.** The walk-minutes say the program is a step the walk-runner could later run. Should the walk-runner run it at every publish and republish, so no agent has to remember to?
8. **Other questions for the build.** How does the program get the item's text: from the walk-document's path and the item number? Where does it run, and where does it put the page and copies before they are published? How does the header look, so that it does not break the copied file? What happens when two linked files share a file name in different directories? What does the agent do when publishing to claude.ai fails? Should the header also name the branch and commit a repository file was copied from, and say when the file differs from main? Should a hook on the Artifact tool refuse an item page the program did not build?
9. **A neighbouring design, not yet filed.** On 2026-10-29 another agent-session on ned-box was writing the GHI-MD `docs/issues/markdown-files-served-as-web-pages-from-ned-box-to-the-lan.md`, on the branch `ghi-markdown-files-served-as-web-pages-from-ned-box-to-the-lan-topic-branch` in the worktree `/home/nedlern/Projects/nedschorus/.claude/worktrees/agent-aa70bcd8200280656`. Its title: "A read-only web server on ned-box renders Markdown files as web pages on the LAN, for approval-walk item pages and other pages agents now publish to claude.ai". That branch had no pull request (`gh pr list --head` found none) and was not on origin (`git ls-remote --heads origin` found nothing); once filed, it can be found by searching the GHIs for that title. If that server is built, does it replace this program, or does this program stay for pages the server cannot reach, such as on an iPad away from home or from an agent-seat on the Mac?
