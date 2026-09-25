"""Export a model-only six-leg A repeatability sweep; never contacts hardware."""
import json
from pathlib import Path

from rocell.application.air_typing_repeat_recipe import preview,review_source
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=Path(__file__).resolve().parents[1]
    exports=root/"runs/wizard-exports"
    source_digest=review_source(exports)
    model=root/"models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf"
    report=preview(model);report["source_assessment_sha256"]=source_digest
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({"mode":"air-typing-repeat-preview"},[],attachments={
        "air-typing-repeat-preview.json":canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Preview export invalid")
    print(json.dumps(dict(status=report["status"],export_path=saved["path"],
                          minimum_modeled_tcp_z_mm=min(row["minimum_modeled_tcp_z_mm"]
                          for row in report["legs"]),
                          minimum_modeled_link_axis_separation_mm=min(
                              row["minimum_modeled_link_axis_separation_mm"]
                              for row in report["legs"]))))


if __name__=="__main__":main()
