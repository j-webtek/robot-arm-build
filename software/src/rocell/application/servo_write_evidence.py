"""Validate raw write evidence against its dispatch; never grant motion authority.

FAILED means acknowledgment verification failed, not that the servo could not
have received the write. In particular, retrying a timed-out write is unsafe.
"""


def assess_write_evidence(record: dict, dispatch: dict) -> dict:
    fields = {"schema", "boot_id", "command_id", "servo_id", "device_us",
              "library_return", "device_error", "ack_policy", "bus_write_status"}
    if not isinstance(record, dict) or set(record) != fields:
        raise ValueError("Invalid write evidence fields")
    if record["schema"] != "rocell.servo_write_evidence.v1":
        raise ValueError("Unsupported write evidence schema")
    for key in ("boot_id", "command_id"):
        value = record[key]
        if (not isinstance(value, str) or not 1 <= len(value) <= 128 or
                any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for c in value)):
            raise ValueError("Invalid write identity")
    for key, low, high in (("servo_id", 1, 253), ("device_us", 0, 2**63-1),
                           ("library_return", -2**31, 2**31-1), ("device_error", -1, 255)):
        if type(record[key]) is not int or not low <= record[key] <= high:
            raise ValueError("Invalid write evidence integer")
    for key in ("boot_id", "command_id", "servo_id", "device_us"):
        if record[key] != dispatch.get(key):
            raise ValueError("Write evidence does not match dispatch")
    if record["ack_policy"] not in ("ENABLED", "DISABLED", "UNKNOWN"):
        raise ValueError("Invalid ACK policy")
    status = "UNKNOWN"
    result, error = record["library_return"], record["device_error"]
    if record["ack_policy"] == "ENABLED":
        if result == 0 or (result == 1 and error > 0):
            status = "FAILED"
        elif result == 1 and error == 0:
            status = "SUCCEEDED"
    if record["bus_write_status"] != status or dispatch.get("bus_write_status") != status:
        raise ValueError("Contradictory write classification")
    return {"schema": "rocell.servo_write_assessment.v1", "bus_write_status": status,
            "acknowledgment_verified": status == "SUCCEEDED",
            "retry_authorized": False, "progression_authority": False,
            "physical_endpoint_verified": False}
