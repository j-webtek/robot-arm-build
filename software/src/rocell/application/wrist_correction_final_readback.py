"""Pure final-readback contract; not acquisition, freshness renewal or admission.

Historical selection and new telemetry are distinct evidence. The future owned
worker must retain/authenticate both and apply the age check again at dispatch.
This helper never changes original timestamps, targets or a review deadline.
"""
import math
from .first_motion_contract import canonical
from .wrist_correction_preview import preview_wrist_correction
from rocell.arm.first_motion_analysis import _window,JOINTS
from rocell.providers.windows.wrist_correction_native_protocol import digest,require

MAX_BYTES=8192
MAX_READS=16
MAX_WINDOW_NS=200_000_000
MAX_AGE_NS=100_000_000


def validate_final_readback(originals,*,basis,baseline_samples,selection_sha256,
        usb_identity,raw,windows,started_ns,finished_ns,now_ns,review_deadline_ns):
    times=(started_ns,finished_ns,now_ns,review_deadline_ns)
    require(all(type(value) is int and 0<value<2**63 for value in times)
        and started_ns<finished_ns<=now_ns<review_deadline_ns
        and finished_ns-started_ns<=MAX_WINDOW_NS,'Final readback time bounds invalid')
    require(type(raw) is bytes and 0<len(raw)<=MAX_BYTES and raw.endswith(b'\n')
        and type(windows) is list and 2<=len(windows)<=MAX_READS,'Bounded complete final readback required')
    require(type(baseline_samples) is list and len(baseline_samples)>=2,'Original baseline required')
    last=baseline_samples[-1]['host_received_ns']
    require(type(last) is int and last<started_ns,'Final readback must follow original baseline')
    # Reconstruct the old selection at its own acquisition time; this is NOT
    # permission to reuse its timestamp as current admission evidence.
    selected=preview_wrist_correction(originals,expected_basis=basis,samples=baseline_samples,
        now_ns=last,usb_identity=usb_identity)
    require(digest(canonical(selected))==selection_sha256,'Original selected preview differs')
    rows,issues,framing=_window(raw,windows,started_ns,finished_ns)
    require(not issues and framing['unobserved_prefix_range'] is None
        and framing['unobserved_suffix_range'] is None,'Final readback contains gaps or incomplete/invalid frames')
    samples=[dict(host_received_ns=finish,joints_rad=dict(zip(JOINTS,joints))) for _,finish,joints in rows]
    require(now_ns-samples[-1]['host_received_ns']<=MAX_AGE_NS,'Final readback is stale')
    refreshed=preview_wrist_correction(originals,expected_basis=basis,samples=samples,
        now_ns=now_ns,usb_identity=usb_identity)
    # Check every frame, including any excursion that later returns to baseline.
    reference=baseline_samples[-1]['joints_rad']
    require(all(abs(sample['joints_rad'][joint]-reference[joint])<=math.radians(.5)
        for sample in samples for joint in JOINTS),'Final readback differs from selected six-joint baseline')
    require(refreshed['candidate_command']==selected['candidate_command']
        and refreshed['nominal_endpoint_rad']==selected['nominal_endpoint_rad']
        and refreshed['proposal_sha256']==selected['proposal_sha256'],'Final readback changes reviewed target')
    return dict(schema='rocell.wrist_correction_final_readback.v1',selection_sha256=selection_sha256,
        raw_sha256=digest(raw),windows_sha256=digest(canonical(windows)),
        original_baseline_sha256=selected['baseline_sha256'],final_baseline_sha256=refreshed['baseline_sha256'],
        original_last_received_ns=last,final_last_received_ns=samples[-1]['host_received_ns'],
        checked_at_ns=now_ns,review_deadline_ns=review_deadline_ns,
        nominal_endpoint_rad=selected['nominal_endpoint_rad'],candidate_command=selected['candidate_command'],
        sample_count=len(samples),host_age_ns=now_ns-samples[-1]['host_received_ns'],
        device_freshness_verified=False,motion_authorized=False,dispatch_admission_implemented=False)
