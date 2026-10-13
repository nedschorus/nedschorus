#!/usr/bin/env python3
"""The subagent tracker: turn a session's records into the subagent turns its complete dialog carries.

Nice-but-dirty: scripts/handoff-extract-conversation.py loads this file only
when a caller asks for subagent turns, and when loading it or running it
fails, the extractor leaves the subagent turns out and says so in the
dialog, so a fault here never stops a handoff. Not a program to run; the
extractor is its only caller.

For each subagent the session dispatched, a turn carries what it was asked
and what it reported, never its own records. The asks are the Agent
(formerly Task) tool's prompt, a Workflow tool's script, a skill the Skill
tool ran as a fork, and a SendMessage to a subagent already dispatched. The
reports arrive in four shapes, each copied up to four times into the
transcript, and each is carried once: a foreground agent's tool result; a
<task-notification> naming an agent or a workflow, with its <result>; an
<agent-message> hand-back (the SubagentHandback tool), whose report the
harness frames and indents; and an <agent-message> a running subagent sent
its session. A launch notice is dropped, and so is a notification whose
result only says the report came as a hand-back or will come later. The
copies of one report are carried once; a report repeated after a SendMessage
to the same subagent is a new report, carried again.
"""

import json
import re

# The extractor's name for the third voice; the extractor checks at load time that both files agree.
SUBAGENT_VOICE = "subagent"
SUBAGENT_DISPATCH_TOOL_NAMES = ("Agent", "Task")
# Notifications for subagents dispatched by a previous session match no dispatch in this transcript.
SUBAGENT_NOTIFICATION_SUMMARY_PREFIXES = ('Agent "', 'Background agent "', 'Dynamic workflow "')
HANDBACK_FRAME_OPENING = "[Subagent hand-back]"
HANDBACK_FRAME_END = "The report follows:"
REPORT_SENT_AS_HANDBACK_PREFIX = "This agent's report was delivered to you as a message"
# A notification sent while a subagent waits on its own background work; its report comes later.
REPORT_NOT_YET_SENT_PREFIX = "This agent has not reported yet"
RESULTS_THAT_ARE_NOT_REPORTS = (REPORT_SENT_AS_HANDBACK_PREFIX, REPORT_NOT_YET_SENT_PREFIX)
LAUNCH_NOTICE_PREFIXES = ("Async agent launched", "Workflow launched")


def notification_tag(body: str, tag: str) -> str:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", body, re.S)
    return match.group(1).strip() if match else ""


def texts_a_report_can_arrive_in(record):
    """Yield every harness text in the record that can carry a notification or an agent-message."""
    record_type = record.get("type")
    if record_type == "queue-operation":
        if isinstance(record.get("content"), str):
            yield record["content"]
    elif record_type == "attachment":
        attachment = record.get("attachment")
        if (isinstance(attachment, dict) and attachment.get("type") == "queued_command"
                and isinstance(attachment.get("prompt"), str)):
            yield attachment["prompt"]
    elif record_type == "user":
        content = (record.get("message") or {}).get("content")
        if isinstance(content, str):
            yield content
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    yield block.get("text", "")


def handback_report_text(framed: str) -> str:
    """Return the report inside a hand-back frame: the indented lines after the frame, unindented."""
    _, found, after = framed.partition(HANDBACK_FRAME_END)
    if not found:
        return framed.strip()
    # The harness indents every report line by two spaces.
    return "\n".join(line[2:] if line.startswith("  ") else line
                     for line in after.lstrip("\n").split("\n")).strip()


def tool_result_text(block) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            part.get("text", "") for part in content
            if isinstance(part, dict) and part.get("type") == "text"
            # The harness appends the agent id and token usage as a block of its own.
            and not part.get("text", "").lstrip().startswith("agentId:"))
    return ""


class SubagentTracker:
    """Turn a session's records into the subagent turns its dialog carries.

    Each turn returned has voice SUBAGENT_VOICE, text, kind ("task", "follow-up",
    "report" or "message"), and "subagent": a dict shared by every turn of one
    subagent, which later records fill in, holding "description", "agent_id",
    "details" (type, model, background, isolation). A report turn also holds "status".
    """

    def __init__(self):
        self.subagent_by_tool_use_id = {}
        self.subagent_by_agent_id = {}
        self.skill_by_tool_use_id = {}
        self.carried_report_keys = set()
        self.follow_ups_sent_by_agent_id = {}
        self.deliveries_by_block = {}

    def subagent_for_agent_id(self, agent_id: str) -> dict:
        subagent = self.subagent_by_agent_id.get(agent_id)
        if subagent is None:
            subagent = {"agent_id": agent_id, "description": "", "details": []}
            self.subagent_by_agent_id[agent_id] = subagent
        return subagent

    def turns_from_record(self, record):
        """Return (new subagent turns, whether the record carried a subagent report at all)."""
        if not isinstance(record, dict):
            return [], False
        turns = []
        carried_report = False
        content = (record.get("message") or {}).get("content")
        if record.get("type") == "assistant" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    turns += self.turns_from_tool_use(block)
        if record.get("type") == "user" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    block_turns, block_carried = self.turns_from_tool_result(block, record)
                    turns += block_turns
                    carried_report = carried_report or block_carried
        for text in texts_a_report_can_arrive_in(record):
            text_turns, text_carried = self.turns_from_harness_text(text, record)
            turns += text_turns
            carried_report = carried_report or text_carried
        return turns, carried_report

    def turns_from_tool_use(self, block):
        name = block.get("name")
        tool_input = block.get("input") if isinstance(block.get("input"), dict) else {}
        tool_use_id = block.get("id") or ""
        if name in SUBAGENT_DISPATCH_TOOL_NAMES:
            details = [str(tool_input[key]) for key in ("subagent_type", "model") if tool_input.get(key)]
            if tool_input.get("run_in_background") in (True, "true"):
                details.append("background")
            if tool_input.get("isolation"):
                details.append(f"isolation {tool_input['isolation']}")
            subagent = {"agent_id": "", "description": str(tool_input.get("description") or ""),
                        "details": details}
            self.subagent_by_tool_use_id[tool_use_id] = subagent
            prompt = tool_input.get("prompt")
            return [self.turn(subagent, "task", prompt if isinstance(prompt, str) else "")]
        if name == "Workflow":
            script = tool_input.get("script") or tool_input.get("scriptPath") or ""
            # The launch result names the workflow; a launch that was refused leaves only the script's meta.
            described = re.search(r"""description:\s*(['"])(.*?)\1""", script) if isinstance(script, str) else None
            subagent = {"agent_id": "", "description": described.group(2) if described else "",
                        "details": ["workflow"]}
            self.subagent_by_tool_use_id[tool_use_id] = subagent
            return [self.turn(subagent, "task", script if isinstance(script, str) else "")]
        if name == "Skill":
            self.skill_by_tool_use_id[tool_use_id] = tool_input
            return []
        if name == "SendMessage":
            recipient = tool_input.get("to") or tool_input.get("recipient")
            message = tool_input.get("message")
            if not isinstance(message, str):
                message = tool_input.get("content")
            if recipient in self.subagent_by_agent_id and isinstance(message, str):
                self.follow_ups_sent_by_agent_id[recipient] = self.follow_ups_sent_by_agent_id.get(recipient, 0) + 1
                return [self.turn(self.subagent_by_agent_id[recipient], "follow-up", message)]
        return []

    def turns_from_tool_result(self, block, record):
        tool_use_id = block.get("tool_use_id") or ""
        result = record.get("toolUseResult") if isinstance(record.get("toolUseResult"), dict) else {}
        if tool_use_id in self.skill_by_tool_use_id and result.get("status") == "forked":
            skill_input = self.skill_by_tool_use_id.pop(tool_use_id)
            subagent = self.subagent_for_agent_id(str(result.get("agentId") or ""))
            subagent["description"] = f"/{result.get('commandName') or skill_input.get('skill', '')}"
            subagent["details"] = ["forked skill"]
            arguments = skill_input.get("args")
            return [self.turn(subagent, "task", arguments if isinstance(arguments, str) else "")], False
        subagent = self.subagent_by_tool_use_id.get(tool_use_id)
        if subagent is None:
            return [], False
        text = tool_result_text(block)
        agent_id = result.get("agentId") or result.get("taskId")
        if not agent_id:
            found = re.search(r"agentId: (\w+)", json.dumps(block.get("content")))
            agent_id = found.group(1) if found else ""
        if agent_id:
            agent_id = str(agent_id)
            subagent["agent_id"] = agent_id
            # A foreground hand-back reaches the transcript before the tool result that names its agent.
            earlier = self.subagent_by_agent_id.setdefault(agent_id, subagent)
            if earlier is not subagent:
                earlier["description"] = earlier["description"] or subagent["description"]
                earlier["details"] = earlier["details"] or subagent["details"]
        if result.get("workflowName") or result.get("runId"):
            subagent["description"] = str(result.get("summary") or result.get("workflowName") or "")
        if block.get("is_error"):
            return [self.turn(subagent, "report", text, status="error")], True
        status = result.get("status") or ""
        if status == "async_launched" or text.lstrip().startswith(LAUNCH_NOTICE_PREFIXES):
            return [], False
        handback = result.get("handbackReport")
        if isinstance(handback, dict) and isinstance(handback.get("text"), str):
            text = handback["text"]
        elif isinstance(result.get("content"), list):
            text = tool_result_text({"content": result["content"]})
        return self.report_turns(subagent, text, status or "completed"), True

    def follow_ups_when_enqueued(self, block: str, record) -> dict:
        """Return the follow-up counts as they stood when the delivery this copy of block belongs to was enqueued.

        The harness writes one delivery as an enqueue, then as a remove, a queued_command attachment or a
        user record, and those later copies can land after a SendMessage to the same agent. The queue drains
        in order and writes each kind of copy once per enqueue, so each later copy is matched to the oldest
        enqueue of the same block that has no copy of its kind yet. A copy with no enqueue left to match
        counts as a delivery of its own.
        """
        deliveries = self.deliveries_by_block.setdefault(block, [])
        record_type = record.get("type")
        if record_type == "queue-operation" and record.get("operation") == "enqueue":
            deliveries.append({"copies": set(), "follow_ups": dict(self.follow_ups_sent_by_agent_id)})
            return deliveries[-1]["follow_ups"]
        copy_kind = record.get("operation") if record_type == "queue-operation" else record_type
        unmatched = [delivery for delivery in deliveries if copy_kind not in delivery["copies"]]
        if not unmatched:
            return self.follow_ups_sent_by_agent_id
        unmatched[0]["copies"].add(copy_kind)
        return unmatched[0]["follow_ups"]

    def turns_from_harness_text(self, text: str, record):
        turns = []
        carried_report = False
        for match in re.finditer(r"<task-notification>(.*?)</task-notification>", text, re.S):
            body = match.group(1)
            follow_ups = self.follow_ups_when_enqueued(match.group(0), record)
            summary = notification_tag(body, "summary")
            task_ids = re.findall(r"<task-id>(.*?)</task-id>", body, re.S)
            tool_use_id = notification_tag(body, "tool-use-id")
            subagent = self.subagent_by_tool_use_id.get(tool_use_id)
            if subagent is None:
                subagent = next((self.subagent_by_agent_id[task_id.strip()] for task_id in task_ids
                                 if task_id.strip() in self.subagent_by_agent_id), None)
            if subagent is None and summary.startswith(SUBAGENT_NOTIFICATION_SUMMARY_PREFIXES):
                subagent = self.subagent_for_agent_id(task_ids[0].strip() if task_ids else "")
            if subagent is None:
                continue
            if not subagent["description"]:
                quoted = re.search(r'"(.*)"', summary)
                subagent["description"] = quoted.group(1) if quoted else summary
            carried_report = True
            report = notification_tag(body, "result")
            if report.startswith(RESULTS_THAT_ARE_NOT_REPORTS):
                continue
            status = notification_tag(body, "status") or "completed"
            report = report or summary
            if "workflow" in subagent["details"] and report.startswith('"'):
                # A workflow's result is its script's return value, written as JSON.
                try:
                    decoded = json.loads(report)
                except json.JSONDecodeError:
                    decoded = None
                if isinstance(decoded, str):
                    report = decoded
            turns += self.report_turns(subagent, report, status, follow_ups)
        if "<agent-message" in text:
            origin = record.get("origin") if isinstance(record.get("origin"), dict) else {}
            for match in re.finditer(r'<agent-message from="([^"]*)">\n?(.*?)(?:</agent-message>|\Z)', text, re.S):
                sender, body = match.group(1), match.group(2)
                if origin.get("from") == sender and isinstance(origin.get("body"), str):
                    body = origin["body"]
                # A user record's copy runs on past the message, so the block is the sender and body alone.
                follow_ups = self.follow_ups_when_enqueued(f"{sender}\n{body.strip()}", record)
                if body.lstrip().startswith(HANDBACK_FRAME_OPENING):
                    carried_report = True
                    turns += self.report_turns(self.subagent_for_agent_id(sender),
                                               handback_report_text(body), "completed", follow_ups)
                elif sender in self.subagent_by_agent_id:
                    carried_report = True
                    turns += self.report_turns(self.subagent_by_agent_id[sender], body.strip(),
                                               "", follow_ups, kind="message")
        return turns, carried_report

    def report_turns(self, subagent, text: str, status: str, follow_ups=None, kind="report"):
        """Return the report as a turn, or no turn when an earlier copy of the same delivery was carried.

        follow_ups is the follow-up counts as they stood when the delivery was enqueued; by default, now.
        """
        agent_id = subagent.get("agent_id")
        # The harness copies one delivery up to four times; a SendMessage starts a new delivery.
        follow_ups = self.follow_ups_sent_by_agent_id if follow_ups is None else follow_ups
        key = (agent_id or id(subagent), follow_ups.get(agent_id, 0),
               kind, " ".join(text.split()), status)
        if key in self.carried_report_keys:
            return []
        self.carried_report_keys.add(key)
        return [self.turn(subagent, kind, text, status=status)]

    @staticmethod
    def turn(subagent, kind, text, status=""):
        return {"voice": SUBAGENT_VOICE, "kind": kind, "text": text.strip(),
                "subagent": subagent, "status": status}
