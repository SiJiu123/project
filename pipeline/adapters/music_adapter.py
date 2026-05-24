from pathlib import Path

from pipeline.adapters.base import ModelAdapter
from pipeline import config
from pipeline.common.io_utils import ensure_dir
from pipeline.common.runner import check_executable, run_command, run_in_conda_env


class MuSiCAdapter(ModelAdapter):
    name = "music"

    def prepare(self) -> None:
        check_executable(config.CONDA_BAT)
        ensure_dir(self.work_dir)
        model_root = config.MODEL_MUSIC_DIR
        run_command(
            [
                "python",
                "converter.py",
                str(self.standard_dir.as_posix()),
                str(self.work_dir.as_posix()),
                self.reference_id,
                self.train_sample_column if self.train_sample_column is not None else "none",
            ],
            cwd=model_root,
        )
        run_in_conda_env(
            config.CONDA_BAT,
            config.MUSIC_CONDA_ENV,
            [
                "Rscript",
                "data_process.R",
                str(self.standard_dir.as_posix()),
                str(self.work_dir.as_posix()),
                self.reference_id,
                self.bulk_id,
            ],
            cwd=model_root,
        )

    def run(self) -> None:
        run_in_conda_env(
            config.CONDA_BAT,
            config.MUSIC_CONDA_ENV,
            [
                "Rscript",
                "music_run.R",
                str(self.work_dir.as_posix()),
                self.reference_id,
                self.bulk_id,
                ",".join(self.cell_types),
                self.train_sample_column if self.train_sample_column is not None else "none",
            ],
            cwd=config.MODEL_MUSIC_DIR,
        )

    def prediction_path(self) -> Path:
        return self.work_dir / f"{self.bulk_id}_music_pred.csv"

    def ground_truth_path(self) -> Path:
        return self.standard_dir / f"{self.bulk_id}_bulk_obs.txt"

    def prediction_read_kwargs(self) -> dict:
        return {"sep": ",", "index_col": 0}

    def ground_truth_read_kwargs(self) -> dict:
        return {"sep": "\t", "index_col": 0}

    def runtime_metadata(self) -> dict:
        metadata = super().runtime_metadata()
        metadata.update(
            {
                "seed_source": "not_applicable_or_deterministic_wrapper",
                "prediction_path": str(self.prediction_path()),
                "ground_truth_path": str(self.ground_truth_path()),
            }
        )
        return metadata
