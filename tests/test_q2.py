import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src._internal.audit import audit_layout
from src._internal.parser import parse_instance_files


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)

BLOCKS = """NumHardBlocks : 4
NumTerminals : 1
b0 block 4 (0, 0) (0, 1) (1, 1) (1, 0)
b1 block 4 (0, 0) (0, 1) (1, 1) (1, 0)
b2 block 4 (0, 0) (0, 1) (1, 1) (1, 0)
b3 block 4 (0, 0) (0, 1) (1, 1) (1, 0)
p0 terminal
"""
NETS = """NumNets : 3
NumPins : 7
NetDegree : 3
b0
b1
p0
NetDegree : 2
b1
b2
NetDegree : 2
b2
b3
"""
PL = """p0 4 4
"""


def write_instance(raw: Path) -> None:
    raw.mkdir(parents=True)
    (raw / "tiny.blocks").write_text(BLOCKS, encoding="utf-8")
    (raw / "tiny.nets").write_text(NETS, encoding="utf-8")
    (raw / "tiny.pl").write_text(PL, encoding="utf-8")


def run_candidate(
    raw: Path,
    output: Path,
    candidate: str,
    *,
    instance: str = "tiny",
    max_evaluations: int = 500,
    hypergraph_init: str | None = None,
) -> dict:
    command = [
            str(PYTHON),
            "-B",
            "-m",
            "src.Q2",
            "run",
            "--instance",
            instance,
            "--candidate",
            candidate,
            "--seed",
            "2101",
            "--max-evaluations",
            str(max_evaluations),
            "--time-limit",
            "5",
            "--restarts",
            "2",
            "--raw",
            str(raw),
            "--output-root",
            str(output),
        ]
    if hypergraph_init is not None:
        command.extend(["--hypergraph-init", hypergraph_init])
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return json.loads(completed.stdout)


class Q2CliTests(unittest.TestCase):
    def test_candidates_share_fixed_outline_record_and_independent_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw"
            write_instance(raw)
            records = [run_candidate(raw, root / candidate, candidate) for candidate in ("Q2-SP", "Q2-BT", "Q2-HG")]
            instance = parse_instance_files(raw / "tiny.blocks", raw / "tiny.nets", raw / "tiny.pl")
            for record in records:
                payload = json.loads(Path(record["layout_path"]).read_text(encoding="utf-8"))
                layout = {name: (item["x"], item["y"], item["rotation"]) for name, item in payload["layout"].items()}
                independent = audit_layout(instance, layout, (0.0, 0.0, record["outline_side"], record["outline_side"]))
                self.assertTrue(record["legal"])
                self.assertTrue(record["formal_audit_match"])
                self.assertEqual(record["HPWL"], independent["HPWL"])
                self.assertLessEqual(record["placement_width"], record["outline_side"])
                self.assertLessEqual(record["placement_height"], record["outline_side"])
                self.assertEqual(record["boundary_overflow"], 0.0)
                self.assertTrue(math.isclose(record["dead_space_ratio"], 0.15))
                self.assertTrue(math.isclose(record["rho"], 0.15 / 1.15))
            self.assertEqual([record["hypergraph_init"] for record in records], [False, False, True])
            self.assertEqual([record["adaptive_constraints"] for record in records], [False, True, True])

    def test_p0_has_a_legal_fixed_outline_initialization_for_n100(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = run_candidate(
                ROOT / "data" / "raw" / "附件",
                Path(tmp),
                "Q2-SP",
                instance="n100",
                max_evaluations=1,
            )
        self.assertTrue(record["legal"])
        self.assertEqual(record["first_feasible_evaluation"], 1)

    def test_p1_has_a_legal_fixed_outline_initialization_for_n100(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = run_candidate(
                ROOT / "data" / "raw" / "附件",
                Path(tmp),
                "Q2-BT",
                instance="n100",
                max_evaluations=1,
            )
        self.assertTrue(record["legal"])
        self.assertEqual(record["first_feasible_evaluation"], 1)

    def test_p2_hypergraph_initialization_preserves_n100_feasibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = run_candidate(
                ROOT / "data" / "raw" / "附件",
                Path(tmp),
                "Q2-HG",
                instance="n100",
                max_evaluations=1,
                hypergraph_init="on",
            )
        self.assertTrue(record["legal"])
        self.assertEqual(record["first_feasible_evaluation"], 1)

    def test_same_seed_is_reproducible_and_p2_switch_can_be_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw"
            write_instance(raw)
            first = run_candidate(raw, root / "first", "Q2-BT")
            second = run_candidate(raw, root / "second", "Q2-BT")
            off = run_candidate(raw, root / "off", "Q2-HG", hypergraph_init="off")
            first_layout = json.loads(Path(first["layout_path"]).read_text(encoding="utf-8"))["layout"]
            second_layout = json.loads(Path(second["layout_path"]).read_text(encoding="utf-8"))["layout"]
        self.assertEqual(first_layout, second_layout)
        self.assertEqual(first["HPWL"], second["HPWL"])
        self.assertEqual(first["evaluations"], second["evaluations"])
        self.assertFalse(off["hypergraph_init"])
        self.assertTrue(off["legal"])


if __name__ == "__main__":
    unittest.main()
