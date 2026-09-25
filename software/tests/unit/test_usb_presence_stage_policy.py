"""Fixed policy tests only; no runtime/file inspection or device operation."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from rocell.application import usb_presence_stage_policy as m
from rocell.application import usb_identity_stage_policy as old
from rocell.providers.windows.usb_identity_protocol import canonical


def test_policy_is_additive_exact_and_inert(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("pure policy performed I/O")

    monkeypatch.setattr(Path, "open", denied)
    legacy = old.usb_identity_stage_policy()
    policy = m.usb_presence_stage_policy()
    data = policy.to_dict()
    assert data["action_id"] == "physical-native-usb-presence"
    assert data["intended_phase"] == "RECONNECT_ABSENCE"
    assert data["leases"] == ["CELL", "SESSION", "CAMERA"]
    assert data["budget"] == dict(
        timeout_ms=25000,
        maximum_output_bytes=131072,
        maximum_opens=0,
        maximum_reads=4,
        maximum_writes=0,
        maximum_frames=0,
        maximum_closes=0,
    )
    assert data["historical_catalog_modified"] is False
    assert data["physical_authority"] is False
    assert policy.sha256 != legacy.sha256
    assert old.usb_identity_stage_policy().payload == legacy.payload
    data["budget"]["maximum_reads"] = 1000
    assert policy.to_dict()["budget"]["maximum_reads"] == 4
    with pytest.raises(FrozenInstanceError):
        policy.payload = b"{}"


@pytest.mark.parametrize(
    "path,value",
    [
        (("revision",), True),
        (("maximum_list_characters",), 9000),
        (("sample_count",), 1),
        (("native_duration_ms",), 10000),
        (("intended_phase",), "BASELINE"),
        (("action_id",), old.POLICY_ACTION),
        (("worker_id",), "other"),
        (("composition",), old.POLICY_COMPOSITION),
        (("budget", "maximum_reads"), 5),
        (("budget", "maximum_opens"), 1),
        (("budget", "maximum_writes"), 1),
        (("budget", "maximum_frames"), 1),
        (("budget", "maximum_closes"), 1),
        (("budget", "timeout_ms"), 30000),
        (("budget", "maximum_output_bytes"), 131073),
        (("physical_authority",), 0),
        (("hardware_qualified",), True),
        (("automatic_retry_allowed",), True),
        (("original_trial_declaration_required",), False),
        (("new_trial_baseline_required",), False),
        (("selected_identity_is_phase_binding",), False),
        (("original_review_required",), False),
        (("durable_consumed_permit_required",), False),
        (("retained_owned_execution_required",), False),
        (("base_catalog_sha256",), "f" * 64),
        (("leases",), ["CELL", "SESSION", "ARM_CONTROLLER"]),
    ],
)
def test_exact_policy_rejects_rehashed_substitution(path, value):
    document = m.usb_presence_stage_policy().to_dict()
    target = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(m.UsbPresencePolicyError):
        m.UsbPresenceStagePolicy(canonical(document))


@pytest.mark.parametrize(
    "payload", [b"", b"{}", "{}", b"x" * 8193, b'{"schema":"x","schema":"y"}', b"[]"]
)
def test_bad_wire_is_not_policy(payload):
    with pytest.raises(m.UsbPresencePolicyError):
        m.UsbPresenceStagePolicy(payload)


def test_policy_inspection_checks_existing_catalog_without_changing_it(monkeypatch):
    from types import SimpleNamespace

    calls = []
    document = SimpleNamespace(
        source_sha256=m.CATALOG_SHA256,
        canonical_stage_order_sha256=m.STAGE_ORDER_SHA256,
    )
    monkeypatch.setattr(
        m,
        "load_physical_onboarding_stage_catalog",
        lambda path: calls.append(path) or document,
    )
    selected = Path("MODELED-WORKSPACE")
    assert (
        m.inspect_usb_presence_stage_policy(selected) == m.usb_presence_stage_policy()
    )
    assert calls == [selected]
    document.source_sha256 = "f" * 64
    with pytest.raises(m.UsbPresencePolicyError, match="CATALOG_CHANGED"):
        m.inspect_usb_presence_stage_policy(selected)
