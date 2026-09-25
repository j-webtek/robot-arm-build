"""Export the r78 four-leg offline sweep; no controller connection."""
import json
from pathlib import Path

from rocell.application.air_typing_r78_preview import preview
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=Path(__file__).resolve().parents[1]
    result=preview(root/"models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf")
    exporter=WizardDiagnosticExporter(root/"runs/wizard-exports");exporter.prepare(create=True)
    saved=exporter.export({"mode":"r78-air-typing-offline-sweep"},[],attachments={
        "r78-air-typing-preview.json":canonical(result)})
    if not verify_export(Path(saved["path"]))["valid"]:raise ValueError("Preview export invalid")
    print(json.dumps(dict(export_path=saved["path"],status=result["status"],
        min_modeled_z_mm=min(row["minimum_modeled_tcp_z_mm"] for row in result["legs"]),
        min_modeled_separation_mm=min(row["minimum_modeled_link_axis_separation_mm"] for row in result["legs"]))))


if __name__=="__main__":main()
