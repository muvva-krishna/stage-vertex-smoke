"""Harness smoke checks (stdlib unittest; no external deps, no model APIs)."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from debev.conditions import load_condition  # noqa: E402
from debev.manifest import load_manifest, validate_manifest  # noqa: E402
from debev.report import build_report  # noqa: E402
from debev.rubric import apply_human_grade, score_machine_portion  # noqa: E402
from debev.trajectory import TrajectoryRecorder  # noqa: E402

FIXTURE = ROOT / "fixtures" / "plumbing_fixture"


class TestManifest(unittest.TestCase):
    def test_fixture_manifest_valid(self):
        data = load_manifest(FIXTURE / "manifest.json")
        errors = [i for i in validate_manifest(data) if i.level == "error"]
        self.assertEqual(errors, [])

    def test_banned_keys_rejected(self):
        data = load_manifest(FIXTURE / "manifest.json")
        data["reference_patch"] = "diff --git ..."
        errors = [i for i in validate_manifest(data) if i.level == "error"]
        self.assertTrue(any("reference_patch" in i.message for i in errors))


class TestConditions(unittest.TestCase):
    def test_all_five_conditions_deterministic(self):
        ev = FIXTURE / "evidence"
        first = {c: load_condition(ev, c, 2000).evidence_tokens for c in
                 ("symptom_only", "repro_log", "state_snapshot", "code_note", "combined")}
        second = {c: load_condition(ev, c, 2000).evidence_tokens for c in
                  ("symptom_only", "repro_log", "state_snapshot", "code_note", "combined")}
        self.assertEqual(first, second)
        self.assertLessEqual(first["symptom_only"], first["combined"])
        # no padding: single-artifact conditions are strictly smaller than combined
        self.assertLess(first["repro_log"], first["combined"])

    def test_budget_enforced(self):
        with self.assertRaises(ValueError):
            load_condition(FIXTURE / "evidence", "combined", 1)


class TestTrajectory(unittest.TestCase):
    def test_private_reasoning_refused(self):
        rec = TrajectoryRecorder(run_id="r", task_id="t", condition="symptom_only")
        with self.assertRaises(ValueError):
            rec.record("agent_note", {"chain_of_thought": "secret"})
        rec.record("agent_note", {"kind": "diagnosis", "text": "visible summary"})
        self.assertEqual(len(rec.events), 1)


class TestRubric(unittest.TestCase):
    def test_machine_portion_scoring(self):
        score = score_machine_portion(
            task_id="t", condition="symptom_only", run_id="r",
            functional_groups=[{"group": "a", "passed": True}, {"group": "b", "passed": False}],
            functional_weights=None,
            compat_groups=[{"group": "c", "passed": True}],
            constraint_checks=[{"name": "x", "passed": True}],
            verification_ran=True,
        )
        comps = {c.component: c for c in score.components}
        self.assertEqual(comps["functional_correctness"].points, 25.0)
        self.assertEqual(comps["root_cause_diagnosis"].points, 0.0)
        self.assertIn("PENDING", comps["root_cause_diagnosis"].detail)
        self.assertFalse(score.passed)


class TestVerificationScoring(unittest.TestCase):
    def test_bare_command_earns_nothing(self):
        from debev.cli import _agent_verification_ran
        events = [{"type": "command", "data": {"cmd": "ls -la", "rc": 0}}]
        self.assertFalse(_agent_verification_ran(events))

    def test_self_reported_verification_earns_nothing(self):
        from debev.cli import _agent_verification_ran
        self.assertFalse(_agent_verification_ran(
            [{"type": "verification", "data": {"name": "x", "result": "PASS"}}]))

    def test_unmarked_test_run_earns_nothing(self):
        from debev.cli import _agent_verification_ran
        self.assertFalse(_agent_verification_ran(
            [{"type": "test_run", "data": {"name": "x", "result": "PASS"}}]))
        self.assertFalse(_agent_verification_ran(
            [{"type": "test_run",
              "data": {"name": "x", "result": "PASS", "via": "toolkit",
                       "replayed": True}}]))

    def test_toolkit_executed_check_counts(self):
        from debev.cli import _agent_verification_ran
        self.assertTrue(_agent_verification_ran(
            [{"type": "test_run",
              "data": {"name": "x", "result": "FAIL", "via": "toolkit"}}]))
        self.assertTrue(_agent_verification_ran(
            [{"type": "test_run",
              "data": {"name": "x", "result": "INCONCLUSIVE", "via": "toolkit"}}]))


class TestLimits(unittest.TestCase):
    def test_tool_budget_stops_calls_and_records_event(self):
        from debev.conditions import load_condition
        from debev.runners import AttemptContext, LimitsTracker
        from debev.toolkit import Toolkit, ToolBudgetExceeded
        from debev.trajectory import TrajectoryRecorder

        ev = load_condition(FIXTURE / "evidence", "symptom_only", 2000)
        with tempfile.TemporaryDirectory() as tmp:
            ctx = AttemptContext(run_id="r", task_id="t", condition="symptom_only",
                                 workspace_dir=Path(tmp), evidence=ev,
                                 allowed_tools=[], limits={"max_tool_calls": 2,
                                                           "max_wall_seconds": 60})
            rec = TrajectoryRecorder(run_id="r", task_id="t", condition="symptom_only")
            tk = Toolkit(ctx, rec, LimitsTracker(2, 60))
            tk.exec(["true"])
            tk.exec(["true"])
            with self.assertRaises(ToolBudgetExceeded):
                tk.exec(["true"])
            kinds = [e["type"] for e in rec.events]
            self.assertIn("limit_exceeded", kinds)
            self.assertEqual(tk.tracker.tool_calls, 2)
            self.assertTrue(tk.tracker.tool_limit_reached)

    def test_wall_deadline_blocks_tool_use(self):
        import time as _time

        from debev.conditions import load_condition
        from debev.runners import AttemptContext, LimitsTracker
        from debev.toolkit import Toolkit, ToolBudgetExceeded
        from debev.trajectory import TrajectoryRecorder

        ev = load_condition(FIXTURE / "evidence", "symptom_only", 2000)
        with tempfile.TemporaryDirectory() as tmp:
            ctx = AttemptContext(run_id="r", task_id="t", condition="symptom_only",
                                 workspace_dir=Path(tmp), evidence=ev,
                                 allowed_tools=[], limits={})
            rec = TrajectoryRecorder(run_id="r", task_id="t", condition="symptom_only")
            tracker = LimitsTracker(60, 1800)
            tracker._t0 -= 2000  # pretend the deadline passed long ago
            tk = Toolkit(ctx, rec, tracker)
            with self.assertRaises(ToolBudgetExceeded) as cm:
                tk.read("x")
            self.assertEqual(cm.exception.kind, "wall_clock")
            self.assertTrue(tracker.wall_limit_reached)

    def test_command_timeout_is_inconclusive(self):
        from debev.conditions import load_condition
        from debev.runners import AttemptContext, LimitsTracker
        from debev.toolkit import Toolkit
        from debev.trajectory import TrajectoryRecorder

        ev = load_condition(FIXTURE / "evidence", "symptom_only", 2000)
        with tempfile.TemporaryDirectory() as tmp:
            ctx = AttemptContext(run_id="r", task_id="t", condition="symptom_only",
                                 workspace_dir=Path(tmp), evidence=ev,
                                 allowed_tools=[], limits={})
            rec = TrajectoryRecorder(run_id="r", task_id="t", condition="symptom_only")
            tk = Toolkit(ctx, rec, LimitsTracker(60, 60))
            result = tk.test("sleep-check", ["sleep", "30"], timeout=1)
            self.assertEqual(result, "INCONCLUSIVE")
            kinds = [e["type"] for e in rec.events]
            self.assertIn("timeout", kinds)


class TestSandboxGuarantees(unittest.TestCase):
    def test_no_credential_inheritance(self):
        import os

        from debev.sandbox import run_command
        os.environ["DEBEV_TEST_SECRET"] = "s3cret"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                res = run_command(["env"], Path(tmp), timeout=30)
                self.assertNotIn("DEBEV_TEST_SECRET", res.stdout)
                self.assertNotIn("s3cret", res.stdout)
        finally:
            del os.environ["DEBEV_TEST_SECRET"]

    def test_oracle_mount_is_read_only_under_bwrap(self):
        from debev.sandbox import detect_isolation, run_command
        if detect_isolation() != "bwrap-sandbox":
            self.skipTest("bwrap unavailable; ro-mount guarantee needs bwrap")
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            ws.mkdir()
            (ws / "f.txt").write_text("x")
            res = run_command(
                [sys.executable, "-c",
                 "open('/workspace/f.txt','a').write('y')"],
                Path(tmp), timeout=30,
                extra_mounts=[(str(ws), "/workspace", "ro")],
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertEqual((ws / "f.txt").read_text(), "x")


class TestOtelDeterminism(unittest.TestCase):
    def _export_twice(self):
        from debev.otel_export import export_otlp, validate_otlp
        events = [
            {"seq": 1, "t_wall_s": 0.0, "type": "run_start", "run_id": "r1",
             "task_id": "t", "condition": "symptom_only",
             "data": {"t_epoch": 1700000000.0}},
            {"seq": 2, "t_wall_s": 1.5, "type": "command", "run_id": "r1",
             "task_id": "t", "condition": "symptom_only",
             "data": {"cmd": "ls", "rc": 0}},
        ]
        meta = {"run_id": "r1", "task_id": "t", "condition": "symptom_only"}
        first = export_otlp(events, meta)
        validate_otlp(first)
        return first, export_otlp(events, meta)

    def test_stable_ids_and_absolute_time(self):
        first, second = self._export_twice()
        self.assertEqual(first, second)
        spans = first["resourceSpans"][0]["scopeSpans"][0]["spans"]
        self.assertEqual(spans[1]["startTimeUnixNano"], str(1700000000_000_000_000 + 1_500_000_000))
        tids = {s["traceId"] for s in spans}
        self.assertEqual(len(tids), 1)
        attrs = dict((a["key"], a.get("value", {})) for a in spans[0]["attributes"])
        self.assertEqual(attrs["debev.time_basis"]["stringValue"], "absolute")

    def test_ids_stable_across_processes(self):
        code = (
            "import json,sys; sys.path.insert(0,'src');"
            "from debev.otel_export import export_otlp;"
            "events=[{'seq':1,'t_wall_s':0.0,'type':'run_start','run_id':'rx',"
            "'task_id':'t','condition':'c','data':{}}];"
            "print(export_otlp(events,{'run_id':'rx'})"
            "['resourceSpans'][0]['scopeSpans'][0]['spans'][0]['traceId'])"
        )
        outs = set()
        for _ in range(2):
            proc = subprocess.run(
                [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT,
                env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(SRC)},
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            outs.add(proc.stdout.strip())
        self.assertEqual(len(outs), 1)  # no PYTHONHASHSEED dependence

    def test_relative_basis_without_epoch(self):
        from debev.otel_export import export_otlp
        events = [{"seq": 1, "t_wall_s": 2.0, "type": "command", "run_id": "r",
                   "task_id": "t", "condition": "c", "data": {}}]
        doc = export_otlp(events, {"run_id": "r"})
        spans = doc["resourceSpans"][0]["scopeSpans"][0]["spans"]
        self.assertEqual(spans[0]["startTimeUnixNano"], str(2_000_000_000))
        attrs = {a["key"]: a.get("value", {}) for a in spans[0]["attributes"]}
        self.assertEqual(attrs["debev.time_basis"]["stringValue"], "relative")


class TestMatrixPlanning(unittest.TestCase):
    def _plan(self, **over):
        plan = {"plan_version": "1.0.0", "study": "s",
                "tasks": ["slot_01", "slot_02", "slot_03"],
                "models": [{"tier": "TIER_A", "model_id": "m-a", "model_version": "v1",
                            "temperature": 0.0, "settings": {},
                            "provider": {"kind": "openai-compatible",
                                         "base_url": "http://127.0.0.1:9",
                                         "env_key": "DEBEV_TEST_KEY_A"}},
                           {"tier": "TIER_B", "model_id": "m-b", "model_version": "v1",
                            "temperature": 0.0, "settings": {},
                            "provider": {"kind": "openai-compatible",
                                         "base_url": "http://127.0.0.1:9",
                                         "env_key": "DEBEV_TEST_KEY_B"}}],
                "harness": {"name": "h", "version": "0.1.0", "tool_policy": "shared"},
                "conditions": ["symptom_only", "repro_log", "state_snapshot",
                               "code_note", "combined"],
                "repetitions": 3, "seed": 7, "randomize": True,
                "limits": {"max_tool_calls": 60, "max_wall_seconds": 1800,
                           "max_evidence_tokens": 2000},
                "budgeting": {}, "provenance": {}}
        plan.update(over)
        return plan

    def test_default_matrix_is_90(self):
        from debev.experiment import expand_matrix, matrix_count
        plan = self._plan()
        self.assertEqual(matrix_count(plan), 90)
        cells = expand_matrix(plan)
        self.assertEqual(len(cells), 90)
        # every model covers every task x condition
        for m in ("m-a", "m-b"):
            got = {(c["task"], c["condition"]) for c in cells if c["model"] == m}
            self.assertEqual(len(got), 15)
        # repetitions are same-cell repeats, not distinct tasks
        reps = {(c["task"], c["condition"], c["model"]) for c in cells}
        self.assertEqual(len(reps), 30)

    def test_order_deterministic_by_seed(self):
        from debev.experiment import expand_matrix
        self.assertEqual(expand_matrix(self._plan()), expand_matrix(self._plan()))

    def test_plan_validation(self):
        import tempfile as _tf
        from debev.experiment import validate_plan
        two_models = [
            {"tier": "TIER_A", "model_id": "TODO-pick-me", "model_version": "v1",
             "temperature": 0.0, "settings": {}},
            {"tier": "TIER_B", "model_id": "m-b", "model_version": "v1",
             "temperature": 0.0, "settings": {}},
        ]
        bad = self._plan(models=two_models)
        errs = [i for i in validate_plan(bad) if i.level == "error"]
        self.assertTrue(any("placeholder" in i.message for i in errs))
        dup = self._plan(tasks=["slot_01", "slot_01"])
        self.assertTrue(any(i.level == "error" for i in validate_plan(dup)))
        with _tf.TemporaryDirectory() as tmp:
            errs2 = [i for i in validate_plan(self._plan(), tasks_root=tmp)
                     if i.level == "error"]
            self.assertTrue(any("missing" in i.message for i in errs2))

    def test_cost_needs_user_prices(self):
        from debev.experiment import cost_upper_bound
        self.assertFalse(cost_upper_bound(self._plan())["computable"])
        legacy = self._plan(budgeting={
            "assumed_max_tokens_per_attempt": 50000,
            "prices": {"m-a": {"input_per_1k": 1.0, "output_per_1k": 2.0,
                               "currency": "USD", "source": "user-supplied"}}})
        legacy_cost = cost_upper_bound(legacy)
        self.assertFalse(legacy_cost["computable"])
        self.assertIn("ambiguous", legacy_cost["reason"])
        priced = self._plan(budgeting={
            "assumed_max_input_tokens_per_attempt": 40000,
            "assumed_max_output_tokens_per_attempt": 10000,
            "max_model_turns_per_attempt": 2,
            "max_retries_per_cell": 1,
            "prices": {"m-a": {"input_per_1k": 1.0, "output_per_1k": 2.0,
                               "currency": "USD", "source": "user-supplied"}}})
        cost = cost_upper_bound(priced)
        self.assertTrue(cost["per_model"]["m-a"]["computable"])
        # (40*1 + 10*2) * 2 turns * 2 tries * 45 cells = 10800
        self.assertEqual(cost["per_model"]["m-a"]["upper_bound"], 10800.0)
        self.assertFalse(cost["per_model"]["m-b"]["computable"])

    def test_spend_cap_gates_execution(self):
        from debev.experiment import check_spend_cap
        no_cap = self._plan()
        self.assertTrue(any(i.level == "error" for i in check_spend_cap(no_cap)))
        priced = self._plan(budgeting={
            "assumed_max_input_tokens_per_attempt": 40000,
            "assumed_max_output_tokens_per_attempt": 10000,
            "max_model_turns_per_attempt": 1,
            "max_retries_per_cell": 0,
            "spend_cap": {"currency": "USD", "amount": 1.0},
            "prices": {"m-a": {"input_per_1k": 1.0, "output_per_1k": 2.0,
                               "currency": "USD", "source": "user-supplied"},
                       "m-b": {"input_per_1k": 1.0, "output_per_1k": 2.0,
                               "currency": "USD", "source": "user-supplied"}}})
        errs = [i for i in check_spend_cap(priced) if i.level == "error"]
        self.assertTrue(any("exceeds spend cap" in i.message for i in errs))

    def test_plan_matrix_cli_dry_run(self):
        import tempfile as _tf
        with _tf.TemporaryDirectory() as tmp:
            # Build a temp tasks root with matching manifests (real slots
            # are placeholders and must NOT validate as runnable tasks).
            tasks_root = Path(tmp) / "tasks"
            for tid in ("slot_01", "slot_02", "slot_03"):
                d = tasks_root / tid
                d.mkdir(parents=True)
                (d / "manifest.json").write_text(json.dumps({
                    "task_id": tid, "conditions": ["symptom_only", "repro_log",
                    "state_snapshot", "code_note", "combined"]}))
            plan_path = Path(tmp) / "plan.json"
            plan_path.write_text(json.dumps(self._plan()))
            proc = subprocess.run(
                [sys.executable, "-m", "debev.cli", "plan-matrix",
                 "--plan", str(plan_path), "--tasks-root", str(tasks_root),
                 "--write", str(Path(tmp) / "exp.json")],
                capture_output=True, text=True, cwd=ROOT,
                env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(SRC)},
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            self.assertIn("90 attempts", proc.stdout)
            artifact = json.loads((Path(tmp) / "exp.json").read_text())
            self.assertTrue(artifact["planned"])
            self.assertEqual(artifact["total"], 90)


class TestHumanGrade(unittest.TestCase):
    def test_pending_not_zero_and_grade_persists(self):
        score = score_machine_portion(
            task_id="t", condition="symptom_only", run_id="r",
            functional_groups=[{"group": "a", "passed": True}],
            functional_weights=None, compat_groups=[],
            constraint_checks=[{"name": "x", "passed": True}],
            verification_ran=True,
        )
        d = score.to_dict()
        diag = next(c for c in d["components"] if c["component"] == "root_cause_diagnosis")
        self.assertEqual(diag["points"], 0.0)
        self.assertIn("PENDING", diag["detail"])
        updated = apply_human_grade(d, diagnosis_pts=14, reporting_pts=2.0,
                                    grader="human", rationale="right file, wrong trigger")
        comps = {c["component"]: c for c in updated["components"]}
        self.assertEqual(comps["root_cause_diagnosis"]["points"], 14)
        self.assertEqual(comps["verification_reporting"]["points"], 4.5)
        self.assertEqual(updated["human_grade"]["grader"], "human")
        with self.assertRaises(ValueError):
            apply_human_grade(score.to_dict(), diagnosis_pts=14)
        with self.assertRaises(ValueError):
            apply_human_grade(score.to_dict(), diagnosis_pts=99, grader="human")


class TestAuditAndOtel(unittest.TestCase):
    def test_audit_fixture_passes(self):
        proc = subprocess.run(
            [sys.executable, "-m", "debev.cli", "audit-task",
             "--task-dir", str(FIXTURE)],
            capture_output=True, text=True, cwd=ROOT,
            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(SRC)},
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertIn("AUDIT PASSED", proc.stdout)

    def test_scripted_fix_run_then_otel_export(self):
        tmp = Path(tempfile.mkdtemp(prefix="debev-test2-"))
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "debev.cli", "run",
                 "--task-dir", str(FIXTURE), "--condition", "symptom_only",
                 "--runs-root", str(tmp / "runs"), "--run-id-prefix", "fix",
                 "--runner", "scripted-fix"],
                capture_output=True, text=True, cwd=ROOT,
                env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(SRC)},
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            run_dir = tmp / "runs" / "fix"
            meta = json.loads((run_dir / "run_meta.json").read_text())
            self.assertTrue(meta["oracle"]["passed"])
            self.assertIn(meta["oracle_isolation"], ("bwrap-sandbox", "fs-separation"))
            self.assertIn("manifest_sha256", meta)
            score = json.loads((run_dir / "score.json").read_text())
            ver = next(c for c in score["components"] if c["component"] == "verification_reporting")
            self.assertEqual(ver["points"], 2.5)  # structured verification event exists
            proc2 = subprocess.run(
                [sys.executable, "-m", "debev.cli", "export-otel",
                 "--run-dir", str(run_dir), "--out", str(tmp / "trace.json")],
                capture_output=True, text=True, cwd=ROOT,
                env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(SRC)},
            )
            self.assertEqual(proc2.returncode, 0, msg=proc2.stdout + proc2.stderr)
            otlp = json.loads((tmp / "trace.json").read_text())
            spans = otlp["resourceSpans"][0]["scopeSpans"][0]["spans"]
            self.assertTrue(any(s["name"] == "debev.verification" for s in spans))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_baseline_probe_runs_real_actions_no_repair(self):
        tmp = Path(tempfile.mkdtemp(prefix="debev-test3-"))
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "debev.cli", "run",
                 "--task-dir", str(FIXTURE), "--condition", "symptom_only",
                 "--runs-root", str(tmp / "runs"), "--run-id-prefix", "base",
                 "--runner", "baseline"],
                capture_output=True, text=True, cwd=ROOT,
                env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(SRC)},
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            run_dir = tmp / "runs" / "base"
            meta = json.loads((run_dir / "run_meta.json").read_text())
            self.assertFalse(meta["oracle"]["passed"])  # probe repairs nothing
            self.assertEqual(meta["runner"], "baseline")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestReplayE2E(unittest.TestCase):
    def test_replay_run_and_report(self):
        tmp = Path(tempfile.mkdtemp(prefix="debev-test-"))
        try:
            # Build a task dir from the plumbing fixture.
            task_dir = tmp / "task"
            (task_dir / "repo").mkdir(parents=True)
            (task_dir / "evidence").mkdir()
            (task_dir / "evaluator").mkdir()
            for f in (FIXTURE / "repo").iterdir():
                shutil.copy2(f, task_dir / "repo" / f.name)
            for f in (FIXTURE / "evidence").iterdir():
                shutil.copy2(f, task_dir / "evidence" / f.name)
            for f in (FIXTURE / "evaluator").iterdir():
                if f.name in ("reference_solution", "partial_fixes"):
                    continue
                shutil.copy2(f, task_dir / "evaluator" / f.name)
            shutil.copy2(FIXTURE / "manifest.json", task_dir / "manifest.json")
            runs_root = tmp / "runs"
            proc = subprocess.run(
                [sys.executable, "-m", "debev.cli", "replay",
                 "--task-dir", str(task_dir),
                 "--condition", "combined",
                 "--runs-root", str(runs_root),
                 "--run-id-prefix", "test-replay",
                 "--replay-file", str(ROOT / "fixtures" / "replay_example.jsonl")],
                capture_output=True, text=True, cwd=ROOT, env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(SRC)},
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            run_dir = runs_root / "test-replay"
            self.assertTrue((run_dir / "trajectory.jsonl").is_file())
            self.assertTrue((run_dir / "score.json").is_file())
            meta = json.loads((run_dir / "run_meta.json").read_text())
            self.assertTrue(meta["replayed"])
            self.assertTrue(meta["oracle"]["passed"], msg=json.dumps(meta["oracle"]))
            # Evaluator files must not leak into the workspace.
            self.assertFalse((run_dir / "workspace" / "oracle.py").exists())
            proc2 = subprocess.run(
                [sys.executable, "-m", "debev.cli", "report",
                 "--runs-root", str(runs_root), "--out", str(tmp / "REPORT.md")],
                capture_output=True, text=True, cwd=ROOT, env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(SRC)},
            )
            self.assertEqual(proc2.returncode, 0, msg=proc2.stdout + proc2.stderr)
            report = json.loads((tmp / "REPORT.md").with_suffix(".json").read_text())
            self.assertTrue(report["pilot"])
            self.assertEqual(report["n_runs"], 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestModelRunnerBoundary(unittest.TestCase):
    def _ctx(self, tmp):
        from debev.conditions import load_condition
        from debev.runners import AttemptContext
        ev = load_condition(FIXTURE / "evidence", "symptom_only", 2000)
        ws = Path(tmp) / "ws"
        ws.mkdir()
        (ws / "a.txt").write_text("hello")
        return AttemptContext(run_id="r", task_id="t", condition="symptom_only",
                              workspace_dir=ws, evidence=ev, allowed_tools=[],
                              limits={"max_tool_calls": 20, "max_wall_seconds": 60})

    def test_loopback_actions_go_through_toolkit_only(self):
        import sys as _sys

        from debev.model_runner import LoopbackTransport, ModelAgentRunner
        from debev.trajectory import TrajectoryRecorder
        script = [json.dumps({"actions": [
            {"op": "read", "path": "a.txt"},
            {"op": "exec", "cmd": [_sys.executable, "-c", "print(1)"]},
            {"op": "test", "name": "t1",
             "cmd": [_sys.executable, "-c", "raise SystemExit(0)"]},
            {"op": "write", "path": "sub/b.txt", "content": "wrote"},
            {"op": "exec", "cmd": "rm -rf /"},  # string cmd must be rejected
            {"op": "finish", "diagnosis": "loopback",
             "verification_summary": "loopback"}]})]
        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._ctx(tmp)
            rec = TrajectoryRecorder(run_id="r", task_id="t", condition="symptom_only")
            runner = ModelAgentRunner(model_id="m", model_version="v",
                                      transport=LoopbackTransport(script), max_turns=3)
            result = runner.run(ctx, rec)
            kinds = [e["type"] for e in rec.events]
            self.assertIn("file_read", kinds)
            self.assertIn("command", kinds)
            self.assertTrue(any(e["type"] == "test_run" and
                                e["data"].get("via") == "toolkit" for e in rec.events))
            self.assertTrue((Path(tmp) / "ws" / "sub" / "b.txt").is_file())
            # string-shell command rejected, attempt ended fail-closed
            self.assertTrue(any(e["type"] == "agent_note" and
                                e["data"].get("kind") == "error" for e in rec.events))
            # string-shell command rejected (graceful: model gets next turn),
            # then loopback script exhausts and finishes on turn 2
            self.assertEqual(result.provider_usage["calls"], 2)

    def test_no_credential_in_outputs(self):
        import os

        from debev.model_runner import LoopbackTransport, ModelAgentRunner
        from debev.trajectory import TrajectoryRecorder
        os.environ["DEBEV_TEST_KEY_X"] = "sk-test-SUPERSECRET123"
        try:
            script = [json.dumps({"actions": [
                {"op": "exec", "cmd": ["env"]},
                {"op": "finish", "diagnosis": "d", "verification_summary": "v"}]})]
            with tempfile.TemporaryDirectory() as tmp:
                ctx = self._ctx(tmp)
                rec = TrajectoryRecorder(run_id="r", task_id="t", condition="symptom_only")
                runner = ModelAgentRunner(model_id="m", model_version="v",
                                          transport=LoopbackTransport(script))
                runner.run(ctx, rec)
                blob = "\n".join(json.dumps(e) for e in rec.events)
                self.assertNotIn("SUPERSECRET123", blob)
        finally:
            del os.environ["DEBEV_TEST_KEY_X"]

    def test_rejected_file_action_is_graceful(self):
        from debev.model_runner import LoopbackTransport, ModelAgentRunner
        from debev.trajectory import TrajectoryRecorder
        script = [json.dumps({"actions": [
            {"op": "read", "path": "nope-missing.txt"},
            {"op": "finish", "diagnosis": "d", "verification_summary": "v"}]}),
            json.dumps({"actions": [
                {"op": "finish", "diagnosis": "recovered",
                 "verification_summary": "recovered"}]})]
        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._ctx(tmp)
            rec = TrajectoryRecorder(run_id="r", task_id="t", condition="symptom_only")
            runner = ModelAgentRunner(model_id="m", model_version="v",
                                      transport=LoopbackTransport(script), max_turns=3)
            result = runner.run(ctx, rec)
            self.assertTrue(any(e["type"] == "agent_note" and
                                e["data"].get("kind") == "error" for e in rec.events))
            self.assertTrue(any(e["type"] == "model_reply" for e in rec.events))
            self.assertEqual(result.diagnosis, "recovered")
            self.assertEqual(result.provider_usage["calls"], 2)

    def test_freeze_violation_refuses(self):
        from debev.model_runner import LoopbackTransport, ModelAgentRunner
        runner = ModelAgentRunner(model_id="m-a", model_version="v1",
                                  transport=LoopbackTransport([]))
        with self.assertRaises(ValueError):
            runner._check_frozen("m-a", "v2")
        with self.assertRaises(ValueError):
            runner._check_frozen("m-other", "v1")
        runner._check_frozen("m-a", "v1")  # exact match OK

    def test_provider_error_text_never_carries_secrets(self):
        from unittest import mock

        from debev.model_runner import ModelAgentRunner, VertexTransport
        from debev.trajectory import TrajectoryRecorder
        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._ctx(tmp)
            rec = TrajectoryRecorder(run_id="r", task_id="t", condition="symptom_only")
            runner = ModelAgentRunner(model_id="m", model_version="v",
                                      transport=VertexTransport("p", "global", "m"),
                                      max_turns=1)
            with mock.patch("debev.model_runner.adc_access_token",
                             return_value="tok-SUPERSECRET"), \
                 mock.patch("urllib.request.urlopen",
                            side_effect=Exception("HTTP 429 QUOTA_EXCEEDED")):
                result = runner.run(ctx, rec)
            blob = "\n".join(json.dumps(e) for e in rec.events)
            self.assertNotIn("SUPERSECRET", blob)
            self.assertIn("429", blob)  # cause preserved for analysis
            self.assertEqual(result.provider_usage["calls"], 0)


class TestRunMatrixDriver(unittest.TestCase):
    def _mini_tasks(self, tmp):
        tasks_root = Path(tmp) / "tasks"
        for tid in ("t1", "t2"):
            d = tasks_root / tid
            (d / "repo").mkdir(parents=True, exist_ok=True)
            (d / "evidence").mkdir(parents=True, exist_ok=True)
            (d / "evaluator").mkdir(parents=True, exist_ok=True)
            if not (d / "manifest.json").is_file():
                (d / "manifest.json").write_text(json.dumps({
                    "task_id": tid,
                    "conditions": ["symptom_only", "repro_log", "state_snapshot",
                                   "code_note", "combined"]}))
        return tasks_root

    def _full_manifest(self, tid):
        return {
            "schema_version": "1.0.0", "task_id": tid, "title": f"test {tid}",
            "repo_snapshot": {"kind": "test", "ref": tid, "provenance": "test"},
            "task_instructions_ref": "instructions.md",
            "allowed_tools": ["read", "write", "exec", "test"],
            "conditions": ["symptom_only", "repro_log", "state_snapshot",
                           "code_note", "combined"],
            "resource_limits": {"max_tool_calls": 60, "max_wall_seconds": 600,
                                "max_evidence_tokens": 2000},
            "oracle": {"entry_point": "oracle.py", "type": "script-groups"},
            "rubric_version": "1.0.0",
            "provenance": {"author": "test", "created": "test", "source": "test"}}

    def _fixture_task(self, tmp, tid):
        """A runnable audit-passing task cloned from the plumbing fixture."""
        import shutil as _shutil
        tasks_root = Path(tmp) / "tasks"
        d = tasks_root / tid
        if d.exists():
            _shutil.rmtree(d)
        _shutil.copytree(FIXTURE, d)
        (d / "manifest.json").write_text(json.dumps(self._full_manifest(tid)))
        (d / "instructions.md").write_text("test instructions")
        return tasks_root

    def _mini_plan(self, tasks):
        return {
            "plan_version": "1.0.0", "study": "ministudy", "tasks": tasks,
            "models": [
                {"tier": "TIER_A", "model_id": "mm-a", "model_version": "v1",
                 "temperature": 0.0, "settings": {},
                 "provider": {"kind": "openai-compatible",
                              "base_url": "http://127.0.0.1:9",
                              "env_key": "DEBEV_TEST_KEY_A"}},
                {"tier": "TIER_B", "model_id": "mm-b", "model_version": "v1",
                 "temperature": 0.0, "settings": {},
                 "provider": {"kind": "openai-compatible",
                              "base_url": "http://127.0.0.1:9",
                              "env_key": "DEBEV_TEST_KEY_B"}}],
            "harness": {"name": "h", "version": "0.1.0", "tool_policy": "shared"},
            "conditions": ["symptom_only", "repro_log", "state_snapshot",
                           "code_note", "combined"],
            "repetitions": 1, "seed": 3, "randomize": True,
            "limits": {"max_tool_calls": 60, "max_wall_seconds": 1800,
                       "max_evidence_tokens": 2000},
            "budgeting": {"assumed_max_input_tokens_per_attempt": 1000,
                          "assumed_max_output_tokens_per_attempt": 500,
                          "max_model_turns_per_attempt": 2,
                          "max_retries_per_cell": 0,
                          "spend_cap": {"currency": "USD", "amount": 100.0},
                          "prices": {
                              "mm-a": {"input_per_1k": 1.0, "output_per_1k": 2.0,
                                       "currency": "USD", "source": "user-supplied"},
                              "mm-b": {"input_per_1k": 1.0, "output_per_1k": 2.0,
                                       "currency": "USD", "source": "user-supplied"}}},
            "provenance": {}}

    def _run_cli_matrix(self, tmp, plan, mode, extra=()):
        plan_path = Path(tmp) / "plan.json"
        plan_path.write_text(json.dumps(plan))
        proc = subprocess.run(
            [sys.executable, "-m", "debev.cli", "run-matrix",
             "--plan", str(plan_path), "--mode", mode,
             "--tasks-root", str(Path(tmp) / "tasks"),
             "--runs-root", str(Path(tmp) / "runs"),
             "--state", str(Path(tmp) / "state.json")] + list(extra),
            capture_output=True, text=True, cwd=ROOT,
            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(SRC)},
        )
        return proc

    def test_execute_refused_without_authorize_spend(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._mini_tasks(tmp)
            proc = self._run_cli_matrix(tmp, self._mini_plan(["t1", "t2"]), "execute")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("--authorize-spend", proc.stdout)

    def test_execute_fail_closed_on_audit(self):
        # t2 is an empty shell (no reference_solution) -> audit fails closed
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture_task(tmp, "t1")
            self._mini_tasks(tmp)
            proc = self._run_cli_matrix(
                tmp, self._mini_plan(["t1", "t2"]), "execute",
                extra=("--authorize-spend",))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("ABORTED", proc.stdout + proc.stderr)

    def test_dry_run_plans_without_provider_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture_task(tmp, "t1")
            plan = self._mini_plan(["t1"])
            proc = self._run_cli_matrix(tmp, plan, "dry-run")
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            self.assertIn("10 cells planned", proc.stdout)  # 1 task x 5 conds x 2 models x 1 rep
            self.assertIn("0 provider calls", proc.stdout)
            state = json.loads((Path(tmp) / "state.json").read_text())
            self.assertEqual(len(state["cells"]), 0)  # dry-run runs nothing
            self.assertNotIn("chat/completions", proc.stdout + proc.stderr)

    def test_execute_offline_loopback_no_cap(self):
        import os as _os

        from debev.matrix import run_matrix
        from debev.model_runner import LoopbackTransport
        with tempfile.TemporaryDirectory() as tmp:
            tasks_root = self._fixture_task(tmp, "t1")
            plan = self._mini_plan(["t1"])
            for m in plan["models"]:
                m["provider"] = {"kind": "openai-compatible",
                                 "base_url": "http://127.0.0.1:9",
                                 "env_key": "DEBEV_TEST_EXEC"}
            plan["budgeting"] = {
                "assumed_max_input_tokens_per_attempt": 1000,
                "assumed_max_output_tokens_per_attempt": 500,
                "max_model_turns_per_attempt": 2,
                "max_retries_per_cell": 0,
                "spend_cap": {"currency": "USD", "amount": 0.01},
                "prices": {m["model_id"]: {"input_per_1k": 1.0, "output_per_1k": 2.0,
                                           "currency": "USD", "source": "user-supplied"}
                           for m in plan["models"]}}
            plan_path = Path(tmp) / "plan.json"
            plan_path.write_text(json.dumps(plan))
            _os.environ["DEBEV_TEST_EXEC"] = "fake-not-a-key"
            try:
                script = [json.dumps({"actions": [
                    {"op": "finish", "diagnosis": "loopback",
                     "verification_summary": "loopback"}]})]
                rc = run_matrix(
                    plan_path, tasks_root, Path(tmp) / "runs", Path(tmp) / "state.json",
                    "execute", authorize_spend=True, fresh=True, no_spend_cap=True,
                    transport_factory=lambda m: LoopbackTransport(list(script)))
                self.assertEqual(rc, 0)
                state = json.loads((Path(tmp) / "state.json").read_text())
                self.assertEqual(len(state["cells"]), 10)  # 1 task x 5 conds x 2 models
                self.assertTrue(all(c["status"] == "done" for c in state["cells"].values()))
                # resume skips everything
                rc2 = run_matrix(
                    plan_path, tasks_root, Path(tmp) / "runs", Path(tmp) / "state.json",
                    "execute", authorize_spend=True, fresh=False, no_spend_cap=True,
                    transport_factory=lambda m: LoopbackTransport(list(script)))
                self.assertEqual(rc2, 0)
            finally:
                del _os.environ["DEBEV_TEST_EXEC"]

    def test_resume_skips_done_cells(self):
        from debev.matrix import cell_key, expand_matrix, load_state, save_state
        with tempfile.TemporaryDirectory() as tmp:
            plan = self._mini_plan(["t1"])
            cells = expand_matrix(plan)
            self.assertEqual(len(cells), 10)  # 1 task x 5 conds x 2 models x 1 rep
            state_path = Path(tmp) / "state.json"
            state = {"plan_hash": "h", "cells": {
                cell_key(cells[0]): {"status": "done", "run_id": "x", "attempts": 1}},
                "spend": {}, "currency": None}
            save_state(state_path, state)
            reloaded = load_state(state_path)
            self.assertEqual(reloaded["cells"][cell_key(cells[0])]["status"], "done")

    def test_smoke_loopback_marks_plumbing_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture_task(tmp, "t1")
            proc = self._run_cli_matrix(tmp, self._mini_plan(["t1"]), "smoke")
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            self.assertIn("SMOKE PASSED", proc.stdout)
            self.assertIn("plumbing-only", proc.stdout)
            meta = json.loads((Path(tmp) / "runs" / "smoke-loopback" / "run_meta.json").read_text())
            self.assertTrue(meta.get("plumbing_only"))

    def test_smoke_on_audited_draft_task(self):
        import shutil as _shutil
        with tempfile.TemporaryDirectory() as tmp:
            tasks_root = self._fixture_task(tmp, "t1")
            proc = subprocess.run(
                [sys.executable, "-m", "debev.cli", "run-matrix",
                 "--plan", str(self._write_plan(tmp)),
                 "--mode", "smoke", "--smoke-task", str(tasks_root / "t1"),
                 "--tasks-root", str(tasks_root),
                 "--runs-root", str(Path(tmp) / "runs"),
                 "--state", str(Path(tmp) / "state.json")],
                capture_output=True, text=True, cwd=ROOT,
                env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(SRC)},
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            self.assertIn("draft task", proc.stdout)
            self.assertIn("SMOKE PASSED", proc.stdout)

    def _write_plan(self, tmp):
        plan_path = Path(tmp) / "plan.json"
        plan_path.write_text(json.dumps(self._mini_plan(["t1"])))
        return plan_path


    def test_report_distinguishes_full_vs_functional(self):
        from debev.report import build_report
        base = {"task_id": "t", "condition": "c", "model": "m", "tier": "T",
                "efficiency": {}, "evidence_tokens": 10, "trajectory_summary": {},
                "failure_labels": [], "replayed": False}
        recs = [
            dict(base, run_id="a", score={"passed": True, "total": 50.0}, full_passed=True),
            dict(base, run_id="b", score={"passed": True, "total": 70.0}, full_passed=False),
            dict(base, run_id="c", score={"passed": False, "total": 10.0}, full_passed=False),
        ]
        rep = build_report(recs)
        cell = rep["cells"][0]
        self.assertEqual(cell["functional_passes"], 2)
        self.assertEqual(cell["full_passes"], 1)
        self.assertNotIn("passes", cell)  # ambiguous key retired
        md = __import__("debev.report", fromlist=["render_markdown"]).render_markdown(rep)
        self.assertIn("funct_pass", md)
        self.assertIn("full_pass", md)
        self.assertIn("NOT a task pass", md)


if __name__ == "__main__":
    unittest.main()
