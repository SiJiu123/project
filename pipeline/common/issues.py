import json
from pathlib import Path


def render_run_issues(results_root: Path) -> Path:
    run_report_path = results_root / "run_report.json"
    out_path = results_root / "run_issues.md"

    if not run_report_path.exists():
        out_path.write_text("# Run Issues\n\nrun_report.json not found.\n", encoding="utf-8")
        return out_path

    with open(run_report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    issue_items = [
        item for item in report
        if str(item.get("status", "OK")).upper() != "OK" or str(item.get("error", "") or "").strip()
    ]

    lines = ["# Run Issues", ""]
    if not issue_items:
        lines.append("No run issues recorded.")
    else:
        lines.extend(
            [
                "| Model | Status | Timestamp | Error |",
                "|---|---|---|---|",
            ]
        )
        for item in issue_items:
            model = str(item.get("model", "")).strip()
            status = str(item.get("status", "")).strip()
            timestamp = str(item.get("timestamp", "")).strip()
            error = str(item.get("error", "") or "").replace("\n", " ").strip()
            lines.append(f"| {model} | {status} | {timestamp} | {error} |")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path
