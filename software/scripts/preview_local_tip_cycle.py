"""Offline tip press/retract from a verified successful final wrist-leg report."""
import argparse
import json
from pathlib import Path
from rocell.application.local_tip_cycle import preview_local_tip_cycle
from rocell.application.local_tip_controller_preview import preview_local_tip_controller
from rocell.application.compensated_elbow_progression import clean_compensated_completion
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export
from rocell.simulation.static_bundle import load_static_simulation_bundle,STATIC_ARTIFACT_PATHS
from rocell.geometry import UrdfModel


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('export_id')
    p.add_argument('--controller-path',action='store_true',help='Screen offline T104 interpolation as well')
    p.add_argument('--retract-reference',action='store_true',help='Offline upward reference from a retained diagnostic plateau; does not promote a failed endpoint')
    args=p.parse_args()
    workspace=Path(__file__).resolve().parents[2];root=workspace/'software/runs/wizard-exports'
    source,digest=_read(root,args.export_id,'attachment-cartesian-trial.json')
    if args.retract_reference:
        from rocell.application.coordinated_trace_review import review_coordinated_trace
        review=review_coordinated_trace(source)
        if (source['run'].get('error') is not None or
            source['run'].get('acknowledgment_received') is not True or
            review['feedback_failures'] or
            any((review['joints'][i]['unchanged_tail_s'] or 0)<1 for i in (2,3))):
            raise ValueError('Settled diagnostic evidence required; no endpoint promotion')
    elif not clean_compensated_completion(source['run']):raise ValueError('Clean completed source required')
    joints=source['run']['transaction']['rows'][-1][3]
    posture_basis='TRANSACTION_COMPLETION'
    if 'post_completion_observation' in source:
        from rocell.application.endpoint_hold_review import review_endpoint_hold
        hold=review_endpoint_hold(source,source['post_completion_observation'])
        if hold['status']!='REPORTED_HOLD_VERIFIED':raise ValueError('Retained hold did not verify')
        # A completion sample can precede the last settling step. Geometry must
        # start from the verified hold endpoint when this evidence is available.
        joints=hold['final_joints_rad'];posture_basis='VERIFIED_POST_COMPLETION_HOLD'
    bundle=load_static_simulation_bundle(workspace)
    model=UrdfModel.from_file(workspace/STATIC_ARTIFACT_PATHS['kinematic_model'])
    preview=preview_local_tip_controller if args.controller_path else preview_local_tip_cycle
    result=preview(model,joints,
                   direction='retract' if args.retract_reference else 'press')
    result['source_endpoint_status']=source['status']
    result.update(source_posture_basis=posture_basis,source_joints_rad=joints)
    result.update(source_export=args.export_id,source_attachment_sha256=digest,static_bundle_sha256=bundle.source_sha256)
    exporter=WizardDiagnosticExporter(root.resolve());exporter.prepare(create=True)
    receipt=exporter.export(dict(mode='offline-local-tip-cycle'),[],attachments={
        'local-tip-cycle.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],preview={k:v for k,v in result.items() if k not in ('waypoints','legs','local_reference')})))


if __name__=='__main__':main()
