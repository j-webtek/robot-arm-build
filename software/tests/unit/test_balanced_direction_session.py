"""Virtual-only balanced direction schedule; no native transport."""
import pytest
from test_comparison_session import harness
from rocell.arm.comparison_session import BalancedDirectionSession
from rocell.application.comparison_wizard_adapter import WizardComparisonAdapter


def test_fixed_abba_single_use_and_adapter_mapping():
    run,calls,_=harness(session_type=BalancedDirectionSession)
    assert run()['status']=='COMPLETED'
    assert calls==['zero','center_up','high','lookup','high','lookup','zero','center_up']
    assert all(name in WizardComparisonAdapter.ACTIONS for name in calls)
    with pytest.raises(ValueError):run()


@pytest.mark.parametrize('fault',['incomplete_hold','endpoint','baseline','command',
    'dispatch_late','slow_review','slow_intent','publish','cancel','final_publish'])
def test_failure_retained_without_retry(fault):
    run,calls,_=harness(session_type=BalancedDirectionSession,fault=fault)
    result=run()
    assert result['status']=='STOPPED'
    assert not result['automatic_retry_allowed'] and not result['resumable']
    assert len(calls)<=2 if fault!='final_publish' else len(calls)==8
