"""Finite command/verify sequencer with no native adapter or hardware imports.

Simulated commands are logged separately from physical writes (always zero).
Absolute targets are fixed in the plan; fresh modeled baselines and predecessor
checks are required at every leg. Rehearsal evidence is not a native permit.
"""
import base64
import hashlib
import math

from rocell.application.first_motion_contract import canonical
from rocell.motion.positional_campaign import PositionalCampaign, compile_wrist_campaign
from rocell.arm.first_motion_analysis import _window
from rocell.arm.wrist_endpoint_verification import verify_reported_wrist, ReportedWristMonitor

FAULTS = ('NONE','DIRECTIONAL_OFFSET','NO_RESPONSE','OSCILLATION','DEPARTURE',
    'OTHER_JOINT','OVERSHOOT','MALFORMED','FEEDBACK_GAP','BATCHED_TIME',
    'BASELINE_DRIFT','CONTEXT_CHANGED','WRITE_UNCERTAIN','CANCELLED',
    'PERSISTENCE_FAILED','EXPIRED','REVERSED_DIRECTION','DELAYED_RESPONSE',
    'TIMESTAMP_REGRESSION','MISSING_JOINT','CPU_STALL','NO_SAMPLES')


def _capture(start, target, begin_ns, *, baseline=False, fault='NONE'):
    count = 20 if baseline else 100
    raw, windows = bytearray(), []
    for index in range(count):
        fraction = 0 if baseline else min(1., index/25)
        angle = start + (target-start)*fraction
        if not baseline:
            if fault == 'NO_RESPONSE': angle = start
            if fault == 'REVERSED_DIRECTION': angle = start-(target-start)*fraction
            # Arrival at the very end cannot establish the required quiet dwell.
            if fault == 'DELAYED_RESPONSE':
                angle = start+(target-start)*max(0., (index-95)/4)
            if fault == 'DIRECTIONAL_OFFSET':
                offset = math.radians(-.254 if target > start else .957)
                angle = start+(target+offset-start)*fraction
            if fault == 'OSCILLATION' and index >= 25: angle = target+math.radians(.2)*(-1)**index
            if fault == 'DEPARTURE' and index >= 90: angle = target+math.radians(.8)
            if fault == 'OVERSHOOT' and index == 40: angle = target+math.copysign(math.radians(1),target-start)
        fields = dict(T=1051,x=0,y=0,z=0,tit=0,b=0,s=0,e=0,t=angle,r=0,g=0)
        if fault == 'OTHER_JOINT' and index == 40: fields['e'] = .1
        if fault == 'MISSING_JOINT' and index == 40: del fields['e']
        line = canonical(fields)+b'\n'
        if fault == 'MALFORMED' and index == 40: line = b'bad\n'
        tick = begin_ns+index*50_000_000
        if fault == 'BATCHED_TIME': tick = begin_ns
        if fault == 'TIMESTAMP_REGRESSION' and index == 40: tick -= 100_000_000
        if fault == 'FEEDBACK_GAP' and 40 <= index < 50: continue
        if fault == 'NO_SAMPLES': continue
        finish = tick if fault == 'BATCHED_TIME' else tick+1
        # A blocked host read gives an uncertain interval, not precise sample time.
        if fault == 'CPU_STALL': tick, finish = begin_ns, begin_ns+count*50_000_000
        windows.append([len(raw),len(raw)+len(line),tick,finish])
        raw.extend(line)
    original = bytes(raw)
    return dict(raw_base64=base64.b64encode(original).decode(),
        raw_sha256=hashlib.sha256(original).hexdigest(),read_windows=windows,
        started_ns=begin_ns,finished_ns=begin_ns+count*50_000_000)


def _decode(capture):
    raw = base64.b64decode(capture['raw_base64'],validate=True)
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != capture['raw_sha256']:
        raise ValueError('Capture digest or byte budget changed')
    try:
        return _window(raw,capture['read_windows'],capture['started_ns'],capture['finished_ns'])
    except ValueError:
        # Retain the invalid original and fail the leg, rather than dropping it
        # or inventing a position when read coverage itself cannot be decoded.
        return [], {'INVALID_CAPTURE'}, None


def simulate_positional_campaign(plan, *, fault='NONE', fault_leg=1, journal=None):
    if type(plan) is not PositionalCampaign or fault not in FAULTS:
        raise ValueError('Exact immutable simulation plan and closed fault required')
    body = plan.to_dict()
    if type(fault_leg) is not int or not 1 <= fault_leg <= len(body['legs']):
        raise ValueError('Fault must identify an enumerated leg')
    if journal is not None:
        from .positional_campaign_journal import PositionalCampaignJournal
        if type(journal) is not PositionalCampaignJournal or journal.plan != plan:
            raise ValueError('Exact matching rehearsal journal required')
    records, writes, reserved = [], [], set()
    angle, clock, previous_digest = body['start_rad'], 1_000_000_000, plan.sha256
    status, total_raw = 'SIMULATION_COMPLETE', 0
    for index, leg in enumerate(body['legs'],1):
        active_fault = fault if index == fault_leg else 'NONE'
        record = dict(leg_id=leg['leg_id'],predecessor_sha256=previous_digest,
            transitions=['BASELINE'],baseline=None,post=None,endpoint=None,
            command=None,status='HELD',reason=None,physical_write_count=0,
            incremental_progress=[],incremental_matches_final=None)
        if active_fault in ('CANCELLED','CONTEXT_CHANGED','EXPIRED'):
            record['reason'] = active_fault
        else:
            actual_start = angle + (.1 if active_fault == 'BASELINE_DRIFT' else 0)
            baseline = record['baseline'] = _capture(actual_start,actual_start,clock,baseline=True)
            before, issues, _ = _decode(baseline)
            clock = baseline['finished_ns']
            if (issues or abs(actual_start-leg['expected_start_rad']) > math.radians(.5)
                    or abs(leg['target_rad']-actual_start) > math.radians(5)
                    or abs(actual_start) > math.radians(10)):
                record['reason'] = 'BASELINE_OR_START_BOUND'
            else:
                # Reservation is modeled here, not a durable native permit.
                if leg['leg_id'] in reserved: raise ValueError('Leg replay')
                if journal is not None:
                    journal.reserve(leg['leg_id'],baseline,previous_digest)
                reserved.add(leg['leg_id'])
                record['transitions'].append('COMMAND_RESERVED')
                record['command'] = dict(leg['command'])
                writes.append(dict(leg_id=leg['leg_id'],command=dict(leg['command'])))
                record['transitions'].append('OBSERVING')
                post = record['post'] = _capture(actual_start,leg['target_rad'],clock,fault=active_fault)
                after, issues, _ = _decode(post)
                clock = post['finished_ns']
                monitor = ReportedWristMonitor(start=before[-1][2],target=leg['target_rad'])
                for row in after:
                    monitor.push(row)
                    snapshot = monitor.snapshot()
                    progress = ('REPORTED_SETTLED' if snapshot['endpoint_verified'] else
                        'SETTLING' if snapshot['final_in_target_band'] else
                        'MOVEMENT_DETECTED' if snapshot['movement_detected'] else 'AWAITING_RESPONSE')
                    if not record['incremental_progress'] or record['incremental_progress'][-1]['state'] != progress:
                        record['incremental_progress'].append(dict(state=progress,host_bounds_ns=list(row[:2])))
                endpoint = record['endpoint'] = verify_reported_wrist(after,
                    start=before[-1][2],target=leg['target_rad'],capture_issues=issues,
                    transport_clean=active_fault != 'WRITE_UNCERTAIN')
                record['incremental_matches_final'] = monitor.snapshot(capture_issues=issues,
                    transport_clean=active_fault != 'WRITE_UNCERTAIN') == endpoint
                if not record['incremental_matches_final']:
                    raise ValueError('Incremental/final verification disagreement')
                record['transitions'].append('VERIFYING')
                if endpoint['endpoint_verified'] and active_fault != 'PERSISTENCE_FAILED':
                    record['status'] = 'LEG_VERIFIED'
                    record['transitions'].append('LEG_COMMITTED')
                    if journal is not None:
                        # Exceptions abort the run before a subsequent command.
                        journal.commit(record)
                    angle = after[-1][2][3]
                else:
                    record['reason'] = 'PERSISTENCE_FAILED' if active_fault == 'PERSISTENCE_FAILED' else endpoint['status']
        for phase in ('baseline','post'):
            if record[phase]: total_raw += len(base64.b64decode(record[phase]['raw_base64']))
        if total_raw > body['limits']['maximum_total_raw_bytes'] or clock > 65_000_000_000:
            raise ValueError('Aggregate simulation budget exceeded')
        previous_digest = hashlib.sha256(canonical(record)).hexdigest()
        records.append(dict(record,record_sha256=previous_digest))
        if record['status'] != 'LEG_VERIFIED':
            if journal is not None:
                journal.hold()
            status = 'SIMULATION_HELD'
            break  # No corrections, retries, implicit return or later writes.
    return dict(schema='rocell.positional_campaign_rehearsal.v1',basis='SYNTHETIC_WIRE_REHEARSAL',
        plan=body,plan_sha256=plan.sha256,fault=fault,fault_leg=fault_leg,status=status,
        legs=records,simulated_commands=writes,simulated_write_count=len(writes),
        skipped_leg_ids=[leg['leg_id'] for leg in body['legs'][len(records):]],
        total_raw_bytes=total_raw,modeled_duration_ns=clock-1_000_000_000,
        device_open_count=0,physical_write_count=0,physical_authority=False,
        native_execution_available=False,unattended_release=False,
        limitations=['Modeled motion timing is not derived from native speed.',
            'Reservations and commits are simulated, not durable live admission.',
            'No hardware backend, automatic recovery, or physical qualification.'])


def verify_rehearsal_report(report):
    """Reproduce the closed deterministic experiment; reject changed originals."""
    if type(report) is not dict: raise ValueError('Rehearsal report required')
    rebuilt = simulate_positional_campaign(PositionalCampaign(canonical(report['plan'])),
        fault=report['fault'],fault_leg=report['fault_leg'])
    if canonical(rebuilt) != canonical(report):
        raise ValueError('Rehearsal originals or result changed')
    return dict(valid=True,physical_authority=False)


def run_wizard_rehearsal(values):
    plan = compile_wrist_campaign(values['pattern'],int(values['leg_count']))
    return simulate_positional_campaign(plan,fault=values['fault'],fault_leg=int(values['fault_leg']))


def run_persisted_wizard_rehearsal(workspace, values):
    """Use a private, non-resumable run directory; include originals in exports."""
    from uuid import uuid4
    from .physical_onboarding_durability import safe_root, contained_path
    from .positional_campaign_journal import PositionalCampaignJournal, export_campaign_journal
    runs = safe_root(workspace/'software'/'runs')
    parent = contained_path(runs,'positional-campaign-journals',label='rehearsal journals')
    parent.mkdir(exist_ok=True)
    directory = contained_path(safe_root(parent),'campaign-'+uuid4().hex,label='rehearsal run')
    directory.mkdir()
    plan = compile_wrist_campaign(values['pattern'],int(values['leg_count']))
    journal = PositionalCampaignJournal(directory,plan)
    report = simulate_positional_campaign(plan,fault=values['fault'],fault_leg=int(values['fault_leg']),journal=journal)
    retained = export_campaign_journal(directory,report)
    retained['path'] = str(directory)
    return report,retained
