#!/usr/bin/env python3
"""Regenerate the local GHI mirror (nedschorus#46, design doc
docs/issues/46-ghi-info-agent-design.md § The GHI mirror).

`ghi-info` — the project's knowledge agent over its GitHub-issue corpus —
answers only from this mirror, never from GitHub directly (the cold-start
prompt's own rule). This script is what keeps the mirror true: it writes
`<mirror-dir>/issues-open.md` (every open issue near-raw: number, title,
labels, updated time, body, comments) and `issues-closed.md` (one line per
closed issue: number, title, close reason, closed date), plus an internal
cache (`.mirror-cache.json`) that makes delta refreshes possible without
re-parsing the rendered Markdown back into data.

Two modes:
  --full   Rebuild the cache from a fetch of every issue, open or closed,
           discarding anything not returned (a GitHub-side deletion is
           purged here — the mirror should never claim an issue GitHub
           itself has stopped returning).
  (delta)  The default. One `updated:>` search against the cache's newest
           seen timestamp re-fetches only changed issues, open or closed,
           and merges them in. Cheap and the routine path — run before
           every ask (design § The ask path, step 1). A session recycle
           calls --full instead, per the design's "rewritten whole from a
           full fetch" rule; deciding WHEN to recycle is ghi-info-ask.py's
           job, not this script's.

Fetches ride `gh api graphql` against GitHub's search connection, not
`gh issue list --json`: measured 2026-08-23 that the box's gh (2.46.0,
Ubuntu's apt package, well behind the Mac's 2.97.0) rejects `--json
stateReason` outright — that field isn't in its allowlist at all, so the
CLI-side flag would silently drop close reasons on the one machine that
actually runs this script. GraphQL's `stateReason` is a server-side schema
field, unaffected by the CLI's own version. The same query returns full
comment bodies inline for every matched issue, paginated — the design's
"comments fetched only for changed issues (one call per issue)" predates
this discovery; delta mode still fetches comments only for changed issues,
just riding the same paginated query as everything else, not a second call.

Also verified, against the live repo and a throwaway probe repo made for
exactly this (nedschorus/ghi-api-probes, private): close, reopen, and a
label added or removed by a standalone `gh issue edit` all move
`updated_at`; only a label bundled into the SAME `gh issue create --label`
call does not move it past the creation timestamp — harmless, since
creation itself always moves `updated_at`, so the issue is still caught by
the next delta query regardless. The design's own named residual — a
same-second boundary clip between two mutations can still slip past a delta
query using strict `>` — is real and accepted; it is what the recycle-time
full rewrite bounds.

Mirror writes go temp-then-rename throughout, so a refresh racing another
process reading the files never exposes a half-written one.

Usage:
  ghi-mirror-refresh.py [--full] [--mirror-dir PATH] [--repo OWNER/NAME]

Exit 0 and prints one JSON line to stdout on success — the contract
ghi-info-ask.py's resume preamble reads:
  {"changed": [13, 24], "full_refresh": false, "mirror_dir": "...",
   "open_path": "...", "closed_path": "..."}
An empty "changed" list means nothing moved since the last refresh. Exit 1
and a plain message on stderr on failure (gh unreachable, bad JSON, an
unwritable mirror directory) — nothing is written; the caller's own fallback
ladder (design § A failed ask never blocks a write) is what handles this,
not a partial mirror.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_REPO = "nedschorus/nedschorus"
DEFAULT_MIRROR_DIR = "ghi-mirror"
CACHE_FILE_NAME = ".mirror-cache.json"
OPEN_FILE_NAME = "issues-open.md"
CLOSED_FILE_NAME = "issues-closed.md"
# Issues per page; GitHub's search connection caps at 100.
PAGE_SIZE = 100
# A generous ceiling against a runaway pagination loop (a server that never
# reports hasNextPage: false) — comfortably above the corpus size measured
# 2026-08-07 (45 issues) and the ~140 seen live at this build.
MAX_PAGES = 50

# Raw GraphQL, not `gh issue list --json ...`: measured 2026-08-23 against
# the box's gh 2.46.0 (Ubuntu's apt package, well behind the Mac's 2.97.0) —
# `--json stateReason` is not in that version's field allowlist at all, so
# the CLI-side flag would silently strip close reasons from the one machine
# that actually runs this script. GraphQL's `stateReason` is a server-side
# schema field, unaffected by the CLI's own version; querying it directly
# with `gh api graphql` works identically on both machines. Comments ride
# the same query (confirmed 2026-08-23: no separate per-issue call needed,
# on either gh version) — the design's "comments fetched only for changed
# issues (one call per issue)" predates this discovery either way.
SEARCH_QUERY = """
query($searchQuery: String!, $cursor: String) {
  search(query: $searchQuery, type: ISSUE, first: %d, after: $cursor) {
    nodes {
      ... on Issue {
        number
        title
        state
        stateReason
        updatedAt
        createdAt
        closedAt
        body
        labels(first: 50) { nodes { name } }
        author { login }
        comments(first: 100) { nodes { author { login } createdAt body } }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
""" % PAGE_SIZE

# A gh that never ran (missing binary, timeout) reports a code gh itself
# cannot return, so "no answer" is never read as "ran and failed with 0
# issues found" — same convention as checkout-freshness-catch-up.py's
# GIT_DID_NOT_RUN.
GH_DID_NOT_RUN = -1


def run_gh(arguments, timeout=120):
    try:
        return subprocess.run(["gh", *arguments], capture_output=True, text=True,
                              check=False, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(arguments, GH_DID_NOT_RUN, "",
                                           f"{type(error).__name__}: {error}")


def _issue_from_node(node: dict) -> dict:
    return {
        "number": node["number"],
        "title": node["title"],
        "state": node["state"],
        "stateReason": node.get("stateReason"),
        "updatedAt": node["updatedAt"],
        "createdAt": node.get("createdAt"),
        "closedAt": node.get("closedAt"),
        "body": node.get("body"),
        "labels": (node.get("labels") or {}).get("nodes") or [],
        "comments": [
            {"author": comment.get("author"), "createdAt": comment.get("createdAt"),
             "body": comment.get("body")}
            for comment in (node.get("comments") or {}).get("nodes") or []
        ],
        "author": node.get("author"),
    }


def fetch_issues(repo: str, search: str = None):
    """Every issue (not PR) matching search, paginated. `is:issue` scopes the
    search connection to issues since the same number sequence carries PRs
    too. Returns (issues, error)."""
    search_query = f"repo:{repo} is:issue"
    if search:
        search_query += f" {search}"
    issues = []
    cursor = None
    for _ in range(MAX_PAGES):
        arguments = ["api", "graphql", "-f", f"query={SEARCH_QUERY}",
                    "-f", f"searchQuery={search_query}"]
        if cursor:
            arguments += ["-f", f"cursor={cursor}"]
        result = run_gh(arguments)
        if result.returncode != 0:
            return None, (result.stderr or "gh api graphql failed with no stderr").strip()
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            return None, f"gh returned unparseable JSON: {error}"
        if payload.get("errors"):
            return None, f"GraphQL error: {payload['errors']}"
        search_result = payload["data"]["search"]
        issues.extend(_issue_from_node(node) for node in search_result["nodes"])
        page_info = search_result["pageInfo"]
        if not page_info.get("hasNextPage"):
            return issues, None
        cursor = page_info.get("endCursor")
    return None, f"gave up after {MAX_PAGES} pages ({len(issues)} issues) — pagination did not end"


def read_cache(cache_path: Path) -> dict:
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"last_refresh_at": None, "issues": {}}


def write_temp_then_rename(path: Path, content: str) -> None:
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def render_open(issues_by_number: dict, generated_at: str) -> str:
    lines = ["# GHI mirror — open issues", f"# generated {generated_at}", ""]
    for number in sorted(issues_by_number, key=int):
        issue = issues_by_number[number]
        if issue.get("state") != "OPEN":
            continue
        labels = ", ".join(label["name"] for label in issue.get("labels", [])) or "(none)"
        lines.append(f"## #{number} — {issue['title']}")
        lines.append(f"Labels: {labels}")
        lines.append(f"Updated: {issue['updatedAt']}")
        lines.append("")
        lines.append(issue.get("body") or "(no body)")
        comments = issue.get("comments") or []
        if comments:
            lines.append("")
            lines.append("### Comments")
            for comment in comments:
                author = (comment.get("author") or {}).get("login") or "?"
                lines.append(f"- @{author} ({comment.get('createdAt', '?')}):")
                for body_line in (comment.get("body") or "").splitlines():
                    lines.append(f"  {body_line}")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def render_closed(issues_by_number: dict) -> str:
    lines = ["# GHI mirror — closed issues (one line each)", ""]
    entries = []
    for number, issue in issues_by_number.items():
        if issue.get("state") != "CLOSED":
            continue
        reason = (issue.get("stateReason") or "unknown").lower()
        closed_at = issue.get("closedAt") or ""
        closed_date = closed_at[:10] if closed_at else "?"
        entries.append((int(number),
                        f"#{number} — {issue['title']} — closed {closed_date} ({reason})"))
    for _, line in sorted(entries):
        lines.append(line)
    lines.append("")
    return "\n".join(lines)


def refresh(mirror_dir: Path, repo: str, full: bool):
    """Do one refresh; returns (result_dict, error). Writes nothing on error."""
    if full:
        cache = {"last_refresh_at": None, "issues": {}}
    else:
        cache = read_cache(mirror_dir / CACHE_FILE_NAME)

    search = None
    if not full and cache.get("last_refresh_at"):
        search = f"updated:>{cache['last_refresh_at']}"
    fetched, error = fetch_issues(repo, search=search)
    if fetched is None:
        return None, error

    changed_numbers = []
    max_updated = cache.get("last_refresh_at")
    for issue in fetched:
        number = str(issue["number"])
        cache["issues"][number] = issue
        changed_numbers.append(issue["number"])
        updated_at = issue.get("updatedAt") or ""
        if updated_at and (max_updated is None or updated_at > max_updated):
            max_updated = updated_at
    cache["last_refresh_at"] = max_updated or cache.get("last_refresh_at")

    try:
        mirror_dir.mkdir(parents=True, exist_ok=True)
        generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        open_path = mirror_dir / OPEN_FILE_NAME
        closed_path = mirror_dir / CLOSED_FILE_NAME
        cache_path = mirror_dir / CACHE_FILE_NAME
        write_temp_then_rename(open_path, render_open(cache["issues"], generated_at))
        write_temp_then_rename(closed_path, render_closed(cache["issues"]))
        write_temp_then_rename(cache_path, json.dumps(cache, indent=2) + "\n")
    except OSError as error:
        return None, f"could not write the mirror at {mirror_dir}: {error}"

    return {
        "changed": sorted(changed_numbers),
        "full_refresh": full,
        "mirror_dir": str(mirror_dir),
        "open_path": str(open_path),
        "closed_path": str(closed_path),
    }, None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate the local GHI mirror ghi-info reads.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__,
    )
    parser.add_argument("--full", action="store_true",
                        help="rebuild from a full fetch instead of a delta")
    parser.add_argument("--mirror-dir", default=DEFAULT_MIRROR_DIR,
                        help=f"where the mirror lives (default {DEFAULT_MIRROR_DIR})")
    parser.add_argument("--repo", default=DEFAULT_REPO,
                        help=f"owner/name to mirror (default {DEFAULT_REPO})")
    arguments = parser.parse_args(argv)

    mirror_dir = Path(arguments.mirror_dir)
    # No prior cache means a delta query has no cutoff to search from — that
    # is a full fetch in every way but name, so treat it as one rather than
    # asking gh for "everything updated after nothing."
    full = arguments.full or not (mirror_dir / CACHE_FILE_NAME).exists()
    result, error = refresh(mirror_dir, arguments.repo, full)
    if result is None:
        print(f"ghi-mirror-refresh: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
