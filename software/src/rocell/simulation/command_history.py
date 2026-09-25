"""Reference command-state hypotheses; never installed firmware attestation.

Stored interpolation state can change at motion completion OR reference feedback
acquisition. T105 recomputes XYZ/pitch but does not assign lastR in this source.
"""
from dataclasses import dataclass
import math
from .controller import ControllerPose,simulate_t104_trace


def command_pose(command):
    if command.get('T')!=104:raise ValueError('T104 goal required')
    values=[command.get(k) for k in ('x','y','z','t','r','g')]
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
        raise ValueError('Complete finite command goal required')
    return ControllerPose(*values)


@dataclass
class ReferenceCommandHistory:
    last_goal: ControllerPose | None = None
    invalidation_reason: str = 'NO_REFERENCE_ORIGIN'

    def invalidate(self,reason):
        self.last_goal=None;self.invalidation_reason=reason

    def complete_reference_command(self,command):
        """Simulation event, NOT an HTTP acknowledgment or endpoint observation."""
        if command.get('T')==105:
            self.invalidate('FEEDBACK_ACQUISITION_VALUES_NOT_SUPPLIED')
            return
        if command.get('T')!=104:
            self.invalidate('INTERVENING_COMMAND_FAMILY_NOT_MODELED');return
        goal=command_pose(command)
        self.last_goal=goal;self.invalidation_reason=''

    def complete_reference_feedback(self,reported_pose):
        """Model module.h:614-619,642, preserving stored roll (not feedback roll).

        This represents reference acquisition, not mere receipt of HTTP JSON.
        Acquisition freshness and installed behavior must be established elsewhere.
        """
        if self.last_goal is None:
            self.invalidate('FEEDBACK_DOES_NOT_ESTABLISH_STORED_ROLL');return
        self.last_goal=ControllerPose(reported_pose.x_mm,reported_pose.y_mm,
            reported_pose.z_mm,reported_pose.pitch_rad,self.last_goal.roll_rad,
            self.last_goal.gripper_raw_rad)
        self.invalidation_reason=''

    def preview(self,command,reported_pose):
        target=command_pose(command)
        if self.last_goal is None:
            return dict(status='REFERENCE_ORIGIN_UNKNOWN',reason=self.invalidation_reason,
                motion_authorized=False,installed_state_verified=False)
        speed=command.get('spd')
        if type(speed) not in (int,float) or not math.isfinite(speed) or speed<=0:
            raise ValueError('Positive finite interpolation coefficient required')
        historical=simulate_t104_trace(self.last_goal,target,spd_coefficient=speed,maximum_samples=1024)
        measured=simulate_t104_trace(reported_pose,target,spd_coefficient=speed,maximum_samples=1024)
        return dict(status='REFERENCE_HYPOTHESES_ONLY',historical_trace=historical,
            measured_trace=measured,motion_authorized=False,installed_state_verified=False)
