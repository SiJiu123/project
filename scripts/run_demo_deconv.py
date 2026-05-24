import argparse
import json
import random
import sys
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import torch
from scipy import sparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.demo_deconv.neural_models import PrototypeDeconv, SupervisedDeconv


def read_h5ad(path: Path):
    if not path.exists():
        raise FileNotFoundError(path)
    return ad.read_h5ad(path)


def matrix_to_dense(x):
    if sparse.issparse(x):
        return x.toarray()
    return np.asarray(x)


def build_pseudobulk(train_adata, cell_types, cell_type_column, n_samples, sample_size, seed):
    rng = np.random.default_rng(seed)
    x = pd.DataFrame(
        matrix_to_dense(train_adata.X).astype(np.float32),
        columns=train_adata.var_names.astype(str),
    ).fillna(0.0).clip(lower=0.0)
    labels = train_adata.obs[cell_type_column].astype(str).reset_index(drop=True)

    samples = []
    fractions = []
    attempts = 0
    max_attempts = n_samples * 100
    while len(samples) < n_samples and attempts < max_attempts:
        attempts += 1
        fracs = rng.random(len(cell_types))
        fracs = fracs / fracs.sum()
        counts = np.rint(fracs * sample_size).astype(int)
        if counts.sum() == 0:
            continue
        fracs = counts / counts.sum()

        parts = []
        ok = True
        for idx, cell_type in enumerate(cell_types):
            type_indices = np.flatnonzero(labels.to_numpy() == cell_type)
            if len(type_indices) == 0 or counts[idx] > len(type_indices):
                ok = False
                break
            chosen = rng.choice(type_indices, size=counts[idx], replace=True)
            parts.append(x.iloc[chosen, :])
        if not ok:
            continue

        sample = pd.concat(parts, axis=0).sum(axis=0)
        max_value = sample.max()
        if max_value > 0:
            sample = sample / max_value
        samples.append(sample.to_numpy(dtype=np.float32))
        fractions.append(fracs.astype(np.float32))

    if len(samples) < n_samples:
        raise RuntimeError(f"Only generated {len(samples)}/{n_samples} pseudo-bulk samples.")
    return np.asarray(samples, dtype=np.float32), np.asarray(fractions, dtype=np.float32)


def make_adata(x, y, gene_names, cell_types):
    adata = ad.AnnData(x)
    adata.var_names = pd.Index(np.asarray(gene_names, dtype=str))
    for idx, cell_type in enumerate(cell_types):
        adata.obs[cell_type] = y[:, idx]
    adata.uns["cell_types"] = list(cell_types)
    return adata


def load_target_bulk(path: Path, gene_names, cell_types):
    bulk = pd.read_csv(path, sep="\t", index_col=0)
    gene_names = pd.Index(np.asarray(gene_names, dtype=str))
    bulk.index = bulk.index.astype(str)
    if not bulk.index.equals(gene_names):
        missing = gene_names.difference(bulk.index)
        extra = bulk.index.difference(gene_names)
        if len(missing) or len(extra):
            raise ValueError(f"Bulk genes do not match training genes: missing={len(missing)}, extra={len(extra)}")
        bulk = bulk.loc[gene_names]

    x = bulk.T.to_numpy(dtype=np.float32)
    row_max = np.max(x, axis=1, keepdims=True)
    row_max[row_max == 0] = 1.0
    x = x / row_max
    y = np.zeros((x.shape[0], len(cell_types)), dtype=np.float32)
    adata = make_adata(x, y, bulk.index, cell_types)
    return adata, bulk.columns.astype(str)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["supdeconv", "protodeconv"], required=True)
    parser.add_argument("--train-h5ad", type=Path, required=True)
    parser.add_argument("--bulk-x", type=Path, required=True)
    parser.add_argument("--cell-types", required=True)
    parser.add_argument("--cell-type-column", default="CellType")
    parser.add_argument("--out-pred", type=Path, required=True)
    parser.add_argument("--out-meta", type=Path, required=True)
    parser.add_argument("--n-samples", type=int, default=6000)
    parser.add_argument("--valid-size", type=int, default=1000)
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=200)
    parser.add_argument("--seed", type=int, default=2021)
    parser.add_argument("--prototype-size", type=int, default=50)
    parser.add_argument("--align-weight", type=float, default=0.01)
    return parser.parse_args()


def main():
    args = parse_args()
    cell_types = [item.strip() for item in args.cell_types.split(",") if item.strip()]
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    train_adata = read_h5ad(args.train_h5ad)
    if args.cell_type_column not in train_adata.obs.columns:
        raise ValueError(f"{args.train_h5ad} missing obs column: {args.cell_type_column}")
    train_adata = train_adata[train_adata.obs[args.cell_type_column].astype(str).isin(cell_types)].copy()

    x, y = build_pseudobulk(
        train_adata,
        cell_types,
        args.cell_type_column,
        args.n_samples,
        args.sample_size,
        args.seed,
    )
    valid_size = min(args.valid_size, max(1, len(x) // 5))
    valid_data = make_adata(x[:valid_size], y[:valid_size], train_adata.var_names, cell_types)
    source_data = make_adata(x[valid_size:], y[valid_size:], train_adata.var_names, cell_types)
    target_data, target_index = load_target_bulk(args.bulk_x, source_data.var_names, cell_types)

    if args.model == "supdeconv":
        model = SupervisedDeconv(args.epochs, args.batch_size, args.learning_rate, seed=args.seed)
    else:
        model = PrototypeDeconv(
            args.epochs,
            args.batch_size,
            args.learning_rate,
            seed=args.seed,
            prototype_size=args.prototype_size,
            align_weight=args.align_weight,
        )

    losses, _ = model.train(source_data, target_data, valid_data, patience=args.patience)
    pred, _ = model.prediction(model.test_target_loader)
    pred.index = target_index
    args.out_pred.parent.mkdir(parents=True, exist_ok=True)
    pred.to_csv(args.out_pred)

    metadata = {
        "model": args.model,
        "seed": args.seed,
        "device": str(model.device),
        "n_samples": args.n_samples,
        "valid_size": valid_size,
        "sample_size": args.sample_size,
        "epochs_requested": args.epochs,
        "epochs_run": len(losses),
        "final_train_loss": losses[-1] if losses else None,
        "prototype_size": args.prototype_size if args.model == "protodeconv" else None,
        "align_weight": args.align_weight if args.model == "protodeconv" else None,
    }
    args.out_meta.parent.mkdir(parents=True, exist_ok=True)
    args.out_meta.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
