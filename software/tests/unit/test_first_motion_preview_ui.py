"""Shipped renderer against a modeled DOM; no browser or physical requests."""
from rocell.application.first_motion_draft import FirstMotionDraft
from test_first_motion_contract import request
from test_wizard_form_drafts_ui import action, view, render, read_only


def test_commissioning_command_and_selected_limits_are_visible():
    selected = action('run_first_motion')
    draft = FirstMotionDraft.from_request(request())
    selected['commissioning_preview'] = draft.preview()
    page = render(view(selected), page='arm')
    assert 'not a +1 degree increment' in page['text']
    assert '20 servo steps/s' in page['text']
    assert 'cancellation is not a physical emergency stop' in page['text']
    assert draft.selection_sha256 in page['text']
    assert 'independent_start_interval_deg' in page['text']
    assert 'distal_radius_mm' in page['text']
    read_only(page)


def test_qualification_review_shows_holds_without_accepting():
    selected = action('review_first_motion_qualification')
    selected['enabled'] = True
    selected['blocked_reasons'] = []
    key = 'operation-'+'2'*32
    selected['fields'][0].update(options=[dict(value=key, label=key)], default=None)
    selected['qualification_previews'] = {key: dict(status='HELD', holds=['OBSERVATION_COVERAGE_INCOMPLETE'],
        reported_observation=dict(outcome='UNKNOWN'), limitations=['Synthetic evidence only.'], assessment_sha256='a'*64)}
    page = render(view(selected), page='arm', steps=[dict(
        edit='field-review_first_motion_qualification-assessment_operation_id', value=key)])
    assert 'OBSERVATION_COVERAGE_INCOMPLETE' in page['text']
    assert 'Synthetic evidence only.' in page['text']
    assert 'acceptance cannot override a hold' in page['text']
    read_only(page)


def test_unattached_form_explains_required_setup_without_claiming_completion():
    selected = action('run_first_motion')
    selected['enabled'] = False
    selected['blocked_reasons'] = ['No host-attached commissioning draft and originals.']
    page = render(view(selected), page='arm')
    for phrase in ('Prepare this commissioning test', 'Missing key storage is not an arm or USB fault',
                   'angle and radius uncertainty', 'all five engineering decisions',
                   'trusted host integration', 'keep this run blocked'):
        assert phrase in page['text']
    assert 'Commissioning selection:' not in page['text']
    read_only(page)


def test_retained_review_selection_displays_exact_preview_without_submission():
    selected = action('review_retained_first_motion_draft')
    selected['enabled'] = True
    selected['blocked_reasons'] = []
    key = 'operation-'+'1'*32
    draft = FirstMotionDraft.from_request(request())
    selected['fields'][0].update(options=[dict(value=key, label=key)], default=None)
    selected['retained_draft_previews'] = {key: draft.preview()}
    page = render(view(selected), page='arm', steps=[dict(
        edit='field-review_retained_first_motion_draft-draft_operation_id', value=key)])
    assert draft.selection_sha256 in page['text']
    assert 'independent_start_interval_deg' in page['text']
    assert 'not current physical verification or motion approval' in page['text']
    read_only(page)
