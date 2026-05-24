from pathlib import Path


def result_dir(results_root: Path, model_name: str) -> Path:
    return results_root / model_name.lower()


def prediction_file(result_path: Path, bulk_id: str) -> Path:
    return result_path / f"predictions_{bulk_id}.csv"


def summary_metrics_file(result_path: Path) -> Path:
    return result_path / "metrics_summary.csv"


def typewise_metrics_file(result_path: Path) -> Path:
    return result_path / "typewise_ccc.csv"
