"""Build Q4 V2 CSV evidence from the frozen exact and SA JSON outputs.

The input gate is deliberately fail-closed: no table is written until all
registered runs, seeds, statuses, metrics, hashes, and protocol parameters
have passed validation.
"""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "outputs" / "q4" / "_runtime" / "v2"
TABLES = ROOT / "outputs" / "q4" / "tables"

SEEDS = tuple(range(1101, 1111))
ROTATIONS = [0, 90, 180, 270]
MODULE_AREA = 24
ALLOWED_STATUSES = {"optimal", "success", "timeout", "no_feasible", "crash"}
SUCCESS_STATUSES = {"optimal", "success"}
AUDIT_KEYS = ("legal", "W", "H", "area", "module_area", "dead_space_ratio", "aspect_ratio", "rho", "deadspace", "HPWL", "square_side")
EXACT_COMMAND = (
    r"D:\Anaconda\envs\CA-py310\python.exe -B -m src.Q4 exact "
    r"--upper-area 36 --time-limit 300 --output "
    r"outputs/q4/_runtime/v2/exact/result.json"
)

MODULE_POLYGONS = {
    "b1": ((1, 0), (3, 0), (3, 2), (4, 2), (4, 4), (0, 4), (0, 2), (1, 2)),
    "b2": ((0, 0), (2, 0), (2, 2), (1, 2), (1, 4), (0, 4)),
    "b3": ((0, 0), (2, 0), (2, 1), (0, 1)),
    "b4": ((0, 0), (1, 0), (1, 4), (0, 4)),
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL-CLOSED: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load_json(path: Path) -> dict:
    require(path.is_file(), f"missing JSON: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read JSON {path}: {exc}")
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def config_hash(config: dict) -> str:
    payload = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def require_equal(actual, expected, label: str) -> None:
    require(actual == expected, f"{label}: expected {expected!r}, got {actual!r}")


def check_common(payload: dict, path: str, mode: str) -> None:
    require_equal(payload.get("problem"), "Q4", f"{path}.problem")
    require_equal(payload.get("mode"), mode, f"{path}.mode")
    status = payload.get("status")
    require(status in ALLOWED_STATUSES, f"{path}.status is not registered: {status!r}")
    formal = payload.get("formal")
    audit = payload.get("audit")
    require(isinstance(formal, dict) and isinstance(audit, dict), f"{path}: formal/audit missing")
    has_metrics = any(key in formal or key in audit for key in AUDIT_KEYS)
    if has_metrics:
        require(all(key in formal and key in audit for key in AUDIT_KEYS), f"{path}: formal/audit metric coverage incomplete")
        for key in AUDIT_KEYS:
            require_equal(formal[key], audit[key], f"{path}.formal/audit.{key}")
    payload_layout = payload.get("layout", {})
    formal_layout = formal.get("layout", {})
    require_equal(payload_layout, formal_layout, f"{path}.payload/formal.layout")
    if status in SUCCESS_STATUSES:
        require(has_metrics, f"{path}: successful result has no formal/audit metrics")
        require(payload.get("formal_audit_match") is True, f"{path}.formal_audit_match is not true")
        require(formal["legal"] is True, f"{path}.formal.legal is not true")
        require(audit["legal"] is True, f"{path}.audit.legal is not true")
    require_equal(payload.get("config_hash"), config_hash(payload.get("config", {})), f"{path}.config_hash")
    require(isinstance(payload.get("code_hash"), str) and payload["code_hash"], f"{path}.code_hash missing")
    require(isinstance(payload.get("command"), str) and payload["command"], f"{path}.command missing")
    require(isinstance(payload_layout, dict), f"{path}.layout missing")


def check_exact(payload: dict) -> None:
    path = "exact/result.json"
    check_common(payload, path, "exact")
    result = payload.get("result", {})
    config = payload.get("config", {})
    if result.get("status") is not None:
        require_equal(result.get("status"), payload.get("status"), f"{path}.result.status")
    else:
        require(payload.get("status") not in SUCCESS_STATUSES, f"{path}.result.status missing for success")
    if payload.get("status") == "optimal":
        require(result.get("complete") is True, f"{path}.result.complete is not true")
        require_equal(result.get("lower_bound"), 24, f"{path}.result.lower_bound")
        require_equal(result.get("upper_bound"), 24, f"{path}.result.upper_bound")
        require_equal(result.get("placements_tested"), 741, f"{path}.result.placements_tested")
    require_equal(payload.get("command"), EXACT_COMMAND, f"{path}.command")
    require_equal(config, {"grid_step": 1, "rotations": ROTATIONS, "search_domain": "integer_translation_grid", "time_limit": 300.0, "upper_area": 36}, f"{path}.config")
    domain = payload.get("domain", {})
    require_equal(domain.get("area_lower_bound"), 24, f"{path}.domain.area_lower_bound")
    require_equal(domain.get("area_upper_bound"), 36, f"{path}.domain.area_upper_bound")
    require_equal(domain.get("grid_step"), 1, f"{path}.domain.grid_step")
    require_equal(domain.get("rotations"), ROTATIONS, f"{path}.domain.rotations")
    require_equal(domain.get("search_domain"), "integer_translation_grid", f"{path}.domain.search_domain")
    require_equal(domain.get("containers_total"), 14, f"{path}.domain.containers_total")
    require_equal(domain.get("containers_checked"), 1, f"{path}.domain.containers_checked")
    if payload.get("status") == "optimal":
        require_equal(result.get("evaluation", {}).get("area"), 24, f"{path}.result.evaluation.area")


def expected_sa_command(seed: int) -> str:
    return (
        rf"D:\Anaconda\envs\CA-py310\python.exe -B -m src.Q4 sa --seed {seed} "
        rf"--max-evaluations 30000 --time-limit 60 --restarts 4 --domain-width 9 "
        rf"--domain-height 9 --output outputs/q4/_runtime/v2/sa/seed_{seed}.json"
    )


def check_sa(payload: dict, seed: int) -> None:
    path = f"sa/seed_{seed}.json"
    check_common(payload, path, "sa")
    result = payload.get("result", {})
    config = payload.get("config", {})
    if result.get("status") is not None:
        require_equal(result.get("status"), payload.get("status"), f"{path}.result.status")
    else:
        require(payload.get("status") not in SUCCESS_STATUSES, f"{path}.result.status missing for success")
    if payload.get("status") == "success":
        require_equal(result.get("seed"), seed, f"{path}.result.seed")
        require_equal(result.get("evaluations"), 30000, f"{path}.result.evaluations")
        require_equal(result.get("restarts_completed"), 4, f"{path}.result.restarts_completed")
        require_equal(result.get("initial_area"), 36, f"{path}.result.initial_area")
    require_equal(payload.get("command"), expected_sa_command(seed), f"{path}.command")
    expected_config = {"domain": [9, 9], "grid_step": 1, "max_evaluations": 30000, "restarts": 4, "rotations": ROTATIONS, "search_domain": "integer_translation_grid", "seed": seed, "temperature_schedule": "per_restart_linear", "time_limit": 60.0}
    require_equal(config, expected_config, f"{path}.config")
    require_equal(result.get("config"), expected_config, f"{path}.result.config")


def rotate_normalized(polygon: Iterable[tuple[int, int]], rotation: int) -> tuple[tuple[int, int], ...]:
    if rotation % 360 == 0:
        raw = tuple(polygon)
    elif rotation % 360 == 90:
        raw = tuple((-y, x) for x, y in polygon)
    elif rotation % 360 == 180:
        raw = tuple((-x, -y) for x, y in polygon)
    elif rotation % 360 == 270:
        raw = tuple((y, -x) for x, y in polygon)
    else:
        fail(f"unsupported rotation: {rotation}")
    min_x = min(x for x, _ in raw)
    min_y = min(y for _, y in raw)
    return tuple((x - min_x, y - min_y) for x, y in raw)


def tukey(values: list[float]) -> tuple[float, float, float]:
    ordered = sorted(values)
    middle = statistics.median(ordered)
    if len(ordered) == 1:
        return ordered[0], middle, ordered[0]
    midpoint = len(ordered) // 2
    lower = ordered[:midpoint]
    upper = ordered[(len(ordered) + 1) // 2 :]
    return float(statistics.median(lower)), float(middle), float(statistics.median(upper))


def optional_number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else ""


def success_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row["status"] == "success" and row["area"] != ""]


def safe_tukey(values: list[float]) -> tuple[float | None, float | None, float | None]:
    return tukey(values) if values else (None, None, None)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    exact_path = RUNTIME / "exact" / "result.json"
    exact = load_json(exact_path)
    check_exact(exact)
    sa_payloads = []
    for seed in SEEDS:
        payload = load_json(RUNTIME / "sa" / f"seed_{seed}.json")
        check_sa(payload, seed)
        sa_payloads.append(payload)

    code_hashes = {exact["code_hash"], *(payload["code_hash"] for payload in sa_payloads)}
    require_equal(len(code_hashes), 1, "code_hash set across exact/SA")

    exact_formal = exact["formal"]
    exact_result = exact["result"]
    exact_area = optional_number(exact_formal.get("area"))
    exact_row = {
        "route": "exact",
        "status": exact["status"],
        "complete": exact_result.get("complete", ""),
        "legal": exact_formal.get("legal", ""),
        "formal_audit_match": exact.get("formal_audit_match", ""),
        "area": exact_area,
        "W": exact_formal.get("W", ""),
        "H": exact_formal.get("H", ""),
        "module_area": exact_formal.get("module_area", ""),
        "deadspace": exact_formal.get("deadspace", ""),
        "lower_bound": exact_result.get("lower_bound", ""),
        "upper_bound": exact_result.get("upper_bound", ""),
        "containers_total": exact.get("domain", {}).get("containers_total", ""),
        "containers_checked": exact.get("domain", {}).get("containers_checked", ""),
        "placements_tested": exact_result.get("placements_tested", ""),
        "runtime": exact_result.get("runtime", ""),
        "evaluations": "",
        "gap": (exact_area - MODULE_AREA) / MODULE_AREA if exact_area != "" else "",
        "code_hash": exact["code_hash"],
        "config_hash": exact["config_hash"],
        "command": exact["command"],
        "layout_path": "outputs/q4/_runtime/v2/exact/result.json",
        "error": exact.get("error", ""),
        "exit_code": exact.get("exit_code", ""),
    }

    sa_rows = []
    for seed, payload in zip(SEEDS, sa_payloads):
        formal = payload["formal"]
        result = payload["result"]
        area = optional_number(formal.get("area"))
        sa_rows.append({
            "seed": seed,
            "status": payload["status"],
            "legal": formal.get("legal", ""),
            "formal_audit_match": payload.get("formal_audit_match", ""),
            "area": area,
            "W": formal.get("W", ""),
            "H": formal.get("H", ""),
            "module_area": formal.get("module_area", ""),
            "deadspace": formal.get("deadspace", ""),
            "dead_space_ratio": formal.get("dead_space_ratio", ""),
            "rho": formal.get("rho", ""),
            "runtime": result.get("runtime", ""),
            "evaluations": result.get("evaluations", ""),
            "initial_area": result.get("initial_area", ""),
            "restarts_completed": result.get("restarts_completed", ""),
            "gap": (area - MODULE_AREA) / MODULE_AREA if area != "" else "",
            "code_hash": payload["code_hash"],
            "config_hash": payload["config_hash"],
            "command": payload["command"],
            "layout_path": f"outputs/q4/_runtime/v2/sa/seed_{seed}.json",
            "error": payload.get("error", ""),
            "exit_code": payload.get("exit_code", ""),
        })

    successful_sa_rows = success_rows(sa_rows)
    areas = [float(row["area"]) for row in successful_sa_rows]
    gaps = [float(row["gap"]) for row in successful_sa_rows]
    runtimes = [float(row["runtime"]) for row in successful_sa_rows if row["runtime"] != ""]
    q1_area, median_area, q3_area = safe_tukey(areas)
    q1_gap, median_gap, q3_gap = safe_tukey(gaps)
    q1_runtime, median_runtime, q3_runtime = safe_tukey(runtimes)
    summary_rows = [
        {"metric": "n_runs", "value": len(sa_rows), "method": "all registered seeds; no exclusions"},
        {"metric": "legal_rate", "value": sum(row["status"] == "success" and row["legal"] is True for row in sa_rows) / len(sa_rows), "method": "successful legal runs / all 10 registered seeds"},
        {"metric": "formal_audit_match_rate", "value": sum(row["status"] == "success" and row["formal_audit_match"] is True for row in sa_rows) / len(sa_rows), "method": "successful audit-matched runs / all 10 registered seeds"},
        {"metric": "best_area", "value": min(areas) if areas else None, "method": "minimum area across successful runs; failures retained in denominator"},
        {"metric": "median_area", "value": median_area, "method": "ordinary median"},
        {"metric": "q1_area", "value": q1_area, "method": "Tukey lower-half median"},
        {"metric": "q3_area", "value": q3_area, "method": "Tukey upper-half median"},
        {"metric": "iqr_area", "value": q3_area - q1_area if q1_area is not None else None, "method": "Q3-Q1"},
        {"metric": "best_gap", "value": min(gaps) if gaps else None, "method": "(area-24)/24"},
        {"metric": "median_gap", "value": median_gap, "method": "ordinary median of (area-24)/24"},
        {"metric": "q1_gap", "value": q1_gap, "method": "Tukey lower-half median"},
        {"metric": "q3_gap", "value": q3_gap, "method": "Tukey upper-half median"},
        {"metric": "iqr_gap", "value": q3_gap - q1_gap if q1_gap is not None else None, "method": "Q3-Q1"},
        {"metric": "median_runtime_seconds", "value": median_runtime, "method": "ordinary median"},
        {"metric": "q1_runtime_seconds", "value": q1_runtime, "method": "Tukey lower-half median"},
        {"metric": "q3_runtime_seconds", "value": q3_runtime, "method": "Tukey upper-half median"},
        {"metric": "iqr_runtime_seconds", "value": q3_runtime - q1_runtime if q1_runtime is not None else None, "method": "Q3-Q1"},
        {"metric": "median_evaluations", "value": statistics.median(row["evaluations"] for row in successful_sa_rows if isinstance(row["evaluations"], (int, float))) if any(isinstance(row["evaluations"], (int, float)) for row in successful_sa_rows) else None, "method": "ordinary median over successful runs"},
    ]

    exact_summary = {
        "route": "exact",
        "n_runs": 1,
        "status": exact["status"],
        "legal_rate": int(exact["status"] in SUCCESS_STATUSES and exact_formal.get("legal") is True),
        "formal_audit_match_rate": int(exact["status"] in SUCCESS_STATUSES and exact.get("formal_audit_match") is True),
        "best_area": exact_area,
        "median_area": exact_area,
        "q1_area": exact_area,
        "q3_area": exact_area,
        "iqr_area": 0 if exact_area != "" else "",
        "best_gap": exact_row["gap"],
        "median_gap": exact_row["gap"],
        "mean_runtime_seconds": exact_result.get("runtime", ""),
        "median_runtime_seconds": exact_result.get("runtime", ""),
        "iqr_runtime_seconds": 0 if exact_result.get("runtime", "") != "" else "",
        "total_evaluations": exact_result.get("placements_tested", ""),
        "code_hash": exact["code_hash"],
        "config_hashes": exact["config_hash"],
        "evidence_path": exact_row["layout_path"],
        "optimality_note": "complete optimal integer declaration domain result",
    }
    sa_summary = {
        "route": "sa",
        "n_runs": len(sa_rows),
        "status": "success" if len(successful_sa_rows) == len(sa_rows) else "mixed",
        "legal_rate": sum(row["status"] == "success" and row["legal"] is True for row in sa_rows) / len(sa_rows),
        "formal_audit_match_rate": sum(row["status"] == "success" and row["formal_audit_match"] is True for row in sa_rows) / len(sa_rows),
        "best_area": min(areas) if areas else "",
        "median_area": median_area,
        "q1_area": q1_area,
        "q3_area": q3_area,
        "iqr_area": q3_area - q1_area if q1_area is not None else "",
        "best_gap": min(gaps) if gaps else "",
        "median_gap": median_gap,
        "mean_runtime_seconds": statistics.mean(runtimes) if runtimes else "",
        "median_runtime_seconds": median_runtime,
        "iqr_runtime_seconds": q3_runtime - q1_runtime if q1_runtime is not None else "",
        "total_evaluations": sum(row["evaluations"] for row in successful_sa_rows if isinstance(row["evaluations"], (int, float))),
        "code_hash": sa_rows[0]["code_hash"],
        "config_hashes": ";".join(row["config_hash"] for row in sa_rows),
        "evidence_path": "outputs/q4/_runtime/v2/sa/seed_1101.json..seed_1110.json",
        "optimality_note": "SA1108 matched area 24; SA does not prove optimality",
    }

    vertex_rows = []
    representatives = []
    if exact["status"] in SUCCESS_STATUSES and exact.get("layout"):
        representatives.append(("exact", "", exact, "exact primary evidence"))
    if sa_payloads[7]["status"] == "success" and sa_payloads[7].get("layout"):
        representatives.append(("sa", 1108, sa_payloads[7], "SA matched optimum; no optimality proof"))
    for route, seed, payload, evidence_role in representatives:
        formal = payload["formal"]
        raw_vertices = {}
        for module in ("b1", "b2", "b3", "b4"):
            placement = payload["layout"][module]
            rotation, anchor_x, anchor_y = placement["rotation"], placement["x"], placement["y"]
            polygon = rotate_normalized(MODULE_POLYGONS[module], rotation)
            raw_vertices[module] = [(anchor_x + local_x, anchor_y + local_y) for local_x, local_y in polygon]
        bbox_min_x = min(x for polygon in raw_vertices.values() for x, _ in polygon)
        bbox_min_y = min(y for polygon in raw_vertices.values() for _, y in polygon)
        for module in ("b1", "b2", "b3", "b4"):
            placement = payload["layout"][module]
            rotation, anchor_x, anchor_y = placement["rotation"], placement["x"], placement["y"]
            for vertex_index, (raw_x, raw_y) in enumerate(raw_vertices[module]):
                vertex_rows.append({
                    "route": route,
                    "seed": seed,
                    "module": module,
                    "vertex_index": vertex_index,
                    "x": raw_x - bbox_min_x,
                    "y": raw_y - bbox_min_y,
                    "rotation": rotation,
                    "anchor_x": anchor_x,
                    "anchor_y": anchor_y,
                    "bbox_min_x": bbox_min_x,
                    "bbox_min_y": bbox_min_y,
                    "module_area": abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(MODULE_POLYGONS[module], MODULE_POLYGONS[module][1:] + MODULE_POLYGONS[module][:1]))) / 2,
                    "W": formal["W"],
                    "H": formal["H"],
                    "status": payload["status"],
                    "legal": formal["legal"],
                    "formal_audit_match": payload["formal_audit_match"],
                    "area": formal["area"],
                    "evidence_role": evidence_role,
                    "code_hash": payload["code_hash"],
                    "layout_path": "outputs/q4/_runtime/v2/exact/result.json" if route == "exact" else "outputs/q4/_runtime/v2/sa/seed_1108.json",
                })

    write_csv(TABLES / "v2_exact_result.csv", list(exact_row), [exact_row])
    write_csv(TABLES / "v2_sa_run_details.csv", list(sa_rows[0]), sa_rows)
    write_csv(TABLES / "v2_sa_summary.csv", ["metric", "value", "method"], summary_rows)
    comparison_fields = list(exact_summary)
    write_csv(TABLES / "v2_route_comparison.csv", comparison_fields, [exact_summary, sa_summary])
    if vertex_rows:
        write_csv(TABLES / "v2_representative_layout_vertices.csv", list(vertex_rows[0]), vertex_rows)
    else:
        write_csv(TABLES / "v2_representative_layout_vertices.csv", ["route", "seed", "module", "vertex_index", "x", "y", "rotation", "anchor_x", "anchor_y", "bbox_min_x", "bbox_min_y", "module_area", "W", "H", "status", "legal", "formal_audit_match", "area", "evidence_role", "code_hash", "layout_path"], [])
    print(json.dumps({"tables": 5, "sa_runs": len(sa_rows), "code_hash": next(iter(code_hashes)), "best_sa_area": min(areas) if areas else None, "sa_median_area": median_area, "sa_q1": q1_area, "sa_q3": q3_area, "sa_iqr": q3_area - q1_area if q1_area is not None else None}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
