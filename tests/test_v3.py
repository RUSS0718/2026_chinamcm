import json
import csv
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from src.v3 import (
    COLD_SEEDS,
    FINAL_SEEDS,
    CommandPlan,
    FreezeError,
    build_plan,
    build_specs,
    check_freeze,
    check_registered,
    check_q4_extension,
    check_q4_registered,
    execute_plan,
    load_frozen_manifest,
    q4_extension_checklist,
    q1_mechanical_decision,
    q2_mechanical_decision,
    q3_mechanical_decision,
    registered_payload,
    summarize_directory,
    summarize_q2,
    summarize_q3,
    write_once,
)


class V3ProtocolTests(unittest.TestCase):
    def test_default_specs_are_complete_and_q2_b_is_frozen(self):
        specs = build_specs()
        self.assertEqual(specs["q2"].q2_v3_baseline, "B")
        self.assertEqual(specs["q3"].seeds, COLD_SEEDS)
        self.assertEqual(specs["q3"].final_seeds, FINAL_SEEDS)
        for spec in specs.values():
            self.assertTrue(all(len(value) == 64 for value in spec.code_hashes.values()))
            self.assertTrue(all(len(value) == 64 for value in spec.config_hashes.values()))
            self.assertEqual(len(spec.data_hash), 64)

    def test_freeze_check_fails_closed_for_hash_seed_and_n300(self):
        spec = build_specs()["q2"]
        manifest = spec.as_dict()
        check_freeze(manifest, spec)
        with self.subTest("hash"):
            broken = {**manifest, "data_hash": "0" * 64}
            with self.assertRaises(FreezeError):
                check_freeze(broken, spec)
        with self.subTest("seed"):
            broken = {**manifest, "seeds": list(range(1, 21))}
            with self.assertRaises(FreezeError):
                check_freeze(broken, spec)
        with self.subTest("n300"):
            broken = {**manifest, "instance": "n300"}
            with self.assertRaises(FreezeError):
                check_freeze(broken, spec, dry_run=True)

    def test_immutable_manifest_rejects_code_drift(self):
        spec = build_specs()["q2"]
        frozen = load_frozen_manifest()["q2"]
        actual = registered_payload(spec)
        check_registered(actual, frozen)
        broken = json.loads(json.dumps(actual))
        broken["code_files"][0]["sha256"] = "0" * 64
        with self.assertRaises(FreezeError):
            check_registered(broken, frozen)

    def test_plan_uses_isolated_seed_markers_without_running(self):
        spec = build_specs()["q2"]
        plans = build_plan(spec, python="python")
        self.assertEqual(len(plans), 60)
        self.assertIn("--candidate", plans[0].command)
        self.assertIn("seed_2201", plans[0].marker.as_posix())
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "P0" / "seed_2201" / "events.jsonl"
            marker.parent.mkdir(parents=True)
            fingerprint = {
                "problem": "q2", "instance": "n200", "config_id": "P0", "seed": 2201,
                "code_hash": "a" * 64, "config_hash": "b" * 64, "data_hash": "c" * 64,
            }
            marker.write_text("existing\n", encoding="utf-8")
            (marker.parent / "v3_freeze.json").write_text(json.dumps(fingerprint), encoding="utf-8")
            with self.assertRaises(FreezeError):
                execute_plan((CommandPlan(("unused",), marker, fingerprint),), execute=False)
            marker.write_text(json.dumps({**fingerprint, "status": "crash", "formal_audit_match": False}) + "\n", encoding="utf-8")
            result = execute_plan((CommandPlan(("unused",), marker, fingerprint),), execute=False)
        self.assertEqual(result[0]["status"], "skipped_existing")

    def test_attempt_slug_rejects_path_escape_and_reserved_names(self):
        spec = build_specs()["q2"]
        for attempt in ("../escape", "a/b", "C:\\outside", ".", "..", "base", ""):
            with self.subTest(attempt=attempt), self.assertRaises(FreezeError):
                build_plan(spec, attempt=attempt)
        plan = build_plan(spec, attempt="retry_01")[0]
        self.assertIn("retry_01", plan.marker.as_posix())
        self.assertTrue(Path(spec.output_root).resolve() in plan.marker.parents)

    def test_partial_output_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "run" / "events.jsonl"
            marker.parent.mkdir(parents=True)
            (marker.parent / "partial.json").write_text("partial", encoding="utf-8")
            with self.assertRaises(FreezeError):
                execute_plan((CommandPlan((sys.executable, "-c", "pass"), marker),), execute=True)

    def test_q3_auxiliary_table_conflict_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "runtime" / "run" / "result.json"
            auxiliary = root / "tables" / "run_attempts.csv"
            auxiliary.parent.mkdir(parents=True)
            (auxiliary.parent / "run_attempts.csv.bak").write_text("old", encoding="utf-8")
            fingerprint = {"problem": "q3", "instance": "n200", "config_id": "Q3-LIN"}
            plan = CommandPlan((sys.executable, "-c", "pass"), marker, fingerprint, auxiliary_markers=(auxiliary,))
            with self.assertRaises(FreezeError):
                execute_plan((plan,), execute=False)

    def test_q3_result_and_auxiliary_markers_validate_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = build_specs()["q3"]
            spec = spec.__class__(**{**spec.__dict__, "output_root": str(Path(tmp) / "q3")})
            plan = build_plan(spec)[0]
            fingerprint = dict(plan.fingerprint)
            cold = list(fingerprint["cold_seeds"])
            final = list(fingerprint["final_seeds"])
            seed_attempts = [{"seed": seed, "mode": "cold", "status": "success", "legal": True, "formal_audit_match": True} for seed in cold]
            final_attempts = [{"seed": seed, "mode": "final_cold", "status": "success", "legal": True, "formal_audit_match": True} for seed in final]
            thresholds = [{"dead_space_ratio": 0.1, "seed_attempts": seed_attempts}]
            config = {"candidate": "Q3-BIN", "seeds": cold, "final_seeds": final}
            payload = {"problem": "Q3", "instance": "n200", "run_id": "fixture", "code_hash": fingerprint["code_hash"],
                       "config_hash": fingerprint["config_hash"], "data_hash": fingerprint["data_hash"], "status": "success",
                       "config": config, "attempts": thresholds, "final_attempts": final_attempts, "selected_ratio": 0.1}
            plan.marker.parent.mkdir(parents=True)
            plan.marker.write_text(json.dumps(payload), encoding="utf-8")
            (plan.marker.parent / "v3_freeze.json").write_text(json.dumps(fingerprint), encoding="utf-8")
            attempts_path, snapshot_path = plan.auxiliary_markers
            attempts_path.parent.mkdir(parents=True, exist_ok=True)
            with attempts_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["phase", "dead_space_ratio", "seed"])
                writer.writeheader()
                writer.writerows({"phase": "threshold", "dead_space_ratio": 0.1, "seed": seed} for seed in cold)
                writer.writerows({"phase": "final", "dead_space_ratio": 0.1, "seed": seed} for seed in final)
            snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
            result = execute_plan((plan,), execute=False)
            self.assertEqual(result[0]["status"], "skipped_existing")

    def test_summary_directory_discovers_registered_q2_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "q2_attempt"
            original = build_specs()["q2"]
            spec = original.__class__(**{**original.__dict__, "output_root": str(base)})
            plans = build_plan(spec)
            for plan in plans:
                plan.marker.parent.mkdir(parents=True, exist_ok=True)
                record = {**dict(plan.fingerprint), "problem": "Q2", "status": "success", "legal": True,
                          "formal_audit_match": True, "HPWL": 10.0, "first_feasible_evaluation": 1,
                          "checkpoint_best_hpwl": {"25": 10.0, "50": 10.0, "75": 10.0, "100": 10.0}}
                plan.marker.write_text(json.dumps(record) + "\n", encoding="utf-8")
                (plan.marker.parent / "v3_freeze.json").write_text(json.dumps(plan.fingerprint), encoding="utf-8")
            summary = summarize_directory("q2", base)
            self.assertEqual(summary["registered_runs"], 60)
            self.assertEqual(summary["discovered_runs"], 60)
            self.assertEqual(summary["missing_runs"], 0)
            self.assertEqual(summary["mechanical_decision"]["decision"], "selected")
            first = plans[0].marker
            original_text = first.read_text(encoding="utf-8")
            first.write_text(original_text * 2, encoding="utf-8")
            with self.assertRaises(FreezeError):
                summarize_directory("q2", base)
            first.write_text(original_text, encoding="utf-8")
            retry_copy = base / "retry" / first.relative_to(base)
            retry_copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(first, retry_copy)
            with self.assertRaises(FreezeError):
                summarize_directory("q2", base)

    def test_q2_summary_reports_missing_checkpoint_data_instead_of_inventing_it(self):
        rows = [
            {"config_id": "P1", "status": "success", "legal": True, "formal_audit_match": True, "HPWL": 10.0},
            {"config_id": "P1", "status": "timeout", "legal": True, "formal_audit_match": True, "HPWL": 12.0},
        ]
        summary = summarize_q2(rows)[0]
        self.assertEqual(summary["legal_rate"], 1.0)
        self.assertEqual(summary["checkpoint_status"], "missing")
        self.assertIsNone(summary["checkpoint_median_best_so_far_HPWL"]["25"])

    def test_q3_summary_keeps_warm_and_final_out_of_cold_denominator(self):
        rows = [
            {"phase": "threshold", "mode": "cold", "legal": True, "formal_audit_match": True, "status": "success"},
            {"phase": "threshold", "mode": "cold", "legal": False, "formal_audit_match": True, "status": "no_feasible"},
            {"phase": "threshold", "mode": "warm", "legal": True, "formal_audit_match": True, "status": "success"},
            {"phase": "final", "mode": "final_cold", "legal": True, "formal_audit_match": True, "status": "timeout"},
        ]
        summary = summarize_q3(rows)
        self.assertEqual(summary["threshold_cold_runs"], 2)
        self.assertEqual(summary["threshold_cold_legal_rate"], 0.5)
        self.assertEqual(summary["threshold_warm_runs"], 1)
        self.assertEqual(summary["final_runs"], 1)
        self.assertTrue(summary["warm_excluded_from_cold"])
        self.assertTrue(summary["final_excluded_from_cold"])
        self.assertEqual(summary["threshold_cold_status_counts"]["status_no_feasible"], 1)
        self.assertEqual(summary["threshold_warm_status_counts"]["status_success"], 1)
        self.assertEqual(summary["final_status_counts"]["status_timeout"], 1)

    def test_mechanical_decisions_are_hard_gated_and_route_deterministic(self):
        good = lambda config_id, metric: {"config_id": config_id, "legal_rate": 1.0, "audit_match_runs": 20,
                                          "missing_runs": 0, "median_area" if metric == "area" else "median_HPWL": 10.0,
                                          "median_aspect_ratio": 1.0, "iqr_area": 1.0, "p90_area": 1.0,
                                          "checkpoint_median_best_so_far_HPWL": {"25": 10.0, "50": 10.0, "75": 10.0, "100": 10.0},
                                          "median_first_feasible_evaluation": 1}
        q1 = q1_mechanical_decision([good(name, "area") for name in ("Q1-G", "Q1-SP", "Q1-BT", "Q1-BT-D", "Q1-BT-both", "Q1-BT-directed-only", "Q1-BT-dedup-only")])
        self.assertEqual(q1["decision"], "selected")
        q2 = q2_mechanical_decision([good(name, "HPWL") for name in ("P0", "P1", "P2")])
        self.assertEqual(q2["decision"], "selected")
        routes = {name: {"d_robust": 0.1 if name == "Q3-BIN" else 0.105, "final_legal_rate": 1.0,
                         "final_median_HPWL": 10.0, "final_iqr_HPWL": 1.0} for name in ("Q3-BIN", "Q3-LIN", "Q3-CONT-R")}
        self.assertEqual(q3_mechanical_decision(routes)["selected"], "Q3-BIN")

    def test_write_once_is_idempotent_and_refuses_different_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            write_once(path, {"seed": 2201})
            write_once(path, {"seed": 2201})
            with self.assertRaises(FreezeError):
                write_once(path, {"seed": 2202})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"seed": 2201})

    def test_q4_extension_is_independent_and_locked_without_human_domain_definition(self):
        checklist = q4_extension_checklist()
        self.assertEqual(checklist["status"], "frozen_integer_domain_pending_main_run_review")
        self.assertEqual(checklist["continuous_domain_confirmed"], False)
        check_q4_extension(checklist)
        self.assertEqual(check_q4_registered()["config_hash"], checklist["config_hash"])
        with self.assertRaises(FreezeError):
            check_q4_extension({**checklist, "n200_selection": True})


if __name__ == "__main__":
    unittest.main()
