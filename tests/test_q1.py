import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def run_q1(output_root: Path, candidate: str, seed: int, max_evaluations: int = 120) -> dict:
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.Q1",
            "run",
            "--instance",
            "n100",
            "--candidate",
            candidate,
            "--seed",
            str(seed),
            "--max-evaluations",
            str(max_evaluations),
            "--time-limit",
            "10",
            "--restarts",
            "1",
            "--raw",
            "data/raw/附件",
            "--output-root",
            str(output_root),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return json.loads(completed.stdout)


class Q1CliTests(unittest.TestCase):
    def test_all_candidates_write_legal_audited_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            records = [run_q1(Path(tmp) / candidate, candidate, 1101) for candidate in ("Q1-G", "Q1-SP", "Q1-BT", "Q1-BT-D")]
            self.assertTrue(all(Path(record["layout_path"]).is_file() for record in records))
            self.assertTrue(all(Path(record["log_path"]).is_file() for record in records))
        self.assertEqual([record["candidate"] for record in records], ["Q1-G", "Q1-SP", "Q1-BT", "Q1-BT-D"])
        self.assertTrue(all(record["status"] in {"success", "timeout"} for record in records))
        self.assertTrue(all(record["legal"] and record["formal_audit_match"] for record in records))

    def test_q1_g_is_deterministic_across_seeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = run_q1(Path(tmp) / "first", "Q1-G", 1101)
            second = run_q1(Path(tmp) / "second", "Q1-G", 1102)
            first_layout = json.loads(Path(first["layout_path"]).read_text(encoding="utf-8"))["layout"]
            second_layout = json.loads(Path(second["layout_path"]).read_text(encoding="utf-8"))["layout"]
        self.assertEqual(first_layout, second_layout)
        self.assertEqual(first["evaluations"], 1)
        self.assertEqual(second["evaluations"], 1)

    def test_q1_sp_is_reproducible_within_evaluation_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = run_q1(Path(tmp) / "first", "Q1-SP", 1101)
            second = run_q1(Path(tmp) / "second", "Q1-SP", 1101)
            first_layout = json.loads(Path(first["layout_path"]).read_text(encoding="utf-8"))["layout"]
            second_layout = json.loads(Path(second["layout_path"]).read_text(encoding="utf-8"))["layout"]
        self.assertEqual(first["evaluations"], 120)
        self.assertEqual(first | {"runtime": 0, "layout_path": "", "log_path": ""}, second | {"runtime": 0, "layout_path": "", "log_path": ""})
        self.assertEqual(first_layout, second_layout)


if __name__ == "__main__":
    unittest.main()
