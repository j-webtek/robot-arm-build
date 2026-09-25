"""Separate Cartesian scope, sharing the proven durable exact-send latches."""
import hashlib
import re
from rocell.arm.cartesian_transaction import CartesianTransaction
from rocell.application.first_motion_contract import canonical
from rocell.providers.windows.arm_wifi_feedback import ADDRESS, MAC
from rocell.providers.windows.arm_wifi_observation import review_observation
from .wifi_dispatch_reservation import WifiDispatchReservation


class WifiCartesianReservation(WifiDispatchReservation):
    def __init__(self, *, root, attempt_id, baseline, now_ns, completion_budget_ns, step_mm=2, elbow_only=False, elbow_degrees=2, compensated_endpoint=False, ghost_first_step=False, wrist_probe=False,wrist_candidate=False,wrist_prepare=False):
        if type(attempt_id) is not str or not re.fullmatch(r'[a-f0-9]{32}',attempt_id):
            raise ValueError('Unique attempt ID required')
        if (baseline.get('status')!='SUCCEEDED' or baseline.get('address')!=ADDRESS
                or baseline.get('expected_mac')!=MAC
                or baseline.get('identity_before_matched') is not True
                or baseline.get('identity_after_matched') is not True
                or baseline.get('cleanup_confirmed') is not True):
            raise ValueError('Verified pinned baseline required')
        review_observation(dict(schema='rocell.arm_wifi_observation.v4',samples=[baseline]))
        finish=round(baseline['response_finished_monotonic_s']*1e9)
        if type(now_ns) is not int or not finish<=now_ns<=finish+1_000_000_000:
            raise ValueError('Fresh baseline required')
        self.transaction=CartesianTransaction(baseline=baseline,baseline_finished_ns=finish,
            completion_budget_ns=completion_budget_ns,step_mm=step_mm,elbow_only=elbow_only,elbow_degrees=elbow_degrees,compensated_endpoint=compensated_endpoint,ghost_first_step=ghost_first_step,wrist_probe=wrist_probe,wrist_candidate=wrist_candidate,wrist_prepare=wrist_prepare)
        tx=self.transaction.snapshot()
        config=dict(transport='WIFI_HTTP',address=ADDRESS,expected_mac=MAC,
            frame='R_ctrl',position_units='mm',angle_units='rad',
            policy=tx['policy'],completion_budget_ns=completion_budget_ns,
            speed=dict(spd=tx['command']['spd'],units='FIRMWARE_COEFFICIENT_NOT_MM_PER_SECOND'),
            firmware_version=None,calibration_id=None)
        if compensated_endpoint or wrist_candidate:
            # Bind desired goal, correction identity and acceptance mode durably.
            config['compensated_candidate']=tx['local_candidate']
        request=dict(schema='rocell.cartesian_move_request.v1',request_id=attempt_id,
            frame='R_ctrl',command=tx['command'],target=tx['target'],baseline=tx['baseline'],
            baseline_finished_ns=finish,configuration=config,
            configuration_id=hashlib.sha256(canonical(config)).hexdigest(),
            motion_authorized=False,replay_allowed=False)
        if elbow_only or wrist_probe:
            config['speed']=dict(spd=tx['command']['spd'],acc=tx['command']['acc'],units='FIRMWARE_SERVO_NATIVE')
            config['command_frame']='CONTROLLER_JOINT'
            config['endpoint_observation_frame']='R_ctrl'
            request['configuration_id']=hashlib.sha256(canonical(config)).hexdigest()
        self._publish(root=root,attempt_id=attempt_id,baseline=baseline,now_ns=now_ns,
            finish=finish,completion_budget_ns=completion_budget_ns,request=request)
