from datetime import datetime
from pathlib import Path
from math import sqrt
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.metrics import mean_squared_error

from pipeline.common.leaderboard import render_leaderboard
from pipeline.common.issues import render_run_issues
from pipeline.common.parity import render_parity_report
from pipeline import config

# -----------------------------------------------------------------------------
# Single-file eval runner (migration-friendly)
# Edit these top-level variables directly.
# -----------------------------------------------------------------------------
DATASET = "human_lung"
TRAIN_ID = "296C"
TEST_ID = "302C"
# Backward-compatible aliases for older notes/scripts.
REFERENCE_ID = TRAIN_ID
BULK_ID = TEST_ID
PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_ROOT = PROJECT_ROOT / "results" / DATASET
WORK_ROOT = PROJECT_ROOT / "work" / DATASET

MODEL = "all"  # scaden | scpdeconv | tape | music | cibersortx | all
SCP_DATASET_NAME = "human_lung_RNA"

CELL_TYPES = [
    "Luminal_Macrophages",
    "Type 2 alveolar",
    "Fibroblasts",
    "Dendritic cells",
]

PLOT_ENABLED = True


def ccc(pred: np.ndarray, gt: np.ndarray) -> float:
    numerator = 2 * np.corrcoef(gt, pred)[0][1] * np.std(gt) * np.std(pred)
    denominator = np.var(gt) + np.var(pred) + (np.mean(gt) - np.mean(pred)) ** 2
    return float(numerator / denominator)


def compute_metrics(pred: pd.DataFrame, gt: pd.DataFrame) -> pd.DataFrame:
    gt = gt[pred.columns]
    x = pd.melt(pred)["value"]
    y = pd.melt(gt)["value"]
    row = {
        "Pearson": pearsonr(x, y)[0],
        "CCC": ccc(x.to_numpy(), y.to_numpy()),
        "RMSE": sqrt(mean_squared_error(x, y)),
    }
    return pd.DataFrame([row])


def compute_typewise_ccc(pred: pd.DataFrame, gt: pd.DataFrame, cell_types) -> pd.DataFrame:
    gt = gt[pred.columns]
    records = []
    for ct in cell_types:
        records.append({"type": ct, "CCC": ccc(pred[ct].to_numpy(), gt[ct].to_numpy())})
    return pd.DataFrame(records)


def read_table(path: Path, sep=None, index_col=0) -> pd.DataFrame:
    if sep is None:
        return pd.read_csv(path, sep=None, engine="python", index_col=index_col)
    return pd.read_csv(path, sep=sep, index_col=index_col)


def write_table(df: pd.DataFrame, path: Path, sep=",", index=True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, sep=sep, index=index)


def align_to_cell_types(df: pd.DataFrame, cell_types) -> pd.DataFrame:
    missing = [c for c in cell_types if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in dataframe: {missing}")
    return df[[c for c in cell_types if c in df.columns]]


def normalize_model_name(name: str) -> str:
    aliases = {
        "scp": "scpdeconv",
        "scpdeconv": "scpdeconv",
        "scaden": "scaden",
        "tape": "tape",
        "music": "music",
        "musicr": "music",
        "cibersortx": "cibersortx",
        "cibersort": "cibersortx",
        "csx": "cibersortx",
    }
    return aliases.get(name.strip().lower(), name.strip().lower())


def get_eval_io(model_name: str):
    std_dir = PROJECT_ROOT / "data" / "standard" / DATASET

    if model_name == "scaden":
        return {
            "pred_path": RESULTS_ROOT / "scaden" / f"predictions_{BULK_ID}.csv",
            "gt_path": std_dir / f"{BULK_ID}_bulk_obs.txt",
            "pred_read": {"sep": None, "index_col": 0},
            "gt_read": {"sep": "\t", "index_col": 0},
        }

    if model_name == "scpdeconv":
        return {
            "pred_path": WORK_ROOT / "scpdeconv" / SCP_DATASET_NAME / "target_predicted_fractions.csv",
            "gt_path": WORK_ROOT / "scpdeconv" / SCP_DATASET_NAME / "target_gt_fractions.csv",
            "pred_read": {"sep": ",", "index_col": None},
            "gt_read": {"sep": ",", "index_col": None},
        }

    if model_name == "tape":
        work_pred = WORK_ROOT / "tape" / f"{BULK_ID}_pred_fractions.txt"
        if work_pred.exists():
            pred_path = work_pred
            pred_read = {"sep": "\t", "index_col": 0}
        else:
            pred_path = RESULTS_ROOT / "tape" / f"predictions_{BULK_ID}.csv"
            pred_read = {"sep": ",", "index_col": 0}
        return {
            "pred_path": pred_path,
            "gt_path": std_dir / f"{BULK_ID}_bulk_obs.txt",
            "pred_read": pred_read,
            "gt_read": {"sep": "\t", "index_col": 0},
        }

    if model_name == "music":
        return {
            "pred_path": WORK_ROOT / "music" / f"{BULK_ID}_music_pred.csv",
            "gt_path": std_dir / f"{BULK_ID}_bulk_obs.txt",
            "pred_read": {"sep": ",", "index_col": 0},
            "gt_read": {"sep": "\t", "index_col": 0},
        }

    if model_name == "cibersortx":
        return {
            "pred_path": WORK_ROOT / "cibersortx" / f"predictions_{BULK_ID}.csv",
            "gt_path": std_dir / f"{BULK_ID}_bulk_obs.txt",
            "pred_read": {"sep": None, "index_col": 0},
            "gt_read": {"sep": "\t", "index_col": 0},
        }

    raise ValueError(f"Unsupported model: {model_name}")


def result_dir(model_name: str) -> Path:
    return RESULTS_ROOT / model_name


def prediction_file(model_name: str) -> Path:
    return result_dir(model_name) / f"predictions_{BULK_ID}.csv"


def summary_metrics_file(model_name: str) -> Path:
    return result_dir(model_name) / "metrics_summary.csv"


def typewise_metrics_file(model_name: str) -> Path:
    return result_dir(model_name) / "typewise_ccc.csv"


def render_typewise_boxplot(results_root: Path, model_names):
    rows = []
    ordered_models = []
    for m in model_names:
        csv_path = results_root / m / "typewise_ccc.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path)
        if "CCC" not in df.columns:
            continue
        cur = pd.DataFrame(
            {
                "model": m,
                "type": df["type"].astype(str),
                "CCC": pd.to_numeric(df["CCC"], errors="coerce"),
            }
        ).dropna(subset=["CCC"])
        if cur.empty:
            continue
        rows.append(cur)
        ordered_models.append(m)

    if not rows:
        raise FileNotFoundError("No valid typewise_ccc.csv found for plotting")

    plot_df = pd.concat(rows, ignore_index=True)
    (results_root / "typewise_ccc_merged.csv").parent.mkdir(parents=True, exist_ok=True)
    plot_df[["model", "type", "CCC"]].to_csv(results_root / "typewise_ccc_merged.csv", index=False)

    data = [plot_df.loc[plot_df["model"] == m, "CCC"].values for m in ordered_models]

    pretty_name = {
        "scaden": "Scaden",
        "scpdeconv": "scpDeconv",
        "tape": "TAPE",
        "music": "MuSiC",
        "cibersortx": "CIBERSORTx",
    }
    display_labels = [pretty_name.get(m, m) for m in ordered_models]

    color_cycle = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2", "#B279A2"]
    box_colors = [color_cycle[i % len(color_cycle)] for i in range(len(ordered_models))]

    plt.figure(figsize=(8, 5))
    box = plt.boxplot(data, labels=display_labels, patch_artist=True)
    for patch, color in zip(box["boxes"], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.35)

    for i, m in enumerate(ordered_models, start=1):
        y = plot_df.loc[plot_df["model"] == m, "CCC"].values
        plt.scatter(np.full(len(y), i), y, alpha=0.85, s=24, color=box_colors[i - 1])

    plt.ylabel("CCC")
    plt.ylim(-0.05, 1.05)
    plt.grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.35)
    plt.tight_layout()
    out_path = results_root / "typewise_ccc_boxplot.png"
    plt.savefig(out_path, dpi=300)
    plt.close()


def evaluate_model(model_name: str):
    io_cfg = get_eval_io(model_name)
    pred_path = io_cfg["pred_path"]
    gt_path = io_cfg["gt_path"]

    if not pred_path.exists() or not gt_path.exists():
        return {
            "model": model_name,
            "status": "SKIPPED",
            "error": f"Missing eval file(s): prediction={pred_path.exists()}, ground_truth={gt_path.exists()}",
            "timestamp": datetime.now().isoformat(),
        }

    pred = read_table(pred_path, **io_cfg["pred_read"])
    gt = read_table(gt_path, **io_cfg["gt_read"])

    pred = align_to_cell_types(pred, CELL_TYPES)
    gt = align_to_cell_types(gt, CELL_TYPES)

    out_dir = result_dir(model_name)
    out_dir.mkdir(parents=True, exist_ok=True)

    write_table(pred, prediction_file(model_name), sep=",", index=True)

    summary = compute_metrics(pred, gt)
    write_table(summary, summary_metrics_file(model_name), sep=",", index=False)

    evaluation_obj = {
        "model": model_name,
        "dataset": DATASET,
        "reference_id": REFERENCE_ID,
        "bulk_id": BULK_ID,
        "pearson": float(summary.loc[0, "Pearson"]),
        "ccc": float(summary.loc[0, "CCC"]),
        "rmse": float(summary.loc[0, "RMSE"]),
        "timestamp": datetime.now().isoformat(),
    }
    with open(out_dir / "evaluation.json", "w", encoding="utf-8") as f:
        json.dump(evaluation_obj, f, ensure_ascii=False, indent=2)

    typewise = compute_typewise_ccc(pred, gt, CELL_TYPES)
    write_table(typewise, typewise_metrics_file(model_name), sep=",", index=False)

    return {
        "model": model_name,
        "status": "OK",
        "error": "",
        "timestamp": datetime.now().isoformat(),
    }


def main():
    m = normalize_model_name(MODEL)
    all_models = ["scaden", "scpdeconv", "tape", "music", "cibersortx"]
    model_names = all_models if m == "all" else [m]

    report = []
    for model_name in model_names:
        try:
            item = evaluate_model(model_name)
        except Exception as exc:
            item = {
                "model": model_name,
                "status": "FAILED",
                "error": str(exc),
                "timestamp": datetime.now().isoformat(),
            }
        report.append(item)
        print(f"[{item['model']}] {item['status']} {item['error']}")

    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_ROOT / "run_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    render_run_issues(RESULTS_ROOT)
    render_leaderboard(RESULTS_ROOT, DATASET, REFERENCE_ID, BULK_ID, all_models)
    baseline = config.PARITY_BASELINES.get(DATASET)
    if baseline is not None:
        render_parity_report(
            RESULTS_ROOT,
            DATASET,
            baseline,
            PROJECT_ROOT / "data" / "standard" / DATASET,
            all_models,
        )

    if PLOT_ENABLED:
        try:
            render_typewise_boxplot(RESULTS_ROOT, [x["model"] for x in report if x["status"] == "OK"])
            print("[plot] typewise_ccc_boxplot.png generated")
        except Exception as exc:
            print(f"[plot] skipped: {exc}")


if __name__ == "__main__":
    main()
