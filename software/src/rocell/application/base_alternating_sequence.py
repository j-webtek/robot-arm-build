"""Prepare a bounded four-leg template without device access or native authority.

Each directional proposal is rebuilt from original evidence. Fixed measured
handoff anchors are planning assumptions; admission checks every fresh baseline.
The native supervisor registers this profile through the guarded wizard path.
"""
from copy import deepcopy
import hashlib

from .first_motion_contract import canonical
from .base_correction_proposal import propose_base_correction, propose_decreasing_base_correction
from rocell.safety.positional_campaign_authority import (
    BASE_SEQUENCE_SCHEMA, PositionalCampaignIntent, fixed_campaign_limits, sequence_start,
)


def prepare_base_alternating_template(template, *, model_raw, expected_model_sha256,
        training_exports, held_out):
    """Use an existing local base intent's identity/context, never its live permit.

    Timestamps become inert. Callers must later use a dedicated staged review and
    newly issued deadline; the result cannot authorize serial access by itself.
    """
    source=PositionalCampaignIntent(canonical(template)).to_dict()
    evidence=dict(expected_model_sha256=expected_model_sha256,
        training_exports=training_exports,held_out=held_out)
    up=propose_base_correction(model_raw,start_joints_rad=sequence_start(source,0),**evidence).to_dict()
    down=propose_decreasing_base_correction(model_raw,start_joints_rad=sequence_start(source,1),**evidence).to_dict()
    return _assemble_template(source,up,down)


def _assemble_template(source,up,down):
    """Pure contract assembly, also exercised with explicitly synthetic fixtures."""
    body=deepcopy(source)
    body.pop('base_experiment',None)
    body.update(schema=BASE_SEQUENCE_SCHEMA,mode='ATTENDED_FOUR_BASE_CORRECTIONS',
        selected_joint='b',issued_ns=1,deadline_ns=60_000_000_001,
        limits=fixed_campaign_limits(BASE_SEQUENCE_SCHEMA))
    config=dict(schema='rocell.base_alternating_configuration.v1',increasing=up,decreasing=down)
    body['base_sequence']=config
    body['references']['configuration_sha256']=hashlib.sha256(canonical(config)).hexdigest()
    body['legs']=[dict(leg_id=f'leg-{i+1:02d}',expected_start_rad=sequence_start(body,i)[0],
        target_rad=p['nominal_target_rad'],command=dict(T=101,joint=1,
            rad=p['proposed_command_target_rad'],spd=20,acc=1))
        for i,p in enumerate((up,down,up,down))]
    return PositionalCampaignIntent(canonical(body))
