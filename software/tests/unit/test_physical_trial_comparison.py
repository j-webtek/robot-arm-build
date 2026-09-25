from pathlib import Path

import pytest

from rocell.application.physical_trial_comparison import compare_results, export_comparison, render_comparison
from rocell.application.wizard_diagnostic_export import verify_export


@pytest.fixture
def inputs():
    recovery = dict(schema='rocell.r29_settled_recovery_analysis.v1',
                    diagnostic_restart_between_command_and_settled_capture=True,
                    physical_accuracy_verified=False,
                    joints=[dict(servo_id=sid, initial_position=2000,
                                 settled_sampled_position=1990, commanded_goal=1980,
                                 observed_delta=-10, residual=10) for sid in range(11, 18)])
    local = dict(schema='rocell.physical_local_step_review.v1', basis='DEVICE_CAPTURE',
                 settling=dict(stability_verified=True, final_positions=[1989]*7),
                 endpoints=[dict(servo_id=sid, start_counts=2000, accepted_counts=1980,
                                 endpoint_error_counts=10) for sid in (12, 13)])
    return recovery, local


def test_different_trials_not_pooled(inputs):
    result = compare_results(*inputs)
    assert result['pooled_statistics'] is False
    assert result['compensation_proposed'] is False
    assert result['rows'][0]['recovery_error'] == 10
    assert result['rows'][0]['local_settled_error'] == 9
    assert 'Unlike trials' in render_comparison(result)


def test_inconsistent_derived_arithmetic_rejected(inputs):
    inputs[0]['joints'][1]['residual'] = 0
    with pytest.raises(ValueError, match='arithmetic'):
        compare_results(*inputs)


def test_missing_settling_not_treated_as_zero(inputs):
    inputs[1]['settling'] = None
    with pytest.raises(ValueError, match='incomplete'):
        compare_results(*inputs)


def test_synthetic_local_result_rejected(inputs):
    inputs[1]['basis'] = 'SYNTHETIC_ONLY'
    with pytest.raises(ValueError):
        compare_results(*inputs)


def test_duplicate_servo_rejected(inputs):
    inputs[0]['joints'][2]['servo_id'] = 12
    with pytest.raises(ValueError):
        compare_results(*inputs)


def test_saved_physical_comparison(tmp_path):
    root = Path(__file__).resolve().parents[2] / 'runs/wizard-exports'
    recovery = root / 'wizard-20260919T212458408646Z-f7e6a7fbf4e942208ea216666ddf55f0'
    local = root / 'wizard-20260919T234006065057Z-53ea59edfe2d4b20bfc7d3eaae25253e'
    if not recovery.exists() or not local.exists():
        pytest.skip('Private historical evidence not distributed')
    saved = Path(export_comparison(recovery, local, tmp_path))
    assert verify_export(saved)['valid']
    text = (saved / 'attachment-trial-comparison.md').read_text()
    assert '| 12 | 2419 | 2429 | 10 | 2405 | 10 | 2414 | 9 |' in text
    assert '| 13 | 1695 | 1688 | -7 | 1709 | -7 | 1702 | -7 |' in text
