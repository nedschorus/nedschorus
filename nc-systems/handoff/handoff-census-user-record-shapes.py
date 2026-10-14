#!/usr/bin/env python3
"""Count transcript user-record shapes to identify injected content."""
import importlib.util
import json, sys, re
from pathlib import Path
from collections import Counter, defaultdict

# The extractor stays in scripts/ until all live supervisors run from nc-systems/handoff/.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "handoff_extract_conversation",
    REPOSITORY_ROOT / "scripts" / "handoff-extract-conversation.py")
_extractor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_extractor)

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
                    # Bracketed injected records can otherwise disappear into typed-dialog.
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
