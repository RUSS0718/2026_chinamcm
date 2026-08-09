"""Render the exact and SA1108 representative Q4 layouts with matplotlib only."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle


ROOT = Path(__file__).resolve().parents[2]
VERTICES = ROOT / "outputs" / "q4" / "tables" / "v2_representative_layout_vertices.csv"
OUT = ROOT / "outputs" / "q4" / "figures" / "v2_representative_layouts"
COLORS = {"b1": "#4477AA", "b2": "#EE6677", "b3": "#228833", "b4": "#CCBB44"}


def read_vertices() -> dict[str, dict]:
    if not VERTICES.is_file():
        raise SystemExit(f"missing vertices CSV: {VERTICES}")
    panels: dict[str, dict] = {}
    with VERTICES.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    for route in ("exact", "sa"):
        selected = [row for row in rows if row["route"] == route]
        if not selected:
            raise SystemExit(f"missing route in vertices CSV: {route}")
        modules: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for row in selected:
            modules[row["module"]].append((float(row["x"]), float(row["y"])))
        if set(modules) != set(COLORS):
            raise SystemExit(f"unexpected module set for {route}: {set(modules)}")
        first = selected[0]
        panels[route] = {
            "modules": modules,
            "W": float(first["W"]),
            "H": float(first["H"]),
            "area": float(first["area"]),
            "status": first["status"],
            "legal": first["legal"],
            "audit": first["formal_audit_match"],
            "seed": first["seed"],
        }
    return panels


def draw_panel(ax, panel: dict, label: str, title: str, subtitle: str) -> None:
    W, H = panel["W"], panel["H"]
    ax.add_patch(Rectangle((0, 0), W, H, fill=False, edgecolor="#222222", linewidth=1.0, zorder=5))
    for module in ("b1", "b2", "b3", "b4"):
        points = panel["modules"][module]
        patch = Polygon(points, closed=True, facecolor=COLORS[module], edgecolor="#1f1f1f", linewidth=0.8, alpha=0.86, zorder=3)
        ax.add_patch(patch)
        cx = sum(x for x, _ in points) / len(points)
        cy = sum(y for _, y in points) / len(points)
        ax.text(cx, cy, module, ha="center", va="center", fontsize=7, weight="bold", color="#111111", zorder=6)
    ax.set_xlim(-0.25, W + 0.25)
    ax.set_ylim(-0.25, H + 0.25)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x (grid units)", fontsize=7)
    ax.set_ylabel("y (grid units)", fontsize=7)
    ax.tick_params(labelsize=6.5, width=0.6, length=3)
    ax.grid(True, color="#d9d9d9", linewidth=0.45, alpha=0.65, zorder=0)
    ax.set_title(f"{label} {title}\n{subtitle}", loc="left", fontsize=8, pad=6)


def main() -> None:
    panels = read_vertices()
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
    })
    fig, axes = plt.subplots(1, 2, figsize=(180 / 25.4, 80 / 25.4), constrained_layout=False)
    draw_panel(axes[0], panels["exact"], "(a)", "Exact primary evidence", "status=optimal | area=24 | deadspace=0 | audit match")
    draw_panel(axes[1], panels["sa"], "(b)", "SA seed 1108 validation", "status=success | area=24 | deadspace=0 | audit match")
    handles = [Polygon([[0, 0]], facecolor=COLORS[module], edgecolor="#1f1f1f", label=module, alpha=0.86) for module in ("b1", "b2", "b3", "b4")]
    fig.legend(handles=handles, labels=["b1", "b2", "b3", "b4"], loc="upper center", bbox_to_anchor=(0.5, 0.99), ncol=4, frameon=False, fontsize=7, handlelength=1.2, columnspacing=1.2)
    fig.text(0.5, 0.015, "Exact proves the 4×6 zero-deadspace integer result; SA1108 independently matched area 24 but does not prove optimality.", ha="center", va="bottom", fontsize=6.5)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.80, bottom=0.17, wspace=0.34)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(f"{OUT}.svg", bbox_inches="tight")
    fig.savefig(f"{OUT}.pdf", bbox_inches="tight")
    fig.savefig(f"{OUT}.png", dpi=600, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {OUT}.svg/.pdf/.png")


if __name__ == "__main__":
    main()
