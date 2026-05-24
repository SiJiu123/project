import anndata as ad
import pandas as pd
from pathlib import Path
import sys

STANDARD_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../../data/standard/human_lung")
WORK_DIR = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("../../work/music")
REFERENCE_ID = sys.argv[3] if len(sys.argv) > 3 else "296C"
SAMPLE_COLUMN = sys.argv[4] if len(sys.argv) > 4 else "Sample"
WORK_DIR.mkdir(parents=True, exist_ok=True)

adata = ad.read_h5ad(STANDARD_DIR / f"{REFERENCE_ID}_train.h5ad")


if adata.raw is not None:
    adata = adata.raw.to_adata()

obs = adata.obs.copy()
if SAMPLE_COLUMN.strip().lower() in ("", "none", "null", "false"):
    raise ValueError("MuSiC requires TRAIN_SAMPLE_COLUMN=<column_name>.")
if SAMPLE_COLUMN.strip().lower() == "auto":
    raise ValueError("SAMPLE_COLUMN=auto is no longer recommended. Use TRAIN_SAMPLE_COLUMN=<column_name> explicitly.")
if SAMPLE_COLUMN not in obs.columns:
    raise KeyError(f"TRAIN_SAMPLE_COLUMN='{SAMPLE_COLUMN}' not found. Available columns: {list(obs.columns)}")
obs["Sample"] = obs[SAMPLE_COLUMN].astype(str)
print(f"MuSiC train sample column: {SAMPLE_COLUMN}")
sample_count = obs["Sample"].nunique()
if sample_count < 2:
    raise ValueError(
        "MuSiC requires at least two sample/donor groups in TRAIN_SAMPLE_COLUMN. "
        f"TRAIN_SAMPLE_COLUMN='{SAMPLE_COLUMN}' has {sample_count} unique value(s). "
        "Use a train h5ad containing multiple donor/sample groups, or skip MODEL=music for this dataset."
    )

# 3. 导出 counts (保持：细胞在行，基因在列)
counts = pd.DataFrame(
    adata.X.toarray() if hasattr(adata.X, 'toarray') else adata.X,
    index=adata.obs_names,
    columns=adata.var_names
)

counts.to_csv(WORK_DIR / f"{REFERENCE_ID}_sc_X.txt", sep="\t", index=True, index_label='')
obs.to_csv(WORK_DIR / f"{REFERENCE_ID}_sc_obs.txt", sep="\t", index=True, index_label='')
