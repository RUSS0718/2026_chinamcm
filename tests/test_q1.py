import random
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from src._internal.audit import audit_layout
from src._internal.evaluator import evaluate
from src._internal.parser import parse_blocks_text
from src._internal.q1_solver import BTreeState, Q1SearchConfig, pack_btree, search_q1
from src.q1 import main


BLOCKS = """NumHardBlocks : 4
NumTerminals : 0
a block 4 (0, 0) (0, 1) (2, 1) (2, 0)
b block 4 (0, 0) (0, 2) (1, 2) (1, 0)
c block 4 (0, 0) (0, 1) (1, 1) (1, 0)
d block 4 (0, 0) (0, 3) (2, 3) (2, 0)
"""


class Q1SolverTests(unittest.TestCase):
    def setUp(self):
        self.instance, issues = parse_blocks_text(BLOCKS)
        self.assertEqual(issues, ())

    def test_complete_tree_and_random_moves_preserve_invariants(self):
        rng = random.Random(1101)
        state = BTreeState.complete(tuple(self.instance.blocks), rng)
        for _ in range(500):
            state.move_random(rng)
            state.rotate_random(rng)
            state.swap_random(rng)
            state.validate()

    def test_contour_places_left_right_children(self):
        state = BTreeState(
            labels=["a", "b", "c", "d"],
            left=[1, None, None, None],
            right=[2, None, 3, None],
            parent=[None, 0, 0, 2],
            rotations=[0, 0, 0, 0],
        )
        packed = pack_btree(state, self.instance.blocks)
        self.assertEqual(packed.layout["a"], (0.0, 0.0, 0))
        self.assertEqual(packed.layout["b"], (2.0, 0.0, 0))
        self.assertEqual(packed.layout["c"], (0.0, 1.0, 0))
        self.assertEqual(packed.layout["d"], (0.0, 2.0, 0))
        self.assertEqual((packed.width, packed.height), (3.0, 5.0))
        self.assertTrue(evaluate(self.instance, packed.layout).legal)

    def test_rotations_and_random_packing_are_legal_and_audited(self):
        rng = random.Random(2201)
        for _ in range(100):
            state = BTreeState.complete(tuple(self.instance.blocks), rng)
            packed = pack_btree(state, self.instance.blocks)
            formal = evaluate(self.instance, packed.layout).as_dict()
            audited = audit_layout(self.instance, packed.layout)
            self.assertTrue(formal["legal"])
            self.assertEqual(formal, audited)

    def test_search_is_reproducible_and_p2_switches_are_recorded(self):
        base = Q1SearchConfig(max_evaluations=500, time_limit=10, restarts=1, calibration_samples=5)
        first = search_q1(self.instance, base, 3301)
        second = search_q1(self.instance, base, 3301)
        self.assertEqual(first.as_dict() | {"runtime": 0}, second.as_dict() | {"runtime": 0})
        self.assertEqual(first.best.layout, second.best.layout)
        p2 = Q1SearchConfig(candidate="Q1-BT-D", directed_moves=True, state_dedup=True, max_evaluations=500, time_limit=10, restarts=1, calibration_samples=5)
        enhanced = search_q1(self.instance, p2, 3301)
        self.assertGreaterEqual(enhanced.duplicate_rejections, 0)
        self.assertTrue(enhanced.formal_metrics["legal"])
        self.assertEqual(enhanced.formal_metrics, enhanced.audit_metrics)

    def test_cli_writes_budgeted_run_record_and_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main([
                    "run",
                    "--instance", "n100",
                    "--candidate", "Q1-BT",
                    "--seed", "1101",
                    "--max-evaluations", "120",
                    "--time-limit", "10",
                    "--restarts", "1",
                    "--raw", "data/raw/附件",
                    "--output-root", tmp,
                    "--config-id", "cli-test",
                ])
            self.assertEqual(code, 0)
            record = json.loads(output.getvalue())
            self.assertEqual(record["evaluations"], 120)
            self.assertTrue(Path(record["layout_path"]).is_file())
            self.assertTrue(Path(record["log_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
