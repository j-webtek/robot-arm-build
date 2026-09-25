"""Pure display projections, including values from the first real in-band run."""
from copy import deepcopy
import math
import pytest
from rocell.application.micro_result_summary import summarize_micro_result


def fixture():
    return dict(status='NO_CORRECTION_NEEDED', micro=None,
        predecessor=dict(status='SUCCEEDED', outcome=dict(transaction=dict(
            state='REPORTED_ENDPOINT_VERIFIED', command=dict(rad=math.radians(.95)),
            desired_endpoint_rad=math.radians(1.25),
            rows=[[1, 2, [0, 0, 0, 0, .021475731, 0]]]))),
        predecessor_hold=dict(status='SUCCEEDED', reconstruction=dict(
            successful_originals=119, response_span_s=34.950386,
            maximum_response_gap_ms=418.2085)))


def test_real_in_band_values_separate_two_errors_without_mutation():
    report=fixture(); original=deepcopy(report)
    summary=summarize_micro_result(report); leg=summary['legs'][0]
    assert report==original
    assert leg['observed_deg']==pytest.approx(1.230468748258267)
    assert leg['desired_error_deg']==pytest.approx(-.019531251741733)
    assert leg['command_error_deg']==pytest.approx(.280468748258267)
    assert leg['hold_samples']==119
    assert not summary['micro_result_present']
    assert not summary['motion_authorized'] and not summary['physical_accuracy_verified']


def test_failed_transaction_does_not_present_receipt_as_endpoint():
    report=fixture(); report['predecessor']['outcome']['transaction']['state']='STOPPED'
    leg=summarize_micro_result(report)['legs'][0]
    assert leg['observed_deg'] is None and leg['desired_error_deg'] is None


def test_missing_reports_and_partial_micro_remain_unknown():
    assert summarize_micro_result({})['legs']==[]
    leg=summarize_micro_result(dict(micro=dict(status='STOPPED')))['legs'][0]
    assert leg['observed_deg'] is None and leg['hold_samples'] is None
    assert leg['hold_status']=='NOT_RUN'


def test_zero_is_preserved_and_nonfinite_command_is_unavailable():
    r=dict(micro=dict(status='STOPPED',context=dict(command=dict(rad=float('nan'))),
        endpoint=dict(reported_settled=True,desired_endpoint_rad=0,final_pose_rad=[0]*6)))
    leg=summarize_micro_result(r)['legs'][0]
    assert leg['command_deg'] is None and leg['command_error_deg'] is None
    assert leg['observed_deg']==0 and leg['desired_error_deg']==0
    assert leg['status']=='STOPPED'  # A displayed settled value is not success.
