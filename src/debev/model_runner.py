"""Shared model-backed AgentRunner: one tool loop for both model tiers.

Both configured models run through THIS loop and the same
debev.toolkit interface, so the model — not the harness — is the
experimental variable. Comparing two different agent stacks would
confound model with harness and is out of scope.

Transport is either OpenAI-compatible chat-completions or Google Vertex
AI generateContent, both over stdlib urllib (no third-party deps).
Credentials are ADC access tokens minted at call time (plan names nothing
secret: project/location live in the plan, the token never does) or
environment keys for OpenAI-compatible endpoints, and are NEVER written
to trajectories, metadata, logs, or files. Task subprocesses get the
scrubbed environment, which excludes credentials by allowlist.

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
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .runners import AttemptContext, AttemptResult, AgentRunner
from .toolkit import Toolkit
from .trajectory import TrajectoryRecorder

MAX_ACTIONS_PER_TURN = 10

SYSTEM_TEMPLATE = """You are a code-repair agent in a controlled evaluation. Work ONLY through the actions below; reply with a single JSON object of the form {"actions": [{"op": "<op-name>", "...": "..."}]} and nothing else.
First list the workspace files (exec ls), then read the task instructions and evidence before editing anything.
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
Rules: never ask for secrets, keys, or credentials; never emit them; never reference files outside the workspace; verify with test ops before finish.
Workflow: make progress every turn — inspect files, reproduce the failure with a test op, edit the code, re-test, then finish. Do not repeat a command that already succeeded; do not re-read files you already have. You have a small fixed number of turns (stated each turn); spend your last turns on finish with a diagnosis and verification summary, even if the fix is incomplete.
Grounding rules: before any write, read every source file in the workspace so your edit addresses the actual code — never invent filenames, functions, or data files, and never create files unrelated to the task. Run every check with the test op (which records PASS/FAIL); bare exec is for inspection only and never counts as verification. Your final diagnosis must name the actual files and functions you changed and observed."""


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


_ADC_TOKEN: dict = {"token": "", "expires_at": 0.0}


def _vertex_host(location: str) -> str:
    if location == "global":
        return "aiplatform.googleapis.com"
    if location in ("us", "eu"):
        return f"aiplatform.{location}.rep.googleapis.com"
    return f"{location}-aiplatform.googleapis.com"


def adc_access_token() -> str:
    """Mint an ADC access token, caching in process memory only.

    Prefers the gcloud CLI (same pattern as the reference repo); falls
    back to an OAuth2 refresh against the ADC file. The token is never
    printed, logged, or stored outside this process.
    """
    now = time.time()
    if _ADC_TOKEN["token"] and now < _ADC_TOKEN["expires_at"] - 60:
        return _ADC_TOKEN["token"]
    adc_file = Path(os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS",
        str(Path.home() / ".config" / "gcloud" / "application_default_credentials.json")))
    if adc_file.is_file():
        try:
            creds = json.loads(adc_file.read_text())
            if all(k in creds for k in ("client_id", "client_secret", "refresh_token")):
                import urllib.parse
                payload = urllib.parse.urlencode({
                    "client_id": creds["client_id"],
                    "client_secret": creds["client_secret"],
                    "refresh_token": creds["refresh_token"],
                    "grant_type": "refresh_token"}).encode()
                req = urllib.request.Request(
                    "https://oauth2.googleapis.com/token", data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    tok_data = json.load(resp)
                tok = tok_data.get("access_token", "").strip()
                if tok:
                    _ADC_TOKEN.update({"token": tok,
                                       "expires_at": now + int(tok_data.get("expires_in", 3500))})
                    return tok
        except Exception:
            pass
    gcloud = os.getenv("GCLOUD_BIN", "")
    if not gcloud:
        home_gcloud = Path.home() / "google-cloud-sdk" / "bin" / "gcloud"
        gcloud = str(home_gcloud) if home_gcloud.exists() else "gcloud"
    tok = subprocess.check_output(
        [gcloud, "auth", "application-default", "print-access-token"],
        text=True, timeout=60).strip()
    if not tok:
        raise RuntimeError("ADC token minting returned empty output")
    _ADC_TOKEN.update({"token": tok, "expires_at": now + 3000})
    return tok


class VertexTransport:
    """Google Vertex AI generateContent via ADC (no API keys anywhere).

    Plan provider block: {kind: "vertex-ai", project, location}.
    Maps system+turns to systemInstruction/contents and usageMetadata to
    {input_tokens, output_tokens}. Errors never include the token.
    """

    def __init__(self, project: str, location: str, model: str,
                 temperature: float = 0.0, timeout: int = 180):
        self.project = project
        self.location = location
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

    def _url(self) -> str:
        return (f"https://{_vertex_host(self.location)}/v1/projects/{self.project}"
                f"/locations/{self.location}/publishers/google/models/"
                f"{self.model}:generateContent")

    def complete(self, messages: list[dict]) -> tuple[str, dict]:
        system = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
        contents = [{"role": ("model" if m.get("role") == "assistant" else "user"),
                     "parts": [{"text": m.get("content", "")}]}
                    for m in messages if m.get("role") in ("user", "assistant")]
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": contents,
                "generationConfig": {"temperature": self.temperature,
                                     "responseMimeType": "application/json"}}
        try:
            token = adc_access_token()
        except Exception as e:
            raise RuntimeError(f"ADC unavailable: {type(e).__name__}") from None
        req = urllib.request.Request(
            self._url(), data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + token}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
        except Exception as e:
            raise RuntimeError(
                f"Vertex call failed ({type(e).__name__}): {str(e)[:200]}") from None
        try:
            parts = payload["candidates"][0]["content"].get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            usage = payload.get("usageMetadata", {}) or {}
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"Vertex response unparseable: {type(e).__name__}") from None
        return text, {"input_tokens": int(usage.get("promptTokenCount", 0)),
                      "output_tokens": int(usage.get("candidatesTokenCount", 0))}


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


def _first_user_message(ctx: AttemptContext) -> str:
    """Ground the first turn: file listing + instructions inline so the
    model starts from the actual task instead of guessing filenames."""
    try:
        files = sorted(str(p.relative_to(ctx.workspace_dir))
                       for p in ctx.workspace_dir.rglob("*") if p.is_file())
    except OSError:
        files = []
    instr = ""
    try:
        instr = (ctx.workspace_dir / "TASK_INSTRUCTIONS.md").read_text(
            encoding="utf-8", errors="replace")[:4000]
    except OSError:
        pass
    return ("Begin. Reply with JSON actions only.\n"
            f"Workspace files:\n" + "\n".join(f"- {f}" for f in files[:50]) +
            f"\n\nTask instructions:\n{instr}")


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
        evidence_files = sorted(f"evidence/{n}" for n in ctx.evidence.artifacts.keys())
        system = _system_prompt(
            ".", evidence_files, list(ctx.allowed_tools),
            (ctx.limits or {}).get("max_tool_calls", "?"),
            (ctx.limits or {}).get("max_wall_seconds", "?"))
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": _first_user_message(ctx)}]
        diagnosis, verification_summary = "", ""
        max_turns = max(1, self.max_turns)
        for turn in range(max_turns):
            try:
                text, usage = self.transport.complete(messages)
            except Exception as e:  # noqa: BLE001 — fail closed, score as-is
                recorder.record("agent_note", {"kind": "error",
                    "text": f"provider call failed: {type(e).__name__}"[:300]})
                break
            self.usage["input_tokens"] += usage.get("input_tokens", 0)
            self.usage["output_tokens"] += usage.get("output_tokens", 0)
            self.usage["calls"] += 1
            recorder.record("model_reply", {"chars": len(text),
                                            "text": text[:2000]})
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
                except (ValueError, PermissionError, KeyError, OSError) as e:
                    recorder.record("agent_note", {"kind": "error",
                        "text": f"rejected action: {e}"[:300]})
                    break
                if isinstance(outcome, tuple):
                    diagnosis, verification_summary, finished = outcome
                    break
            messages.append({"role": "user",
                             "content": f"Continue (turn {turn + 2} of {max_turns}). "
                                        "Reply with JSON actions only; if done, finish."})
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
