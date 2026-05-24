from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable


class ModelAdapter(ABC):
    name: str

    def __init__(
        self,
        project_root: Path,
        results_root: Path,
        dataset: str,
        reference_id: str,
        bulk_id: str,
        cell_types: Iterable[str],
        standard_dir: Path,
        train_cell_type_column: str = "CellType",
        test_cell_type_column: str = "CellType",
        train_sample_column: str = "Sample",
        test_sample_column: str = "Sample",
        seed: int = 0,
    ):
        self.project_root = project_root
        self.results_root = results_root
        self.dataset = dataset
        self.reference_id = reference_id
        self.bulk_id = bulk_id
        self.cell_types = list(cell_types)
        self.standard_dir = standard_dir
        self.train_cell_type_column = train_cell_type_column
        self.test_cell_type_column = test_cell_type_column
        self.train_sample_column = train_sample_column
        self.test_sample_column = test_sample_column
        self.seed = int(seed)
        self.work_root = project_root / "work" / dataset
        self.work_dir = self.work_root / self.name

    @abstractmethod
    def prepare(self) -> None:
        pass

    @abstractmethod
    def run(self) -> None:
        pass

    @abstractmethod
    def prediction_path(self) -> Path:
        pass

    @abstractmethod
    def ground_truth_path(self) -> Path:
        pass

    @abstractmethod
    def prediction_read_kwargs(self) -> dict:
        pass

    @abstractmethod
    def ground_truth_read_kwargs(self) -> dict:
        pass

    def runtime_metadata(self) -> dict:
        return {
            "seed": self.seed,
            "dataset": self.dataset,
            "train_id": self.reference_id,
            "test_id": self.bulk_id,
            "standard_dir": str(self.standard_dir),
            "work_dir": str(self.work_dir),
            "train_cell_type_column": self.train_cell_type_column,
            "test_cell_type_column": self.test_cell_type_column,
            "train_sample_column": self.train_sample_column,
            "test_sample_column": self.test_sample_column,
        }
