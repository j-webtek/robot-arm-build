"""Verify the five immutable r95 exports and summarize controller consistency."""
import json
from pathlib import Path

from rocell.application.bare_hover_cycle_analysis import analyze
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import (
    WizardDiagnosticExporter, verify_export,
)

EXPORTS = (
    "wizard-20260925T175239899544Z-b01b2d4bd0014798bcd16078e6fac8a3",
    "wizard-20260925T184230842590Z-c53992896fce4d4f99d27db7cad107a8",
    "wizard-20260925T184309529486Z-0ef21c5ddcdc4d9492cdd8b564cb9bf3",
    "wizard-20260925T184440994897Z-ee8a958090454b44b20c5283f8b61319",
    "wizard-20260925T184552652527Z-43a68b4aa26347deb4bc89f9d087eb74",
)


def main(root: Path) -> dict:
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    records = []
    for export_id in EXPORTS:
        directory = exports / export_id
        if not verify_export(directory)["valid"]:
            raise ValueError(f"Invalid r95 export: {export_id}")
        records.append(json.loads(
            (directory / "attachment-bare-hover-leg.json").read_text()))
    report = analyze(records)
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({"mode": "r95-bare-hover-offline-analysis"}, [],
        attachments={"r95-bare-hover-analysis.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r95 analysis export invalid")
    return dict(report=report, export=saved["path"])


if __name__ == "__main__":
    print(json.dumps(main(Path(__file__).resolve().parents[1]), indent=2))
