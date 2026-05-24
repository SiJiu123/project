from pathlib import Path
from typing import Iterable

import pandas as pd

from pipeline.common.io_utils import describe_file


def _safe_float(value):
    if value is None:
        return ""
    return f"{float(value):.6f}"


def render_parity_report(
    results_root: Path,
    dataset: str,
    baseline: dict,
    standard_dir: Path,
    model_names: Iterable[str],
) -> Path:
    train_id = baseline["train_id"]
    test_id = baseline["test_id"]
    lines = [
        "# Parity Report",
        "",
        f"Dataset: `{dataset}`",
        "",
        f"Baseline train/test: `{train_id}` / `{test_id}`",
        f"Baseline pseudo-bulk method: `{baseline.get('pseudo_bulk_method', '')}`",
        "",
        "## Input Evidence",
        "",
        "| File | Exists | Size | SHA256 |",
        "|---|---|---:|---|",
    ]

    evidence_files = [
        standard_dir / f"{train_id}_counts.txt",
        standard_dir / f"{train_id}_celltypes.txt",
        standard_dir / f"{test_id}_bulk_X.txt",
        standard_dir / f"{test_id}_bulk_obs.txt",
    ]
    for path in evidence_files:
        info = describe_file(path)
        lines.append(
            f"| `{path.name}` | {info['exists']} | {info['size'] or ''} | `{info['sha256'] or ''}` |"
        )

    lines.extend(
        [
            "",
            "## Metrics",
            "",
            "| Model | Old Pearson | Current Pearson | Old CCC | Current CCC | Old RMSE | Current RMSE |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for model_name in model_names:
        key = str(model_name).lower()
        old = baseline.get("models", {}).get(key, {})
        metrics_path = results_root / key / "metrics_summary.csv"
        current = {}
        if metrics_path.exists():
            df = pd.read_csv(metrics_path)
            if not df.empty:
                current = df.iloc[0].to_dict()
        lines.append(
            "| {model} | {old_p} | {cur_p} | {old_c} | {cur_c} | {old_r} | {cur_r} |".format(
                model=key,
                old_p=_safe_float(old.get("Pearson")),
                cur_p=_safe_float(current.get("Pearson")),
                old_c=_safe_float(old.get("CCC")),
                cur_c=_safe_float(current.get("CCC")),
                old_r=_safe_float(old.get("RMSE")),
                cur_r=_safe_float(current.get("RMSE")),
            )
        )

    for model_name in model_names:
        key = str(model_name).lower()
        old_typewise = baseline.get("models", {}).get(key, {}).get("typewise")
        if not old_typewise:
            continue
        typewise_path = results_root / key / "typewise_ccc.csv"
        current_typewise = {}
        if typewise_path.exists():
            df = pd.read_csv(typewise_path)
            if "type" in df.columns and "CCC" in df.columns:
                current_typewise = {
                    str(row["type"]): float(row["CCC"])
                    for _, row in df.iterrows()
                }
        lines.extend(
            [
                "",
                f"## Typewise CCC: `{key}`",
                "",
                "| Cell Type | Old CCC | Current CCC |",
                "|---|---:|---:|",
            ]
        )
        for cell_type, old_value in old_typewise.items():
            lines.append(
                f"| {cell_type} | {_safe_float(old_value)} | {_safe_float(current_typewise.get(cell_type))} |"
            )

    out_path = results_root / "parity_report.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path
