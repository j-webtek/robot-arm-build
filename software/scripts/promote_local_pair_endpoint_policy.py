"""Compose anchor and r50 evidence into a bounded two-endpoint resolver."""
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.local_pair_endpoint_policy import derive_endpoint_policy
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export

ANCHOR='wizard-20260920T225030977676Z-49605b8c62e2470bb558a7bf8d0e5a5e'
LOOKUP='wizard-20260921T021831649937Z-b061470e8d864fadba3664929977b836'


def main():
    root=Path(__file__).resolve().parents[1];exports=(root/'runs/wizard-exports').resolve()
    anchor,_=_read(exports,ANCHOR,'attachment-local-pair-plateau-policy.json')
    lookup,_=_read(exports,LOOKUP,'attachment-fine-pair-lookup-analysis.json')
    policy=derive_endpoint_policy(anchor,lookup,lookup_analysis_export=LOOKUP)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'local-pair-endpoint-policy'},[],attachments={
        'local-pair-endpoint-policy.json':canonical(policy)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Endpoint policy export invalid')
    print(json.dumps({'export_path':saved['path'],'scope':policy['scope'],
                      'lookups':len(policy['rules']),'movement_authorized':False}))


if __name__=='__main__':main()
