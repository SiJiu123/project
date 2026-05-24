from pathlib import Path

import pandas as pd

from pipeline.adapters.base import ModelAdapter
from pipeline import config
from pipeline.common.io_utils import ensure_dir
from pipeline.common.runner import check_executable, run_in_conda_env


class ScpDeconvAdapter(ModelAdapter):
    name = "scpdeconv"

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
        dataset_name: str = "human_lung_RNA",
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
        self.dataset_name = dataset_name
        self.target_mode = "external_simulated"

    def _result_dir(self) -> Path:
        return self.work_dir / self.dataset_name

    def _bulk_x(self) -> Path:
        return self.standard_dir / f"{self.bulk_id}_bulk_X.txt"

    def _bulk_obs(self) -> Path:
        return self.standard_dir / f"{self.bulk_id}_bulk_obs.txt"

    def _unified_target_bulk_csv(self) -> Path:
        return self._result_dir() / "unified_target_bulk.csv"

    def _unified_target_obs_csv(self) -> Path:
        return self._result_dir() / "unified_target_obs.csv"

    def _clear_stale_outputs(self) -> None:
        for filename in (
            "target_predicted_fractions.csv",
            "target_gt_fractions.csv",
            "pred_fraction_target_scatter.jpg",
            "Loss_metric_plot_stage3.png",
            "Loss_plot_stage2.png",
        ):
            path = self._result_dir() / filename
            if path.exists():
                path.unlink()

    def _write_unified_target_bulk(self) -> Path:
        bulk_x = self._bulk_x()
        if not bulk_x.exists():
            raise FileNotFoundError(f"Missing unified bulk input for scpdeconv: {bulk_x}")

        ensure_dir(self._result_dir())
        bulk_df = pd.read_csv(bulk_x, sep="\t", index_col=0).T
        bulk_df.to_csv(self._unified_target_bulk_csv())
        return self._unified_target_bulk_csv()

    def _write_unified_target_obs(self) -> Path:
        bulk_obs = self._bulk_obs()
        if not bulk_obs.exists():
            raise FileNotFoundError(f"Missing unified bulk obs for scpdeconv: {bulk_obs}")

        ensure_dir(self._result_dir())
        obs_df = pd.read_csv(bulk_obs, sep="\t", index_col=0)
        obs_df.to_csv(self._unified_target_obs_csv())
        return self._unified_target_obs_csv()

    def prepare(self) -> None:
        check_executable(config.CONDA_BAT)
        self._clear_stale_outputs()
        self._write_unified_target_bulk()
        self._write_unified_target_obs()

    def run(self) -> None:
        result_dir = self._result_dir()
        ensure_dir(result_dir)
        self._clear_stale_outputs()
        target_bulk_csv = self._write_unified_target_bulk()
        target_obs_csv = self._write_unified_target_obs()
        run_in_conda_env(
            config.CONDA_BAT,
            config.SCP_CONDA_ENV,
            [
                "python",
                "main.py",
                "--dataset",
                self.dataset_name,
                "--data_dir",
                str(self.standard_dir.as_posix()),
                "--result_dir",
                str(result_dir.as_posix()),
                "--reference_id",
                self.reference_id,
                "--bulk_id",
                self.bulk_id,
                "--cell_type_column",
                self.train_cell_type_column,
                "--cell_types",
                ",".join(self.cell_types),
                "--target_type",
                self.target_mode,
                "--target_dataset_name",
                str(target_bulk_csv),
                "--target_metadata_name",
                str(target_obs_csv),
            ],
            cwd=config.MODEL_SCP_DECONV_DIR / "scpdeconv_main",
        )

    def prediction_path(self) -> Path:
        return self.work_dir / self.dataset_name / "target_predicted_fractions.csv"

    def ground_truth_path(self) -> Path:
        return self._bulk_obs()

    def prediction_read_kwargs(self) -> dict:
        return {"sep": ",", "index_col": 0}

    def ground_truth_read_kwargs(self) -> dict:
        return {"sep": "\t", "index_col": 0}

    def runtime_metadata(self) -> dict:
        metadata = super().runtime_metadata()
        metadata.update(
            {
                "dataset_name": self.dataset_name,
                "effective_seed": 2021,
                "seed_source": "scpdeconv_internal_fixed",
                "training_target_mode": "internal_simulated",
                "evaluation_target_mode": "unified_bulk_with_unified_proportions",
                "target_mode": self.target_mode,
                "unified_target_bulk_csv": str(self._unified_target_bulk_csv()),
                "unified_target_obs_csv": str(self._unified_target_obs_csv()),
                "prediction_path": str(self.prediction_path()),
                "ground_truth_path": str(self.ground_truth_path()),
            }
        )
        return metadata
