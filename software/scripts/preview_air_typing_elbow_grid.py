"""Export model-only two-goal elbow grid from retained r82 pose."""
import json
from pathlib import Path

from rocell.application.air_typing_elbow_grid_recipe import preview,review_source
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


if __name__=="__main__":
    root=Path(__file__).resolve().parents[1];exports=root/"runs/wizard-exports"
    digest=review_source(exports)
    report=preview(root/"models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf")
    report["source_assessment_sha256"]=digest
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({"mode":"air-typing-elbow-grid-preview"},[],attachments={
        "air-typing-elbow-grid-preview.json":canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Elbow-grid preview export invalid")
    print(json.dumps(dict(status=report["status"],export_path=saved["path"],
                          minimum_modeled_tcp_z_mm=min(r["minimum_modeled_tcp_z_mm"]
                          for r in report["legs"]),
                          minimum_modeled_link_axis_separation_mm=min(
                              r["minimum_modeled_link_axis_separation_mm"]
                              for r in report["legs"]))))
