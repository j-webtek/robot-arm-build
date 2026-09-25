"""Export the first bounded encoder-space ghost-key molecule; no hardware access."""
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.ghost_pair_cycle_candidate import plan_ghost_pair_cycle
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export

POLICY='wizard-20260921T034659920859Z-ecdab535f19544a7aaa4d8671d507e50'


def main():
    root=Path(__file__).resolve().parents[1];exports=(root/'runs/wizard-exports').resolve()
    policy,_=_read(exports,POLICY,'attachment-local-interval-command-policy.json')
    candidate=plan_ghost_pair_cycle(policy,current_goals=[2377,1737],
        current_positions=[2385,1730],hover_positions=[2388,1727],
        press_positions=[2390,1725])
    candidate['command_policy_export']=POLICY
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'ghost-pair-cycle-candidate'},[],attachments={
        'ghost-pair-cycle-candidate.json':canonical(candidate)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Ghost pair cycle candidate export invalid')
    print(json.dumps({'export_path':saved['path'],'status':candidate['status'],
        'transition_deltas':candidate['transition_deltas'],
        'movement_authorized':False}))


if __name__=='__main__':main()
