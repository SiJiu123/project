import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from pipeline.common.naming import summary_metrics_file


def render_leaderboard(
    results_root: Path,
    dataset: str,
    reference_id: str,
    bulk_id: str,
    model_names: Iterable[str],
) -> Path:
    report_by_model = {}
    run_report_path = results_root / "run_report.json"
    if run_report_path.exists():
        with open(run_report_path, "r", encoding="utf-8") as f:
            for item in json.load(f):
                report_by_model[str(item.get("model", "")).lower()] = item

    rows = []
    for model_name in model_names:
        key = model_name.lower()
        metrics_path = summary_metrics_file(results_root / key)
        report_item = report_by_model.get(key, {})

        row = {
            "model": key,
            "CCC": None,
            "RMSE": None,
            "status": str(report_item.get("status", "MISSING")),
        }

        if metrics_path.exists():
            metrics = pd.read_csv(metrics_path)
            if not metrics.empty:
                row["CCC"] = float(metrics.loc[0, "CCC"])
                row["RMSE"] = float(metrics.loc[0, "RMSE"])
                if row["status"] == "MISSING":
                    row["status"] = "OK"

        rows.append(row)

    ok_rows = [r for r in rows if r["CCC"] is not None]
    other_rows = [r for r in rows if r["CCC"] is None]
    ok_rows.sort(key=lambda r: (-r["CCC"], r["RMSE"], r["model"]))
    ranked_rows = ok_rows + other_rows

    lines = [
        "# Leaderboard",
        "",
        f"Dataset: {dataset} (train={reference_id}, test={bulk_id})",
        "",
        "| Rank | Model | CCC | RMSE | Status |",
        "|---:|---|---:|---:|---|",
    ]

    for idx, row in enumerate(ranked_rows, start=1):
        ccc_text = f"{row['CCC']:.6f}" if row["CCC"] is not None else ""
        rmse_text = f"{row['RMSE']:.6f}" if row["RMSE"] is not None else ""
        lines.append(
            f"| {idx} | {row['model']} | {ccc_text} | {rmse_text} | {row['status']} |"
        )

    out_path = results_root / "leaderboard.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path
