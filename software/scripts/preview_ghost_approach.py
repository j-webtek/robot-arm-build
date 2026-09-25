"""Offline approach preview from verified product and saved cycle-preflight exports."""
import argparse
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.product_ghost_approach import preview_ghost_approach
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export
from rocell.simulation.static_bundle import load_static_simulation_bundle,STATIC_ARTIFACT_PATHS
from rocell.geometry import UrdfModel


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--product-export',required=True)
    parser.add_argument('--pose-export',required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]/'software/runs/wizard-exports'
    source,_=_read(root,args.product_export,'attachment-static-task.json')
    pose,_=_read(root,args.pose_export,'attachment-compensated-cycle.json')
    workspace=Path(__file__).resolve().parents[2]
    bundle=load_static_simulation_bundle(workspace)
    model=UrdfModel.from_file(workspace/STATIC_ARTIFACT_PATHS['kinematic_model'])
    report=preview_ghost_approach(source,pose['baseline'],model=model)
    report['static_bundle_sha256']=bundle.source_sha256
    exporter=WizardDiagnosticExporter(root.resolve()); exporter.prepare(create=True)
    receipt=exporter.export(dict(mode='offline-ghost-approach',product_export=args.product_export,pose_export=args.pose_export),[],
        attachments={'ghost-approach.json':json.dumps(report,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']: raise ValueError('Invalid export')
    print(json.dumps(dict(status=report['status'],translation_mm=report['translation_mm'],planned_legs=report['planned_legs'],evaluated_legs=len(report['legs']),export=receipt['path'])))


if __name__=='__main__': main()
