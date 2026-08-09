"""Build fail-closed Q3 V2 n100 tables from the three formal runs."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = ROOT / "outputs" / "q3" / "_runtime" / "v2_n100" / "n100"
TABLE_ROOT = ROOT / "outputs" / "q3" / "tables"
EXPECTED_CODE_HASH = "a3971eefa77bc2cdaecd9fa0f59e85fc37668df57d6587d2217ec3f416ae8215"
CANDIDATES = ("Q3-BIN", "Q3-LIN", "Q3-CONT-R")
RUN_IDS = {
    "Q3-BIN": "v2_n100_q3_bin",
    "Q3-LIN": "v2_n100_q3_lin",
    "Q3-CONT-R": "v2_n100_q3_cont_r",
}
EXPECTED_ROWS = {"Q3-BIN": 80, "Q3-LIN": 200, "Q3-CONT-R": 86}
SEEDS = tuple(range(1101, 1111))
STATUSES = ("success", "optimal", "timeout", "no_feasible", "crash")
AUDIT_KEYS = (
    "legal",
    "W",
    "H",
    "area",
    "module_area",
    "dead_space_ratio",
    "aspect_ratio",
    "rho",
    "deadspace",
    "HPWL",
    "square_side",
)


def fail(message: str) -> None:
    raise SystemExit(f"FAIL-CLOSED: {message}")


def compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def q_hash(config: dict) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode("utf-8")).hexdigest()


def tukey(values: list[float]) -> tuple[float, float, float, float]:
    ordered = sorted(values)
    if not ordered:
        return (None, None, None, None)  # type: ignore[return-value]
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        lower = ordered[:midpoint]
        upper = ordered[midpoint + 1 :]
    else:
        lower = ordered[:midpoint]
        upper = ordered[midpoint:]
    q1 = median(lower) if lower else ordered[0]
    q3 = median(upper) if upper else ordered[-1]
    return (ordered[0], median(ordered), q1, q3)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def expected_config(candidate: str) -> dict:
    return {
        "adaptive_constraints": True,
        "candidate": candidate,
        "continuous_compression": candidate == "Q3-CONT-R",
        "decision_rule": "robust",
        "final_max_evaluations": 30000,
        "final_restarts": 4,
        "final_seeds": list(SEEDS),
        "final_time_limit": 60.0,
        "hypergraph_init": True,
        "inner_candidate": "Q2-HG",
        "lower_ratio": 0.0,
        "max_evaluations": 30000,
        "precision": 0.005,
        "restarts": 4,
        "robust_min_success_rate": 0.8,
        "seeds": list(SEEDS),
        "time_limit": 60.0,
        "upper_ratio": 0.15,
        "workers": 5,
    }


def check_seed(seed_record: dict, expected_mode: str | None = None) -> dict:
    required = {
        "HPWL",
        "error",
        "evaluations",
        "formal_audit_match",
        "legal",
        "mode",
        "restarts_completed",
        "runtime",
        "seed",
        "status",
    }
    missing = required - set(seed_record)
    if missing:
        fail(f"seed record missing keys: {sorted(missing)}")
    if expected_mode is not None and seed_record["mode"] != expected_mode:
        fail(f"unexpected mode {seed_record['mode']!r}, expected {expected_mode!r}")
    if seed_record["seed"] not in SEEDS:
        fail(f"unregistered seed {seed_record['seed']}")
    if seed_record["status"] not in STATUSES:
        fail(f"unknown status {seed_record['status']!r}")
    if not isinstance(seed_record["legal"], bool):
        fail("legal must be boolean")
    if seed_record["formal_audit_match"] is not True:
        fail("formal_audit_match is not true")
    if seed_record["runtime"] < 0 or seed_record["evaluations"] < 0:
        fail("negative runtime/evaluations")
    return seed_record


def load_candidate(candidate: str) -> dict:
    run_id = RUN_IDS[candidate]
    result_path = RUNTIME_ROOT / run_id / "result.json"
    if not result_path.is_file():
        fail(f"missing formal result: {relative(result_path)}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("candidate") not in (None, candidate):
        fail(f"candidate field mismatch in {relative(result_path)}")
    if result.get("run_id") != run_id:
        fail(f"run_id mismatch in {relative(result_path)}")
    if result.get("code_hash") != EXPECTED_CODE_HASH:
        fail(f"code hash mismatch for {candidate}")
    if q_hash(result["config"]) != result.get("config_hash"):
        fail(f"config hash does not recompute for {candidate}")
    if result["config"] != expected_config(candidate):
        fail(f"frozen config mismatch for {candidate}")
    command = result.get("command", "")
    prefix = r"D:\Anaconda\envs\CA-py310\python.exe -B -m src.Q3 "
    if not command.startswith(prefix) or f"--candidate {candidate}" not in command:
        fail(f"actual absolute command missing for {candidate}")
    environment = result.get("environment")
    if set(environment or {}) != {"python", "platform", "cwd", "cpu_count"}:
        fail(f"environment fields mismatch for {candidate}")
    if result.get("runtime_seconds", -1) < 0:
        fail(f"negative runtime_seconds for {candidate}")
    layout_path = ROOT / result["layout_path"]
    if not layout_path.is_file():
        fail(f"missing layout: {relative(layout_path)}")
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    if layout.get("formal_metrics") != layout.get("audit_metrics"):
        fail(f"layout formal/audit mismatch for {candidate}")
    layout_record = layout.get("record", {})
    if layout_record.get("candidate") != candidate or layout_record.get("code_hash") != EXPECTED_CODE_HASH:
        fail(f"layout record identity mismatch for {candidate}")
    if layout_record.get("config_hash") != result.get("config_hash"):
        fail(f"layout record config hash mismatch for {candidate}")
    if layout.get("runtime_metadata", {}).get("command") != command:
        fail(f"layout command mismatch for {candidate}")
    if layout.get("runtime_metadata", {}).get("environment") != environment:
        fail(f"layout environment mismatch for {candidate}")

    threshold_attempts = result.get("attempts", [])
    all_threshold_records: list[dict] = []
    threshold_rows: list[dict] = []
    for attempt in threshold_attempts:
        records = [check_seed(record) for record in attempt.get("seed_attempts", [])]
        cold = [record for record in records if record["mode"] == "cold"]
        warm = [record for record in records if record["mode"] == "warm"]
        if len(cold) != 10 or sorted(record["seed"] for record in cold) != list(SEEDS):
            fail(f"{candidate} threshold {attempt.get('dead_space_ratio')} does not have 10 cold seeds")
        if candidate != "Q3-CONT-R" and warm:
            fail(f"unexpected warm records for {candidate}")
        if attempt.get("cold_runs") != 10:
            fail(f"cold_runs mismatch for {candidate}")
        legal_count = sum(record["legal"] for record in cold)
        if attempt.get("cold_legal_runs") != legal_count:
            fail(f"cold legal count mismatch for {candidate}")
        rate = legal_count / 10
        if abs(attempt.get("cold_success_rate", -1) - rate) > 1e-12:
            fail(f"cold success rate mismatch for {candidate}")
        if bool(attempt.get("robust")) != (rate >= 0.8):
            fail(f"robust flag mismatch for {candidate}")
        legal_hpwl = [record["HPWL"] for record in cold if record["legal"] and record["HPWL"] is not None]
        if legal_hpwl and attempt.get("best_HPWL") != min(legal_hpwl):
            fail(f"best HPWL mismatch for {candidate}")
        all_threshold_records.extend(records)
        threshold_rows.append(
            {
                "candidate": candidate,
                "dead_space_ratio": attempt["dead_space_ratio"],
                "cold_runs": len(cold),
                "cold_legal_runs": legal_count,
                "cold_success_rate": rate,
                "robust": bool(attempt["robust"]),
                "best_HPWL": attempt.get("best_HPWL"),
                "status_counts": compact(dict(sorted(Counter(record["status"] for record in cold).items()))),
                "warm_count": len(warm),
                "warm_status_counts": compact(dict(sorted(Counter(record["status"] for record in warm).items()))),
            }
        )

    final_records = [check_seed(record, "final_cold") for record in result.get("final_attempts", [])]
    if len(final_records) != 10 or sorted(record["seed"] for record in final_records) != list(SEEDS):
        fail(f"{candidate} final does not have exactly 10 final_cold seeds")
    all_records = all_threshold_records + final_records
    if len(all_records) != EXPECTED_ROWS[candidate]:
        fail(f"{candidate} record count {len(all_records)} != {EXPECTED_ROWS[candidate]}")
    final_best = result.get("final_best")
    if not final_best or final_best.get("seed") not in SEEDS:
        fail(f"{candidate} missing final incumbent")
    if final_best.get("formal_audit_match") is not True:
        fail(f"{candidate} final incumbent audit mismatch")
    if result.get("layout_path") != final_best.get("layout_path"):
        fail(f"{candidate} final layout path mismatch")
    best_seed = final_best["seed"]
    for record in final_records:
        if record["seed"] == best_seed and not result["layout_path"]:
            fail(f"{candidate} best final seed lacks layout path")

    return {
        "candidate": candidate,
        "result": result,
        "layout": layout,
        "result_path": result_path,
        "layout_path": layout_path,
        "threshold_rows": threshold_rows,
        "threshold_records": all_threshold_records,
        "final_records": final_records,
        "all_records": all_records,
        "best_seed": best_seed,
    }


def build() -> dict[str, dict]:
    loaded = {candidate: load_candidate(candidate) for candidate in CANDIDATES}
    threshold_rows = [row for candidate in CANDIDATES for row in loaded[candidate]["threshold_rows"]]
    write_csv(
        TABLE_ROOT / "v2_n100_threshold_summary.csv",
        [
            "candidate",
            "dead_space_ratio",
            "cold_runs",
            "cold_legal_runs",
            "cold_success_rate",
            "robust",
            "best_HPWL",
            "status_counts",
            "warm_count",
            "warm_status_counts",
        ],
        threshold_rows,
    )

    final_rows: list[dict] = []
    for candidate in CANDIDATES:
        item = loaded[candidate]
        result = item["result"]
        for record in item["final_records"]:
            final_rows.append(
                {
                    "candidate": candidate,
                    "seed": record["seed"],
                    "status": record["status"],
                    "legal": record["legal"],
                    "HPWL": record["HPWL"],
                    "runtime": record["runtime"],
                    "evaluations": record["evaluations"],
                    "restarts_completed": record["restarts_completed"],
                    "formal_audit_match": record["formal_audit_match"],
                    "error": record["error"],
                    "layout_path": result["layout_path"] if record["seed"] == item["best_seed"] else "",
                    "source_result": relative(item["result_path"]),
                }
            )
    write_csv(
        TABLE_ROOT / "v2_n100_final_seed_details.csv",
        list(final_rows[0]),
        final_rows,
    )

    comparison_rows: list[dict] = []
    for candidate in CANDIDATES:
        item = loaded[candidate]
        result = item["result"]
        final_legal_hpwl = [
            record["HPWL"] for record in item["final_records"] if record["legal"] and record["HPWL"] is not None
        ]
        best, med, q1, q3 = tukey(final_legal_hpwl)
        warm_records = [record for record in item["threshold_records"] if record["mode"] == "warm"]
        comparison_rows.append(
            {
                "candidate": candidate,
                "d_best": result["d_best"],
                "d_robust": result["d_robust"],
                "selected_ratio": result["selected_ratio"],
                "thresholds": len(result["attempts"]),
                "cold_total": sum(record["mode"] == "cold" for record in item["all_records"]),
                "warm_total": len(warm_records),
                "final_total": len(item["final_records"]),
                "final_legal_rate": sum(record["legal"] for record in item["final_records"]) / 10,
                "best_HPWL": best,
                "median_HPWL": med,
                "Tukey_Q1_HPWL": q1,
                "Tukey_Q3_HPWL": q3,
                "Tukey_IQR_HPWL": q3 - q1 if q1 is not None else None,
                "runtime_seconds": result["runtime_seconds"],
                "status": result["status"],
                "code_hash": result["code_hash"],
                "config_hash": result["config_hash"],
                "command": result["command"],
                "environment": compact(result["environment"]),
                "layout_path": result["layout_path"],
            }
        )
    write_csv(
        TABLE_ROOT / "v2_n100_candidate_comparison.csv",
        list(comparison_rows[0]),
        comparison_rows,
    )

    failure_rows: list[dict] = []
    for candidate in CANDIDATES:
        item = loaded[candidate]
        mode_records = {
            "cold": [record for record in item["threshold_records"] if record["mode"] == "cold"],
            "warm": [record for record in item["threshold_records"] if record["mode"] == "warm"],
            "final_cold": item["final_records"],
        }
        for mode, records in mode_records.items():
            for status in STATUSES:
                selected = [record for record in records if record["status"] == status]
                failure_rows.append(
                    {
                        "candidate": candidate,
                        "mode": mode,
                        "status": status,
                        "count": len(selected),
                        "legal_count": sum(record["legal"] for record in selected),
                        "formal_audit_match_count": sum(record["formal_audit_match"] for record in selected),
                        "error_count": sum(bool(record["error"]) for record in selected),
                        "errors": compact(sorted({record["error"] for record in selected if record["error"]})),
                    }
                )
    write_csv(
        TABLE_ROOT / "v2_n100_failure_summary.csv",
        list(failure_rows[0]),
        failure_rows,
    )

    module_rows: list[dict] = []
    module_fields = [
        "candidate",
        "seed",
        "module",
        "x",
        "y",
        "rotation",
        "status",
        "legal",
        "source_result",
        "source_layout",
    ]
    module_fields += [f"formal_{key}" for key in AUDIT_KEYS]
    module_fields += [f"audit_{key}" for key in AUDIT_KEYS]
    for candidate in CANDIDATES:
        item = loaded[candidate]
        layout = item["layout"]
        record = layout["record"]
        formal = layout["formal_metrics"]
        audit = layout["audit_metrics"]
        for module, placement in sorted(layout["layout"].items()):
            row = {
                "candidate": candidate,
                "seed": record["seed"],
                "module": module,
                "x": placement["x"],
                "y": placement["y"],
                "rotation": placement["rotation"],
                "status": record["status"],
                "legal": record["legal"],
                "source_result": relative(item["result_path"]),
                "source_layout": relative(item["layout_path"]),
            }
            row.update({f"formal_{key}": formal.get(key) for key in AUDIT_KEYS})
            row.update({f"audit_{key}": audit.get(key) for key in AUDIT_KEYS})
            module_rows.append(row)
    if len(module_rows) != 300:
        fail(f"final layout module rows {len(module_rows)} != 300")
    write_csv(TABLE_ROOT / "v2_n100_final_layout_modules.csv", module_fields, module_rows)
    return loaded


if __name__ == "__main__":
    build()
    print("Q3 V2 deliverables built from formal JSON inputs")
