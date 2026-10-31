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

    def test_structured_verification_counts(self):
        from debev.cli import _agent_verification_ran
        self.assertTrue(_agent_verification_ran(
            [{"type": "verification", "data": {"name": "x", "result": "FAIL"}}]))
        self.assertTrue(_agent_verification_ran(
            [{"type": "test_run", "data": {"name": "x", "result": "PASS"}}]))
        self.assertFalse(_agent_verification_ran(
            [{"type": "test_run", "data": {"name": "x"}}]))


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


if __name__ == "__main__":
    unittest.main()
