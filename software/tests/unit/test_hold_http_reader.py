import pytest
from rocell.application.hold_transport_snapshot import HoldHTTPReader
from rocell.application.servo_transport_snapshot import STATUS, RECORD


@pytest.mark.parametrize('path,budget', [(STATUS, 513), (RECORD+'12', 4608),
    (RECORD+'0', 4609), ('/rocell/diagnostics/start', 100), ('/js', 100)])
def test_hold_reader_rejects_other_routes_and_budgets(path, budget, monkeypatch):
    reader = HoldHTTPReader('192.168.0.225')
    def forbidden(*args, **kwargs):
        pytest.fail('No socket allowed')
    monkeypatch.setattr('rocell.application.servo_diagnostic_http.socket.socket', forbidden)
    with pytest.raises(ValueError):
        reader(path, maximum_bytes=budget, timeout_seconds=3)
    with pytest.raises(ValueError):
        reader(STATUS, maximum_bytes=512, timeout_seconds=3)
