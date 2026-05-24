from pathlib import Path

from pipeline.adapters.base import ModelAdapter
from pipeline.common.io_utils import ensure_dir


class CIBERSORTxAdapter(ModelAdapter):
    name = "cibersortx"

    def prepare(self) -> None:
        # External model workflow: no internal prepare needed here.
        ensure_dir(self.work_dir)

    def run(self) -> None:
        # External model workflow: user places prediction file manually.
        pass

    def prediction_path(self) -> Path:
        return self.work_dir / f"predictions_{self.bulk_id}.csv"

    def ground_truth_path(self) -> Path:
        return self.standard_dir / f"{self.bulk_id}_bulk_obs.txt"

    def prediction_read_kwargs(self) -> dict:
        # Use auto delimiter detection for flexibility.
        return {"sep": None, "index_col": 0}

    def ground_truth_read_kwargs(self) -> dict:
        return {"sep": "\t", "index_col": 0}

    def runtime_metadata(self) -> dict:
        metadata = super().runtime_metadata()
        metadata.update(
            {
                "seed_source": "external_prediction",
                "prediction_path": str(self.prediction_path()),
                "ground_truth_path": str(self.ground_truth_path()),
            }
        )
        return metadata
