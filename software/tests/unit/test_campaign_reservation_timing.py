"""Selected-sample recency remains bounded before and after durable claims."""
import pytest
from test_positional_campaign_admission import setup,baseline
from rocell.safety.positional_campaign_admission import BaselineAgeExceeded


@pytest.mark.parametrize('after_claim',[False,True])
def test_expiry_reports_exact_boundary_and_burns_admission(tmp_path,monkeypatch,after_claim):
    admission,_,clock=setup(tmp_path)
    admission.claim_open();baseline(admission,clock)
    if after_claim:
        publish=admission._publish
        def delayed(stage,body):
            result=publish(stage,body)
            if stage.endswith('-dispatch'):clock[0]=admission._acquired+251_000_000
            return result
        monkeypatch.setattr(admission,'_publish',delayed)
    else:clock[0]=admission._acquired+251_000_000
    with pytest.raises(BaselineAgeExceeded) as caught:admission.consume_command()
    assert caught.value.diagnostic==dict(reason='SELECTED_BASELINE_EXPIRED',
        phase='AFTER_DISPATCH_CLAIM' if after_claim else 'BEFORE_DISPATCH_CLAIM',
        selected_sample_age_ns=251_000_000,maximum_age_ns=250_000_000)
    assert len(list(tmp_path.glob('*-dispatch.json')))==int(after_claim)
    with pytest.raises(ValueError):admission.consume_command()
