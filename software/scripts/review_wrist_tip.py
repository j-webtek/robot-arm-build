"""Project a verified wrist cycle into the hypothetical stylus model, offline."""
import argparse
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.wrist_tip_review import review_wrist_tip
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export
from rocell.simulation.static_bundle import load_static_simulation_bundle,STATIC_ARTIFACT_PATHS
from rocell.geometry import UrdfModel


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cycle-export',required=True)
    p.add_argument('--ghost-export',required=True);args=p.parse_args()
    workspace=Path(__file__).resolve().parents[2];root=workspace/'software/runs/wizard-exports'
    cycle,digest=_read(root,args.cycle_export,'attachment-compensated-cycle.json')
    if cycle.get('schema')!='rocell.compensated_wrist_cycle.v1' or cycle.get('status')!='LOCAL_CYCLE_REPORTED_ENDPOINTS_VERIFIED' or len(cycle.get('legs',[]))!=2:
        raise ValueError('Completed wrist cycle index required')
    reports=[];sources=[dict(export=args.cycle_export,sha256=digest)]
    for entry in cycle['legs']:
        identity=Path(entry['export']).name
        report,digest=_read(root,identity,'attachment-cartesian-trial.json')
        reports.append(report);sources.append(dict(export=identity,sha256=digest))
    ghost,digest=_read(root,args.ghost_export,'attachment-static-task.json')
    sources.append(dict(export=args.ghost_export,sha256=digest))
    bundle=load_static_simulation_bundle(workspace)
    model=UrdfModel.from_file(workspace/STATIC_ARTIFACT_PATHS['kinematic_model'])
    result=review_wrist_tip(reports,ghost,model)
    result.update(sources=sources,static_bundle_sha256=bundle.source_sha256)
    exporter=WizardDiagnosticExporter(root.resolve());exporter.prepare(create=True)
    receipt=exporter.export(dict(mode='offline-wrist-tip-review'),[],attachments={
        'wrist-tip-review.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise ValueError('Invalid geometry export')
    print(json.dumps(dict(export=receipt['path'],review={k:v for k,v in result.items() if k!='legs'},
        legs=[{k:v for k,v in leg.items() if k!='modeled_arc_samples'} for leg in result['legs']])))


if __name__=='__main__':main()
