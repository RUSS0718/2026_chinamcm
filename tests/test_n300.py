from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import src.n300 as n300
from src.v3 import FreezeError, build_plan, execute_plan


class N300HoldoutTests(unittest.TestCase):
    def test_plans_use_registered_holdout_matrix_and_n300_data(self):
        specs = n300.build_specs()
        q1, q2 = specs["q1"], specs["q2"]
        q1_plans, q2_plans = build_plan(q1), build_plan(q2)
        self.assertEqual(len(q1_plans), 90)
        self.assertEqual(len(q2_plans), 60)
        self.assertEqual(n300.Q1_CANDIDATES, ("Q1-G", "Q1-SP", "Q1-BT"))
        self.assertEqual(n300.Q2_CANDIDATES, ("P0", "P1"))
        self.assertEqual(q1.seeds, tuple(range(3301, 3331)))
        self.assertEqual(q2.seeds, tuple(range(3301, 3331)))
        self.assertEqual(set(q1.config_hashes), {"Q1-G", "Q1-SP", "Q1-BT"})
        self.assertEqual(set(q2.config_hashes), {"P0", "P1"})
        self.assertEqual((q1.workers, q2.workers), (8, 8))
        self.assertEqual((q1.threads, q2.threads), (1, 1))
        self.assertEqual((q1.budgets["time_limit"], q2.budgets["time_limit"]), (600.0, 600.0))
        self.assertTrue(all(plan.fingerprint["environment"]["workers"] == 8 for plan in q1_plans + q2_plans))
        self.assertTrue(all("--time-limit" in plan.command and "600.0" in plan.command for plan in q1_plans + q2_plans))
        self.assertEqual({item["path"] for item in n300.registered_payload(q1)["data_files"]}, {"data/raw/附件/n300.blocks"})
        self.assertEqual({item["path"] for item in n300.registered_payload(q2)["data_files"]},
                         {"data/raw/附件/n300.blocks", "data/raw/附件/n300.nets", "data/raw/附件/n300.pl"})

    def test_code_manifest_binds_runner_v3_and_algorithm_files(self):
        payload = n300.registered_payload(n300.build_specs()["q1"])
        paths = {item["path"] for item in payload["code_files"]}
        self.assertIn("src/n300.py", paths)
        self.assertIn("src/v3.py", paths)
        self.assertIn("src/Q1/__main__.py", paths)

    def test_plan_does_not_execute_and_run_requires_execute_and_manifest(self):
        with patch("builtins.print"), patch("src.n300.execute_plan") as execute:
            n300.main(["plan", "--problem", "q1"])
            execute.assert_not_called()
        with self.assertRaises(SystemExit):
            n300.main(["run", "--problem", "q1"])
        with self.assertRaises(FreezeError):
            n300.main(["run", "--problem", "q1", "--execute", "--manifest", "outputs/v3_frozen_manifest.json"])
        with self.assertRaises(FreezeError):
            n300.main(["run", "--problem", "q1", "--execute", "--manifest", "outputs/v3_n300_frozen_manifest.json"])
        with self.assertRaises(FreezeError):
            n300.main(["run", "--problem", "q1", "--execute", "--manifest", "outputs/v3_n300_frozen_manifest_v2.json"])
        with patch("src.n300._load_manifest", side_effect=FreezeError("missing test manifest")):
            with self.assertRaises(FreezeError):
                n300.main(["run", "--problem", "q1", "--execute"])

    def test_freeze_writes_one_joint_manifest_and_run_selects_problem_entry(self):
        captured = {}

        def capture(path, payload):
            captured["path"] = path
            captured["payload"] = payload

        with patch("src.n300.write_once", side_effect=capture):
            n300.main(["freeze"])
        self.assertEqual(captured["path"], n300.N300_MANIFEST_PATH)
        manifest = captured["payload"]
        self.assertEqual(manifest["protocol"], "v3_n300_holdout_v3")
        self.assertTrue({"q1", "q2"}.issubset(manifest))
        self.assertEqual(manifest["q1"]["spec"]["output_root"], n300.N300_OUTPUT_ROOTS["q1"])
        self.assertEqual(manifest["q2"]["spec"]["output_root"], n300.N300_OUTPUT_ROOTS["q2"])
        self.assertTrue(all(manifest[p]["selection_locked"] for p in ("q1", "q2")))
        self.assertEqual(manifest["q1"]["preselected"], "Q1-BT")
        self.assertEqual(manifest["q2"]["preselected"], "P1")
        self.assertEqual(manifest["q1"]["ablations"], [])
        self.assertEqual(manifest["q2"]["ablations"], [])
        for problem in ("q1", "q2"):
            with patch("src.n300._load_manifest", return_value=manifest), patch("src.n300._check_manifest") as check, patch("src.n300.execute_plan", return_value=[]):
                n300.main(["run", "--problem", problem, "--execute"])
            self.assertIs(check.call_args.args[1], manifest[problem])

    def test_cli_rejects_q3_and_q4(self):
        for problem in ("q3", "q4"):
            with self.assertRaises(SystemExit):
                n300.main(["plan", "--problem", problem])

    def test_q2_execute_groups_candidates_serially_with_eight_workers(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            spec = replace(n300.build_specs()["q2"], output_root=tmp)
            plans = build_plan(spec)

            def fake_parallel(group, workers, cwd):
                calls.append((len(group), workers))
                return [{"index": index, "status": "completed"} for index, _ in group]

            with patch("src.v3._execute_parallel", side_effect=fake_parallel), patch("src.v3._execute_one") as one:
                result = execute_plan(plans, execute=True)
        self.assertEqual(calls, [(30, 8), (30, 8)])
        one.assert_not_called()
        self.assertEqual(len(result), 60)

    def test_summary_is_fail_closed_and_selection_locked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = replace(n300.build_specs()["q1"], output_root=str(root))
            summary = n300._summary_directory("q1", root, spec)
        self.assertEqual(summary["registered_runs"], 90)
        self.assertEqual(summary["discovered_runs"], 0)
        self.assertEqual(summary["missing_runs"], 90)
        self.assertTrue(summary["selection_locked"])
        self.assertEqual(summary["preselected"], "Q1-BT")
        self.assertEqual(summary["baselines"], ["Q1-G", "Q1-SP"])
        self.assertEqual(summary["ablations"], [])
        self.assertFalse(summary["reselection_allowed"])
        self.assertIsNone(summary["mechanical_decision"]["selected"])
        self.assertEqual(set(summary["pairwise"]), {"Q1-BT_vs_Q1-G", "Q1-BT_vs_Q1-SP"})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = replace(n300.build_specs()["q2"], output_root=str(root))
            summary = n300._summary_directory("q2", root, spec)
        self.assertEqual(summary["registered_runs"], 60)
        self.assertEqual(set(summary["pairwise"]), {"P1_vs_P0"})
        self.assertEqual(summary["ablations"], [])


if __name__ == "__main__":
    unittest.main()
