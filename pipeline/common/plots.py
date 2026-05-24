from pathlib import Path
from typing import Iterable

import matplotlib
import pandas as pd
import numpy as np
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render_typewise_boxplot(results_root: Path, model_names: Iterable[str]) -> Path:
    rows = []
    ordered_models = []
    for model in model_names:
        csv_path = results_root / model / "typewise_ccc.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path)
        if "CCC" not in df.columns:
            continue
        current = pd.DataFrame(
            {
                "model": model,
                "type": df["type"].astype(str),
                "CCC": pd.to_numeric(df["CCC"], errors="coerce"),
            }
        ).dropna(subset=["CCC"])
        if current.empty:
            continue
        rows.append(current)
        ordered_models.append(model)

    if not rows:
        raise FileNotFoundError("No valid typewise_ccc.csv found for plotting")

    plot_df = pd.concat(rows, ignore_index=True)
    merged_csv = results_root / "typewise_ccc_merged.csv"
    plot_df[["model", "type", "CCC"]].to_csv(merged_csv, index=False)

    plot_df["model"] = pd.Categorical(plot_df["model"], categories=ordered_models, ordered=True)

    data = [plot_df.loc[plot_df["model"] == m, "CCC"].values for m in ordered_models]

    pretty_name = {
        "scaden": "Scaden",
        "scpdeconv": "scpDeconv",
        "tape": "TAPE",
        "music": "MuSiC",
        "cibersortx": "CIBERSORTx",
    }
    display_labels = [pretty_name.get(m, m) for m in ordered_models]

    color_cycle = [
        "#4C78A8",
        "#F58518",
        "#54A24B",
        "#E45756",
        "#72B7B2",
        "#B279A2",
    ]
    box_colors = [color_cycle[i % len(color_cycle)] for i in range(len(ordered_models))]

    plt.figure(figsize=(8, 5))
    box = plt.boxplot(data, labels=display_labels, patch_artist=True)
    for patch, color in zip(box["boxes"], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.35)

    for i, model in enumerate(ordered_models, start=1):
        y = plot_df.loc[plot_df["model"] == model, "CCC"].values
        plt.scatter(np.full(len(y), i), y, alpha=0.85, s=24, color=box_colors[i - 1])

    plt.ylabel("CCC")
    plt.ylim(-0.05, 1.05)
    plt.grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.35)
    plt.tight_layout()

    out_path = results_root / "typewise_ccc_boxplot.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    return out_path
