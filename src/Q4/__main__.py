from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from .model import Q4Instance
from .sa import solve_sa
from .search import solve_exact


def _code_manifest() -> tuple[str, list[dict]]:
    root = Path(__file__).parents[2]
    paths = sorted(list((root / "src" / "Q4").glob("*.py")) + [root / "src" / "_internal" / "audit.py"], key=lambda path: path.relative_to(root).as_posix())
    digest = hashlib.sha256()
    manifest = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        digest.update(relative.encode("utf-8"))
        digest.update(data)
        manifest.append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return digest.hexdigest(), manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q4 integer-grid exact/SA runner")
    parser.add_argument("mode", choices=("exact", "sa"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-evaluations", type=int, default=1000)
    parser.add_argument("--time-limit", type=float, default=60.0)
    parser.add_argument("--restarts", type=int, default=4)
    parser.add_argument("--domain-width", type=int, default=9)
    parser.add_argument("--domain-height", type=int, default=9)
    parser.add_argument("--upper-area", type=int, default=36)
    args = parser.parse_args(argv)
    if args.time_limit < 0:
        parser.error("time_limit must be non-negative")
    instance = Q4Instance.default()
    try:
        if args.mode == "exact":
            result = solve_exact(instance, upper_area=args.upper_area, time_limit=args.time_limit)
        else:
            if args.max_evaluations <= 0:
                parser.error("max_evaluations must be positive")
            if args.restarts <= 0:
                parser.error("restarts must be positive")
            if args.domain_width <= 0 or args.domain_height <= 0:
                parser.error("domain dimensions must be positive")
            result = solve_sa(instance, seed=args.seed, max_evaluations=args.max_evaluations, time_limit=args.time_limit, restarts=args.restarts, domain=(args.domain_width, args.domain_height))
    except ValueError as error:
        parser.error(str(error))
    result_data = result.as_dict()
    if args.mode == "exact":
        config = {"upper_area": args.upper_area, "time_limit": args.time_limit, "grid_step": 1, "rotations": [0, 90, 180, 270], "search_domain": "integer_translation_grid"}
    else:
        config = result.config
    code_hash, code_manifest = _code_manifest()
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    command = subprocess.list2cmdline([sys.executable, "-B", "-m", "src.Q4", *sys.argv[1:]])
    payload = {
        "problem": "Q4",
        "mode": args.mode,
        "status": result.status,
        "code_hash": code_hash,
        "code_manifest": code_manifest,
        "config": config,
        "config_hash": config_hash,
        "command": command,
        "environment": {"python": sys.version, "platform": platform.platform(), "cwd": str(Path.cwd()), "cpu_count": os.cpu_count()},
        "layout": result_data.get("layout", {}),
        "formal": result_data.get("evaluation", {}),
        "audit": {},
        "formal_audit_match": result_data.get("formal_audit_match", False),
        "domain": result_data.get("domain", {}),
        "result": result_data,
    }
    if result.evaluation is not None and result.layout:
        from src._internal.audit import audit_layout

        outline = (0, 0, result.evaluation.width, result.evaluation.height) if args.mode == "exact" else None
        payload["audit"] = audit_layout(instance, result.layout, outline)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
