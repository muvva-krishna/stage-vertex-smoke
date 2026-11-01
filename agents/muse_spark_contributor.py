"""One-shot JSON-patch adapter locked to the requested contributor model."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from debev.runners import AgentRunner, AttemptContext, AttemptResult  # noqa: E402
from debev.toolkit import Toolkit  # noqa: E402
from debev.trajectory import TrajectoryRecorder  # noqa: E402


MODEL_ID = "opencode-go/muse-spark-1.3-contributor"
MUTABLE_PREFIX = "debev_config/"


def _extract_json(text: str) -> dict:
    """Accept a JSON object, optionally wrapped in a markdown fence."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3].rstrip()
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char == "{":
            try:
                value, _end = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
    raise ValueError("contributor model did not return a JSON object")


class MuseSparkContributorRunner(AgentRunner):
    """Ask only Muse Spark 1.3 Contributor for one patch, then run public tests."""

    def run(self, ctx: AttemptContext, recorder: TrajectoryRecorder) -> AttemptResult:
        if ctx.task_id != "migration-resume":
            raise ValueError("MuseSparkContributorRunner is configured for migration-resume only")
        binary = shutil.which("opencode")
        if not binary:
            raise RuntimeError("opencode CLI was not found; no fallback model is permitted")

        source_files = {}
        for path in sorted((ctx.workspace_dir / "debev_config").glob("*.py")):
            source_files[str(path.relative_to(ctx.workspace_dir))] = path.read_text(encoding="utf-8")
        prompt = {
            "task": (ctx.workspace_dir / "TASK_INSTRUCTIONS.md").read_text(encoding="utf-8"),
            "evidence": ctx.evidence.artifacts,
            "source_files": source_files,
            "request": (
                "Repair this task using the supplied evidence and source only. "
                "Do not use tools, do not ask questions, and do not modify tests. "
                "Return exactly one JSON object with keys: diagnosis (one short sentence), "
                "files (object mapping changed relative source paths to complete replacement "
                "file contents), and verification (one short factual sentence). "
                "Only return files under debev_config/. Do not include private reasoning."
            ),
        }
        message = json.dumps(prompt, ensure_ascii=False)
        safe_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", ""),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "TMPDIR"):
            if os.environ.get(name):
                safe_env[name] = os.environ[name]
        command = [
            binary, "run", "--model", MODEL_ID, "--agent", "muse-patch",
            "--title", f"debev-{ctx.run_id}", message,
        ]
        recorder.record("agent_note", {"kind":"model_selection", "model":MODEL_ID,
                                         "agent":"muse-patch", "tools_enabled":False})
        recorder.record("command", {"cmd":f"opencode run --model {MODEL_ID} --agent muse-patch",
                                     "rc":None, "isolation":"OpenCode agent denies all tools"})
        proc = subprocess.run(
            command, cwd=ctx.workspace_dir, env=safe_env,
            capture_output=True, text=True,
            timeout=int(ctx.limits.get("max_wall_seconds", 900)),
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout)[-2000:]
            recorder.record("agent_note", {"kind":"model_error", "text":detail})
            raise RuntimeError(f"{MODEL_ID} request failed (no model fallback): {detail}")
        raw_path = ctx.workspace_dir.parent / "model_response_raw.txt"
        raw_path.write_text(proc.stdout, encoding="utf-8")
        answer = _extract_json(proc.stdout)
        response_path = ctx.workspace_dir.parent / "model_response.json"
        response_path.write_text(json.dumps(answer, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
        files = answer.get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError(
                f"{MODEL_ID} response had no patch files; raw response saved to {raw_path}"
            )
        tk = Toolkit(ctx, recorder)
        for relpath, content in files.items():
            if (not isinstance(relpath, str) or not relpath.startswith(MUTABLE_PREFIX)
                    or ".." in Path(relpath).parts or not relpath.endswith(".py")
                    or not isinstance(content, str)):
                raise ValueError(f"model returned a disallowed file path: {relpath!r}")
            tk.write(relpath, content)

        public_result = tk.test(
            "public-unittest-suite",
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            timeout=int(ctx.limits.get("max_wall_seconds", 900)),
        )
        verification = (f"public unittest suite: {public_result}; hidden oracle is separate.")
        recorder.record("agent_note", {"kind":"model_answer", "diagnosis":str(answer.get("diagnosis", ""))[:400],
                                         "verification":str(answer.get("verification", ""))[:300],
                                         "public_tests":public_result})
        return AttemptResult(
            diagnosis=str(answer.get("diagnosis", ""))[:1000],
            verification_summary=verification,
        )
