import pytest

from rocell.arm.endpoint_correction_simulation import assess_correction


def record(actual, desired=1.25, verified=True):
    return dict(final_deg=actual, desired_endpoint_deg=desired,
                full_validation_success=verified, baseline_rad=[0]*6)


def test_accepted_endpoint_needs_no_correction():
    result = assess_correction(record(1.230468748))
    assert result['decision']=='ACCEPT_REPORTED_ENDPOINT'
    assert not result['motion_authorized']


@pytest.mark.parametrize('actual', [1.406250023, 1.494140602, 1.142578111])
def test_small_corrections_rejected_by_existing_guard(actual):
    assert assess_correction(record(actual))['decision']=='STOP_DIRECT_CORRECTION_OUTSIDE_ENVELOPE'


def test_failed_or_partial_evidence_cannot_be_repaired():
    assert assess_correction({'full_validation_success':False})['decision']=='STOP_INCOMPLETE_OR_UNVERIFIED'


def test_eligible_geometry_is_not_authority_or_prediction():
    result = assess_correction(record(0))
    assert result['decision']=='DIRECT_CORRECTION_GEOMETRY_ELIGIBLE_ONLY'
    assert result['outcome_unknown'] and result['fresh_baseline_required']
    assert not result['plant_response_predicted'] and not result['motion_authorized']


@pytest.mark.parametrize('band', [0,-1,float('nan'),True])
def test_invalid_analysis_band(band):
    with pytest.raises(ValueError):assess_correction(record(1.2),band_deg=band)
