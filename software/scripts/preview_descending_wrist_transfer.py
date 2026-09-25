"""Export one proposed return using the historical descending correction; no I/O."""
import json
from pathlib import Path
from rocell.geometry import UrdfModel
from rocell.application.product_ghost_export_review import _read
from rocell.application.descending_wrist_transfer import build_descending_transfer
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    parent_id='wizard-20260917T191119271010Z-1adad8f0b95e46e995f3c89967081e06'
    ascending_id='wizard-20260917T210328946326Z-0b32d64591154cb688d0f406a57ee317'
    parent,ph=_read(root,parent_id,'attachment-post-tip-wrist-candidate.json')
    ascending,ah=_read(root,ascending_id,'attachment-all-joint-trial.json')
    model=UrdfModel.from_file(Path(__file__).resolve().parents[1]/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    result=dict(candidate=build_descending_transfer(model,parent,ascending),
        sources=[dict(export=parent_id,sha256=ph),dict(export=ascending_id,sha256=ah)],
        limitation='New posture/target transfer. Prior descending success is not prospective validation here.')
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-descending-wrist-transfer'},[],attachments={
        'descending-wrist-transfer.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],review=result)))


if __name__=='__main__':main()
