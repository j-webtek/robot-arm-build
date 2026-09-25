"""Pinned, read-only HTTP commissioning probe. No general command API.

ARP comparison is a local consistency check, not device authentication. A single
HTTP response never qualifies freshness, motion admission or spatial accuracy.
"""
import hashlib
import base64
import http.client
import json
import math
import time

from rocell.arm.feedback import parse_feedback_1051, KNOWN_1051_FIELDS

ADDRESS = '192.168.0.225'
MAC = 'FC-E8-C0-F8-D5-38'
PATH = '/js?json=%7B%22T%22%3A105%7D'
LIMIT = 16384


def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate feedback field')
        result[key]=value
    return result


def neighbor_mac():
    from .ipv4_neighbor import lookup_neighbor
    return lookup_neighbor(ADDRESS)


def probe(*, cancelled=lambda: False, identity=neighbor_mac,
          connection_factory=http.client.HTTPConnection, clock=time.perf_counter,
          retain_response=False):
    """One GET only; no proxies, redirects, retry, configuration or movement.

    Socket inactivity timeout is two seconds. Body reads also check a five-second
    elapsed budget. This is not hard process containment for hostile slow headers.
    Unknown response fields are never exported (they could contain credentials).
    """
    report = dict(schema='rocell.arm_wifi_feedback.v1', address=ADDRESS,
        expected_mac=MAC, status='FAILED', request_attempts=0, motion_commands=0,
        identity_method='WINDOWS_GETIPNETTABLE_BEFORE_AND_AFTER',
        timing_clock='HOST_PERF_COUNTER',
        request_type=105, physical_authority=False, motion_authorized=False,
        freshness_verified=False, physical_accuracy_verified=False,
        serial_ports_opened=0, http_connections_created=0, cleanup_confirmed=False)
    connection = None
    phase = 'IDENTITY_BEFORE'
    started = clock()
    try:
        if cancelled():
            raise ValueError('CANCELLED')
        if identity() != MAC:
            raise ValueError('IDENTITY_NOT_MATCHED')
        report['identity_before_matched'] = True
        if cancelled():
            raise ValueError('CANCELLED')
        phase = 'CONNECTION_CREATE'
        connection = connection_factory(ADDRESS, timeout=2)
        report['http_connections_created'] = 1
        report['request_attempts'] = 1
        http_started = clock()
        report['request_started_monotonic_s'] = http_started
        phase = 'REQUEST_SEND'
        connection.request('GET', PATH, headers={'Cache-Control':'no-cache','Connection':'close'})
        phase = 'RESPONSE_HEADERS'
        response = connection.getresponse()
        report['http_status'] = response.status
        if response.status != 200:
            raise ValueError('HTTP_STATUS_NOT_200')
        phase = 'RESPONSE_BODY'
        raw = bytearray()
        for _ in range(LIMIT + 1):
            if cancelled():
                raise ValueError('CANCELLED')
            if clock()-http_started > 5:
                raise ValueError('BODY_TIME_BUDGET_EXCEEDED')
            chunk = response.read1(min(4096, LIMIT+1-len(raw)))
            raw.extend(chunk)
            if len(raw) > LIMIT:
                raise ValueError('RESPONSE_TOO_LARGE')
            if not chunk:
                break
        http_finished = clock()
        report['response_finished_monotonic_s'] = http_finished
        report['http_elapsed_ms'] = round((http_finished-http_started)*1000, 3)
        phase = 'FEEDBACK_PARSE'
        data = json.loads(raw,object_pairs_hook=unique_object)
        if type(data) is not dict:
            raise ValueError('INVALID_FEEDBACK')
        parsed = parse_feedback_1051(data)
        keys = ('b','s','e','t','r','g')
        if not all(type(data.get(k)) in (int,float) and math.isfinite(data[k]) for k in keys):
            raise ValueError('INVALID_FEEDBACK')
        if retain_response and (len(raw)>2048 or not set(data)<=KNOWN_1051_FIELDS or
                not all(type(v) in (int,float) and math.isfinite(v) for v in data.values())):
            raise ValueError('RAW_RETENTION_SCHEMA_REJECTED')
        phase = 'IDENTITY_AFTER'
        if identity() != MAC:
            raise ValueError('IDENTITY_CHANGED')
        if cancelled():
            raise ValueError('CANCELLED')
        report.update(status='SUCCEEDED', identity_after_matched=True,
            response_bytes=len(raw), response_sha256=hashlib.sha256(raw).hexdigest(),
            joints_rad={k:data[k] for k in keys})
        # Do not manufacture Cartesian coordinates from joint feedback or fill
        # absent fields with zero. Installed firmware may omit this entire set.
        cartesian_keys = ('x','y','z','tit')
        missing = [key for key in cartesian_keys if key not in data]
        report['controller_cartesian'] = dict(
            status='REPORTED_COMPLETE' if not missing else 'NOT_REPORTED' if len(missing)==4 else 'REPORTED_PARTIAL',
            frame='R_ctrl', position_units='mm', pitch_units='rad',
            values={key:data.get(key) for key in cartesian_keys}, missing_fields=missing,
            controller_model_correlation_verified=False, physical_accuracy_verified=False)
        # Optional firmware fields: absence is unknown, never torque OFF or 0 V.
        joint_names=('base','shoulder','elbow','wrist_pitch','wrist_roll','gripper')
        report['servo_status']=dict(
            torque_switches={k:parsed.torque_switches.get(k) for k in joint_names},
            missing_torque_switches=[k for k in joint_names if k not in parsed.torque_switches],
            loads_raw={k:parsed.loads_raw.get(k) for k in joint_names},
            voltage_v=parsed.voltage_v,reported_only=True,
            actuator_health_verified=False,loads_are_calibrated_force=False)
        if retain_response:
            report['response_base64']=base64.b64encode(raw).decode('ascii')
    except Exception as error:
        # Never retain exception text or raw response: both can contain secrets.
        allowed={'CANCELLED','IDENTITY_NOT_MATCHED','IDENTITY_CHANGED','HTTP_STATUS_NOT_200',
                 'BODY_TIME_BUDGET_EXCEEDED','RESPONSE_TOO_LARGE','INVALID_FEEDBACK','RAW_RETENTION_SCHEMA_REJECTED'}
        reason=str(error) if type(error) is ValueError and str(error) in allowed else 'REQUEST_OR_FEEDBACK_FAILED'
        # Fixed categories only: exception messages/args may contain response data.
        categories=((TimeoutError,'TIMEOUT'),(http.client.RemoteDisconnected,'REMOTE_DISCONNECTED'),
            (ConnectionResetError,'CONNECTION_RESET'),(ConnectionRefusedError,'CONNECTION_REFUSED'),
            (http.client.IncompleteRead,'INCOMPLETE_READ'),(http.client.BadStatusLine,'BAD_STATUS_LINE'),
            (json.JSONDecodeError,'JSON_INVALID'),(UnicodeError,'ENCODING_INVALID'),
            (OSError,'OS_ERROR'),(ValueError,'VALIDATION_FAILED'))
        category=next((label for cls,label in categories if isinstance(error,cls)),'UNCLASSIFIED')
        report.update(status='FAILED', reason=reason,failure_phase=phase,error_category=category)
        for attr in ('errno','winerror'):
            code=getattr(error,attr,None)
            if type(code) is int:report[attr]=code
    finally:
        if connection is not None:
            try:
                connection.close()
                report['cleanup_confirmed'] = True
            except Exception:
                report.update(status='FAILED', reason='CLEANUP_FAILED')
        else:
            report['cleanup_confirmed'] = True
        report['elapsed_ms'] = round((clock()-started)*1000, 3)
    return report


def sample_feedback(*, cancelled=lambda: False, run_probe=None, clock=time.perf_counter):
    """Eight sequential observations, stopping on the first fault; not a stream.

    Each sample retains both MAC checks. No catch-up requests, automatic retries
    or inference that unchanged joint values establish device freshness.
    The 30-second budget is checked between probes, not hard process containment.
    """
    run_probe = probe if run_probe is None else run_probe
    started = clock()
    samples = []
    stop = 'COMPLETED'
    for index in range(8):
        if cancelled():
            stop = 'CANCELLED'
            break
        if clock()-started >= 30:
            stop = 'SESSION_BUDGET_EXCEEDED'
            break
        sample = run_probe(cancelled=cancelled)
        samples.append(dict(sample_index=index, **sample))
        if sample['status'] != 'SUCCEEDED':
            stop = 'FIRST_FAULT'
            break
    successful = [s for s in samples if s['status']=='SUCCEEDED']
    times = [s['http_elapsed_ms'] for s in successful]
    gaps = [(b['response_finished_monotonic_s']-a['response_finished_monotonic_s'])*1000
            for a,b in zip(successful,successful[1:])]
    keys = ('b','s','e','t','r','g')
    return dict(schema='rocell.arm_wifi_sampling.v1', status='SUCCEEDED' if stop=='COMPLETED' else 'FAILED',
        stop_reason=stop, maximum_samples=8, sample_count=len(samples),
        successful_samples=len(successful), failed_samples=len(samples)-len(successful),
        request_attempts=sum(s['request_attempts'] for s in samples), samples=samples,
        http_timing_ms=None if not times else dict(minimum=min(times),maximum=max(times),mean=sum(times)/len(times)),
        response_completion_gaps_ms=gaps,
        reported_joint_span_rad=None if not successful else {
            k:max(s['joints_rad'][k] for s in successful)-min(s['joints_rad'][k] for s in successful) for k in keys},
        elapsed_ms=round((clock()-started)*1000,3),
        cadence_basis='SEQUENTIAL_WITH_TWO_IDENTITY_LOOKUPS_PER_SAMPLE',
        movement_ready=False, freshness_verified=False, physical_accuracy_verified=False,
        motion_commands=0, serial_ports_opened=0, physical_authority=False, motion_authorized=False)
