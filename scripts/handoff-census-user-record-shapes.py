#!/usr/bin/env python3
"""Census of user-record shapes across every Claude Code session transcript.

The receipt behind handoff-extract-conversation.py's INJECTED_TEXT_PREFIXES
list (2026-08-17: 341 transcripts, both machines — 59% of kept user-record
words were harness-injected). Rerun it when extracts look noisy again: a new
unclassified shape in its output is a new prefix for that list.

The known shapes are IMPORTED from the extractor, never copied (review
finding, 2026-08-17: an out-of-sync copy either false-alarms on shapes the
extractor already drops or silently blesses shapes it keeps). Anything the
extractor drops reports as dropped:<prefix>; the deliberate keeps are the
short KEPT_AS_DIALOG_PREFIXES list here. A shape in neither group is the
signal this census exists to raise. Run it from a checkout — it needs the
extractor beside it.

Walks ~/.claude/projects/*/*.jsonl (or the root given as argv[1]),
classifies every type=="user" record the extractor's pre-prefix filter would
keep (not isMeta, not sidechain, non-empty text), and prints a histogram of
opening shapes plus samples of anything unclassified.
"""
import importlib.util
import json, sys, re
from pathlib import Path
from collections import Counter, defaultdict

_spec = importlib.util.spec_from_file_location(
    "handoff_extract_conversation",
    Path(__file__).with_name("handoff-extract-conversation.py"))
_extractor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_extractor)

# Injected shapes the extractor deliberately KEEPS as dialog.
KEPT_AS_DIALOG_PREFIXES = ("<bash-input>",)

KNOWN_PREFIXES = {
    prefix: "dropped" for prefix in _extractor.INJECTED_TEXT_PREFIXES
}
KNOWN_PREFIXES.update({prefix: "kept" for prefix in KEPT_AS_DIALOG_PREFIXES})

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".claude" / "projects"
shape_counts = Counter()
shape_words = Counter()
per_project = defaultdict(Counter)
unknown_samples = []
files = 0
bad_lines = 0

for jsonl in sorted(root.glob("*/*.jsonl")):
    files += 1
    project = jsonl.parent.name
    try:
        with jsonl.open("rb") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                except Exception:
                    bad_lines += 1
                    continue
                if not isinstance(record, dict) or record.get("type") != "user":
                    continue
                if record.get("isSidechain") or record.get("isMeta"):
                    continue
                content = record.get("message", {}).get("content")
                if isinstance(content, str):
                    text = content.strip()
                elif isinstance(content, list):
                    text = "\n".join(
                        block.get("text", "") for block in content
                        if isinstance(block, dict) and block.get("type") == "text"
                    ).strip()
                else:
                    text = ""
                if not text:
                    continue
                matched = next((p for p in KNOWN_PREFIXES if text.startswith(p)), None)
                shape = f"{KNOWN_PREFIXES[matched]}:{matched}" if matched else None
                if shape is None:
                    # Bracketed openings are sampled too: an injected shape
                    # need not use angle brackets, and one absorbed into
                    # typed-dialog is invisible (review finding, 2026-08-17).
                    if text.startswith("<"):
                        shape = "OTHER-ANGLE:" + re.split(r"[ >\n]", text, maxsplit=1)[0][:40]
                    elif text.startswith("["):
                        shape = "OTHER-BRACKET:" + re.split(r"[\]\n]", text, maxsplit=1)[0][:40]
                    else:
                        shape = "typed-dialog"
                shape_counts[shape] += 1
                shape_words[shape] += len(text.split())
                per_project[project][shape] += 1
                if shape.startswith(("OTHER-ANGLE", "OTHER-BRACKET")) and len(unknown_samples) < 12:
                    unknown_samples.append((project, text[:160].replace("\n", " ")))
    except OSError:
        continue

print(f"files: {files}  bad lines: {bad_lines}")
print(f"{'shape':<42}{'records':>9}{'words':>11}")
for shape, count in shape_counts.most_common():
    print(f"{shape:<42}{count:>9}{shape_words[shape]:>11}")
print("\nprojects with most non-dialog user records:")
def injected_count(counts):
    # kept: shapes are deliberate dialog, not noise (review finding).
    return sum(v for k, v in counts.items()
               if k != "typed-dialog" and not k.startswith("kept:"))


scored = sorted(per_project.items(),
                key=lambda kv: injected_count(kv[1]),
                reverse=True)[:8]
for project, counts in scored:
    noise = injected_count(counts)
    print(f"  {project[:60]:<62} dialog={counts.get('typed-dialog',0):<6} injected={noise}")
if unknown_samples:
    print("\nunclassified angle-bracket samples:")
    for project, sample in unknown_samples:
        print(f"  [{project[:30]}] {sample}")
