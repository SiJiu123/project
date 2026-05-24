from pathlib import Path
import shutil
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

# Top-level knobs (keep simple and directly editable)
N_PSEUDO_BULK = 1000
CELLS_PER_BULK = 50
RANDOM_SEED = 0
FRACTION_MODE = "uniform"  # "uniform" | "dirichlet"
USE_LIBRARY_SIZE_SCALING = False
NOISE_STD = 0.0


def _clear_axis_names(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.index.name = ""
    out.columns.name = ""
    return out


def _to_dense_matrix(x) -> np.ndarray:
    if isinstance(x, np.ndarray):
        return np.asarray(x, dtype=np.float32)
    return x.toarray().astype(np.float32)


def resolve_celltype_column(obs: pd.DataFrame, cell_type_column: str = "auto") -> str:
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


def _extract_celltype(obs: pd.DataFrame, cell_type_column: str = "auto") -> pd.Series:
    return obs[resolve_celltype_column(obs, cell_type_column)].astype(str)


def _load_h5ad_as_counts_and_labels(h5ad_path: Path, cell_type_column: str = "auto"):
    import anndata as ad

    adata = ad.read_h5ad(h5ad_path)
    matrix = _to_dense_matrix(adata.X)
    counts = pd.DataFrame(matrix, index=adata.obs_names.astype(str), columns=adata.var_names.astype(str))
    labels = pd.DataFrame({"CellType": _extract_celltype(adata.obs, cell_type_column).values}, index=counts.index)
    return counts, labels


def _random_fractions(rng: np.random.Generator, n_celltypes: int, mode: str) -> np.ndarray:
    if mode == "uniform":
        weights = rng.random(n_celltypes)
        total = weights.sum()
        if total == 0:
            return np.repeat(1.0 / n_celltypes, n_celltypes)
        return weights / total
    if mode == "dirichlet":
        return rng.dirichlet(np.ones(n_celltypes))
    raise ValueError(f"Unsupported fraction mode: {mode}")


def _counts_from_fractions(fracs: np.ndarray, total_cells: int) -> np.ndarray:
    expected = fracs * total_cells
    base = np.floor(expected).astype(int)
    deficit = int(total_cells - base.sum())
    if deficit > 0:
        remainders = expected - base
        take_order = np.argsort(-remainders)
        base[take_order[:deficit]] += 1
    return base


def simulate_bulk(
    counts_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    celltypes: Iterable[str],
    n_samples: int = N_PSEUDO_BULK,
    cells_per_sample: int = CELLS_PER_BULK,
    fraction_mode: str = FRACTION_MODE,
    random_seed: int = RANDOM_SEED,
    use_library_size_scaling: bool = USE_LIBRARY_SIZE_SCALING,
    noise_std: float = NOISE_STD,
):
    rng = np.random.default_rng(random_seed)

    celltype_series = labels_df["CellType"].astype(str)
    selected_celltypes = [ct for ct in celltypes if ct in set(celltype_series.values)]
    if not selected_celltypes:
        raise ValueError("None of the requested cell types exist in labels_df")

    pools: Dict[str, np.ndarray] = {}
    for ct in selected_celltypes:
        pool = np.where(celltype_series.values == ct)[0]
        if len(pool) == 0:
            raise ValueError(f"Cell type '{ct}' has no cells in input")
        pools[ct] = pool

    expr = counts_df.to_numpy(dtype=np.float32)
    n_genes = expr.shape[1]

    sample_ids: List[str] = [str(i) for i in range(n_samples)]
    simulated = np.zeros((n_samples, n_genes), dtype=np.float32)
    obs_rows = np.zeros((n_samples, len(selected_celltypes)), dtype=np.float32)

    for i in range(n_samples):
        fracs = _random_fractions(rng, len(selected_celltypes), fraction_mode)
        n_cells_each = _counts_from_fractions(fracs, cells_per_sample)

        sample_expr = np.zeros(n_genes, dtype=np.float32)
        for j, ct in enumerate(selected_celltypes):
            draw_n = int(n_cells_each[j])
            if draw_n <= 0:
                continue
            chosen = rng.choice(pools[ct], size=draw_n, replace=True)
            sample_expr += expr[chosen].sum(axis=0)

        if use_library_size_scaling:
            # Optional multiplicative depth scaling, disabled by default.
            scale = rng.uniform(0.8, 1.2)
            sample_expr *= np.float32(scale)

        if noise_std > 0:
            sample_expr += rng.normal(0.0, noise_std, size=sample_expr.shape).astype(np.float32)
            sample_expr = np.clip(sample_expr, a_min=0.0, a_max=None)

        simulated[i, :] = sample_expr
        # Keep continuous composition as generated; do not quantize by integer cell counts.
        obs_rows[i, :] = fracs.astype(np.float32)

    bulk_df = pd.DataFrame(simulated, index=sample_ids, columns=counts_df.columns)
    obs_df = pd.DataFrame(obs_rows, index=sample_ids, columns=selected_celltypes)
    return bulk_df, obs_df


def rebuild_standard_dataset(
    train_h5ad_path: Path,
    test_h5ad_path: Path,
    output_dir: Path,
    reference_id: str,
    bulk_id: str,
    celltypes_for_bulk: Optional[Iterable[str]] = None,
    train_cell_type_column: str = "CellType",
    test_cell_type_column: str = "CellType",
    pseudobulk_methods: Iterable[str] = ("uniform", "dirichlet"),
    active_method: str = "uniform",
    random_seed: int = RANDOM_SEED,
):
    output_dir.mkdir(parents=True, exist_ok=True)

    train_counts, train_labels = _load_h5ad_as_counts_and_labels(train_h5ad_path, train_cell_type_column)
    test_counts, test_labels = _load_h5ad_as_counts_and_labels(test_h5ad_path, test_cell_type_column)

    if celltypes_for_bulk is None:
        # Keep stable order based on appearance in test labels.
        celltypes_for_bulk = list(dict.fromkeys(test_labels["CellType"].tolist()))

    method_outputs = {}
    for idx, method in enumerate(pseudobulk_methods):
        bulk_df, bulk_obs = simulate_bulk(
            counts_df=test_counts,
            labels_df=test_labels,
            celltypes=celltypes_for_bulk,
            n_samples=N_PSEUDO_BULK,
            cells_per_sample=CELLS_PER_BULK,
            fraction_mode=method,
            random_seed=int(random_seed) + idx,
            use_library_size_scaling=USE_LIBRARY_SIZE_SCALING,
            noise_std=NOISE_STD,
        )
        bulk_x_variant = output_dir / f"{bulk_id}_bulk_X.{method}.txt"
        bulk_obs_variant = output_dir / f"{bulk_id}_bulk_obs.{method}.txt"
        _clear_axis_names(bulk_df.T).to_csv(bulk_x_variant, sep="\t", index=True)
        _clear_axis_names(bulk_obs).to_csv(bulk_obs_variant, sep="\t", index=True)
        method_outputs[method] = (bulk_x_variant, bulk_obs_variant)

    if active_method not in method_outputs:
        raise ValueError(
            f"Active pseudo-bulk method '{active_method}' is not in generated methods: {list(method_outputs)}"
        )

    active_bulk_x, active_bulk_obs = method_outputs[active_method]

    std_ref_h5ad = output_dir / f"{reference_id}_train.h5ad"
    std_bulk_h5ad = output_dir / f"{bulk_id}_test.h5ad"
    if train_h5ad_path.resolve() != std_ref_h5ad.resolve():
        shutil.copy2(train_h5ad_path, std_ref_h5ad)
    if test_h5ad_path.resolve() != std_bulk_h5ad.resolve():
        shutil.copy2(test_h5ad_path, std_bulk_h5ad)

    _clear_axis_names(train_counts).to_csv(output_dir / f"{reference_id}_counts.txt", sep="\t", index=True)
    train_labels[["CellType"]].to_csv(output_dir / f"{reference_id}_celltypes.txt", sep="\t", index=False)

    _clear_axis_names(test_counts).to_csv(output_dir / f"{bulk_id}_counts.txt", sep="\t", index=True)
    test_labels[["CellType"]].to_csv(output_dir / f"{bulk_id}_celltypes.txt", sep="\t", index=False)

    shutil.copy2(active_bulk_x, output_dir / f"{bulk_id}_bulk_X.txt")
    shutil.copy2(active_bulk_obs, output_dir / f"{bulk_id}_bulk_obs.txt")

    outputs = {
        f"{reference_id}_train.h5ad": std_ref_h5ad,
        f"{bulk_id}_test.h5ad": std_bulk_h5ad,
        f"{reference_id}_counts.txt": output_dir / f"{reference_id}_counts.txt",
        f"{reference_id}_celltypes.txt": output_dir / f"{reference_id}_celltypes.txt",
        f"{bulk_id}_counts.txt": output_dir / f"{bulk_id}_counts.txt",
        f"{bulk_id}_celltypes.txt": output_dir / f"{bulk_id}_celltypes.txt",
        f"{bulk_id}_bulk_X.txt": output_dir / f"{bulk_id}_bulk_X.txt",
        f"{bulk_id}_bulk_obs.txt": output_dir / f"{bulk_id}_bulk_obs.txt",
    }
    for method in method_outputs:
        outputs[f"{bulk_id}_bulk_X.{method}.txt"] = output_dir / f"{bulk_id}_bulk_X.{method}.txt"
        outputs[f"{bulk_id}_bulk_obs.{method}.txt"] = output_dir / f"{bulk_id}_bulk_obs.{method}.txt"
    return outputs


def rebuild_standard_human_lung(
    train_h5ad_path: Path,
    test_h5ad_path: Path,
    output_dir: Path,
    celltypes_for_bulk: Optional[Iterable[str]] = None,
    pseudobulk_methods: Iterable[str] = ("uniform", "dirichlet"),
    active_method: str = "uniform",
    random_seed: int = RANDOM_SEED,
):
    return rebuild_standard_dataset(
        train_h5ad_path=train_h5ad_path,
        test_h5ad_path=test_h5ad_path,
        output_dir=output_dir,
        reference_id="296C",
        bulk_id="302C",
        celltypes_for_bulk=celltypes_for_bulk,
        train_cell_type_column="CellType",
        test_cell_type_column="CellType",
        pseudobulk_methods=pseudobulk_methods,
        active_method=active_method,
        random_seed=random_seed,
    )
