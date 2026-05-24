# Unified Deconvolution Pipeline

This repository provides a unified entrypoint to run and evaluate 5 models on pre-split train/test h5ad datasets:
- `scaden`
- `scpdeconv`
- `tape`
- `music`
- `cibersortx` (external prediction drop-in)

## 1. Current Layout

Core files/folders:
- `config.py` : centralized runtime config
- `run_pipeline.py` : unified entrypoint
- `pipeline/` : orchestrator + adapters + common utilities
- `data/standard/<DATASET>/` : canonical input data
- `utils/data_factory.py` : source-driven pseudo-bulk generator (uniform + dirichlet)
- `work/<DATASET>/` : model-specific temporary artifacts
- `results/<DATASET>/` : unified evaluation outputs
- `save_models/<DATASET>/` : saved model weights
- `scripts/` : utility scripts
- `OPERATION_LOG.md` : operation history log

## 2. Canonical Inputs

Required source files for a dataset:
- `data/standard/<DATASET>/<TRAIN_ID>_train.h5ad`, or `data/<DATASET>/<TRAIN_ID>_train.h5ad`
- `data/standard/<DATASET>/<TEST_ID>_test.h5ad`, or `data/<DATASET>/<TEST_ID>_test.h5ad`

Generated standard files in `data/standard/<DATASET>/`:
- `<TRAIN_ID>_counts.txt`
- `<TRAIN_ID>_celltypes.txt`
- `<TEST_ID>_counts.txt`
- `<TEST_ID>_celltypes.txt`
- `<TEST_ID>_bulk_X.txt`
- `<TEST_ID>_bulk_obs.txt`

Also generated (method variants):
- `<TEST_ID>_bulk_X.uniform.txt`
- `<TEST_ID>_bulk_obs.uniform.txt`
- `<TEST_ID>_bulk_X.dirichlet.txt`
- `<TEST_ID>_bulk_obs.dirichlet.txt`

Also generated in `prepare` stage:
- `<TRAIN_ID>_counts_transposed.txt`
- `<TRAIN_ID>_class_labels.txt` (no header)

`<TRAIN_ID>_class_labels.txt` format:
- first column: target cell type name (from `CELL_TYPES`)
- each remaining column maps to one cell from the transposed counts columns
- value rule: same cell type -> `1`, otherwise -> `2`

`<TEST_ID>_bulk_X.txt` and `<TEST_ID>_bulk_obs.txt` are always copied from the active method in `config.py`.

## 3. Environment

`config.py` defines conda env bindings and paths:
- `SCADEN_CONDA_ENV`
- `SCP_CONDA_ENV`
- `TAPE_CONDA_ENV`
- `MUSIC_CONDA_ENV`
- `CONDA_BAT`

It also controls pseudo-bulk method selection:
- `PSEUDOBULK_METHODS = ("uniform", "dirichlet")`
- `PSEUDOBULK_ACTIVE_METHOD = "uniform"` (or `"dirichlet"`)

Dataset selection can be edited in `config.py` or overridden on the command line:
- `DATASET`
- `TRAIN_ID` (preferred; `REFERENCE_ID` is still supported)
- `TEST_ID` (preferred; `BULK_ID` is still supported)
- `TRAIN_CELL_TYPE_COLUMN` and `TEST_CELL_TYPE_COLUMN` (h5ad `obs` column names)
- `TRAIN_SAMPLE_COLUMN` and `TEST_SAMPLE_COLUMN` (h5ad `obs` column names; MuSiC uses the train sample column)
- `CELL_TYPES` (comma-separated list, or `auto`)

Dataset-specific column defaults should be added to `DATASET_CONFIGS` in `config.py`. Command-line column arguments are still supported as one-off overrides.

And controls whether to rebuild the standard 10 files at `prepare`:
- `STANDARD_REBUILD_MODE = "always"` : always rebuild
- `STANDARD_REBUILD_MODE = "if_missing"` : rebuild only when core files are missing
- `STANDARD_REBUILD_MODE = "never"` : never rebuild, use existing files

Make sure these envs exist before running.

## 3.1 Rebuild Standard Files

From project root:

```powershell
C:\Users\Lenovo\miniconda3\envs\dzwdecode\python.exe scripts/migrate_naming.py
C:\Users\Lenovo\miniconda3\envs\dzwdecode\python.exe scripts/migrate_naming.py DATASET=my_dataset TRAIN_ID=A TEST_ID=B CELL_TYPES=auto
```

Behavior:
- reads `<TRAIN_ID>_train.h5ad` and `<TEST_ID>_test.h5ad`
- regenerates counts/celltypes txt files
- generates both uniform and dirichlet pseudo-bulk variants
- activates one method into canonical `<TEST_ID>_bulk_X.txt` and `<TEST_ID>_bulk_obs.txt`

## 4. How To Run

From project root:

```powershell
# all stages for one model using config.py defaults
& "C:\Users\Lenovo\miniconda3\envs\dzwdecode\python.exe" run_pipeline.py MODEL=scaden STAGES=prepare,run,eval

# run a different pre-split dataset
& "C:\Users\Lenovo\miniconda3\envs\dzwdecode\python.exe" run_pipeline.py MODEL=all STAGES=prepare,run,eval DATASET=my_dataset TRAIN_ID=A TEST_ID=B CELL_TYPES=auto

# all models, eval only
& "C:\Users\Lenovo\miniconda3\envs\dzwdecode\python.exe" run_pipeline.py MODEL=all STAGES=eval

# full chain for all models
& "C:\Users\Lenovo\miniconda3\envs\dzwdecode\python.exe" run_pipeline.py MODEL=all STAGES=prepare,run,eval
```

Supported `MODEL`:
- `scaden`, `scpdeconv`, `tape`, `music`, `cibersortx`, `all`
- multiple models are also supported with commas, for example `MODEL=scaden,tape,scpdeconv`

Supported `STAGES`:
- `prepare`, `run`, `eval` (comma-separated)

MuSiC note:
- MuSiC requires a sample/donor grouping column in the train h5ad `obs`.
- Set it with `TRAIN_SAMPLE_COLUMN=<column_name>`, for example `TRAIN_SAMPLE_COLUMN=donor` or `TRAIN_SAMPLE_COLUMN=study_sample`.
- If the selected sample column has fewer than two unique groups, MuSiC is skipped/fails clearly because the method needs cross-sample variation.

For new datasets, split/filter the original h5ad outside this pipeline first. The pipeline starts from `<TRAIN_ID>_train.h5ad` and `<TEST_ID>_test.h5ad`; it does not run donor-specific split scripts.

## 5. Outputs

Per-model outputs in `results/<DATASET>/<model>/`:
- `predictions_<TEST_ID>.csv`
- `metrics_summary.csv`
- `typewise_ccc.csv`
- `evaluation.json`

Global outputs:
- `results/<DATASET>/run_report.json`
- `results/<DATASET>/leaderboard.md`
- `results/<DATASET>/typewise_ccc_boxplot.png`

For `cibersortx`:
- place external prediction file at `work/<DATASET>/cibersortx/predictions_<TEST_ID>.csv`
- required columns should include all configured `CELL_TYPES`
- `eval` will auto-skip this model if prediction file is missing

## 6. Notes

- Upstream model source directories are treated as read-only and should not be modified:
  - `models/scaden/scaden-master`
  - `models/tape/tape_main`
  - `models/music/music_master`
  - `models/scp_deconv/scpdeconv_main`
- Temporary intermediate files are kept under `work/<DATASET>/`.
- If a run is interrupted, check `results/<DATASET>/run_report.json` and regenerate missing stage outputs.
