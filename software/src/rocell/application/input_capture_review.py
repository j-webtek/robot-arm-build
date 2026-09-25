"""Evaluate an explicitly collected test-pad transcript, never robot telemetry.

Browser isTrusted is reported provenance, not authentication or robot identity.
This action imports no input hook, browser driver, camera or arm provider.
"""
import re
from .wizard_diagnostic_coordinator import decode_diagnostic_json


def review_input_capture(text):
    if type(text) is not str:
        raise ValueError('Capture JSON required')
    data=decode_diagnostic_json(text.encode(),maximum=12000)
    if (type(data) is not dict or set(data)!= {'schema','capture_id','expected','stop_reason','events'}
            or data['schema']!='rocell.input_capture.v1'
            or type(data['capture_id']) is not str
            or re.fullmatch(r'[a-f0-9-]{36}',data['capture_id']) is None
            or type(data['expected']) is not str
            or re.fullmatch(r'[a-z]{1,8}',data['expected']) is None
            or data['stop_reason'] not in ('STOPPED','BLUR','TIME_LIMIT','EVENT_LIMIT','UNSUPPORTED_INPUT')
            or type(data['events']) is not list or len(data['events'])>64):
        raise ValueError('Bounded test-pad capture required')
    held=set(); presses=[]; chars=[]; issues=[]; previous=0
    for event in data['events']:
        if (type(event) is not dict or set(event)!= {'kind','key','at_ms','repeat','trusted'}
                or event['kind'] not in ('down','up','text')
                or type(event['key']) is not str or re.fullmatch(r'[a-z]',event['key']) is None
                or type(event['at_ms']) is not int or not previous<=event['at_ms']<=60000
                or type(event['repeat']) is not bool or type(event['trusted']) is not bool):
            raise ValueError('Invalid input-event record')
        previous=event['at_ms']
        key=event['key']
        if not event['trusted']:issues.append('SCRIPTED_OR_UNTRUSTED_EVENT')
        if event['repeat']:issues.append('REPEAT_EVENT')
        if event['kind']=='down':
            if key in held:issues.append('DUPLICATE_KEY_DOWN')
            elif held:issues.append('OVERLAPPING_PRESSES')
            held.add(key);presses.append(key)
        elif event['kind']=='up':
            if key not in held:issues.append('UNPAIRED_RELEASE')
            held.discard(key)
        else:
            if key not in held:issues.append('TEXT_WITHOUT_MATCHING_KEY_DOWN')
            chars.append(key)
    if held:issues.append('MISSING_KEY_RELEASE')
    if data['stop_reason']!='STOPPED':issues.append('CAPTURE_INTERRUPTED')
    actual=''.join(chars)
    if actual!=data['expected']:
        issues.append('MISSING_INPUT' if len(actual)<len(data['expected']) else
                      'EXTRA_INPUT' if len(actual)>len(data['expected']) else 'WRONG_INPUT')
    if ''.join(presses)!=data['expected']:issues.append('KEY_SEQUENCE_MISMATCH')
    return dict(schema='rocell.input_capture_review.v1',status='INPUT_MATCH_OBSERVED' if not issues else 'INPUT_NOT_VERIFIED',
        capture_id=data['capture_id'],expected=data['expected'],observed_text=actual,
        event_count=len(data['events']),press_count=len(presses),issues=sorted(set(issues)),
        stop_reason=data['stop_reason'],capture=data,basis='SUPPLIED_BROWSER_TEST_PAD_TRANSCRIPT',
        browser_provenance_authenticated=False,robot_press_confirmed=False,
        physical_accuracy_verified=False,motion_authorized=False,hardware_access=False,
        limitations=['Only focused test-pad input is represented; not global keyboard monitoring.',
                     'Browser events do not identify whether a person or robot caused the input.',
                     'No command-to-event timing correlation or Android pairing is established.'])
