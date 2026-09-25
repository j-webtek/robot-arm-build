"""T102 scope using the existing durable exact-send latches."""
import re
from rocell.arm.all_joint_transaction import AllJointTransaction
from rocell.providers.windows.arm_wifi_feedback import ADDRESS, MAC
from rocell.providers.windows.arm_wifi_observation import review_observation
from .wifi_dispatch_reservation import WifiDispatchReservation


def verify_sample(sample):
    if (sample.get('status') != 'SUCCEEDED' or sample.get('address') != ADDRESS
            or sample.get('expected_mac') != MAC
            or any(sample.get(k) is not True for k in
                   ('identity_before_matched','identity_after_matched','cleanup_confirmed'))
            or sample.get('timing_clock') != 'HOST_PERF_COUNTER'):
        raise ValueError('Pinned, cleaned-up, monotonic feedback required')
    review_observation(dict(schema='rocell.arm_wifi_observation.v4',samples=[sample]))


class WifiAllJointReservation(WifiDispatchReservation):
    def __init__(self, *, root, attempt_id, baseline, now_ns, model, overrides,wrist_single=False,normalized_candidate=False,elbow_single=False):
        if type(attempt_id) is not str or not re.fullmatch('[a-f0-9]{32}',attempt_id):
            raise ValueError('Unique attempt ID required')
        verify_sample(baseline)
        finish=round(baseline['response_finished_monotonic_s']*1e9)
        if type(now_ns) is not int or not finish <= now_ns <= finish+1_000_000_000:
            raise ValueError('Fresh baseline required')
        self.transaction=AllJointTransaction(model,baseline,
            baseline_finished_s=finish/1e9,overrides=overrides,wrist_single=wrist_single,normalized_candidate=normalized_candidate,elbow_single=elbow_single)
        request=dict(schema='rocell.all_joint_request.v1',request_id=attempt_id,
            command=self.transaction.command,baseline_finished_ns=finish,
            desired_joints_rad=self.transaction.desired,candidate=self.transaction.candidate,identification_probe=self.transaction.probe,
            frame='CONTROLLER_JOINT',angle_units='rad',speed_units='FIRMWARE_SERVO_NATIVE',
            preview=self.transaction.preview,motion_authorized=False,replay_allowed=False)
        self._publish(root=root,attempt_id=attempt_id,baseline=baseline,now_ns=now_ns,
            finish=finish,completion_budget_ns=10_000_000_000,request=request)
