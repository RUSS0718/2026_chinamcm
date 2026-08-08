import json
import hashlib
import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.q4_v2 import build_deliverables

from src.Q4 import (
    DEFAULT_MODULES,
    Q4Block,
    Q4Instance,
    bbox,
    evaluate_layout,
    formal_audit_match,
    polygon_area,
    rotate_normalized,
    solve_exact,
    solve_sa,
)


class Q4GeometryTests(unittest.TestCase):
    def test_confirmed_local_vertices_and_areas(self):
        self.assertEqual(DEFAULT_MODULES["b1"], ((1, 0), (3, 0), (3, 2), (4, 2), (4, 4), (0, 4), (0, 2), (1, 2)))
        self.assertEqual(DEFAULT_MODULES["b2"], ((0, 0), (2, 0), (2, 2), (1, 2), (1, 4), (0, 4)))
        self.assertEqual(DEFAULT_MODULES["b3"], ((0, 0), (2, 0), (2, 1), (0, 1)))
        self.assertEqual(DEFAULT_MODULES["b4"], ((0, 0), (1, 0), (1, 4), (0, 4)))
        self.assertEqual({name: polygon_area(poly) for name, poly in DEFAULT_MODULES.items()}, {"b1": 12, "b2": 6, "b3": 2, "b4": 4})

    def test_four_rotations_normalize_to_lower_left_bbox(self):
        expected = {
            0: ((1, 0), (3, 0), (3, 2), (4, 2), (4, 4), (0, 4), (0, 2), (1, 2)),
            90: ((4, 1), (4, 3), (2, 3), (2, 4), (0, 4), (0, 0), (2, 0), (2, 1)),
            180: ((3, 4), (1, 4), (1, 2), (0, 2), (0, 0), (4, 0), (4, 2), (3, 2)),
            270: ((0, 3), (0, 1), (2, 1), (2, 0), (4, 0), (4, 4), (2, 4), (2, 3)),
        }
        for rotation, polygon in expected.items():
            actual = rotate_normalized(DEFAULT_MODULES["b1"], rotation)
            self.assertEqual(actual, polygon)
            self.assertEqual(bbox(actual), (4, 4))
            self.assertEqual(min(x for x, _ in actual), 0)
            self.assertEqual(min(y for _, y in actual), 0)
            self.assertEqual(polygon_area(actual), 12)

    def test_boundary_contact_is_legal_but_positive_overlap_is_not(self):
        instance = Q4Instance.default()
        touching = {
            "b1": (0, 0, 0),
            "b2": (4, 0, 0),
            "b3": (6, 0, 0),
            "b4": (8, 0, 0),
        }
        overlap = dict(touching, b2=(3, 0, 0))
        self.assertTrue(evaluate_layout(instance, touching).legal)
        self.assertFalse(evaluate_layout(instance, overlap).legal)

    def test_concave_nested_region_and_formal_audit_match(self):
        instance = Q4Instance({
            "l": Q4Block("l", ((0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3))),
            "s": Q4Block("s", ((0, 0), (1, 0), (1, 1), (0, 1))),
        })
        self.assertTrue(evaluate_layout(instance, {"l": (0, 0, 0), "s": (1, 1, 0)}).legal)
        self.assertFalse(evaluate_layout(instance, {"l": (0, 0, 0), "s": (0, 0, 0)}).legal)
        self.assertTrue(formal_audit_match(Q4Instance.default(), {
            "b1": (0, 0, 0), "b2": (4, 0, 0), "b3": (6, 0, 0), "b4": (8, 0, 0)
        }))

    def test_hand_layout_metrics_and_fixed_outline(self):
        layout = {"b1": (0, 0, 0), "b2": (4, 0, 0), "b3": (6, 0, 0), "b4": (8, 0, 0)}
        result = evaluate_layout(Q4Instance.default(), layout)
        self.assertEqual((result.width, result.height, result.area), (9, 4, 36))
        self.assertEqual((result.module_area, result.deadspace), (24, 12))
        self.assertEqual(result.dead_space_ratio, 0.5)
        fixed = evaluate_layout(Q4Instance.default(), layout, (9, 4))
        self.assertTrue(fixed.legal)
        self.assertFalse(evaluate_layout(Q4Instance.default(), layout, (8, 4)).legal)
        self.assertTrue(formal_audit_match(Q4Instance.default(), layout, (9, 4)))

    def test_exact_solver_reports_complete_optimal_domain_result(self):
        tiny = Q4Instance({
            "a": Q4Block("a", ((0, 0), (1, 0), (1, 1), (0, 1))),
            "b": Q4Block("b", ((0, 0), (1, 0), (1, 1), (0, 1))),
        })
        result = solve_exact(tiny, upper_area=2)
        self.assertEqual(result.status, "optimal")
        self.assertTrue(result.complete)
        self.assertEqual((result.evaluation.area, result.lower_bound, result.upper_bound), (2, 2, 2))
        self.assertTrue(result.formal_audit_match)
        self.assertEqual(result.audit["area"], 2)
        self.assertTrue(result.evaluation.legal)
        self.assertGreaterEqual(result.runtime, 0)

    def test_exact_timeout_keeps_independent_row_incumbent_and_bounds(self):
        result = solve_exact(Q4Instance.default(), upper_area=36, time_limit=0)
        self.assertEqual(result.status, "timeout")
        self.assertIsNotNone(result.layout)
        self.assertIsNotNone(result.evaluation)
        self.assertTrue(result.evaluation.legal)
        self.assertEqual(result.upper_bound, 36)
        self.assertEqual(result.lower_bound, 24)
        self.assertEqual(result.audit["area"], 36)

    def test_exact_no_feasible_does_not_report_fake_upper_bound(self):
        impossible = Q4Instance({
            "a": Q4Block("a", DEFAULT_MODULES["b1"]),
            "b": Q4Block("b", DEFAULT_MODULES["b1"]),
        })
        result = solve_exact(impossible, upper_area=24)
        self.assertEqual(result.status, "no_feasible")
        self.assertTrue(result.complete)
        self.assertIsNone(result.upper_bound)
        self.assertIsNone(result.evaluation)

    def test_sa_small_budget_is_reproducible_and_not_exact_seeded(self):
        first = solve_sa(Q4Instance.default(), seed=17, max_evaluations=30, time_limit=2, restarts=1)
        second = solve_sa(Q4Instance.default(), seed=17, max_evaluations=30, time_limit=2, restarts=1)
        self.assertEqual(first.status, "success")
        self.assertEqual(first.evaluations, 30)
        self.assertEqual(first.layout, second.layout)
        self.assertEqual(first.evaluation.area, second.evaluation.area)
        self.assertEqual(first.initial_area, 36)
        self.assertTrue(first.formal_audit_match)
        self.assertEqual(first.audit["area"], first.evaluation.area)
        self.assertGreaterEqual(first.runtime, 0)

    def test_sa_budget_is_shared_deterministically_across_restarts(self):
        result = solve_sa(Q4Instance.default(), seed=17, max_evaluations=4, time_limit=2, restarts=2)
        self.assertEqual(result.evaluations, 4)
        self.assertEqual(result.restarts_completed, 2)

    def test_cli_sa_smoke_writes_traceable_json(self):
        with tempfile.TemporaryDirectory() as directory:
            output = f"{directory}/q4_sa.json"
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "src.Q4", "sa", "--seed", "17", "--max-evaluations", "5", "--time-limit", "2", "--restarts", "1", "--output", output],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(Path(output).read_text(encoding="utf-8"))
            self.assertEqual(payload["problem"], "Q4")
            self.assertIn(payload["status"], {"success", "timeout"})
            self.assertTrue(payload["code_hash"])
            self.assertTrue(payload["config_hash"])
            self.assertIn("formal", payload)
            self.assertIn("audit", payload)
            self.assertIn("layout", payload)
            self.assertEqual(payload["formal"]["legal"], payload["audit"]["legal"])
            self.assertEqual(payload["formal"]["area"], payload["audit"]["area"])
            self.assertEqual(payload["formal"]["module_area"], payload["audit"]["module_area"])
            self.assertEqual(set(payload["config"]), {"seed", "max_evaluations", "time_limit", "restarts", "domain", "temperature_schedule", "grid_step", "rotations", "search_domain"})
            self.assertNotIn("output", payload["config"])
            self.assertEqual(payload["command"].split()[0], sys.executable)
            self.assertEqual(payload["environment"]["cwd"], str(Path.cwd()))
            self.assertIn("cpu_count", payload["environment"])
            self.assertTrue(payload["code_manifest"])
            for entry in payload["code_manifest"]:
                self.assertEqual(set(entry), {"path", "bytes", "sha256"})
            digest = hashlib.sha256()
            for entry in payload["code_manifest"]:
                data = Path(entry["path"]).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                self.assertEqual(entry["bytes"], len(data))
                self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
                digest.update(entry["path"].encode("utf-8"))
                digest.update(data)
            self.assertEqual(payload["code_hash"], digest.hexdigest())
            self.assertEqual({entry["path"] for entry in payload["code_manifest"]}, {"src/Q4/__init__.py", "src/Q4/__main__.py", "src/Q4/geometry.py", "src/Q4/model.py", "src/Q4/sa.py", "src/Q4/search.py", "src/_internal/audit.py"})
            self.assertIn("-B -m src.Q4", payload["command"])

    def test_exact_timeout_without_incumbent_has_no_upper_bound(self):
        impossible = Q4Instance({
            "a": Q4Block("a", DEFAULT_MODULES["b1"]),
            "b": Q4Block("b", DEFAULT_MODULES["b1"]),
        })
        result = solve_exact(impossible, upper_area=24, time_limit=0)
        self.assertEqual(result.status, "timeout")
        self.assertIsNone(result.upper_bound)

    def test_solver_rejects_invalid_configuration(self):
        with self.assertRaises(ValueError):
            solve_sa(max_evaluations=0)
        with self.assertRaises(ValueError):
            solve_sa(restarts=0)
        with self.assertRaises(ValueError):
            solve_sa(domain=(0, 9))
        with self.assertRaises(ValueError):
            solve_sa(time_limit=-1)
        with self.assertRaises(ValueError):
            solve_exact(upper_area=23)
        with self.assertRaises(ValueError):
            solve_exact(time_limit=-1)

    def test_deliverable_gate_allows_failure_status_for_registered_seed(self):
        payload = json.loads(Path("outputs/q4/_runtime/v2/sa/seed_1101.json").read_text(encoding="utf-8"))
        payload["status"] = "timeout"
        payload["result"]["status"] = "timeout"
        payload["formal_audit_match"] = False
        build_deliverables.check_sa(payload, 1101)

    def test_deliverable_gate_compares_all_audit_metrics_and_layout(self):
        payload = json.loads(Path("outputs/q4/_runtime/v2/sa/seed_1108.json").read_text(encoding="utf-8"))
        tampered_audit = copy.deepcopy(payload)
        tampered_audit["audit"]["HPWL"] = 1
        with self.assertRaises(SystemExit):
            build_deliverables.check_sa(tampered_audit, 1108)
        tampered_layout = copy.deepcopy(payload)
        tampered_layout["layout"]["b1"]["x"] += 1
        with self.assertRaises(SystemExit):
            build_deliverables.check_sa(tampered_layout, 1108)

    def test_deliverable_stats_keep_failures_out_of_success_metrics(self):
        rows = [
            {"status": "success", "area": 24},
            {"status": "timeout", "area": 24},
            {"status": "crash", "area": ""},
        ]
        self.assertEqual(build_deliverables.success_rows(rows), [rows[0]])

    def test_rotated_modules_keep_area_and_extent_and_audit(self):
        for name, polygon in DEFAULT_MODULES.items():
            expected_area = {"b1": 12, "b2": 6, "b3": 2, "b4": 4}[name]
            expected_extents = {
                "b1": (4, 4),
                "b2": ((2, 4), (4, 2)),
                "b3": ((2, 1), (1, 2)),
                "b4": ((1, 4), (4, 1)),
            }[name]
            for rotation in (0, 90, 180, 270):
                rotated = rotate_normalized(polygon, rotation)
                self.assertEqual(polygon_area(rotated), expected_area)
                self.assertEqual(bbox(rotated), expected_extents if isinstance(expected_extents[0], int) else expected_extents[rotation in (90, 270)])
        layout = {"b1": (0, 0, 90), "b2": (4, 0, 180), "b3": (6, 0, 270), "b4": (8, 0, 90)}
        self.assertTrue(formal_audit_match(Q4Instance.default(), layout))

    def test_cli_exact_timeout_smoke_keeps_traceable_incumbent(self):
        with tempfile.TemporaryDirectory() as directory:
            output = f"{directory}/q4_exact.json"
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "src.Q4", "exact", "--upper-area", "36", "--time-limit", "0", "--output", output],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(Path(output).read_text(encoding="utf-8"))
            self.assertEqual(payload["mode"], "exact")
            self.assertEqual(payload["status"], "timeout")
            self.assertEqual(payload["formal"]["area"], 36)
            self.assertEqual(payload["audit"]["area"], 36)
            self.assertEqual(set(payload["config"]), {"upper_area", "time_limit", "grid_step", "rotations", "search_domain"})
            self.assertEqual(payload["config"]["grid_step"], 1)
            self.assertEqual(payload["config"]["rotations"], [0, 90, 180, 270])
            self.assertEqual(payload["domain"]["containers_total"], payload["result"]["domain"]["containers_total"])
            self.assertEqual(set(payload["domain"]), {"grid_step", "rotations", "search_domain", "area_lower_bound", "area_upper_bound", "width_range", "height_range", "containers_total", "containers_checked"})

    def test_cli_rejects_invalid_configuration(self):
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "src.Q4", "sa", "--max-evaluations", "0"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "src.Q4", "sa", "--domain-width", "0"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
