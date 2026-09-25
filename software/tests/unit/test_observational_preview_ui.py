"""Shipped JavaScript renderer with modeled DOM; no hardware or browser requests."""
from test_wizard_form_drafts_ui import action, view, render, read_only


def test_relative_policy_and_simple_sequence_are_visible():
    selected = action('run_observational_movement')
    selected['observational_preview'] = dict(delta_degrees=-1, spd=20, acc=1,
        return_motion=False, usb_identity=dict(serial_number='SYNTHETIC-ONLY'))
    page = render(view(selected), page='arm')
    for phrase in ('-1 degree from the captured baseline', '20 servo steps/s',
                   'not a fixed +1-degree target', 'Notes and photos are optional',
                   'Cancellation is not a physical emergency stop', 'SYNTHETIC-ONLY'):
        assert phrase in page['text']
    assert 'angle and radius uncertainty' not in page['text']
    read_only(page)


def test_absolute_target_is_explicit_and_never_rendered_as_increment():
    selected = action('run_observational_movement')
    selected['observational_preview'] = dict(absolute_target_degrees=0,
        reviewed_draft=dict(target_deg=0, direction=1), fresh_baseline_required=True,
        retry_allowed=False, spd=20, acc=1, return_motion=False,
        usb_identity=dict(serial_number='SYNTHETIC-ONLY'))
    page = render(view(selected), page='arm')
    assert 'Absolute wrist-pitch target: 0 degrees' in page['text']
    assert 'One wrist-pitch increment:' not in page['text']
    assert 'fresh six-joint baseline' in page['text']
    read_only(page)


def test_conflicting_absolute_and_relative_preview_is_disabled():
    selected = action('run_observational_movement')
    selected['enabled'] = True
    selected['observational_preview'] = dict(absolute_target_degrees=0, delta_degrees=1,
        reviewed_draft=dict(target_deg=0, direction=1), fresh_baseline_required=True,
        retry_allowed=False, spd=20, acc=1, return_motion=False)
    page = render(view(selected), page='arm')
    assert all(control['disabled'] for control in page['observations'][-1]['controls'])


def test_setup_renders_retained_absolute_draft_as_distinct_choice():
    selected = action('setup_observational_movement')
    field = next(f for f in selected['fields'] if f['name'] == 'absolute_draft')
    field['options'] = [{'value':'relative', 'label':'Relative increment'},
        {'value':'a'*64, 'label':'Absolute 0 degrees from retained telemetry'}]
    page = render(view(selected), page='arm')
    assert 'Absolute 0 degrees from retained telemetry' in page['text']
    assert 'relative increment or retained absolute draft' in page['text']
    read_only(page)


def test_missing_preview_explains_setup_without_inventing_target():
    selected = action('run_observational_movement')
    selected['enabled'] = True  # Even a malformed enabled view must not expose an active form.
    page = render(view(selected), page='arm')
    assert 'No valid staged observational preview' in page['text']
    assert 'One wrist-pitch increment:' not in page['text']
    assert all(control['disabled'] for control in page['observations'][-1]['controls'])
    read_only(page)
