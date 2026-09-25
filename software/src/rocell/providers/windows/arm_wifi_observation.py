"""35-second stationary feedback observation; never a movement admission."""
import base64
import hashlib
import json
import math
import threading
import time
from .arm_wifi_feedback import probe, unique_object
from rocell.arm.feedback import parse_feedback_1051, KNOWN_1051_FIELDS

PROFILES = {'rocell.arm_wifi_observation.v1':(.2,200),
            'rocell.arm_wifi_observation.v2':(.1,400),
            'rocell.arm_wifi_observation.v3':(.5,70),
            'rocell.arm_wifi_observation.v4':(.15,234)}

COOLDOWN_PROFILES = {'rocell.arm_wifi_observation.v3', 'rocell.arm_wifi_observation.v4'}


def review_observation(report):
    """Rebuild pose spans and timing from exact retained successful bodies."""
    if report.get('schema') not in PROFILES or not 0<len(report['samples'])<=PROFILES[report['schema']][1]:
        raise ValueError('Bounded observation required')
    poses=[];finishes=[];prior=None
    for sample in report['samples']:
        if sample['status']!='SUCCEEDED':
            if sample is not report['samples'][-1]:raise ValueError('Fault must end observation')
            continue
        raw=base64.b64decode(sample['response_base64'],validate=True)
        if len(raw)>2048 or len(raw)!=sample['response_bytes'] or hashlib.sha256(raw).hexdigest()!=sample['response_sha256']:
            raise ValueError('Response integrity mismatch')
        data=json.loads(raw,object_pairs_hook=unique_object)
        if not set(data)<=KNOWN_1051_FIELDS or not all(type(v) in (int,float) and math.isfinite(v) for v in data.values()):
            raise ValueError('Numeric feedback only')
        parse_feedback_1051(data)
        pose={k:data[k] for k in ('b','s','e','t','r','g')}
        if pose!=sample['joints_rad']:raise ValueError('Derived pose mismatch')
        start,end=sample['request_started_monotonic_s'],sample['response_finished_monotonic_s']
        if not all(type(v) in (int,float) and math.isfinite(v) for v in (start,end)) or start>end or (prior is not None and start<prior):
            raise ValueError('Invalid request ordering')
        prior=end;finishes.append(end);poses.append(pose)
    gaps=[(b-a)*1000 for a,b in zip(finishes,finishes[1:])]
    return dict(valid=True,successful_originals=len(poses),
        response_span_s=finishes[-1]-finishes[0] if finishes else None,
        maximum_response_gap_ms=max(gaps) if gaps else None,
        response_gaps_over_250ms=sum(gap>250 for gap in gaps),
        reported_joint_span_rad={k:max(p[k] for p in poses)-min(p[k] for p in poses)
            for k in poses[0]} if poses else None,
        physical_accuracy_verified=False,freshness_verified=False,movement_ready=False)


def observe(*, cancelled=lambda:False, run_probe=None, clock=time.perf_counter, wait=None):
    return _observe('rocell.arm_wifi_observation.v1',cancelled=cancelled,
        run_probe=run_probe,clock=clock,wait=wait)


def observe_fast(*, cancelled=lambda:False, run_probe=None, clock=time.perf_counter, wait=None):
    """Separate 10-Hz ceiling; v1 evidence and five-Hz behavior are unchanged."""
    return _observe('rocell.arm_wifi_observation.v2',cancelled=cancelled,
        run_probe=run_probe,clock=clock,wait=wait)


def observe_spaced(*, cancelled=lambda:False, run_probe=None, clock=time.perf_counter, wait=None):
    """Diagnostic cooldown after each completed request, not a retry policy."""
    return _observe('rocell.arm_wifi_observation.v3',cancelled=cancelled,
        run_probe=run_probe,clock=clock,wait=wait)


def observe_intermediate(*, cancelled=lambda:False, run_probe=None, clock=time.perf_counter, wait=None):
    """Separate 150-ms completion cooldown; preserves previous controls unchanged."""
    return _observe('rocell.arm_wifi_observation.v4',cancelled=cancelled,
        run_probe=run_probe,clock=clock,wait=wait)


def _observe(schema, *, cancelled, run_probe, clock, wait):
    period,maximum=PROFILES[schema]
    run_probe=probe if run_probe is None else run_probe
    wait=threading.Event().wait if wait is None else wait
    started=clock();samples=[];stop='DURATION_REACHED';retained_bytes=0
    while clock()-started<35-1e-9:
        if cancelled():stop='CANCELLED';break
        if len(samples)>=maximum:stop='SAMPLE_LIMIT';break
        began=clock()
        sample=run_probe(cancelled=cancelled,retain_response=True)
        samples.append(sample)
        retained_bytes+=len(json.dumps(sample,separators=(',',':')).encode())
        if sample['status']!='SUCCEEDED':
            stop='CANCELLED' if sample.get('reason')=='CANCELLED' else 'FIRST_FAULT'
            break
        if schema=='rocell.arm_wifi_observation.v2' and retained_bytes>=512000:
            stop='RETENTION_BUDGET';break
        # Profile-limited request starts; never a backlog or catch-up burst.
        # Cooldown profiles wait after completion, even for slow reads.
        remaining=max(0,35-(clock()-started))
        delay=min(period if schema in COOLDOWN_PROFILES else
                  max(0,period-(clock()-began)),remaining)
        if delay:wait(delay)
    report=dict(schema=schema,samples=samples,
        status='SUCCEEDED' if stop=='DURATION_REACHED' and samples else 'FAILED',
        stop_reason=stop,elapsed_s=clock()-started,maximum_samples=maximum,
        request_attempts=sum(s['request_attempts'] for s in samples),
        motion_commands=0,serial_ports_opened=0,physical_authority=False,motion_authorized=False,
        exclusive_scope='PARTICIPATING_WIZARD_WIFI_AND_POSITIONAL_CAMPAIGNS_ONLY')
    if schema in COOLDOWN_PROFILES:
        report['post_completion_quiet_s']=period
        report['cadence_basis']='COMPLETION_PLUS_QUIET_PERIOD'
    if samples:
        report['reconstruction']=review_observation(report)
        from rocell.arm.discrete_endpoint import assess_stationary_timing
        report['discrete_timing_assessment']=assess_stationary_timing(report)
    return report
