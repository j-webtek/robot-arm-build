"""Commissioning preparation never becomes a substitute endpoint permit."""
import json
from pathlib import Path

import pytest

from rocell.application.first_motion_rehearsal import SCENARIOS, proposal, rehearse, assess
from rocell.application.wizard_actions import ACTION_BY_ID, validate_action_input, WizardError
from rocell.application.wizard_worker import run


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_all_scenarios_are_deterministic_bounded_and_non_authorizing(scenario):
    result = rehearse(scenario)
    assert result == rehearse(scenario)
    assert len(json.dumps(result)) < 4096
    assert result['device_open_count'] == result['serial_write_count'] == 0
    assessment = result['assessment']
    assert (assessment['status']=='OBSERVATIONS_AGREE_REVIEW_REQUIRED') == (scenario=='NOMINAL')
    for name in ('endpoint_baseline_qualified', 'device_sample_freshness_verified',
                 'physical_authority', 'motion_authorized', 'automatic_return_allowed',
                 'automatic_retry_allowed', 'campaign_advance_allowed'):
        assert assessment[name] is False


def test_proposal_is_detached_and_geometry_is_a_requirement_not_a_fact():
    original = proposal()
    original['required_independent_start_interval_deg'][0] = -90
    assert proposal()['required_independent_start_interval_deg'] == [-5,5]
    assert not proposal()['geometry_conditions_established']
    assert not proposal()['live_execution_implemented']


@pytest.mark.parametrize('field,value', [('cleanup',1), ('cancelled',0),
    ('other_joint_moved','false'), ('telemetry','APPROVED'), ('physical',True), ('write','RETRY')])
def test_invalid_observations_refused(field,value):
    observations = dict(telemetry='EXPECTED',physical='EXPECTED',write='COMPLETE',
                        cleanup=True,cancelled=False,other_joint_moved=False)
    observations[field] = value
    with pytest.raises(ValueError):
        assess(**observations)


def test_public_worker_returns_rehearsal_and_cannot_take_commands(tmp_path):
    result = run(tmp_path, 'first_motion_rehearse', {'scenario':'TELEMETRY_ONLY'}, 'test')
    assert result['steps'][0]['report']['assessment']['status']=='INCONCLUSIVE_OR_FAILED'
    with pytest.raises(WizardError):
        validate_action_input(ACTION_BY_ID['first_motion_rehearse'],
                              {'scenario':'NOMINAL','command':{'T':101}})
