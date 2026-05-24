from pathlib import Path

# Top-level config style (default): edit these values directly.
PROJECT_ROOT = Path(__file__).resolve().parent

MODEL = "scaden"  # scaden | scpdeconv | tape | music | cibersortx | supdeconv | protodeconv | all
DATASET = "human_lung"
TRAIN_ID = "296C"
TEST_ID = "302C"
# Backward-compatible aliases. Prefer TRAIN_ID/TEST_ID in new commands.
REFERENCE_ID = TRAIN_ID
BULK_ID = TEST_ID
TRAIN_CELL_TYPE_COLUMN = "CellType"
TEST_CELL_TYPE_COLUMN = "CellType"
TRAIN_SAMPLE_COLUMN = "Sample"
TEST_SAMPLE_COLUMN = "Sample"
# Backward-compatible aliases. Prefer split train/test parameters in new commands.
CELL_TYPE_COLUMN = TRAIN_CELL_TYPE_COLUMN
SAMPLE_COLUMN = TRAIN_SAMPLE_COLUMN

# Dataset-specific metadata columns. These are defaults for each dataset and can
# still be overridden from the command line.
DATASET_CONFIGS = {
    "human_lung": {
        "TRAIN_CELL_TYPE_COLUMN": "CellType",
        "TEST_CELL_TYPE_COLUMN": "CellType",
        "TRAIN_SAMPLE_COLUMN": "Sample",
        "TEST_SAMPLE_COLUMN": "Sample",
        "CELL_TYPES": [
            "Luminal_Macrophages",
            "Type 2 alveolar",
            "Fibroblasts",
            "Dendritic cells",
        ],
    },
    "mouse_islet": {
        "TRAIN_CELL_TYPE_COLUMN": "cell_type",
        "TEST_CELL_TYPE_COLUMN": "cell_type",
        "TRAIN_SAMPLE_COLUMN": "study_sample",
        "TEST_SAMPLE_COLUMN": "study_sample",
        "CELL_TYPES": [
            "beta",
            "alpha",
            "delta",
            "endothelial",
            "immune",
            "gamma",
        ],
    },
}


def get_dataset_config(dataset: str) -> dict:
    defaults = {
        "TRAIN_CELL_TYPE_COLUMN": TRAIN_CELL_TYPE_COLUMN,
        "TEST_CELL_TYPE_COLUMN": TEST_CELL_TYPE_COLUMN,
        "TRAIN_SAMPLE_COLUMN": TRAIN_SAMPLE_COLUMN,
        "TEST_SAMPLE_COLUMN": TEST_SAMPLE_COLUMN,
        "CELL_TYPES": CELL_TYPES,
    }
    defaults.update(DATASET_CONFIGS.get(dataset, {}))
    return defaults

# Default full chain
STAGES = ("prepare", "run", "eval")

TRAIN_STEPS = 5000
SEED = 0
SCP_DATASET_NAME = "human_lung_RNA"

# Pseudo-bulk generation options for standard 10-file rebuild.
# Available methods: "uniform", "dirichlet"
PSEUDOBULK_METHODS = ("uniform", "dirichlet")
PSEUDOBULK_ACTIVE_METHOD = "uniform"

# Control whether standard 10-file data should be rebuilt in prepare stage.
# - "always": rebuild every prepare run
# - "if_missing": rebuild only when any core standard file is missing
# - "never": never rebuild; use existing files as-is
STANDARD_REBUILD_MODE = "never"    # always/if_missing/never

# Scaden simulation knobs (dataset-sensitive; keep configurable).
SCADEN_SIM_N_REF = 6000
SCADEN_SIM_N_BULK = 1000
SCADEN_PATTERN_REF = "*_counts.txt"
SCADEN_PATTERN_BULK = "*_counts.txt"

CELL_TYPES = [
    "Luminal_Macrophages",
    "Type 2 alveolar",
    "Fibroblasts",
    "Dendritic cells",
]

RESULTS_ROOT = PROJECT_ROOT / "results"
WORK_ROOT = PROJECT_ROOT / "work"

MODELS_ROOT = PROJECT_ROOT / "models"
MODEL_SCADEN_DIR = MODELS_ROOT / "scaden"
MODEL_MUSIC_DIR = MODELS_ROOT / "music"
MODEL_TAPE_DIR = MODELS_ROOT / "tape"
MODEL_SCP_DECONV_DIR = MODELS_ROOT / "scp_deconv"

WORK_DATASET_ROOT = WORK_ROOT / DATASET
WORK_SCADEN_DIR = WORK_DATASET_ROOT / "scaden"
WORK_TAPE_DIR = WORK_DATASET_ROOT / "tape"
WORK_MUSIC_DIR = WORK_DATASET_ROOT / "music"
WORK_SCP_DECONV_DIR = WORK_DATASET_ROOT / "scpdeconv"
WORK_CIBERSORTX_DIR = WORK_DATASET_ROOT / "cibersortx"

DATA_ROOT = PROJECT_ROOT / "data"
DATA_STANDARD_DIR = DATA_ROOT / "standard" / DATASET

STD_REF_H5AD = DATA_STANDARD_DIR / f"{REFERENCE_ID}_train.h5ad"
STD_BULK_H5AD = DATA_STANDARD_DIR / f"{BULK_ID}_test.h5ad"
STD_REF_COUNTS = DATA_STANDARD_DIR / f"{REFERENCE_ID}_counts.txt"
STD_REF_CELLTYPES = DATA_STANDARD_DIR / f"{REFERENCE_ID}_celltypes.txt"
STD_BULK_COUNTS = DATA_STANDARD_DIR / f"{BULK_ID}_counts.txt"
STD_BULK_CELLTYPES = DATA_STANDARD_DIR / f"{BULK_ID}_celltypes.txt"
STD_BULK_X = DATA_STANDARD_DIR / f"{BULK_ID}_bulk_X.txt"
STD_BULK_OBS = DATA_STANDARD_DIR / f"{BULK_ID}_bulk_obs.txt"

# Extra prepare artifacts for external CIBERSORTx-like workflows.
STD_REF_COUNTS_TRANSPOSED = DATA_STANDARD_DIR / f"{REFERENCE_ID}_counts_transposed.txt"
STD_REF_CLASS_LABELS = DATA_STANDARD_DIR / f"{REFERENCE_ID}_class_labels.txt"

# External prediction drop-in file for CIBERSORTx adapter.
CIBERSORTX_PREDICTION_FILE = WORK_CIBERSORTX_DIR / f"predictions_{BULK_ID}.csv"

# Environment-aware executable pins (Windows absolute paths).
# These defaults follow your conda env naming convention.
CONDA_BAT = r"C:\Users\Lenovo\miniconda3\condabin\conda.bat"
MUSIC_CONDA_ENV = "music_env"
SCADEN_CONDA_ENV = "scaden_env"
SCP_CONDA_ENV = "scp_env"
TAPE_CONDA_ENV = "tape_env"

PARITY_BASELINES = {
    "human_lung": {
        "train_id": "296C",
        "test_id": "302C",
        "pseudo_bulk_method": "uniform",
        "models": {
            "scaden": {
                "Pearson": 0.916179,
                "CCC": 0.914159,
                "RMSE": 0.055446,
                "typewise": {
                    "Luminal_Macrophages": 0.847671,
                    "Type 2 alveolar": 0.988878,
                    "Fibroblasts": 0.987586,
                    "Dendritic cells": 0.833317,
                },
            },
            "scpdeconv": {
                "Pearson": 0.980262,
                "CCC": 0.977580,
                "RMSE": 0.028232,
                "typewise": {
                    "Luminal_Macrophages": 0.961748,
                    "Type 2 alveolar": 0.988856,
                    "Fibroblasts": 0.992921,
                    "Dendritic cells": 0.962995,
                },
            },
            "tape": {
                "Pearson": 0.570061,
                "CCC": 0.568751,
                "RMSE": 0.124195,
                "typewise": {
                    "Luminal_Macrophages": 0.405148,
                    "Type 2 alveolar": 0.881858,
                    "Fibroblasts": 0.791648,
                    "Dendritic cells": 0.369143,
                },
            },
            "music": {
                "Pearson": 0.967029,
                "CCC": 0.967017,
                "RMSE": 0.035579,
            },
        },
    }
}
