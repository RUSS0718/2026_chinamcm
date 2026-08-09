"""Build reproducible Q2 n100 comparison tables."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics


LEGACY_CONFIGS = (
    ("P0", "Q2-SP", False),
    ("P1", "Q2-BT", False),
    ("P2-OFF", "Q2-HG", False),
    ("P2-ON", "Q2-HG", True),
)

REPAIRED_CONFIGS = (
    ("P0-GROUND", "Q2-SP", False, False, "shelf", "classic"),
    ("A2-BASE", "Q2-BT", False, False, "shelf", "fast"),
    ("P1", "Q2-BT", True, False, "shelf", "fast"),
    ("P2-OFF", "Q2-HG", True, False, "shelf", "fast"),
    ("P2-ON", "Q2-HG", True, True, "shelf", "fast"),
)

STRESS_CONFIGS = (
    ("A2-BASE-RANDOM", "Q2-BT", False, False, "random", "fast"),
    ("P1-RANDOM", "Q2-BT", True, False, "random", "fast"),
)


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty table: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _bool(value: object) -> bool:
    return value is True or str(value) == "True"


def _quartiles(values: list[float]) -> tuple[float | None, float | None, float | None]:
    if not values:
        return None, None, None
    if len(values) == 1:
        return values[0], values[0], 0.0
    quartiles = statistics.quantiles(values, n=4, method="inclusive")
    return quartiles[0], quartiles[2], quartiles[2] - quartiles[0]


def _summary(config_id: str, rows: list[dict]) -> dict:
    legal = [row for row in rows if _bool(row.get("legal")) and row.get("HPWL") not in {None, ""}]
    hpwl = [float(row["HPWL"]) for row in legal]
    q1, q3, iqr = _quartiles(hpwl)
    best = min(legal, key=lambda row: float(row["HPWL"])) if legal else None
    improvements = [float(row["improvement_from_initial"]) for row in rows if row.get("improvement_from_initial") not in {None, ""}]
    return {
        "config_id": config_id,
        "candidate": rows[0]["candidate"],
        "adaptive_constraints": rows[0].get("adaptive_constraints", ""),
        "hypergraph_init": rows[0].get("hypergraph_init", ""),
        "sa_schedule": rows[0].get("sa_schedule", ""),
        "initialization_mode": rows[0].get("initialization_mode", ""),
        "runs": len(rows),
        "legal_runs": len(legal),
        "audit_matches": sum(_bool(row.get("formal_audit_match")) for row in rows),
        "full_evaluation_runs": sum(
            row.get("status") == "success" and int(row.get("evaluations", 0)) == int(row.get("max_evaluations", 0))
            for row in rows
        ),
        "status_success": sum(row["status"] == "success" for row in rows),
        "status_timeout": sum(row["status"] == "timeout" for row in rows),
        "status_no_feasible": sum(row["status"] == "no_feasible" for row in rows),
        "status_crash": sum(row["status"] == "crash" for row in rows),
        "best_HPWL": best["HPWL"] if best else None,
        "median_HPWL": statistics.median(hpwl) if hpwl else None,
        "q1_HPWL": q1,
        "q3_HPWL": q3,
        "iqr_HPWL": iqr,
        "median_first_feasible_evaluation": statistics.median(
            int(row["first_feasible_evaluation"]) for row in legal if row.get("first_feasible_evaluation") not in {None, ""}
        ) if legal else None,
        "median_first_feasible_time": statistics.median(
            float(row["first_feasible_time"]) for row in legal if row.get("first_feasible_time") not in {None, ""}
        ) if legal else None,
        "median_evaluations": statistics.median(int(row["evaluations"]) for row in rows),
        "median_runtime": statistics.median(float(row["runtime"]) for row in rows),
        "median_improvement_from_initial": statistics.median(improvements) if improvements else None,
        "best_layout_path": best["layout_path"] if best else "",
    }


def _paired(comparison: str, baseline: list[dict], candidate: list[dict]) -> list[dict]:
    baseline_by_seed = {int(row["seed"]): row for row in baseline}
    candidate_by_seed = {int(row["seed"]): row for row in candidate}
    if set(baseline_by_seed) != set(candidate_by_seed):
        raise ValueError(f"{comparison}: seed sets differ")
    rows = []
    for seed in sorted(baseline_by_seed):
        before_row = baseline_by_seed[seed]
        after_row = candidate_by_seed[seed]
        before = float(before_row["HPWL"]) if _bool(before_row.get("legal")) and before_row.get("HPWL") not in {None, ""} else None
        after = float(after_row["HPWL"]) if _bool(after_row.get("legal")) and after_row.get("HPWL") not in {None, ""} else None
        difference = after - before if before is not None and after is not None else None
        rows.append({
            "comparison": comparison,
            "seed": seed,
            "baseline_legal": _bool(before_row.get("legal")),
            "candidate_legal": _bool(after_row.get("legal")),
            "baseline_HPWL": before,
            "candidate_HPWL": after,
            "difference": difference,
            "relative_difference_percent": difference / before * 100.0 if difference is not None and before else None,
            "candidate_better": difference < 0 if difference is not None else None,
        })
    return rows


def _validate_group(
    config: tuple[str, str, bool, bool, str, str],
    rows: list[dict],
    expected_seeds: set[int],
    code_hashes: set[str],
    data_hashes: set[str],
    budgets: set[tuple[str, str, str]],
    require_full: bool,
) -> None:
    config_id, candidate, adaptive, hypergraph, initialization_mode, schedule = config
    if len(rows) != len(expected_seeds):
        raise ValueError(f"{config_id}: expected {len(expected_seeds)} rows, got {len(rows)}")
    if {row["candidate"] for row in rows} != {candidate}:
        raise ValueError(f"{config_id}: candidate mismatch")
    if {_bool(row.get("adaptive_constraints")) for row in rows} != {adaptive}:
        raise ValueError(f"{config_id}: adaptive constraint flag mismatch")
    if {_bool(row.get("hypergraph_init")) for row in rows} != {hypergraph}:
        raise ValueError(f"{config_id}: hypergraph flag mismatch")
    if {row.get("initialization_mode") for row in rows} != {initialization_mode}:
        raise ValueError(f"{config_id}: initialization mode mismatch")
    if {row.get("sa_schedule") for row in rows} != {schedule}:
        raise ValueError(f"{config_id}: SA schedule mismatch")
    seeds = [int(row["seed"]) for row in rows]
    if set(seeds) != expected_seeds or len(seeds) != len(set(seeds)):
        raise ValueError(f"{config_id}: seed set mismatch")
    for row in rows:
        if not _bool(row.get("formal_audit_match")):
            raise ValueError(f"{config_id}/seed {row['seed']}: formal audit mismatch")
        if not Path(row["layout_path"]).is_file() or not Path(row["log_path"]).is_file():
            raise ValueError(f"{config_id}/seed {row['seed']}: missing layout or log")
        if require_full and not (row["status"] == "success" and int(row["evaluations"]) == int(row["max_evaluations"])):
            raise ValueError(f"{config_id}/seed {row['seed']}: incomplete evaluation budget")
    code_hashes.update(row["code_hash"] for row in rows)
    data_hashes.update(row["data_hash"] for row in rows)
    budgets.update((row["max_evaluations"], row["time_limit"], row["restarts"]) for row in rows)


def _assert_p1_p2_off_identical(p1: list[dict], p2_off: list[dict]) -> None:
    by_p1 = {int(row["seed"]): row for row in p1}
    by_off = {int(row["seed"]): row for row in p2_off}
    for seed in sorted(by_p1):
        left = json.loads(Path(by_p1[seed]["layout_path"]).read_text(encoding="utf-8"))
        right = json.loads(Path(by_off[seed]["layout_path"]).read_text(encoding="utf-8"))
        for key in ("layout", "formal_metrics", "audit_metrics"):
            if left[key] != right[key]:
                raise ValueError(f"P1/P2-OFF deterministic layout mismatch at seed {seed}: {key}")
        for key in ("evaluations", "proposals", "accepted", "restart_initial_signatures", "restart_init_seeds", "restart_search_seeds"):
            if left["record"].get(key) != right["record"].get(key):
                raise ValueError(f"P1/P2-OFF deterministic trace mismatch at seed {seed}: {key}")


def summarize_repaired(
    paths: list[Path],
    stress_paths: list[Path],
    output_root: Path,
    run_id: str,
    expected_seeds: set[int],
) -> dict:
    configs = list(REPAIRED_CONFIGS)
    groups: dict[str, list[dict]] = {}
    code_hashes: set[str] = set()
    data_hashes: set[str] = set()
    budgets: set[tuple[str, str, str]] = set()
    combined: list[dict] = []
    for config, path in zip(configs, paths):
        config_id = config[0]
        rows = _read(path)
        _validate_group(config, rows, expected_seeds, code_hashes, data_hashes, budgets, require_full=True)
        groups[config_id] = rows
        combined.extend({**row, "config_id": config_id} for row in rows)
    if len(code_hashes) != 1 or len(data_hashes) != 1 or len(budgets) != 1:
        raise ValueError(f"comparison protocol differs: code_hashes={code_hashes}, data_hashes={data_hashes}, budgets={budgets}")
    _assert_p1_p2_off_identical(groups["P1"], groups["P2-OFF"])
    summaries = [_summary(config[0], groups[config[0]]) for config in configs]
    paired = _paired("P1-minus-P0", groups["P0-GROUND"], groups["P1"])
    paired += _paired("P1-minus-A2-BASE", groups["A2-BASE"], groups["P1"])
    paired += _paired("P2-ON-minus-P2-OFF", groups["P2-OFF"], groups["P2-ON"])
    paired += _paired("P2-OFF-minus-P1", groups["P1"], groups["P2-OFF"])
    _write_csv(output_root / f"{run_id}_run_details.csv", combined)
    _write_csv(output_root / f"{run_id}_summary.csv", summaries)
    _write_csv(output_root / f"{run_id}_paired_differences.csv", paired)
    snapshot = {
        "profile": "repaired",
        "input_tables": [path.as_posix() for path in paths],
        "code_hash": next(iter(code_hashes)),
        "data_hash": next(iter(data_hashes)),
        "budget": list(next(iter(budgets))),
        "seeds": sorted(expected_seeds),
        "scope": "n100 repaired development screening; not final model selection",
        "comparisons": ["P1-minus-P0", "P1-minus-A2-BASE", "P2-ON-minus-P2-OFF", "P2-OFF-minus-P1"],
    }
    snapshot_path = output_root / f"{run_id}_comparison_snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stress_groups: dict[str, list[dict]] = {}
    stress_combined: list[dict] = []
    stress_configs = list(STRESS_CONFIGS)
    for config, path in zip(stress_configs, stress_paths):
        config_id = config[0]
        rows = _read(path)
        _validate_group(config, rows, expected_seeds, code_hashes, data_hashes, budgets, require_full=False)
        stress_groups[config_id] = rows
        stress_combined.extend({**row, "config_id": config_id} for row in rows)
    _write_csv(output_root / f"{run_id}_a2_stress_run_details.csv", stress_combined)
    _write_csv(output_root / f"{run_id}_a2_stress_summary.csv", [_summary(config[0], stress_groups[config[0]]) for config in stress_configs])
    _write_csv(output_root / f"{run_id}_a2_stress_paired_differences.csv", _paired("P1-RANDOM-minus-A2-BASE-RANDOM", stress_groups["A2-BASE-RANDOM"], stress_groups["P1-RANDOM"]))
    return {
        "summary": summaries,
        "paired_rows": len(paired),
        "snapshot": snapshot_path.as_posix(),
        "stress_runs": len(stress_combined),
    }


def summarize_legacy(paths: list[Path], output_root: Path, run_id: str) -> dict:
    groups = {}
    code_hashes = set()
    budgets = set()
    seeds = None
    combined = []
    for (config_id, candidate, hypergraph), path in zip(LEGACY_CONFIGS, paths):
        rows = _read(path)
        if not rows:
            raise ValueError(f"empty run table: {path}")
        if {row["candidate"] for row in rows} != {candidate}:
            raise ValueError(f"{config_id}: candidate mismatch")
        if {_bool(row["hypergraph_init"]) for row in rows} != {hypergraph}:
            raise ValueError(f"{config_id}: hypergraph flag mismatch")
        group_seeds = {int(row["seed"]) for row in rows}
        seeds = group_seeds if seeds is None else seeds
        if group_seeds != seeds:
            raise ValueError(f"{config_id}: seed set mismatch")
        code_hashes.update(row["code_hash"] for row in rows)
        budgets.update((row["max_evaluations"], row["time_limit"], row["restarts"]) for row in rows)
        groups[config_id] = rows
        combined.extend({**row, "config_id": config_id} for row in rows)
    if len(code_hashes) != 1 or len(budgets) != 1:
        raise ValueError(f"comparison protocol differs: code_hashes={code_hashes}, budgets={budgets}")
    summaries = [_summary(config_id, groups[config_id]) for config_id, _candidate, _flag in LEGACY_CONFIGS]
    paired = _paired("P1-minus-P0", groups["P0"], groups["P1"])
    paired += _paired("P2-ON-minus-P2-OFF", groups["P2-OFF"], groups["P2-ON"])
    _write_csv(output_root / f"{run_id}_run_details.csv", combined)
    _write_csv(output_root / f"{run_id}_summary.csv", summaries)
    _write_csv(output_root / f"{run_id}_paired_differences.csv", paired)
    snapshot = {
        "profile": "legacy",
        "input_tables": [path.as_posix() for path in paths],
        "code_hash": next(iter(code_hashes)),
        "budget": list(next(iter(budgets))),
        "seeds": sorted(seeds or []),
        "scope": "n100 development coarse screening; not final model selection",
    }
    snapshot_path = output_root / f"{run_id}_comparison_snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"summary": summaries, "paired_rows": len(paired), "snapshot": snapshot_path.as_posix()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Q2 n100 comparison tables")
    parser.add_argument("--p0", type=Path, required=True)
    parser.add_argument("--p1", type=Path, required=True)
    parser.add_argument("--p2-off", type=Path, required=True)
    parser.add_argument("--p2-on", type=Path, required=True)
    parser.add_argument("--a2-base", type=Path)
    parser.add_argument("--a2-base-random", type=Path)
    parser.add_argument("--p1-random", type=Path)
    parser.add_argument("--output-root", type=Path, default=Path("outputs/q2/tables"))
    parser.add_argument("--run-id", default="v2_n100_current")
    parser.add_argument("--seeds", default="1101-1110")
    args = parser.parse_args(argv)
    seeds = set()
    for token in args.seeds.split(","):
        token = token.strip()
        if "-" in token:
            first, last = token.split("-", 1)
            seeds.update(range(int(first), int(last) + 1))
        elif token:
            seeds.add(int(token))
    if args.a2_base is None:
        result = summarize_legacy([args.p0, args.p1, args.p2_off, args.p2_on], args.output_root, args.run_id)
    else:
        if args.a2_base_random is None or args.p1_random is None:
            parser.error("repaired profile requires --a2-base-random and --p1-random")
        result = summarize_repaired(
            [args.p0, args.a2_base, args.p1, args.p2_off, args.p2_on],
            [args.a2_base_random, args.p1_random],
            args.output_root,
            args.run_id,
            seeds,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
