"""Compose r50 discrete lookups and the validated r51 upper interval; no motion."""
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.local_interval_command_policy import derive_interval_command_policy
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export

ENDPOINT_POLICY='wizard-20260921T025358135319Z-9e37a08d875249caac4601884359f7ed'
INTERVAL_MODEL='wizard-20260921T034147915991Z-6193f1cb9d754682b9cfd9c449e7ae11'


def main():
    root=Path(__file__).resolve().parents[1];exports=(root/'runs/wizard-exports').resolve()
    endpoint,_=_read(exports,ENDPOINT_POLICY,'attachment-local-pair-endpoint-policy.json')
    model,_=_read(exports,INTERVAL_MODEL,'attachment-local-interval-model.json')
    policy=derive_interval_command_policy(endpoint,model,model_export=INTERVAL_MODEL)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'local-interval-command-policy'},[],attachments={
        'local-interval-command-policy.json':canonical(policy)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Interval command policy export invalid')
    print(json.dumps({'export_path':saved['path'],'scope':policy['scope'],
        'minimum_command':policy['interval']['minimum_command'],
        'maximum_command':policy['interval']['maximum_command'],
        'movement_authorized':False}))


if __name__=='__main__':main()
