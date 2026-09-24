#!/usr/bin/env python3
"""Tests for merge-gate.sh.

Runs the gate under bash with a stand-in `gh` first on PATH. The stand-in serves
responses captured from real read-only GitHub calls, stored in
merge-gate-test-captured-github-responses/ with capture-record.json beside them:
the command, machine, gh version, UTC time, exit code and stderr of each
capture. No fixture here was typed. Where a case needs a value the captures do
not hold together — a merged pull request reads mergeStateStatus UNKNOWN, so a
passing case must be given CLEAN — the suite changes that one field and takes
the value's spelling from another capture that holds it (CLEAN from cli/cli
14475, DIRTY from nedschorus 600, isDraft true from cli/cli 14507). Where a case
needs a review channel as it stood earlier, it serves a leading slice of the
captured channel: GitHub returns reviews oldest first, so a prefix is the channel
as it read before the next review was posted.

The pagination cases are the regression tests for the worst finding, F1: the
gate read one page of 30 items per channel. Their channels are pytorch/pytorch
pull requests 114309 (54 inline, 53 issue, 51 reviews) and 190902 (42 reviews,
the head's approval at index 41, an older one at 23). Nothing in this repository
reached 30 items in any channel when measured 2026-09-22. For each, the
stand-in serves the full paginated capture when the gate passes --paginate and
the captured first page when it does not, which is what gh does.

The stand-in logs every call with the GH_TOKEN it saw. Every case that reaches
gh asserts it was called, that each call named the case's pull request, and
that the token was the one in the case's token file, so a case cannot pass by
reaching the real gh or the real credential. Cases that must stop before gh
assert the log is empty.

Exit codes are asserted exactly: 0 passed, 1 refused, 2 could not run.

THE LIVE-CHAIN CASES ARE THE REGRESSION TESTS FOR F4'S WITHDRAWAL. The merge
lane's chain on ned-box (walk-ledgers/merge-lane-review-gate-merge-chain.sh)
posts its approving review AS ned-review-merge, sets reviewed-since to that
review's submitted_at, and then runs this gate. The 2026-09-22 cleanup's F4
refused an approval by ned-review-merge, which refused both shapes the chain
produced on 2026-09-23: pull request 665, approved only by ned-review-merge, and
667, approved by mac-claude and then by ned-review-merge. The user ruled F4 out
2026-09-23. Both live-chain cases pass on those captures, and the mutation that
re-adds the filter turns 665 red. 667 is not its target: with the filter back,
667 pins mac-claude's approval, and the merge account's own later approval is
within F2's bound below, so it passes.

THE THIRD LIVE-CHAIN CASE IS A PULL REQUEST THE MERGE ACCOUNT OPENED. GitHub
refuses an approval from the author, so on PR 687 mac-claude approved (the pin)
and ned-review-merge then posted its review as COMMENTED, and the chain passed
that review's time as reviewed-since. Bounded by the pin alone, F2 refused it
and so did every earlier reviewed-since (the review counted as new). The bound
is now the later of the pin and the merge account's own latest review; the
mutation back to the pin alone turns the case red, and two neighbouring 687
cases hold the rest of F2 and F5 in place on the same capture.

THE PIN IS EXCLUDED FROM THE REVIEW COUNT BY ID, AND THAT STAYS. Codex asked, on
PR 691's merge review, whether another account's approval posted after
reviewed-since should count: it becomes the pin and is never counted. Counting
the pin instead refuses the lane's own recorded calls. merge-lane-2 gated PR 662
with reviewed-since 2026-09-23T00:54:38Z and PR 663 with 01:32:58Z, each taken
seconds before its own approval posted (00:54:43Z, 01:33:05Z), as recorded in
nedlern@ned-box:/home/nedlern/.claude/projects/-home-nedlern-agents-merge-lane-2/0283c766-09a0-40f0-b809-a0d0833f3264.jsonl.
Case LANE 662 replays the first, and the mutation that counts the pin turns it
red. merge-lane-2's scan of merged pull requests 540 to 701 found none where
another account approved after the merge account, so the case Codex describes
has not occurred.

The mutation section reruns named cases against a mutated COPY of the gate in a
scratch directory, one mutation per fix, and requires each to go red. The file
under test is never modified, so no revert can discard uncommitted work. Each
mutation asserts that its replacement text was found. An unmutated copy is run
after all mutations as the control.

F7, UNSTABLE on the merge-state allow-list, has no case by the user's ruling.

Run: python3 scripts/merge-gate-test.py
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GATE = Path(__file__).with_name("merge-gate.sh")
FIXTURES = Path(__file__).with_name("merge-gate-test-captured-github-responses")
BASH = shutil.which("bash")
TEST_TOKEN = "merge-gate-test-token-not-a-credential"
CHAIN_GATE_LINE = ('bash walk-ledgers/merge-gate.sh "$PR" "$HEAD" "$SINCE" '
                   '|| { echo "GATE REFUSED; not merging"; exit 1; }')

failures = []
scratch = Path(tempfile.mkdtemp(prefix="merge-gate-test-"))

GH_STAND_IN = r'''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
with open(os.environ["MERGE_GATE_TEST_GH_CALL_LOG"], "a") as log:
    log.write(json.dumps({"argv": argv, "gh_token": os.environ.get("GH_TOKEN")}) + "\n")
routes = json.load(open(os.environ["MERGE_GATE_TEST_GH_ROUTES"]))
if argv[:2] == ["pr", "view"]:
    key = "state"
elif argv[:1] == ["api"]:
    endpoint = argv[1]
    channel = ("reviews" if endpoint.endswith("/reviews") else
               "issue" if "/issues/" in endpoint else
               "inline" if endpoint.endswith("/comments") else "unknown")
    key = channel + (":paginated" if "--paginate" in argv else ":first-page")
else:
    key = "unknown"
route = routes.get(key)
if route is None:
    sys.stderr.write("merge-gate-test stand-in: unarranged gh call %r\n" % (argv,))
    sys.exit(97)
sys.stdout.buffer.write(open(route["stdout_file"], "rb").read())
sys.stderr.write(route.get("stderr", ""))
sys.exit(route.get("exit", 0))
'''


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def captured(name):
    path = FIXTURES / name
    if not path.exists():
        raise SystemExit(f"merge-gate-test: captured fixture missing: {path}")
    return path


def channel_items(path):
    """Every item of a channel capture: gh --paginate prints one array per page."""
    decoder = json.JSONDecoder()
    text = Path(path).read_text()
    position, items = 0, []
    while True:
        while position < len(text) and text[position].isspace():
            position += 1
        if position >= len(text):
            return items
        page, position = decoder.raw_decode(text, position)
        items.extend(page)


def captured_value(state_capture, field):
    return json.loads(captured(state_capture).read_text())[field]


def arranged_state(state_capture, **fields):
    state = json.loads(captured(state_capture).read_text())
    state.update(fields)
    path = Path(tempfile.mkstemp(dir=scratch, suffix="-state.json")[1])
    path.write_text(json.dumps(state, separators=(",", ":")) + "\n")
    return path


def channel_prefix(channel_capture, through_id):
    """The captured channel as it stood when the item with through_id was the newest."""
    items = channel_items(captured(channel_capture))
    ids = [item["id"] for item in items]
    kept = items[:ids.index(through_id) + 1]
    path = Path(tempfile.mkstemp(dir=scratch, suffix="-channel.json")[1])
    path.write_text(json.dumps(kept))
    return path


def channel_routes(channel, paginated, first_page=None):
    """Routes for one channel. first_page defaults to the paginated capture,
    which capture-record.json shows byte-identical for channels under a page."""
    return {f"{channel}:paginated": {"stdout_file": str(paginated)},
            f"{channel}:first-page": {"stdout_file": str(first_page or paginated)}}


def captured_channel_routes(channel, stem):
    first_page = FIXTURES / f"{stem}-first-page-only.json"
    return channel_routes(channel, captured(f"{stem}-paginated.json"),
                          first_page if first_page.exists() else None)


QUIET_INLINE = captured_channel_routes("inline", "nedschorus-nedschorus-665-inline-channel")
QUIET_ISSUE = captured_channel_routes("issue", "nedschorus-nedschorus-665-issue-channel")
CLEAN = captured_value("cli-cli-14475-pr-view-state.json", "mergeStateStatus")


def review(channel_capture, review_id):
    for item in channel_items(captured(channel_capture)):
        if item["id"] == review_id:
            return item
    raise SystemExit(f"merge-gate-test: review {review_id} not in {channel_capture}")


# The base every refusal case varies: nedschorus PR 667's review channel as it
# stood after its first review, mac-claude's approval of the merged head, with
# both comment channels quiet and the state given CLEAN.
BASE_PR = "667"
BASE_REVIEWS = "nedschorus-nedschorus-667-reviews-channel-paginated.json"
BASE_APPROVAL = review(BASE_REVIEWS, 5286260878)
BASE_HEAD = captured_value("nedschorus-nedschorus-667-pr-view-state.json", "headRefOid")


def base_routes(**state_fields):
    fields = {"mergeStateStatus": CLEAN}
    fields.update(state_fields)
    routes = {"state": {"stdout_file": str(arranged_state(
        "nedschorus-nedschorus-667-pr-view-state.json", **fields))}}
    routes.update(channel_routes("reviews", channel_prefix(BASE_REVIEWS, BASE_APPROVAL["id"])))
    routes.update(QUIET_INLINE)
    routes.update(QUIET_ISSUE)
    return routes


class Run:
    def __init__(self, completed, calls):
        self.code = completed.returncode
        self.stdout = completed.stdout
        self.stderr = completed.stderr
        self.calls = calls

    def summary(self):
        return (f"exit {self.code}, {len(self.calls)} gh call(s), "
                f"stdout {self.stdout.strip()[:300]!r}, stderr {self.stderr.strip()[:300]!r}")


def run_gate(gate, pr, expected, since, routes, token=TEST_TOKEN, path_override=None,
             wrapper=None):
    case_dir = Path(tempfile.mkdtemp(dir=scratch))
    home = case_dir / "home"
    token_dir = home / ".config" / "nedschorus"
    token_dir.mkdir(parents=True)
    if token is not None:
        (token_dir / "ned-review-merge.token").write_text(token)
    stand_in_dir = case_dir / "bin"
    stand_in_dir.mkdir()
    stand_in = stand_in_dir / "gh"
    stand_in.write_text(GH_STAND_IN)
    stand_in.chmod(0o755)
    routes_file = case_dir / "routes.json"
    routes_file.write_text(json.dumps(routes))
    call_log = case_dir / "gh-calls.jsonl"
    call_log.write_text("")
    environment = {key: value for key, value in os.environ.items() if key != "GH_TOKEN"}
    environment.update(
        HOME=str(home),
        PATH=path_override(stand_in_dir) if path_override else
        f"{stand_in_dir}{os.pathsep}{os.environ['PATH']}",
        MERGE_GATE_TEST_GH_ROUTES=str(routes_file),
        MERGE_GATE_TEST_GH_CALL_LOG=str(call_log))
    arguments = [str(pr), expected, since]
    if wrapper:
        # The live chain's own line, with its relative path pointed at this gate.
        environment["GATE"] = str(gate)
        command = [BASH, "-c", 'PR=$1 HEAD=$2 SINCE=$3; ' +
                   wrapper.replace("walk-ledgers/merge-gate.sh", '"$GATE"'),
                   "chain", *arguments]
    else:
        command = [BASH, str(gate), *arguments]
    completed = subprocess.run(command, capture_output=True, text=True, env=environment,
                               timeout=120)
    calls = [json.loads(line) for line in call_log.read_text().splitlines() if line]
    return Run(completed, calls)


def reached_gh_honestly(run, pr):
    """The stand-in was called, only for this pull request, with the case's token."""
    return (bool(run.calls)
            and all(pr in " ".join(call["argv"]) for call in run.calls)
            and all(call["gh_token"] == TEST_TOKEN for call in run.calls))


def stopped_before_gh(run):
    return not run.calls


def refused_with(run, pr, *phrases):
    return (run.code == 1 and reached_gh_honestly(run, pr)
            and all(phrase in run.stderr for phrase in phrases))


def could_not_run_before_gh(run, *phrases):
    return run.code == 2 and stopped_before_gh(run) and all(p in run.stderr for p in phrases)


def passed_pinned_to(run, pr, sha):
    return (run.code == 0 and reached_gh_honestly(run, pr)
            and f"--match-head-commit {sha}" in run.stdout)


# ---------------------------------------------------------------------------
# Cases. Each returns (ok, detail) for the gate at the path it is given, so the
# mutation section can rerun it against a mutated copy.
# ---------------------------------------------------------------------------

def case_a1_pass_control(gate):
    run = run_gate(gate, BASE_PR, BASE_HEAD, BASE_APPROVAL["submitted_at"], base_routes())
    return passed_pinned_to(run, BASE_PR, BASE_APPROVAL["commit_id"]), run.summary()


def case_live_chain_merge_account_only_approval(gate):
    """PR 665 as the chain gates it: its one approval is ned-review-merge's own."""
    reviews = "nedschorus-nedschorus-665-reviews-channel-paginated.json"
    own = review(reviews, 5286200944)
    routes = {"state": {"stdout_file": str(arranged_state(
        "nedschorus-nedschorus-665-pr-view-state.json", mergeStateStatus=CLEAN))}}
    routes.update(captured_channel_routes("reviews", "nedschorus-nedschorus-665-reviews-channel"))
    routes.update(QUIET_INLINE)
    routes.update(QUIET_ISSUE)
    run = run_gate(gate, "665", own["commit_id"], own["submitted_at"], routes)
    return passed_pinned_to(run, "665", own["commit_id"]), run.summary()


def case_live_chain_second_approval_by_merge_account(gate):
    """PR 667 as the chain gates it: mac-claude approved, then ned-review-merge,
    and reviewed-since is ned-review-merge's approval."""
    own = review(BASE_REVIEWS, 5286364766)
    routes = {"state": {"stdout_file": str(arranged_state(
        "nedschorus-nedschorus-667-pr-view-state.json", mergeStateStatus=CLEAN))}}
    routes.update(captured_channel_routes("reviews", "nedschorus-nedschorus-667-reviews-channel"))
    routes.update(QUIET_INLINE)
    routes.update(QUIET_ISSUE)
    run = run_gate(gate, "667", own["commit_id"], own["submitted_at"], routes)
    return passed_pinned_to(run, "667", own["commit_id"]), run.summary()


PR_687_REVIEWS = "nedschorus-nedschorus-687-reviews-channel-paginated.json"


def pr_687_routes():
    routes = {"state": {"stdout_file": str(arranged_state(
        "nedschorus-nedschorus-687-pr-view-state.json", mergeStateStatus=CLEAN))}}
    routes.update(captured_channel_routes("reviews", "nedschorus-nedschorus-687-reviews-channel"))
    routes.update(captured_channel_routes("inline", "nedschorus-nedschorus-687-inline-channel"))
    routes.update(captured_channel_routes("issue", "nedschorus-nedschorus-687-issue-channel"))
    return routes


def case_live_chain_merge_account_opened_the_pull_request(gate):
    """PR 687 as the chain gates it: the merge account opened it, so it cannot
    approve. mac-claude approved (the pin), then the merge account posted its
    required COMMENTED review, and reviewed-since is that review."""
    pin = review(PR_687_REVIEWS, 5297823520)
    own = review(PR_687_REVIEWS, 5297826635)
    run = run_gate(gate, "687", pin["commit_id"], own["submitted_at"], pr_687_routes())
    return passed_pinned_to(run, "687", pin["commit_id"]), run.summary()


def case_687_since_at_the_approval_counts_the_merge_accounts_review(gate):
    """The same channel with reviewed-since at the approval: the merge account's
    later review is new activity, as every account's is (F5)."""
    pin = review(PR_687_REVIEWS, 5297823520)
    run = run_gate(gate, "687", pin["commit_id"], pin["submitted_at"], pr_687_routes())
    return refused_with(run, "687", "1 NEW review(s)"), run.summary()


def case_687_since_after_the_merge_accounts_review(gate):
    """reviewed-since one second after the merge account's own latest review is
    still later than anything it did, and refuses (F2)."""
    pin = review(PR_687_REVIEWS, 5297823520)
    own = review(PR_687_REVIEWS, 5297826635)
    run = run_gate(gate, "687", pin["commit_id"], one_second_after(own["submitted_at"]),
                   pr_687_routes())
    return refused_with(run, "687", "is later than"), run.summary()


def case_lane_662_since_taken_before_its_own_approval(gate):
    """PR 662 as merge-lane-2 gated it: reviewed-since taken five seconds before
    its own approval posted. The pin's exclusion by id is what passes it."""
    reviews = "nedschorus-nedschorus-662-reviews-channel-paginated.json"
    own = review(reviews, 5285715840)
    routes = {"state": {"stdout_file": str(arranged_state(
        "nedschorus-nedschorus-662-pr-view-state.json", mergeStateStatus=CLEAN))}}
    routes.update(captured_channel_routes("reviews", "nedschorus-nedschorus-662-reviews-channel"))
    routes.update(QUIET_INLINE)
    routes.update(QUIET_ISSUE)
    run = run_gate(gate, "662", own["commit_id"], "2026-09-23T00:54:38Z", routes)
    return passed_pinned_to(run, "662", own["commit_id"]), run.summary()


def case_f2_since_at_another_accounts_later_review(gate):
    """Only the merge account's own reviews extend F2's bound. pytorch 114309's
    pin (malfet, 15:16:51Z) is followed by xinyazhang's COMMENTED review at
    17:20:06Z; reviewed-since at that review is still later than the bound."""
    later = review("pytorch-pytorch-114309-reviews-channel-paginated.json", 1782308820)
    routes = {"state": {"stdout_file": str(arranged_state(
        "pytorch-pytorch-114309-pr-view-state.json", mergeStateStatus=CLEAN))}}
    routes.update(captured_channel_routes("reviews", "pytorch-pytorch-114309-reviews-channel"))
    routes.update(QUIET_INLINE)
    routes.update(QUIET_ISSUE)
    head = captured_value("pytorch-pytorch-114309-pr-view-state.json", "headRefOid")
    run = run_gate(gate, "114309", head, later["submitted_at"], routes)
    return refused_with(run, "114309", "is later than"), run.summary()


def case_b1_inline_beyond_first_page(gate):
    # reviewed-since is the newest timestamp on the captured first page, so every
    # new comment is on page two: 24 of them.
    routes = base_routes()
    routes.update(captured_channel_routes("inline", "pytorch-pytorch-114309-inline-channel"))
    run = run_gate(gate, BASE_PR, BASE_HEAD, "2023-12-05T02:47:43Z", routes)
    return refused_with(run, BASE_PR, "24 NEW inline comment(s)"), run.summary()


def case_b1_issue_beyond_first_page(gate):
    routes = base_routes()
    routes.update(captured_channel_routes("issue", "pytorch-pytorch-114309-issue-channel"))
    run = run_gate(gate, BASE_PR, BASE_HEAD, "2023-12-13T22:18:59Z", routes)
    return refused_with(run, BASE_PR, "21 NEW issue comment(s)"), run.summary()


def case_b1_reviews_beyond_first_page(gate):
    # The pin is index 49; reviewed-since is the newest review on page one, so
    # the 20 reviews after it, the pin excluded, are all on page two.
    routes = {"state": {"stdout_file": str(arranged_state(
        "pytorch-pytorch-114309-pr-view-state.json", mergeStateStatus=CLEAN))}}
    routes.update(captured_channel_routes("reviews", "pytorch-pytorch-114309-reviews-channel"))
    routes.update(QUIET_INLINE)
    routes.update(QUIET_ISSUE)
    head = captured_value("pytorch-pytorch-114309-pr-view-state.json", "headRefOid")
    run = run_gate(gate, "114309", head, "2023-12-05T18:35:06Z", routes)
    return refused_with(run, "114309", "20 NEW review(s)"), run.summary()


def case_b2_pin_beyond_first_page(gate):
    # The head's approvals are indices 39-41; page one holds only an older
    # approval of another commit, at index 23.
    reviews = "pytorch-pytorch-190902-reviews-channel-paginated.json"
    pin = review(reviews, 4887265721)
    routes = {"state": {"stdout_file": str(arranged_state(
        "pytorch-pytorch-190902-pr-view-state.json", mergeStateStatus=CLEAN))}}
    routes.update(captured_channel_routes("reviews", "pytorch-pytorch-190902-reviews-channel"))
    routes.update(QUIET_INLINE)
    routes.update(QUIET_ISSUE)
    head = captured_value("pytorch-pytorch-190902-pr-view-state.json", "headRefOid")
    run = run_gate(gate, "190902", head, pin["submitted_at"], routes)
    return passed_pinned_to(run, "190902", pin["commit_id"]), run.summary()


def one_second_after(timestamp):
    moment = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    return (moment + datetime.timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def case_b3_since_after_the_approval(gate):
    run = run_gate(gate, BASE_PR, BASE_HEAD, one_second_after(BASE_APPROVAL["submitted_at"]),
                   base_routes())
    return refused_with(run, BASE_PR, "is later than"), run.summary()


def case_b4_since_with_an_offset(gate):
    run = run_gate(gate, BASE_PR, BASE_HEAD, "2026-09-23T03:36:54+01:00", base_routes())
    return could_not_run_before_gh(run, "reviewed-since must be exactly"), run.summary()


PR_636_REVIEWS = "nedschorus-nedschorus-636-reviews-channel-paginated.json"


def case_b6_merge_accounts_later_findings(gate):
    # 636's channel as it stood after mac-claude approved 88faccd0: the review
    # before it is ned-review-merge's CHANGES_REQUESTED, after reviewed-since.
    pin = review(PR_636_REVIEWS, 5285938045)
    since = review(PR_636_REVIEWS, 5285368166)["submitted_at"]
    routes = {"state": {"stdout_file": str(arranged_state(
        "nedschorus-nedschorus-636-pr-view-state.json",
        headRefOid=pin["commit_id"], mergeStateStatus=CLEAN))}}
    routes.update(channel_routes("reviews", channel_prefix(PR_636_REVIEWS, pin["id"])))
    routes.update(QUIET_INLINE)
    routes.update(QUIET_ISSUE)
    run = run_gate(gate, "636", pin["commit_id"], since, routes)
    return refused_with(run, "636", "1 NEW review(s)"), run.summary()


CLI_14475_INLINE = "cli-cli-14475-inline-channel-paginated.json"


def cli_14475_routes():
    routes = {"state": {"stdout_file": str(captured("cli-cli-14475-pr-view-state.json"))}}
    routes.update(captured_channel_routes("reviews", "cli-cli-14475-reviews-channel"))
    routes.update(captured_channel_routes("inline", "cli-cli-14475-inline-channel"))
    routes.update(captured_channel_routes("issue", "cli-cli-14475-issue-channel"))
    return routes


def case_b7_edited_comment(gate):
    # reviewed-since is the second comment's created_at. Two comments created
    # before it were updated after it, so the count by latest timestamp is 6 and
    # by created_at alone 4. Every value in this case is as captured.
    since = channel_items(captured(CLI_14475_INLINE))[9]["created_at"]
    head = captured_value("cli-cli-14475-pr-view-state.json", "headRefOid")
    run = run_gate(gate, "14475", head, since, cli_14475_routes())
    return refused_with(run, "14475", "6 NEW inline comment(s)"), run.summary()


def case_c1_token_file_missing(gate):
    run = run_gate(gate, BASE_PR, BASE_HEAD, BASE_APPROVAL["submitted_at"], base_routes(),
                   token=None)
    return could_not_run_before_gh(run, "could not read the merge account's token"), run.summary()


def case_c2_token_file_empty(gate):
    run = run_gate(gate, BASE_PR, BASE_HEAD, BASE_APPROVAL["submitted_at"], base_routes(),
                   token="")
    return could_not_run_before_gh(run, "is empty"), run.summary()


def case_d1_jq_absent(gate):
    run = run_gate(gate, BASE_PR, BASE_HEAD, BASE_APPROVAL["submitted_at"], base_routes(),
                   path_override=lambda stand_in_dir: str(stand_in_dir))
    return could_not_run_before_gh(run, "jq is not on PATH"), run.summary()


def case_d2_abbreviated_expected(gate):
    run = run_gate(gate, BASE_PR, BASE_HEAD[:8], BASE_APPROVAL["submitted_at"], base_routes())
    return could_not_run_before_gh(run, "is 8 characters, not 40"), run.summary()


def case_d3_expected_not_hex(gate):
    run = run_gate(gate, BASE_PR, BASE_HEAD.upper(), BASE_APPROVAL["submitted_at"], base_routes())
    return could_not_run_before_gh(run, "not a full 40-character hex sha"), run.summary()


def case_e1_no_approval(gate):
    routes = {"state": {"stdout_file": str(captured("nedschorus-nedschorus-636-pr-view-state.json"))}}
    routes.update(channel_routes("reviews", channel_prefix(PR_636_REVIEWS, 5285920906)))
    routes.update(QUIET_INLINE)
    routes.update(QUIET_ISSUE)
    head = captured_value("nedschorus-nedschorus-636-pr-view-state.json", "headRefOid")
    since = review(PR_636_REVIEWS, 5285920906)["submitted_at"]
    run = run_gate(gate, "636", head, since, routes)
    return refused_with(run, "636", "no APPROVED review"), run.summary()


def case_e2_head_moved(gate):
    other = captured_value("nedschorus-nedschorus-636-pr-view-state.json", "headRefOid")
    run = run_gate(gate, BASE_PR, other, BASE_APPROVAL["submitted_at"], base_routes())
    return refused_with(run, BASE_PR, "head moved", other, BASE_HEAD), run.summary()


def case_e3_approval_covers_another_commit(gate):
    pin = review(PR_636_REVIEWS, 5285938045)
    routes = {"state": {"stdout_file": str(arranged_state(
        "nedschorus-nedschorus-636-pr-view-state.json", mergeStateStatus=CLEAN))}}
    routes.update(channel_routes("reviews", channel_prefix(PR_636_REVIEWS, pin["id"])))
    routes.update(QUIET_INLINE)
    routes.update(QUIET_ISSUE)
    head = captured_value("nedschorus-nedschorus-636-pr-view-state.json", "headRefOid")
    run = run_gate(gate, "636", head, pin["submitted_at"], routes)
    return refused_with(run, "636", f"the approval covers {pin['commit_id']}", head), run.summary()


def case_e4_draft(gate):
    draft = captured_value("cli-cli-14507-pr-view-state.json", "isDraft")
    run = run_gate(gate, BASE_PR, BASE_HEAD, BASE_APPROVAL["submitted_at"],
                   base_routes(isDraft=draft))
    return draft is True and refused_with(run, BASE_PR, "is a draft"), run.summary()


def case_e5_review_decision_not_approved(gate):
    decision = captured_value("nedschorus-nedschorus-643-pr-view-state.json", "reviewDecision")
    run = run_gate(gate, BASE_PR, BASE_HEAD, BASE_APPROVAL["submitted_at"],
                   base_routes(reviewDecision=decision))
    return refused_with(run, BASE_PR, f"reviewDecision is {decision}"), run.summary()


def case_e6_merge_state(gate, state_capture):
    merge_state = captured_value(state_capture, "mergeStateStatus")
    run = run_gate(gate, BASE_PR, BASE_HEAD, BASE_APPROVAL["submitted_at"],
                   base_routes(mergeStateStatus=merge_state))
    return refused_with(run, BASE_PR, f"mergeStateStatus is {merge_state}"), run.summary()


def case_e6_dirty(gate):
    return case_e6_merge_state(gate, "nedschorus-nedschorus-600-pr-view-state.json")


def case_e6_blocked(gate):
    return case_e6_merge_state(gate, "nedschorus-nedschorus-643-pr-view-state.json")


def case_e6_unknown_as_captured(gate):
    # A merged pull request's state as GitHub returned it, unarranged.
    routes = base_routes()
    routes["state"] = {"stdout_file": str(captured("nedschorus-nedschorus-667-pr-view-state.json"))}
    run = run_gate(gate, BASE_PR, BASE_HEAD, BASE_APPROVAL["submitted_at"], routes)
    return refused_with(run, BASE_PR, "mergeStateStatus is UNKNOWN"), run.summary()


def e7_run(gate):
    pin = review("cli-cli-14475-reviews-channel-paginated.json", 5288445014)
    head = captured_value("cli-cli-14475-pr-view-state.json", "headRefOid")
    return run_gate(gate, "14475", head, pin["submitted_at"], cli_14475_routes())


def case_e7_new_inline_comments(gate):
    # Every value as captured: two inline comments after the approval.
    run = e7_run(gate)
    return refused_with(run, "14475", "NEW inline comment(s)"), run.summary()


def case_e10_stamped_exactly_since_is_not_new(gate):
    # Four of cli/cli 14475's inline comments were updated at the approval's own
    # second; counting them would make the refusal read 6, not 2.
    run = e7_run(gate)
    return refused_with(run, "14475", "2 NEW inline comment(s)"), run.summary()


def case_e9_gh_fails(gate):
    routes = base_routes()
    not_found = captured("nedschorus-nedschorus-999999-reviews-channel-not-found.json")
    record = capture_record_entry(not_found.name)
    for key in ("reviews:paginated", "reviews:first-page"):
        routes[key] = {"stdout_file": str(not_found), "exit": record["exit_code"],
                       "stderr": record["stderr"]}
    run = run_gate(gate, BASE_PR, BASE_HEAD, BASE_APPROVAL["submitted_at"], routes)
    return (record["exit_code"] != 0
            and refused_with(run, BASE_PR, "could not read the review channel")), run.summary()


def comment_channel_failing_after_its_first_page(gate, channel, first_page_capture, reason):
    # gh --paginate prints the pages it has read, then exits non-zero when a later
    # page fails. What it printed here is pytorch 114309's captured first page; the
    # exit status and stderr are the captured 404's. reviewed-since is the base
    # approval, years after every comment on that page, so the partial read counts
    # nothing new and only the channel's status check can refuse.
    record = capture_record_entry("nedschorus-nedschorus-999999-reviews-channel-not-found.json")
    routes = base_routes()
    routes[f"{channel}:paginated"] = {"stdout_file": str(captured(first_page_capture)),
                                      "exit": record["exit_code"], "stderr": record["stderr"]}
    run = run_gate(gate, BASE_PR, BASE_HEAD, BASE_APPROVAL["submitted_at"], routes)
    return (record["exit_code"] != 0 and refused_with(run, BASE_PR, reason)), run.summary()


def case_e9_inline_channel_fails_after_its_first_page(gate):
    return comment_channel_failing_after_its_first_page(
        gate, "inline", "pytorch-pytorch-114309-inline-channel-first-page-only.json",
        "could not read the inline comment channel")


def case_e9_issue_channel_fails_after_its_first_page(gate):
    return comment_channel_failing_after_its_first_page(
        gate, "issue", "pytorch-pytorch-114309-issue-channel-first-page-only.json",
        "could not read the issue comment channel")


def case_fa_chain_line_passes_a_pass(gate):
    run = run_gate(gate, BASE_PR, BASE_HEAD, BASE_APPROVAL["submitted_at"], base_routes(),
                   wrapper=CHAIN_GATE_LINE)
    return run.code == 0 and "GATE REFUSED; not merging" not in run.stdout, run.summary()


def case_fa_chain_line_stops_on_a_refusal(gate):
    run = run_gate(gate, BASE_PR, BASE_HEAD, one_second_after(BASE_APPROVAL["submitted_at"]),
                   base_routes(), wrapper=CHAIN_GATE_LINE)
    return run.code == 1 and "GATE REFUSED; not merging" in run.stdout, run.summary()


def case_fa_chain_line_stops_when_the_gate_could_not_run(gate):
    run = run_gate(gate, BASE_PR, BASE_HEAD, BASE_APPROVAL["submitted_at"], base_routes(),
                   token=None, wrapper=CHAIN_GATE_LINE)
    return (run.code == 1 and "GATE REFUSED; not merging" in run.stdout
            and "GATE COULD NOT RUN" in run.stderr), run.summary()


CASES = [
    ("A1 everything in order passes, pinned to the approval's commit", case_a1_pass_control),
    ("LIVE CHAIN: PR 665 as the chain gates it, approved only by ned-review-merge, passes",
     case_live_chain_merge_account_only_approval),
    ("LIVE CHAIN: PR 667 as the chain gates it, since = ned-review-merge's later approval, passes",
     case_live_chain_second_approval_by_merge_account),
    ("LIVE CHAIN: PR 687, opened by the merge account, since = its COMMENTED review after "
     "mac-claude's approval, passes", case_live_chain_merge_account_opened_the_pull_request),
    ("F2 PR 687 with reviewed-since at the approval counts the merge account's later review",
     case_687_since_at_the_approval_counts_the_merge_accounts_review),
    ("F2 PR 687 with reviewed-since after the merge account's own latest review refuses",
     case_687_since_after_the_merge_accounts_review),
    ("F2 reviewed-since at another account's review after the pin refuses",
     case_f2_since_at_another_accounts_later_review),
    ("LANE: PR 662 as merge-lane-2 gated it, reviewed-since taken before its own approval, passes",
     case_lane_662_since_taken_before_its_own_approval),
    ("B1 an inline comment beyond the first page of 30 is counted", case_b1_inline_beyond_first_page),
    ("B1 an issue comment beyond the first page of 30 is counted", case_b1_issue_beyond_first_page),
    ("B1 a review beyond the first page of 30 is counted", case_b1_reviews_beyond_first_page),
    ("B2 the approval at the head, beyond the first page, is the pin", case_b2_pin_beyond_first_page),
    ("B3 reviewed-since later than the approval refuses", case_b3_since_after_the_approval),
    ("B4 reviewed-since with an offset could not run, before gh", case_b4_since_with_an_offset),
    ("B6 the merge account's later CHANGES_REQUESTED is new activity", case_b6_merge_accounts_later_findings),
    ("B7 a comment edited after reviewed-since is new activity", case_b7_edited_comment),
    ("C1 a missing token file could not run, before gh", case_c1_token_file_missing),
    ("C2 an empty token file could not run, before gh", case_c2_token_file_empty),
    ("D1 jq absent could not run, naming jq", case_d1_jq_absent),
    ("D2 an abbreviated expected sha could not run, naming its length", case_d2_abbreviated_expected),
    ("D3 an expected sha that is not lowercase hex could not run", case_d3_expected_not_hex),
    ("E1 no approving review refuses", case_e1_no_approval),
    ("E2 a moved head refuses, naming both shas", case_e2_head_moved),
    ("E3 an approval of another commit refuses, naming both", case_e3_approval_covers_another_commit),
    ("E4 a draft refuses", case_e4_draft),
    ("E5 reviewDecision CHANGES_REQUESTED refuses", case_e5_review_decision_not_approved),
    ("E6 mergeStateStatus DIRTY refuses", case_e6_dirty),
    ("E6 mergeStateStatus BLOCKED refuses", case_e6_blocked),
    ("E6 mergeStateStatus UNKNOWN, as a merged pull request reads, refuses", case_e6_unknown_as_captured),
    ("E7 inline comments after the approval refuse", case_e7_new_inline_comments),
    ("E10 a comment stamped exactly reviewed-since is not new", case_e10_stamped_exactly_since_is_not_new),
    ("E9 gh failing on a channel read refuses", case_e9_gh_fails),
    ("E9 the inline comment channel failing after its first page refuses",
     case_e9_inline_channel_fails_after_its_first_page),
    ("E9 the issue comment channel failing after its first page refuses",
     case_e9_issue_channel_fails_after_its_first_page),
    ("F-a the chain's gate line exits 0 on a pass", case_fa_chain_line_passes_a_pass),
    ("F-a the chain's gate line stops on a refusal", case_fa_chain_line_stops_on_a_refusal),
    ("F-a the chain's gate line stops when the gate could not run",
     case_fa_chain_line_stops_when_the_gate_could_not_run),
]


def capture_record_entry(file_name):
    for entry in CAPTURE_RECORD["captures"]:
        if entry["file"] == file_name:
            return entry
    raise SystemExit(f"merge-gate-test: {file_name} has no entry in capture-record.json")


CAPTURE_RECORD = json.loads(captured("capture-record.json").read_text())


def check_every_fixture_has_a_capture_record():
    recorded = {entry["file"] for entry in CAPTURE_RECORD["captures"]
                if entry.get("stored", True)}
    stored = {path.name for path in FIXTURES.iterdir() if path.name != "capture-record.json"}
    check("every stored fixture has a capture record, and every record's file is stored",
          recorded == stored,
          f"stored without record {sorted(stored - recorded)}, "
          f"recorded but missing {sorted(recorded - stored)}")


# ---------------------------------------------------------------------------
# Mutations: (name, [(old, new)], [case functions that must go red]).
# ---------------------------------------------------------------------------

# The pre-repository form was `export GH_TOKEN=$(cat $TOKEN_FILE)`, whose status
# is export's; the mutation puts that shape back in place of the whole block.
TOKEN_BLOCK = (
    'token=$(cat "$TOKEN_FILE" 2>/dev/null)\n'
    '[ $? -eq 0 ] || cannot "could not read the merge account\'s token at $TOKEN_FILE"\n'
    '[ -n "$token" ] || cannot "the token file $TOKEN_FILE is empty"\n'
    'export GH_TOKEN="$token"\n')

MUTATIONS = [
    ("F1 without --paginate", [(" --paginate)", ")")],
     [case_b1_inline_beyond_first_page, case_b1_issue_beyond_first_page,
      case_b1_reviews_beyond_first_page, case_b2_pin_beyond_first_page]),
    ("F2 without the reviewed-since bound",
     [('[ "$since_ok" = "true" ] || fail', '[ "$since_ok" = "true" ] || true')],
     [case_b3_since_after_the_approval, case_687_since_after_the_merge_accounts_review]),
    ("F3 without the reviewed-since format check",
     [('*) cannot "reviewed-since must be exactly', '*) : "reviewed-since must be exactly')],
     [case_b4_since_with_an_offset]),
    ("F2 bounded by the pin alone, without the merge account's own latest review",
     [("'[$approved] + [.[][] | select(.user.login == $merge_account and .submitted_at != null)",
       "'[$approved] + [.[][] | select(false)")],
     [case_live_chain_merge_account_opened_the_pull_request]),
    ("F2's bound extended by every account's reviews, not only the merge account's",
     [("select(.user.login == $merge_account and .submitted_at != null)",
       "select(.submitted_at != null)")],
     [case_f2_since_at_another_accounts_later_review]),
    ("the pinned approval counted as new activity",
     [("select(.id != $approval_id and ", "select(")],
     [case_lane_662_since_taken_before_its_own_approval]),
    ("without the inline comment channel's read check",
     [('[ $? -eq 0 ] || fail "could not read the inline comment channel"',
       ': || fail "could not read the inline comment channel"')],
     [case_e9_inline_channel_fails_after_its_first_page]),
    ("without the issue comment channel's read check",
     [('[ $? -eq 0 ] || fail "could not read the issue comment channel"',
       ': || fail "could not read the issue comment channel"')],
     [case_e9_issue_channel_fails_after_its_first_page]),
    ("F4's merge-account filter re-added to the pin",
     [('select(.state == "APPROVED")',
       'select(.state == "APPROVED" and .user.login != "ned-review-merge")')],
     # 665 alone: with the filter back, 667 pins mac-claude's approval and the
     # merge account's own later approval is within F2's bound, so it passes.
     [case_live_chain_merge_account_only_approval]),
    ("F5 with the merge account's reviews excluded again",
     [('select(.id != $approval_id and', 'select(.user.login != "ned-review-merge" and .id != $approval_id and')],
     [case_b6_merge_accounts_later_findings]),
    ("F6 by created_at alone", [("[.created_at, .updated_at]", "[.created_at]")],
     [case_b7_edited_comment]),
    ("the boundary moved to at-or-after",
     [("\n                   > ($since | fromdateiso8601))]",
       "\n                   >= ($since | fromdateiso8601))]")],
     [case_e10_stamped_exactly_since_is_not_new]),
    ("the token read with export's status",
     [(TOKEN_BLOCK, 'export GH_TOKEN=$(cat "$TOKEN_FILE" 2>/dev/null)\n')],
     [case_c1_token_file_missing]),
    ("without the jq check", [("command -v jq >/dev/null 2>&1 ||", "true ||")],
     [case_d1_jq_absent]),
    ("without the expected-sha checks",
     [('*[!0-9a-f]*|"") cannot', '*[!0-9a-f]*|"") :'), ("[ ${#EXPECTED} -eq 40 ] ||", "true ||")],
     [case_d2_abbreviated_expected, case_d3_expected_not_hex]),
    ("without the head check", [('[ "$head" = "$EXPECTED" ] ||', "true ||")],
     [case_e2_head_moved]),
    ("without the pin-is-head check", [('[ "$approved_sha" = "$head" ] ||', "true ||")],
     [case_e3_approval_covers_another_commit]),
]


def case_name_of(function):
    for name, candidate in CASES:
        if candidate is function:
            return name
    raise SystemExit(f"merge-gate-test: mutation names an unlisted case {function.__name__}")


def run_mutations():
    source = GATE.read_text()
    for mutation_name, replacements, targets in MUTATIONS:
        mutated = source
        applied = True
        for old, new in replacements:
            if mutated.count(old) < 1:
                applied = False
                check(f"mutation '{mutation_name}' applied", False,
                      f"replacement text not found in merge-gate.sh: {old!r}")
                break
            mutated = mutated.replace(old, new)
        if not applied:
            continue
        mutated_gate = Path(tempfile.mkdtemp(dir=scratch)) / "merge-gate.sh"
        mutated_gate.write_text(mutated)
        for target in targets:
            ok, detail = target(mutated_gate)
            check(f"mutation '{mutation_name}' turns red: {case_name_of(target)}", not ok,
                  f"the case still passed against the mutated gate: {detail}")


def run_cases(gate, label):
    passed = 0
    for name, function in CASES:
        ok, detail = function(gate)
        check(f"{label}{name}", ok, detail)
        passed += ok
    return passed


def main():
    if BASH is None:
        raise SystemExit("merge-gate-test: bash is not on PATH")
    check_every_fixture_has_a_capture_record()
    check("the CLEAN spelling came from a capture", CLEAN == "CLEAN", f"read {CLEAN!r}")
    first = run_cases(GATE, "")
    run_mutations()
    # The control: an unmutated copy, run after every mutation.
    control_gate = Path(tempfile.mkdtemp(dir=scratch)) / "merge-gate.sh"
    shutil.copyfile(GATE, control_gate)
    control = run_cases(control_gate, "control after mutations: ")
    print(f"\n{first} of {len(CASES)} cases passed; the unmutated control after the "
          f"mutations passed {control} of {len(CASES)}")
    shutil.rmtree(scratch, ignore_errors=True)
    if failures:
        print(f"\n{len(failures)} check(s) failed:")
        for name in failures:
            print(f"  {name}")
        sys.exit(1)
    print("\nall cases passed")


if __name__ == "__main__":
    main()
