from pathlib import Path
import shutil

import pandas as pd

from pipeline.adapters.base import ModelAdapter
from pipeline import config
from pipeline.common.io_utils import ensure_dir
from pipeline.common.naming import result_dir
from pipeline.common.runner import check_executable, run_in_conda_env


class ScadenAdapter(ModelAdapter):
    name = "scaden"

    def __init__(
        self,
        project_root: Path,
        results_root: Path,
        dataset: str,
        reference_id: str,
        bulk_id: str,
        cell_types,
        standard_dir: Path,
        train_cell_type_column: str = "CellType",
        test_cell_type_column: str = "CellType",
        train_sample_column: str = "Sample",
        test_sample_column: str = "Sample",
        train_steps: int = 5000,
        seed: int = 0,
    ):
        super().__init__(
            project_root,
            results_root,
            dataset,
            reference_id,
            bulk_id,
            cell_types,
            standard_dir,
            train_cell_type_column=train_cell_type_column,
            test_cell_type_column=test_cell_type_column,
            train_sample_column=train_sample_column,
            test_sample_column=test_sample_column,
            seed=seed,
        )
        self.train_steps = int(train_steps)
        self.scaden_data_root = self.work_dir

    def _bulk_x(self) -> Path:
        return self.standard_dir / f"{self.bulk_id}_bulk_X.txt"

    def _bulk_obs(self) -> Path:
        return self.standard_dir / f"{self.bulk_id}_bulk_obs.txt"

    def _processed_h5ad(self) -> Path:
        return self.scaden_data_root / f"{self.reference_id}_processed.h5ad"

    def _reference_work_dir(self) -> Path:
        return self.scaden_data_root / self.reference_id

    def _prepare_scaden_input_dir(self, dataset_id: str) -> Path:
        src_counts = self.standard_dir / f"{dataset_id}_counts.txt"
        src_celltypes = self.standard_dir / f"{dataset_id}_celltypes.txt"
        dataset_dir = self.scaden_data_root / dataset_id
        ensure_dir(dataset_dir)
        # Scaden reads counts with dtype=float32 and may try casting index col.
        # Use a numeric index in staging to avoid parser failures on cell-id strings.
        df_counts = pd.read_csv(src_counts, sep="\t", index_col=0)
        df_counts.index = range(len(df_counts))
        df_counts.to_csv(dataset_dir / f"{dataset_id}_counts.txt", sep="\t")

        df_labels = pd.read_csv(src_celltypes, sep="\t")
        if "Celltype" not in df_labels.columns:
            if "CellType" in df_labels.columns:
                df_labels = df_labels.rename(columns={"CellType": "Celltype"})
            elif len(df_labels.columns) == 1:
                df_labels.columns = ["Celltype"]
            else:
                raise ValueError(
                    f"Unsupported celltype schema for {dataset_id}: {list(df_labels.columns)}"
                )
        df_labels.to_csv(dataset_dir / f"{dataset_id}_celltypes.txt", sep="\t", index=False)
        return dataset_dir

    def _preflight(self, dataset_id: str) -> None:
        counts = self.standard_dir / f"{dataset_id}_counts.txt"
        labels = self.standard_dir / f"{dataset_id}_celltypes.txt"
        if not counts.exists() or not labels.exists():
            raise FileNotFoundError(
                f"Missing Scaden input pair for {dataset_id}: "
                f"counts={counts.exists()}, celltypes={labels.exists()}"
            )

        n_counts = len(pd.read_csv(counts, sep="\t", index_col=0))
        n_labels = len(pd.read_csv(labels, sep="\t"))
        if n_counts != n_labels:
            raise ValueError(
                f"Scaden input row mismatch for {dataset_id}: "
                f"counts_rows={n_counts}, celltypes_rows={n_labels}"
            )

    def prepare(self) -> None:
        check_executable(config.CONDA_BAT)
        ensure_dir(self.scaden_data_root)
        self._preflight(self.reference_id)
        self._preflight(self.bulk_id)
        ref_dir = self._prepare_scaden_input_dir(self.reference_id)
        run_in_conda_env(
            config.CONDA_BAT,
            config.SCADEN_CONDA_ENV,
            [
                "python",
                str((self.project_root / "scripts" / "run_scaden_simulate.py").as_posix()),
                "--data",
                str(ref_dir.as_posix()),
                "--n_samples",
                str(config.SCADEN_SIM_N_REF),
                "--pattern",
                config.SCADEN_PATTERN_REF,
                "--prefix",
                self.reference_id,
                "--out",
                str(ref_dir.as_posix()),
                "--seed",
                str(self.seed),
            ],
            cwd=config.MODEL_SCADEN_DIR / "scaden-master",
        )
        run_in_conda_env(
            config.CONDA_BAT,
            config.SCADEN_CONDA_ENV,
            [
                "scaden",
                "process",
                str((self._reference_work_dir() / f"{self.reference_id}.h5ad").as_posix()),
                str(self._bulk_x().as_posix()),
                "--processed_path",
                str(self._processed_h5ad().as_posix()),
            ],
            cwd=self.project_root,
        )

    def run(self) -> None:
        model_dir = self.project_root / "save_models" / self.dataset / f"scaden{self.train_steps}"
        if model_dir.exists():
            shutil.rmtree(model_dir)
        ensure_dir(model_dir.parent)

        run_in_conda_env(
            config.CONDA_BAT,
            config.SCADEN_CONDA_ENV,
            [
                "scaden",
                "train",
                str(self._processed_h5ad().as_posix()),
                "--steps",
                str(self.train_steps),
                "--seed",
                str(self.seed),
                "--model_dir",
                str(model_dir.as_posix()),
            ],
            cwd=self.project_root,
        )

        out_dir = result_dir(self.results_root, self.name)
        ensure_dir(out_dir)
        run_in_conda_env(
            config.CONDA_BAT,
            config.SCADEN_CONDA_ENV,
            [
                "scaden",
                "predict",
                "--model_dir",
                str(model_dir.as_posix()),
                "--seed",
                str(self.seed),
                str(self._bulk_x().as_posix()),
                "--outname",
                str((out_dir / f"predictions_{self.bulk_id}.csv").as_posix()),
            ],
            cwd=self.project_root,
        )

    def prediction_path(self) -> Path:
        return result_dir(self.results_root, self.name) / f"predictions_{self.bulk_id}.csv"

    def ground_truth_path(self) -> Path:
        return self._bulk_obs()

    def prediction_read_kwargs(self) -> dict:
        return {"sep": None, "index_col": 0}

    def ground_truth_read_kwargs(self) -> dict:
        return {"sep": "\t", "index_col": 0}

    def runtime_metadata(self) -> dict:
        metadata = super().runtime_metadata()
        metadata.update(
            {
                "simulate_seed": self.seed,
                "train_seed": self.seed,
                "predict_seed": self.seed,
                "train_steps": self.train_steps,
                "reference_work_dir": str(self._reference_work_dir()),
                "processed_h5ad": str(self._processed_h5ad()),
                "bulk_x": str(self._bulk_x()),
                "bulk_obs": str(self._bulk_obs()),
            }
        )
        return metadata
