"""One uncorrected reverse identification, bound to a verified forward endpoint.

No forward bias is applied in reverse. This is not an automatic recovery action:
the native adapter must explicitly select this experiment and match fresh state.
"""
from pathlib import Path
from rocell.geometry import UrdfModel
from .product_ghost_export_review import _read
from .identification_endpoint import verified_identification_endpoint
from .asynchronous_response_review import review_response_envelope


def frozen_probe(*, speed_comparison=False):
    if type(speed_comparison) is not bool:
        raise ValueError('Explicit named speed comparison required')
    software=Path(__file__).resolve().parents[3]
    report,digest=_read(software/'runs/wizard-exports',
        'wizard-20260917T212741969917Z-84e87697a9404f2a95a3a321374800bd',
        'attachment-all-joint-trial.json')
    model=UrdfModel.from_file(software/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    endpoint=verified_identification_endpoint(report,model)
    start=endpoint['joints_rad']
    expected=[.001533981,.033747577,1.807029368,-.053689328,.018407769,3.138524692]
    if start!=expected:
        raise ValueError('Reviewed forward endpoint changed')
    target=list(start);target[2]=1.79168956
    envelope=review_response_envelope(model,start,target,extra_steps=1)
    if envelope['status']!='NO_SAMPLED_EXCEEDANCE':
        raise ValueError('Reverse probe exceeds model envelope')
    return dict(baseline_joints_rad=start,target_rad=target[2],source_sha256=digest,
        command=dict(T=101,joint=3,rad=target[2],spd=40 if speed_comparison else 20,acc=1),
        speed_comparison=speed_comparison,
        compensation_applied=False,motion_authorized=False,
        reverse_identification=True,envelope=envelope,source_endpoint=endpoint)
