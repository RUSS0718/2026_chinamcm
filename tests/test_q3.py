import ast
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.Q3 import search
from src.Q3.__main__ import _attempt_rows
from src.Q3.common import Q3Result, Q3SearchConfig, SeedAttempt, ThresholdAttempt, validate_config
from src._internal.audit import audit_layout
from src._internal.evaluator import evaluate
from src._internal.parser import parse_instance_files


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)

BLOCKS = """NumHardBlocks : 1
NumTerminals : 0
b0 block 4 (0, 0) (0, 1) (1, 1) (1, 0)
"""
NETS = """NumNets : 0
NumPins : 0
"""
PL = ""


class FakeResult:
    def __init__(
        self,
        legal: bool,
        hpwl: float | None = None,
        best_state=None,
        *,
        status: str | None = None,
    ):
        self.status = status or ("success" if legal else "no_feasible")
        self.audit_metrics = {"legal": legal}
        self._formal_metrics = {"HPWL": hpwl} if hpwl is not None else {}
        self.runtime = 0.0
        self.evaluations = 1
        self.proposals = 0
        self.accepted = 0
        self.restarts_completed = 1
        self.first_feasible_evaluation = 1 if legal else None
        self.first_feasible_time = 0.0 if legal else None
        self.error = None
        self.best_state = best_state

    @property
    def formal_metrics(self):
        return self._formal_metrics


def tiny_instance():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "tiny.blocks").write_text(BLOCKS, encoding="utf-8")
        (root / "tiny.nets").write_text(NETS, encoding="utf-8")
        (root / "tiny.pl").write_text(PL, encoding="utf-8")
        yield parse_instance_files(root / "tiny.blocks", root / "tiny.nets", root / "tiny.pl")


def threshold_config(candidate: str, *, continuous_compression: bool = False) -> Q3SearchConfig:
    return Q3SearchConfig(
        candidate=candidate,
        inner_candidate="Q2-BT",
        lower_ratio=0.0,
        upper_ratio=0.4,
        precision=0.05,
        robust_min_success_rate=1.0,
        decision_rule="any",
        seeds=(1,),
        max_evaluations=1,
        time_limit=1.0,
        restarts=1,
        continuous_compression=continuous_compression,
        final_seeds=(2,),
        final_max_evaluations=1,
        final_time_limit=1.0,
        final_restarts=1,
    )


class Q3SearchTests(unittest.TestCase):
    def test_q2_sp_inner_config_uses_classic_schedule(self):
        config = Q3SearchConfig(candidate="Q3-LIN", inner_candidate="Q2-SP")

        self.assertEqual(search._inner_config(config, 0.1).sa_schedule, "classic")

    def test_crashed_legal_cold_attempt_does_not_define_boundaries(self):
        config = Q3SearchConfig(
            robust_min_success_rate=1.0,
            seeds=(1,),
            final_seeds=(2,),
        )
        threshold = ThresholdAttempt(
            dead_space_ratio=0.1,
            outline_side=1.0,
            seed_attempts=[
                SeedAttempt(1, "cold", FakeResult(True, hpwl=1.0, status="crash")),
            ],
        )

        with (
            patch.object(search, "_threshold_search", return_value=[threshold]),
            patch.object(search, "_final_attempts", return_value=[]),
        ):
            result = search.solve_q3(object(), config)

        self.assertEqual(threshold.success_rate, 0.0)
        self.assertFalse(threshold.cold_legal_attempts)
        self.assertIsNone(result.d_best)
        self.assertIsNone(result.d_robust)

    def test_timeout_legal_attempt_counts_but_crashed_final_attempt_does_not_win(self):
        threshold = ThresholdAttempt(
            dead_space_ratio=0.1,
            outline_side=1.0,
            seed_attempts=[
                SeedAttempt(1, "cold", FakeResult(True, hpwl=0.1, status="crash")),
                SeedAttempt(2, "cold", FakeResult(True, hpwl=1.0, status="timeout")),
            ],
        )
        result = Q3Result(
            attempts=[],
            d_best=None,
            d_robust=None,
            selected_ratio=None,
            final_attempts=[
                SeedAttempt(3, "final_cold", FakeResult(True, hpwl=0.1, status="crash")),
                SeedAttempt(4, "final_cold", FakeResult(True, hpwl=1.0, status="timeout")),
            ],
        )

        self.assertEqual(threshold.success_rate, 0.5)
        self.assertEqual([attempt.seed for attempt in threshold.cold_legal_attempts], [2])
        self.assertEqual(result.final_best.seed, 4)

    def test_config_default_enables_compression_only_for_continuous_candidate(self):
        self.assertFalse(Q3SearchConfig().continuous_compression)
        self.assertFalse(Q3SearchConfig(candidate="Q3-BIN").continuous_compression)
        self.assertTrue(Q3SearchConfig(candidate="Q3-CONT-R").continuous_compression)
        self.assertFalse(
            Q3SearchConfig(candidate="Q3-CONT-R", continuous_compression=False).continuous_compression
        )

    def test_n100_default_seeds_follow_collaboration_protocol(self):
        config = Q3SearchConfig()
        self.assertEqual(config.seeds, tuple(range(1101, 1111)))
        self.assertEqual(config.final_seeds, tuple(range(1101, 1111)))
        self.assertEqual(config.robust_min_success_rate, 0.8)
        self.assertEqual(config.workers, 1)
        self.assertEqual(config.as_dict()["workers"], 1)

    def test_robust_decision_requires_eight_of_ten_cold_runs(self):
        config = Q3SearchConfig(
            robust_min_success_rate=0.8,
            decision_rule="robust",
            seeds=tuple(range(10)),
            final_seeds=(99,),
        )

        def threshold_with_cold_successes(count: int) -> ThresholdAttempt:
            attempts = [
                SeedAttempt(seed, "cold", FakeResult(seed < count, hpwl=1.0 if seed < count else None))
                for seed in range(10)
            ]
            return ThresholdAttempt(0.1, 1.0, attempts)

        eight = threshold_with_cold_successes(8)
        seven = threshold_with_cold_successes(7)
        self.assertTrue(search._decision(eight, config))
        self.assertFalse(search._decision(seven, config))
        self.assertEqual(search._minimum_ratio([eight, seven], config, robust=True), 0.1)

    def test_best_warm_state_uses_best_legal_warm_or_cold_state(self):
        attempt = ThresholdAttempt(
            dead_space_ratio=0.1,
            outline_side=1.0,
            seed_attempts=[
                SeedAttempt(1, "warm", FakeResult(True, hpwl=0.1, best_state="warm-state")),
                SeedAttempt(1, "cold", FakeResult(True, hpwl=1.0, best_state="cold-state")),
                SeedAttempt(2, "cold", FakeResult(False)),
            ],
        )
        self.assertEqual(search._best_warm_state(attempt), "warm-state")

    def test_linear_and_binary_outer_threshold_sequences_differ(self):
        instance = next(tiny_instance())
        observed = {}

        def fake_inner(_instance, config, _seed, warm_state=None):
            observed.setdefault(config.dead_space_ratio, []).append(warm_state)
            legal = config.dead_space_ratio >= 0.15
            return FakeResult(
                legal,
                hpwl=1.0 if legal else None,
                best_state=f"state-{config.dead_space_ratio}",
            )

        with patch.object(search, "_run_inner", side_effect=fake_inner):
            linear = search._threshold_search(instance, threshold_config("Q3-LIN"))
            binary = search._threshold_search(instance, threshold_config("Q3-BIN"))

        linear_ratios = [attempt.dead_space_ratio for attempt in linear]
        binary_ratios = [attempt.dead_space_ratio for attempt in binary]
        self.assertNotEqual(linear_ratios, binary_ratios)
        self.assertEqual(linear_ratios, [0.4, 0.35, 0.3, 0.25, 0.2, 0.15, 0.1])
        self.assertEqual(binary_ratios, [0.4, 0.0, 0.2, 0.1, 0.15])

    def test_linear_n100_stops_at_first_failed_adjacent_ratio(self):
        instance = next(tiny_instance())
        config = Q3SearchConfig(
            candidate="Q3-LIN",
            inner_candidate="Q2-BT",
            lower_ratio=0.0,
            upper_ratio=0.15,
            precision=0.005,
            robust_min_success_rate=0.8,
            decision_rule="robust",
            seeds=tuple(range(10)),
            max_evaluations=1,
            time_limit=1.0,
            restarts=1,
            final_seeds=(99,),
            final_max_evaluations=1,
            final_time_limit=1.0,
            final_restarts=1,
            workers=1,
        )

        def fake_inner(_instance, inner_config, _seed, warm_state=None):
            legal = inner_config.dead_space_ratio >= 0.14
            return FakeResult(legal, hpwl=1.0 if legal else None, best_state="cold-state")

        with patch.object(search, "_run_inner", side_effect=fake_inner):
            attempts = search._threshold_search(instance, config)

        ratios = [attempt.dead_space_ratio for attempt in attempts]
        self.assertEqual(ratios, [0.15, 0.145, 0.14, 0.135])
        self.assertEqual(attempts[-1].success_rate, 0.0)
        self.assertFalse(search._decision(attempts[-1], config))

    def test_continuous_compression_uses_binary_and_switch_off_is_cold(self):
        instance = next(tiny_instance())
        events = []

        def fake_inner(_instance, config, _seed, warm_state=None):
            events.append((config.dead_space_ratio, warm_state))
            legal = config.dead_space_ratio >= 0.15
            return FakeResult(
                legal,
                hpwl=1.0 if legal else None,
                best_state=f"state-{config.dead_space_ratio}",
            )

        with patch.object(search, "_run_inner", side_effect=fake_inner):
            enabled = search._threshold_search(
                instance,
                threshold_config("Q3-CONT-R", continuous_compression=True),
            )
            enabled_events = list(events)
            events.clear()
            disabled = search._threshold_search(
                instance,
                threshold_config("Q3-CONT-R", continuous_compression=False),
            )
            disabled_events = list(events)

        self.assertEqual(
            [attempt.dead_space_ratio for attempt in enabled],
            [0.4, 0.0, 0.2, 0.1, 0.15],
        )
        self.assertEqual(
            [attempt.dead_space_ratio for attempt in disabled],
            [0.4, 0.0, 0.2, 0.1, 0.15],
        )
        self.assertTrue(any(state is not None for _ratio, state in enabled_events))
        self.assertTrue(all(state is None for _ratio, state in disabled_events))

    def test_warm_only_success_does_not_decide_or_define_boundaries(self):
        attempt = ThresholdAttempt(
            dead_space_ratio=0.1,
            outline_side=1.0,
            seed_attempts=[
                SeedAttempt(1, "warm", FakeResult(True, hpwl=1.0, best_state="warm")),
                SeedAttempt(1, "cold", FakeResult(False)),
            ],
        )
        any_config = threshold_config("Q3-CONT-R")
        robust_config = Q3SearchConfig(
            **{**any_config.__dict__, "decision_rule": "robust"},
        )

        self.assertFalse(search._decision(attempt, any_config))
        self.assertFalse(search._decision(attempt, robust_config))
        self.assertIsNone(search._minimum_ratio([attempt], any_config, robust=False))
        self.assertIsNone(search._minimum_ratio([attempt], robust_config, robust=True))
        serialized = attempt.as_dict(any_config.robust_min_success_rate)
        self.assertFalse(serialized["found_legal"])
        self.assertIsNone(serialized["best_HPWL"])
        self.assertEqual(
            [item["mode"] for item in serialized["seed_attempts"]],
            ["warm", "cold"],
        )

    def test_continuous_compression_off_matches_bin_result(self):
        instance = next(tiny_instance())

        def fake_inner(_instance, config, _seed, warm_state=None):
            legal = config.dead_space_ratio >= 0.15
            return FakeResult(
                legal,
                hpwl=1.0 if legal else None,
                best_state=f"state-{config.dead_space_ratio}",
            )

        with patch.object(search, "_run_inner", side_effect=fake_inner):
            binary = search.solve_q3(instance, threshold_config("Q3-BIN"))
            continuous_off = search.solve_q3(
                instance,
                threshold_config("Q3-CONT-R", continuous_compression=False),
            )

        self.assertEqual(
            [attempt.dead_space_ratio for attempt in binary.attempts],
            [attempt.dead_space_ratio for attempt in continuous_off.attempts],
        )
        self.assertEqual(binary.d_best, continuous_off.d_best)
        self.assertEqual(binary.d_robust, continuous_off.d_robust)
        self.assertEqual(binary.selected_ratio, continuous_off.selected_ratio)
        self.assertEqual(
            [(attempt.seed, attempt.mode, attempt.result.formal_metrics) for attempt in binary.final_attempts],
            [(attempt.seed, attempt.mode, attempt.result.formal_metrics) for attempt in continuous_off.final_attempts],
        )

    def test_continuous_compression_rejects_invalid_combinations(self):
        invalid_configs = (
            Q3SearchConfig(candidate="Q3-BIN", continuous_compression=True),
            Q3SearchConfig(
                candidate="Q3-CONT-R",
                inner_candidate="Q2-SP",
                continuous_compression=True,
            ),
        )
        for config in invalid_configs:
            with self.subTest(config=config):
                with self.assertRaisesRegex(ValueError, "continuous_compression"):
                    validate_config(config)

    def test_workers_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "workers"):
            validate_config(Q3SearchConfig(workers=0))

    def test_workers_one_keeps_cold_seed_order(self):
        instance = next(tiny_instance())
        config = Q3SearchConfig(
            candidate="Q3-BIN",
            inner_candidate="Q2-BT",
            seeds=(3, 1, 2),
            final_seeds=(9,),
            max_evaluations=1,
            time_limit=1.0,
            restarts=1,
            final_max_evaluations=1,
            final_time_limit=1.0,
            final_restarts=1,
            workers=1,
        )
        seen = []

        def fake_inner(_instance, _config, seed, warm_state=None):
            seen.append((seed, warm_state))
            return FakeResult(True, hpwl=float(seed), best_state=f"state-{seed}")

        with patch.object(search, "_run_inner", side_effect=fake_inner):
            attempts = search._run_cold_attempts(
                instance,
                search._inner_config(config, 0.1),
                config.seeds,
                config.workers,
            )

        self.assertEqual([attempt.seed for attempt in attempts], [3, 1, 2])
        self.assertEqual(seen, [(3, None), (1, None), (2, None)])

    def test_workers_five_uses_process_pool_and_preserves_seed_order(self):
        instance = next(tiny_instance())
        config = Q3SearchConfig(
            candidate="Q3-BIN",
            inner_candidate="Q2-BT",
            seeds=(7, 8, 9),
            final_seeds=(99,),
            max_evaluations=1,
            time_limit=1.0,
            restarts=1,
            final_max_evaluations=1,
            final_time_limit=1.0,
            final_restarts=1,
            workers=5,
        )
        seen = []
        executors = []

        class RecordingExecutor:
            def __init__(self, max_workers):
                self.max_workers = max_workers
                self.tasks = []
                executors.append(self)

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def map(self, function, tasks):
                self.tasks = list(tasks)
                return [function(task) for task in self.tasks]

        def fake_inner(_instance, _config, seed, warm_state=None):
            seen.append((seed, warm_state))
            return FakeResult(True, hpwl=float(seed), best_state=f"state-{seed}")

        with (
            patch.object(search, "ProcessPoolExecutor", RecordingExecutor),
            patch.object(search, "_run_inner", side_effect=fake_inner),
        ):
            attempts = search._run_cold_attempts(
                instance,
                search._inner_config(config, 0.1),
                config.seeds,
                config.workers,
            )

        self.assertEqual([attempt.seed for attempt in attempts], [7, 8, 9])
        self.assertEqual(executors[0].max_workers, 5)
        self.assertEqual(seen, [(7, None), (8, None), (9, None)])

    def test_search_module_has_no_replace_import(self):
        tree = ast.parse(Path(search.__file__).read_text(encoding="utf-8"))
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        self.assertNotIn("replace", imported_names)

    def test_final_attempts_use_selected_ratio_and_final_seeds_without_warm_state(self):
        instance = next(tiny_instance())
        config = Q3SearchConfig(
            candidate="Q3-BIN",
            inner_candidate="Q2-BT",
            seeds=(1, 2),
            final_seeds=(11, 12, 13),
            max_evaluations=1,
            time_limit=1.0,
            restarts=1,
            final_max_evaluations=17,
            final_time_limit=2.0,
            final_restarts=3,
            workers=1,
        )
        calls = []

        def fake_inner(_instance, inner_config, seed, warm_state=None):
            calls.append((inner_config.dead_space_ratio, inner_config.max_evaluations, inner_config.time_limit, inner_config.restarts, seed, warm_state))
            return FakeResult(True, hpwl=float(seed))

        with patch.object(search, "_run_inner", side_effect=fake_inner):
            attempts = search._final_attempts(instance, config, 0.075)

        self.assertEqual([attempt.seed for attempt in attempts], [11, 12, 13])
        self.assertEqual([attempt.mode for attempt in attempts], ["final_cold", "final_cold", "final_cold"])
        self.assertEqual(
            calls,
            [
                (0.075, 17, 2.0, 3, 11, None),
                (0.075, 17, 2.0, 3, 12, None),
                (0.075, 17, 2.0, 3, 13, None),
            ],
        )


def write_tiny_instance(raw: Path) -> None:
    raw.mkdir(parents=True)
    (raw / "tiny.blocks").write_text(BLOCKS, encoding="utf-8")
    (raw / "tiny.nets").write_text(NETS, encoding="utf-8")
    (raw / "tiny.pl").write_text(PL, encoding="utf-8")


def cli_command(
    raw: Path,
    root: Path,
    precision: str = "0.05",
    *,
    run_id: str | None = None,
    continuous_compression: bool | None = None,
    workers: int = 1,
) -> list[str]:
    command = [
        str(PYTHON),
        "-B",
        "-m",
        "src.Q3",
        "--instance",
        "tiny",
        "--candidate",
        "Q3-BIN",
        "--inner-candidate",
        "Q2-SP",
        "--lower-ratio",
        "0",
        "--upper-ratio",
        "0.1",
        "--precision",
        precision,
        "--seeds",
        "1",
        "--max-evaluations",
        "1",
        "--time-limit",
        "5",
        "--restarts",
        "1",
        "--workers",
        str(workers),
        "--final-seeds",
        "2",
        "--final-max-evaluations",
        "1",
        "--final-time-limit",
        "5",
        "--final-restarts",
        "1",
        "--raw",
        str(raw),
        "--runtime-root",
        str(root / "runtime"),
        "--table-root",
        str(root / "tables"),
    ]
    if run_id is not None:
        command.extend(["--run-id", run_id])
    if continuous_compression is not None:
        command.extend(["--continuous-compression", "on" if continuous_compression else "off"])
    return command


def run_cli(
    raw: Path,
    root: Path,
    precision: str = "0.05",
    *,
    run_id: str | None = None,
    continuous_compression: bool | None = None,
    workers: int = 1,
) -> dict:
    command = cli_command(
        raw,
        root,
        precision,
        run_id=run_id,
        continuous_compression=continuous_compression,
        workers=workers,
    )
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return json.loads(completed.stdout)


class Q3CliTests(unittest.TestCase):
    def test_cli_records_reproducible_command_environment_and_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw"
            write_tiny_instance(raw)
            command = cli_command(raw, root, run_id="trace-contract")
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
            payload = json.loads(completed.stdout)
            expected_command = subprocess.list2cmdline(
                [sys.executable, "-B", "-m", "src.Q3", *command[4:]]
            )
            self.assertEqual(payload["command"], expected_command)
            self.assertGreaterEqual(payload["runtime_seconds"], 0)
            self.assertEqual(
                set(payload["environment"]), {"python", "platform", "cwd", "cpu_count"}
            )
            layout_payload = json.loads(Path(payload["layout_path"]).read_text(encoding="utf-8"))
        metadata = layout_payload["runtime_metadata"]
        self.assertEqual(metadata["command"], expected_command)
        self.assertEqual(metadata["environment"], payload["environment"])

    def test_compatibility_script_cli_help(self):
        completed = subprocess.run(
            [
                str(PYTHON),
                "-B",
                str(ROOT / "src" / "q3.py"),
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn("--continuous-compression", completed.stdout)

    def test_cli_writes_final_layout_and_traceable_layout_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw"
            write_tiny_instance(raw)
            payload = run_cli(raw, root)
            self.assertEqual(payload["config"]["robust_min_success_rate"], 0.8)
            self.assertEqual(payload["config"]["workers"], 1)

            result_path = root / "runtime" / "tiny" / payload["run_id"] / "result.json"
            layout_path = Path(payload["layout_path"])
            table_path = root / "tables" / f"{payload['run_id']}_attempts.csv"

            self.assertTrue(result_path.is_file())
            self.assertTrue(layout_path.is_file())
            self.assertEqual(payload["layout_path"], json.loads(result_path.read_text(encoding="utf-8"))["layout_path"])
            self.assertTrue(table_path.is_file())

            layout_payload = json.loads(layout_path.read_text(encoding="utf-8"))
            self.assertEqual(set(layout_payload["layout"]), {"b0"})
            self.assertEqual(set(layout_payload["layout"]["b0"]), {"x", "y", "rotation"})
            self.assertIn("formal_metrics", layout_payload)
            self.assertIn("audit_metrics", layout_payload)
            self.assertIn("seed", layout_payload["record"])
            self.assertIn("status", layout_payload["record"])
            self.assertIn("config", layout_payload)
            self.assertIn("run_id", layout_payload["record"])

            instance = parse_instance_files(
                raw / "tiny.blocks",
                raw / "tiny.nets",
                raw / "tiny.pl",
            )
            layout = {
                name: (item["x"], item["y"], item["rotation"])
                for name, item in layout_payload["layout"].items()
            }
            side = layout_payload["record"]["outline_side"]
            bounds = (0.0, 0.0, side, side)
            self.assertEqual(
                evaluate(instance, layout, bounds).as_dict(),
                layout_payload["formal_metrics"],
            )
            self.assertEqual(
                audit_layout(instance, layout, bounds),
                layout_payload["audit_metrics"],
            )

            with table_path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertIn("layout_path", rows[0])
            self.assertTrue(
                any(row["phase"] == "final" and Path(row["layout_path"]) == layout_path for row in rows)
            )

    def test_cli_workers_two_runs_real_windows_process_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw"
            write_tiny_instance(raw)
            payload = run_cli(raw, root, workers=2)

        self.assertEqual(payload["config"]["workers"], 2)
        self.assertEqual(payload["config"]["robust_min_success_rate"], 0.8)

    def test_explicit_run_id_has_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw"
            write_tiny_instance(raw)
            payload = run_cli(raw, root, run_id="explicit-q3-run")

        self.assertEqual(payload["run_id"], "explicit-q3-run")

    def test_cli_rejects_continuous_compression_for_non_continuous_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw"
            write_tiny_instance(raw)
            completed = subprocess.run(
                cli_command(raw, root, continuous_compression=True),
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("continuous_compression", completed.stderr)

    def test_only_best_final_seed_gets_layout_path(self):
        config = threshold_config("Q3-BIN")
        best = SeedAttempt(2, "final_cold", FakeResult(True, hpwl=1.0))
        other = SeedAttempt(3, "final_cold", FakeResult(True, hpwl=2.0))
        result = Q3Result([], None, None, None, [best, other])

        rows = _attempt_rows(result, config, "runtime/tiny/layout.json")
        paths = {row["seed"]: row["layout_path"] for row in rows}
        self.assertEqual(paths[2], "runtime/tiny/layout.json")
        self.assertEqual(paths[3], "")

    def test_default_run_id_changes_when_configuration_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw"
            write_tiny_instance(raw)
            first = run_cli(raw, root, precision="0.05")
            second = run_cli(raw, root, precision="0.025")

        self.assertNotEqual(first["run_id"], second["run_id"])


if __name__ == "__main__":
    unittest.main()
