"""Public command-line interface for Question 1 placement candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import sys

from .._internal.parser import parse_blocks_file
from .p0 import search_p0
from .p1_p2 import Q1SearchConfig, SearchResult, search_q1


CANDIDATES = ("Q1-G", "Q1-SP", "Q1-BT", "Q1-BT-D")


def _json_dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _normalized_file_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _code_hash() -> str:
    files = (
        Path(__file__),
        Path(__file__).with_name("p1_p2.py"),
        Path(__file__).with_name("p0.py"),
        Path(__file__).parents[1] / "_internal" / "parser.py",
        Path(__file__).parents[1] / "_internal" / "evaluator.py",
        Path(__file__).parents[1] / "_internal" / "audit.py",
        Path(__file__).parents[1] / "_internal" / "geometry.py",
    )
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


def _parse_candidates(value: str) -> list[str]:
    candidates = [item.strip() for item in value.split(",") if item.strip()]
    unknown = sorted(set(candidates) - set(CANDIDATES))
    if not candidates or unknown:
        raise ValueError(f"unsupported candidates: {', '.join(unknown) or value}")
    return candidates


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


def _config(candidate: str, args: argparse.Namespace) -> Q1SearchConfig:
    directed = args.directed_moves if getattr(args, "directed_moves", None) is not None else candidate == "Q1-BT-D"
    dedup = args.state_dedup if getattr(args, "state_dedup", None) is not None else candidate == "Q1-BT-D"
    return Q1SearchConfig(
        candidate=candidate,
        directed_moves=directed,
        state_dedup=dedup,
        max_evaluations=args.max_evaluations,
        time_limit=args.time_limit,
        restarts=args.restarts,
    )


def _search(instance, config: Q1SearchConfig, seed: int) -> SearchResult:
    return search_p0(instance, config, seed) if config.candidate in {"Q1-G", "Q1-SP"} else search_q1(instance, config, seed)


def _layout_dict(result: SearchResult) -> dict:
    if result.best is None:
        return {}
    return {name: {"x": x, "y": y, "rotation": rotation} for name, (x, y, rotation) in sorted(result.best.layout.items())}


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
    _json_dump(layout_path, {"record": record, "config": config.as_dict(), "layout": _layout_dict(result), "formal_metrics": result.formal_metrics, "audit_metrics": result.audit_metrics})
    log_path.write_text(json.dumps({"event": "run_complete", **record}, ensure_ascii=False) + "\n", encoding="utf-8")
    record = dict(record)
    record["layout_path"] = layout_path.as_posix()
    record["log_path"] = log_path.as_posix()
    return record


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _summary_rows(records: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for row in records:
        groups.setdefault(row["config_id"], []).append(row)
    summaries = []
    for config_id, group in groups.items():
        legal = [row for row in group if row["legal"] is True and row["area"] is not None]
        areas = [float(row["area"]) for row in legal]
        best = min(legal, key=lambda row: (row["area"], row["aspect_ratio"])) if legal else None
        summaries.append({
            "config_id": config_id,
            "candidate": group[0]["candidate"],
            "runs": len(group),
            "legal_runs": len(legal),
            "status_success": sum(row["status"] == "success" for row in group),
            "status_timeout": sum(row["status"] == "timeout" for row in group),
            "status_no_feasible": sum(row["status"] == "no_feasible" for row in group),
            "status_crash": sum(row["status"] == "crash" for row in group),
            "best_area": best["area"] if best else None,
            "median_area": statistics.median(areas) if areas else None,
            "median_evaluations": statistics.median(float(row["evaluations"]) for row in group),
            "best_layout_path": best["layout_path"] if best else "",
        })
    return summaries


def _write_representative_layouts(path: Path, records: list[dict]) -> None:
    rows = []
    for config_id in sorted({record["config_id"] for record in records}):
        legal = [record for record in records if record["config_id"] == config_id and record["legal"] is True and record["area"] is not None]
        if not legal:
            continue
        best = min(legal, key=lambda record: (record["area"], record["aspect_ratio"]))
        payload = json.loads(Path(best["layout_path"]).read_text(encoding="utf-8"))
        for name, item in payload["layout"].items():
            rows.append({"config_id": config_id, "seed": best["seed"], "area": best["area"], "aspect_ratio": best["aspect_ratio"], "block": name, **item})
    _write_csv(path, rows, ["config_id", "seed", "area", "aspect_ratio", "block", "x", "y", "rotation"])


def _environment() -> dict:
    return {"python": sys.version, "implementation": platform.python_implementation(), "platform": platform.platform(), "logical_cpu_count": os.cpu_count(), "rng": "random.Random (CPython seeded Mersenne Twister)"}


def run_one(args: argparse.Namespace) -> int:
    instance = _load_instance(Path(args.raw), args.instance)
    config = _config(args.candidate, args)
    result = _search(instance, config, args.seed)
    record = _run_record(args.instance, args.config_id or args.candidate, config, args.seed, result, _code_hash())
    record = _write_single_run(Path(args.output_root), args.instance, args.config_id or args.candidate, args.seed, config, result, record)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0 if result.status in {"success", "timeout"} and result.formal_metrics.get("legal") is True else 1


def batch(args: argparse.Namespace) -> int:
    instance = _load_instance(Path(args.raw), args.instance)
    seeds = _parse_seeds(args.seeds)
    candidates = _parse_candidates(args.candidates)
    code_hash = _code_hash()
    runtime_root = Path(args.runtime_root)
    records = []
    configs = []
    for candidate in candidates:
        config = _config(candidate, args)
        configs.append(config)
        for seed in seeds:
            result = _search(instance, config, seed)
            record = _run_record(args.instance, candidate, config, seed, result, code_hash)
            records.append(_write_single_run(runtime_root, args.instance, candidate, seed, config, result, record))
    table_root = Path(args.table_root)
    prefix = args.run_id
    _write_csv(table_root / f"{prefix}_run_details.csv", records, list(records[0]))
    summaries = _summary_rows(records)
    _write_csv(table_root / f"{prefix}_summary.csv", summaries, list(summaries[0]))
    _write_representative_layouts(table_root / f"{prefix}_representative_layouts.csv", records)
    _json_dump(table_root / f"{prefix}_config_snapshot.json", {"command": args.command_text, "code_hash": code_hash, "environment": _environment(), "configs": [{**config.as_dict(), "config_hash": _config_hash(config)} for config in configs], "seeds": seeds})
    print(json.dumps({"runs": len(records), "summary": summaries}, ensure_ascii=False, indent=2))
    return 0 if all(record["legal"] is True and record["formal_audit_match"] for record in records) else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Q1 placement candidate runner")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run one candidate and seed")
    run.add_argument("--instance", default="n100")
    run.add_argument("--candidate", choices=CANDIDATES, required=True)
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
    batch_parser = sub.add_parser("batch", help="run a candidate set across seeds")
    batch_parser.add_argument("--instance", default="n100")
    batch_parser.add_argument("--candidates", default="Q1-G,Q1-SP,Q1-BT")
    batch_parser.add_argument("--seeds", default="1101-1110")
    batch_parser.add_argument("--max-evaluations", type=int, default=100_000)
    batch_parser.add_argument("--time-limit", type=float, default=60.0)
    batch_parser.add_argument("--restarts", type=int, default=4)
    batch_parser.add_argument("--directed-moves", type=_on_off, default=None)
    batch_parser.add_argument("--state-dedup", type=_on_off, default=None)
    batch_parser.add_argument("--raw", default="data/raw/附件")
    batch_parser.add_argument("--runtime-root", default="outputs/q1/_runtime/v2_n100_p0_p1")
    batch_parser.add_argument("--table-root", default="outputs/q1/tables")
    batch_parser.add_argument("--run-id", default="v2_n100_p0_p1")
    batch_parser.set_defaults(handler=batch)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "batch":
        args.command_text = "python -B -m src.Q1 batch " + " ".join(sys.argv[2:] if argv is None else argv[1:])
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
