"""Export the frozen direct-transition campaign; planning only, no hardware access."""
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.ghost_pair_transition_campaign import plan_ghost_pair_transition_campaign
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=Path(__file__).resolve().parents[1];exports=(root/'runs/wizard-exports').resolve()
    plan=plan_ghost_pair_transition_campaign()
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'ghost-pair-transition-campaign-plan'},[],attachments={
        'ghost-pair-transition-campaign-plan.json':canonical(plan)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Transition campaign plan export invalid')
    print(json.dumps({'export_path':saved['path'],'plan_sha256':plan['plan_sha256'],
        'legs':plan['manifest']['legs'],'required_sessions':plan['required_sessions'],
        'movement_authorized':False}))


if __name__=='__main__':main()
