"""Offline review of the benign phone target's transcript; no device access.

CSS pixels describe the captured viewport, not millimeters or board coordinates.
Supplied browser flags are evidence claims, not authenticated robot attribution.
"""
import math
import re
from .wizard_diagnostic_coordinator import decode_diagnostic_json


def review_tap_capture(text):
    if type(text) is not str:
        raise ValueError('Tap capture JSON required')
    data = decode_diagnostic_json(text.encode(), maximum=12000)
    def number(value, low, high):
        return type(value) in (int, float) and math.isfinite(value) and low <= value <= high
    if (type(data) is not dict or set(data) != {
            'schema','capture_id','expected_taps','viewport','target','stop_reason','events'}
            or data['schema'] != 'rocell.tap_capture.v1'
            or type(data['capture_id']) is not str
            or re.fullmatch(r'[a-f0-9-]{36}', data['capture_id']) is None
            or type(data['expected_taps']) is not int or not 1 <= data['expected_taps'] <= 8
            or data['stop_reason'] not in ('STOPPED','TIME_LIMIT','EVENT_LIMIT','INTERRUPTED')
            or type(data['events']) is not list or len(data['events']) > 32):
        raise ValueError('Bounded phone tap capture required')
    viewport, target = data['viewport'], data['target']
    if (type(viewport) is not dict or set(viewport) != {'width','height'}
            or not all(number(v,1,10000) for v in viewport.values())
            or type(target) is not dict or set(target) != {'left','top','right','bottom'}
            or not all(number(v,0,10000) for v in target.values())
            or not 0 <= target['left'] < target['right'] <= viewport['width']
            or not 0 <= target['top'] < target['bottom'] <= viewport['height']):
        raise ValueError('Valid viewport and target rectangle required')
    issues = set(); previous = 0; phase = 'down'; clicks = 0
    for event in data['events']:
        if (type(event) is not dict or set(event) != {'kind','x','y','at_ms','trusted'}
                or event['kind'] not in ('down','up','click','cancel')
                or type(event['at_ms']) is not int or not previous <= event['at_ms'] <= 60000
                or type(event['trusted']) is not bool
                or not number(event['x'],0,viewport['width'])
                or not number(event['y'],0,viewport['height'])):
            raise ValueError('Invalid tap event')
        previous = event['at_ms']
        if not event['trusted']: issues.add('UNTRUSTED_EVENT')
        if not (target['left'] < event['x'] < target['right']
                and target['top'] < event['y'] < target['bottom']):
            issues.add('OUTSIDE_TARGET_INTERIOR')
        if event['kind'] != phase: issues.add('INVALID_TAP_SEQUENCE')
        phase = {'down':'up','up':'click','click':'down','cancel':'down'}[event['kind']]
        if event['kind'] == 'cancel': issues.add('POINTER_CANCELLED')
        if event['kind'] == 'click': clicks += 1
    if phase != 'down': issues.add('INCOMPLETE_TAP')
    if clicks != data['expected_taps']: issues.add('TAP_COUNT_MISMATCH')
    if data['stop_reason'] != 'STOPPED': issues.add('CAPTURE_INTERRUPTED')
    return dict(schema='rocell.tap_capture_review.v1',
        status='TAP_SEQUENCE_OBSERVED' if not issues else 'TAP_NOT_VERIFIED',
        capture_id=data['capture_id'], expected_taps=data['expected_taps'], observed_clicks=clicks,
        issues=sorted(issues), capture=data, coordinate_units='CSS_PIXELS',
        browser_provenance_authenticated=False, robot_tap_confirmed=False,
        physical_accuracy_verified=False, motion_authorized=False, hardware_access=False)
