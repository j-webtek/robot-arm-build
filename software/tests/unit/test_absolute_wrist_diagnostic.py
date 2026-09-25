"""Absolute diagnostic drafts cannot obtain live single-trial authority."""
import copy
import math

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.motion.absolute_wrist_diagnostic import (
    AbsoluteWristDiagnosticDraft, draft_absolute_wrist, preview_absolute_wrist,
    preview_absolute_wrist_from_capture,
)
from rocell.safety.observational_review_authority import ObservationalIntent
from test_observational_wrist_plan import capture


def fixture(start_deg=-4, target_deg=0, direction=1):
    samples = capture()
    for row in samples:
        row['joints_rad']['t'] = math.radians(start_deg)
    draft = draft_absolute_wrist(expected_start_joints_rad=samples[-1]['joints_rad'],
                                target_deg=target_deg, direction=direction)
    return draft, samples


@pytest.mark.parametrize('target', [-4, 0, 4])
def test_opposite_approaches_preserve_exact_same_absolute_target(target):
    commands = []
    for direction in (-1, 1):
        draft, samples = fixture(target - direction * 4, target, direction)
        original = copy.deepcopy(samples)
        preview = preview_absolute_wrist(draft, samples=samples, now_ns=1_300_000_000)
        commands.append(preview['candidate_command'])
        assert not preview['motion_authorized'] and not preview['automatic_next_command_allowed']
        assert samples == original
        # A bounded drift is checked, but never added to the absolute target.
        samples[-1]['joints_rad']['t'] += math.radians(.1)
        changed = preview_absolute_wrist(draft, samples=samples, now_ns=1_300_000_000)
        assert changed['candidate_command'] == commands[-1]
        assert changed['baseline_sha256'] != preview['baseline_sha256']
    assert commands[0] == commands[1] == dict(T=101, joint=4, rad=math.radians(target), spd=20, acc=1)


@pytest.mark.parametrize('field,value', [('target_deg', True), ('target_deg', .0),
    ('target_deg', 3), ('target_deg', float('nan')), ('direction', True),
    ('direction', 0), ('direction', -1), ('motion_authorized', True),
    ('schema', 'rocell.observational_intent.v1')])
def test_mutated_draft_rejected(field, value):
    draft, _ = fixture()
    body = draft.to_dict()
    body[field] = value
    with pytest.raises(ValueError):
        AbsoluteWristDiagnosticDraft(canonical(body))


@pytest.mark.parametrize('fault', ['drift', 'wrong_side', 'too_far', 'no_op',
    'stale', 'gap', 'batched_conflict', 'nonfinite', 'missing_joint', 'future'])
def test_changed_or_unsuitable_baseline_rejected(fault):
    draft, samples = fixture()
    now = 1_300_000_000
    if fault == 'drift':
        for row in samples: row['joints_rad']['b'] += math.radians(.6)
    if fault in ('wrong_side', 'too_far', 'no_op'):
        for row in samples:
            row['joints_rad']['t'] = math.radians(dict(wrong_side=4, too_far=-6, no_op=0)[fault])
    if fault == 'stale': now = 4_000_000_000
    if fault == 'gap': samples = [samples[0], samples[-1]]
    if fault == 'batched_conflict':
        samples[-1]['host_received_ns'] = samples[-2]['host_received_ns']
        samples[-1]['joints_rad']['t'] += math.radians(1)
    if fault == 'nonfinite': samples[0]['joints_rad']['r'] = float('inf')
    if fault == 'missing_joint': del samples[0]['joints_rad']['g']
    if fault == 'future': now = 1_100_000_000
    with pytest.raises(ValueError):
        preview_absolute_wrist(draft, samples=samples, now_ns=now)


@pytest.mark.parametrize('start', [-5.01, -.5, 0, 4])
def test_declared_start_must_define_bounded_resolvable_approach(start):
    with pytest.raises(ValueError): fixture(start)


def test_draft_immutable_and_incompatible_with_native_intent():
    draft, samples = fixture()
    saved = draft.canonical_bytes
    samples[-1]['joints_rad']['t'] = 100
    body = draft.to_dict()
    body['limits']['maximum_commands'] = 2
    assert draft.canonical_bytes == saved
    with pytest.raises(ValueError): AbsoluteWristDiagnosticDraft(canonical(body))
    with pytest.raises(ValueError): ObservationalIntent(saved)
    with pytest.raises(ValueError):
        preview_absolute_wrist(body, samples=capture(), now_ns=1_300_000_000)


@pytest.mark.parametrize('corrupt', [False, True])
def test_raw_capture_uses_all_complete_records(corrupt):
    import json
    draft, samples = fixture()
    raw, windows = b'', []
    for index, sample in enumerate(samples):
        line = json.dumps(dict(T=1051, x=1, y=2, z=3, tit=0,
                               **sample['joints_rad'])).encode() + b'\n'
        if corrupt and index == 2: line = b'{broken}\n'
        stamp = sample['host_received_ns']
        windows.append([len(raw), len(raw) + len(line), stamp, stamp])
        raw += line
    kwargs = dict(started_ns=990_000_000, finished_ns=1_210_000_000, now_ns=1_300_000_000)
    if corrupt:
        with pytest.raises(ValueError):
            preview_absolute_wrist_from_capture(draft, raw, windows, **kwargs)
    else:
        report = preview_absolute_wrist_from_capture(draft, raw, windows, **kwargs)
        assert report['candidate_command']['rad'] == 0
        assert report['raw_capture_framing']['original_bytes'] == len(raw)
        assert report['motion_authorized'] is False
