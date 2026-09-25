"""Export a matched-start pilot proposal from verified offline compensation data."""
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.compensation_ab_plan import draft_comparison
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=Path(__file__).resolve().parents[1]/'runs/wizard-exports'
    source='wizard-20260920T180630996955Z-ee8cf46f611b41488c4ff50d9a3619bb'
    proposal,digest=_read(root,source,'attachment-stateful-compensation.json')
    record,_=_read(root,proposal['source_pose']['export_id'],'attachment-characterization-result.json')
    report=draft_comparison(proposal,record['bounds'])
    report.update(source_export=source,source_sha256=digest,anchor_is_historical=True,
        prerequisite='Fresh native baseline and reviewed identical conditioning evidence for each campaign')
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-compensation-ab-plan'},[],attachments={
        'compensation-ab-plan.json':json.dumps(report,indent=2).encode()})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Plan export failed')
    print(json.dumps(dict(export_path=saved['path'],campaigns=report['campaigns'],hardware_access=False)))


if __name__=='__main__':main()
