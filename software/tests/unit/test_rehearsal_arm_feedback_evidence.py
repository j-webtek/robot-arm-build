"""Lossless evidence tests use the real worker with sealed memory-only serial."""

from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from threading import Event
from typing import Any

import pytest

from rocell.application import rehearsal_arm_feedback_evidence as evidence
from rocell.application.physical_connection_contracts import (
    EvidenceOrigin,
    RoArmUsbSerialIdentity,
    SingleT105FeedbackRequest,
    UsbDriverIdentity,
)
from rocell.providers.windows import arm_feedback_worker as arm


SOURCE = "8" * 64
BINDING = "b" * 64


class Clock:
    value = 1_000_000_000

    def __call__(self):
        self.value += 1
        return self.value

    def wait(self, event, seconds):
        self.value += int(seconds * 1_000_000_000)
        return event.is_set()


def request(clock: Clock, maximum_line_bytes: int = 2048):
    identity = RoArmUsbSerialIdentity(
        "ffff",
        "0002",
        "SYNTHETIC-NOT-PHYSICAL",
        "USB\\VID_FFFF&PID_0002\\SYNTHETIC-NOT-PHYSICAL",
        "usb-unit:ffff:0002:SYNTHETIC-NOT-PHYSICAL",
        "COM404",
        UsbDriverIdentity("SYNTHETIC", "memory-only", "1.0", "not-installed.inf"),
    )
    controller = arm.ReviewedControllerBinding(
        identity,
        "1" * 64,
        "2" * 64,
        "3" * 64,
        "4" * 64,
        "5" * 64,
        EvidenceOrigin.SYNTHETIC_REHEARSAL,
    )
    feedback = SingleT105FeedbackRequest(
        "fixture-run",
        controller.identity_receipt_sha256,
        identity.identity_sha256,
        "6" * 64,
        "7" * 64,
        "fixture-controller-session",
        clock.value,
        maximum_line_bytes,
    )
    return arm.ArmFeedbackCampaignRequest(
        "fixture-campaign",
        SOURCE,
        "9" * 64,
        "a" * 64,
        controller,
        feedback,
        clock.value + 30_000_000_000,
    )


def run(
    scenario=arm.IncapableSerialScenario(),
    *,
    maximum_line_bytes=2048,
    cancel=False,
    resolver=None,
):
    clock = Clock()
    req = request(clock, maximum_line_bytes)
    backend = arm.IncapableSerialBackend(scenario)
    acknowledged = False

    def authorize(observed):
        nonlocal acknowledged
        assert not acknowledged and observed is req
        acknowledged = True

    worker = arm.ArmFeedbackWorker(
        authorizer=authorize,
        identity_resolver=resolver or (lambda expected: expected),
        backend=backend,
        monotonic_ns=clock,
        wait=clock.wait,
    )
    cancelled = Event()
    if cancel:
        cancelled.set()
    result = worker.run(req, cancellation=cancelled)
    return req, result, backend


def retain(req, result):
    return evidence.retain_rehearsal_arm_feedback_evidence(
        req, result, binding_sha256=BINDING, source_sha256=SOURCE
    )


def encoded(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def verify(document, req, *, trusted_hash=None, **kwargs):
    payload = encoded(document)
    return evidence.verify_rehearsal_arm_feedback_evidence(
        payload,
        expected_request=req,
        expected_binding_sha256=BINDING,
        expected_evidence_sha256=trusted_hash or hashlib.sha256(payload).hexdigest(),
        expected_source_sha256=SOURCE,
        **kwargs,
    )


@pytest.fixture(scope="module")
def nominal():
    req, result, backend = run()
    return req, result, retain(req, result), backend


def test_actual_lifecycle_complete_lossless_round_trip(nominal):
    req, result, retained, backend = nominal
    assert [row[0] for row in backend.trace].count("write") == 1
    assert retained.result == result
    assert (
        verify(
            retained.to_dict(), req, trusted_hash=retained.evidence_sha256
        ).canonical_bytes()
        == retained.canonical_bytes()
    )
    document = retained.to_dict()
    assert set(document["result"]) == set(
        arm.ArmFeedbackCampaignResult.__dataclass_fields__
    )
    assert (
        document["result"]["feedback_receipt"]["timing"]
        == result.feedback_receipt.timing.to_dict()
    )
    assert (
        document["result"]["feedback_receipt"]["receipt_sha256"]
        == result.feedback_receipt.receipt_sha256
    )
    assert document["result"]["feedback_receipt"]["wire_references"] == {
        "request": "request.wire_request_hex",
        "response": "result.response_bytes",
    }
    assert (
        bytes.fromhex(document["result"]["response_bytes"]["bytes_hex"])
        == result.response_bytes
    )
    assert (
        retained.result.feedback_receipt.to_dict() == result.feedback_receipt.to_dict()
    )
    summary = retained.safe_summary()
    assert summary["technical_response_valid"] is True
    assert summary["feedback_receipt_valid"] is True
    assert summary["serial_cleanup_confirmed"] is True
    assert summary["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    assert summary["physical_authority"] is False
    assert document["authority"]["stage_advance_authority"] is False
    assert "outcome" not in document  # no stage assessment manufactured


@pytest.mark.parametrize(
    "scenario",
    [
        arm.IncapableSerialScenario(preexisting_bytes=b"secret-boot\n"),
        arm.IncapableSerialScenario(short_write_count=1),
        arm.IncapableSerialScenario(response_bytes=b""),
        arm.IncapableSerialScenario(response_bytes=b"not-json\n"),
        arm.IncapableSerialScenario(response_bytes=b'{"T":104}\n'),
        arm.IncapableSerialScenario(response_bytes=b'{"T":1051}\nextra\n'),
        arm.IncapableSerialScenario(response_bytes=b"\xff\n"),
        arm.IncapableSerialScenario(fail_at=("close",)),
        arm.IncapableSerialScenario(fail_at=("configure",)),
        arm.IncapableSerialScenario(fail_at=("open",)),
        arm.IncapableSerialScenario(fail_at=("write",)),
        arm.IncapableSerialScenario(fail_at=("read",)),
        arm.IncapableSerialScenario(already_open=True),
        arm.IncapableSerialScenario(close_remains_open=True),
        arm.IncapableSerialScenario(read_returns_nonbytes=True),
    ],
    ids=[
        "boot",
        "short",
        "timeout",
        "json",
        "wrong-type",
        "extra",
        "binary",
        "close",
        "configure",
        "open",
        "write",
        "read",
        "already-open",
        "still-open",
        "nonbytes",
    ],
)
def test_actual_fault_results_retain_without_fabricated_timing(scenario):
    req, result, _ = run(scenario)
    retained = retain(req, result)
    assert retained.result == result
    assert retained.safe_summary()["feedback_receipt_valid"] is False
    assert retained.to_dict()["result"]["feedback_receipt"] is None
    assert retained.safe_summary()["timing"]["transaction_timing_available"] is False
    assert (
        retained.safe_summary()["final_power_state"]
        == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    )
    assert verify(retained.to_dict(), req).result == result


def test_close_failure_preserves_valid_response_but_not_successful_receipt():
    req, result, _ = run(arm.IncapableSerialScenario(fail_at=("close",)))
    summary = retain(req, result).safe_summary()
    assert summary["technical_response_valid"] is True
    assert summary["serial_cleanup_confirmed"] is False
    assert summary["feedback_receipt_valid"] is False
    assert summary["effect_uncertain"] is True
    assert summary["worker_outcome"] == "FAILED_UNCERTAIN"


def test_valid_packet_with_buffered_suffix_keeps_both_byte_streams():
    packet = b'{"T":1051,"x":1}\n'
    suffix = b"INCAPABLE-sensitive-suffix"
    req, result, _ = run(
        arm.IncapableSerialScenario(
            response_bytes=packet + suffix, read_fragment_bytes=len(packet)
        )
    )
    retained = retain(req, result)
    assert retained.result.response_bytes == packet
    assert retained.result.unexpected_bytes == suffix[: len(packet)]
    assert retained.safe_summary()["technical_response_valid"] is True
    assert retained.safe_summary()["feedback_receipt_valid"] is False
    assert retained.safe_summary()["serial_cleanup_confirmed"] is True
    assert retained.safe_summary()["effect_uncertain"] is True


def test_actual_overlong_response_preserves_detection_byte():
    req, result, _ = run(arm.IncapableSerialScenario(response_bytes=b"x" * 2050))
    retained = retain(req, result)
    assert len(retained.result.response_bytes) == req.feedback.maximum_line_bytes + 1
    assert retained.safe_summary()["technical_response_valid"] is False
    assert retained.safe_summary()["worker_outcome"] == "FAILED_UNCERTAIN"


def test_oversized_write_api_return_stays_distinct_from_confirmed_bytes():
    req, result, _ = run(arm.IncapableSerialScenario(short_write_count=11))
    retained = retain(req, result)
    assert retained.result.write_api_returned_count == 11
    assert retained.result.api_counts.write_attempts == 1
    assert retained.result.api_counts.write_bytes_confirmed == 0
    assert retained.result.api_counts.writes_confirmed == 0


def test_preopen_cancel_has_zero_effect_counts_and_no_invented_close():
    req, result, backend = run(cancel=True)
    retained = retain(req, result)
    assert backend.trace == ()
    assert result.outcome is arm.ArmFeedbackOutcome.CANCELLED_PRE_OPEN
    assert retained.safe_summary()["serial_cleanup_confirmed"] is False
    assert all(value == 0 for value in retained.safe_summary()["api_counts"].values())


def test_identity_change_keeps_zero_writes():
    calls = 0

    def resolver(expected):
        nonlocal calls
        calls += 1
        return replace(expected, port_name="COM405") if calls == 2 else expected

    req, result, _ = run(resolver=resolver)
    retained = retain(req, result)
    assert retained.result.api_counts.write_attempts == 0
    assert (
        retained.safe_summary()["primary_error"]["code"]
        == "CONTROLLER_IDENTITY_CHANGED"
    )


def test_prefix_omission_is_explicit_and_hash_bound():
    secret = b"INCAPABLE-secret-not-for-logs\n" * 80
    req, result, _ = run(arm.IncapableSerialScenario(preexisting_bytes=secret))
    retained = retain(req, result)
    doc = retained.to_dict()
    assert result.api_counts.write_attempts == 0
    assert result.unexpected_bytes_unretained > 0
    accounting = doc["wire_accounting"]
    assert accounting["unexpected_retention"] == "BOUNDED_PREFIX_WITH_OMISSIONS"
    assert accounting["unexpected_observed_bytes"] == len(secret)
    assert accounting["unexpected_retained_prefix_bytes"] + accounting[
        "unexpected_unretained_observed_bytes"
    ] == len(secret)
    assert secret[:256] == retained.result.unexpected_bytes
    assert "INCAPABLE-secret" not in str(retained.safe_summary())
    assert secret[:16].hex() not in str(retained.safe_summary())


def test_unknown_response_fields_remain_lossless_and_private():
    wire = b'{"T":1051,"x":1,"future":{"credential":"do-not-display"}}\n'
    req, result, _ = run(arm.IncapableSerialScenario(response_bytes=wire))
    retained = retain(req, result)
    assert retained.result.feedback_receipt.response_bytes == wire
    assert retained.safe_summary()["technical_response_valid"] is True
    assert "do-not-display" not in str(retained.safe_summary())
    assert b"do-not-display".hex() not in str(retained.safe_summary())


def test_maximum_wire_evidence_stays_bounded_without_duplicate_receipt_bytes():
    wire = b'{"T":1051,"unknown":"' + b"x" * 65_500 + b'"}\n'
    req, result, _ = run(
        arm.IncapableSerialScenario(response_bytes=wire, read_fragment_bytes=1024),
        maximum_line_bytes=65536,
    )
    retained = retain(req, result)
    assert len(retained.canonical_bytes()) < evidence.MAX_EVIDENCE_BYTES
    assert retained.result.response_bytes == wire
    assert retained.result.feedback_receipt.response_bytes == wire
    assert retained.canonical_bytes().count(wire.hex().encode()) == 1


def test_verification_is_pure_no_worker_or_file_calls(nominal, monkeypatch):
    req, _, retained, _ = nominal

    def forbidden(*args, **kwargs):
        raise AssertionError("verification replay or filesystem I/O")

    monkeypatch.setattr(arm.ArmFeedbackWorker, "run", forbidden)
    monkeypatch.setattr(arm.IncapableSerialBackend, "create_closed", forbidden)
    monkeypatch.setattr(arm, "rehearse_arm_feedback_campaign", forbidden)
    for name in ("open", "read_bytes", "read_text", "stat", "resolve"):
        monkeypatch.setattr(Path, name, forbidden)
    assert verify(
        retained.to_dict(), req, trusted_hash=retained.evidence_sha256
    ).result.response_bytes


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_sha256", "0" * 64),
        ("binding_sha256", "c" * 64),
        ("request_sha256", "c" * 64),
        ("controller_binding_sha256", "c" * 64),
        ("schema", "future.v2"),
    ],
)
def test_top_level_binding_and_schema_tampering(nominal, field, value):
    req, _, retained, _ = nominal
    doc = retained.to_dict()
    doc[field] = value
    with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
        verify(doc, req)


@pytest.mark.parametrize(
    "field",
    [
        "campaign_id",
        "source_sha256",
        "operation_sha256",
        "energization_envelope_sha256",
    ],
)
def test_exact_expected_request_cannot_be_substituted(nominal, field):
    req, _, retained, _ = nominal
    changed = replace(
        req, **{field: "other-campaign" if field == "campaign_id" else "c" * 64}
    )
    with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
        verify(retained.to_dict(), changed)


@pytest.mark.parametrize("field", list(arm.SerialApiCounts.__dataclass_fields__))
@pytest.mark.parametrize("value", [True, -1, 100_000])
def test_counter_types_and_bounds(nominal, field, value):
    req, result, _, _ = nominal
    bad = replace(result, api_counts=replace(result.api_counts, **{field: value}))
    with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
        retain(req, bad)


@pytest.mark.parametrize(
    "field,value",
    [
        ("connection_closed", 1),
        ("elapsed_ns", True),
        ("opened_monotonic_ns", False),
        ("closed_monotonic_ns", 0),
        ("unexpected_bytes_unretained", True),
        ("write_api_returned_count", True),
        ("request_sha256", "c" * 64),
        ("response_bytes", b'{"T":104}\n'),
        ("unexpected_bytes", b"unobserved"),
        ("outcome", arm.ArmFeedbackOutcome.FAILED_UNCERTAIN),
    ],
)
def test_result_contradictions_rejected(nominal, field, value):
    req, result, _, _ = nominal
    with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
        retain(req, replace(result, **{field: value}))


def test_settings_order_and_duplicate_pairs_are_not_silently_collapsed(nominal):
    req, result, _, _ = nominal
    before = result.settings_before_open
    for bad in (
        before + (before[0],),
        tuple(reversed(before)),
        (),
        (("port", "COM1"),),
    ):
        with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
            retain(req, replace(result, settings_before_open=bad))


def test_failed_result_counter_relationships_remain_strict():
    req, result, _ = run(arm.IncapableSerialScenario(fail_at=("configure",)))
    with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError, match="identity"):
        retain(
            req,
            replace(result, api_counts=replace(result.api_counts, identity_checks=0)),
        )
    with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError, match="read lacks"):
        retain(
            req, replace(result, api_counts=replace(result.api_counts, read_attempts=1))
        )


def test_missing_or_unbounded_cleanup_diagnostics_rejected(nominal):
    req, result, _, _ = nominal
    for errors in (
        (None,),
        (arm.SerialLifecycleError("CLOSE_UNCONFIRMED", "CLOSING", "ValueError"),) * 9,
    ):
        with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
            retain(req, replace(result, cleanup_errors=errors))


@pytest.mark.parametrize("field", list(evidence._TIMING_FIELDS))
def test_transaction_timestamp_boolean_rejected(nominal, field):
    req, _, retained, _ = nominal
    doc = retained.to_dict()
    doc["result"]["feedback_receipt"]["timing"][field] = True
    with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
        verify(doc, req)


def test_raw_hash_length_reference_and_timing_tampering(nominal):
    req, _, retained, _ = nominal
    for kind in (
        "wire",
        "wire-hash",
        "wire-count",
        "reference",
        "receipt-hash",
        "timing",
        "quiet",
    ):
        doc = retained.to_dict()
        if kind == "wire":
            doc["result"]["response_bytes"]["bytes_hex"] = (
                "ff" + doc["result"]["response_bytes"]["bytes_hex"][2:]
            )
        elif kind == "wire-hash":
            doc["result"]["response_bytes"]["sha256"] = "f" * 64
        elif kind == "wire-count":
            doc["result"]["response_bytes"]["retained_bytes"] += 1
        elif kind == "reference":
            doc["result"]["feedback_receipt"]["wire_references"][
                "response"
            ] = "elsewhere"
        elif kind == "receipt-hash":
            doc["result"]["feedback_receipt"]["receipt_sha256"] = "f" * 64
        else:
            timing = doc["result"]["feedback_receipt"]["timing"]
            timing[
                (
                    "port_closed_monotonic_ns"
                    if kind == "timing"
                    else "pre_request_buffer_observed_monotonic_ns"
                )
            ] = 1
        with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
            verify(doc, req)


@pytest.mark.parametrize(
    "location",
    [
        "root",
        "request",
        "result",
        "receipt",
        "counts",
        "summary",
        "authority",
        "provenance",
    ],
)
def test_unknown_fields_fail_closed(nominal, location):
    req, _, retained, _ = nominal
    doc = retained.to_dict()
    targets = {
        "root": doc,
        "request": doc["request"],
        "result": doc["result"],
        "receipt": doc["result"]["feedback_receipt"],
        "counts": doc["result"]["api_counts"],
        "summary": doc["safe_summary"],
        "authority": doc["authority"],
        "provenance": doc["provenance"],
    }
    targets[location]["unknown"] = True
    with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
        verify(doc, req)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"[]",
        b'{"a":1,"a":2}',
        b'{"a":NaN}',
        b"\xff",
        b" " * (evidence.MAX_EVIDENCE_BYTES + 1),
        b'{"a":' + b"[" * 22 + b"0" + b"]" * 22 + b"}",
        encoded({"a": [0] * 65}),
    ],
    ids=["empty", "array", "duplicate", "nan", "utf8", "oversize", "deep", "wide"],
)
def test_bounded_json(nominal, payload):
    req = nominal[0]
    with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
        evidence.verify_rehearsal_arm_feedback_evidence(
            payload,
            expected_request=req,
            expected_binding_sha256=BINDING,
            expected_evidence_sha256="e" * 64,
            expected_source_sha256=SOURCE,
        )


def test_physical_result_or_request_never_admitted(nominal):
    req, result, _, _ = nominal
    physical = replace(
        req,
        controller=replace(req.controller, origin=EvidenceOrigin.PHYSICAL_OBSERVATION),
    )
    with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
        retain(req, replace(result, origin=EvidenceOrigin.PHYSICAL_OBSERVATION))
    with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
        retain(physical, replace(result, request_sha256=physical.request_sha256))


def test_summary_tampering_cannot_promote_power_or_stage(nominal):
    req, _, retained, _ = nominal
    for field, value in (
        ("final_power_state", "DEENERGIZED"),
        ("physical_authority", True),
        ("serial_cleanup_confirmed", 1),
        ("installed_firmware_proven_by_packet", True),
    ):
        doc = retained.to_dict()
        doc["safe_summary"][field] = value
        with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
            verify(doc, req)


def test_trusted_hash_required_even_for_semantically_consistent_reseal(nominal):
    req, _, retained, _ = nominal
    doc = retained.to_dict()
    # Binding changes are coherent only if the independently supplied expected
    # context also changes; even then the original trusted evidence hash rejects.
    doc["binding_sha256"] = "d" * 64
    doc["safe_summary"]["binding_sha256"] = "d" * 64
    with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
        evidence.verify_rehearsal_arm_feedback_evidence(
            encoded(doc),
            expected_request=req,
            expected_binding_sha256="d" * 64,
            expected_evidence_sha256=retained.evidence_sha256,
            expected_source_sha256=SOURCE,
        )


def test_builder_source_and_context_are_not_implicitly_filled(nominal):
    req, result, _, _ = nominal
    with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
        evidence.retain_rehearsal_arm_feedback_evidence(
            req, result, binding_sha256=BINDING, source_sha256="f" * 64
        )
    with pytest.raises(evidence.RehearsalArmFeedbackEvidenceError):
        evidence.retain_rehearsal_arm_feedback_evidence(
            req, result, binding_sha256="0" * 64, source_sha256=SOURCE
        )


def test_immutable_data_and_summary_copies(nominal):
    retained = nominal[2]
    before = retained.canonical_bytes()
    retained.to_dict()["result"]["response_bytes"]["bytes_hex"] = "00"
    retained.safe_summary()["physical_authority"] = True
    assert retained.canonical_bytes() == before
    assert retained.safe_summary()["physical_authority"] is False
