import sys

from pipeline import config


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


def _parse_stages(stage_text):
    return tuple(s.strip().lower() for s in stage_text.split(",") if s.strip())


def _parse_cell_types(cell_types_text):
    if isinstance(cell_types_text, str):
        if cell_types_text.strip().lower() == "auto":
            return "auto"
        return [s.strip() for s in cell_types_text.split(",") if s.strip()]
    return list(cell_types_text)


def _resolve_input_h5ad(project_root, dataset, reference_id, bulk_id):
    standard_dir = project_root / "data" / "standard" / dataset
    source_dir = project_root / "data" / dataset
    ref_name = f"{reference_id}_train.h5ad"
    bulk_name = f"{bulk_id}_test.h5ad"
    ref_path = standard_dir / ref_name if (standard_dir / ref_name).exists() else source_dir / ref_name
    bulk_path = standard_dir / bulk_name if (standard_dir / bulk_name).exists() else source_dir / bulk_name
    return ref_path, bulk_path


def _resolve_celltype_column(obs, cell_type_column):
    if cell_type_column and cell_type_column.strip().lower() != "auto":
        if cell_type_column not in obs.columns:
            raise KeyError(
                f"Configured cell type column '{cell_type_column}' not found in h5ad obs. "
                f"Available columns: {list(obs.columns)}"
            )
        return cell_type_column
    for col in ("CellType", "Celltype"):
        if col in obs.columns:
            return col
    raise KeyError(
        "Cell type column not found in h5ad obs. "
        "Expected one of: CellType, Celltype, or set CELL_TYPE_COLUMN=<column_name>."
    )


def _resolve_sample_column(obs, sample_column):
    if sample_column is None:
        return None
    value = str(sample_column).strip()
    if value.lower() in ("", "none", "null", "false"):
        return None
    if value.lower() != "auto":
        if value not in obs.columns:
            raise KeyError(
                f"Configured sample column '{value}' not found in h5ad obs. "
                f"Available columns: {list(obs.columns)}"
            )
        return value
    candidates = ("Sample", "sample", "sample_id", "SampleID", "study_sample", "donor", "donor_id", "patient", "subject", "batch")
    for col in candidates:
        if col in obs.columns and obs[col].astype(str).nunique() >= 2:
            return col
    for col in candidates:
        if col in obs.columns:
            return col
    return None


def _infer_cell_types(project_root, dataset, reference_id, bulk_id, test_cell_type_column):
    standard_dir = project_root / "data" / "standard" / dataset
    bulk_obs = standard_dir / f"{bulk_id}_bulk_obs.txt"
    if bulk_obs.exists():
        import pandas as pd

        return list(pd.read_csv(bulk_obs, sep="\t", index_col=0).columns.astype(str))

    _, bulk_h5ad = _resolve_input_h5ad(project_root, dataset, reference_id, bulk_id)
    if not bulk_h5ad.exists():
        raise FileNotFoundError(
            f"Cannot infer CELL_TYPES=auto because test h5ad is missing: {bulk_h5ad}"
        )

    import anndata as ad

    adata = ad.read_h5ad(bulk_h5ad)
    column = _resolve_celltype_column(adata.obs, test_cell_type_column)
    return list(dict.fromkeys(adata.obs[column].astype(str).tolist()))


def main():
    overrides = _parse_cli_overrides(sys.argv)

    model = overrides.get("MODEL", config.MODEL)
    dataset = overrides.get("DATASET", config.DATASET)
    dataset_config = config.get_dataset_config(dataset)
    reference_id = overrides.get("TRAIN_ID", overrides.get("REFERENCE_ID", config.REFERENCE_ID))
    bulk_id = overrides.get("TEST_ID", overrides.get("BULK_ID", config.BULK_ID))
    train_cell_type_column = overrides.get(
        "TRAIN_CELL_TYPE_COLUMN",
        overrides.get("CELL_TYPE_COLUMN", dataset_config["TRAIN_CELL_TYPE_COLUMN"]),
    )
    test_cell_type_column = overrides.get(
        "TEST_CELL_TYPE_COLUMN",
        overrides.get("CELL_TYPE_COLUMN", dataset_config["TEST_CELL_TYPE_COLUMN"]),
    )
    train_sample_column = overrides.get(
        "TRAIN_SAMPLE_COLUMN",
        overrides.get("SAMPLE_COLUMN", dataset_config["TRAIN_SAMPLE_COLUMN"]),
    )
    test_sample_column = overrides.get(
        "TEST_SAMPLE_COLUMN",
        overrides.get("SAMPLE_COLUMN", dataset_config["TEST_SAMPLE_COLUMN"]),
    )
    cell_types = _parse_cell_types(overrides.get("CELL_TYPES", dataset_config["CELL_TYPES"]))
    train_steps = int(overrides.get("TRAIN_STEPS", config.TRAIN_STEPS))
    seed = int(overrides.get("SEED", config.SEED))
    scp_dataset_name = overrides.get("SCP_DATASET_NAME", config.SCP_DATASET_NAME)
    standard_rebuild_mode = overrides.get("STANDARD_REBUILD_MODE", config.STANDARD_REBUILD_MODE)

    if cell_types == "auto":
        cell_types = _infer_cell_types(
            project_root=config.PROJECT_ROOT,
            dataset=dataset,
            reference_id=reference_id,
            bulk_id=bulk_id,
            test_cell_type_column=test_cell_type_column,
        )

    if "STAGES" in overrides:
        stages = _parse_stages(overrides["STAGES"])
    else:
        stages = config.STAGES

    from pipeline.orchestrator import PipelineOrchestrator

    orchestrator = PipelineOrchestrator(
        project_root=config.PROJECT_ROOT,
        results_root=config.RESULTS_ROOT,
        dataset=dataset,
        reference_id=reference_id,
        bulk_id=bulk_id,
        cell_types=cell_types,
        train_cell_type_column=train_cell_type_column,
        test_cell_type_column=test_cell_type_column,
        train_sample_column=train_sample_column,
        test_sample_column=test_sample_column,
        train_steps=train_steps,
        seed=seed,
        scp_dataset_name=scp_dataset_name,
        standard_rebuild_mode=standard_rebuild_mode,
    )
    orchestrator.run(model=model, stages=stages)


if __name__ == "__main__":
    main()
