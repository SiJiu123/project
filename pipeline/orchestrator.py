import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from pipeline import config
from pipeline.common.io_utils import align_to_cell_types, ensure_dir, read_table, write_table
from pipeline.common.naming import prediction_file, result_dir, summary_metrics_file, typewise_metrics_file
from pipeline.common.runner import run_command
from pipeline.model_registry import REGISTRY, normalize_model_name, parse_model_names


class PipelineOrchestrator:
    def __init__(
        self,
        project_root: Path,
        results_root: Path,
        dataset: str,
        reference_id: str,
        bulk_id: str,
        cell_types: Iterable[str],
        train_cell_type_column: str = "CellType",
        test_cell_type_column: str = "CellType",
        train_sample_column: str = "Sample",
        test_sample_column: str = "Sample",
        train_steps: int = 5000,
        seed: int = 0,
        scp_dataset_name: str = "human_lung_RNA",
        standard_rebuild_mode: str = "always",
    ):
        self.project_root = project_root
        self.dataset = dataset
        self.global_results_root = results_root
        self.results_root = results_root / self.dataset
        self.reference_id = reference_id
        self.bulk_id = bulk_id
        self.cell_types = list(cell_types)
        self.train_cell_type_column = train_cell_type_column
        self.test_cell_type_column = test_cell_type_column
        self.train_sample_column = train_sample_column
        self.test_sample_column = test_sample_column
        self.train_steps = train_steps
        self.seed = int(seed)
        self.scp_dataset_name = scp_dataset_name
        self.standard_rebuild_mode = str(standard_rebuild_mode)
        self.standard_dir = self.project_root / "data" / "standard" / self.dataset

    def _build_adapter(self, model_name: str):
        normalized = normalize_model_name(model_name)
        if normalized not in REGISTRY:
            raise ValueError(f"Unsupported model: {model_name}")
        adapter_cls = REGISTRY[normalized]

        if normalized == "scaden":
            return adapter_cls(
                self.project_root,
                self.results_root,
                self.dataset,
                self.reference_id,
                self.bulk_id,
                self.cell_types,
                self.standard_dir,
                train_cell_type_column=self.train_cell_type_column,
                test_cell_type_column=self.test_cell_type_column,
                train_sample_column=self.train_sample_column,
                test_sample_column=self.test_sample_column,
                train_steps=self.train_steps,
                seed=self.seed,
            )
        if normalized == "scpdeconv":
            return adapter_cls(
                self.project_root,
                self.results_root,
                self.dataset,
                self.reference_id,
                self.bulk_id,
                self.cell_types,
                self.standard_dir,
                train_cell_type_column=self.train_cell_type_column,
                test_cell_type_column=self.test_cell_type_column,
                train_sample_column=self.train_sample_column,
                test_sample_column=self.test_sample_column,
                dataset_name=self.scp_dataset_name,
                seed=self.seed,
            )
        return adapter_cls(
            self.project_root,
            self.results_root,
            self.dataset,
            self.reference_id,
            self.bulk_id,
            self.cell_types,
            self.standard_dir,
            train_cell_type_column=self.train_cell_type_column,
            test_cell_type_column=self.test_cell_type_column,
            train_sample_column=self.train_sample_column,
            test_sample_column=self.test_sample_column,
            seed=self.seed,
        )

    def _should_rebuild_standard_data(self) -> bool:
        mode = self.standard_rebuild_mode.strip().lower()
        if mode == "always":
            return True
        if mode == "never":
            return False
        if mode == "if_missing":
            required = [
                self.standard_dir / f"{self.reference_id}_train.h5ad",
                self.standard_dir / f"{self.bulk_id}_test.h5ad",
                self.standard_dir / f"{self.reference_id}_counts.txt",
                self.standard_dir / f"{self.reference_id}_celltypes.txt",
                self.standard_dir / f"{self.bulk_id}_counts.txt",
                self.standard_dir / f"{self.bulk_id}_celltypes.txt",
                self.standard_dir / f"{self.bulk_id}_bulk_X.txt",
                self.standard_dir / f"{self.bulk_id}_bulk_obs.txt",
                self.standard_dir / f"{self.reference_id}_counts_transposed.txt",
                self.standard_dir / f"{self.reference_id}_class_labels.txt",
            ]
            if any(not p.exists() for p in required):
                return True
            return False
        raise ValueError(
            f"Unsupported STANDARD_REBUILD_MODE: {self.standard_rebuild_mode}. "
            "Use one of: always, if_missing, never"
        )

    def run(self, model: str, stages: Iterable[str]) -> None:
        stage_set = {s.lower() for s in stages}
        model_names = parse_model_names(model)
        normalized = normalize_model_name(model)

        if "prepare" in stage_set:
            data_args = [
                f"DATASET={self.dataset}",
                f"TRAIN_ID={self.reference_id}",
                f"TEST_ID={self.bulk_id}",
                f"TRAIN_CELL_TYPE_COLUMN={self.train_cell_type_column}",
                f"TEST_CELL_TYPE_COLUMN={self.test_cell_type_column}",
                f"TRAIN_SAMPLE_COLUMN={self.train_sample_column}",
                f"TEST_SAMPLE_COLUMN={self.test_sample_column}",
                f"CELL_TYPES={','.join(self.cell_types)}",
                f"SEED={self.seed}",
            ]
            if self._should_rebuild_standard_data():
                run_command(["python", "scripts/migrate_naming.py", *data_args], cwd=self.project_root)
            else:
                print("Skip standard 10-file rebuild (STANDARD_REBUILD_MODE policy).")

            run_command(["python", "scripts/build_cibersortx_inputs.py", *data_args], cwd=self.project_root)

        run_report = []

        for model_name in model_names:
            adapter = self._build_adapter(model_name)
            report_item = {
                "model": model_name,
                "status": "OK",
                "error": "",
                "timestamp": datetime.now().isoformat(),
                "seed": self.seed,
                "pseudo_bulk_method": config.PSEUDOBULK_ACTIVE_METHOD,
                "input_files": self._report_input_files(),
                "model_metadata": adapter.runtime_metadata(),
            }
            try:
                if "prepare" in stage_set:
                    adapter.prepare()
                if "run" in stage_set:
                    adapter.run()
                if "eval" in stage_set:
                    pred_path = adapter.prediction_path()
                    gt_path = adapter.ground_truth_path()
                    if not pred_path.exists() or not gt_path.exists():
                        report_item["status"] = "SKIPPED"
                        report_item["error"] = (
                            f"Missing eval file(s): prediction={pred_path.exists()}, ground_truth={gt_path.exists()}"
                        )
                        print(f"[{adapter.name}] skip eval: {report_item['error']}")
                    else:
                        report_item.update(self._evaluate(adapter))
            except Exception as exc:
                report_item["status"] = "FAILED"
                report_item["error"] = str(exc)
                if len(model_names) == 1:
                    raise
            finally:
                run_report.append(report_item)

        ensure_dir(self.results_root)
        with open(self.results_root / "run_report.json", "w", encoding="utf-8") as f:
            json.dump(run_report, f, ensure_ascii=False, indent=2)

        if "eval" in stage_set:
            from pipeline.common.issues import render_run_issues
            from pipeline.common.leaderboard import render_leaderboard
            from pipeline.common.parity import render_parity_report
            from pipeline.common.plots import render_typewise_boxplot

            render_run_issues(self.results_root)
            render_leaderboard(
                self.results_root,
                self.dataset,
                self.reference_id,
                self.bulk_id,
                model_names,
            )
            baseline = config.PARITY_BASELINES.get(self.dataset)
            if baseline is not None:
                render_parity_report(
                    self.results_root,
                    self.dataset,
                    baseline,
                    self.standard_dir,
                    model_names,
                )
            # Always attempt a combined figure from available model eval artifacts.
            render_typewise_boxplot(self.results_root, model_names)

    def _evaluate(self, adapter) -> dict:
        from pipeline.common.metrics import compute_metrics, compute_typewise_ccc
        from pipeline.common.io_utils import describe_file

        pred = read_table(adapter.prediction_path(), **adapter.prediction_read_kwargs())
        gt = read_table(adapter.ground_truth_path(), **adapter.ground_truth_read_kwargs())

        pred = align_to_cell_types(pred, self.cell_types)
        gt = align_to_cell_types(gt, self.cell_types)

        model_out = result_dir(self.results_root, adapter.name)
        ensure_dir(model_out)

        pred_out = prediction_file(model_out, self.bulk_id)
        write_table(pred, pred_out, sep=",", index=True)

        summary = compute_metrics(pred, gt)
        write_table(summary, summary_metrics_file(model_out), sep=",", index=False)

        evaluation_obj = {
            "model": adapter.name,
            "dataset": self.dataset,
            "reference_id": self.reference_id,
            "bulk_id": self.bulk_id,
            "seed": self.seed,
            "pseudo_bulk_method": config.PSEUDOBULK_ACTIVE_METHOD,
            "input_files": self._report_input_files(),
            "model_metadata": adapter.runtime_metadata(),
            "pearson": float(summary.loc[0, "Pearson"]),
            "ccc": float(summary.loc[0, "CCC"]),
            "rmse": float(summary.loc[0, "RMSE"]),
            "timestamp": datetime.now().isoformat(),
        }
        with open(model_out / "evaluation.json", "w", encoding="utf-8") as f:
            json.dump(evaluation_obj, f, ensure_ascii=False, indent=2)

        typewise = compute_typewise_ccc(pred, gt, self.cell_types)
        write_table(typewise, typewise_metrics_file(model_out), sep=",", index=False)
        return {
            "pearson": float(summary.loc[0, "Pearson"]),
            "ccc": float(summary.loc[0, "CCC"]),
            "rmse": float(summary.loc[0, "RMSE"]),
            "prediction_file": describe_file(pred_out),
            "ground_truth_file": describe_file(adapter.ground_truth_path()),
        }

    def _report_input_files(self) -> dict:
        from pipeline.common.io_utils import describe_file

        return {
            "train_h5ad": describe_file(self.standard_dir / f"{self.reference_id}_train.h5ad"),
            "test_h5ad": describe_file(self.standard_dir / f"{self.bulk_id}_test.h5ad"),
            "train_counts": describe_file(self.standard_dir / f"{self.reference_id}_counts.txt"),
            "train_celltypes": describe_file(self.standard_dir / f"{self.reference_id}_celltypes.txt"),
            "bulk_x": describe_file(self.standard_dir / f"{self.bulk_id}_bulk_X.txt"),
            "bulk_obs": describe_file(self.standard_dir / f"{self.bulk_id}_bulk_obs.txt"),
        }
