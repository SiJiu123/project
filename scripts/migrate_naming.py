from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import (  # noqa: E402
    BULK_ID,
    CELL_TYPES,
    DATASET,
    PSEUDOBULK_ACTIVE_METHOD,
    PSEUDOBULK_METHODS,
    REFERENCE_ID,
    SEED,
    get_dataset_config,
)
from utils.data_factory import rebuild_standard_dataset, resolve_celltype_column  # noqa: E402


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


def _resolve_h5ad(filename: str, standard_dir: Path, source_dir: Path) -> Path:
    for candidate in (standard_dir / filename, source_dir / filename):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Missing source h5ad: {filename}")


def _infer_cell_types_from_h5ad(h5ad_path: Path, cell_type_column: str):
    import anndata as ad

    adata = ad.read_h5ad(h5ad_path)
    column = resolve_celltype_column(adata.obs, cell_type_column)
    return list(dict.fromkeys(adata.obs[column].astype(str).tolist()))


def main() -> None:
    overrides = _parse_cli_overrides(sys.argv)
    dataset = overrides.get("DATASET", DATASET)
    dataset_config = get_dataset_config(dataset)
    reference_id = overrides.get("TRAIN_ID", overrides.get("REFERENCE_ID", REFERENCE_ID))
    bulk_id = overrides.get("TEST_ID", overrides.get("BULK_ID", BULK_ID))
    train_cell_type_column = overrides.get(
        "TRAIN_CELL_TYPE_COLUMN",
        overrides.get("CELL_TYPE_COLUMN", dataset_config["TRAIN_CELL_TYPE_COLUMN"]),
    )
    test_cell_type_column = overrides.get(
        "TEST_CELL_TYPE_COLUMN",
        overrides.get("CELL_TYPE_COLUMN", dataset_config["TEST_CELL_TYPE_COLUMN"]),
    )
    cell_types = _parse_cell_types(overrides.get("CELL_TYPES", dataset_config["CELL_TYPES"]))
    seed = int(overrides.get("SEED", SEED))
    standard_dir = PROJECT_ROOT / "data" / "standard" / dataset
    source_dir = PROJECT_ROOT / "data" / dataset

    train_h5ad = _resolve_h5ad(f"{reference_id}_train.h5ad", standard_dir, source_dir)
    test_h5ad = _resolve_h5ad(f"{bulk_id}_test.h5ad", standard_dir, source_dir)
    if cell_types == "auto":
        cell_types = _infer_cell_types_from_h5ad(test_h5ad, test_cell_type_column)

    outputs = rebuild_standard_dataset(
        train_h5ad_path=train_h5ad,
        test_h5ad_path=test_h5ad,
        output_dir=standard_dir,
        reference_id=reference_id,
        bulk_id=bulk_id,
        celltypes_for_bulk=cell_types,
        train_cell_type_column=train_cell_type_column,
        test_cell_type_column=test_cell_type_column,
        pseudobulk_methods=PSEUDOBULK_METHODS,
        active_method=PSEUDOBULK_ACTIVE_METHOD,
        random_seed=seed,
    )

    print("Core standard files rebuilt from source h5ad:")
    print(f"Dataset: {dataset}")
    print(f"Train/Test: {reference_id}/{bulk_id}")
    print(f"Active pseudo-bulk method: {PSEUDOBULK_ACTIVE_METHOD}")
    print(f"Seed: {seed}")
    for name, path in outputs.items():
        print(f"  - {name}: {path}")


if __name__ == "__main__":
    main()
