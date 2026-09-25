"""Finite three-leg local cycle, reusing publish-before-progression checks."""
from .compensated_elbow_cycle import CompensatedElbowCycle
from .wrist_map_trial import preview_map_trial
from .post_tip_wrist_candidate import preview_frozen_candidate
from rocell.kinematics.firmware_reference import forward

MODES=('map-cycle-entry','post-tip-candidate','map-held-out')
WRISTS=(-.052155347,-.064427193,-.072097097)


def preview_leg(baseline,mode):
    if mode not in MODES:raise ValueError('Named local cycle leg required')
    if mode=='post-tip-candidate':return preview_frozen_candidate(baseline)
    return preview_map_trial(baseline,preparation=mode=='map-cycle-entry',cycle_entry=mode=='map-cycle-entry')


class LocalWristMappingCycle(CompensatedElbowCycle):
    MODES=MODES
    JOINT=4
    SCHEMA='rocell.local_wrist_mapping_cycle.v1'

    def candidate(self,mode):
        # Synthetic geometry is used ONLY to derive the expected immutable
        # candidate. The hardware adapter independently requires fresh feedback.
        q=[.001533981,.033747577,1.67357304,WRISTS[MODES.index(mode)],.018407769,3.138524692]
        synthetic=dict(status='SUCCEEDED',identity_before_matched=True,identity_after_matched=True,
            joints_rad=dict(zip(('b','s','e','t','r','g'),q)),
            controller_cartesian=dict(values=dict(zip(('x','y','z','tit'),forward(*q[:4])))))
        return preview_leg(synthetic,mode)['local_candidate']
