Issue: https://github.com/nedlern/nedschorus/issues/4

## Founding-context notes (new-vp review at admission, 2026-07-21)

- Admission ≠ authorization: every external action (domain purchase, account creation, first post on any platform) needs the boss's explicit go, one at a time — the earned-complexity ladder applies to publishing exactly as to automation.
- The daily journal's raw material largely already exists by construction: the committed `handoff/<NNNN>-transcript.md` series and the numbered handoffs are the build-and-learning record the journal entries distill from.
- The strategy's seven publishing skills join the skills roster AFTER the five founding skills; each is built (or imported through the entry checkpoint) when its channel goes live, not before.
- Body below is cops's staged text, admitted verbatim; revisions ride this pair as ordinary REVISE dispositions.

# Ned's Chorus Open-Source Publishing and Community Strategy

Ned's Chorus should publish from an owned home, use social platforms for discovery, and give technical participants a clear path from reader to contributor. The daily journal is the source; newsletters and social posts are edited derivatives, not competing archives.

## Decisions

- Open-source Ned's Chorus from the beginning.
- Make `nedschorus.com` the permanent project and publishing home.
- Publish a short daily build-and-learning journal on the owned domain.
- Use Substack for a weekly email relationship, not as the canonical daily archive.
- Use a self-managed `r/nedschorus` community for conversation about the project.
- Use GitHub for code, actionable issues, releases, and contributor-facing decisions.
- Syndicate selectively. Do not publish the same full entry indiscriminately to every platform.
- Treat Reddit and Hacker News as communities with their own norms, not as broadcast endpoints.

## Goals

The publishing system should:

1. Build a durable, searchable account of creating Ned's Chorus.
2. Let readers follow without requiring a social-platform account.
3. Help technically interested readers become testers and contributors.
4. Accumulate the project's reputation under the `nedschorus.com` name.
5. Keep daily publishing small enough that it does not displace building the project.
6. Make one piece of source material reusable without making every channel sound automated.

## Publication Architecture

| Surface | Role | Recommended cadence | Primary action for readers |
|---|---|---:|---|
| `nedschorus.com/journal` | Canonical daily archive | Daily | Read, subscribe, inspect linked work |
| GitHub repository | Code, issues, releases, contribution | Continuous | Try, report, contribute |
| GitHub Discussions | Open-ended project questions and announcements | As needed | Discuss and propose |
| Substack | Weekly editorial digest and email list | Weekly | Subscribe by email |
| LinkedIn personal profile | Professional discovery and founder narrative | Two or three posts per week | Comment or follow |
| DEV Community | Selected technical articles | One or two per week | Read technical detail |
| Bluesky | Lightweight daily conversation | Most days | Reply, follow, share |
| `r/nedschorus` | Project-owned Reddit community | Daily seed initially; then community-led | Discuss, show work, ask questions |
| Hacker News | Exceptional essays and usable-project milestones | Occasionally | Evaluate and discuss |

The owned site should expose RSS or Atom in addition to email. Each journal entry should have a stable URL, publication date, useful title and description, social-preview image, self-referencing canonical link, and links to the relevant commit, issue, discussion, release, or demonstration.

When substantially identical content appears elsewhere, the copy should identify the `nedschorus.com` entry as canonical where the platform supports that. Google treats canonical annotations as a strong signal for selecting the representative URL and consolidating duplicate-page signals.[^google-canonical]

## Daily Journal Format

The daily entry is a laboratory note, not an obligation to produce a polished essay. A repeatable entry should answer:

1. What did I try?
2. What did I expect?
3. What actually happened?
4. What surprised me or changed my mind?
5. What changed in the project?
6. What remains unresolved?
7. Where can the reader inspect or try it?

A useful default length is 300–800 words. A day with one concrete observation is publishable; padding it into a grand lesson is not necessary.

### Daily entry template

```markdown
---
title: "<Specific finding or change>"
date: YYYY-MM-DD
description: "<One-sentence reason this entry is interesting>"
canonical_url: "https://nedschorus.com/journal/<slug>/"
---

# <Specific finding or change>

## What I tried

<The experiment, implementation, or decision.>

## What I expected

<The prior model or prediction.>

## What happened

<Observed result, including failures.>

## What I learned

<The change in understanding and why it matters.>

## What changed

- Commit: <link>
- Issue or discussion: <link>
- Demonstration: <link, when available>

## What comes next

<The next experiment or an honest unresolved question.>
```

## Weekly Substack Letter

The Substack should be an original weekly synthesis rather than seven duplicated daily posts. A strong recurring structure is:

- The week's central discovery
- Five short things learned
- One failed approach and what it revealed
- One decision that changed the project
- The best demonstration, screenshot, or code link
- What will be tested next week

`notes.nedschorus.com` is the cleanest Substack address if the newsletter is created there. Substack currently requires a subdomain for custom domains, charges a one-time custom-domain fee, and still sends newsletters from a Substack email address.[^substack-domain] Substack permits exporting posts and publication data, so the archive and subscriber list are recoverable.[^substack-export]

Do not redirect the root `nedschorus.com` domain to Substack. Keep the root domain as the project home and make the newsletter one part of that project.

## LinkedIn Publishing

Publish primarily from the founder's personal profile. A new software brand has little relationship capital; the person building it does.

Each LinkedIn post should stand on its own:

1. Open with the surprising observation or tension.
2. Explain what happened in two to five short paragraphs.
3. Include one image, result, or concrete example when useful.
4. Link to the canonical journal entry for the complete account.
5. Ask a real question only when the answer could influence the project.

Use a weekly LinkedIn newsletter later if the personal posts establish recurring interest. LinkedIn newsletters can notify subscribers by email, push notification, and in-product notification.[^linkedin-newsletter]

## DEV Community Syndication

Cross-post the strongest technical entries to DEV Community after the original appears on `nedschorus.com`. Good candidates include reproducible failures, architectural lessons, measured comparisons, debugging accounts, and small tutorials.

Do not cross-post diary entries whose value depends on following the entire project narrative. DEV supports a `canonical_url` frontmatter field, so syndicated copies can point search engines and readers to the owned original.[^dev-canonical]

## Bluesky Presence

Use Bluesky for short daily observations, screenshots, questions, release links, and conversations with individual developers. Configure the account to use `@nedschorus.com` as its handle if available. Bluesky identities support human-readable domain handles resolved through DNS or HTTPS.[^bluesky-identity]

A Bluesky post should usually contain the idea itself, not only a headline and outbound link. The link is evidence or continuation.

## GitHub Community Surfaces

Use each GitHub surface for one kind of work:

- Repository README: what Ned's Chorus is, who it is for, how to try it, and current maturity.
- Issues: actionable defects and bounded work.
- Discussions: open-ended questions, design proposals, demonstrations, polls, and announcements.
- Releases: durable versioned changes and upgrade notes.
- Contributing guide: the smallest safe path to a first contribution.

GitHub Discussions is designed for project direction, questions, announcements, polls, and open-ended conversation that does not yet belong in an issue.[^github-discussions]

Every journal entry that describes a code change should link to inspectable repository evidence. Every repository release should link back to the most useful explanatory journal entry when one exists.

## The `r/nedschorus` Community

Creating a subreddit makes its creator the top moderator. The moderator controls the community rules, appearance, flairs, moderation team, removals, and bans within that community, subject to Reddit's sitewide rules and Moderator Code of Conduct.[^reddit-moderator]

This avoids dependence on the moderators of unrelated subreddits. It does not make the community independent of Reddit itself: Reddit administrators control the platform, and an abandoned community can be requested by another moderator.[^reddit-inactive]

### Name and creation constraints

- Prefer exactly `r/nedschorus`, in lowercase.
- Confirm availability through Reddit's creation interface; the public availability check was inconclusive.
- Reddit community names are permanent, including capitalization.
- A created community cannot be deleted, although it can be made private or left without its original moderator.[^reddit-create][^reddit-delete]
- Create it when there is enough initial material to keep it visibly active, rather than reserving it and leaving it empty.

### Recommended initial settings

- Community type: public
- Display name: Ned's Chorus
- Description: a concise statement that this is the official community for the open-source project and its build journal
- Initial topics: software development, open source, and the most accurate available AI-agent or developer-tools topic
- Post flairs: `Official`, `Build Log`, `Question`, `Design`, `Showcase`, `Bug`, `Help`, `Discussion`
- User flair: postpone until real community roles emerge
- Moderation: begin with manual review and simple rules; add automation only in response to observed problems

### Initial rules

1. Discuss Ned's Chorus, collaborative software development, or directly relevant experiments.
2. Criticism is welcome; attack arguments and behavior, not people.
3. Do not publish secrets, private transcripts, credentials, or another person's personal information.
4. Use GitHub Issues for reproducible bugs and bounded feature requests; discussion may begin on Reddit.
5. Do not spam products, referral links, low-effort generated content, or unrelated projects.
6. Disclose affiliation when presenting a tool, service, or project connected to you.

### Seed content

Start the community with enough substance that a new visitor understands what participation looks like:

1. Welcome and purpose
2. What Ned's Chorus is and is not
3. Current project status and how to try it
4. Weekly open questions thread
5. First build-log discussion
6. Contribution and bug-reporting guide
7. Community rules and moderation philosophy

Use a short native summary for each daily journal discussion, then link to the complete entry. The subreddit should contain meaningful discussion even if the reader does not follow the link.

After activity develops, appoint one trusted backup moderator with full permissions and strong account security. The founder remains top moderator, while the backup reduces the risk of losing operational access through one account.

## Reddit Outside `r/nedschorus`

Do not automatically repost every journal entry into larger programming communities. Participate in a relevant subreddit and share a Ned's Chorus article only when it directly contributes to that community's subject.

Reddit states that promotional content is not inherently spam, but individual communities may prohibit it or use expectations such as no more than ten percent self-promotional participation.[^reddit-promotion] The rules of the destination subreddit still apply even when the author manages `r/nedschorus`.

## Hacker News

Use Hacker News for exceptional technical articles and meaningful project milestones, not as a daily distribution channel. Hacker News permits submitting one's own work some of the time but asks users not to use the site primarily for promotion.[^hacker-news-guidelines]

Use `Show HN` only when people can try a non-trivial build. Blog posts, newsletters, signup pages, and ordinary reading material do not qualify as Show HN submissions.[^show-hn]

## Channels Not Needed at Launch

Do not add Medium, Threads, X, Mastodon, Discord, Slack, or YouTube merely to claim coverage. Add another channel only when at least one of these is true:

- A real audience is already present there.
- Readers repeatedly ask for that format or community.
- Existing source material can be adapted at low cost without becoming generic.
- The platform enables something the current set cannot, such as demonstrations through video.

A later YouTube channel may be useful for short demonstrations and monthly retrospectives. A chat community should wait until there is enough participation to justify real-time moderation and enough durable documentation to prevent useful answers disappearing into chat.

## Sustainable Publishing Workflow

### Daily

1. Write the journal entry in Markdown alongside the project.
2. Run formatting, link, metadata, canonical-URL, RSS, and build checks.
3. Publish to `nedschorus.com`.
4. Create one social-preview image from a project visual, screenshot, diagram, or recurring illustrated system.
5. Produce a short Reddit discussion version and a short Bluesky version.
6. Publish a LinkedIn version only when the entry has a clear professional lesson.
7. Record the canonical URL and distribution results in machine-readable metadata.

### Weekly

1. Rank the week's entries by reader response, technical importance, and narrative value.
2. Write the Substack synthesis.
3. Cross-post one or two deeply technical entries to DEV with their canonical URLs.
4. Publish the weekly open thread in `r/nedschorus`.
5. Review questions and feedback that should become GitHub Discussions or Issues.
6. Record which channels produced subscribers, participants, bug reports, or contributors.

### At meaningful milestones

1. Publish a GitHub release.
2. Write an owned-site explanation and demonstration.
3. Decide whether the milestone is strong enough for Hacker News or Show HN.
4. Prepare to remain present for discussion after submitting it.

## Measures That Matter

Avoid optimizing for raw impressions. Track outcomes that move an open-source project:

- Returning readers
- RSS and email subscribers
- People who successfully try the project
- GitHub stars only as a weak awareness signal
- Discussions containing substantive feedback
- Reproducible bug reports
- First-time contributors
- Repeat contributors
- Journal entries that continue receiving search traffic
- Channel-to-site visits and site-to-GitHub conversions

Review these monthly. Stop investing in a channel that creates posting work but no conversations, subscribers, users, or contributors.

## Skills and Automation to Find or Build

The first skill should own the source-of-truth workflow. Social automation comes after the publishing path is reliable.

### 1. Owned-site journal publishing skill

Trigger examples: "publish today's journal", "publish this build log", "turn this into a Ned's Chorus post".

Required behavior:

- Create or revise a Markdown journal entry from notes and linked repository evidence.
- Preserve the author's voice and separate observation from interpretation.
- Generate and validate title, slug, date, description, canonical URL, tags, and social metadata.
- Verify links to commits, issues, discussions, releases, and demonstrations.
- Build and render the site locally.
- Validate RSS or Atom, sitemap, canonical links, and social-preview tags.
- Present the rendered result before deployment.
- Commit the exact source that produced the deployment.

Search terms: `static site publishing`, `Markdown blog`, `Astro blog`, `Eleventy blog`, `Hugo blog`, `RSS`, `Open Graph`, `SEO validation`, `deployment`.

### 2. Channel adaptation skill

Trigger examples: "adapt this post for distribution", "make the social versions".

Required behavior:

- Read the canonical article rather than inventing a second source.
- Produce distinct drafts for LinkedIn, Bluesky, Reddit, and DEV.
- Keep each version native to the channel.
- Set DEV's canonical URL.
- Never publish automatically unless the invocation explicitly requests publication.
- Return every draft with the destination, character or format constraints, canonical link, and proposed publication time.

Search terms: `content repurposing`, `social syndication`, `cross-posting`, `DEV API`, `LinkedIn post`, `Bluesky API`, `Reddit API`.

### 3. Weekly editorial digest skill

Trigger examples: "make this week's Chorus Notes", "prepare the weekly digest".

Required behavior:

- Enumerate that week's canonical entries and repository milestones.
- Select rather than concatenate.
- Identify the central narrative, strongest lesson, failed approach, decision, and next experiment.
- Produce a Substack-ready draft plus subject line and preview text.
- Link every summarized claim to its owned source.

Search terms: `newsletter`, `Substack`, `weekly digest`, `editorial synthesis`, `RSS digest`.

### 4. Social-preview image skill

Trigger examples: "make the preview image for this entry", "create today's journal card".

Required behavior:

- Use the established warm, harmonious Ned's Chorus visual language rather than technological or science-fiction imagery.
- Prefer project screenshots, diagrams, garden imagery, musical motifs, or human collaboration when they fit the article.
- Produce the site's required Open Graph dimensions and platform-safe crops.
- Keep title text readable and avoid turning every entry into the same generic template.
- Verify the rendered preview against the actual page metadata.

Search terms: `Open Graph image`, `social preview`, `image generation`, `brand templates`, `dynamic OG images`.

### 5. Subreddit steward skill

Trigger examples: "prepare today's subreddit discussion", "review the Ned's Chorus mod queue", "write the weekly open thread".

Required behavior:

- Draft native discussion posts from canonical entries.
- Apply appropriate post flair.
- Distinguish official announcements from ordinary participation.
- Summarize moderation reports without hiding dissent.
- Enforce only the published community rules.
- Escalate ambiguous moderation decisions for human review.
- Never ban a person, remove a substantial good-faith critique, or change community settings without explicit approval.

Search terms: `Reddit moderation`, `Reddit API`, `subreddit management`, `AutoModerator`, `community management`.

### 6. Release-to-publication skill

Trigger examples: "turn this release into a public explanation", "prepare the launch package".

Required behavior:

- Read the exact release diff, merged issues, and demonstrations.
- Produce the owned-site release article, GitHub release notes, newsletter section, social drafts, and—only when warranted—a Hacker News draft.
- State maturity and limitations honestly.
- Verify that installation and try-it instructions work from a clean environment.

Search terms: `release notes`, `GitHub Releases`, `changelog`, `launch checklist`, `Show HN`.

### 7. Publishing analytics skill

Trigger examples: "review this month's publishing", "which channels are working".

Required behavior:

- Combine owned-site, newsletter, GitHub, and platform metrics.
- Separate reach from meaningful project outcomes.
- Attribute traffic and conversions through consistent campaign parameters where appropriate.
- Identify entries that led to trials, issues, discussions, or contributions.
- Recommend a specific channel cadence change and show the evidence.

Search terms: `privacy-friendly analytics`, `Plausible`, `Umami`, `Google Search Console`, `newsletter analytics`, `GitHub traffic`.

## Skill Selection Criteria

Prefer a skill or automation when it:

- Keeps Markdown and owned URLs as the source of truth.
- Exposes drafts for human review before external publication.
- Supports export and migration.
- Uses official APIs or documented platform behavior.
- Is idempotent: rerunning does not create duplicate posts.
- Records destination URLs and publication state.
- Fails visibly on partial publication.
- Keeps credentials out of prompts, generated files, and logs.
- Allows one channel to fail without blocking the canonical owned-site publication.

Reject a skill or service when it:

- Requires composing the source article inside a proprietary platform.
- Publishes the same text everywhere without channel-specific review.
- Cannot set or preserve canonical URLs where duplication matters.
- Hides publication state or makes duplicate posts difficult to detect.
- Requests broad account permissions unrelated to its job.
- Treats impressions as the publishing system's primary success measure.

## Recommended Launch Sequence

1. Establish the canonical journal and feed at `nedschorus.com`.
2. Publish three to five entries so new visitors can understand the project.
3. Open the GitHub repository with clear maturity, license, contribution, and security information.
4. Create and seed `r/nedschorus` after confirming the exact name through Reddit's creation screen.
5. Establish the Substack weekly letter at `notes.nedschorus.com`.
6. Begin LinkedIn and Bluesky adaptation from the owned entries.
7. Cross-post the first strong technical article to DEV with its canonical URL.
8. Submit to Hacker News only when a particular article merits it; use Show HN when the project is genuinely usable.
9. Review channel outcomes after thirty days and remove work that is not producing readers, users, feedback, or contributors.

## Sources

[^google-canonical]: [Google Search Central: How to specify a canonical URL](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)
[^substack-domain]: [Substack: Set up a custom domain](https://support.substack.com/hc/en-us/articles/360051222571-How-do-I-set-up-my-custom-domain-on-Substack)
[^substack-export]: [Substack: Export publication posts and data](https://support.substack.com/hc/en-us/articles/360037466012-How-do-I-export-my-posts)
[^linkedin-newsletter]: [LinkedIn: Newsletters FAQ](https://www.linkedin.com/help/linkedin/answer/a517914/newsletters-on-linkedin-faq)
[^dev-canonical]: [DEV Community: Editor Guide](https://dev.to/p/editor_guide)
[^bluesky-identity]: [Bluesky: Resolving Identities](https://docs.bsky.app/docs/advanced-guides/resolving-identities)
[^github-discussions]: [GitHub: About Discussions](https://docs.github.com/en/discussions/collaborating-with-your-community-using-discussions/about-discussions)
[^reddit-moderator]: [Reddit Help: How to become a moderator](https://support.reddithelp.com/hc/en-us/articles/205192505-How-do-I-become-a-moderator)
[^reddit-inactive]: [Reddit Help: Take over an inactive community](https://support.reddithelp.com/hc/en-us/articles/360043478471-How-can-I-take-over-an-inactive-community)
[^reddit-create]: [Reddit Help: Create a community](https://support.reddithelp.com/hc/en-us/articles/15484258409492-How-to-create-a-community)
[^reddit-delete]: [Reddit Help: Delete a community](https://support.reddithelp.com/hc/en-us/articles/15484241265684-How-do-I-delete-a-community)
[^reddit-promotion]: [Reddit Help: How to keep spam out of a community](https://support.reddithelp.com/hc/en-us/articles/28012014962580-How-do-I-keep-spam-out-of-my-community)
[^hacker-news-guidelines]: [Hacker News Guidelines](https://news.ycombinator.com/newsguidelines.html)
[^show-hn]: [Show HN Guidelines](https://news.ycombinator.com/showhn.html)
