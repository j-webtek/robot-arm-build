"""Run an enumerated bounded wrist or base experiment through the wizard.

Requires explicit operator setup confirmation. Uses a retained baseline only to
stage expected joint values; the native child must acquire and match a fresh
baseline before writing. Correction is applied only in explicitly selected,
evidence-rebuilt profiles; no automatic retry is applied.
"""
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import time

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.first_motion_contract import canonical
from rocell.arm.telemetry_coverage import complete_frame_interval, iter_window_records
from rocell.safety.positional_campaign_authority import BOUNDED_CHECKS
from rocell.safety.positional_campaign_authority import BASE_MIDPOINT_TARGETS


# Enumerated experiments, not an unrestricted angle input. The intent validator
# separately enforces the actual starting-pose delta and all motion limits.
TARGET_PROFILES = {'zero-then-four': (0,4), 'four-then-zero': (4,0),
                   'minus-four-then-zero': (-4,0), 'two-then-zero': (2,0),
                   'zero-then-two': (0,2), 'two-then-four': (2,4)}
BASE_PROFILES={'plus-one':1,'minus-one':-1,'plus-two':2,'minus-two':-2}
BASE_PROFILES.update(dict.fromkeys(BASE_MIDPOINT_TARGETS,0))


def correction_evidence(workspace):
    """Fixed frozen experiment, not arbitrary uploaded offsets or destinations.

    The score file selects originals only. Staging revalidates all six original
    exports and the frozen model before accepting any of their derived values.
    """
    import re
    expected='82a4f18803b4963d192b216149066951a7c277ef6c2e5aae2e398c7b6c4a7fc6'
    root=workspace/'software/runs'
    model=(root/'WRIST_ENDPOINT_MODEL_COMPARISON_20260914.json').read_bytes()
    score=json.loads((root/'TWO_DEGREE_REPETITION_SCORE_20260914.json').read_bytes())
    if score['frozen_model_sha256']!=expected or len(score['rows'])!=6:
        raise ValueError('Fixed prospective experiment selection differs')
    exports=[]
    for row in score['rows']:
        name=row['campaign_id']
        if type(name) is not str or not re.fullmatch('campaign-[a-f0-9]{32}',name):
            raise ValueError('Invalid prospective campaign reference')
        exports.append(dict(directory=str(root/'wizard-exports'/name),
            report_name=name+'-parent-report.json',report_sha256=row['report_sha256']))
    return dict(model_raw=model,expected_model_sha256=expected,exports=exports)


def retained_start(path):
    """Read historical planning values, preserving and disclosing framing issues.

    Do not modify the original or claim it is a clean/fresh execution baseline.
    The actual baseline gate is separate and remains enforced by the child.
    """
    original = path.read_bytes()
    if len(original) > 2_097_152:
        raise ValueError('Baseline original exceeds budget')
    outcome = json.loads(original)
    observation = json.loads(base64.b64decode(outcome['body']['stdout_base64'], validate=True))['child_result']['observation']
    if observation['status'] != 'CAPTURED_CLOSED' or observation['errors']:
        raise ValueError('Baseline capture did not close cleanly')
    blob = observation['capture']['raw']
    raw = base64.b64decode(blob['base64'], validate=True)
    if len(raw) != blob['bytes'] or hashlib.sha256(raw).hexdigest() != blob['sha256']:
        raise ValueError('Baseline byte integrity mismatch')
    data, windows, framing = complete_frame_interval(raw, observation['read_windows'])
    rows = list(iter_window_records(data, windows))
    bad = [r for r in rows if r['kind'] != 'POSE_TELEMETRY']
    # Only an explicitly disclosed initial mid-frame fragment is admissible for
    # planning. Interior corrupt lines are never discarded to manufacture data.
    if bad and (len(bad) != 1 or bad[0] is not rows[0] or bad[0]['end'] > 4096):
        raise ValueError('Interior invalid telemetry; no test prepared')
    poses = [r for r in rows if r['kind'] == 'POSE_TELEMETRY']
    keys = ('b','s','e','t','r','g')
    if len(poses) < 20:
        raise ValueError('Insufficient retained planning samples')
    values = [[r['fields'][key] for key in keys] for r in poses]
    if any(type(v) not in (int,float) or not math.isfinite(v) for row in values for v in row):
        raise ValueError('Invalid retained joint values')
    if any(max(row[i] for row in values)-min(row[i] for row in values) > math.radians(.1) for i in range(6)):
        raise ValueError('Retained starting joints were not stable')
    return values[-1], original, dict(pose_records=len(poses), initial_fragment_records=len(bad),
        framing=framing, historical_only=True, fresh_baseline_required=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator-confirmed', action='store_true')
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--controller-directory', type=Path, required=True)
    experiment=parser.add_mutually_exclusive_group()
    experiment.add_argument('--order', choices=tuple(TARGET_PROFILES), default='zero-then-four')
    experiment.add_argument('--model-correction',action='store_true',
        help='One frozen-model corrected +2 endpoint; no return or retry')
    experiment.add_argument('--single-target',choices=('two','four'),
        help='One ordinary +2 control or +4 positioning command; no second leg')
    experiment.add_argument('--base-probe',choices=tuple(BASE_PROFILES),
        help='One uncorrected enumerated base probe; whole arm sweep must be clear')
    experiment.add_argument('--base-experiment',choices=('corrected','control','decreasing-corrected','decreasing-control'),
        help='One frozen base endpoint (+1 degree increasing or +0.4 degree decreasing): inverse command or matched control')
    experiment.add_argument('--base-sequence',action='store_true',
        help='Four fixed compensated base legs in one connection; stop progression on any failed leg')
    experiment.add_argument('--base-speed',choices=('increasing','decreasing'),
        help='One fixed speed-10 base candidate; old speed-20 inverse is unvalidated here')
    experiment.add_argument('--roll-probe',choices=('increasing','decreasing'),
        help='One uncorrected one-degree wrist-roll probe; no return or retry')
    experiment.add_argument('--roll-fixed',choices=('increasing','decreasing'),
        help='One previously transmitted fixed roll target from its measured anchor')
    experiment.add_argument('--roll-persistence',choices=('increasing','decreasing'),
        help='One uncorrected roll degree, then 35 seconds on the same connection')
    experiment.add_argument('--roll-long-fixed',choices=('increasing','decreasing'),
        help='One frozen roll target from its measured anchor, with 35-second observation')
    experiment.add_argument('--roll-variation',choices=('low','nominal','high','return-low','return-nominal','return-high'),
        help='One v22 enumerated roll case, framed 35-second observation; no queued return')
    parser.add_argument('--synchronized-baseline',action='store_true',
        help='Opt in to v7 base-only retained startup synchronization')
    parser.add_argument('--cross-window-framing',action='store_true',
        help='Opt in to v21 framed telemetry; requires --roll-long-fixed')
    args = parser.parse_args()
    if args.cross_window_framing and not args.roll_long_fixed:
        parser.error('Cross-window framing requires --roll-long-fixed')
    if args.synchronized_baseline and not (args.base_probe or args.base_experiment or args.base_sequence or args.base_speed or args.roll_probe or args.roll_fixed or args.roll_persistence or args.roll_long_fixed):
        parser.error('Synchronized baseline requires the base probe')
    if args.base_probe and abs(BASE_PROFILES[args.base_probe])==2 and not args.synchronized_baseline:
        parser.error('Two-degree base probe requires --synchronized-baseline')
    if args.base_probe in BASE_MIDPOINT_TARGETS and not args.synchronized_baseline:
        parser.error('Midpoint probe requires --synchronized-baseline')
    if not args.operator_confirmed:
        parser.error('Present operator, clear full route, supplied power and USB confirmation required')
    start, baseline, details = retained_start(args.baseline)
    targets_deg = list(TARGET_PROFILES[args.order])
    if args.single_target:
        targets_deg=[2 if args.single_target=='two' else 4]
    if args.base_experiment:
        targets_deg=[.4 if args.base_experiment.startswith('decreasing-') else 1]
    if args.base_sequence:
        targets_deg=[1,.4,1,.4]
    if args.base_speed:
        targets_deg=[.4 if args.base_speed=='decreasing' else 1]
    if args.roll_probe:
        targets_deg=[math.degrees(start[4])+(1 if args.roll_probe=='increasing' else -1)]
    if args.roll_persistence:
        targets_deg=[math.degrees(start[4])+(1 if args.roll_persistence=='increasing' else -1)]
    if args.roll_fixed:
        from rocell.safety.positional_campaign_authority import roll_fixed_configuration
        targets_deg=[math.degrees(roll_fixed_configuration(args.roll_fixed.upper())['target_rad'])]
    if args.roll_long_fixed:
        from rocell.safety.positional_campaign_authority import roll_long_fixed_configuration
        targets_deg=[math.degrees(roll_long_fixed_configuration(args.roll_long_fixed.upper())['target_rad'])]
    if args.roll_variation:
        from rocell.safety.positional_campaign_authority import roll_variation_configuration
        targets_deg=[math.degrees(roll_variation_configuration(args.roll_variation)['target_rad'])]
    if args.base_probe:
        targets_deg=[math.degrees(start[0])+BASE_PROFILES[args.base_probe]]
        if args.base_probe in BASE_MIDPOINT_TARGETS:
            targets_deg=[math.degrees(BASE_MIDPOINT_TARGETS[args.base_probe])]
    workspace = Path(__file__).resolve().parents[2]
    controller = (args.controller_directory/'controller.original.json').read_bytes()
    protocol = (args.controller_directory/'protocol.original.json').read_bytes()
    identity = json.loads(controller)['identity']
    usb = dict(vid=int(identity['vid'],16), pid=int(identity['pid'],16), serial_number=identity['unit_serial'])
    if usb != dict(vid=0x10c4,pid=0xea60,serial_number='52E4E1E8337FEF119E92181CEDD322A4'):
        raise ValueError('Different arm; this bench test is not transferable')
    originals = dict(native_controller_review_sha256=controller, protocol_review_sha256=protocol,
        owned_baseline_sha256=canonical(json.loads(baseline)),
        configuration_sha256=canonical(dict(schema='rocell.attended_bench_configuration.v1',
            targets_deg=targets_deg, spd=20,acc=1,compensation_applied=False, planning_capture=details)),
        workcell_sha256=canonical(dict(schema='rocell.attended_bench_workcell.v1',
            basis='USER_REPORTED_CURRENT_SETUP', secured=True, entire_wrist_route_clear=True,
            board_mapping_used=False, measured_clearance=False)),
        tool_payload_sha256=canonical(dict(schema='rocell.attended_bench_tool.v1',
            basis='USER_REPORTED_UNCHANGED_AS_DELIVERED', added_payload=False, contact=False)),
        bounded_motion_risk_sha256=canonical(dict(schema='rocell.attended_bounded_motion_risk.v1',
            operator_present=True, entire_accepted_motion_clear=True, no_contact=True, no_added_payload=True,
            accepted_goal_may_finish=True, software_cancel_is_not_physical_stop=True)))
    service = ArrivalWizardService(workspace, mode='physical')
    if args.roll_probe or args.roll_fixed or args.roll_persistence or args.roll_long_fixed or args.roll_variation:
        originals['workcell_sha256']=canonical(dict(schema='rocell.roll_probe_workcell.v1',
            basis='USER_REPORTED_CURRENT_SETUP',secured=True,entire_wrist_roll_sweep_clear=True,
            board_mapping_used=False,measured_clearance=False))
    if args.base_probe or args.base_experiment or args.base_sequence or args.base_speed:
        originals['configuration_sha256']=canonical(dict(schema='rocell.base_probe_configuration.v1',
            selected_joint='b',targets_deg=targets_deg,spd=20,acc=1,
            compensation_applied=False,planning_capture=details))
        originals['workcell_sha256']=canonical(dict(schema='rocell.base_probe_workcell.v1',
            basis='USER_REPORTED_CURRENT_SETUP',secured=True,entire_arm_base_sweep_clear=True,
            board_mapping_used=False,measured_clearance=False))
    def action(name, **values):
        ticket = service.prepare_action(name, values, service.view()['revision'])
        if name == 'run_positional_campaign':
            print(json.dumps(dict(preview=ticket['effects'])), flush=True)
        receipt = service.execute_action(ticket['ticket_id'])
        deadline = time.monotonic()+65
        while time.monotonic() < deadline:
            operation = service.operation(receipt['operation_id'])
            if operation['status'] not in ('QUEUED','RUNNING'):
                summary = dict(action=name, operation_id=receipt['operation_id'],
                    status=operation['status'], error=operation.get('error'))
                if name == 'run_positional_campaign':
                    summary['result'] = operation.get('result')
                if name == 'export_logs':
                    summary['export'] = (operation.get('result') or {}).get('receipt',{}).get('path')
                print(json.dumps(summary), flush=True)
                if operation['status'] != 'SUCCEEDED':
                    raise RuntimeError(name+' did not succeed; no retry')
                return operation
            time.sleep(.1)
        raise RuntimeError('Wizard observation deadline exceeded; no retry')
    try:
        action('inventory_devices', metadata_only=True, power_disconnected=False)
        matches = [c for c in service.view()['device_selection']['devices']['SERIAL']['candidates']
            if (c['vid'],c['pid'],c['unit_serial'])==('10c4','ea60',usb['serial_number']) and not c['identity_blockers']]
        if len(matches)!=1: raise ValueError('Exact unique connected arm not found')
        action('review_arm_candidate', choice_id=matches[0]['choice_id'],reviewer_id='Codex',metadata_only=True)
        action('inspect_native_arm_metadata',metadata_only=True,power_disconnected=False)
        action('record_powered_arm_startup',operator_id='Jack',adapter_on=True,usb_connected=True,
            secured_and_clear=True,stationary=True,startup_motion='unknown')
        if args.roll_variation:
            preview=service.configure_roll_target_variation(usb_identity=usb,start_joints_rad=start,
                originals=originals,case_id=args.roll_variation)
        elif args.roll_long_fixed:
            preview=service.configure_roll_long_fixed_probe(usb_identity=usb,start_joints_rad=start,
                originals=originals,direction=args.roll_long_fixed.upper(),framed=args.cross_window_framing)
        elif args.roll_persistence:
            preview=service.configure_roll_persistence_probe(usb_identity=usb,start_joints_rad=start,
                originals=originals,direction=args.roll_persistence.upper())
        elif args.roll_fixed:
            preview=service.configure_roll_fixed_probe(usb_identity=usb,start_joints_rad=start,
                originals=originals,direction=args.roll_fixed.upper())
        elif args.roll_probe:
            preview=service.configure_roll_mapping_probe(usb_identity=usb,start_joints_rad=start,
                originals=originals,direction=args.roll_probe.upper())
        elif args.base_speed:
            from rocell.application.base_compensation_evidence import load_fixed_base_compensation_evidence
            preview=service.configure_base_speed_experiment(usb_identity=usb,start_joints_rad=start,
                originals=originals,direction=args.base_speed.upper(),
                **load_fixed_base_compensation_evidence(workspace))
        elif args.base_sequence:
            from rocell.application.base_compensation_evidence import load_fixed_base_compensation_evidence
            preview=service.configure_base_alternating_sequence(usb_identity=usb,start_joints_rad=start,
                originals=originals,**load_fixed_base_compensation_evidence(workspace))
        elif args.base_experiment:
            from rocell.application.base_compensation_evidence import load_fixed_base_compensation_evidence
            preview = service.configure_base_compensation_experiment(usb_identity=usb,start_joints_rad=start,
                originals=originals,experiment_kind='CORRECTED' if args.base_experiment in ('corrected','decreasing-corrected') else 'UNCORRECTED_CONTROL',
                direction='DECREASING' if args.base_experiment.startswith('decreasing-') else 'INCREASING',
                **load_fixed_base_compensation_evidence(workspace))
        elif args.base_probe in BASE_MIDPOINT_TARGETS:
            preview = service.configure_base_midpoint_probe(usb_identity=usb,start_joints_rad=start,
                target_name=args.base_probe,originals=originals)
        elif args.base_probe:
            preview = service.configure_base_mapping_probe(usb_identity=usb,start_joints_rad=start,
                delta_deg=BASE_PROFILES[args.base_probe],originals=originals,
                synchronize=args.synchronized_baseline)
        elif args.model_correction:
            preview = service.configure_model_corrected_campaign(usb_identity=usb,start_joints_rad=start,
                originals=originals,**correction_evidence(workspace))
        else:
            preview = service.configure_positional_campaign(usb_identity=usb,start_joints_rad=start,
                targets_rad=[math.radians(v) for v in targets_deg], originals=originals)
        print(json.dumps(dict(staged=preview)), flush=True)
        action('run_positional_campaign',operator_id='Jack',**dict.fromkeys(BOUNDED_CHECKS,True))
    finally:
        try: action('export_logs')
        finally: service.shutdown()


if __name__ == '__main__':
    main()
