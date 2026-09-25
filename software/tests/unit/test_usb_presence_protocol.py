"""Pure codecs plus the separately linked native fixture, never USB enumeration."""

from copy import deepcopy
from pathlib import Path
import subprocess

import pytest

from rocell.providers.windows import usb_presence_protocol as module
from rocell.providers.windows.usb_identity_protocol import canonical, digest


def request():
    return module.build_usb_presence_request(
        attempt_id="MODELED_ATTEMPT",
        session_id="MODELED_SESSION",
        source_sha256="a" * 64,
        phase_binding_sha256="a" * 64,
        target_instance_id=r"USB\VID_1234&PID_5678\UNIT_A",
        selected_identity_sha256="a" * 64,
        operation_sha256="a" * 64,
        permit_sha256="a" * 64,
        helper_sha256="a" * 64,
        runtime_registration_sha256="a" * 64,
        request_nonce="a" * 64,
    )


def modeled(outcome="ABSENT"):
    r = request()
    ids = [] if outcome == "ABSENT" else [r.to_dict()["target_instance_id"]]

    def moment(ms):
        return dict(monotonic_ms=ms, utc_ns=1780000000000000000 + ms * 1000000)

    return dict(
        schema=module.OBSERVATION_SCHEMA,
        request=r.to_dict(),
        request_sha256=r.sha256,
        provider="INCAPABLE_FIXTURE",
        filter=module.physical_device_filter(r.to_dict()["target_instance_id"]),
        scope="PRESENT_PHYSICAL_USB_DEVICE_INSTANCES",
        outcome=outcome,
        error=None,
        started=moment(10),
        finished=moment(30),
        samples=[
            dict(
                started=moment(11 + i * 5),
                finished=moment(14 + i * 5),
                required_chars=8192,
                used_chars=sum(len(s) + 1 for s in ids) + 1,
                api_calls=2,
                native_code=0,
                complete=True,
                target_present=bool(ids),
                error=None,
                instance_ids=list(ids),
            )
            for i in range(2)
        ],
        api_calls=4,
        device_handle_opens=0,
        configuration_writes=0,
        frames=0,
        physical_authority=False,
    )


def parse(value):
    return module.UsbPresenceObservation(canonical(value))


def test_request_roundtrip_and_mutability_are_exact():
    r = request()
    assert module.UsbPresenceRequest(r.payload).payload == r.payload
    copy = r.to_dict()
    copy["target_instance_id"] = "CHANGED"
    assert r.to_dict()["target_instance_id"] != "CHANGED"


@pytest.mark.parametrize("outcome", ["ABSENT", "PRESENT"])
def test_two_complete_modeled_samples_have_no_authority(outcome):
    value = modeled(outcome)
    observation = parse(value)
    assert observation.to_dict() == value
    assert observation.safe_summary()["physical_authority"] is False
    assert observation.safe_summary()["provider"] == "INCAPABLE_FIXTURE"


@pytest.mark.parametrize(
    "target",
    [
        "",
        "ROOT",
        r"USB\VID_1234&PID_5678&MI_00\UNIT",
        "USB\\VID_1234&PID_5678\\",
        r"USB\VID_1234&PID_5678\UNIT\EXTRA",
        r"PCI\VID_1234&PID_5678\UNIT",
        "USB\\VID_1234&PID_5678\\UNICODE_é",
    ],
)
def test_invalid_nonphysical_or_ambiguous_target_refused(target):
    with pytest.raises(module.UsbPresenceProtocolError):
        module.physical_device_filter(target)


@pytest.mark.parametrize(
    "field", ["sample_count", "native_duration_ms", "admission_timeout_ms"]
)
@pytest.mark.parametrize("wrong", [True, "2", 0, 10001])
def test_request_never_coerces_or_widens_fixed_budgets(field, wrong):
    value = request().to_dict()
    value[field] = wrong
    with pytest.raises(ValueError):
        module.UsbPresenceRequest(canonical(value))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda v: v.update(outcome="PRESENT"),
        lambda v: v.update(api_calls=0),
        lambda v: v.update(physical_authority=True),
        lambda v: v["samples"].pop(),
        lambda v: v["samples"][0].update(complete=False, target_present=None),
        lambda v: v["samples"][0].update(native_code=13),
        lambda v: v["samples"][0].update(used_chars=5),
        lambda v: v["finished"].update(monotonic_ms=2010),
        lambda v: v["finished"].update(utc_ns=1),
        lambda v: v.update(request_sha256="b" * 64),
        lambda v: v.update(filter=r"USB\VID_4321&PID_8765"),
        lambda v: v["samples"][0].update(
            instance_ids=[r"USB\VID_1234&PID_5678\UNIT_A"], used_chars=30
        ),
    ],
)
def test_rehashed_incomplete_changed_or_late_packets_cannot_claim_absence(mutation):
    value = modeled()
    mutation(value)
    with pytest.raises(ValueError):
        parse(value)


def test_a_different_same_model_unit_does_not_count_as_the_target():
    value = modeled()
    for sample in value["samples"]:
        sample["instance_ids"] = [r"USB\VID_1234&PID_5678\ANOTHER_UNIT"]
        sample["used_chars"] = len(sample["instance_ids"][0]) + 2
    assert parse(value).to_dict()["outcome"] == "ABSENT"


def test_missing_receipt_has_no_valid_absence_substitute():
    with pytest.raises(ValueError):
        module.UsbPresenceObservation(b"")
    value = modeled()
    value.update(outcome="HELD", error="ACQUISITION_DEADLINE", samples=[], api_calls=0)
    assert parse(value).to_dict()["samples"] == []


@pytest.fixture(scope="module")
def native_fixture():
    binary = (
        Path(__file__).resolve().parents[2]
        / "native/windows_usb_presence/build/Release/rocell_usb_presence_tests.exe"
    )
    if not binary.is_file():
        pytest.skip("build the separately linked native presence fixture first")
    return binary


@pytest.mark.parametrize(
    "scenario",
    [
        "absent",
        "same-model",
        "present",
        "mixed-case",
        "changed",
        "size-failed",
        "list-failed",
        "growth",
        "oversize",
        "zero-size",
        "unterminated",
        "wrong-filter",
        "duplicate",
        "many",
        "nonascii",
        "late-size",
        "late-list",
        "stop-size",
        "stop-list",
        "exception",
    ],
)
def test_native_incapable_outputs_are_accepted_without_relabeling(
    native_fixture, scenario
):
    result = subprocess.run(
        [str(native_fixture), "--wire", scenario],
        capture_output=True,
        timeout=5,
        check=True,
    )
    observed = module.UsbPresenceObservation(result.stdout).to_dict()
    assert observed["provider"] == "INCAPABLE_FIXTURE"
    assert observed["request"] == request().to_dict()
    assert observed["api_calls"] <= 4
    assert observed["physical_authority"] is False


def test_readiness_release_and_result_cannot_cross_bindings():
    r = request()
    ready = dict(
        schema=module.READY_SCHEMA,
        request_sha256=r.sha256,
        child_pid=50,
        challenge="c" * 64,
        permit_sha256=r.to_dict()["permit_sha256"],
    )
    release = module.encode_usb_presence_release(ready, r, child_pid=50)
    assert b"usb_presence_release.v1" in release
    result = dict(
        schema=module.RESULT_SCHEMA,
        request_sha256=r.sha256,
        child_pid=50,
        challenge_sha256=digest(ready["challenge"].encode("ascii")),
        permit_sha256=r.to_dict()["permit_sha256"],
        observation=modeled(),
    )
    kwargs = dict(
        child_pid=50,
        challenge=ready["challenge"],
        expected_provider="INCAPABLE_FIXTURE",
    )
    assert (
        module.decode_usb_presence_result(canonical(result), r, **kwargs).to_dict()
        == modeled()
    )
    for key in ("request_sha256", "permit_sha256", "challenge_sha256"):
        changed = deepcopy(result)
        changed[key] = "b" * 64
        with pytest.raises(ValueError):
            module.decode_usb_presence_result(canonical(changed), r, **kwargs)
    kwargs["expected_provider"] = "WINDOWS_CONFIGURATION_MANAGER"
    with pytest.raises(ValueError):
        module.decode_usb_presence_result(canonical(result), r, **kwargs)
