import json
import sys
from pathlib import Path

from pipeline import config
from pipeline.adapters.base import ModelAdapter
from pipeline.common.io_utils import ensure_dir
from pipeline.common.naming import prediction_file, result_dir
from pipeline.common.runner import run_command


class _DemoDeconvAdapter(ModelAdapter):
    demo_model_name = ""
    epochs = 100
    batch_size = 50
    learning_rate = 1e-4
    train_samples = 6000
    valid_size = 1000
    sample_size = 30
    patience = 200

    def _train_h5ad(self) -> Path:
        return self.standard_dir / f"{self.reference_id}_train.h5ad"

    def _bulk_x(self) -> Path:
        return self.standard_dir / f"{self.bulk_id}_bulk_X.txt"

    def _bulk_obs(self) -> Path:
        return self.standard_dir / f"{self.bulk_id}_bulk_obs.txt"

    def _out_dir(self) -> Path:
        return result_dir(self.results_root, self.name)

    def _metadata_path(self) -> Path:
        return self.work_dir / "run_metadata.json"

    def prepare(self) -> None:
        ensure_dir(self.work_dir)
        missing = [p for p in [self._train_h5ad(), self._bulk_x(), self._bulk_obs()] if not p.exists()]
        if missing:
            raise FileNotFoundError(f"Missing {self.name} input file(s): {missing}")

    def run(self) -> None:
        ensure_dir(self.work_dir)
        ensure_dir(self._out_dir())
        run_command(
            [
                sys.executable,
                str(self.project_root / "scripts" / "run_demo_deconv.py"),
                "--model",
                self.demo_model_name,
                "--train-h5ad",
                str(self._train_h5ad()),
                "--bulk-x",
                str(self._bulk_x()),
                "--cell-types",
                ",".join(self.cell_types),
                "--cell-type-column",
                self.train_cell_type_column,
                "--out-pred",
                str(self.prediction_path()),
                "--out-meta",
                str(self._metadata_path()),
                "--n-samples",
                str(self.train_samples),
                "--valid-size",
                str(self.valid_size),
                "--sample-size",
                str(self.sample_size),
                "--epochs",
                str(self.epochs),
                "--batch-size",
                str(self.batch_size),
                "--learning-rate",
                str(self.learning_rate),
                "--patience",
                str(self.patience),
                "--seed",
                str(self.seed + 2021),
            ],
            cwd=self.project_root,
        )

    def prediction_path(self) -> Path:
        return prediction_file(self._out_dir(), self.bulk_id)

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
                "demo_model_name": self.demo_model_name,
                "train_h5ad": str(self._train_h5ad()),
                "bulk_x": str(self._bulk_x()),
                "bulk_obs": str(self._bulk_obs()),
                "epochs": self.epochs,
                "batch_size": self.batch_size,
                "learning_rate": self.learning_rate,
                "train_samples": self.train_samples,
                "valid_size": self.valid_size,
                "sample_size": self.sample_size,
                "metadata_path": str(self._metadata_path()),
            }
        )
        if self._metadata_path().exists():
            metadata["run_metadata"] = json.loads(self._metadata_path().read_text(encoding="utf-8"))
        return metadata


class SupDeconvAdapter(_DemoDeconvAdapter):
    name = "supdeconv"
    demo_model_name = "supdeconv"


class ProtoDeconvAdapter(_DemoDeconvAdapter):
    name = "protodeconv"
    demo_model_name = "protodeconv"
