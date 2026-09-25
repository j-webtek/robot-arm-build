"""Exercise new discovery starts using the unchanged v16 motion contract."""
import math
import pytest
from test_roll_mapping_campaign import roll_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_capture import exercise
from test_positional_campaign_native_export import bundle
from rocell.application.first_motion_contract import canonical
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
from rocell.application.positional_campaign_native_export import verify_native_retained_export


def discovery_body(direction, start):
    body = roll_body(direction)
    body['start_joints_rad'][4] = start
    leg = body['legs'][0]
    leg['expected_start_rad'] = start
    leg['target_rad'] = leg['command']['rad'] = start + math.radians(direction)
    PositionalCampaignIntent(canonical(body))
    return body


@pytest.mark.parametrize('direction,start', [(1, .001533981), (-1, math.radians(.9))])
def test_new_starts_reconstruct(tmp_path, monkeypatch, direction, start):
    install(monkeypatch)
    body = discovery_body(direction, start)
    monkeypatch.setattr('test_positional_current_context.body', lambda: body)
    root, name, _ = bundle(tmp_path, monkeypatch, initial_prefix=b'}\n')
    result = verify_native_retained_export(root, name)
    assert result['valid'] and result['endpoint_completion_consistent']
    assert result['endpoint_diagnostics'][0]['start_rad'] == start


@pytest.mark.parametrize('direction,start', [(1, .001533981), (-1, math.radians(.9))])
@pytest.mark.parametrize('mode', ['bias', 'miss', 'other_joint'])
def test_discovery_bias_and_faults(tmp_path, monkeypatch, direction, start, mode):
    install(monkeypatch)
    body = discovery_body(direction, start)
    monkeypatch.setattr('test_positional_current_context.body', lambda: body)
    target = body['legs'][0]['target_rad']
    bias = math.radians(-.21 if direction == 1 else .385)
    kernel, _, _, _, result = exercise(tmp_path, monkeypatch,
        response_target_rad=target + bias if mode == 'bias' else None,
        missed_leg=1 if mode == 'miss' else None,
        failure='other_joint' if mode == 'other_joint' else None)
    assert len(kernel.writes) == 1
    assert result['cleanup']['all_handles_closed']
    assert (result['status'] == 'REPORTED_CAMPAIGN_COMPLETE') == (mode == 'bias')
