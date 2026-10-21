"""Shared model-backed AgentRunner: one tool loop for both model tiers.

Both configured models run through THIS loop and the same
debev.toolkit interface, so the model — not the harness — is the
experimental variable. Comparing two different agent stacks would
confound model with harness and is out of scope.

Transport is a minimal OpenAI-compatible chat-completions POST over
stdlib urllib (no third-party deps). Credentials are read from the
environment at call time (plan names the variable via
model.provider.env_key) and are NEVER written to trajectories, metadata,
logs, or files. Task subprocesses get the scrubbed environment, which
excludes credentials by allowlist.

The model may only act through toolkit ops dispatched here (read/write/
exec/test/verify/note/finish). Replies must be a single JSON object
{"actions": [...]}; anything else ends the attempt (fail closed). Shell
commands are always argv lists via the toolkit — shell=True is never
used anywhere on this path.

No paid calls happen in tests or dry runs: LoopbackBackend serves canned,
explicitly labeled replies for smoke/offline tests.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

from .runners import AttemptContext, AttemptResult, AgentRunner
from .toolkit import Toolkit
from .trajectory import TrajectoryRecorder

MAX_ACTIONS_PER_TURN = 10

SYSTEM_TEMPLATE = """You are a code-repair agent in a controlled evaluation. Work ONLY through the actions below; reply with a single JSON object like {"actions": [{"op": "read", "path": "f.py"}]} and nothing else.
Workspace: $WORKSPACE (all paths relative to it). Task instructions: TASK_INSTRUCTIONS.md. Evidence for this condition: $EVIDENCE_FILES.
Allowed tools: $ALLOWED_TOOLS. Tool budget: $MAX_TOOLS calls; wall budget: $MAX_WALL_S seconds.
Ops:
- {"op": "read", "path": "<rel>"} read a workspace file
- {"op": "write", "path": "<rel>", "content": "<full text>"} overwrite/create a workspace file
- {"op": "exec", "cmd": ["prog", "arg"]} run a command (argv list, no shell)
- {"op": "test", "name": "<label>", "cmd": ["prog", "arg"]} run a check; result recorded PASS/FAIL/INCONCLUSIVE
- {"op": "verify", "name": "<label>", "result": "PASS|FAIL|ERROR|INCONCLUSIVE", "detail": "..."} your final verification claim (self-reported; only executed test ops earn machine credit)
- {"op": "note", "kind": "diagnosis", "text": "..."} short user-visible diagnosis (no hidden reasoning)
- {"op": "finish", "diagnosis": "...", "verification_summary": "..."} end the attempt
Rules: never ask for secrets, keys, or credentials; never emit them; never reference files outside the workspace; verify with test ops before finish."""


def _system_prompt(workspace: str, evidence_files: list[str], allowed_tools: list[str],
                   max_tools: object, max_wall_s: object) -> str:
    out = SYSTEM_TEMPLATE
    for key, val in (("$WORKSPACE", workspace),
                     ("$EVIDENCE_FILES", ", ".join(evidence_files)),
                     ("$ALLOWED_TOOLS", ", ".join(allowed_tools)),
                     ("$MAX_TOOLS", str(max_tools)),
                     ("$MAX_WALL_S", str(max_wall_s))):
        out = out.replace(key, val)
    return out


class Transport(Protocol):
    def complete(self, messages: list[dict]) -> tuple[str, dict]:
        """Return (reply_text, usage{input_tokens, output_tokens})."""
        ...


class OpenAICompatibleTransport:
    def __init__(self, base_url: str, model: str, env_key: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.env_key = env_key
        self.timeout = timeout

    def _key(self) -> str:
        key = os.environ.get(self.env_key, "")
        if not key:
            raise RuntimeError(
                f"credential env var {self.env_key!r} is not set; "
                "provide credentials through the environment, never in the repo")
        return key

    def complete(self, messages: list[dict]) -> tuple[str, dict]:
        payload = json.dumps({"model": self.model, "messages": messages}).encode()
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + self._key()},
            method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode())
        choice = body["choices"][0]["message"]["content"] or ""
        usage = body.get("usage", {}) or {}
        return choice, {"input_tokens": int(usage.get("prompt_tokens", 0)),
                        "output_tokens": int(usage.get("completion_tokens", 0))}


class LoopbackTransport:
    """Offline stand-in: serves canned replies, labels everything loopback.

    For smoke tests of the loop/toolkit boundary only. Produces no model
    output and must never be presented as a model result.
    """

    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.calls = 0

    def complete(self, messages: list[dict]) -> tuple[str, dict]:
        if self.calls >= len(self.replies):
            return json.dumps({"actions": [
                {"op": "finish", "diagnosis": "loopback script exhausted (plumbing-only)",
                 "verification_summary": "loopback (plumbing-only)"}]}), \
                {"input_tokens": 0, "output_tokens": 0}
        text = self.replies[self.calls]
        self.calls += 1
        return text, {"input_tokens": 10, "output_tokens": 10}


def _parse_actions(text: str) -> list[dict]:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if "\n" in t:
            first, _, rest = t.partition("\n")
            if first.strip().lower() in ("json", "jsonc"):
                t = rest
    obj = json.loads(t)
    actions = obj.get("actions")
    if not isinstance(actions, list):
        raise ValueError("reply must be {\"actions\": [...]}")
    return actions


@dataclass
class ModelAgentRunner(AgentRunner):
    """One shared loop; constructed per plan model entry (frozen)."""

    model_id: str
    model_version: str
    temperature: float = 0.0
    settings: dict = field(default_factory=dict)
    transport: Transport | None = None
    max_turns: int = 20

    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "calls": 0})

    def _check_frozen(self, expected_id: str, expected_version: str) -> None:
        if self.model_id != expected_id or self.model_version != expected_version:
            raise ValueError(
                f"model freeze violation: runner has {self.model_id}@{self.model_version} "
                f"but cell requires {expected_id}@{expected_version}; refusing to substitute")

    def run(self, ctx: AttemptContext, recorder: TrajectoryRecorder) -> AttemptResult:
        from .toolkit import ToolBudgetExceeded

        if self.transport is None:
            raise RuntimeError("ModelAgentRunner has no transport configured")
        tk = Toolkit(ctx, recorder)
        evidence_files = sorted(ctx.evidence.artifacts.keys())
        system = _system_prompt(
            ".", evidence_files, list(ctx.allowed_tools),
            (ctx.limits or {}).get("max_tool_calls", "?"),
            (ctx.limits or {}).get("max_wall_seconds", "?"))
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": "Begin. Reply with JSON actions only."}]
        diagnosis, verification_summary = "", ""
        for _turn in range(max(1, self.max_turns)):
            try:
                text, usage = self.transport.complete(messages)
            except Exception as e:  # noqa: BLE001 — fail closed, score as-is
                recorder.record("agent_note", {"kind": "error",
                    "text": f"provider call failed: {type(e).__name__}"[:300]})
                break
            self.usage["input_tokens"] += usage.get("input_tokens", 0)
            self.usage["output_tokens"] += usage.get("output_tokens", 0)
            self.usage["calls"] += 1
            messages.append({"role": "assistant", "content": text})
            try:
                actions = _parse_actions(text)
            except (ValueError, json.JSONDecodeError):
                recorder.record("agent_note", {"kind": "error",
                    "text": "unparsable model reply; ending attempt (fail closed)"})
                break
            finished = False
            for action in actions[:MAX_ACTIONS_PER_TURN]:
                try:
                    outcome = self._dispatch(tk, action)
                except ToolBudgetExceeded:
                    raise
                except (ValueError, PermissionError, KeyError) as e:
                    recorder.record("agent_note", {"kind": "error",
                        "text": f"rejected action: {e}"[:300]})
                    done, finished = False, True
                    break
                if isinstance(outcome, tuple):
                    diagnosis, verification_summary, finished = outcome
                    break
            messages.append({"role": "user", "content": "Continue. Reply with JSON actions only."})
            if finished:
                break
        return AttemptResult(diagnosis=diagnosis or "no diagnosis reported",
                             verification_summary=verification_summary or "no verification reported",
                             provider_usage=dict(self.usage))

    def _dispatch(self, tk: Toolkit, action: dict):
        """Execute one model action via the toolkit. Returns 'finish',
        (diagnosis, summary, True), False to continue, and raises on budget."""
        if not isinstance(action, dict):
            raise ValueError("action must be an object")
        op = action.get("op")
        if op == "read":
            tk.read(str(action["path"]))
        elif op == "write":
            content = action.get("content")
            if not isinstance(content, str):
                raise ValueError("write needs string content")
            tk.write(str(action["path"]), content)
        elif op == "exec":
            cmd = action.get("cmd")
            self._check_cmd(cmd)
            tk.exec([str(c) for c in cmd])
        elif op == "test":
            cmd = action.get("cmd")
            self._check_cmd(cmd)
            tk.test(str(action.get("name", "model-check")), [str(c) for c in cmd])
        elif op == "verify":
            tk.verify(str(action.get("name", "model-claim")),
                      str(action["result"]), str(action.get("detail", "")))
        elif op == "note":
            if action.get("kind") != "diagnosis":
                raise ValueError("note kind must be 'diagnosis'")
            tk.recorder.record("agent_note", {"kind": "diagnosis",
                                              "text": str(action.get("text", ""))[:2000]})
        elif op == "finish":
            return (str(action.get("diagnosis", "")),
                    str(action.get("verification_summary", "")), True)
        else:
            raise ValueError(f"unknown op {op!r}")
        return False

    @staticmethod
    def _check_cmd(cmd: Any) -> None:
        if not isinstance(cmd, list) or not cmd or not all(isinstance(c, (str, int, float)) for c in cmd):
            raise ValueError("cmd must be a non-empty argv list (no shell strings)")
