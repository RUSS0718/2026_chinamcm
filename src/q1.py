"""Question 1 V2 command line entrypoint."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time

from ._internal.audit import audit_layout
from ._internal.evaluator import evaluate
from ._internal.parser import parse_blocks_file
from ._internal.q1_solver import Q1SearchConfig, SearchResult, search_q1


CONFIGS = (
    ("P1", "Q1-BT", False, False),
    ("P2-directed-only", "Q1-BT-D", True, False),
    ("P2-dedup-only", "Q1-BT-D", False, True),
    ("P2", "Q1-BT-D", True, True),
)


def _json_dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _normalized_file_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(_normalized_file_bytes(path)).hexdigest()


def _code_hash() -> str:
    files = [
        Path(__file__),
        Path(__file__).parent / "_internal" / "parser.py",
        Path(__file__).parent / "_internal" / "q1_solver.py",
        Path(__file__).parent / "_internal" / "evaluator.py",
        Path(__file__).parent / "_internal" / "audit.py",
    ]
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.as_posix().encode("utf-8"))
        digest.update(_normalized_file_bytes(path))
    return digest.hexdigest()


def _config_hash(config: Q1SearchConfig) -> str:
    payload = json.dumps(config.as_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _parse_seeds(value: str) -> list[int]:
    seeds: list[int] = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            first, last = token.split("-", 1)
            seeds.extend(range(int(first), int(last) + 1))
        else:
            seeds.append(int(token))
    if not seeds:
        raise ValueError("no seeds supplied")
    return seeds


def _on_off(value: str) -> bool:
    lowered = value.lower()
    if lowered in {"on", "true", "1", "yes"}:
        return True
    if lowered in {"off", "false", "0", "no"}:
        return False
    raise argparse.ArgumentTypeError("expected on or off")


def _load_instance(raw_dir: Path, instance_name: str):
    path = raw_dir / f"{instance_name}.blocks"
    if not path.is_file():
        raise FileNotFoundError(path)
    instance, issues = parse_blocks_file(path, strict=True)
    if issues:
        raise ValueError("; ".join(issues))
    return instance


def _input_audit(raw_dir: Path, instance_names: tuple[str, ...]) -> dict:
    rows = []
    for name in instance_names:
        path = raw_dir / f"{name}.blocks"
        instance, issues = parse_blocks_file(path, strict=False)
        dimensions = [(block.width, block.height) for block in instance.blocks.values()]
        rows.append(
            {
                "instance": name,
                "source": path.as_posix(),
                "sha256_lf_normalized": _sha256_file(path),
                "declared_blocks": instance.declared_blocks,
                "parsed_blocks": len(instance.blocks),
                "declared_terminals": instance.declared_terminals,
                "processed_rows": len(instance.blocks),
                "excluded_rows": len(issues),
                "exclusion_reasons": list(issues),
                "positive_dimensions": all(w > 0 and h > 0 for w, h in dimensions),
                "four_vertex_rectangles": all(len(block.polygon) == 4 for block in instance.blocks.values()),
                "unique_names": len(instance.blocks) == len(set(instance.blocks)),
                "total_module_area": sum(w * h for w, h in dimensions),
                "min_width": min((w for w, h in dimensions), default=None),
                "max_width": max((w for w, h in dimensions), default=None),
                "min_height": min((h for w, h in dimensions), default=None),
                "max_height": max((h for w, h in dimensions), default=None),
            }
        )
    return {
        "source_of_truth": "data/raw/附件/*.blocks",
        "q1_uses_only_blocks": True,
        "instances": rows,
    }


def _layout_dict(result: SearchResult) -> dict:
    if result.best is None:
        return {}
    return {
        name: {"x": x, "y": y, "rotation": rotation}
        for name, (x, y, rotation) in sorted(result.best.layout.items())
    }


def _run_record(instance_name: str, config_id: str, config: Q1SearchConfig, seed: int, result: SearchResult, code_hash: str) -> dict:
    formal = result.formal_metrics
    audit = result.audit_metrics
    return {
        "instance": instance_name,
        "problem": "Q1",
        "config_id": config_id,
        "candidate": config.candidate,
        "directed_moves": config.directed_moves,
        "state_dedup": config.state_dedup,
        "seed": seed,
        "code_hash": code_hash,
        "config_hash": _config_hash(config),
        "max_evaluations": config.max_evaluations,
        "time_limit": config.time_limit,
        "restarts": config.restarts,
        "status": result.status,
        "legal": audit.get("legal"),
        "W": formal.get("W"),
        "H": formal.get("H"),
        "area": formal.get("area"),
        "module_area": formal.get("module_area"),
        "aspect_ratio": formal.get("aspect_ratio"),
        "deadspace": formal.get("deadspace"),
        "dead_space_ratio": formal.get("dead_space_ratio"),
        "rho": formal.get("rho"),
        "HPWL": formal.get("HPWL"),
        "runtime": result.runtime,
        "evaluations": result.evaluations,
        "proposals": result.proposals,
        "accepted": result.accepted,
        "duplicate_rejections": result.duplicate_rejections,
        "restarts_completed": result.restarts_completed,
        "formal_audit_match": formal == audit,
        "error": result.error or "",
    }


def _write_single_run(output_root: Path, instance_name: str, config_id: str, seed: int, config: Q1SearchConfig, result: SearchResult, record: dict) -> dict:
    run_dir = output_root / instance_name / config_id / f"seed_{seed}"
    run_dir.mkdir(parents=True, exist_ok=True)
    layout_path = run_dir / "layout.json"
    log_path = run_dir / "events.jsonl"
    run_payload = {
        "record": record,
        "config": config.as_dict(),
        "layout": _layout_dict(result),
        "formal_metrics": result.formal_metrics,
        "audit_metrics": result.audit_metrics,
    }
    _json_dump(layout_path, run_payload)
    log_path.write_text(json.dumps({"event": "run_complete", **record}, ensure_ascii=False) + "\n", encoding="utf-8")
    record = dict(record)
    record["layout_path"] = layout_path.as_posix()
    record["log_path"] = log_path.as_posix()
    return record


def _quantiles(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    q = statistics.quantiles(values, n=4, method="inclusive")
    return q[0], q[2]


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _summary_rows(records: list[dict]) -> list[dict]:
    by_config: dict[str, list[dict]] = {}
    for row in records:
        by_config.setdefault(row["config_id"], []).append(row)
    rows = []
    for config_id, group in by_config.items():
        legal = [r for r in group if r.get("legal") is True and r.get("area") is not None]
        areas = [float(r["area"]) for r in legal]
        aspects = [float(r["aspect_ratio"]) for r in legal]
        q1_area, q3_area = _quantiles(areas)
        best = min(legal, key=lambda r: (r["area"], r["aspect_ratio"])) if legal else None
        rows.append(
            {
                "config_id": config_id,
                "candidate": group[0]["candidate"],
                "directed_moves": group[0]["directed_moves"],
                "state_dedup": group[0]["state_dedup"],
                "runs": len(group),
                "legal_runs": len(legal),
                "status_success": sum(r["status"] == "success" for r in group),
                "status_timeout": sum(r["status"] == "timeout" for r in group),
                "status_no_feasible": sum(r["status"] == "no_feasible" for r in group),
                "status_crash": sum(r["status"] == "crash" for r in group),
                "best_area": best["area"] if best else None,
                "best_aspect_ratio": best["aspect_ratio"] if best else None,
                "median_area": _median(areas),
                "q1_area": q1_area,
                "q3_area": q3_area,
                "median_aspect_ratio": _median(aspects),
                "median_runtime": _median([float(r["runtime"]) for r in group]),
                "median_evaluations": _median([float(r["evaluations"]) for r in group]),
                "best_layout_path": best.get("layout_path", "") if best else "",
            }
        )
    return rows


def _write_representative_layouts(path: Path, records: list[dict], runtime_root: Path) -> None:
    rows = []
    for config_id in sorted({r["config_id"] for r in records}):
        group = [r for r in records if r["config_id"] == config_id and r.get("legal") is True and r.get("area") is not None]
        if not group:
            continue
        best = min(group, key=lambda r: (r["area"], r["aspect_ratio"]))
        layout_path = Path(best["layout_path"])
        payload = json.loads(layout_path.read_text(encoding="utf-8"))
        for name, item in payload.get("layout", {}).items():
            rows.append({"config_id": config_id, "seed": best["seed"], "area": best["area"], "aspect_ratio": best["aspect_ratio"], "block": name, **item})
    _write_csv(path, rows, ["config_id", "seed", "area", "aspect_ratio", "block", "x", "y", "rotation"])


def _environment() -> dict:
    return {
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "rng": "random.Random (CPython seeded Mersenne Twister)",
    }


def _write_report(path: Path, *, records: list[dict], summaries: list[dict], audit: dict, code_hash: str, command: str, environment: dict, assumptions: dict) -> None:
    lines = [
        "# Q1 V2 数据处理与模型报告",
        "",
        "- 状态：REVIEWING",
        "- 问题：Q1",
        "- 负责人：钟江铭（P1/P2）",
        "- 交叉复核：蔡乔夕",
        f"- 更新：{time.strftime('%Y-%m-%d')}",
        "- 范围：n100 开发、消融与粗筛；不包含 n200 正式选型、n300 留出或 P0 实现。",
        "",
        "## 1. 数据处理与口径",
        "",
        "Q1 只读取 `data/raw/附件/*.blocks`。本阶段不使用 `.nets` 或 `.pl`，不修改原始附件。解析要求声明块数与有效块数一致、模块名唯一、每个模块为四点正矩形、宽高为正；不满足的记录进入排除原因，不静默删除。",
        "",
        "```text",
        json.dumps(audit, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 2. 模型定义",
        "",
        "节点变量为 B*-Tree 的根、左右子节点关系、模块标签和旋转变量 `r_i∈{0,90}`。左子节点放在父模块右侧，右子节点与父模块同横坐标；模块纵坐标由 contour 在其横向区间的最大高度确定。该解码结构保证候选布局不发生正面积重叠，最终仍由共享评价器和独立审计复核。",
        "",
        "对布局包围盒 `W,H`，主目标为 `min (W·H)`；面积相同才最小化 `max(W,H)/min(W,H)`。内部 Fast-SA 劣解接受概率为 `min(1, exp(-Δ/T))`，初温由平均上坡代价和初始接受概率 `0.9` 标定，采用论文中的 `c=100,k=7` 三阶段温度更新。",
        "",
        "P1 使用旋转、节点移动和节点交换。P2 在 P1 上分别测试定向扰动、布局及整体 90° 对称状态去重，以及两个组件同时开启。搜索指标始终采用精确字典序；相对 0.5% 只作为跨种子工程非劣比较假设。",
        "",
        "## 3. 入口、参数与环境",
        "",
        f"实际批量命令：`{command}`",
        "",
        f"代码哈希：`{code_hash}`",
        "",
        "```json",
        json.dumps({"environment": environment, "assumptions": assumptions}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 4. n100 阶段运行结果",
        "",
        "以下结果仅是固定预算下的开发粗筛，不是最终模型有效性或优于 P0 的结论。失败运行保留在完整明细中。",
        "",
        "| 配置 | 合法/总数 | success | timeout | no_feasible | crash | 最好面积 | 中位面积 | 中位长宽比 | 中位评价次数 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['config_id']} | {row['legal_runs']}/{row['runs']} | {row['status_success']} | {row['status_timeout']} | {row['status_no_feasible']} | {row['status_crash']} | {row['best_area']} | {row['median_area']} | {row['median_aspect_ratio']} | {row['median_evaluations']} |"
        )
    lines.extend(
        [
            "",
            "面积持平容差和主模型选型仍需 n200 正式协议；P0 当前未接入，因此本报告不宣称 P1/P2 相对基线的优越性，也不代替两人共同冻结 C3。",
            "",
            "## 5. 证据文件",
            "",
            "- `data/processed/q1_v2_input_audit.json`：Q1 输入审计与哈希。",
            "- `outputs/q1/tables/v2_n100_run_details.csv`：全部配置和种子的运行明细。",
            "- `outputs/q1/tables/v2_n100_ablation_summary.csv`：配置汇总。",
            "- `outputs/q1/tables/v2_n100_paired_differences.csv`：相同种子的配对差值。",
            "- `outputs/q1/tables/v2_n100_representative_layouts.csv`：各配置代表性完整布局。",
            "- `outputs/q1/_runtime/`：逐次布局和日志；不进入最终结果目录。",
            "",
            "## 6. 未解决事项",
            "",
            "1. Q1 P0 尚未上传，Q1 整体 V2 验收不能闭环。",
            "2. n200 前仍需由两人共同冻结候选、预算、机器线程、RNG 和非劣判定。",
            "3. n100 粗筛不构成最终模型选择；任何论文确定数字须等待 V3 的正式比较和独立复核。",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_one(args: argparse.Namespace) -> int:
    raw_dir = Path(args.raw)
    output_root = Path(args.output_root)
    instance = _load_instance(raw_dir, args.instance)
    directed = args.directed_moves if args.directed_moves is not None else args.candidate == "Q1-BT-D"
    dedup = args.state_dedup if args.state_dedup is not None else args.candidate == "Q1-BT-D"
    config = Q1SearchConfig(
        candidate=args.candidate,
        directed_moves=directed,
        state_dedup=dedup,
        max_evaluations=args.max_evaluations,
        time_limit=args.time_limit,
        restarts=args.restarts,
    )
    code_hash = _code_hash()
    result = search_q1(instance, config, args.seed)
    record = _run_record(args.instance, args.config_id or args.candidate, config, args.seed, result, code_hash)
    record = _write_single_run(output_root, args.instance, args.config_id or args.candidate, args.seed, config, result, record)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0 if result.status in {"success", "timeout"} and result.formal_metrics.get("legal") is True else 1


def _paired_rows(records: list[dict]) -> list[dict]:
    p1 = {(r["seed"]): r for r in records if r["config_id"] == "P1"}
    rows = []
    for config_id in sorted({r["config_id"] for r in records if r["config_id"] != "P1"}):
        for row in records:
            if row["config_id"] != config_id or row["seed"] not in p1:
                continue
            base = p1[row["seed"]]
            rows.append(
                {
                    "config_id": config_id,
                    "seed": row["seed"],
                    "p1_area": base.get("area"),
                    "candidate_area": row.get("area"),
                    "area_delta": (row["area"] - base["area"]) if row.get("area") is not None and base.get("area") is not None else None,
                    "p1_aspect_ratio": base.get("aspect_ratio"),
                    "candidate_aspect_ratio": row.get("aspect_ratio"),
                    "aspect_delta": (row["aspect_ratio"] - base["aspect_ratio"]) if row.get("aspect_ratio") is not None and base.get("aspect_ratio") is not None else None,
                    "p1_legal": base.get("legal"),
                    "candidate_legal": row.get("legal"),
                }
            )
    return rows


def batch(args: argparse.Namespace) -> int:
    raw_dir = Path(args.raw)
    runtime_root = Path(args.runtime_root)
    table_root = Path(args.table_root)
    instance = _load_instance(raw_dir, args.instance)
    seeds = _parse_seeds(args.seeds)
    configs = []
    for config_id, candidate, directed, dedup in CONFIGS:
        configs.append(
            (
                config_id,
                Q1SearchConfig(
                    candidate=candidate,
                    directed_moves=directed,
                    state_dedup=dedup,
                    max_evaluations=args.max_evaluations,
                    time_limit=args.time_limit,
                    restarts=args.restarts,
                ),
            )
        )
    code_hash = _code_hash()
    records: list[dict] = []
    for config_id, config in configs:
        for seed in seeds:
            result = search_q1(instance, config, seed)
            record = _run_record(args.instance, config_id, config, seed, result, code_hash)
            records.append(_write_single_run(runtime_root, args.instance, config_id, seed, config, result, record))
            print(f"{config_id} seed={seed} status={result.status} legal={record['legal']} area={record['area']} evaluations={result.evaluations}", flush=True)

    audit = _input_audit(raw_dir, ("n100", "n200", "n300"))
    processed_path = Path(args.processed_audit)
    _json_dump(processed_path, audit)
    summaries = _summary_rows(records)
    detail_fields = list(records[0])
    _write_csv(table_root / "v2_n100_run_details.csv", records, detail_fields)
    summary_fields = list(summaries[0]) if summaries else []
    _write_csv(table_root / "v2_n100_ablation_summary.csv", summaries, summary_fields)
    paired = _paired_rows(records)
    _write_csv(table_root / "v2_n100_paired_differences.csv", paired, list(paired[0]) if paired else ["config_id", "seed"])
    _write_representative_layouts(table_root / "v2_n100_representative_layouts.csv", records, runtime_root)
    assumptions = {
        "p0_scope": "P1/P2 only; P0 remains a missing dependency",
        "area_noninferiority_relative_tolerance": 0.005,
        "n100_seeds": seeds,
        "max_evaluations_per_run": args.max_evaluations,
        "time_limit_seconds_per_run": args.time_limit,
        "restarts_per_run": args.restarts,
    }
    snapshot = {
        "code_hash": code_hash,
        "configs": [{"config_id": config_id, **config.as_dict(), "config_hash": _config_hash(config)} for config_id, config in configs],
        "environment": _environment(),
        "assumptions": assumptions,
        "command": args.command_text,
    }
    _json_dump(table_root / "v2_n100_config_snapshot.json", snapshot)
    _write_report(
        Path(args.report),
        records=records,
        summaries=summaries,
        audit=audit,
        code_hash=code_hash,
        command=args.command_text,
        environment=snapshot["environment"],
        assumptions=assumptions,
    )
    print(json.dumps({"runs": len(records), "summary": summaries, "report": args.report}, ensure_ascii=False, indent=2))
    return 0 if all(r["legal"] is True for r in records if r["status"] != "crash") else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Q1 B*-Tree/Fast-SA V2 runner")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one candidate and seed")
    run.add_argument("--instance", default="n100")
    run.add_argument("--candidate", choices=["Q1-BT", "Q1-BT-D"], required=True)
    run.add_argument("--seed", type=int, required=True)
    run.add_argument("--max-evaluations", type=int, default=100_000)
    run.add_argument("--time-limit", type=float, default=60.0)
    run.add_argument("--restarts", type=int, default=4)
    run.add_argument("--directed-moves", type=_on_off, default=None)
    run.add_argument("--state-dedup", type=_on_off, default=None)
    run.add_argument("--raw", default="data/raw/附件")
    run.add_argument("--output-root", default="outputs/q1/_runtime")
    run.add_argument("--config-id", default=None)
    run.set_defaults(handler=run_one)

    batch_parser = sub.add_parser("batch", help="run the four n100 V2 configurations")
    batch_parser.add_argument("--instance", default="n100")
    batch_parser.add_argument("--seeds", default="1101-1110")
    batch_parser.add_argument("--max-evaluations", type=int, default=100_000)
    batch_parser.add_argument("--time-limit", type=float, default=60.0)
    batch_parser.add_argument("--restarts", type=int, default=4)
    batch_parser.add_argument("--raw", default="data/raw/附件")
    batch_parser.add_argument("--runtime-root", default="outputs/q1/_runtime")
    batch_parser.add_argument("--table-root", default="outputs/q1/tables")
    batch_parser.add_argument("--processed-audit", default="data/processed/q1_v2_input_audit.json")
    batch_parser.add_argument("--report", default="outputs/q1/reports/v2_model_report.md")
    batch_parser.set_defaults(handler=batch)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "batch":
        args.command_text = "python -B -m src.q1 batch " + " ".join(sys.argv[2:] if argv is None else argv[1:])
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
