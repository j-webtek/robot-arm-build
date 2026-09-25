"""Export the cross-session-validated anchor policy; offline only."""
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.local_pair_plateau_policy import derive_plateau_policy
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export

R48='wizard-20260920T214732246917Z-16d2099d2e1747f5bc0d6082c99501bf'
R49='wizard-20260920T224608597099Z-151dafd0c1d547a9bc323d28db5cc550'


def main():
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    r48,_=_read(exports,R48,'attachment-local-pair-mapping-result.json')
    r49,_=_read(exports,R49,'attachment-separated-pair-mapping-result.json')
    policy=derive_plateau_policy(r49['rows'],r48['rows'],r49_export=R49,r48_export=R48)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'local-pair-plateau-policy'},[],attachments={
        'local-pair-plateau-policy.json':canonical(policy)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Plateau policy export invalid')
    print(json.dumps({'export_path':saved['path'],'heldout':policy['heldout'],
                      'fine_endpoint_lookup_validated':False,'movement_authorized':False}))


if __name__=='__main__':main()
