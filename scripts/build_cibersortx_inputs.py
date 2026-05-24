from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import (  # noqa: E402
    BULK_ID,
    DATASET,
    REFERENCE_ID,
    get_dataset_config,
)


def _parse_cli_overrides(argv):
    overrides = {}
    for arg in argv[1:]:
        token = arg.strip()
        if token.startswith("--") and "=" in token:
            key, value = token[2:].split("=", 1)
            overrides[key.strip().upper()] = value.strip()
        elif "=" in token:
            key, value = token.split("=", 1)
            overrides[key.strip().upper()] = value.strip()
    return overrides


def _parse_cell_types(value):
    if isinstance(value, str):
        if value.strip().lower() == "auto":
            return "auto"
        return [s.strip() for s in value.split(",") if s.strip()]
    return list(value)


def _extract_celltype_column(df: pd.DataFrame) -> pd.Series:
    for col in ("CellType", "Celltype"):
        if col in df.columns:
            return df[col].astype(str)
    if len(df.columns) == 1:
        return df.iloc[:, 0].astype(str)
    raise ValueError(f"Unsupported celltype schema: {list(df.columns)}")


def main() -> None:
    overrides = _parse_cli_overrides(sys.argv)
    dataset = overrides.get("DATASET", DATASET)
    dataset_config = get_dataset_config(dataset)
    reference_id = overrides.get("TRAIN_ID", overrides.get("REFERENCE_ID", REFERENCE_ID))
    bulk_id = overrides.get("TEST_ID", overrides.get("BULK_ID", BULK_ID))
    cell_types = _parse_cell_types(overrides.get("CELL_TYPES", dataset_config["CELL_TYPES"]))
    standard_dir = PROJECT_ROOT / "data" / "standard" / dataset
    ref_counts = standard_dir / f"{reference_id}_counts.txt"
    ref_celltypes = standard_dir / f"{reference_id}_celltypes.txt"
    bulk_obs = standard_dir / f"{bulk_id}_bulk_obs.txt"
    ref_counts_transposed = standard_dir / f"{reference_id}_counts_transposed.txt"
    ref_class_labels = standard_dir / f"{reference_id}_class_labels.txt"

    if not ref_counts.exists():
        raise FileNotFoundError(f"Missing counts file: {ref_counts}")
    if not ref_celltypes.exists():
        raise FileNotFoundError(f"Missing celltypes file: {ref_celltypes}")

    if cell_types == "auto":
        if not bulk_obs.exists():
            raise FileNotFoundError(f"Cannot resolve CELL_TYPES=auto because bulk obs is missing: {bulk_obs}")
        cell_types = list(pd.read_csv(bulk_obs, sep="\t", index_col=0).columns.astype(str))

    counts_df = pd.read_csv(ref_counts, sep="\t", index_col=0)
    labels_df = pd.read_csv(ref_celltypes, sep="\t")
    celltype_series = _extract_celltype_column(labels_df)

    if len(counts_df) != len(celltype_series):
        raise ValueError(
            f"Row mismatch between counts and celltypes: counts={len(counts_df)}, celltypes={len(celltype_series)}"
        )

    # 1) Save transpose of reference counts matrix.
    counts_t = counts_df.T
    counts_t.index.name = ""
    counts_t.columns.name = ""
    counts_t.to_csv(ref_counts_transposed, sep="\t", index=True)

    # 2) Build class-label matrix without header.
    # First column is target cell type, remaining columns map to cells in transposed-count columns.
    cell_labels = celltype_series.tolist()
    lines = []
    for ct in cell_types:
        row_values = ["1" if current == ct else "2" for current in cell_labels]
        lines.append("\t".join([ct] + row_values))

    with open(ref_class_labels, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

    print(f"Generated CIBERSORTx inputs for {dataset} ({reference_id}/{bulk_id})")
    print(f"Generated transposed counts: {ref_counts_transposed}")
    print(f"Generated class labels: {ref_class_labels}")


if __name__ == "__main__":
    main()
