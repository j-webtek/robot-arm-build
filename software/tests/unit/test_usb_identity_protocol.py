"""Pure USB admission/retention contracts; no hardware observations or release.

Modeled endpoints and hashes exercise byte bindings only. Encoding a RELEASE
does not consume an M1 permit, check a live deadline or authorize USB access.
"""

from dataclasses import FrozenInstanceError
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import subprocess
from types import ModuleType

import pytest

from rocell.providers.windows import usb_identity_protocol as protocol


REQUEST_KEYS = {
    "schema",
    "attempt_id",
    "session_id",
    "source_sha256",
    "operation_sha256",
    "selected_identity_sha256",
    "native_identity_sha256",
    "endpoint",
    "endpoint_sha256",
    "expected_device_instance_id",
    "expected_device_instance_id_sha256",
    "helper_sha256",
    "runtime_registration_sha256",
    "permit_sha256",
    "native_duration_ms",
    "admission_timeout_ms",
}
HASH_KEYS = sorted(key for key in REQUEST_KEYS if key.endswith("_sha256"))
ENDPOINT = r"\\?\usb#vid_1234&pid_5678#MODELED-CAMERA-ONLY#{test-interface}"
INSTANCE = r"USB\VID_1234&PID_5678\MODELED-CAMERA-ONLY"


def request_document(**changes):
    """Explicitly modeled owned request, not a physical registration or permit."""
    value = {
        "schema": "rocell.native_usb_identity_admission_request.v1",
        "attempt_id": "attempt-" + "1" * 32,
        "session_id": "physical-camera-" + "2" * 32,
        "source_sha256": "a" * 64,
        "operation_sha256": "b" * 64,
        "selected_identity_sha256": "c" * 64,
        "native_identity_sha256": "d" * 64,
        "endpoint": ENDPOINT,
        "endpoint_sha256": hashlib.sha256(ENDPOINT.encode("utf-8")).hexdigest(),
        "expected_device_instance_id": INSTANCE,
        "expected_device_instance_id_sha256": hashlib.sha256(
            INSTANCE.encode("utf-8")
        ).hexdigest(),
        "helper_sha256": "e" * 64,
        "runtime_registration_sha256": "f" * 64,
        "permit_sha256": "9" * 64,
        "native_duration_ms": 10000,
        "admission_timeout_ms": 5000,
    }
    value.update(changes)
    return value


def admission_request(**changes):
    return protocol.UsbIdentityAdmissionRequest(
        protocol.canonical(request_document(**changes))
    )


def ready_for(request, *, pid=31415, challenge="f" * 64):
    return protocol.UsbIdentityReady(
        protocol.canonical(
            {
                "schema": "rocell.native_usb_identity_admission_ready.v1",
                "request_sha256": request.request_sha256,
                "child_pid": pid,
                "challenge": challenge,
            }
        )
    )


def reject_request(value):
    with pytest.raises(protocol.UsbIdentityProtocolError):
        protocol.UsbIdentityAdmissionRequest(protocol.canonical(value))


def test_request_exact_canonical_detached_snapshot_and_wire():
    value = request_document()
    request = protocol.UsbIdentityAdmissionRequest(protocol.canonical(value))
    original = request.payload
    assert set(request.to_dict()) == REQUEST_KEYS
    assert request.request_sha256 == hashlib.sha256(original).hexdigest()
    assert request.wire() == original + b"\n"
    assert len(request.wire()) <= 16 * 1024
    assert request.to_dict()["admission_timeout_ms"] == 5000
    assert request.to_dict()["native_duration_ms"] == 10000
    value["permit_sha256"] = "0" * 64
    detached = request.to_dict()
    detached["endpoint"] = "a different modeled endpoint"
    assert request.to_dict() == request_document()
    assert request.payload == original
    with pytest.raises(FrozenInstanceError):
        request.payload = b"{}"


@pytest.mark.parametrize("key", sorted(REQUEST_KEYS))
def test_request_missing_field_is_not_defaulted(key):
    value = request_document()
    del value[key]
    reject_request(value)


@pytest.mark.parametrize(
    "extra",
    [
        {"endpoint_path": ENDPOINT},
        {"expires_monotonic_ns": 123456},
        {"physical_authority": True},
        {"reset_port": False},
        {"controls": []},
        {"retry_count": 0},
    ],
)
def test_request_extra_fields_cannot_extend_operation(extra):
    reject_request(request_document(**extra))


@pytest.mark.parametrize("key", HASH_KEYS)
@pytest.mark.parametrize("invalid", [None, True, 123, "A" * 64, "a" * 63, "g" * 64])
def test_all_request_hashes_have_strict_lowercase_sha256_shape(key, invalid):
    reject_request(request_document(**{key: invalid}))


@pytest.mark.parametrize("key", ["endpoint", "expected_device_instance_id"])
def test_target_bytes_and_hash_cannot_be_changed_independently(key):
    value = request_document()
    value[key] += "CHANGED"
    reject_request(value)
    value = request_document()
    value[key + "_sha256"] = "0" * 64
    reject_request(value)


@pytest.mark.parametrize("key", ["endpoint", "expected_device_instance_id"])
@pytest.mark.parametrize(
    "invalid", [None, 42, True, "", "line\nfeed", "nul\0", "del\x7f", "\ud800"]
)
def test_target_invalid_type_control_or_encoding_is_held(key, invalid):
    reject_request(request_document(**{key: invalid}))


@pytest.mark.parametrize("key", ["endpoint", "expected_device_instance_id"])
def test_target_limit_is_utf8_bytes_while_canonical_document_is_ascii(key):
    text = "\u03a9" * 2048
    request = admission_request(
        **{key: text, key + "_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    )
    assert request.payload.isascii() and b"\\u03a9" in request.payload
    assert request.to_dict()[key] == text
    oversized = text + "x"
    reject_request(
        request_document(
            **{
                key: oversized,
                key + "_sha256": hashlib.sha256(oversized.encode("utf-8")).hexdigest(),
            }
        )
    )


@pytest.mark.parametrize("key", ["attempt_id", "session_id"])
@pytest.mark.parametrize(
    "invalid",
    [None, False, 1, "", " leading", "trailing ", "../other", "\u03a9", "x" * 97],
)
def test_identifiers_are_bounded_ascii_not_paths(key, invalid):
    reject_request(request_document(**{key: invalid}))


@pytest.mark.parametrize("key", ["native_duration_ms", "admission_timeout_ms"])
@pytest.mark.parametrize(
    "invalid", [True, False, None, "5000", 0, -1, 4999, 5001, 9999, 10001]
)
def test_admission_and_native_durations_are_exact_fixed_integers(key, invalid):
    reject_request(request_document(**{key: invalid}))


@pytest.mark.parametrize(
    "payload",
    [b"", b"{}\n", b"[]", b"null", b"\xff", bytearray(b"{}"), "{}", memoryview(b"{}")],
)
def test_request_requires_exact_bounded_canonical_bytes(payload):
    with pytest.raises(protocol.UsbIdentityProtocolError):
        protocol.UsbIdentityAdmissionRequest(payload)


def test_request_rejects_noncanonical_duplicate_and_noninteger_json():
    value = request_document()
    wire = protocol.canonical(value)
    alternatives = (
        b" " + wire,
        wire + b"\n",
        json.dumps(value, sort_keys=True).encode("ascii"),
        b'{"schema":"ignored",' + wire[1:],
        wire.replace(b'"native_duration_ms":10000', b'"native_duration_ms":1e4'),
        wire.replace(b'"native_duration_ms":10000', b'"native_duration_ms":10000.0'),
        wire.replace(b'"native_duration_ms":10000', b'"native_duration_ms":NaN'),
        b'{"nested":' + b"[" * 14 + b"null" + b"]" * 14 + b"}",
        b"x" * protocol.MAX_REQUEST_BYTES,
    )
    for payload in alternatives:
        with pytest.raises(protocol.UsbIdentityProtocolError):
            protocol.UsbIdentityAdmissionRequest(payload)


def test_total_request_limit_is_independent_of_individual_utf8_limits():
    value = request_document()
    for key in ("endpoint", "expected_device_instance_id"):
        value[key] = "\u03a9" * 2048
        value[key + "_sha256"] = hashlib.sha256(value[key].encode("utf-8")).hexdigest()
    assert len(protocol.canonical(value)) > protocol.MAX_REQUEST_BYTES
    reject_request(value)


def test_ready_exact_child_request_challenge_and_release_permit_binding():
    request = admission_request()
    value = ready_for(request).to_dict()
    ready = protocol.parse_usb_identity_ready(
        protocol.canonical(value) + b"\n",
        expected_request_sha256=request.request_sha256,
        expected_child_pid=value["child_pid"],
    )
    assert (
        ready.challenge_sha256
        == hashlib.sha256(value["challenge"].encode("ascii")).hexdigest()
    )
    release_wire = protocol.usb_identity_release(request, ready)
    assert release_wire.endswith(b"\n") and release_wire.count(b"\n") == 1
    assert len(release_wire) <= protocol.MAX_HANDSHAKE_BYTES
    release = json.loads(release_wire)
    assert release == {
        "schema": "rocell.native_usb_identity_admission_release.v1",
        "request_sha256": request.request_sha256,
        "child_pid": value["child_pid"],
        "challenge_sha256": ready.challenge_sha256,
        "permit_sha256": request.to_dict()["permit_sha256"],
    }
    assert release_wire == protocol.canonical(release) + b"\n"
    detached = ready.to_dict()
    detached["child_pid"] = 1
    assert ready.to_dict() == value
    with pytest.raises(FrozenInstanceError):
        ready.payload = b"{}"


@pytest.mark.parametrize(
    "field", ["schema", "request_sha256", "child_pid", "challenge"]
)
def test_ready_requires_every_exact_field(field):
    value = ready_for(admission_request()).to_dict()
    del value[field]
    with pytest.raises(protocol.UsbIdentityProtocolError):
        protocol.UsbIdentityReady(protocol.canonical(value))


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", protocol.REQUEST_SCHEMA),
        ("request_sha256", "X" * 64),
        ("challenge", None),
        ("challenge", "f" * 63),
        ("child_pid", True),
        ("child_pid", 0),
        ("child_pid", 2**32),
        ("child_pid", "31415"),
        ("extra", None),
    ],
)
def test_ready_rejects_foreign_fields_types_and_bounds(field, value):
    document = ready_for(admission_request()).to_dict()
    document[field] = value
    with pytest.raises(protocol.UsbIdentityProtocolError):
        protocol.UsbIdentityReady(protocol.canonical(document))


@pytest.mark.parametrize(
    "fault",
    [
        "wrong-request",
        "wrong-pid",
        "bool-pid",
        "no-newline",
        "two-lines",
        "crlf",
        "leading-space",
        "duplicate",
        "oversize",
        "wrong-type",
    ],
)
def test_ready_line_and_parent_identity_are_independently_checked(fault):
    request = admission_request()
    ready = ready_for(request)
    wire = ready.payload + b"\n"
    expected_hash, expected_pid = request.request_sha256, 31415
    if fault == "wrong-request":
        expected_hash = "0" * 64
    elif fault == "wrong-pid":
        expected_pid += 1
    elif fault == "bool-pid":
        expected_pid = True
    elif fault == "no-newline":
        wire = ready.payload
    elif fault == "two-lines":
        wire += wire
    elif fault == "crlf":
        wire = ready.payload + b"\r\n"
    elif fault == "leading-space":
        wire = b" " + wire
    elif fault == "duplicate":
        wire = b'{"child_pid":31415,' + wire[1:]
    elif fault == "oversize":
        wire = b"x" * protocol.MAX_HANDSHAKE_BYTES + b"\n"
    elif fault == "wrong-type":
        wire = bytearray(wire)
    with pytest.raises(protocol.UsbIdentityProtocolError):
        protocol.parse_usb_identity_ready(
            wire,
            expected_request_sha256=expected_hash,
            expected_child_pid=expected_pid,
        )


def test_release_refuses_ready_from_another_exact_request():
    request = admission_request()
    another = admission_request(permit_sha256="8" * 64)
    with pytest.raises(protocol.UsbIdentityProtocolError) as error:
        protocol.usb_identity_release(request, ready_for(another))
    assert error.value.code == "RELEASE_REQUEST_BINDING"


@pytest.mark.parametrize("target", ["request", "ready"])
@pytest.mark.parametrize("fault", ["dict", "subclass", "forged-fields", "noncanonical"])
def test_release_reconstructs_exact_types_instead_of_trusting_frozen_dataclasses(
    target, fault
):
    request = admission_request()
    ready = ready_for(request)
    value = request if target == "request" else ready
    if fault == "dict":
        value = value.to_dict()
    elif fault == "subclass":

        class Subclass(type(value)):
            pass

        value = Subclass(value.payload)
    else:
        forged = object.__new__(type(value))
        payload = b"{}" if fault == "forged-fields" else b" " + value.payload
        object.__setattr__(forged, "payload", payload)
        value = forged
    with pytest.raises(protocol.UsbIdentityProtocolError):
        protocol.usb_identity_release(
            value if target == "request" else request,
            value if target == "ready" else ready,
        )


def test_import_construction_encoding_and_detachment_are_inert(
    monkeypatch, native_observations
):
    import builtins
    import ctypes
    import io
    import os
    import subprocess
    import time

    source = Path(protocol.__file__).read_bytes()
    compiled = compile(source, str(protocol.__file__), "exec")
    module = ModuleType("test_inert_usb_protocol")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    request_bytes = admission_request().payload
    ready_bytes = ready_for(admission_request()).payload
    native_request, native_value = native_case(native_observations)
    native_ready = ready_for(native_request)
    owned_wire = protocol.canonical(
        owned_document(native_request, native_value, native_ready)
    )

    def forbidden(*args, **kwargs):
        pytest.fail("pure USB protocol attempted filesystem/process/DLL/clock access")

    # Restore the guards before pytest renders a failure (its reporter reads
    # source files). This does not suppress any failure from the guarded code.
    with monkeypatch.context() as guard:
        for owner, names in (
            (builtins, ("open",)),
            (io, ("open",)),
            (
                Path,
                (
                    "open",
                    "read_bytes",
                    "write_bytes",
                    "stat",
                    "lstat",
                    "mkdir",
                    "resolve",
                ),
            ),
            (os, ("open", "stat", "lstat", "listdir", "scandir")),
            (subprocess, ("Popen", "run", "check_output")),
            (ctypes, ("CDLL", "WinDLL")),
            (time, ("monotonic", "monotonic_ns", "time", "time_ns")),
        ):
            for name in names:
                if hasattr(owner, name):
                    guard.setattr(owner, name, forbidden)
        exec(compiled, module.__dict__)
        request = module.UsbIdentityAdmissionRequest(request_bytes)
        ready = module.parse_usb_identity_ready(
            ready_bytes + b"\n",
            expected_request_sha256=request.request_sha256,
            expected_child_pid=31415,
        )
        assert module.usb_identity_release(request, ready)
        assert request.to_dict()["native_duration_ms"] == 10000
        assert ready.to_dict()["child_pid"] == 31415
        restored_request = module.UsbIdentityAdmissionRequest(native_request.payload)
        restored_ready = module.UsbIdentityReady(native_ready.payload)
        _, observation = module.parse_owned_usb_identity_result(
            owned_wire, request=restored_request, ready=restored_ready, returncode=0
        )
        assert observation.to_dict() == native_value
        assert observation.sha256 == module.digest(observation.payload)


NATIVE_SCENARIOS = (
    "nominal",
    "unicode",
    "usb2",
    "pipes",
    "v2-unavailable",
    "no-serial",
    "duplicate-mapping",
    "changed-device",
    "malformed-device",
    "malformed-language",
    "malformed-serial",
    "language-conflict",
    "malformed-ex",
    "malformed-v2",
    "close-failure",
    "call-limit",
    "api-failure",
    "timeout",
    "cancelled",
    "byte-limit",
    "maximum-raw",
)
OBSERVED_SCENARIOS = {"nominal", "unicode", "usb2", "pipes", "v2-unavailable"}


@pytest.fixture(scope="module")
def native_observations():
    """Actual separately linked fake API producer; never the Windows adapter.

    CMake links this executable to tests.cpp and usb_identity_core only, not
    windows_api.cpp/SetupAPI/CM. No build or production executable is selected.
    """
    executable = (
        Path(__file__).resolve().parents[2]
        / "native/windows_usb_identity/build/Release/rocell_usb_identity_tests.exe"
    )
    if not executable.is_file():
        pytest.skip("Separately linked incapable USB producer is not built")

    def emit(*args):
        completed = subprocess.run(
            [str(executable), *args], capture_output=True, check=True, timeout=10
        )
        assert completed.stderr == b""
        assert 0 < len(completed.stdout) <= protocol.MAX_OBSERVATION_BYTES + 2
        return completed.stdout

    request = protocol.UsbIdentityAdmissionRequest(emit("--request").rstrip(b"\r\n"))
    wires = {scenario: emit("--emit", scenario) for scenario in NATIVE_SCENARIOS}
    return request, wires


def native_case(native_observations, scenario="nominal"):
    request, wires = native_observations
    value = json.loads(wires[scenario])
    if scenario == "unicode":
        document = request.to_dict()
        document["endpoint"] = value["requested_endpoint"]
        document["endpoint_sha256"] = protocol.digest(
            document["endpoint"].encode("utf-8")
        )
        request = protocol.UsbIdentityAdmissionRequest(protocol.canonical(document))
    assert value["request_sha256"] == request.request_sha256
    return request, value


def parse_observation(value, request):
    return protocol.parse_usb_identity_observation(
        protocol.canonical(value), request=request
    )


def reaccount(value):
    """Independent test accounting after an explicitly adversarial trace edit."""
    calls = value["calls"]
    ioctls = {
        "HUB_INFORMATION",
        "CONNECTION_DRIVER_KEY",
        "CONNECTION_EX",
        "CONNECTION_EX_V2",
        "DEVICE_DESCRIPTOR",
        "LANGUAGE_DESCRIPTOR",
        "SERIAL_DESCRIPTOR",
    }
    descriptors = {"DEVICE_DESCRIPTOR", "LANGUAGE_DESCRIPTOR", "SERIAL_DESCRIPTOR"}
    counts = {key: 0 for key in value["accounting"]}
    live = set()
    for sequence, row in enumerate(calls, 1):
        row["sequence"] = sequence
        op, ok = row["operation"], row["status"] == "OK"
        counts["api_calls"] += 1
        counts["returned_bytes"] += row["returned_bytes"]
        if op == "OPEN_HUB":
            counts["hub_open_attempts"] += 1
            counts["hub_open_successes"] += int(ok)
            if ok:
                live.add(row["handle_id"])
                counts["peak_open_handles"] = max(
                    counts["peak_open_handles"], len(live)
                )
        elif op == "CLOSE_HUB":
            counts["close_attempts"] += 1
            counts["close_successes"] += int(ok)
            if ok:
                live.discard(row["handle_id"])
        elif op in ioctls:
            counts["ioctl_attempts"] += 1
            counts["ioctl_successes"] += int(ok)
            counts["descriptor_requests"] += int(op in descriptors)
    counts["remaining_open_handles"] = len(live)
    value["accounting"] = counts


@pytest.mark.parametrize("scenario", NATIVE_SCENARIOS)
def test_actual_incapable_native_observation_cross_language_retention(
    native_observations, scenario
):
    request, value = native_case(native_observations, scenario)
    result = protocol.parse_usb_identity_observation(
        native_observations[1][scenario], request=request
    )
    assert result.to_dict() == value
    assert result.payload == protocol.canonical(value)
    assert result.sha256 == hashlib.sha256(result.payload).hexdigest()
    assert result.to_dict()["outcome"] == (
        "OBSERVED" if scenario in OBSERVED_SCENARIOS else "HELD"
    )
    assert (
        "qualified" not in value
        and "physical_authority" not in value
        and "PASS" not in value.values()
    )
    detached = result.to_dict()
    detached["calls"].clear()
    assert result.to_dict() == value


def test_usb2_and_unavailable_v2_remain_observations_not_usb3_qualification(
    native_observations,
):
    request, usb2 = native_case(native_observations, "usb2")
    assert parse_observation(usb2, request).to_dict()["outcome"] == "OBSERVED"
    assert usb2["link"]["ex_speed"] == 2
    assert usb2["link"]["operating_superspeed_or_higher"] is False
    assert usb2["link"]["capable_superspeed_or_higher"] is True
    request, missing = native_case(native_observations, "v2-unavailable")
    assert parse_observation(missing, request).to_dict()["outcome"] == "OBSERVED"
    assert missing["link"]["ex_v2_available"] is False
    assert missing["link"]["ex_v2_raw_hex"] is None
    assert missing["link"]["operating_superspeed_or_higher"] is None


def test_unicode_native_utf8_is_canonicalized_without_losing_descriptor_bytes(
    native_observations,
):
    request, value = native_case(native_observations, "unicode")
    wire = json.dumps(value, ensure_ascii=False).encode("utf-8")
    assert not wire.isascii()
    result = protocol.parse_usb_identity_observation(wire, request=request)
    assert result.payload.isascii()
    assert result.to_dict() == value
    serial = value["serial_descriptors"][0]
    assert bytes.fromhex(serial["raw_hex"])[2:].decode("utf-16-le") == serial["value"]
    with pytest.raises(protocol.UsbIdentityProtocolError):
        protocol.UsbIdentityObservation(wire)


@pytest.mark.parametrize(
    "role",
    [
        "schema",
        "request_sha256",
        "requested_endpoint",
        "expected_device_instance_id",
        "outcome",
        "pre_mapping",
        "post_mapping",
        "device_descriptor",
        "languages",
        "serial_descriptors",
        "link",
        "accounting",
        "calls",
        "error",
        "elapsed_ms",
    ],
)
def test_observation_has_no_optional_root_fields(native_observations, role):
    request, value = native_case(native_observations)
    del value[role]
    with pytest.raises(protocol.UsbIdentityProtocolError):
        parse_observation(value, request)


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("pre_mapping",),
        ("post_mapping",),
        ("pre_mapping", "hops", 0),
        ("device_descriptor",),
        ("languages",),
        ("serial_descriptors", 0),
        ("link",),
        ("accounting",),
        ("calls", 0),
    ],
)
def test_nested_wire_fields_are_closed(native_observations, path):
    request, value = native_case(native_observations)
    target = value
    for key in path:
        target = target[key]
    target["unreviewed_extension"] = False
    with pytest.raises(protocol.UsbIdentityProtocolError):
        parse_observation(value, request)


@pytest.mark.parametrize("scenario", sorted(set(NATIVE_SCENARIOS) - OBSERVED_SCENARIOS))
def test_held_native_receipts_cannot_be_promoted_by_relabeling(
    native_observations, scenario
):
    request, value = native_case(native_observations, scenario)
    value.update(outcome="OBSERVED", error=None)
    with pytest.raises(protocol.UsbIdentityProtocolError):
        parse_observation(value, request)


@pytest.mark.parametrize(
    "fault",
    [
        "descriptor-vid",
        "descriptor-pid",
        "serial-decoding",
        "serial-language",
        "language-bytes",
        "ex-speed",
        "v2-flag",
        "v2-protocol",
        "ex-descriptor",
        "port",
        "wrong-unit",
        "deadline-boundary",
        "mapping-drift",
        "mapping-cycle",
    ],
)
def test_raw_descriptors_mapping_link_and_deadline_cannot_contradict_observed_fields(
    native_observations, fault
):
    request, value = native_case(native_observations)
    if fault.startswith("descriptor-"):
        value["device_descriptor"][fault.removeprefix("descriptor-")] = "ffff"
    elif fault == "serial-decoding":
        value["serial_descriptors"][0]["value"] += "OTHER"
    elif fault == "serial-language":
        value["serial_descriptors"][0]["language_id"] += 1
    elif fault == "language-bytes":
        value["languages"]["language_ids"] = [0x411]
    elif fault == "ex-speed":
        value["link"]["ex_speed"] = 2
    elif fault == "v2-flag":
        value["link"]["operating_superspeed_or_higher"] = False
    elif fault == "v2-protocol":
        value["link"]["supported_usb_protocols"] = 0
    elif fault == "ex-descriptor":
        raw = bytearray.fromhex(value["link"]["ex_raw_hex"])
        raw[12] ^= 1
        value["link"]["ex_raw_hex"] = raw.hex()
    elif fault == "port":
        for name in ("pre_mapping", "post_mapping"):
            value[name]["hops"][0]["connection_index"] = 1
    elif fault == "wrong-unit":
        for name in ("pre_mapping", "post_mapping"):
            value[name]["physical_usb_instance_id"] = r"USB\VID_ffff&PID_eeee\DIFFERENT"
    elif fault == "deadline-boundary":
        value["elapsed_ms"] = 10000
    elif fault == "mapping-drift":
        value["post_mapping"]["endpoint_instance_id"] += "CHANGED"
    elif fault == "mapping-cycle":
        value["pre_mapping"]["hops"].append(deepcopy(value["pre_mapping"]["hops"][0]))
    with pytest.raises(protocol.UsbIdentityProtocolError):
        parse_observation(value, request)


def test_malformed_raw_bytes_are_kept_only_with_null_decoded_fields_and_held(
    native_observations,
):
    for scenario, role, decoded in (
        ("malformed-device", "device_descriptor", "vid"),
        ("malformed-language", "languages", "language_ids"),
        ("malformed-serial", "serial_descriptors", "value"),
    ):
        request, value = native_case(native_observations, scenario)
        result = parse_observation(value, request).to_dict()
        item = result[role][0] if role == "serial_descriptors" else result[role]
        assert item["raw_hex"]
        assert item[decoded] in (None, [])
        assert result["outcome"] == "HELD" and result["error"] is not None


def test_all_accounting_fields_are_independently_rederived(native_observations):
    request, original = native_case(native_observations)
    for key in original["accounting"]:
        for replacement in (True, original["accounting"][key] + 1):
            value = deepcopy(original)
            value["accounting"][key] = replacement
            with pytest.raises(protocol.UsbIdentityProtocolError):
                parse_observation(value, request)


@pytest.mark.parametrize(
    "fault",
    [
        "missing-port",
        "ambiguous-port",
        "wrong-serial-index",
        "wrong-serial-language",
        "wrong-bytes",
        "wrong-target",
        "wrong-ancestry",
        "close-phase",
        "phase-order",
        "ioctl-before-open",
        "double-close",
        "close-retry",
        "unknown-operation",
    ],
)
def test_rehashed_trace_cannot_invent_mapping_serial_or_cleanup_provenance(
    native_observations, fault
):
    request, value = native_case(native_observations)
    calls = value["calls"]
    serial = next(row for row in calls if row["operation"] == "SERIAL_DESCRIPTOR")
    if fault == "missing-port":
        calls.remove(
            next(
                row
                for row in calls
                if row["phase"] == "PRE" and row["operation"] == "CONNECTION_EX"
            )
        )
    elif fault == "ambiguous-port":
        row = deepcopy(
            next(row for row in calls if row["operation"] == "CONNECTION_DRIVER_KEY")
        )
        calls.insert(
            calls.index(next(r for r in calls if r["operation"] == "CLOSE_HUB")), row
        )
    elif fault == "wrong-serial-index":
        serial["descriptor_index"] += 1
    elif fault == "wrong-serial-language":
        serial["language_id"] += 1
    elif fault == "wrong-bytes":
        serial["returned_bytes"] -= 1
    elif fault == "wrong-target":
        next(row for row in calls if row["operation"] == "DEVICE_ID")[
            "observed_text"
        ] = "OTHER-UNIT"
    elif fault == "wrong-ancestry":
        next(row for row in calls if row["operation"] == "PARENT")[
            "observed_number"
        ] = 99
    elif fault == "close-phase":
        next(row for row in calls if row["operation"] == "CLOSE_HUB")["phase"] = "PRE"
    elif fault == "phase-order":
        calls[0]["phase"] = "POST"
    elif fault == "ioctl-before-open":
        row = next(row for row in calls if row["operation"] == "CONNECTION_EX")
        calls.remove(row)
        calls.insert(0, row)
    elif fault in {"double-close", "close-retry"}:
        row = next(row for row in calls if row["operation"] == "CLOSE_HUB")
        index = calls.index(row)
        if fault == "close-retry":
            row.update(status="ERROR", error_domain="WIN32", error_code=6)
        calls.insert(index + 1, deepcopy(row))
    elif fault == "unknown-operation":
        calls[0]["operation"] = "RESET_PORT"
    reaccount(value)
    with pytest.raises(protocol.UsbIdentityProtocolError):
        parse_observation(value, request)


def test_missing_native_cleanup_is_not_repaired_by_top_level_observed(
    native_observations,
):
    request, value = native_case(native_observations, "close-failure")
    assert value["accounting"]["close_attempts"] == 1
    assert value["accounting"]["remaining_open_handles"] == 1
    assert value["error"]["code"] == "CLOSE_FAILED"
    assert parse_observation(value, request).to_dict() == value
    value.update(outcome="OBSERVED", error=None)
    with pytest.raises(protocol.UsbIdentityProtocolError):
        parse_observation(value, request)


def test_observed_cannot_hide_a_failed_required_call_followed_by_retry(
    native_observations,
):
    request, value = native_case(native_observations)
    failed = deepcopy(value["calls"][0])
    assert failed["operation"] == "MAP_ENDPOINT"
    failed.update(
        status="ERROR",
        error_domain="CM",
        error_code=13,
        returned_bytes=0,
        observed_text=None,
        observed_number=None,
    )
    value["calls"].insert(0, failed)
    reaccount(value)
    with pytest.raises(protocol.UsbIdentityProtocolError):
        parse_observation(value, request)


@pytest.mark.parametrize(
    "fault",
    [
        "selected-port-disconnected",
        "unqueried-connected-port",
        "subject-not-trace",
        "serial-trace-not-subject",
    ],
)
def test_retained_raw_scan_and_descriptor_bytes_authenticate_observation(
    native_observations, fault
):
    request, value = native_case(native_observations)
    calls = value["calls"]
    if fault in {"selected-port-disconnected", "unqueried-connected-port"}:
        target_port = 2 if fault == "selected-port-disconnected" else 1
        row = next(
            row
            for row in calls
            if row["phase"] == "PRE"
            and row["operation"] == "CONNECTION_EX"
            and row["connection_index"] == target_port
        )
        raw = bytearray.fromhex(row["returned_raw_hex"])
        raw[31:35] = (0 if target_port == 2 else 1).to_bytes(4, "little")
        row["returned_raw_hex"] = raw.hex()
    elif fault == "subject-not-trace":
        # Keep the two top-level descriptor copies self-consistent. The actual
        # retained call outputs, not another redundant projection, expose this.
        descriptor = bytearray.fromhex(value["device_descriptor"]["raw_hex"])
        descriptor[2:4] = (0x0200).to_bytes(2, "little")
        value["device_descriptor"].update(raw_hex=descriptor.hex(), bcd_usb=0x0200)
        ex = bytearray.fromhex(value["link"]["ex_raw_hex"])
        ex[4:22] = descriptor
        value["link"]["ex_raw_hex"] = ex.hex()
    elif fault == "serial-trace-not-subject":
        row = next(row for row in calls if row["operation"] == "SERIAL_DESCRIPTOR")
        raw = bytearray.fromhex(row["returned_raw_hex"])
        raw[2] ^= 1  # Same length, still valid UTF-16, different observed serial.
        row["returned_raw_hex"] = raw.hex()
    reaccount(value)
    with pytest.raises(protocol.UsbIdentityProtocolError):
        parse_observation(value, request)


def owned_document(request, observation, ready):
    """Modeled parent envelope around actual incapable native receipt bytes."""
    return {
        "schema": protocol.RESULT_SCHEMA,
        "request_sha256": request.request_sha256,
        "child_pid": ready.to_dict()["child_pid"],
        "challenge_sha256": ready.challenge_sha256,
        "permit_sha256": request.to_dict()["permit_sha256"],
        "native_receipt": observation,
    }


@pytest.mark.parametrize(
    "scenario,returncode",
    [("nominal", 0), ("usb2", 0), ("close-failure", 1), ("malformed-serial", 1)],
)
def test_owned_result_preserves_success_or_held_and_exact_parent_binding(
    native_observations, scenario, returncode
):
    request, value = native_case(native_observations, scenario)
    ready = ready_for(request)
    outer = owned_document(request, value, ready)
    restored, observation = protocol.parse_owned_usb_identity_result(
        protocol.canonical(outer), request=request, ready=ready, returncode=returncode
    )
    assert restored == outer and observation.to_dict() == value


@pytest.mark.parametrize(
    "fault",
    [
        "schema",
        "request_sha256",
        "child_pid",
        "challenge_sha256",
        "permit_sha256",
        "extra",
        "inner-target",
        "inner-request",
        "other-ready",
        "exit",
        "bool-exit",
        "duplicate",
        "oversize",
    ],
)
def test_owned_result_denies_parent_native_and_exit_mismatches(
    native_observations, fault
):
    request, value = native_case(native_observations)
    ready = ready_for(request)
    outer = owned_document(request, value, ready)
    returncode = 0
    if fault in {"schema", "request_sha256", "challenge_sha256", "permit_sha256"}:
        outer[fault] = "invalid" if fault == "schema" else "0" * 64
    elif fault == "child_pid":
        outer["child_pid"] = True
    elif fault == "extra":
        outer["cleanup_confirmed"] = True
    elif fault == "inner-target":
        value["requested_endpoint"] += "CHANGED"
    elif fault == "inner-request":
        value["request_sha256"] = "0" * 64
    elif fault == "other-ready":
        ready = ready_for(request, challenge="e" * 64)
    elif fault == "exit":
        returncode = 1
    elif fault == "bool-exit":
        returncode = False
    wire = protocol.canonical(outer)
    if fault == "duplicate":
        wire = b'{"child_pid":31415,' + wire[1:]
    elif fault == "oversize":
        wire += b" " * protocol.MAX_RESULT_BYTES
    with pytest.raises(protocol.UsbIdentityProtocolError):
        protocol.parse_owned_usb_identity_result(
            wire, request=request, ready=ready, returncode=returncode
        )


@pytest.mark.parametrize("field", ["request", "ready"])
def test_owned_parser_reconstructs_forged_admission_subjects(
    native_observations, field
):
    request, value = native_case(native_observations)
    ready = ready_for(request)
    wire = protocol.canonical(owned_document(request, value, ready))
    kind = (
        protocol.UsbIdentityAdmissionRequest
        if field == "request"
        else protocol.UsbIdentityReady
    )
    forged = object.__new__(kind)
    object.__setattr__(forged, "payload", b"{}")
    with pytest.raises(protocol.UsbIdentityProtocolError):
        protocol.parse_owned_usb_identity_result(
            wire,
            request=forged if field == "request" else request,
            ready=forged if field == "ready" else ready,
            returncode=0,
        )


@pytest.mark.parametrize(
    "fault",
    [
        "bool-elapsed",
        "bool-port",
        "false-v2",
        "serial-tuple",
        "duplicate-key",
        "nonfinite",
        "nonobject",
        "oversize",
    ],
)
def test_observation_invalid_types_json_and_bounds_remain_closed(
    native_observations, fault
):
    request, value = native_case(native_observations)
    if fault == "bool-elapsed":
        value["elapsed_ms"] = True
    elif fault == "bool-port":
        value["pre_mapping"]["hops"][0]["connection_index"] = True
    elif fault == "false-v2":
        value["link"]["ex_v2_available"] = 1
    elif fault == "serial-tuple":
        value["serial_descriptors"] = {}
    wire = protocol.canonical(value)
    if fault == "duplicate-key":
        wire = b'{"elapsed_ms":0,' + wire[1:]
    elif fault == "nonfinite":
        wire = wire.replace(b'"elapsed_ms":0', b'"elapsed_ms":Infinity')
    elif fault == "nonobject":
        wire = b"[]"
    elif fault == "oversize":
        wire += b" " * protocol.MAX_OBSERVATION_BYTES
    with pytest.raises(protocol.UsbIdentityProtocolError):
        protocol.parse_usb_identity_observation(wire, request=request)
