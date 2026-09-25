"""Authenticated two-leg attended campaign review, not dispatch permission.

Separate schema and MAC domain from single-trial and simulation contracts.
Sealing associates explicit human review with immutable targets and evidence
references. It neither proves that evidence true nor enables a native backend.
"""
from dataclasses import dataclass
import hashlib
import hmac
import math
import re

from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json

DOMAIN = b'rocell.attended-positional-review.v1\x00'
REFERENCES = frozenset(('source_sha256','runtime_sha256','protocol_review_sha256',
    'native_controller_review_sha256','configuration_sha256','workcell_sha256',
    'tool_payload_sha256','stop_qualification_sha256','owned_baseline_sha256'))
CHECKS = frozenset(('secured_and_clear','operator_present_and_shutdown_reachable',
    'starting_pose_visually_consistent','enumerated_route_reviewed','stop_behavior_reviewed'))
BOUNDED_REFERENCES = (REFERENCES - {'stop_qualification_sha256'}) | {'bounded_motion_risk_sha256'}
BOUNDED_CHECKS = (CHECKS - {'stop_behavior_reviewed'}) | {'accepted_goal_completion_risk_reviewed'}
CORRECTION_SCHEMA = 'rocell.attended_positional_intent.v4'
SINGLE_SCHEMA = 'rocell.attended_positional_intent.v5'
BASE_SCHEMA = 'rocell.attended_positional_intent.v6'
SYNC_BASE_SCHEMA = 'rocell.attended_positional_intent.v7'
TWO_DEGREE_BASE_SCHEMA = 'rocell.attended_positional_intent.v8'
MIDPOINT_BASE_SCHEMA = 'rocell.attended_positional_intent.v9'
BASE_CORRECTION_SCHEMA = 'rocell.attended_positional_intent.v10'
BASE_CONTROL_SCHEMA = 'rocell.attended_positional_intent.v11'
DECREASING_BASE_CORRECTION_SCHEMA = 'rocell.attended_positional_intent.v12'
DECREASING_BASE_CONTROL_SCHEMA = 'rocell.attended_positional_intent.v13'
BASE_SEQUENCE_SCHEMA = 'rocell.attended_positional_intent.v14'
BASE_SPEED_SCHEMA = 'rocell.attended_positional_intent.v15'
ROLL_PROBE_SCHEMA = 'rocell.attended_positional_intent.v16'
ROLL_FIXED_SCHEMA = 'rocell.attended_positional_intent.v17'
ROLL_PERSISTENCE_V18_SCHEMA = 'rocell.attended_positional_intent.v18'
ROLL_PERSISTENCE_SCHEMA = 'rocell.attended_positional_intent.v19'
ROLL_LONG_FIXED_SCHEMA = 'rocell.attended_positional_intent.v20'
ROLL_FRAMED_SCHEMA = 'rocell.attended_positional_intent.v21'
ROLL_VARIATION_SCHEMA = 'rocell.attended_positional_intent.v22'
ROLL_PERSISTENCE_SCHEMAS = (ROLL_PERSISTENCE_V18_SCHEMA, ROLL_PERSISTENCE_SCHEMA, ROLL_LONG_FIXED_SCHEMA, ROLL_FRAMED_SCHEMA, ROLL_VARIATION_SCHEMA)
ROLL_SCHEMAS = (ROLL_PROBE_SCHEMA, ROLL_FIXED_SCHEMA, *ROLL_PERSISTENCE_SCHEMAS)
DECREASING_BASE_SCHEMAS = (DECREASING_BASE_CORRECTION_SCHEMA, DECREASING_BASE_CONTROL_SCHEMA)
BASE_CORRECTED_SCHEMAS = (BASE_CORRECTION_SCHEMA, DECREASING_BASE_CORRECTION_SCHEMA)
BASE_EXPERIMENT_SCHEMAS = (BASE_CORRECTION_SCHEMA, BASE_CONTROL_SCHEMA, *DECREASING_BASE_SCHEMAS)
# Frozen arithmetic midpoints of the two observed command anchors per direction.
# These are uncorrected experiment targets, not inverse-model motor commands.
BASE_MIDPOINT_TARGETS = {
    'positive-midpoint': (0.025123196519943297+0.04257648903988659)/2,
    'negative-midpoint': (-0.01649881603988659-0.008249407519943295)/2,
}
SYNC_BASE_SCHEMAS = (SYNC_BASE_SCHEMA,TWO_DEGREE_BASE_SCHEMA,MIDPOINT_BASE_SCHEMA,*BASE_EXPERIMENT_SCHEMAS,BASE_SEQUENCE_SCHEMA,BASE_SPEED_SCHEMA)
BASE_SCHEMAS = (BASE_SCHEMA, *SYNC_BASE_SCHEMAS)
SYNCHRONIZED_SCHEMAS = (*SYNC_BASE_SCHEMAS, *ROLL_SCHEMAS)
BOUNDED_SCHEMAS = ('rocell.attended_positional_intent.v2', 'rocell.attended_positional_intent.v3', CORRECTION_SCHEMA, SINGLE_SCHEMA, *BASE_SCHEMAS, *ROLL_SCHEMAS)
CAPACITY_SCHEMA = 'rocell.attended_positional_intent.v3'


def fixed_campaign_limits(schema='rocell.attended_positional_intent.v1'):
    if schema not in ('rocell.attended_positional_intent.v1', *BOUNDED_SCHEMAS):
        raise ValueError('Unknown campaign capacity profile')
    limits = dict(maximum_writes=2,maximum_duration_s=30,maximum_leg_s=8,
        baseline_s=1,observation_s=5,open_s=4,cleanup_s=2,
        maximum_delta_deg=5,minimum_wrist_deg=-10,maximum_wrist_deg=10,
        start_tolerance_deg=.5,arrival_tolerance_deg=.5,settling_span_deg=.1,
        other_joint_tolerance_deg=.5,dwell_ms=200,spd=20,acc=1,
        maximum_total_raw_bytes=131072,maximum_raw_bytes_per_leg=65536,
        fault_policy='HOLD_NO_RETRY_NO_RETURN',export_policy='WORKSPACE_WIZARD_EXPORTS')
    if schema in (CAPACITY_SCHEMA, CORRECTION_SCHEMA, SINGLE_SCHEMA, *BASE_SCHEMAS):
        # V3 changes capture storage only: 16 KiB baseline + 80 KiB post per
        # leg. V1/V2 signed limits and exports retain their original meaning.
        limits.update(maximum_total_raw_bytes=196608,maximum_raw_bytes_per_leg=98304)
    if schema in (CORRECTION_SCHEMA, SINGLE_SCHEMA, *BASE_SCHEMAS):
        limits.update(maximum_writes=1, maximum_total_raw_bytes=98304)
    if schema in BASE_SCHEMAS:
        limits.update(maximum_delta_deg=1.5,minimum_selected_joint_deg=-5,maximum_selected_joint_deg=5)
    if schema in SYNC_BASE_SCHEMAS:
        limits.update(baseline_s=1.25,synchronization_maximum_ms=250,synchronization_maximum_bytes=4096)
    if schema in (TWO_DEGREE_BASE_SCHEMA,MIDPOINT_BASE_SCHEMA,*BASE_EXPERIMENT_SCHEMAS):
        limits.update(maximum_delta_deg=2.5)
    if schema == BASE_SEQUENCE_SCHEMA:
        limits.update(maximum_writes=4,maximum_duration_s=60,
            maximum_total_raw_bytes=393216,maximum_delta_deg=2.5,start_tolerance_deg=.01)
    if schema == BASE_SPEED_SCHEMA:
        limits.update(spd=10,maximum_delta_deg=2.5,start_tolerance_deg=.01)
    if schema in ROLL_SCHEMAS:
        limits.update(maximum_writes=1,maximum_total_raw_bytes=98304,maximum_raw_bytes_per_leg=98304,
            baseline_s=1.25,synchronization_maximum_ms=250,synchronization_maximum_bytes=4096,
            maximum_delta_deg=1.5,minimum_selected_joint_deg=-3,maximum_selected_joint_deg=3,
            start_tolerance_deg=.01)
    if schema in ROLL_PERSISTENCE_SCHEMAS:
        limits.update(observation_s=35, maximum_leg_s=39,
            maximum_duration_s=50 if schema==ROLL_PERSISTENCE_V18_SCHEMA else 60,
            maximum_total_raw_bytes=540672, maximum_raw_bytes_per_leg=540672)
    return limits


def validate_campaign_intent(body,now_ns):
    fields = {'schema','mode','session_id','campaign_id','usb_identity','references',
        'issued_ns','deadline_ns','start_joints_rad','legs','limits'}
    corrected = type(body) is dict and body.get('schema') == CORRECTION_SCHEMA
    single = type(body) is dict and body.get('schema') == SINGLE_SCHEMA
    base = type(body) is dict and body.get('schema') in BASE_SCHEMAS
    experiment = type(body) is dict and body.get('schema') in BASE_EXPERIMENT_SCHEMAS
    sequence = type(body) is dict and body.get('schema') == BASE_SEQUENCE_SCHEMA
    speed = type(body) is dict and body.get('schema') == BASE_SPEED_SCHEMA
    roll = type(body) is dict and body.get('schema') in ROLL_SCHEMAS
    if roll:fields.update(('selected_joint','roll_probe'))
    if speed:fields.add('base_speed')
    if sequence:fields.add('base_sequence')
    if experiment:fields.add('base_experiment')
    if base:fields.add('selected_joint')
    if corrected:
        fields.add('correction')
    if (type(body) is not dict or set(body) != fields
            or body['schema'] not in ('rocell.attended_positional_intent.v1', *BOUNDED_SCHEMAS)
            or body['mode'] != ('ATTENDED_ONE_ROLL_PROBE' if roll else 'ATTENDED_FOUR_BASE_CORRECTIONS' if sequence else 'ATTENDED_ONE_BASE_PROBE' if base else 'ATTENDED_ONE_CORRECTION' if corrected else 'ATTENDED_ONE_CONTROL' if single else 'ATTENDED_TWO_LEG')):
        raise ValueError('Exact attended two-leg intent required; unattended is not released')
    for name,prefix in (('session_id','wizard-'),('campaign_id','campaign-')):
        if type(body[name]) is not str or not re.fullmatch(prefix+'[a-f0-9]{32}',body[name]):
            raise ValueError('Exact host session/campaign identifier required')
    identity = body['usb_identity']
    if (type(identity) is not dict or set(identity) != {'vid','pid','serial_number'}
            or type(identity['vid']) is not int or identity['vid'] != 0x10c4
            or type(identity['pid']) is not int or identity['pid'] != 0xea60
            or type(identity['serial_number']) is not str
            or not re.fullmatch('[A-F0-9]{32}',identity['serial_number'])):
        raise ValueError('Exact received USB bridge identity required')
    refs = body['references']
    required_refs = BOUNDED_REFERENCES if body['schema'] in BOUNDED_SCHEMAS else REFERENCES
    if (type(refs) is not dict or set(refs) != required_refs
            or any(type(v) is not str or not re.fullmatch('[a-f0-9]{64}',v) or v == '0'*64 for v in refs.values())):
        raise ValueError('Complete non-placeholder campaign evidence references required')
    issued,deadline = body['issued_ns'],body['deadline_ns']
    if (any(type(v) is not int for v in (issued,deadline,now_ns))
            or not 0 < issued <= now_ns < deadline < 2**63
            or deadline-issued != fixed_campaign_limits(body['schema'])['maximum_duration_s']*1_000_000_000):
        raise ValueError('Current fixed 30-second campaign lifetime required')
    if canonical(body['limits']) != canonical(fixed_campaign_limits(body['schema'])):
        raise ValueError('Fixed two-leg campaign limits required')
    start = body['start_joints_rad']
    if (type(start) is not list or len(start) != 6
            or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>2*math.pi for v in start)
            or abs(start[3]) > math.radians(10)):
        raise ValueError('Finite six-joint baseline and bounded wrist start required')
    # These coarse numeric bounds are NOT clearance or servo-limit validation.
    if base and (body['selected_joint']!='b' or abs(start[0])>math.radians(5)):
        raise ValueError('V6 admits only the local base probe')
    previous = start[campaign_joint_index(body)]
    if type(body['legs']) is not list or len(body['legs']) != (4 if sequence else 1 if corrected or single or base or roll else 2):
        raise ValueError('Exactly two enumerated legs required')
    for index,leg in enumerate(body['legs'],1):
        if type(leg) is not dict or set(leg) != {'leg_id','expected_start_rad','target_rad','command'}:
            raise ValueError('Exact absolute leg required')
        target = leg['target_rad']
        if (leg['leg_id'] != f'leg-{index:02d}'
                or type(leg['expected_start_rad']) not in (int,float) or leg['expected_start_rad'] != (sequence_start(body,index-1)[0] if sequence else previous)
                or type(target) not in (int,float) or not math.isfinite(target)
                or abs(target)>math.radians(10)
                or not math.radians(.5)<abs(target-previous)<=math.radians(5)
                or (not corrected and not experiment and not sequence and not speed and canonical(leg['command']) != canonical(dict(T=101,joint=5 if roll else 1 if base else 4,rad=target,spd=20,acc=1)))):
            raise ValueError('Leg target, predecessor, speed or command mismatch')
        nominal_delta=2 if body['schema']==TWO_DEGREE_BASE_SCHEMA else 1
        midpoint=body['schema']==MIDPOINT_BASE_SCHEMA
        if midpoint and (target not in BASE_MIDPOINT_TARGETS.values() or abs(target-previous)>math.radians(2.5)):
            raise ValueError('Exact fixed midpoint and local delta required')
        if base and not midpoint and not experiment and not sequence and not speed and (abs(target)>math.radians(5) or not math.isclose(abs(target-previous),math.radians(nominal_delta),rel_tol=0,abs_tol=1e-12)):
            raise ValueError('Base probe must match its versioned nominal delta in the local envelope')
        previous = target
    if single and body['legs'][0]['target_rad'] not in (math.radians(2),math.radians(4)):
        raise ValueError('Single control supports only tested +2/+4 targets')
    if roll:
        p=body['roll_probe'];leg=body['legs'][0]
        direction='INCREASING' if leg['target_rad']>start[4] else 'DECREASING'
        fixed=body['schema'] in (ROLL_FIXED_SCHEMA,ROLL_LONG_FIXED_SCHEMA,ROLL_FRAMED_SCHEMA,ROLL_VARIATION_SCHEMA)
        expected=roll_fixed_configuration(direction) if fixed else roll_probe_configuration(direction)
        if body['schema'] in ROLL_PERSISTENCE_SCHEMAS:
            expected=roll_persistence_configuration(direction)
        if body['schema'] in (ROLL_LONG_FIXED_SCHEMA,ROLL_FRAMED_SCHEMA):
            expected=roll_long_fixed_configuration(direction, framed=body['schema']==ROLL_FRAMED_SCHEMA)
        if body['schema']==ROLL_VARIATION_SCHEMA:
            expected=roll_variation_configuration(p.get('case_id') if type(p) is dict else None)
        if (body['selected_joint']!='r' or canonical(p)!=canonical(expected)
                or hashlib.sha256(canonical(p)).hexdigest()!=refs['configuration_sha256']
                or (fixed and leg['target_rad']!=expected['target_rad'])
                or (not fixed and not math.isclose(abs(leg['target_rad']-start[4]),math.radians(1),rel_tol=0,abs_tol=1e-12))):
            raise ValueError('Fixed uncorrected one-degree roll probe required')
        require_correction_start(body,start)
    if corrected:
        _validate_correction(body)
    if experiment:
        _validate_base_experiment(body)
    if speed:
        _validate_base_speed(body)
    if sequence:
        p=body['base_sequence']
        if (type(p) is not dict or set(p)!={'schema','increasing','decreasing'}
                or p['schema']!='rocell.base_alternating_configuration.v1'
                or hashlib.sha256(canonical(p)).hexdigest()!=refs['configuration_sha256']):
            raise ValueError('Exact bound alternating configuration required')
        for leg in body['legs']:
            _validate_base_experiment(sequence_leg_body(body,leg))
        require_correction_start(body,start,body['legs'][0])
    return body


def roll_probe_configuration(direction):
    """Pinned reference mapping only; no imported empirical compensation."""
    if direction not in ('INCREASING','DECREASING'):
        raise ValueError('Known roll direction required')
    return dict(schema='rocell.roll_probe_configuration.v1',direction=direction,
        joint='r',logical_joint_id=5,servo_bus_id=16,delta_deg=1,spd=20,acc=1,
        reference_archive_sha256='a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57',
        compensation_applied=False,installed_binary_verified=False,motion_authorized=False)


def roll_persistence_configuration(direction):
    """Same one-degree geometry; separately versioned long observation contract."""
    config=roll_probe_configuration(direction)
    config.update(schema='rocell.roll_persistence_configuration.v1', observation_s=35)
    return config


def roll_long_fixed_configuration(direction, *, framed=False):
    """Frozen long-window command points; measured anchors are not compensation."""
    config=roll_persistence_configuration(direction)
    config.pop('delta_deg')
    config.update(schema='rocell.roll_long_fixed_configuration.v1',
        target_rad=.022055234519943297 if direction=='INCREASING' else -.0005795035199432953,
        expected_roll_start_rad=.004601942 if direction=='INCREASING' else .021475731)
    if framed:
        config['schema']='rocell.roll_long_fixed_configuration.v2'
    return config


def roll_variation_configuration(case_id):
    """Six pinned cases; no arbitrary targets, learned offsets or queued return."""
    offsets={'low':.9,'nominal':1.,'high':1.1}
    if type(case_id) is not str:
        raise ValueError('Enumerated roll variation case required')
    returning=case_id.startswith('return-')
    label=case_id[7:] if returning else case_id
    if label not in offsets:
        raise ValueError('Enumerated roll variation case required')
    start=[.007669904,0.,1.593806039,.047553404,.007669904,3.149262558]
    target=start[4]+math.radians(offsets[label])
    if returning:
        start[4],target=target,start[4]
    config=roll_persistence_configuration('DECREASING' if returning else 'INCREASING')
    config.pop('delta_deg')
    config.update(schema='rocell.roll_target_variation_configuration.v1',case_id=case_id,
        expected_start_joints_rad=start,expected_roll_start_rad=start[4],target_rad=target)
    return config


def roll_fixed_configuration(direction):
    """Previously transmitted raw targets and measured anchors, never an inverse."""
    config=roll_probe_configuration(direction)
    config.pop('delta_deg')
    config.update(schema='rocell.roll_fixed_configuration.v1',
        target_rad=.015919311519943295 if direction=='INCREASING' else -.005181446519943296,
        expected_roll_start_rad=.001533981 if direction=='INCREASING' else .012271846)
    return config


def base_speed_leg_body(body):
    """Internal geometry/endpoint view, never a speed-20 dispatch permission.

    V15 independently validates actual speed-10 bytes. Only unchanged numerical
    endpoint and fitted start-domain checks are shared with older experiments.
    """
    config=body['base_speed'];proposal=config['proposal']
    leg=body['legs'][0]
    return dict(body,
        schema=DECREASING_BASE_CORRECTION_SCHEMA if proposal['direction']=='DECREASING' else BASE_CORRECTION_SCHEMA,
        base_experiment=proposal,
        legs=[dict(leg,command=dict(leg['command'],spd=20))],
        references=dict(body['references'],configuration_sha256=hashlib.sha256(canonical(proposal)).hexdigest()))


def _validate_base_speed(body):
    from rocell.application.base_speed_experiment import speed_experiment_spec
    config=body['base_speed']
    if (type(config) is not dict or set(config)!={'schema','specification','proposal'}
            or config['schema']!='rocell.base_speed_configuration.v1'
            or hashlib.sha256(canonical(config)).hexdigest()!=body['references']['configuration_sha256']
            or type(config['proposal']) is not dict):
        raise ValueError('Exact bound speed configuration required')
    spec=speed_experiment_spec(direction=config['proposal'].get('direction'),speed=10)
    if canonical(config['specification'])!=canonical(spec):
        raise ValueError('Fixed candidate speed specification required')
    command=dict(T=101,joint=1,rad=spec['transmitted_rad'],spd=10,acc=1)
    if canonical(body['legs'][0]['command'])!=canonical(command):
        raise ValueError('Exact speed-10 candidate command required')
    if abs(body['start_joints_rad'][0]-spec['expected_base_start_rad'])>math.radians(.01):
        raise ValueError('Speed experiment must match the measured route anchor')
    _validate_base_experiment(base_speed_leg_body(body))
    require_correction_start(body,body['start_joints_rad'])


def sequence_start(body,index):
    """Fixed measured handoff anchors; never the previous desired angle."""
    start=list(body['start_joints_rad'])
    start[0]=.007669904 if index%2==0 else .018407769
    return start


def sequence_leg_body(body,leg):
    """Project one v14 leg onto unchanged v10/v12 verification mathematics.

    This internal view is not a signed intent or independent dispatch permit.
    The full sequence admission still owns timing, ordering and write count.
    """
    index=next((i for i,item in enumerate(body['legs']) if item==leg),None)
    if index is None:raise ValueError('Leg does not belong to the sequence')
    decreasing=index%2==1
    proposal=body['base_sequence']['decreasing' if decreasing else 'increasing']
    return dict(body,schema=DECREASING_BASE_CORRECTION_SCHEMA if decreasing else BASE_CORRECTION_SCHEMA,
        legs=[leg],start_joints_rad=sequence_start(body,index),base_experiment=proposal,
        references=dict(body['references'],configuration_sha256=hashlib.sha256(canonical(proposal)).hexdigest()))


def campaign_joint_index(body):
    """Versioned axis selection; older records always retain wrist semantics."""
    return 4 if body['schema'] in ROLL_SCHEMAS else 0 if body['schema'] in BASE_SCHEMAS else 3


def _validate_base_experiment(body):
    """One frozen local inverse/control pair, not an arbitrary model executor.

    Trusted staging rebuilds the model and held-out evidence. Native admission
    additionally pins this experiment's numerical domain and command so a signed
    configuration cannot broaden the trial. The control shares the same starting
    domain but sends the nominal endpoint without extrapolating the model.
    """
    p = body['base_experiment']
    leg = body['legs'][0]
    corrected = body['schema'] in BASE_CORRECTED_SCHEMAS
    decreasing = body['schema'] in DECREASING_BASE_SCHEMAS
    candidate = -0.011952475158143525 if decreasing else 0.04076651868282478
    nominal = math.radians(.4 if decreasing else 1)
    if (type(p) is not dict
            or p.get('schema') != ('rocell.offline_base_correction_proposal.v2' if decreasing else 'rocell.offline_base_correction_proposal.v1')
            or hashlib.sha256(canonical(p)).hexdigest() != body['references']['configuration_sha256']):
        raise ValueError('Base proposal/configuration association differs')
    fixed = dict(nominal_target_rad=nominal, proposed_command_target_rad=candidate,
        direction='DECREASING' if decreasing else 'INCREASING',
        start_domain_rad=[0.009203885,0.018407769] if decreasing else [0.006135923,0.007669904],
        command_domain_rad=[-0.01649881603988659,-0.008249407519943295] if decreasing else [0.025123196519943297,0.04257648903988659],
        model_file_sha256='fa8158f348758829ec29452525ccd97b77c34da97778b4073a031a3677884cb5',
        model_sha256='643f9b946319c400de08f2a508700ee27afd500f55e084dc8c7a5cf7f5d40852',
        training_dataset_sha256='aba418750431a590fc96d2c303bf3966d8b8b25445b51bdbc282fde97eb37b5c',
        maximum_commands=1, spd=20, acc=1, maximum_delta_deg=2.5,
        observation_s=5, arrival_tolerance_deg=.5, experiment_error_screen_deg=.25,
        automatic_retry=False, motion_authorized=False, compensation_enabled=False,
        physical_accuracy_verified=False, fresh_baseline_required=True, start_is_historical_only=True)
    if any(canonical(p.get(k)) != canonical(v) for k,v in fixed.items()):
        raise ValueError('Frozen base experiment policy or model differs')
    keys=('native_controller_review_sha256','protocol_review_sha256','workcell_sha256','tool_payload_sha256')
    if (p.get('context_references') != {k:body['references'][k] for k in keys}
            or p.get('expected_start_joints_rad') != body['start_joints_rad']
            or leg['target_rad'] != nominal
            or canonical(leg['command']) != canonical(dict(T=101,joint=1,
                rad=candidate if corrected else nominal,spd=20,acc=1))):
        raise ValueError('Base experiment context, nominal or transmitted target differs')
    require_correction_start(body,body['start_joints_rad'])


def _validate_correction(body):
    """Bind the host-rebuilt proposal to the signed configuration and targets.

    Model/source verification occurs during trusted staging. Child validation
    enforces the same immutable proposal and bounded geometry, not model truth.
    """
    p=body['correction']; leg=body['legs'][0]
    if (type(p) is not dict or p.get('schema')!='rocell.offline_model_correction_proposal.v1'
            or hashlib.sha256(canonical(p)).hexdigest()!=body['references']['configuration_sha256']):
        raise ValueError('Correction proposal/configuration association differs')
    required=('nominal_target_deg','proposed_command_target_deg','proposed_command_target_rad',
              'bias_deg','uncorrected_mean_absolute_error_deg')
    if any(type(p.get(k)) not in (int,float) or not math.isfinite(p[k]) for k in required):
        raise ValueError('Finite correction fields required')
    if (p['nominal_target_deg']!=2 or abs(p['bias_deg'])>1
            or not 0<p['uncorrected_mean_absolute_error_deg']<=2
            or p['proposed_command_target_deg']!=2-p['bias_deg']
            or p['proposed_command_target_rad']!=math.radians(p['proposed_command_target_deg'])
            or leg['target_rad']!=math.radians(2)
            or canonical(leg['command'])!=canonical(dict(T=101,joint=4,rad=p['proposed_command_target_rad'],spd=20,acc=1))
            or p.get('expected_start_joints_rad')!=body['start_joints_rad']
            or p.get('direction')!=('INCREASING' if leg['target_rad']>leg['expected_start_rad'] else 'DECREASING')
            or any(p.get(k) is not False for k in ('motion_authorized','compensation_enabled','automatic_retry'))
            or any(p.get(k)!=v for k,v in dict(maximum_commands=1,spd=20,acc=1,
                arrival_tolerance_deg=.5,observation_s=5,maximum_delta_deg=5,
                correction_screen_maximum_error_deg=.25).items())):
        raise ValueError('Correction targets or fixed policy differ')
    keys=('native_controller_review_sha256','protocol_review_sha256','workcell_sha256','tool_payload_sha256')
    if p.get('context_references')!={k:body['references'][k] for k in keys}:
        raise ValueError('Correction context differs from reviewed originals')
    require_correction_start(body, body['start_joints_rad'])


def require_correction_start(body, start, leg=None):
    """Check both targets at the fresh baseline, not just the nominal target."""
    if body['schema'] in ROLL_SCHEMAS:
        target=body['legs'][0]['target_rad']
        if body['schema']==ROLL_VARIATION_SCHEMA and any(abs(a-b)>math.radians(.01)
                for a,b in zip(start,body['roll_probe']['expected_start_joints_rad'])):
            raise ValueError('Variation six-joint start differs from enumerated anchor')
        if (body['schema'] in (ROLL_FIXED_SCHEMA,ROLL_LONG_FIXED_SCHEMA,ROLL_FRAMED_SCHEMA,ROLL_VARIATION_SCHEMA)
                and abs(start[4]-body['roll_probe']['expected_roll_start_rad'])>math.radians(.01)):
            raise ValueError('Fixed roll start differs from measured anchor')
        reference=(.007669904,0,1.593806039,.047553404,-.001533981,3.149262558)
        if (any(abs(a-b)>math.radians(.01) for a,b in zip(start,body['start_joints_rad']))
                or any(abs(start[i]-reference[i])>math.radians(.5) for i in (0,1,2,3,5))
                or abs(start[4])>math.radians(2) or abs(target)>math.radians(3)
                or not math.radians(.5)<abs(target-start[4])<=math.radians(1.5)
                or (target-start[4])*(target-body['legs'][0]['expected_start_rad'])<=0):
            raise ValueError('Roll pose, fresh start, direction or local envelope differs')
        return
    if body['schema']==BASE_SPEED_SCHEMA:
        if any(abs(a-b)>math.radians(.01) for a,b in zip(start,body['start_joints_rad'])):
            raise ValueError('Speed experiment six-joint start differs')
        return require_correction_start(base_speed_leg_body(body),start)
    if body['schema']==BASE_SEQUENCE_SCHEMA:
        if leg is None:raise ValueError('Explicit next sequence leg required')
        view=sequence_leg_body(body,leg)
        if any(abs(a-b)>math.radians(.01) for a,b in zip(start,view['start_joints_rad'])):
            raise ValueError('Sequence handoff differs from measured anchor')
        return require_correction_start(view,start)
    if body['schema'] not in (CORRECTION_SCHEMA,SINGLE_SCHEMA,*BASE_SCHEMAS):
        return
    leg=body['legs'][0]
    if body['schema'] in BASE_EXPERIMENT_SCHEMAS:
        # Do not replace this learned start-domain gate with the looser generic
        # baseline-matching tolerance; both gates apply to every fresh sample.
        low,high=body['base_experiment']['start_domain_rad']
        if not low<=start[0]<=high:
            raise ValueError('Fresh base start is outside the fitted experiment domain')
        if body['schema'] in DECREASING_BASE_SCHEMAS and start[0]<=math.radians(.9):
            # Check the effective boundary directly: subtraction rounding must
            # not turn exactly 0.5 degrees of nominal travel into >0.5 degrees.
            raise ValueError('Decreasing experiment requires a base start above +0.9 degree')
    if body['schema'] in BASE_SCHEMAS and abs(start[0])>math.radians(5):
        raise ValueError('Fresh base start is outside the local envelope')
    for target in (leg['target_rad'],leg['command']['rad']):
        delta=target-start[campaign_joint_index(body)]
        maximum=1.5 if body['schema'] in BASE_SCHEMAS else 5
        minimum=.5
        if body['schema']==TWO_DEGREE_BASE_SCHEMA:
            minimum,maximum=1.5,2.5
        if body['schema'] in (MIDPOINT_BASE_SCHEMA,*BASE_EXPERIMENT_SCHEMAS):
            maximum=2.5
        if (abs(target)>math.radians(5 if body['schema'] in BASE_SCHEMAS else 10) or not math.radians(minimum)<abs(delta)<=math.radians(maximum)
                or delta*(leg['target_rad']-leg['expected_start_rad'])<=0):
            raise ValueError('Correction start reverses approach or exceeds bounds')


def verify_campaign_endpoint(body, leg, rows, *, start, capture_issues, transport_clean,
                             write_finished_ns=None, capture_finished_ns=None):
    """Identical endpoint mathematics for the child and retained parent review."""
    from rocell.arm.wrist_endpoint_verification import verify_reported_wrist
    if body['schema'] in ROLL_PERSISTENCE_SCHEMAS:
        from rocell.arm.endpoint_persistence import analyze_endpoint_persistence
        result=analyze_endpoint_persistence(rows,joint='r',start=start,target=leg['target_rad'],
            write_finished_ns=write_finished_ns,capture_finished_ns=capture_finished_ns,
            capture_issues=capture_issues,transport_clean=transport_clean)
        endpoint=dict(result['full_window_endpoint'])
        endpoint.update(persistence=result,
            endpoint_verified=result['status']=='REPORTED_ENDPOINT_PERSISTENT',
            status=result['status'])
        return endpoint
    if body['schema'] in ROLL_SCHEMAS:
        from rocell.arm.joint_endpoint_verification import verify_reported_joint
        return verify_reported_joint(rows,joint='r',start=start,target=leg['target_rad'],
            capture_issues=capture_issues,transport_clean=transport_clean)
    if body['schema']==BASE_SPEED_SCHEMA:
        view=base_speed_leg_body(body)
        endpoint=verify_campaign_endpoint(view,view['legs'][0],rows,start=start,
            capture_issues=capture_issues,transport_clean=transport_clean)
        endpoint['correction'].update(experiment_kind='SPEED_CANDIDATE',
            spd=10,acc=1,model_training_speed=20,speed_specific_model_validated=False)
        return endpoint
    if body['schema']==BASE_SEQUENCE_SCHEMA:
        return verify_campaign_endpoint(sequence_leg_body(body,leg),leg,rows,start=start,
            capture_issues=capture_issues,transport_clean=transport_clean)
    if body['schema'] in BASE_SCHEMAS:
        from rocell.arm.joint_endpoint_verification import verify_reported_joint
        endpoint=verify_reported_joint(rows,joint='b',start=start,target=leg['target_rad'],
            capture_issues=capture_issues,transport_clean=transport_clean)
        if body['schema'] in BASE_EXPERIMENT_SCHEMAS:
            commanded=verify_reported_joint(rows,joint='b',start=start,target=leg['command']['rad'],
                capture_issues=capture_issues,transport_clean=transport_clean)
            if commanded['joint_excursion']:
                endpoint.update(endpoint_verified=False,status='JOINT_EXCURSION',joint_excursion=True)
            error=endpoint['final_error_rad']
            passed=bool(endpoint['endpoint_verified'] and error is not None and abs(error)<=math.radians(.25))
            # The stricter experiment screen participates in progression, not
            # just a cosmetic diagnostic beside a looser arrival flag.
            if endpoint['endpoint_verified'] and not passed:
                endpoint.update(endpoint_verified=False,status='TARGET_MISSED')
            endpoint['correction']=dict(experiment_kind='CORRECTED' if body['schema'] in BASE_CORRECTED_SCHEMAS else 'UNCORRECTED_CONTROL',
                nominal_target_rad=leg['target_rad'],command_target_rad=leg['command']['rad'],
                command_endpoint_diagnostic=commanded,experiment_screen_passed=passed,
                model_sha256=body['base_experiment']['model_sha256'],physical_accuracy_verified=False)
        return endpoint
    endpoint=verify_reported_wrist(rows,start=start,target=leg['target_rad'],
        capture_issues=capture_issues,transport_clean=transport_clean)
    if body['schema']==CORRECTION_SCHEMA:
        commanded=verify_reported_wrist(rows,start=start,target=leg['command']['rad'],
            capture_issues=capture_issues,transport_clean=transport_clean)
        if commanded['wrist_excursion']:
            endpoint.update(endpoint_verified=False,status='WRIST_EXCURSION',wrist_excursion=True)
        error=endpoint['final_error_rad']
        endpoint['correction']=dict(nominal_target_rad=leg['target_rad'],
            command_target_rad=leg['command']['rad'], command_endpoint_diagnostic=commanded,
            improvement_screen_passed=bool(endpoint['endpoint_verified'] and error is not None
                and abs(error)<=math.radians(.25)
                and abs(error)<math.radians(body['correction']['uncorrected_mean_absolute_error_deg'])))
    return endpoint


@dataclass(frozen=True,slots=True)
class PositionalCampaignIntent:
    canonical_bytes: bytes

    def __post_init__(self):
        self.to_dict()

    def to_dict(self):
        if type(self.canonical_bytes) is not bytes:
            raise ValueError('Immutable intent bytes required')
        body = decode_diagnostic_json(self.canonical_bytes,maximum=16384)
        if type(body) is not dict or canonical(body) != self.canonical_bytes:
            raise ValueError('Canonical campaign intent required')
        return validate_campaign_intent(body,body.get('issued_ns'))

    @property
    def sha256(self):
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    def require_start_time(self,now_ns):
        self.require_remaining_time(now_ns, phase='open')

    def require_remaining_time(self, now_ns, *, phase):
        """Reserve cleanup before work, never extend the immutable deadline.

        The open phase includes two seconds for parent/process handoff. Each
        leg reserves its full eight-second bound plus serial cleanup. Dispatch
        reserves the one-second write cap, five-second observation and cleanup.
        This check cannot preempt a blocked callback or stop an accepted goal.
        """
        body = validate_campaign_intent(self.to_dict(), now_ns)
        limits = body['limits']
        if phase == 'open':
            required_s = (limits['open_s'] + len(body['legs']) * limits['maximum_leg_s']
                + limits['cleanup_s'] + 2)
        elif phase == 'leg':
            required_s = limits['maximum_leg_s'] + limits['cleanup_s']
        elif phase == 'dispatch':
            required_s = 1 + limits['observation_s'] + limits['cleanup_s']
        else:
            raise ValueError('Unknown campaign timing phase')
        if now_ns + required_s * 1_000_000_000 > body['deadline_ns']:
            raise ValueError('Insufficient campaign work and cleanup budget')

    @property
    def request_sha256(self):
        """Shared collector association; does not convert the request domain."""
        return self.sha256

    def runtime_body(self):
        body=self.to_dict()
        limits=dict(maximum_baseline_ms=1000,maximum_post_observation_ms=5000,
            maximum_baseline_bytes=16384,maximum_post_bytes=49152,
            maximum_baseline_reads=256,maximum_post_reads=512)
        if body['schema'] in (CAPACITY_SCHEMA, CORRECTION_SCHEMA, SINGLE_SCHEMA, *BASE_SCHEMAS, *ROLL_SCHEMAS):
            limits['maximum_post_bytes'] = 81920
        if body['schema'] in SYNCHRONIZED_SCHEMAS:
            limits['maximum_baseline_ms']=1250
        if body['schema'] in ROLL_PERSISTENCE_SCHEMAS:
            limits.update(maximum_post_observation_ms=35000, maximum_post_bytes=524288,
                maximum_post_reads=4096)
        return dict(body,limits=limits,issued_monotonic_ns=body['issued_ns'],
            deadline_monotonic_ns=body['deadline_ns'])


def _review(value,intent,now_ns):
    required_checks = BOUNDED_CHECKS if intent['schema'] in BOUNDED_SCHEMAS else CHECKS
    if (type(value) is not dict or set(value) != {'operator_id','recorded_ns','checks'}
            or type(value['operator_id']) is not str
            or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',value['operator_id'])
            or type(value['recorded_ns']) is not int
            or not intent['issued_ns'] <= value['recorded_ns'] <= now_ns
            or type(value['checks']) is not dict or set(value['checks']) != required_checks
            or any(v is not True for v in value['checks'].values())):
        raise ValueError('Explicit campaign review required; no assumed checks')


class PositionalCampaignReviewAuthority:
    def __init__(self,key):
        if type(key) is not bytes or len(key) != 32:
            raise ValueError('Protected domain-derived 32-byte key required')
        self._key = key

    def seal(self,intent,review,*,now_ns):
        if type(intent) is not PositionalCampaignIntent:
            raise ValueError('Exact campaign intent required')
        intent.require_start_time(now_ns)
        body = intent.to_dict()
        _review(review,body,now_ns)
        bundle = dict(schema='rocell.attended_positional_review.v1',intent=body,review=review)
        bundle['mac'] = hmac.new(self._key,DOMAIN+canonical(bundle),hashlib.sha256).hexdigest()
        return canonical(bundle)

    def verify(self,raw,*,intent,current_usb_identity,current_references,now_ns):
        if type(intent) is not PositionalCampaignIntent or type(raw) is not bytes:
            raise ValueError('Exact campaign and review originals required')
        bundle = decode_diagnostic_json(raw,maximum=24576)
        if (type(bundle) is not dict or set(bundle) != {'schema','intent','review','mac'}
                or bundle['schema'] != 'rocell.attended_positional_review.v1' or canonical(bundle) != raw):
            raise ValueError('Canonical campaign review required')
        mac = bundle.pop('mac')
        if (type(mac) is not str or not re.fullmatch('[a-f0-9]{64}',mac)
                or not hmac.compare_digest(mac,hmac.new(self._key,DOMAIN+canonical(bundle),hashlib.sha256).hexdigest())):
            raise ValueError('Campaign review authentication failed')
        body = validate_campaign_intent(bundle['intent'],now_ns)
        _review(bundle['review'],body,now_ns)
        if (canonical(body) != intent.canonical_bytes
                or canonical(current_usb_identity) != canonical(body['usb_identity'])
                or canonical(current_references) != canonical(body['references'])):
            raise ValueError('Campaign, unit or current evidence changed')
        return dict(intent_sha256=intent.sha256,bundle_sha256=hashlib.sha256(raw).hexdigest(),
            verified_at_ns=now_ns,deadline_ns=body['deadline_ns'],
            evidence_kind='HOST_AUTHENTICATED_CAMPAIGN_REVIEW',
            physical_truth_verified=False,motion_authorized=False)
