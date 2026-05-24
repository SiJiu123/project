from math import sqrt
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.metrics import mean_squared_error


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


def compute_typewise_ccc(pred: pd.DataFrame, gt: pd.DataFrame, cell_types: Iterable[str]) -> pd.DataFrame:
    gt = gt[pred.columns]
    records = []
    for cell_type in cell_types:
        type_pred = pred[cell_type].to_numpy()
        type_gt = gt[cell_type].to_numpy()
        records.append({"type": cell_type, "CCC": ccc(type_pred, type_gt)})
    return pd.DataFrame(records)
