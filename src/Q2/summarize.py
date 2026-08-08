"""Build reproducible Q2 n100 development comparison tables."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics


CONFIGS = (
    ("P0", "Q2-SP", False),
    ("P1", "Q2-BT", False),
    ("P2-OFF", "Q2-HG", False),
    ("P2-ON", "Q2-HG", True),
)


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _bool(value: str) -> bool:
    return value == "True"


def _summary(config_id: str, rows: list[dict]) -> dict:
    legal = [row for row in rows if _bool(row["legal"])]
    hpwl = [float(row["HPWL"]) for row in legal]
    return {
        "config_id": config_id,
        "candidate": rows[0]["candidate"],
        "hypergraph_init": rows[0]["hypergraph_init"],
        "runs": len(rows),
        "legal_runs": len(legal),
        "audit_matches": sum(_bool(row["formal_audit_match"]) for row in rows),
        "status_success": sum(row["status"] == "success" for row in rows),
        "status_timeout": sum(row["status"] == "timeout" for row in rows),
        "status_no_feasible": sum(row["status"] == "no_feasible" for row in rows),
        "status_crash": sum(row["status"] == "crash" for row in rows),
        "best_HPWL": min(hpwl) if hpwl else None,
        "median_HPWL": statistics.median(hpwl) if hpwl else None,
        "median_first_feasible_evaluation": statistics.median(
            int(row["first_feasible_evaluation"]) for row in legal
        ) if legal else None,
        "median_first_feasible_time": statistics.median(
            float(row["first_feasible_time"]) for row in legal
        ) if legal else None,
        "median_evaluations": statistics.median(int(row["evaluations"]) for row in rows),
        "median_runtime": statistics.median(float(row["runtime"]) for row in rows),
    }


def _paired(comparison: str, baseline: list[dict], candidate: list[dict]) -> list[dict]:
    baseline_by_seed = {int(row["seed"]): row for row in baseline}
    candidate_by_seed = {int(row["seed"]): row for row in candidate}
    if set(baseline_by_seed) != set(candidate_by_seed):
        raise ValueError(f"{comparison}: seed sets differ")
    rows = []
    for seed in sorted(baseline_by_seed):
        before = float(baseline_by_seed[seed]["HPWL"])
        after = float(candidate_by_seed[seed]["HPWL"])
        difference = after - before
        rows.append({
            "comparison": comparison,
            "seed": seed,
            "baseline_HPWL": before,
            "candidate_HPWL": after,
            "difference": difference,
            "relative_difference_percent": difference / before * 100.0,
            "candidate_better": difference < 0,
        })
    return rows


def summarize(paths: list[Path], output_root: Path, run_id: str) -> dict:
    groups = {}
    code_hashes = set()
    budgets = set()
    seeds = None
    combined = []
    for (config_id, candidate, hypergraph), path in zip(CONFIGS, paths):
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

    summaries = [_summary(config_id, groups[config_id]) for config_id, _candidate, _flag in CONFIGS]
    paired = _paired("P1-minus-P0", groups["P0"], groups["P1"])
    paired += _paired("P2-ON-minus-P2-OFF", groups["P2-OFF"], groups["P2-ON"])
    _write_csv(output_root / f"{run_id}_run_details.csv", combined)
    _write_csv(output_root / f"{run_id}_summary.csv", summaries)
    _write_csv(output_root / f"{run_id}_paired_differences.csv", paired)
    snapshot = {
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
    parser = argparse.ArgumentParser(description="Summarize four frozen Q2 development batches")
    parser.add_argument("--p0", type=Path, required=True)
    parser.add_argument("--p1", type=Path, required=True)
    parser.add_argument("--p2-off", type=Path, required=True)
    parser.add_argument("--p2-on", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("outputs/q2/tables"))
    parser.add_argument("--run-id", default="v2_n100_current")
    args = parser.parse_args(argv)
    result = summarize([args.p0, args.p1, args.p2_off, args.p2_on], args.output_root, args.run_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
