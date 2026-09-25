"""Synthetic endpoint samples -> bounded original wire bytes -> real analysis.

This adapter is deliberately transport-free. Placeholder b/s/e/t joint values
are synthetic zeros, not an IK solution. Only endpoint/orientation fields are
used for Cartesian analysis. Timing is an idealized model with zero-width reads.
"""

import base64
import hashlib
import json

from rocell.arm.movement_analysis import analyze_trial, analyze_endpoint_trial
from .characterization_plan import AXES, FrozenCampaign, _number

MODEL_COMMAND_NS = 1_000_000_000


def analyze_synthetic_trial(plan: FrozenCampaign, trial_id: str, samples: list,
                            *, malformed_index: int | None = None,
                            observation_contract: str = 'CONTINUOUS') -> dict:
    """Build bounded evidence without truncation; reject oversized trial models."""
    if type(samples) is not list or len(samples) > 512:
        raise ValueError("Synthetic trial exceeds 512-read capture budget")
    if observation_contract not in {'CONTINUOUS', 'SUPERVISED_ENDPOINT_ONLY'}:
        raise ValueError('Unsupported observation contract')
    if malformed_index is not None and (type(malformed_index) is not int or not 0 <= malformed_index < len(samples)):
        raise ValueError("Invalid malformed sample index")
    raw = bytearray()
    windows, last = [], -1
    for index, sample in enumerate(samples):
        if type(sample) is not dict or set(sample) != {'model_elapsed_s','pose'}:
            raise ValueError("Invalid synthetic sample")
        pose = sample['pose']
        if type(pose) is not dict or set(pose) != set(AXES):
            raise ValueError("Invalid synthetic pose")
        # Reuse the planner's strict bounded number semantics rather than allow
        # booleans/nonfinite values into a supposedly deterministic model.
        elapsed = _number(sample['model_elapsed_s'], 'model_elapsed_s')
        if elapsed < 0 or elapsed <= last:
            raise ValueError("Synthetic sample times must strictly increase")
        last = elapsed
        p = {key:_number(value,key) for key,value in pose.items()}
        message = {'T':1051,'x':p['x_mm'],'y':p['y_mm'],'z':p['z_mm'],
                   'tit':p['pitch_rad'],'r':p['roll_rad'],'g':p['gripper_rad'],
                   'b':0,'s':0,'e':0,'t':0}
        line = json.dumps(message, separators=(',',':'), allow_nan=False).encode()+b'\n'
        if index == malformed_index:
            line = b'synthetic-malformed-frame\n'
        if len(line)>256 or len(raw)+len(line)>65536:
            raise ValueError("Synthetic wire capture byte budget exceeded")
        tick = MODEL_COMMAND_NS + 1 + round(elapsed*1e9)
        if windows and tick <= windows[-1][3]:
            raise ValueError("Synthetic timestamps collapse at nanosecond resolution")
        windows.append([len(raw),len(raw)+len(line),tick,tick])
        raw.extend(line)
    original=bytes(raw)
    end = windows[-1][3] if windows else MODEL_COMMAND_NS+1
    analyzer = analyze_endpoint_trial if observation_contract == 'SUPERVISED_ENDPOINT_ONLY' else analyze_trial
    result = analyzer(plan,trial_id,original,windows,command_completed_ns=MODEL_COMMAND_NS,
                           observation_end_ns=end,basis='SYNTHETIC_WIRE_REHEARSAL')
    return {'schema':'rocell.synthetic_trial_evidence.v1',
            'basis':'SYNTHETIC_WIRE_REHEARSAL',
            'observation_contract':observation_contract,
            'raw':{'bytes':len(original),'sha256':hashlib.sha256(original).hexdigest(),
                   'base64':base64.b64encode(original).decode('ascii')},
            'read_windows':windows,'command_completed_ns':MODEL_COMMAND_NS,
            'observation_end_ns':end,'analysis':result,
            'joint_values_are_synthetic_placeholders':True,'physical_authority':False}
