"""Independent startup-record review; never grants motion or physical accuracy."""
import base64
import hashlib

from .baseline_only_review import assess_baseline_only
from .servo_diagnostic_contract import _integer
from .servo_control_state_assessment import assess_control_state
from .servo_session_assessment import assess_session
from .startup_command_contract import validate_startup_plan


def assess_startup_session(snapshot, plan, *, boot_id, approved_policy):
    """Review complete write evidence against frozen host expectations.

    Invalid/incomplete pre-command evidence raises ValueError for the caller to
    retain as inconclusive. A matching authorization record is not independent
    proof of transport provenance, HMAC verification, or durable export.
    """
    doc = validate_startup_plan(plan, boot_id, approved_policy)
    command = doc['command']; policy = approved_policy
    items = snapshot['records']
    prefix = ['startup_auth', 'startup_first', 'startup_second', 'startup_control',
              'receipt', 'converted', 'hook', 'dispatch', 'write']
    if (type(items) is not list or len(items) < len(prefix) or
            [item['kind'] for item in items[:9]] != prefix or
            any(item['kind'] != 'pair' for item in items[9:])):
        raise ValueError('Complete ordered startup evidence required')
    auth, first, second, control = [item['record'] for item in items[:4]]
    expected = dict(schema='rocell.startup_authorization.v1', boot_id=boot_id,
        command_id=command['command_id'], startup_plan_sha256=hashlib.sha256(plan.encoded).hexdigest(),
        policy_id=policy['policy_id'], authentication_verified=True)
    if (type(auth) is not dict or set(auth) != set(expected) | {'received_us'} or
            any(auth[key] != value or type(auth[key]) is not type(value) for key, value in expected.items())):
        raise ValueError('Startup authorization binding mismatch')
    authorized = _integer(auth['received_us'])
    # Validate raw pair lengths, sequence, register map and chronology before
    # accessing compact timestamps or decoded positions.
    baselines = [assess_baseline_only(record, boot_id=boot_id,
        scan_id=command['command_id'], maximum_pair_us=policy['maximum_pair_us'],
        maximum_scan_us=policy['maximum_scan_us']) for record in (first, second)]
    if any(result['status'] != 'BASELINE_CAPTURED' for result in baselines):
        raise ValueError('Incomplete startup scan')
    for result in baselines:
        for joint, window in zip(result['joints'], policy['joints']):
            if joint['target'] != 0 or joint['moving'] != 0 or not window[0] <= joint['position'] <= window[1]:
                raise ValueError('Startup scan state outside policy')
    if any(abs(a['position'] - b['position']) > policy['drift_tolerance']
           for a, b in zip(baselines[0]['joints'], baselines[1]['joints'])):
        raise ValueError('Startup position drift')
    first_start, first_end = first['reads'][0][0][1], first['reads'][-1][1][2]
    second_start, second_end = second['reads'][0][0][1], second['reads'][-1][1][2]
    if not (authorized <= first_start and
            policy['minimum_separation_us'] <= second_start - first_end <= policy['maximum_wait_us']):
        raise ValueError('Startup scan separation invalid')
    receipt, converted, hook = [item['record'] for item in items[4:7]]
    if any(type(converted.get(key)) is not int or converted[key] != value
           for key, value in doc['schedule'].items()):
        raise ValueError('Startup sampling schedule mismatch')
    # Existing session review independently checks hook clocks, receipt payload,
    # transmitted target, write acknowledgment and fresh endpoint samples.
    result = assess_session(dict(snapshot, records=items[4:]),
        base64.b64decode(doc['sent_base64'], validate=True), command, doc['policy'], origin=doc['origin'])
    write_started = int(hook['started_us_raw'])
    control_result = assess_control_state(control, boot_id=boot_id,
        command_id=command['command_id'], reviewed_mode=policy['reviewed_mode'],
        after_us=second_end, boundary_us=write_started, maximum_age_us=policy['maximum_age_us'])
    if (not control_result['last_finished_us'] <= receipt['received_us'] <= write_started or
            write_started - second_start > policy['maximum_age_us']):
        raise ValueError('Startup evidence stale at write boundary')
    target = command['wire_count']; window = policy['joints'][3]
    position = baselines[1]['joints'][3]['position']
    if not (1024 <= target <= 3071 and window[0] <= target <= window[1] and
            abs(target - position) <= doc['baseline_policy']['maximum_delta_counts']):
        raise ValueError('Startup target exceeds position-relative bounds')
    return dict(result, schema='rocell.startup_session_assessment.v1',
        startup_plan_sha256=expected['startup_plan_sha256'], startup_evidence_verified=True,
        initial_elbow_position=position, command_delta_counts=target-position,
        durable_export_verified=False)
