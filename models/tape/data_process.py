from pathlib import Path
import sys

import pandas as pd


def _get_celltype_series(df_labels: pd.DataFrame) -> pd.Series:
    for column in ("Celltype", "CellType"):
        if column in df_labels.columns:
            return df_labels[column]
    raise KeyError(f"No celltype column found. Available columns: {list(df_labels.columns)}")


def _build_sc_counts(standard_dir: Path, out_path: Path, dataset_id: str) -> None:
    counts_path = standard_dir / f"{dataset_id}_counts.txt"
    labels_path = standard_dir / f"{dataset_id}_celltypes.txt"

    df_matrix = pd.read_csv(counts_path, sep="\t", index_col=0)
    df_labels = pd.read_csv(labels_path, sep="\t")

    celltypes = _get_celltype_series(df_labels)
    if len(df_matrix) != len(celltypes):
        raise ValueError(
            f"Row mismatch for {dataset_id}: counts_rows={len(df_matrix)}, celltypes_rows={len(celltypes)}"
        )

    df_matrix.index = celltypes
    df_matrix.to_csv(out_path, sep="\t", index_label="")


def main() -> None:
    standard_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../../data/standard/human_lung")
    work_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("../../work/tape")
    reference_id = sys.argv[3] if len(sys.argv) > 3 else "296C"
    work_dir.mkdir(parents=True, exist_ok=True)

    _build_sc_counts(standard_dir, work_dir / f"{reference_id}_sc_counts.txt", reference_id)
    print("TAPE data preparation finished")


if __name__ == "__main__":
    main()
