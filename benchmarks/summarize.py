"""Generate a compact result table and chart from plot_backends.py JSON output."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "_deps"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--chart", type=Path)
    args = parser.parse_args()
    results = []
    for path in args.directory.glob("*.json"):
        result = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(result, dict) and "rows" in result:
            results.append(result)
    print("| Backend | Points/series | Refresh median / p95 (ms) | Pan+zoom median / p95 (ms) |")
    print("|---|---:|---:|---:|")
    notes = []
    for result in results:
        rows = result["rows"]
        for refresh in [r for r in rows if r["mode"] == "refresh"]:
            count = refresh.get("points_per_series")
            zoom = next(r for r in rows if r["mode"] == "pan_zoom" and r.get("points_per_series") == count)
            count_text = f"{count:,}" if count else f"{refresh['raw_samples_per_series']:,} raw"
            print(f"| {result['backend']} | {count_text} | {refresh['median_ms']:.2f} / {refresh['p95_ms']:.2f} | {zoom['median_ms']:.2f} / {zoom['p95_ms']:.2f} |")
        if "storage_read_five_series" in result:
            notes.append(f"\n{result['backend']} storage/conversion: {result['storage_read_five_series']}; "
                  f"build time: {result['build_seconds']:.2f} s; "
                  f"plotted counts: {rows[0]['plotted_points_per_series']}\n")
    for note in notes:
        print(note)
    if args.chart:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        candidates = [r for r in results if not r["backend"].startswith("current-widget")]
        candidates.sort(key=lambda r: next(x["median_ms"] for x in r["rows"] if x["points_per_series"] == 1000 and x["mode"] == "pan_zoom"))
        fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
        names = [r["backend"] for r in candidates]
        for ax, mode in zip(axes, ("refresh", "pan_zoom")):
            values = [next(x["median_ms"] for x in r["rows"] if x["points_per_series"] == 1000 and x["mode"] == mode) for r in candidates]
            colors = ["#b7791f" if name in ("qpainter", "qgraphicsview", "opengl") else "#2878a0" for name in names]
            ax.barh(names, values, color=colors)
            ax.set_title("Fixed axes" if mode == "refresh" else "Changing X range")
            ax.set_xlabel("Median update + render time (ms); lower is better")
            ax.set_xscale("log")
            ax.grid(axis="x", alpha=.2)
            for i, value in enumerate(values):
                ax.text(value*1.04, i, f"{value:.1f}", va="center", fontsize=9)
            ax.set_xlim(right=max(values)*1.7)
        axes[0].invert_yaxis()
        fig.suptitle("Five traces × 1,000 submitted points, 1000 × 900 window")
        fig.text(.02, .015, "Blue: plotting libraries with axes. Brown: incomplete custom prototypes (less work). Logarithmic time axis.", fontsize=9)
        fig.tight_layout(rect=(0,.05,1,.95))
        fig.savefig(args.chart)


if __name__ == "__main__":
    main()
