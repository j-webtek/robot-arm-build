"""Fit the r61 direction hypothesis from three immutable campaign exports."""
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.visible_interval_analysis import analyze_visible_interval_cycles
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


SOURCES = (
    "wizard-20260922T231423328861Z-4964be9217f44d1e97bfab522fe2e743",
    "wizard-20260922T232910754318Z-d79be2ed34814a949658bfad4e269eae",
    "wizard-20260922T233002049318Z-4108c0fe4ee5457fbde2efaed2564591",
)


def main():
    root = Path(__file__).resolve().parents[1]
    exports = (root / "runs/wizard-exports").resolve()
    cycles = []
    for source in SOURCES:
        document, _ = _read(exports, source, "attachment-visible-interval-campaign-result.json")
        cycles.append(document)
    analysis = analyze_visible_interval_cycles(cycles)
    analysis["source_exports"] = list(SOURCES)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export(
        {"mode": "visible-interval-direction-analysis"}, [],
        attachments={"visible-interval-direction-model.json": canonical(analysis)},
    )
    if not verify_export(Path(saved["path"]).resolve())["valid"]:
        raise ValueError("Direction model export invalid")
    print(json.dumps({"export_path": saved["path"],
                      "direction_models": analysis["direction_models"],
                      "held_out_proposal": analysis["held_out_proposal"],
                      "compensation_promoted": False}))


if __name__ == "__main__":
    main()
