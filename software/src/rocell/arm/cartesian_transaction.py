"""One bounded controller-space vertical move; no I/O or motion authority.

T104 receipts are not arrival acknowledgments. Only subsequent XYZ/pitch and
joint observations can establish a reported endpoint. This does not measure a
physical stylus or qualify a board transform.
"""
from copy import deepcopy
import math

from rocell.application.controller_route_preview import preview_vertical_pair, preview_elbow_isolation
from rocell.arm.protocol import CartesianGoal
from rocell.kinematics.firmware_reference import forward, inverse, joint_response_comparison, REFERENCE_SHA256

GAP_NS = 1_000_000_000
JOINT_KEYS = ('b','s','e','t','r','g')
POSE_KEYS = ('x','y','z','tit')


class CartesianTransaction:
    """Fixed +2 or +5 mm Z diagnostic leg, unchanged pitch, roll and gripper.

    The adapter must hold the transport lock and bind the actual identity before
    reserving/sending. A retained snapshot is not sufficient for a live call.
    All acceptance tolerances are provisional reported-state commissioning
    settings, not claims about physical accuracy or task/contact readiness.
    """
    def __init__(self, *, baseline, baseline_finished_ns, completion_budget_ns, step_mm=2, elbow_only=False, elbow_degrees=2, compensated_endpoint=False, ghost_first_step=False, wrist_probe=False,wrist_candidate=False,wrist_prepare=False):
        transfer_entry=wrist_probe=='map-transfer-entry'
        if transfer_entry:wrist_probe='map-cycle-entry'
        transfer_tip=ghost_first_step=='post-transfer-tip'
        if transfer_tip:ghost_first_step='local-tip-press'
        affine_candidate=ghost_first_step=='affine-interior'
        if affine_candidate:ghost_first_step='post-transfer-candidate'
        transfer_candidate=ghost_first_step=='post-transfer-candidate'
        if transfer_candidate and compensated_endpoint is not True:
            raise ValueError('Transferred coordinated candidate requires desired endpoint verification')
        if transfer_candidate:ghost_first_step='local-tip-candidate'
        if type(wrist_prepare) is not bool or (wrist_prepare and (not wrist_probe or wrist_candidate)):
            raise ValueError('Exclusive wrist preparation required')
        if (type(wrist_candidate) is not bool and wrist_candidate not in ('extended-start','nearby-target','pair-down','pair-up')) or (wrist_candidate and not wrist_probe):
            raise ValueError('Wrist candidate requires wrist probe')
        if wrist_probe in ('post-tip','post-tip-reverse','post-overshoot') and (wrist_candidate or wrist_prepare or compensated_endpoint):
            raise ValueError('Post-tip diagnostic must be uncompensated')
        if wrist_probe in ('post-tip-candidate','post-tip-reverse-candidate','post-overshoot-candidate','map-prepare','map-held-out','map-cycle-entry','map-transfer') and (wrist_candidate is not True or wrist_prepare or not compensated_endpoint):
            raise ValueError('Held-out wrist candidate requires desired endpoint verification')
        if (type(wrist_probe) is not bool and wrist_probe not in ('post-coordinated','post-coordinated-ascending','post-tip','post-tip-reverse','post-overshoot','post-tip-candidate','post-tip-reverse-candidate','post-overshoot-candidate','map-prepare','map-held-out','map-cycle-entry','map-transfer')) or (wrist_probe and (ghost_first_step or elbow_only or step_mm!=2 or elbow_degrees!=2)):
            raise ValueError('Exclusive wrist probe required')
        coordinated_mode=ghost_first_step in ('coordinated-candidate','coordinated-candidate-v2','local-tip-candidate')
        if (type(ghost_first_step) is not bool and ghost_first_step not in ('post-wrist','coordinated-candidate','coordinated-candidate-v2','local-tip-press','local-tip-candidate','local-tip-retract')) or (ghost_first_step and (elbow_only or (compensated_endpoint and not coordinated_mode) or step_mm!=2 or elbow_degrees!=2)):
            raise ValueError('Exclusive first ghost step required')
        # Only named candidates supply a desired target distinct from the wire target.
        qualified_compensation = ((elbow_only and elbow_degrees in (3,-6)) or
                                  (wrist_probe and bool(wrist_candidate) and not wrist_prepare) or
                                  coordinated_mode)
        if type(compensated_endpoint) is not bool or (compensated_endpoint and not qualified_compensation):
            raise ValueError('Compensated endpoint requires a qualified local candidate')
        self._compensated_endpoint=compensated_endpoint
        if type(elbow_degrees) is not int or elbow_degrees not in (2,5,-3,1,-1,3,-4,-5,-6,-7,-8,-9,-10) or (not elbow_only and elbow_degrees!=2):
            raise ValueError('Named elbow lift only')
        self._elbow_degrees=elbow_degrees if elbow_only else None
        if type(elbow_only) is not bool or (elbow_only and (type(step_mm) is not int or step_mm!=2)):
            raise ValueError('Exact named elbow diagnostic required')
        preview = preview_elbow_isolation(baseline,elbow_degrees=elbow_degrees) if elbow_only else preview_vertical_pair(baseline,step_mm=step_mm)
        if ghost_first_step:
            if ghost_first_step in ('local-tip-press','local-tip-retract'):
                from rocell.application.local_tip_press import preview_local_tip_press
                preview=preview_local_tip_press(baseline,retract=ghost_first_step=='local-tip-retract',post_transfer=transfer_tip)
            elif coordinated_mode:
                from rocell.application.coordinated_candidate import preview_frozen_candidate
                preview=preview_frozen_candidate(baseline,revised=ghost_first_step=='coordinated-candidate-v2',tip=ghost_first_step=='local-tip-candidate',post_transfer=transfer_candidate,affine=affine_candidate)
            else:
                from rocell.application.ghost_first_step import preview_first_step
                preview=preview_first_step(baseline,post_wrist=ghost_first_step=='post-wrist')
        if wrist_probe:
            from rocell.application.coordinated_wrist_probe import preview_wrist_probe
            if wrist_probe in ('map-prepare','map-held-out','map-cycle-entry','map-transfer'):
                from rocell.application.wrist_map_trial import preview_map_trial
                preview=preview_map_trial(baseline,preparation=wrist_probe in ('map-prepare','map-cycle-entry'),cycle_entry=wrist_probe=='map-cycle-entry',posture_transfer=transfer_entry or wrist_probe=='map-transfer')
            elif wrist_probe in ('post-tip-candidate','post-tip-reverse-candidate','post-overshoot-candidate'):
                from rocell.application.post_tip_wrist_candidate import preview_frozen_candidate
                preview=preview_frozen_candidate(baseline,reverse=wrist_probe=='post-tip-reverse-candidate',post_overshoot=wrist_probe=='post-overshoot-candidate')
            elif wrist_probe in ('post-tip','post-tip-reverse','post-overshoot'):
                from rocell.application.coordinated_wrist_probe import preview_post_tip_wrist
                preview=preview_post_tip_wrist(baseline,reverse=wrist_probe=='post-tip-reverse',post_overshoot=wrist_probe=='post-overshoot')
            else:
                preview=preview_wrist_probe(baseline,candidate=wrist_candidate,prepare=wrist_prepare,
                    post_coordinated=wrist_probe in ('post-coordinated','post-coordinated-ascending'),ascending=wrist_probe=='post-coordinated-ascending')
        if preview['status'] != 'PREVIEW_ONLY_NOT_EXECUTABLE':
            raise ValueError('Screened controller route required')
        self._candidate=preview.get('local_candidate')
        if (type(baseline_finished_ns) is not int or baseline_finished_ns <= 0
                or type(completion_budget_ns) is not int
                or not 2_000_000_000 <= completion_budget_ns <= 15_000_000_000):
            raise ValueError('Bounded timestamps and completion budget required')
        self._start = tuple(preview['starting_pose'])
        self._joints = tuple(baseline['joints_rad'][k] for k in JOINT_KEYS)
        self._step_mm=step_mm
        self._scope=f'LOCAL_Z_PLUS_{step_mm}MM_ONLY'
        if wrist_probe:
            self._target=tuple(preview['target_pose'])
            self._expected=tuple(preview['target_joints_rad'])
            self._command=dict(T=101,joint=4,rad=self._expected[3],spd=20,acc=1)
            self._scope='POST_APPROACH_WRIST_MINUS_1P5_DEGREES_V1'
            if wrist_probe=='post-tip':self._scope='POST_TIP_WRIST_RESPONSE_MINUS_1P5_DEGREES_V1'
            if wrist_probe=='post-overshoot':self._scope='POST_OVERSHOOT_WRIST_RESPONSE_MINUS_1P5_DEGREES_V1'
            if wrist_probe=='post-tip-reverse':self._scope='POST_TIP_WRIST_RESPONSE_PLUS_1P5_DEGREES_V1'
            if wrist_probe=='post-coordinated':self._scope='POST_COORDINATED_WRIST_MINUS_1P5_DEGREES_V1'
            if wrist_probe=='post-coordinated-ascending':self._scope='POST_COORDINATED_WRIST_PLUS_1P5_DEGREES_V1'
            if wrist_candidate:self._scope='POST_APPROACH_WRIST_CANDIDATE_V1'
            if wrist_candidate and wrist_probe=='post-coordinated-ascending':self._scope='POST_COORDINATED_WRIST_ASCENDING_CANDIDATE_V1'
            if wrist_candidate and wrist_probe=='post-coordinated':self._scope='POST_COORDINATED_WRIST_CANDIDATE_V1'
            if wrist_candidate=='nearby-target':self._scope='POST_COORDINATED_WRIST_CANDIDATE_V2'
            if wrist_candidate=='extended-start':self._scope='POST_APPROACH_WRIST_CANDIDATE_V2'
            if wrist_prepare:self._scope='POST_APPROACH_WRIST_PREPARATION_V1'
            if wrist_candidate in ('pair-down','pair-up'):self._scope='WRIST_SHARED_PAIR_'+wrist_candidate.removeprefix('pair-').upper()+'_V1'
            if wrist_probe=='post-tip-candidate':self._scope='POST_TIP_WRIST_HELD_OUT_CANDIDATE_V1'
            if wrist_probe=='post-overshoot-candidate':self._scope='POST_OVERSHOOT_WRIST_HELD_OUT_TRANSFER_V1'
            if wrist_probe=='post-tip-reverse-candidate':self._scope='POST_TIP_WRIST_REVERSE_HELD_OUT_CANDIDATE_V1'
            if wrist_probe in ('map-prepare','map-held-out','map-cycle-entry','map-transfer'):self._scope='WRIST_'+wrist_probe.upper().replace('-','_')+'_V1'
            if transfer_entry:self._scope='WRIST_MAP_TRANSFER_ENTRY_V1'
        elif elbow_only:
            self._target=tuple(preview['target_pose'])
            self._expected=tuple(preview['target_joints_rad'])
            self._command=dict(T=101,joint=3,rad=self._expected[2],spd=40 if elbow_degrees==-10 else 20,acc=1)
            self._scope=('ELBOW_ONLY_PLUS_3_DEGREES_REVIEWED_INTERVAL' if elbow_degrees==-3
                         else f'ELBOW_ONLY_MINUS_{elbow_degrees}_DEGREES')
            if self._candidate: self._scope='ELBOW_LOCAL_ASCENDING_CANDIDATE_V1'
            if elbow_degrees==-1: self._scope='ELBOW_LOCAL_ASCENDING_CANDIDATE_V2'
            if elbow_degrees==3: self._scope='ELBOW_LOCAL_ASCENDING_CANDIDATE_V3'
            if elbow_degrees==-4: self._scope='ELBOW_LOCAL_DESCENDING_CANDIDATE_V1'
            if elbow_degrees==-5: self._scope='ELBOW_LOCAL_DESCENDING_CANDIDATE_V2'
            if elbow_degrees==-6: self._scope='ELBOW_FIXED_START_MAPPING_SAMPLE_V1'
            if elbow_degrees==-7: self._scope='POST_TIP_REVERSE_ELBOW_ISOLATION_V1'
            if elbow_degrees==-8: self._scope='POST_TIP_ELBOW_PLUS_0P012_RAD_V1'
            if elbow_degrees==-9: self._scope='POST_OVERSHOOT_ELBOW_MINUS_0P008_RAD_V1'
            if elbow_degrees==-10: self._scope='POST_OVERSHOOT_ELBOW_SPEED40_V1'
        else:
            self._target = (*self._start[:2],self._start[2]+step_mm,self._start[3])
            if ghost_first_step:
                self._target=tuple(preview['target_pose'])
                self._scope='FIRST_GHOST_APPROACH_5MM_UNCOMPENSATED_V1'
                if ghost_first_step=='post-wrist':self._scope='POST_WRIST_GHOST_APPROACH_5MM_UNCOMPENSATED_V2'
                if ghost_first_step=='coordinated-candidate':self._scope='COORDINATED_OFFSET_HELD_OUT_V1'
                if ghost_first_step=='coordinated-candidate-v2':self._scope='COORDINATED_OFFSET_HELD_OUT_V2'
                if ghost_first_step=='local-tip-press':self._scope='LOCAL_HYPOTHETICAL_TIP_PRESS_2MM_V1'
                if transfer_tip:self._scope='POST_TRANSFER_TIP_PRESS_2MM_V1'
                if ghost_first_step=='local-tip-retract':self._scope='LOCAL_HYPOTHETICAL_TIP_RETRACT_2MM_V1'
                if ghost_first_step=='local-tip-candidate':self._scope='LOCAL_TIP_PRESS_HELD_OUT_V1'
                if transfer_candidate:self._scope='POST_TRANSFER_TIP_HELD_OUT_V1'
                if affine_candidate:self._scope='COORDINATED_AFFINE_INTERIOR_V1'
            self._expected = (*inverse(*self._target),*self._joints[4:])
            self._command = CartesianGoal(*self._target,*self._joints[4:],.05).to_message()
        self._baseline_end = baseline_finished_ns
        self._budget = completion_budget_ns
        self._last = baseline_finished_ns
        self._state = 'PREPARED'
        self._dispatch = self._receipt = None
        self._rows = []
        self._in_band_since = None
        self._in_band_count = 0
        self._result = None
        self._tip_monitor = None
        self._observed_tip_displacement_mm = None
        if transfer_candidate or transfer_tip or transfer_entry or self._elbow_degrees in (-7,-8,-9,-10) or wrist_probe in ('post-overshoot','post-overshoot-candidate','map-transfer'):
            # Enforce the same hypothetical tool bound used by the preview.
            # This is a sampled model-space progression guard, not a servo stop
            # or independently measured collision-clearance guarantee.
            from pathlib import Path
            from rocell.geometry import UrdfModel
            from rocell.application.wrist_tip_review import modeled_tip
            model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/
                'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
            self._tip_monitor=(model,modeled_tip(model,self._joints))

    def _time(self, now):
        if type(now) is not int or now < self._last:
            raise ValueError('Monotonic host time required')
        self._last = now

    def begin_dispatch(self, now):
        self._time(now)
        if self._state != 'PREPARED':
            raise ValueError('Attempt already used')
        if now-self._baseline_end > GAP_NS:
            self._state = 'BASELINE_EXPIRED'
            raise ValueError('Fresh baseline required')
        self._dispatch = now
        self._state = 'DISPATCHING'
        return deepcopy(self._command)

    def acknowledge(self, now):
        self._time(now)
        if self._state != 'DISPATCHING':
            raise ValueError('No pending dispatch')
        if now >= self.next_deadline_ns():
            self._state = 'COMMAND_OUTCOME_UNCERTAIN'
            return
        self._receipt = now
        self._state = 'OBSERVING'

    def next_deadline_ns(self):
        if self._state == 'DISPATCHING':
            return self._dispatch+GAP_NS
        if self._state == 'OBSERVING':
            last = self._rows[-1][1] if self._rows else self._receipt
            return min(last+GAP_NS,self._dispatch+self._budget)
        return None

    def fault(self, now, *, cancelled=False):
        self._time(now)
        if self._state in ('DISPATCHING','OBSERVING'):
            self._state = 'CANCELLED_OUTCOME_UNCERTAIN' if cancelled else 'COMMAND_OUTCOME_UNCERTAIN'

    def tick(self, now):
        self._time(now)
        if self._state in ('DISPATCHING','OBSERVING') and now >= self.next_deadline_ns():
            self._state = ('COMMAND_OUTCOME_UNCERTAIN' if self._state=='DISPATCHING' else
                           'COMPLETION_DEADLINE_EXCEEDED' if now>=self._dispatch+self._budget else
                           'FEEDBACK_GAP_EXCEEDED')

    def observe(self, row, now):
        """row = (request-start ns, response-finish ns, XYZ/pitch, six joints)."""
        self._time(now)
        if self._state != 'OBSERVING':
            raise ValueError('Post-receipt observation required')
        if now >= self.next_deadline_ns():
            self.tick(now)
            return
        if len(self._rows)>=128:
            self._state='OBSERVATION_BUDGET_EXCEEDED'
            return
        begin,end,pose,joints = row
        prior = self._rows[-1][1] if self._rows else self._receipt
        if (type(begin) is not int or type(end) is not int or
                not prior <= begin <= end <= now):
            self._state='FEEDBACK_GAP_EXCEEDED'
            return
        if (len(pose)!=4 or len(joints)!=6 or
                any(type(v) not in (int,float) or not math.isfinite(v) for v in (*pose,*joints))):
            self._state='INVALID_FEEDBACK'
            return
        self._rows.append(deepcopy(row))
        recovered=forward(*joints[:4])
        if math.dist(pose[:3],recovered[:3])>.01 or abs(pose[3]-recovered[3])>1e-5:
            self._state='CONTROLLER_MODEL_MISMATCH'
            return
        if (any(abs(a-b)>math.radians(({5:6,-3:4,-4:6,-5:6,-6:6}.get(self._elbow_degrees,3)) if i==2 else 3)
                for i,(a,b) in enumerate(zip(joints[:4],self._joints[:4])))
                or max(abs(a-b) for a,b in zip(joints[4:],self._joints[4:]))>.02):
            self._state='UNEXPECTED_JOINT_CHANGE'
            return
        if self._tip_monitor is not None:
            from rocell.application.wrist_tip_review import modeled_tip
            model,origin=self._tip_monitor
            self._observed_tip_displacement_mm=math.dist(origin,modeled_tip(model,joints))
            if self._observed_tip_displacement_mm>6:
                self._state='OBSERVED_HYPOTHETICAL_TIP_BOUND_EXCEEDED'
                self._result=dict(endpoint_verified=False,
                    observed_hypothetical_tip_displacement_mm=self._observed_tip_displacement_mm,
                    hypothetical_tip_bound_mm=6,physical_accuracy_verified=False)
                return
        position_error=math.dist(pose[:3],self._target[:3])
        angle_error=abs(pose[3]-self._target[3])
        joint_error=max(abs(a-b) for a,b in zip(joints,self._expected))
        in_band=position_error<=.5 and angle_error<=.02 and joint_error<=.02
        if in_band:
            if self._in_band_since is None:
                self._in_band_since=end
            self._in_band_count+=1
        else:
            self._in_band_since=None
            self._in_band_count=0
        verified=(in_band and self._in_band_count>=3 and begin-self._in_band_since>=500_000_000)
        self._result=dict(endpoint_verified=verified,position_error_mm=position_error,
            pitch_error_rad=angle_error,max_expected_joint_error_rad=joint_error,
            in_band_samples=self._in_band_count,physical_accuracy_verified=False,
            joint_comparison=joint_response_comparison(self._joints,self._expected,joints,
                commanded_joints=(('e',) if self._command['joint']==3 else ('t',)) if self._command['T']==101 else JOINT_KEYS),
            servo_conversion_reference_sha256=REFERENCE_SHA256,
            installed_firmware_verified=False)
        if verified:
            self._state='REPORTED_ENDPOINT_VERIFIED'
        if self._compensated_endpoint:
            from rocell.application.elbow_local_candidate import evaluate_desired_endpoint
            desired=evaluate_desired_endpoint(self._joints,self._rows,candidate=self._candidate)
            if desired['status']=='DESIRED_REPORTED_ENDPOINT_VERIFIED':
                # A distinct task outcome. Never rewrite the wire-target result.
                self._state='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'

    def snapshot(self):
        from rocell.application.elbow_local_candidate import evaluate_desired_endpoint
        return deepcopy(dict(schema='rocell.cartesian_transaction.v1',state=self._state,
            local_candidate=self._candidate,
            desired_endpoint_result=evaluate_desired_endpoint(self._joints,self._rows,candidate=self._candidate) if self._candidate else None,
            command=self._command,command_attempts=int(self._dispatch is not None),
            baseline=self._start,baseline_joints=self._joints,target=self._target,
            expected_joints=self._expected,baseline_finished_ns=self._baseline_end,
            dispatch_started_ns=self._dispatch,acknowledgment_finished_ns=self._receipt,
            completion_budget_ns=self._budget,rows=self._rows,result=self._result,
            observed_hypothetical_tip_displacement_mm=self._observed_tip_displacement_mm,
            policy=dict(position_tolerance_mm=.5,angle_tolerance_rad=.02,dwell_ns=500_000_000,
                        minimum_samples=3,max_feedback_gap_ns=GAP_NS,scope=self._scope,
                        compensated_endpoint=self._compensated_endpoint),
            automatic_retry_allowed=False,automatic_return_allowed=False,
            physical_accuracy_verified=False,motion_authorized=False))
