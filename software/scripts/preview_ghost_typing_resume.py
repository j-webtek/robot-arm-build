"""Export the model-only B-key cycle from the last verified arm readback."""
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.ghost_typing_resume_preview import preview
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    exports = root / "runs/wizard-exports"
    report = preview(root / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf", exports)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "ghost-typing-resume-preview"}, [], attachments={
        "ghost-typing-resume-preview.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Ghost typing preview export invalid")
    print(json.dumps(dict(status=report["status"], export_path=saved["path"],
                          legs=len(report["legs"]),
                          minimum_modeled_tcp_z_mm=min(
                              row["minimum_modeled_tcp_z_mm"] for row in report["legs"]),
                          minimum_modeled_link_axis_separation_mm=min(
                              row["minimum_modeled_link_axis_separation_mm"]
                              for row in report["legs"]))))
