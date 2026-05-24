from pathlib import Path

from pipeline.adapters.base import ModelAdapter
from pipeline import config
from pipeline.common.io_utils import ensure_dir
from pipeline.common.runner import check_executable, run_in_conda_env


class TAPEAdapter(ModelAdapter):
    name = "tape"

    def prepare(self) -> None:
        check_executable(config.CONDA_BAT)
        ensure_dir(self.work_dir)
        run_in_conda_env(
            config.CONDA_BAT,
            config.TAPE_CONDA_ENV,
            [
                "python",
                "data_process.py",
                str(self.standard_dir.as_posix()),
                str(self.work_dir.as_posix()),
                self.reference_id,
                str(self.seed),
            ],
            cwd=config.MODEL_TAPE_DIR,
        )

    def run(self) -> None:
        run_in_conda_env(
            config.CONDA_BAT,
            config.TAPE_CONDA_ENV,
            [
                "python",
                "tape_run.py",
                str(self.standard_dir.as_posix()),
                str(self.work_dir.as_posix()),
                self.reference_id,
                self.bulk_id,
                str(self.seed),
            ],
            cwd=config.MODEL_TAPE_DIR,
        )

    def prediction_path(self) -> Path:
        work_pred = self.work_dir / f"{self.bulk_id}_pred_fractions.txt"
        if work_pred.exists():
            return work_pred
        return self.results_root / self.name / f"predictions_{self.bulk_id}.csv"

    def ground_truth_path(self) -> Path:
        return self.standard_dir / f"{self.bulk_id}_bulk_obs.txt"

    def prediction_read_kwargs(self) -> dict:
        work_pred = self.work_dir / f"{self.bulk_id}_pred_fractions.txt"
        if work_pred.exists():
            return {"sep": "\t", "index_col": 0}
        return {"sep": ",", "index_col": 0}

    def ground_truth_read_kwargs(self) -> dict:
        return {"sep": "\t", "index_col": 0}

    def runtime_metadata(self) -> dict:
        metadata = super().runtime_metadata()
        metadata.update(
            {
                "effective_seed": self.seed,
                "prediction_path": str(self.prediction_path()),
                "ground_truth_path": str(self.ground_truth_path()),
            }
        )
        return metadata
