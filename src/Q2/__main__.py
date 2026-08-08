"""Command-line runner for Q2-SP, Q2-BT, and Q2-HG."""

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

from .._internal.parser import parse_instance_files
from .common import Q2SearchConfig, square_side
from .p0 import search_p0
from .p1_p2 import search_p1_p2


CANDIDATES = ("Q2-SP", "Q2-BT", "Q2-HG")


def _json_dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _code_hash() -> str:
    digest = hashlib.sha256()
    files = [Path(__file__), Path(__file__).with_name("common.py"), Path(__file__).with_name("p0.py"), Path(__file__).with_name("p1_p2.py")]
    files += [Path(__file__).parents[1] / "_internal" / name for name in ("parser.py", "evaluator.py", "audit.py", "geometry.py")]
    for path in files:
        digest.update(path.as_posix().encode("utf-8"))
        digest.update(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
    return digest.hexdigest()


def _config_hash(config: Q2SearchConfig) -> str:
    return hashlib.sha256(json.dumps(config.as_dict(), sort_keys=True).encode("utf-8")).hexdigest()


def _on_off(value: str) -> bool:
    lowered = value.lower()
    if lowered in {"on", "true", "1", "yes"}:
        return True
    if lowered in {"off", "false", "0", "no"}:
        return False
    raise argparse.ArgumentTypeError("expected on or off")


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


def _load_instance(raw_dir: Path, instance_name: str):
    paths = tuple(raw_dir / f"{instance_name}{suffix}" for suffix in (".blocks", ".nets", ".pl"))
    if not all(path.is_file() for path in paths):
        missing = ", ".join(str(path) for path in paths if not path.is_file())
        raise FileNotFoundError(missing)
    instance = parse_instance_files(*paths)
    references = {pin for net in instance.nets for pin in net.pins}
    known = set(instance.blocks) | set(instance.terminals)
    missing = sorted(references - known)
    if missing or sum(len(net.pins) for net in instance.nets) != instance.declared_pins:
        raise ValueError(f"Q2 input audit failed: missing={missing}, pin_count={sum(len(net.pins) for net in instance.nets)}")
    if set(instance.terminals) != set(instance.declared_terminal_names):
        raise ValueError("Q2 input audit failed: terminal declarations and .pl positions differ")
    return instance


def _config(candidate: str, args: argparse.Namespace) -> Q2SearchConfig:
    adaptive = args.adaptive_constraints if args.adaptive_constraints is not None else candidate != "Q2-SP"
    hypergraph = args.hypergraph_init if args.hypergraph_init is not None else candidate == "Q2-HG"
    return Q2SearchConfig(
        candidate=candidate,
        adaptive_constraints=adaptive,
        hypergraph_init=hypergraph,
        max_evaluations=args.max_evaluations,
        time_limit=args.time_limit,
        restarts=args.restarts,
    )


def _search(instance, config: Q2SearchConfig, seed: int):
    return search_p0(instance, config, seed) if config.candidate == "Q2-SP" else search_p1_p2(instance, config, seed)


def _layout_dict(result) -> dict:
    if result.best is None:
        return {}
    return {name: {"x": x, "y": y, "rotation": rotation} for name, (x, y, rotation) in sorted(result.best.layout.items())}


def _record(instance_name: str, config_id: str, config: Q2SearchConfig, seed: int, result, code_hash: str, side: float) -> dict:
    formal = result.formal_metrics
    audit = result.audit_metrics
    placement_width = result.best.packed.width if result.best is not None else None
    placement_height = result.best.packed.height if result.best is not None else None
    boundary_overflow = result.best.overflow if result.best is not None else None
    return {
        "instance": instance_name,
        "problem": "Q2",
        "config_id": config_id,
        "candidate": config.candidate,
        "adaptive_constraints": config.adaptive_constraints,
        "hypergraph_init": config.hypergraph_init,
        "seed": seed,
        "code_hash": code_hash,
        "config_hash": _config_hash(config),
        "max_evaluations": config.max_evaluations,
        "time_limit": config.time_limit,
        "restarts": config.restarts,
        "dead_space_ratio_target": config.dead_space_ratio,
        "rho_target": config.dead_space_ratio / (1.0 + config.dead_space_ratio),
        "outline_side": side,
        "placement_width": placement_width,
        "placement_height": placement_height,
        "boundary_overflow": boundary_overflow,
        "status": result.status,
        "legal": audit.get("legal"),
        "W": formal.get("W"),
        "H": formal.get("H"),
        "area": formal.get("area"),
        "module_area": formal.get("module_area"),
        "deadspace": formal.get("deadspace"),
        "dead_space_ratio": formal.get("dead_space_ratio"),
        "rho": formal.get("rho"),
        "HPWL": formal.get("HPWL"),
        "first_feasible_evaluation": result.first_feasible_evaluation,
        "first_feasible_time": result.first_feasible_time,
        "runtime": result.runtime,
        "evaluations": result.evaluations,
        "proposals": result.proposals,
        "accepted": result.accepted,
        "restarts_completed": result.restarts_completed,
        "formal_audit_match": formal == audit,
        "error": result.error or "",
    }


def _write_run(output_root: Path, instance_name: str, config_id: str, seed: int, config: Q2SearchConfig, result, record: dict) -> dict:
    run_dir = output_root / instance_name / config_id / f"seed_{seed}"
    layout_path = run_dir / "layout.json"
    log_path = run_dir / "events.jsonl"
    _json_dump(layout_path, {"record": record, "config": config.as_dict(), "layout": _layout_dict(result), "formal_metrics": result.formal_metrics, "audit_metrics": result.audit_metrics})
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps({"event": "run_complete", **record}, ensure_ascii=False) + "\n", encoding="utf-8")
    out = dict(record)
    out["layout_path"] = layout_path.as_posix()
    out["log_path"] = log_path.as_posix()
    return out


def _summary(records: list[dict]) -> list[dict]:
    rows = []
    for config_id in sorted({record["config_id"] for record in records}):
        group = [record for record in records if record["config_id"] == config_id]
        legal = [record for record in group if record["legal"] is True and record["HPWL"] is not None]
        hpwls = [float(record["HPWL"]) for record in legal]
        best = min(legal, key=lambda row: row["HPWL"]) if legal else None
        rows.append({
            "config_id": config_id,
            "candidate": group[0]["candidate"],
            "runs": len(group),
            "legal_runs": len(legal),
            "status_success": sum(row["status"] == "success" for row in group),
            "status_timeout": sum(row["status"] == "timeout" for row in group),
            "status_no_feasible": sum(row["status"] == "no_feasible" for row in group),
            "status_crash": sum(row["status"] == "crash" for row in group),
            "best_HPWL": best["HPWL"] if best else None,
            "median_HPWL": statistics.median(hpwls) if hpwls else None,
            "median_evaluations": statistics.median(float(row["evaluations"]) for row in group),
            "best_layout_path": best["layout_path"] if best else "",
        })
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_one(args: argparse.Namespace) -> int:
    instance = _load_instance(Path(args.raw), args.instance)
    config = _config(args.candidate, args)
    side = square_side(instance, config.dead_space_ratio)
    result = _search(instance, config, args.seed)
    record = _record(args.instance, args.config_id or args.candidate, config, args.seed, result, _code_hash(), side)
    record = _write_run(Path(args.output_root), args.instance, args.config_id or args.candidate, args.seed, config, result, record)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0 if record["legal"] is True and record["formal_audit_match"] else 1


def batch(args: argparse.Namespace) -> int:
    instance = _load_instance(Path(args.raw), args.instance)
    seeds = _parse_seeds(args.seeds)
    candidates = _parse_candidates(args.candidates)
    side = square_side(instance)
    code_hash = _code_hash()
    records = []
    configs = []
    for candidate in candidates:
        config = _config(candidate, args)
        configs.append(config)
        for seed in seeds:
            result = _search(instance, config, seed)
            records.append(_write_run(Path(args.runtime_root), args.instance, candidate, seed, config, result, _record(args.instance, candidate, config, seed, result, code_hash, side)))
    summaries = _summary(records)
    table_root = Path(args.table_root)
    _write_csv(table_root / f"{args.run_id}_run_details.csv", records)
    _write_csv(table_root / f"{args.run_id}_summary.csv", summaries)
    _json_dump(table_root / f"{args.run_id}_config_snapshot.json", {"command": args.command_text, "code_hash": code_hash, "environment": {"python": sys.version, "implementation": platform.python_implementation(), "platform": platform.platform(), "logical_cpu_count": os.cpu_count()}, "configs": [{**config.as_dict(), "config_hash": _config_hash(config)} for config in configs], "seeds": seeds})
    print(json.dumps({"runs": len(records), "summary": summaries}, ensure_ascii=False, indent=2))
    return 0 if all(record["legal"] is True and record["formal_audit_match"] for record in records) else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Q2 fixed-outline placement runner")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "batch"):
        item = sub.add_parser(command)
        item.add_argument("--instance", default="n100")
        if command == "run":
            item.add_argument("--candidate", choices=CANDIDATES, required=True)
            item.add_argument("--seed", type=int, required=True)
            item.add_argument("--output-root", default="outputs/q2/_runtime")
            item.add_argument("--config-id", default=None)
        else:
            item.add_argument("--candidates", default="Q2-SP,Q2-BT,Q2-HG")
            item.add_argument("--seeds", default="1101-1110")
            item.add_argument("--runtime-root", default="outputs/q2/_runtime/v2")
            item.add_argument("--table-root", default="outputs/q2/tables")
            item.add_argument("--run-id", default="v2_p0_p1_p2")
        item.add_argument("--max-evaluations", type=int, default=100_000)
        item.add_argument("--time-limit", type=float, default=60.0)
        item.add_argument("--restarts", type=int, default=4)
        item.add_argument("--adaptive-constraints", type=_on_off, default=None)
        item.add_argument("--hypergraph-init", type=_on_off, default=None)
        item.add_argument("--raw", default="data/raw/附件")
        item.set_defaults(handler=run_one if command == "run" else batch)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "batch":
        args.command_text = "python -B -m src.Q2 batch " + " ".join(sys.argv[2:] if argv is None else argv[1:])
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
