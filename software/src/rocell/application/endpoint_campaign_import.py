"""Read fixed-name endpoint exports for descriptive offline campaign analysis.

Consistency checks do not authenticate the filesystem or prove a physical move.
No retained record is turned into a fresh approval, device open or retry.
"""

import base64
import hashlib
from pathlib import Path
import re

from rocell.motion.characterization_plan import FrozenCampaign, freeze_campaign
from rocell.providers.windows.endpoint_native_wire import decode_request
from rocell.providers.windows.endpoint_native_registration import validate_payload
from rocell.providers.windows.endpoint_native_result import decode_result, validate_result, MAX_RESULT_BYTES
from .physical_onboarding_durability import safe_root, contained_path, read_bounded_regular_file
from .wizard_diagnostic_coordinator import decode_diagnostic_json


def summarize_saved_endpoint_campaign(root, plan, attempt_ids, *, minimum_repetitions=3, check_current=None):
    """Explicit bounded selection, never a directory sweep or best-run filter."""
    from rocell.arm.movement_campaign_analysis import summarize_endpoint_campaign
    if (type(attempt_ids) is not list or len(attempt_ids)>128
            or any(type(item) is not str for item in attempt_ids)
            or len(set(attempt_ids))!=len(attempt_ids)):
        raise ValueError('At most 128 distinct selected attempt IDs required')
    if check_current is not None and not callable(check_current):
        raise ValueError('Current-work check must be callable')
    def check():
        if check_current is not None and check_current() is not None:
            raise ValueError('Current-work check refused')
    check()
    rows = []
    for attempt in attempt_ids:
        check()
        rows.append(load_endpoint_observation(root,attempt,plan))
    check()
    report = summarize_endpoint_campaign(plan,rows,minimum_repetitions=minimum_repetitions)
    check()
    report['selected_attempt_ids'] = list(attempt_ids)
    report['limitations'].append('Offline export consistency does not reauthenticate the original parent process or establish current approval; filesystem modification remains possible.')
    return report


def parse_campaign_review_input(values):
    """Semantic UI fields only: canonical planner data and explicit IDs."""
    plan_text, selected = values['plan_json'], values['attempt_ids']
    if (type(plan_text) is not str or len(plan_text.encode('utf-8'))>16384
            or type(selected) is not str or len(selected)>6000):
        raise ValueError('Saved campaign review input exceeds bounds')
    plan = freeze_campaign(decode_diagnostic_json(plan_text.encode('utf-8'),maximum=16384))
    attempts = selected.split()
    if (not 1<=len(attempts)<=128 or len(set(attempts))!=len(attempts)
            or any(re.fullmatch(r'operation-[a-f0-9]{32}',item) is None for item in attempts)):
        raise ValueError('Select 1–128 distinct operation IDs, separated by whitespace')
    return plan, attempts


def load_endpoint_observation(root, attempt_id, plan):
    """Load one original request, report and both streams; preserve failed trials.

    All names are derived from the exact operation ID, never report-supplied
    paths. Native result validation reconstructs capture analysis and checks its
    association before any eligible comparison row can be produced.
    """
    if (type(plan) is not FrozenCampaign or type(attempt_id) is not str
            or re.fullmatch(r'operation-[a-f0-9]{32}',attempt_id) is None):
        raise ValueError('Exact campaign and operation ID required')
    root = safe_root(Path(root))
    prefix = attempt_id+'-endpoint-'
    def read(name, maximum):
        return read_bounded_regular_file(contained_path(root,prefix+name,
            label='retained endpoint original'),maximum_bytes=maximum)
    report = decode_diagnostic_json(read('report.json',MAX_RESULT_BYTES),maximum=MAX_RESULT_BYTES)
    if (type(report) is not dict or report.get('schema')!='rocell.endpoint_retained_result.v1'
            or report.get('status') not in {'RESULT_RETAINED','RESULT_REJECTED','PROCESS_COMPLETION_UNCONFIRMED'}
            or report.get('physical_movement_verified') is not False
            or report.get('physical_stop_verified') is not False or report.get('replay_allowed') is not False
            or type(report.get('originals')) is not dict
            or set(report['originals'])!={'request.json','stdout.bin','stderr.bin'}):
        raise ValueError('Retained endpoint report required')
    streams = {}
    for name, maximum in (('request.json',65536),('stdout.bin',MAX_RESULT_BYTES),('stderr.bin',8192)):
        wrapped = decode_diagnostic_json(read(name+'.original.json',2*MAX_RESULT_BYTES),maximum=2*MAX_RESULT_BYTES)
        if (type(wrapped) is not dict or set(wrapped)!={'bytes','base64'}
                or type(wrapped['base64']) is not str or len(wrapped['base64'])>4*((maximum+2)//3)
                or type(wrapped['bytes']) is not int):
            raise ValueError('Bounded stream wrapper required')
        raw = base64.b64decode(wrapped['base64'],validate=True)
        expected = {'file':prefix+name+'.original.json','bytes':len(raw),
                    'sha256':hashlib.sha256(raw).hexdigest()}
        if len(raw)>maximum or wrapped['bytes']!=len(raw) or report['originals'][name]!=expected:
            raise ValueError('Retained stream digest, length or fixed filename mismatch')
        streams[name]=raw
    wire = decode_request(streams['request.json'])
    request = validate_payload(wire['payload'])
    body = request.to_dict()
    if (body['attempt_id']!=attempt_id or report.get('request_sha256')!=request.request_sha256
            or freeze_campaign(body['campaign']).canonical_bytes!=plan.canonical_bytes):
        raise ValueError('Retained request belongs to a different attempt or campaign')
    row = {'trial_id':body['trial_id'],'outcome':report['status'],'evidence':None}
    # A failed/undecodable original is still a campaign failure, not a zero error
    # endpoint. Do not opportunistically rescue bytes rejected by publication.
    if report['status']=='RESULT_REJECTED':
        return row
    value = decode_result(streams['stdout.bin'],wire=wire)
    summary = validate_result(value,wire=wire)
    if summary!=report.get('summary'):
        raise ValueError('Retained summary differs from reconstructed native result')
    execution = value['child_result']['execution']
    trial = execution.get('trial')
    if trial is None or trial.get('post') is None:
        return row
    post = trial['post']
    raw = b''.join(base64.b64decode(c,validate=True) for c in post['raw']['base64_chunks'])
    clean = (report['status']=='RESULT_RETAINED' and report.get('returncode')==0
             and type(report.get('returncode')) is int and report.get('process_tree_closed') is True
             and report.get('errors')==[] and summary['endpoint_observed'])
    row['outcome'] = 'OBSERVATION_COMPLETED' if clean else execution['status']
    # Cleanup/parent completion uncertainty cannot be erased by a good endpoint.
    if not clean and row['outcome']=='OBSERVED_ENDPOINT_DWELL':
        row['outcome']=report['status']
    row['evidence'] = {'basis':'RETAINED_PHYSICAL_CAPTURE','physical_authority':False,
        'observation_contract':'SUPERVISED_ENDPOINT_ONLY',
        'raw':{'base64':base64.b64encode(raw).decode('ascii'),'bytes':len(raw),
               'sha256':hashlib.sha256(raw).hexdigest()},
        'read_windows':post['read_windows'],'command_completed_ns':trial['write']['write_finished_ns'],
        'observation_end_ns':post['finished_ns']}
    return row
