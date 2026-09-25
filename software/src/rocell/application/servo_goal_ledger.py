"""Offline mixed-goal continuity checks; not native admission or motion authority."""
from dataclasses import dataclass
from pathlib import Path

from .first_motion_contract import canonical
from .product_ghost_export_review import _read
from .startup_started_run import replay_started_startup
from .servo_transport_export import replay_transport_export
from .baseline_only_review import assess_baseline_only
from .servo_acquisition_pair import assess_acquisition_pair
from .servo_diagnostic_contract import _integer, _identifier
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .servo_control_state_assessment import assess_control_state


@dataclass(frozen=True)
class GoalLedger:
    # Immutable exact bytes, not a mutable dictionary or transferable authority.
    encoded: bytes


def load_startup_ledger(root, started_export_id):
    root=Path(root).resolve()
    replay=replay_started_startup(root,started_export_id)
    assessment=replay['outcome'].get('assessment')
    if (replay['delivery']['result']!='CONTROLLER_REPORTED_ACCEPTANCE' or
            replay['outcome']['status']!='ASSESSED' or not assessment or
            assessment['category']!='DIAGNOSTIC_ENDPOINT_CRITERIA_MET' or
            assessment['write']['acknowledgment_verified'] is not True):
        raise ValueError('Verified accepted startup arrival required; no continuation')
    link,link_hash=_read(root,started_export_id,'attachment-started-startup-run.json')
    run,_=_read(root,link['startup_run_export_id'],'attachment-startup-run.json')
    context,_=_read(root,run['plan_export_id'],'attachment-startup-context.json')
    snapshot=replay_transport_export(root,run['capture_export_id'])['summary']
    records=snapshot['records'];second=records[2]['record'];dispatch=records[7]['record']
    baseline=assess_baseline_only(second,boot_id=context['boot_id'],scan_id=dispatch['command_id'])
    pair=assess_acquisition_pair(records[-1]['record'],boot_id=context['boot_id'],
        command_id=dispatch['command_id'],servo_id=14,dispatch_us=dispatch['device_us'],
        previous_sequence=-1,previous_finished_us=dispatch['device_us'],
        maximum_pair_us=context['approved_policy']['maximum_pair_us'])
    if pair['decoded']['feedback']['moving']['decoded_value']!=0:
        raise ValueError('Last endpoint sample still reports motion')
    joints=[dict(servo_id=j['servo_id'],goal=j['target'],position=j['position'],commanded=False)
            for j in baseline['joints']]
    joints[3].update(goal=dispatch['wire_count'],
        position=pair['decoded']['feedback']['position']['decoded_value'],commanded=True)
    return GoalLedger(canonical(dict(schema='rocell.goal_ledger.v1',boot_id=context['boot_id'],
        predecessor_command_id=dispatch['command_id'],predecessor_export_id=started_export_id,
        predecessor_sha256=link_hash,finished_us=pair['last_finished_us'],
        policy=context['approved_policy'],joints=joints,progression_authority=False)))


def assess_mixed_goal_scan(root, started_export_id, record, *, scan_id, boundary_us):
    """Rebuild ledger from verified exports on every review; no supplied mutable ledger.

    A passing scan checks one observation only. Two-scan stability, control-state
    reads, signed campaign phase and final native write guard are still required.
    """
    ledger=decode_diagnostic_json(load_startup_ledger(root,started_export_id).encoded,maximum=4096)
    return _assess_scan(ledger, record, scan_id=scan_id, boundary_us=boundary_us)


def _assess_scan(ledger, record, *, scan_id, boundary_us):
    # Only internal callers supply a ledger reconstructed from verified exports.
    _identifier(scan_id);_integer(boundary_us)
    if scan_id==ledger['predecessor_command_id']:raise ValueError('Distinct continuation observation ID required')
    policy=ledger['policy']
    result=assess_baseline_only(record,boot_id=ledger['boot_id'],scan_id=scan_id,
        maximum_pair_us=policy['maximum_pair_us'],maximum_scan_us=policy['maximum_scan_us'])
    if result['status']!='BASELINE_CAPTURED':raise ValueError('Incomplete continuation scan')
    first=record['reads'][0][0][1];last=record['reads'][-1][1][2]
    if not ledger['finished_us']<first<=last<=boundary_us or boundary_us-first>policy['maximum_age_us']:
        raise ValueError('Continuation observation stale or predates predecessor')
    for observed,expected,window in zip(result['joints'],ledger['joints'],policy['joints']):
        if (observed['servo_id']!=expected['servo_id'] or observed['target']!=expected['goal'] or
                observed['moving']!=0 or not window[0]<=observed['position']<=window[1] or
                abs(observed['position']-expected['position'])>policy['drift_tolerance']):
            raise ValueError('Continuation goal/position differs from verified ledger')
    return dict(schema='rocell.mixed_goal_scan_assessment.v1',status='OBSERVATION_MATCHES_LEDGER',
        predecessor_sha256=ledger['predecessor_sha256'],joints=result['joints'],
        oldest_age_us=boundary_us-first,progression_authority=False,
        control_state_verified=False,two_scan_stability_verified=False,physical_accuracy_verified=False)


def assess_mixed_goal_observation(root, started_export_id, first, second, control,
                                  *, scan_id, boundary_us):
    """Offline pre-leg continuity review, not a signed/native movement admission.

    The first scan is a stability anchor. The second scan and control reads must
    be fresh at the proposed boundary; the anchor's permitted age is instead
    bounded by the explicit inter-scan wait policy, as in startup commissioning.
    """
    ledger = decode_diagnostic_json(load_startup_ledger(root, started_export_id).encoded,
                                   maximum=4096)
    policy = ledger['policy']
    # Validate compact row shape before extracting any timestamps.
    anchor = assess_baseline_only(first, boot_id=ledger['boot_id'], scan_id=scan_id,
        maximum_pair_us=policy['maximum_pair_us'], maximum_scan_us=policy['maximum_scan_us'])
    if anchor['status'] != 'BASELINE_CAPTURED':
        raise ValueError('Incomplete continuation stability anchor')
    first_end = first['reads'][-1][1][2]
    a = _assess_scan(ledger, first, scan_id=scan_id, boundary_us=first_end)
    b = _assess_scan(ledger, second, scan_id=scan_id, boundary_us=boundary_us)
    second_start = second['reads'][0][0][1]
    second_end = second['reads'][-1][1][2]
    if not policy['minimum_separation_us'] <= second_start-first_end <= policy['maximum_wait_us']:
        raise ValueError('Continuation scan separation invalid')
    if any(abs(x['position']-y['position']) > policy['drift_tolerance']
           for x, y in zip(a['joints'], b['joints'])):
        raise ValueError('Continuation scan-to-scan drift')
    control_result = assess_control_state(control, boot_id=ledger['boot_id'], command_id=scan_id,
        reviewed_mode=policy['reviewed_mode'], after_us=second_end,
        boundary_us=boundary_us, maximum_age_us=policy['maximum_age_us'])
    return dict(schema='rocell.mixed_goal_observation_assessment.v1',
        status='OBSERVATION_MATCHES_LEDGER', predecessor_sha256=ledger['predecessor_sha256'],
        first=a, second=b, control=control_result, control_state_verified=True,
        two_scan_stability_verified=True, progression_authority=False,
        provenance_verified=False, physical_accuracy_verified=False)
