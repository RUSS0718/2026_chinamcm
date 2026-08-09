import json
import csv
from dataclasses import replace
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

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
    summarize_q1,
    summarize_q2,
    summarize_q3,
    summarize_q4,
    write_once,
)
from src.v3 import _q4_config_digest, _q4_slot_configs, _validate_completed
from src.Q4.geometry import EXTERNAL_DATA_MANIFEST_HASH
from src.q3_holdout import (
    COLD_SEEDS as Q3_HOLDOUT_COLD_SEEDS,
    FINAL_SEEDS as Q3_HOLDOUT_FINAL_SEEDS,
    build_holdout_plan,
    build_holdout_spec,
    check_holdout_spec,
    dry_run_payload,
)


class V3ProtocolTests(unittest.TestCase):
    def test_q4_plan_is_726_slots_and_workers_eight(self):
        spec = build_specs()["q4"]
        plans = build_plan(spec)
        self.assertEqual(spec.workers, 8)
        self.assertEqual(spec.output_root.replace("\\", "/"), "outputs/q4/_runtime/v3_integer_domain")
        self.assertEqual(len(plans), 726)
        self.assertEqual(sum(plan.fingerprint["mode"] == "exact" for plan in plans), 6)
        self.assertEqual(sum(plan.fingerprint["mode"] == "sa" for plan in plans), 720)
        self.assertEqual({plan.fingerprint["geometry"] for plan in plans}, {"G-", "G0", "G+"})
        self.assertEqual({tuple(plan.fingerprint["domain"]) for plan in plans}, {(9, 9), (12, 12)})
        self.assertTrue(all(plan.fingerprint["environment"]["workers"] == 8 for plan in plans))
        self.assertTrue(all("n200" not in plan.fingerprint["config_id"] and "n300" not in plan.fingerprint["config_id"] for plan in plans))

    def test_q4_summary_requires_registered_shape_and_computes_gap(self):
        spec = build_specs()["q4"]
        plans = build_plan(spec)
        rows = []
        for plan in plans:
            fp = plan.fingerprint
            rows.append({"config_id": fp["config_id"], "geometry": fp["geometry"], "mode": fp["mode"],
                         "seed": fp["seed"], "status": "optimal" if fp["mode"] == "exact" else "success",
                         "formal": {"legal": True, "area": 24}, "formal_audit_match": True,
                         "domain_formal": {"legal": True, "area": fp["domain"][0] * fp["domain"][1]},
                         "domain_audit_match": True})
        summary = summarize_q4(rows, plans)
        self.assertEqual(summary["registered_slots"], 726)
        self.assertEqual(len(summary["exact"]), 6)
        self.assertEqual(len(summary["summary_by_cell"]), 36)
        self.assertTrue(all(cell["legal_rate"] == 1.0 and cell["incumbent_gap"]["median"] == 0.0 for cell in summary["summary_by_cell"]))

    def test_q4_summary_rejects_domain_outside_layout_as_legal(self):
        spec = build_specs()["q4"]
        plans = build_plan(spec)
        rows = []
        for plan in plans:
            fp = plan.fingerprint
            rows.append({"config_id": fp["config_id"], "geometry": fp["geometry"], "mode": fp["mode"],
                         "seed": fp["seed"], "status": "optimal" if fp["mode"] == "exact" else "success",
                         "formal": {"legal": True, "area": 24}, "formal_audit_match": True,
                         "domain_formal": {"legal": True, "area": fp["domain"][0] * fp["domain"][1]},
                         "domain_audit_match": True})
        exact = next(row for row in rows if row["mode"] == "exact")
        exact["domain_formal"] = {"legal": False, "area": exact["domain_formal"]["area"]}
        exact["domain_audit_match"] = False
        summary = summarize_q4(rows, plans)
        self.assertFalse(summary["exact"][0]["legal"])
        self.assertIsNone(summary["exact"][0]["area"])

    def test_q4_marker_validator_accepts_complete_failure_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = replace(build_specs()["q4"], output_root=tmp)
            plan = build_plan(spec)[0]
            fp = dict(plan.fingerprint)
            payload = {"problem": "Q4", "instance": fp["instance"], "geometry": fp["geometry"],
                       "b1_beam_thickness": fp["b1_beam_thickness"], "domain": fp["domain"], "mode": "exact",
                       "seed": None, "data_hash": fp["data_hash"], "code_hash": fp["code_hash"],
                       "config": _q4_slot_configs()[fp["config_id"]], "config_hash": fp["config_hash"],
                       "command": fp["command"], "command_argv": fp["command_argv"], "environment": {"omp_num_threads": "1", "mkl_num_threads": "1", "openblas_num_threads": "1"},
                       "status": "timeout", "formal": {}, "audit": {},
                       "formal_audit_match": False, "domain_formal": {}, "domain_audit": {},
                       "domain_audit_match": False}
            plan.marker.parent.mkdir(parents=True)
            plan.marker.write_text(json.dumps(payload), encoding="utf-8")
            (plan.marker.parent / "v3_freeze.json").write_text(json.dumps(fp), encoding="utf-8")
            self.assertEqual(_validate_completed(plan)["status"], "timeout")

    def test_q4_real_single_plan_executes_and_validator_accepts(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = replace(build_specs()["q4"], output_root=tmp)
            original = build_plan(spec)[0]
            command = list(original.command)
            command[command.index("--time-limit") + 1] = "0"
            config = dict(_q4_slot_configs()[original.fingerprint["config_id"]])
            config["time_limit"] = 0.0
            fingerprint = dict(original.fingerprint)
            fingerprint.update({"command": subprocess.list2cmdline(command), "command_argv": command, "config": config, "config_hash": _q4_config_digest(config)})
            plan = CommandPlan(tuple(command), original.marker, fingerprint, original.env)
            result = execute_plan((plan,), execute=True)
            self.assertEqual(result[0]["status"], "completed")
            self.assertEqual(_validate_completed(plan)["status"], "timeout")

    def test_q4_full_preflight_rejects_partial_before_any_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = replace(build_specs()["q4"], output_root=tmp)
            plans = build_plan(spec)
            plans[-1].marker.parent.mkdir(parents=True)
            (plans[-1].marker.parent / "partial.txt").write_text("partial", encoding="utf-8")
            with self.assertRaises(FreezeError):
                execute_plan(plans, execute=True)
            self.assertFalse(plans[0].marker.exists())

    def test_q4_directory_summary_injects_plan_config_id_and_rejects_forged_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = replace(build_specs()["q4"], output_root=tmp)
            plans = build_plan(spec)
            for plan in plans:
                fp = plan.fingerprint
                payload = {"problem": "Q4", "instance": fp["instance"], "geometry": fp["geometry"],
                           "b1_beam_thickness": fp["b1_beam_thickness"], "domain": fp["domain"],
                           "mode": fp["mode"], "seed": fp["seed"], "data_hash": fp["data_hash"],
                           "code_hash": fp["code_hash"], "config": fp["config"], "config_hash": fp["config_hash"],
                           "command": fp["command"], "command_argv": fp["command_argv"],
                           "environment": {"omp_num_threads": "1", "mkl_num_threads": "1", "openblas_num_threads": "1"},
                           "status": "timeout", "formal": {}, "audit": {}, "formal_audit_match": False,
                           "domain_formal": {}, "domain_audit": {}, "domain_audit_match": False}
                plan.marker.parent.mkdir(parents=True, exist_ok=True)
                plan.marker.write_text(json.dumps(payload), encoding="utf-8")
                (plan.marker.parent / "v3_freeze.json").write_text(json.dumps(dict(fp)), encoding="utf-8")
            summary = summarize_directory("q4", root)
            self.assertEqual(summary["registered_slots"], 726)
            self.assertEqual(summary["discovered_slots"], 726)
            first_sidecar = plans[0].marker.parent / "v3_freeze.json"
            forged = json.loads(first_sidecar.read_text(encoding="utf-8"))
            forged["config_id"] = "forged"
            first_sidecar.write_text(json.dumps(forged), encoding="utf-8")
            with self.assertRaises(FreezeError):
                summarize_directory("q4", root)
    def test_workers_are_frozen_by_problem(self):
        specs = build_specs()
        self.assertEqual(specs["q1"].workers, 8)
        self.assertEqual(specs["q2"].processes, 4)
        self.assertEqual(specs["q2"].threads, 1)
        self.assertEqual(specs["q2"].workers, 4)
        self.assertEqual(specs["q3"].workers, 4)  # Q3 inner cold-seed workers; outer route execution stays serial.

    def test_q3_n300_holdout_is_single_route_bounded_and_independent(self):
        spec = build_holdout_spec()
        check_holdout_spec(spec)
        plan = build_holdout_plan(spec, "holdout_test")
        payload = dry_run_payload(spec, plan, "holdout_test")

        self.assertEqual(spec.instance, "n300")
        self.assertEqual(spec.candidates, ("Q3-BIN",))
        self.assertEqual(spec.seeds, Q3_HOLDOUT_COLD_SEEDS)
        self.assertEqual(spec.final_seeds, Q3_HOLDOUT_FINAL_SEEDS)
        self.assertEqual((spec.processes, spec.workers, spec.threads), (4, 4, 1))
        self.assertEqual(payload["max_thresholds"], 7)
        self.assertEqual(payload["max_threshold_attempts"], 210)
        self.assertEqual(payload["max_final_attempts"], 30)
        self.assertEqual(payload["max_attempts"], 240)
        self.assertLessEqual(payload["estimated_runtime_minutes"]["upper"], 95)
        self.assertTrue(all(payload["gate"].values()))
        command = " ".join(plan.command)
        self.assertIn("Q3-BIN", command)
        self.assertNotIn("Q3-LIN", command)
        self.assertNotIn("Q3-CONT-R", command)
        self.assertIn("3301-3330", command)
        self.assertIn("3401-3430", command)
        self.assertIn("--stop-submissions-after 6000.0", command)
        self.assertIn("--hard-stop-after 6260.0", command)
        self.assertEqual({Path(item["path"]).name for item in payload["data_files"]}, {"n300.blocks", "n300.nets", "n300.pl"})

        with self.assertRaises(FreezeError):
            check_holdout_spec(replace(spec, candidates=("Q3-BIN", "Q3-LIN")))

    def test_q1_execution_manifest_is_immutable_run_snapshot(self):
        payload = json.loads(Path("outputs/q1/tables/v3_n200_execution_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["execution_runner_sha"], "c5701e2a1c429f67aa20141e5c114741d2e50ab3151875a4ee160e39d1e19bb0")
        self.assertEqual(payload["execution_overall"], "67cae4dceb0bcd8b0c01d21f6513782ba3fd8bb70dfcba659bcb4179ad02d2ef")
        self.assertEqual(payload["base_commit"], "832e8bde7d9a857c4023693f1a67249e25f07d5d")
        self.assertEqual(payload["q1_frozen_payload"]["spec"]["workers"], 8)
        self.assertEqual(len(payload["q1_frozen_payload"]["commands"]), 7)

    def test_q1_execute_preflights_all_slots_before_starting_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans = []
            for index in range(140):
                marker = root / f"config_{index}" / "seed_2201" / "events.jsonl"
                fingerprint = {"problem": "q1", "instance": "n200", "config_id": f"C{index}", "seed": 2201,
                               "code_hash": "a" * 64, "config_hash": "b" * 64, "data_hash": "c" * 64,
                               "environment": {"workers": 8}}
                plans.append(CommandPlan((sys.executable, str(marker)), marker, fingerprint))
            partial = plans[-1].marker.parent
            partial.mkdir(parents=True)
            (partial / "partial.txt").write_text("interrupted", encoding="utf-8")
            with patch("src.v3.subprocess.run") as run:
                with self.assertRaises(FreezeError):
                    execute_plan(tuple(plans), execute=True)
                run.assert_not_called()
            self.assertFalse(any(plan.marker.parent.exists() for plan in plans[:-1]))

    def test_q1_execute_is_bounded_ordered_and_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans = []
            for index in range(16):
                marker = root / f"config_{index}" / "seed_2201" / "events.jsonl"
                fingerprint = {"problem": "q1", "instance": "n200", "config_id": f"C{index}", "seed": 2201,
                               "code_hash": "a" * 64, "config_hash": "b" * 64, "data_hash": "c" * 64,
                               "environment": {"workers": 8}}
                plans.append(CommandPlan((sys.executable, str(marker)), marker, fingerprint))
            lock = threading.Lock()
            active = 0
            maximum = 0

            def fake_run(command, **_kwargs):
                nonlocal active, maximum
                marker = Path(command[1])
                with lock:
                    active += 1
                    maximum = max(maximum, active)
                time.sleep(0.01)
                record = {**next(plan.fingerprint for plan in plans if plan.marker == marker),
                          "status": "success", "formal_audit_match": True}
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(json.dumps(record) + "\n", encoding="utf-8")
                with lock:
                    active -= 1
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("src.v3.subprocess.run", side_effect=fake_run):
                result = execute_plan(tuple(plans), execute=True)
            self.assertEqual([item["index"] for item in result], list(range(16)))
            self.assertTrue(all(item["status"] == "completed" for item in result))
            self.assertEqual(maximum, 8)
            self.assertEqual(len({item["marker"] for item in result}), 16)

    def test_q3_outer_execution_stays_serial_when_inner_workers_are_four(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans = []
            for index in range(8):
                marker = root / f"route_{index}" / "result.jsonl"
                fingerprint = {"problem": "q3", "instance": "n200", "config_id": f"Q3-{index}", "seed": 2201,
                               "code_hash": "a" * 64, "config_hash": "b" * 64, "data_hash": "c" * 64,
                               "environment": {"workers": 4}}
                plans.append(CommandPlan((sys.executable, str(marker)), marker, fingerprint))
            lock = threading.Lock()
            active = 0
            maximum = 0

            def fake_run(command, **_kwargs):
                nonlocal active, maximum
                marker = Path(command[1])
                with lock:
                    active += 1
                    maximum = max(maximum, active)
                time.sleep(0.01)
                plan = next(plan for plan in plans if plan.marker == marker)
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(json.dumps({**plan.fingerprint, "status": "success", "formal_audit_match": True}) + "\n", encoding="utf-8")
                with lock:
                    active -= 1
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("src.v3.subprocess.run", side_effect=fake_run):
                result = execute_plan(tuple(plans), execute=True)
            self.assertEqual([item["index"] for item in result], list(range(8)))
            self.assertEqual(maximum, 1)

    def test_q1_interrupt_cancels_unstarted_futures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans = []
            for index in range(32):
                marker = root / f"config_{index}" / "seed_2201" / "events.jsonl"
                fingerprint = {"problem": "q1", "instance": "n200", "config_id": f"C{index}", "seed": 2201,
                               "code_hash": "a" * 64, "config_hash": "b" * 64, "data_hash": "c" * 64,
                               "environment": {"workers": 8}}
                plans.append(CommandPlan((sys.executable, str(marker)), marker, fingerprint))
            with patch("src.v3._execute_one", side_effect=KeyboardInterrupt) as run:
                with self.assertRaises(KeyboardInterrupt):
                    execute_plan(tuple(plans), execute=True)
                self.assertLessEqual(run.call_count, 8)

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
        next(item for item in broken["code_files"] if item["path"] != "src/v3.py")["sha256"] = "0" * 64
        with self.assertRaises(FreezeError):
            check_registered(broken, frozen)

        broken = json.loads(json.dumps(actual))
        command = broken["commands"][0]["command"]
        command[command.index("--max-evaluations") + 1] = "1"
        with self.assertRaises(FreezeError):
            check_registered(broken, frozen)

    def test_completed_marker_allows_host_paths_but_rejects_budget_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = replace(build_specs()["q2"], output_root=tmp, seeds=(2201,))
            plan = build_plan(spec)[0]
            fingerprint = json.loads(json.dumps(plan.fingerprint))
            fingerprint["command"][0] = r"E:\python.exe"
            output_index = fingerprint["command"].index("--output-root") + 1
            fingerprint["command"][output_index] = r"E:\historical-output"
            fingerprint["environment"].update({
                "python_executable": r"E:\python.exe",
                "platform": "Windows-historical",
                "logical_cpu_count": 12,
            })
            plan.marker.parent.mkdir(parents=True)
            (plan.marker.parent / "v3_freeze.json").write_text(json.dumps(fingerprint), encoding="utf-8")
            record = {key: plan.fingerprint[key] for key in (
                "problem", "instance", "config_id", "seed", "code_hash", "config_hash", "data_hash"
            )}
            record.update({"status": "timeout", "formal_audit_match": True})
            plan.marker.write_text(json.dumps(record) + "\n", encoding="utf-8")
            self.assertEqual(_validate_completed(plan)["status"], "timeout")

            fingerprint["command"][fingerprint["command"].index("--max-evaluations") + 1] = "1"
            (plan.marker.parent / "v3_freeze.json").write_text(json.dumps(fingerprint), encoding="utf-8")
            with self.assertRaises(FreezeError):
                _validate_completed(plan)

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
                          "first_feasible_time": 0.01,
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

    def test_q2_first_feasible_comparison_uses_time_not_evaluation_count(self):
        rows = [
            {"config_id": "P1", "status": "success", "legal": True, "formal_audit_match": True,
             "HPWL": 10.0, "first_feasible_evaluation": 1, "first_feasible_time": 0.01},
            {"config_id": "P2", "status": "success", "legal": True, "formal_audit_match": True,
             "HPWL": 10.0, "first_feasible_evaluation": 1, "first_feasible_time": 0.20},
        ]
        summaries = summarize_q2(rows)
        by_id = {row["config_id"]: row for row in summaries}
        self.assertEqual(by_id["P1"]["median_first_feasible_time"], 0.01)
        self.assertEqual(by_id["P2"]["median_first_feasible_time"], 0.20)
        decision = q2_mechanical_decision([
            {**by_id[config_id], "registered_runs": 1, "missing_runs": 0, "audit_match_runs": 20,
             "checkpoint_median_best_so_far_HPWL": {str(point): None for point in (25, 50, 75, 100)}}
            for config_id in ("P1", "P2")
        ])
        self.assertFalse(decision["first_feasible"])
        self.assertEqual(decision["p2_same_budget"], "report_only")

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
                                          "median_first_feasible_evaluation": 1, "median_first_feasible_time": 0.01}
        q1 = q1_mechanical_decision([good(name, "area") for name in ("Q1-G", "Q1-SP", "Q1-BT", "Q1-BT-D", "Q1-BT-both", "Q1-BT-directed-only", "Q1-BT-dedup-only")])
        self.assertEqual(q1["decision"], "selected")
        self.assertEqual([row["config_id"] for row in q1["rankings"]], ["Q1-BT", "Q1-BT-D", "Q1-G", "Q1-SP"])
        self.assertNotIn("Q1-BT-both", [row["config_id"] for row in q1["rankings"]])
        self.assertEqual(set(q1["ablation_completeness"]), {"Q1-BT-both", "Q1-BT-directed-only", "Q1-BT-dedup-only"})
        self.assertIn("p2_legal_noninferior", q1)
        missing = q1_mechanical_decision([good(name, "area") for name in ("Q1-G", "Q1-SP", "Q1-BT")])
        self.assertEqual(missing["decision"], "blocked_missing_main_candidate")
        q2 = q2_mechanical_decision([good(name, "HPWL") for name in ("P0", "P1", "P2")])
        self.assertEqual(q2["decision"], "selected")
        routes = {name: {"d_robust": 0.1 if name == "Q3-BIN" else 0.105, "final_legal_rate": 1.0,
                         "final_median_HPWL": 10.0, "final_iqr_HPWL": 1.0} for name in ("Q3-BIN", "Q3-LIN", "Q3-CONT-R")}
        self.assertEqual(q3_mechanical_decision(routes)["selected"], "Q3-BIN")

    def test_q1_summary_min_max_and_first_feasible_protocol_deviation(self):
        rows = [{"config_id": config, "seed": 2201, "area": area, "aspect_ratio": aspect,
                 "legal": True, "formal_audit_match": True, "status": "timeout"}
                for config, area, aspect in (("Q1-G", 10, 2), ("Q1-SP", 11, 3), ("Q1-BT", 12, 4), ("Q1-BT-D", 13, 5))]
        summary = next(item for item in summarize_q1(rows, (2201,)) if item["config_id"] == "Q1-G")
        self.assertEqual(summary["min_area"], 10.0)
        self.assertEqual(summary["max_area"], 10.0)
        self.assertEqual(summary["min_aspect_ratio"], 2.0)
        self.assertEqual(summary["max_aspect_ratio"], 2.0)
        self.assertEqual(summary["first_feasible_status"], "not_recorded_protocol_deviation")

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
        self.assertEqual(build_specs()["q4"].data_hash, EXTERNAL_DATA_MANIFEST_HASH)
        self.assertEqual(checklist["data_hash"], EXTERNAL_DATA_MANIFEST_HASH)
        self.assertEqual(checklist["status"], "frozen_integer_domain_pending_main_run_review")
        self.assertEqual(checklist["continuous_domain_confirmed"], False)
        check_q4_extension(checklist)
        self.assertEqual(check_q4_registered()["config_hash"], checklist["config_hash"])
        with self.assertRaises(FreezeError):
            check_q4_extension({**checklist, "n200_selection": True})


if __name__ == "__main__":
    unittest.main()
