from copy import deepcopy
import pytest
from test_movement_campaign_ui import render
from test_arrival_wizard_service import make_service,_run
from test_wizard_component_workspaces_ui import render as render_page


@pytest.mark.parametrize('scenario',['arrival','stationary','reboot','no_readback','paired_arrival','paired_failed_read'])
def test_actual_service_result_renders_without_hardware_claim(make_service,scenario):
    service,runner,_=make_service(mode='physical')
    operation=_run(service,'simulate_servo_diagnostics',{'scenario':scenario})
    page=render(operation)
    assert 'Servo diagnostics' in page and 'NOT QUALIFIED' in page
    assert scenario in page and 'offline replay' in page
    if scenario=='reboot':assert 'Rejected trace' in page
    if scenario=='stationary':assert 'FRESH_POSITION_NOT_SETTLED' in page
    if scenario=='paired_arrival':
        assert 'transmitted target' in page and 'final measured position' in page
        assert 'operating mode' in page and 'UNAVAILABLE' in page
    assert not runner.calls


def test_invalid_hardware_authority_not_displayed_as_pass(make_service):
    service,_,_=make_service(mode='physical')
    operation=_run(service,'simulate_servo_diagnostics',{'scenario':'arrival'})
    bad=deepcopy(operation);bad['result']['steps'][0]['report']['progression_authority']=True
    assert 'unavailable or inconsistent' in render(bad)


def test_arm_page_contains_new_action(make_service):
    service,runner,_=make_service(mode='physical')
    result=render_page(service.view(),page='arm')
    assert 'Rehearse servo diagnostics' in str(result)
    assert not runner.calls
