"""Offline proposal from the retained r36 response, never a live command tool."""
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.characterization_host_session import _pose
from rocell.application.shoulder_movement_matrix import draft_matrix, classify_observation
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root=Path(__file__).resolve().parents[1]/'runs/wizard-exports'
    source='wizard-20260920T162633791002Z-eee288e20c1446ba8b5d489b339b7985'
    record,digest=_read(root,source,'attachment-characterization-result.json')
    poses=[_pose(p) for p in record['observations']]
    review=classify_observation(_pose(record['baseline']),record['goals'][record['leg']],poses,
        bounds=record['bounds'],delivery_confirmed=True,export_verified=True)
    final=poses[-1]
    matrix=draft_matrix(final.goals[1:3],final.positions[1:3],
                        previous_targets=[(2389,1725),(2397,1717)])
    report=dict(source_export=source,source_sha256=digest,observation_review=review,
                matrix=matrix,baseline_is_historical=True,hardware_access=False,
                live_progression_policy_changed=False)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-movement-matrix-review'},[],attachments={
        'movement-matrix.json':json.dumps(report,indent=2).encode()})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Export verification failed')
    print(json.dumps(dict(export_path=saved['path'],classification=review['classification'],
                         legs=len(matrix['legs']),hardware_access=False)))


if __name__=='__main__':main()
