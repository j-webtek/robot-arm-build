"""Fixed new-posture cycle; all legs require exported reported endpoint holds."""
from .compensated_elbow_cycle import CompensatedElbowCycle
from .wrist_map_trial import preview_map_trial
from .post_tip_wrist_candidate import preview_frozen_candidate
from rocell.kinematics.firmware_reference import forward

MODES=('map-transfer-entry','post-overshoot-candidate','map-transfer')
WRISTS=(-.052155347,-.064427193,-.075165059)


def preview_leg(baseline,mode):
    if mode not in MODES:raise ValueError('Named transfer cycle leg required')
    if mode=='post-overshoot-candidate':
        return preview_frozen_candidate(baseline,post_overshoot=True)
    return preview_map_trial(baseline,posture_transfer=True,
        preparation=mode=='map-transfer-entry',cycle_entry=mode=='map-transfer-entry')


class TransferredWristCycle(CompensatedElbowCycle):
    MODES=MODES
    JOINT=4
    SCHEMA='rocell.transferred_wrist_cycle.v1'

    def __init__(self):
        super().__init__(require_hold=True)

    def candidate(self,mode):
        # Geometry-only synthetic input binds the immutable candidate; native
        # admission still requires actual current feedback before each command.
        q=[.001533981,.033747577,1.691980809,WRISTS[MODES.index(mode)],.018407769,3.138524692]
        synthetic=dict(status='SUCCEEDED',identity_before_matched=True,identity_after_matched=True,
            joints_rad=dict(zip(('b','s','e','t','r','g'),q)),
            controller_cartesian=dict(values=dict(zip(('x','y','z','tit'),forward(*q[:4])))))
        return preview_leg(synthetic,mode)['local_candidate']
