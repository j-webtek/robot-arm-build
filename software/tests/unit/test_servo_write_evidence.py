import pytest

from rocell.application.servo_write_evidence import assess_write_evidence


def fixture(ack="ENABLED", result=1, error=0, status="SUCCEEDED"):
    record = dict(schema="rocell.servo_write_evidence.v1", boot_id="boot",
                  command_id="command", servo_id=14, device_us=123,
                  library_return=result, device_error=error,
                  ack_policy=ack, bus_write_status=status)
    dispatch = {k: record[k] for k in
                ("boot_id", "command_id", "servo_id", "device_us", "bus_write_status")}
    return record, dispatch


@pytest.mark.parametrize("ack,result,error,status", [
    ("ENABLED", 1, 0, "SUCCEEDED"), ("ENABLED", 0, -1, "FAILED"),
    ("ENABLED", 1, 32, "FAILED"), ("ENABLED", 1, -1, "UNKNOWN"),
    ("DISABLED", 1, 0, "UNKNOWN"), ("UNKNOWN", 1, 0, "UNKNOWN"),
    ("ENABLED", -1, 0, "UNKNOWN"),
])
def test_classification_does_not_authorize_retry_or_motion(ack, result, error, status):
    assessed = assess_write_evidence(*fixture(ack, result, error, status))
    assert assessed["bus_write_status"] == status
    assert assessed["acknowledgment_verified"] == (status == "SUCCEEDED")
    assert not assessed["retry_authorized"]
    assert not assessed["progression_authority"]
    assert not assessed["physical_endpoint_verified"]


@pytest.mark.parametrize("field,value", [
    ("boot_id", "other"), ("command_id", "other"), ("servo_id", 15),
    ("device_us", 124), ("library_return", True), ("device_error", 256),
    ("ack_policy", "GUESS"), ("bus_write_status", "UNKNOWN"),
    ("schema", "unknown"), ("command_id", 'bad"identity'),
])
def test_rejects_malformed_or_misbound_evidence(field, value):
    record, dispatch = fixture()
    record[field] = value
    with pytest.raises(ValueError):
        assess_write_evidence(record, dispatch)


def test_disabled_ack_cannot_claim_success():
    with pytest.raises(ValueError):
        assess_write_evidence(*fixture("DISABLED"))
