"""Fail-closed Q3-BIN n300 fixed-budget holdout entry.

This module is deliberately separate from :mod:`src.v3`: the existing V3
runner is part of immutable n200 registrations and must keep rejecting n300.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence

from .Q3.__main__ import _code_hash as q3_code_hash
from .Q3.__main__ import _config_hash as q3_config_hash
from .Q3.common import Q3SearchConfig
from .v3 import (
    CommandPlan,
    FreezeError,
    FreezeSpec,
    _read_rows,
    _status_counts,
    _validate_completed,
    file_manifest,
    manifest_hash,
    runtime_environment,
    summarize_q3,
    validate_attempt_slug,
    write_once,
)


ROOT = Path(__file__).resolve().parents[1]
ROUTE = "Q3-BIN"
INSTANCE = "n300"
COLD_SEEDS = tuple(range(3301, 3331))
FINAL_SEEDS = tuple(range(3401, 3431))
WORKERS = 4
PROCESSES = 4
THREADS = 1
MAX_THRESHOLDS = 7
MAX_ATTEMPTS = 240
STOP_SUBMISSIONS_SECONDS = 6_000.0
CHILD_HARD_STOP_SECONDS = 6_260.0
ORCHESTRATOR_TIMEOUT_SECONDS = 6_280.0
FORMAL_PROCESS_LIMIT_SECONDS = 6_300.0
OUTPUT_ROOT = "outputs/q3/_runtime/v3_n300_bin_holdout"
RUN_ID = "v3_n300_q3-bin"


def holdout_config() -> Q3SearchConfig:
    return Q3SearchConfig(
        candidate=ROUTE,
        inner_candidate="Q2-HG",
        lower_ratio=0.0,
        upper_ratio=0.15,
        precision=0.005,
        robust_min_success_rate=0.8,
        decision_rule="robust",
        seeds=COLD_SEEDS,
        max_evaluations=30_000,
        time_limit=60.0,
        restarts=4,
        workers=WORKERS,
        adaptive_constraints=True,
        hypergraph_init=True,
        continuous_compression=False,
        final_seeds=FINAL_SEEDS,
        final_max_evaluations=30_000,
        final_time_limit=60.0,
        final_restarts=4,
    )


def _data_paths(root: Path = ROOT) -> tuple[Path, ...]:
    raw = root / "data" / "raw" / "附件"
    return tuple(raw / f"n300{suffix}" for suffix in (".blocks", ".nets", ".pl"))


def _data_files(root: Path = ROOT) -> list[dict[str, Any]]:
    rows = file_manifest(_data_paths(root), root)
    for row, path in zip(rows, _data_paths(root)):
        row["raw_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def build_holdout_spec(root: Path = ROOT) -> FreezeSpec:
    config = holdout_config()
    data_files = file_manifest(_data_paths(root), root)
    return FreezeSpec(
        problem="q3",
        instance=INSTANCE,
        candidates=(ROUTE,),
        code_hashes={ROUTE: q3_code_hash()},
        config_hashes={ROUTE: q3_config_hash(config)},
        data_hash=manifest_hash(data_files),
        seeds=COLD_SEEDS,
        budgets={"max_evaluations": 30_000, "time_limit": 60.0, "restarts": 4},
        processes=PROCESSES,
        threads=THREADS,
        workers=WORKERS,
        rng="random.Random (CPython MT19937)",
        stop_conditions=(
            "max_evaluations",
            "wall_clock",
            "stop_submissions_at_100_minutes",
            "hard_stop_before_105_minutes",
            "uncaught_exception",
            "preserve_failure_status",
        ),
        output_root=OUTPUT_ROOT,
        final_seeds=FINAL_SEEDS,
    )


def check_holdout_spec(spec: FreezeSpec, root: Path = ROOT) -> None:
    if spec.as_dict() != build_holdout_spec(root).as_dict():
        raise FreezeError("Q3 n300 holdout differs from the frozen single-route registration")
    if spec.candidates != (ROUTE,):
        raise FreezeError("Q3 n300 holdout accepts Q3-BIN only")
    if spec.seeds != COLD_SEEDS or spec.final_seeds != FINAL_SEEDS:
        raise FreezeError("Q3 n300 holdout seed registration mismatch")
    if (spec.processes, spec.workers, spec.threads) != (4, 4, 1):
        raise FreezeError("Q3 n300 holdout requires processes=workers=4 and threads=1")


def build_holdout_plan(
    spec: FreezeSpec,
    attempt: str,
    *,
    python: str = sys.executable,
) -> CommandPlan:
    validate_attempt_slug(attempt)
    check_holdout_spec(spec)
    base_root = Path(spec.output_root).resolve()
    root = (base_root / attempt).resolve()
    if base_root not in root.parents:
        raise FreezeError("attempt output escapes the holdout root")
    command = (
        python,
        "-B",
        "-m",
        "src.Q3",
        "--instance",
        INSTANCE,
        "--candidate",
        ROUTE,
        "--inner-candidate",
        "Q2-HG",
        "--lower-ratio",
        "0",
        "--upper-ratio",
        "0.15",
        "--precision",
        "0.005",
        "--robust-min-success-rate",
        "0.8",
        "--decision-rule",
        "robust",
        "--seeds",
        "3301-3330",
        "--max-evaluations",
        "30000",
        "--time-limit",
        "60.0",
        "--restarts",
        "4",
        "--workers",
        "4",
        "--adaptive-constraints",
        "on",
        "--hypergraph-init",
        "on",
        "--continuous-compression",
        "off",
        "--final-seeds",
        "3401-3430",
        "--final-max-evaluations",
        "30000",
        "--final-time-limit",
        "60.0",
        "--final-restarts",
        "4",
        "--stop-submissions-after",
        str(STOP_SUBMISSIONS_SECONDS),
        "--hard-stop-after",
        str(CHILD_HARD_STOP_SECONDS),
        "--raw",
        "data/raw/附件",
        "--runtime-root",
        str(root / "runtime"),
        "--table-root",
        str(root / "tables"),
        "--run-id",
        RUN_ID,
    )
    environment = runtime_environment(spec, python=python)
    fingerprint = {
        "problem": "q3",
        "instance": INSTANCE,
        "config_id": ROUTE,
        "cold_seeds": list(COLD_SEEDS),
        "final_seeds": list(FINAL_SEEDS),
        "code_hash": spec.code_hashes[ROUTE],
        "config_hash": spec.config_hashes[ROUTE],
        "data_hash": spec.data_hash,
        "attempt": attempt,
        "command": list(command),
        "environment": environment,
        "study_scope": "q3_bin_n300_fixed_budget_holdout",
        "max_thresholds": MAX_THRESHOLDS,
        "max_attempts": MAX_ATTEMPTS,
        "stop_submissions_after_seconds": STOP_SUBMISSIONS_SECONDS,
        "child_hard_stop_after_seconds": CHILD_HARD_STOP_SECONDS,
        "orchestrator_timeout_seconds": ORCHESTRATOR_TIMEOUT_SECONDS,
    }
    return CommandPlan(
        command=command,
        marker=root / "runtime" / INSTANCE / RUN_ID / "result.json",
        fingerprint=fingerprint,
        env={"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
        auxiliary_markers=(
            root / "tables" / f"{RUN_ID}_attempts.csv",
            root / "tables" / f"{RUN_ID}_config_snapshot.json",
        ),
    )


def dry_run_payload(
    spec: FreezeSpec,
    plan: CommandPlan,
    attempt: str,
    root: Path = ROOT,
) -> dict[str, Any]:
    check_holdout_spec(spec, root)
    config = holdout_config()
    span = config.upper_ratio - config.lower_ratio
    max_thresholds = 2 + math.ceil(math.log2(span / config.precision))
    max_threshold_attempts = max_thresholds * len(COLD_SEEDS)
    max_final_attempts = len(FINAL_SEEDS)
    max_attempts = max_threshold_attempts + max_final_attempts
    waves_per_stage = math.ceil(len(COLD_SEEDS) / WORKERS)
    pure_minutes = (max_thresholds + 1) * waves_per_stage * config.time_limit / 60.0
    estimated = {"lower": math.ceil(pure_minutes + 1.0), "upper": math.ceil(pure_minutes * 1.4)}
    if max_attempts > 240:
        raise FreezeError(f"dry-run exceeds 240 attempts: {max_attempts}")
    if estimated["upper"] > 95:
        raise FreezeError(f"estimated runtime exceeds 95 minutes: {estimated['upper']}")
    runner_files = file_manifest((Path(__file__),), root)
    return {
        "mode": "dry-run",
        "study_scope": "Q3-BIN n300 quick fixed-budget holdout validation",
        "status": "REVIEWING",
        "route": ROUTE,
        "instance": INSTANCE,
        "inner_candidate": "Q2-HG",
        "config": config.as_dict(),
        "threshold_cold_seeds": list(COLD_SEEDS),
        "independent_final_seeds": list(FINAL_SEEDS),
        "max_thresholds": max_thresholds,
        "max_threshold_attempts": max_threshold_attempts,
        "max_final_attempts": max_final_attempts,
        "max_attempts": max_attempts,
        "workers": WORKERS,
        "processes": PROCESSES,
        "threads_per_process": THREADS,
        "thread_environment": {"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
        "budget": dict(spec.budgets),
        "pure_schedule_minutes": pure_minutes,
        "estimated_runtime_minutes": estimated,
        "stop_submissions_after_minutes": STOP_SUBMISSIONS_SECONDS / 60.0,
        "child_hard_stop_after_minutes": CHILD_HARD_STOP_SECONDS / 60.0,
        "formal_process_limit_minutes": FORMAL_PROCESS_LIMIT_SECONDS / 60.0,
        "data_files": _data_files(root),
        "data_hash": spec.data_hash,
        "code_hash": spec.code_hashes[ROUTE],
        "config_hash": spec.config_hashes[ROUTE],
        "runner_code_manifest_hash": manifest_hash(runner_files),
        "runner_code_files": runner_files,
        "python": runtime_environment(spec),
        "attempt_id": attempt,
        "output_directory": plan.marker.parents[3].as_posix(),
        "command": list(plan.command),
        "marker": plan.marker.as_posix(),
        "fingerprint": plan.fingerprint,
        "gate": {
            "single_route": ROUTE == "Q3-BIN",
            "attempts_within_240": max_attempts <= 240,
            "estimated_runtime_within_95_minutes": estimated["upper"] <= 95,
        },
        "interpretation_boundary": "Not a complete n300 three-route comparison; no BIN superiority claim over LIN or CONT-R is allowed.",
    }


def _progress_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FreezeError(f"invalid progress JSON: {path}") from exc
        if not isinstance(item, dict):
            raise FreezeError(f"progress event is not an object: {path}")
        events.append(item)
    return events


def validate_complete_result(plan: CommandPlan) -> dict[str, Any]:
    payload = _validate_completed(plan)
    if payload.get("execution_complete") is not True or payload.get("stop_reason") is not None:
        raise FreezeError("holdout marker is partial")
    if payload.get("config") != holdout_config().as_dict():
        raise FreezeError("holdout marker config differs from registration")
    if len(payload.get("attempts", ())) > MAX_THRESHOLDS:
        raise FreezeError("holdout produced more than seven thresholds")
    rows = []
    for threshold in payload.get("attempts", ()):
        cold = [item for item in threshold.get("seed_attempts", ()) if item.get("mode") == "cold"]
        if tuple(item.get("seed") for item in cold) != COLD_SEEDS:
            raise FreezeError("threshold contains missing or unregistered cold seeds")
        rows.extend(cold)
    final = [item for item in payload.get("final_attempts", ()) if item.get("mode") == "final_cold"]
    if tuple(item.get("seed") for item in final) != FINAL_SEEDS:
        raise FreezeError("final contains missing or unregistered seeds")
    rows.extend(final)
    if len(rows) > MAX_ATTEMPTS:
        raise FreezeError("holdout contains more than 240 attempts")
    if any(item.get("status") == "crash" for item in rows):
        raise FreezeError("holdout contains a crash")
    if any(item.get("formal_audit_match") is not True for item in rows):
        raise FreezeError("holdout contains a formal audit mismatch")
    progress = _progress_events(plan.marker.parent / "_live_progress.jsonl")
    if any(item.get("event") == "run_error" for item in progress):
        raise FreezeError("holdout progress contains run_error")
    if sum(item.get("event") == "run_complete" for item in progress) != 1:
        raise FreezeError("holdout progress lacks exactly one run_complete")
    return payload


def execute_holdout(spec: FreezeSpec, plan: CommandPlan, registration: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
    check_holdout_spec(spec)
    attempt_root = plan.marker.parents[3]
    if attempt_root.exists():
        raise FreezeError(f"refusing to reuse existing holdout attempt: {attempt_root}")
    write_once(attempt_root / "holdout_registration.json", dict(registration))
    plan.marker.parent.mkdir(parents=True, exist_ok=False)
    write_once(plan.marker.parent / "v3_freeze.json", dict(plan.fingerprint or {}))
    child_env = os.environ.copy()
    child_env.update(plan.env or {})
    status: dict[str, Any] = {
        "command": list(plan.command),
        "marker": plan.marker.as_posix(),
        "timeout_seconds": ORCHESTRATOR_TIMEOUT_SECONDS,
    }
    try:
        completed = subprocess.run(
            plan.command,
            cwd=ROOT,
            env=child_env,
            capture_output=True,
            text=True,
            check=False,
            timeout=ORCHESTRATOR_TIMEOUT_SECONDS,
        )
        status.update({
            "returncode": completed.returncode,
            "stdout_bytes": len(completed.stdout.encode("utf-8")),
            "stdout_sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
            "stderr": completed.stderr,
        })
    except subprocess.TimeoutExpired as exc:
        status.update({"returncode": None, "error": "orchestrator_timeout", "exception": str(exc)})
        write_once(attempt_root / "_orchestrator_status.json", status)
        return 2, status
    try:
        validated = validate_complete_result(plan)
        status.update({
            "validation": "complete",
            "result_status": validated.get("status"),
            "runtime_seconds": validated.get("runtime_seconds"),
        })
        exit_code = 0 if completed.returncode == 0 else 2
    except Exception as exc:
        status.update({"validation": "partial_or_invalid", "validation_error": f"{type(exc).__name__}: {exc}"})
        exit_code = 2
    write_once(attempt_root / "_orchestrator_status.json", status)
    return exit_code, status


def _rows_from_progress(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for event in events:
        if event.get("event") != "seed_complete":
            continue
        rows.append({
            "phase": event.get("phase"),
            "dead_space_ratio": event.get("dead_space_ratio"),
            "config_id": ROUTE,
            **{key: value for key, value in event.items() if key not in {"event", "timestamp", "candidate", "phase", "dead_space_ratio"}},
        })
    return rows


def summarize_attempt(attempt_root: Path) -> dict[str, Any]:
    root = attempt_root.resolve()
    base = Path(OUTPUT_ROOT).resolve()
    if root.parent != base:
        raise FreezeError(f"attempt must be directly under {base}")
    validate_attempt_slug(root.name)
    registration_path = root / "holdout_registration.json"
    if not registration_path.is_file():
        raise FreezeError("missing holdout registration")
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    spec = build_holdout_spec()
    plan = build_holdout_plan(spec, root.name)
    progress_path = plan.marker.parent / "_live_progress.jsonl"
    events = _progress_events(progress_path)
    complete = False
    validation_error = None
    result_payload: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    if plan.marker.is_file():
        try:
            result_payload = validate_complete_result(plan)
            rows = _read_rows(plan.marker)
            complete = True
        except Exception as exc:
            validation_error = f"{type(exc).__name__}: {exc}"
            try:
                raw = json.loads(plan.marker.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    result_payload = raw
                    rows = _read_rows(plan.marker)
            except Exception:
                rows = _rows_from_progress(events)
    else:
        validation_error = "missing result.json"
        rows = _rows_from_progress(events)
    reduced = summarize_q3(rows, COLD_SEEDS, FINAL_SEEDS)
    if not complete:
        reduced["d_best"] = None
        reduced["d_robust"] = None
    threshold_details = []
    ratios = sorted({float(row["dead_space_ratio"]) for row in rows if row.get("phase") == "threshold" and row.get("dead_space_ratio") is not None})
    for ratio in ratios:
        group = [row for row in rows if row.get("phase") == "threshold" and float(row.get("dead_space_ratio")) == ratio and row.get("mode") == "cold"]
        threshold_details.append({
            "dead_space_ratio": ratio,
            "registered_cold_seeds": list(COLD_SEEDS),
            "seed_attempts": group,
            "cold_legal_runs": sum(item.get("legal") is True and item.get("formal_audit_match") is True for item in group),
            "formal_audit_match_runs": sum(item.get("formal_audit_match") is True for item in group),
            "missing_runs": len(COLD_SEEDS) - len(group),
            "status_counts": _status_counts(group),
        })
    d_robust = reduced.get("d_robust")
    smaller = [item for item in threshold_details if d_robust is not None and item["dead_space_ratio"] < float(d_robust)]
    adjacent = max(smaller, key=lambda item: item["dead_space_ratio"]) if smaller else None
    final_rows = [row for row in rows if row.get("phase") == "final" and row.get("mode") == "final_cold"]
    final_audit = sum(row.get("formal_audit_match") is True for row in final_rows)
    final_legal = sum(row.get("legal") is True and row.get("formal_audit_match") is True for row in final_rows)
    n200_payload = json.loads((ROOT / "outputs/q3/tables/v3_n200_summary.json").read_text(encoding="utf-8"))
    terminal = next((event for event in reversed(events) if event.get("event") in {"run_complete", "run_stopped", "run_error"}), None)
    return {
        "problem": "q3",
        "study_scope": "Q3-BIN n300 quick fixed-budget holdout validation",
        "status": "REVIEWING",
        "execution_complete": complete,
        "validation_error": validation_error,
        "terminal_event": terminal,
        "attempt_id": root.name,
        "attempt_root": root.as_posix(),
        "route": ROUTE,
        "instance": INSTANCE,
        "registered_threshold_cold_seeds": list(COLD_SEEDS),
        "registered_independent_final_seeds": list(FINAL_SEEDS),
        "actual_attempts": len(rows),
        "max_attempts": MAX_ATTEMPTS,
        "runtime_seconds": result_payload.get("runtime_seconds"),
        "code_hash": result_payload.get("code_hash", registration.get("code_hash")),
        "config_hash": result_payload.get("config_hash", registration.get("config_hash")),
        "data_hash": result_payload.get("data_hash", registration.get("data_hash")),
        "data_files": registration.get("data_files", _data_files()),
        "command": result_payload.get("command", subprocess.list2cmdline(plan.command)),
        "environment": result_payload.get("environment", registration.get("python")),
        "config": result_payload.get("config", holdout_config().as_dict()),
        "summary": reduced,
        "threshold_details": threshold_details,
        "adjacent_smaller_tested": adjacent,
        "final_details": {
            "registered_seeds": list(FINAL_SEEDS),
            "attempts": final_rows,
            "legal_and_audited_runs": final_legal,
            "legal_rate": final_legal / len(FINAL_SEEDS),
            "formal_audit_match_runs": final_audit,
            "formal_audit_rate": final_audit / len(FINAL_SEEDS),
            "missing_runs": len(FINAL_SEEDS) - len(final_rows),
            "status_counts": _status_counts(final_rows),
        },
        "n200_q3_bin_reference": n200_payload.get("summary_by_route", {}).get(ROUTE, {}),
        "interpretation_boundary": {
            "lin_run": False,
            "cont_r_run": False,
            "three_route_comparison": False,
            "q3_bin_superiority_claim_allowed": False,
            "timeout_is_not_failure_or_optimality": True,
            "not_found_is_not_infeasibility": True,
        },
    }


def _value(item: Any) -> str:
    if item is None:
        return "NA"
    if isinstance(item, float):
        return f"{item:.12g}"
    return str(item)


def _status_text(counts: Mapping[str, Any]) -> str:
    return ", ".join(
        f"{name.removeprefix('status_')}={counts.get(name, 0)}"
        for name in ("status_timeout", "status_no_feasible", "status_crash", "status_success")
    )


def render_report(payload: Mapping[str, Any]) -> str:
    summary = payload["summary"]
    final = payload["final_details"]
    n200 = payload["n200_q3_bin_reference"]
    runtime = float(payload.get("runtime_seconds") or 0.0)
    completion = "完整" if payload["execution_complete"] else "不完整（仅保留 partial 证据）"
    lines = [
        "# Q3-BIN V3 n300 快速固定预算留出验证报告",
        "",
        "- 问题：`Q3`",
        "- 状态：`REVIEWING`",
        "- 主责建模师：钟江铭",
        "- 复核人：蔡乔夕（待人工复核）",
        "- 更新时间：2026-08-09",
        f"- 执行完整性：{completion}",
        f"- attempt：`{payload['attempt_id']}`",
        f"- 证据根目录：`{payload['attempt_root']}`",
        "",
        "## 1. 直接结论与解释边界",
        "",
        f"`d_best={_value(summary.get('d_best'))}`，`d_robust={_value(summary.get('d_robust'))}`。final 合法且审计一致率 {final['legal_and_audited_runs']}/30 = {final['legal_rate']:.3f}，formal audit 一致率 {final['formal_audit_match_runs']}/30 = {final['formal_audit_rate']:.3f}。",
        f"final HPWL：median={_value(summary.get('final_median_HPWL'))}，IQR={_value(summary.get('final_iqr_HPWL'))}，P90={_value(summary.get('final_p90_HPWL'))}。",
        "本轮未运行 Q3-LIN 或 Q3-CONT-R，不能形成完整 n300 三路线比较，也不能据此证明 Q3-BIN 优于 LIN/CONT-R。",
        "`timeout` 表示达到 60 秒固定预算，不表示失败、收敛或最优；较小死区未找到只能写成本预算内未找到，不能写成数学不可行。",
    ]
    if not payload["execution_complete"]:
        lines.extend(["", f"不完整原因：`{payload.get('validation_error')}`；停止位置：`{json.dumps(payload.get('terminal_event'), ensure_ascii=False)}`。不得把本批次写成正式完成。"])
    lines.extend([
        "",
        "## 2. 冻结配置与运行规模",
        "",
        "- route：`Q3-BIN`；inner：`Q2-HG`；ratio：`0–0.15`；precision：`0.005`；decision：`robust`；minimum success：`0.80`",
        "- adaptive constraints：`on`；hypergraph init：`on`；continuous compression：`off`",
        "- `30000 evaluations / 60 s / 4 restarts`；workers/processes：`4/4`；threads/process：`1`",
        "- threshold cold seeds：`3301–3330`；independent final seeds：`3401–3430`",
        f"- 实际 attempts：`{payload['actual_attempts']}` / 最大 `240`；运行时间：`{runtime:.3f} s`（`{runtime / 60.0:.2f} min`）",
        "",
        "## 3. Threshold 点",
        "",
        "| d | cold seeds | 合法且审计一致 | missing | robust | 状态 |",
        "|---:|---|---:|---:|:---:|---|",
    ])
    reduced_by_ratio = {float(item["dead_space_ratio"]): item for item in summary.get("thresholds", ())}
    for item in payload["threshold_details"]:
        reduced = reduced_by_ratio.get(float(item["dead_space_ratio"]), {})
        lines.append(f"| {_value(item['dead_space_ratio'])} | 3301–3330 | {item['cold_legal_runs']}/30 | {item['missing_runs']} | {'是' if reduced.get('robust') and payload['execution_complete'] else '否'} | {_status_text(item['status_counts'])} |")
    adjacent = payload.get("adjacent_smaller_tested")
    lines.extend(["", "相邻更小已测试点："])
    lines.append("- 无。" if adjacent is None else f"- `d={_value(adjacent['dead_space_ratio'])}`：合法且审计一致 {adjacent['cold_legal_runs']}/30，missing={adjacent['missing_runs']}，{_status_text(adjacent['status_counts'])}。仅表示固定预算搜索状态。")
    lines.extend([
        "",
        "### 3.1 每个 threshold 的 cold seed 记录",
        "",
        "| d | seed | status | legal | audit match | HPWL | runtime_s | evaluations |",
        "|---:|---:|---|:---:|:---:|---:|---:|---:|",
    ])
    for threshold in payload["threshold_details"]:
        for attempt in threshold["seed_attempts"]:
            lines.append(f"| {_value(threshold['dead_space_ratio'])} | {attempt.get('seed')} | {attempt.get('status')} | {attempt.get('legal')} | {attempt.get('formal_audit_match')} | {_value(attempt.get('HPWL'))} | {_value(attempt.get('runtime'))} | {_value(attempt.get('evaluations'))} |")
    lines.extend([
        "",
        "## 4. Independent final seeds",
        "",
        f"状态：{_status_text(final['status_counts'])}；missing={final['missing_runs']}。",
        "",
        "| seed | status | legal | audit match | HPWL | runtime_s | evaluations |",
        "|---:|---|:---:|:---:|---:|---:|---:|",
    ])
    for attempt in final["attempts"]:
        lines.append(f"| {attempt.get('seed')} | {attempt.get('status')} | {attempt.get('legal')} | {attempt.get('formal_audit_match')} | {_value(attempt.get('HPWL'))} | {_value(attempt.get('runtime'))} | {_value(attempt.get('evaluations'))} |")
    lines.extend([
        "",
        "## 5. 与 n200 Q3-BIN 的规模稳定性对照",
        "",
        "| 实例 | threshold 点数 | d_best | d_robust | final 合法率 | HPWL median | IQR | P90 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        f"| n200 | {_value(n200.get('threshold_count'))} | {_value(n200.get('d_best'))} | {_value(n200.get('d_robust'))} | {_value(n200.get('final_legal_rate'))} | {_value(n200.get('final_median_HPWL'))} | {_value(n200.get('final_iqr_HPWL'))} | {_value(n200.get('final_p90_HPWL'))} |",
        f"| n300 | {_value(summary.get('threshold_count'))} | {_value(summary.get('d_best'))} | {_value(summary.get('d_robust'))} | {_value(summary.get('final_legal_rate'))} | {_value(summary.get('final_median_HPWL'))} | {_value(summary.get('final_iqr_HPWL'))} | {_value(summary.get('final_p90_HPWL'))} |",
        "",
        "该对照只检查冻结 Q3-BIN 从 n200 到 n300 的固定预算规模稳定性；HPWL 绝对量级不用于跨实例优劣排序。",
        "",
        "## 6. 完整性与哈希",
        "",
        f"- threshold：{summary.get('threshold_cold_runs')}/{summary.get('threshold_cold_registered_runs')}；missing={summary.get('threshold_cold_missing_runs')}；{_status_text(summary.get('threshold_cold_status_counts', {}))}",
        f"- final：{summary.get('final_runs')}/30；missing={summary.get('final_missing_runs')}；{_status_text(summary.get('final_status_counts', {}))}",
        f"- code hash：`{payload['code_hash']}`",
        f"- config hash：`{payload['config_hash']}`",
        f"- aggregate data hash：`{payload['data_hash']}`",
        "",
        "| 原始文件 | bytes | raw SHA-256 | normalized SHA-256 |",
        "|---|---:|---|---|",
    ])
    for item in payload["data_files"]:
        lines.append(f"| `{item['path']}` | {item['bytes']} | `{item['raw_sha256']}` | `{item['sha256']}` |")
    lines.extend([
        "",
        "实际命令：",
        "",
        "```text",
        str(payload.get("command")),
        "```",
        "",
        "## 7. 未执行与待复核",
        "",
        "- 未运行 Q3-LIN、Q3-CONT-R，未调参、加预算、补 seed 或挑选结果。",
        "- 未修改 `data/raw/`，未覆盖 n200/既有 attempt，未迁入 `outputs/q3/final/`。",
        "- 未创建 commit，未 push。状态保持 `REVIEWING`，等待人工复核。",
    ])
    return "\n".join(lines) + "\n"


def write_text_once(path: Path, payload: str) -> None:
    text = payload if payload.endswith("\n") else payload + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise FreezeError(f"refusing to overwrite existing report: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as stream:
        stream.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q3-BIN n300 fixed-budget holdout")
    parser.add_argument("command", choices=("dry-run", "run", "summary"))
    parser.add_argument("--attempt")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if args.command == "summary":
        if args.input is None:
            parser.error("summary requires --input")
        payload = summarize_attempt(args.input)
        if args.output:
            write_once(args.output, payload)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        if args.report:
            write_text_once(args.report, render_report(payload))
        return 0 if payload["execution_complete"] else 2
    if not args.attempt:
        parser.error(f"{args.command} requires a unique --attempt slug")
    spec = build_holdout_spec()
    plan = build_holdout_plan(spec, args.attempt)
    dry = dry_run_payload(spec, plan, args.attempt)
    if args.command == "dry-run":
        payload = dry
        exit_code = 0
    else:
        registration = {**dry, "mode": "registered_formal_run"}
        exit_code, status = execute_holdout(spec, plan, registration)
        payload = {"registration": registration, "orchestrator_status": status}
    if args.output:
        write_once(args.output, payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
