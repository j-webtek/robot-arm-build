"""Two fixed local wrist pairs; default is one read-only starting preview."""
import argparse
import json
from pathlib import Path
from rocell.geometry import UrdfModel
from rocell.providers.windows.all_joint_native import run_native_identification
from rocell.application.repeated_wrist_pair import run_two_pairs
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    exports=(root/'software/runs/wizard-exports').resolve()
    model=UrdfModel.from_file(root/'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    def leg(direction):
        result=run_native_identification(reservation_root=root/'software/runs/cartesian-reservations',
            export_root=exports,model=model,experiment='pair-'+direction,execute=args.execute)
        tx=result.get('transaction',{});rows=tx.get('rows',[])
        print(json.dumps(dict(direction=direction,status=result['status'],export=result.get('export'),
            final=rows[-1]['reported_joints_rad'] if rows else None,
            error_mm=rows[-1]['desired_tip_error_mm'] if rows else None)),flush=True)
        return result
    def verify_leg(result,direction):
        export=result['export']
        if export.get('verified') is not True:return False
        path=Path(export['path']).resolve()
        if path.parent!=exports:return False
        saved,_=_read(exports,path.name,'attachment-all-joint-trial.json')
        tx=saved['transaction'];current=result['transaction']
        return (tx['state']=='REPORTED_SETTLED_PENDING_EXPORT'
            and saved['experiment']=='pair-'+direction
            and all(tx[k]==json.loads(json.dumps(current[k])) for k in
                ('command','candidate','desired_joints_rad','transmitted_joints_rad','rows')))
    if not args.execute:leg('up');return
    result=run_two_pairs(run_leg=leg,verify_leg=verify_leg)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'two-fixed-wrist-pairs'},[],attachments={
        'repeated-wrist-pair.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']))['valid']:raise ValueError('Campaign export failed; do not repeat')
    print(json.dumps(dict(status=result['status'],export=receipt['path'],legs=len(result['legs']))))


if __name__=='__main__':main()
