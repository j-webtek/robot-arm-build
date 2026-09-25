"""Exact isolated elbow demand from the reviewed local 2 mm press geometry."""
import hashlib
from pathlib import Path
from .product_ghost_export_review import _read
from .first_motion_contract import canonical


def frozen_probe(*, nearby=False):
    report,digest=_read(Path(__file__).resolve().parents[3]/'runs/wizard-exports',
        'wizard-20260917T211153372030Z-d80ef059e17f4471bd51de3afbf9850a',
        'attachment-press-demands.json')
    start=report['endpoint']['joints_rad'];target=report['isolated_elbow_target_rad']
    expected=[.001533981,.033747577,1.762543925,-.053689328,.018407769,3.138524692]
    if start!=expected or target!=1.7742992981223962:
        raise ValueError('Reviewed elbow probe identity changed')
    if type(nearby) is not bool:raise ValueError('Explicit nearby experiment required')
    if nearby:
        # This is a second identification point, not a correction of the failure.
        prior,digest=_read(Path(__file__).resolve().parents[3]/'runs/wizard-exports',
            'wizard-20260917T211417782591Z-7a6acfc727ba4e6395a14ae328c02760',
            'attachment-all-joint-trial.json')
        if digest!='48235102ddbea8ad9836952711a318ac0551f7f1c3d6312acf260b2dec229f5b':
            raise ValueError('Prior elbow evidence changed')
        start=list(prior['transaction']['rows'][-1]['reported_joints_rad'])
        target=1.785417714
    result=dict(baseline_joints_rad=start,target_rad=target,source_sha256=digest,
        command=dict(T=101,joint=3,rad=target,spd=20,acc=1),
        compensation_applied=False,motion_authorized=False,nearby_identification=nearby)
    return dict(result,probe_sha256=hashlib.sha256(canonical(result)).hexdigest())
