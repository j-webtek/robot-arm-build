"""Export the frozen three-startup local-interval campaign; planning only."""
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.local_interval_campaign import plan_local_interval_campaign
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=Path(__file__).resolve().parents[1];exports=(root/'runs/wizard-exports').resolve()
    plan=plan_local_interval_campaign();exporter=WizardDiagnosticExporter(exports)
    exporter.prepare(create=True);saved=exporter.export({'mode':'local-interval-campaign-plan'},[],
        attachments={'local-interval-campaign-plan.json':canonical(plan)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Plan export invalid')
    print(json.dumps({'export_path':saved['path'],'sessions':plan['sessions'],
        'endpoints':len(plan['endpoint_commands']),'writes_per_session':len(plan['manifest']['goals']),
        'hardware_access':False,'movement_authorized':False}))


if __name__=='__main__':main()
