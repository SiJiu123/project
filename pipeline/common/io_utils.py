import hashlib
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_table(path: Path, sep: Optional[str] = None, index_col: Optional[int] = 0) -> pd.DataFrame:
    if sep is None:
        return pd.read_csv(path, sep=None, engine="python", index_col=index_col)
    return pd.read_csv(path, sep=sep, index_col=index_col)


def write_table(df: pd.DataFrame, path: Path, sep: str = ",", index: bool = True) -> None:
    ensure_parent_dir(path)
    df.to_csv(path, sep=sep, index=index)


def align_to_cell_types(df: pd.DataFrame, cell_types: Iterable[str]) -> pd.DataFrame:
    ordered = [c for c in cell_types if c in df.columns]
    missing = [c for c in cell_types if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in dataframe: {missing}")
    return df[ordered]


def normalize_celltype_column(df: pd.DataFrame) -> pd.DataFrame:
    renamed = df.copy()
    if "Celltype" in renamed.columns and "CellType" not in renamed.columns:
        renamed = renamed.rename(columns={"Celltype": "CellType"})
    return renamed


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def describe_file(path: Path) -> dict:
    exists = path.exists()
    return {
        "path": str(path),
        "exists": exists,
        "size": path.stat().st_size if exists else None,
        "sha256": file_sha256(path) if exists else None,
    }
