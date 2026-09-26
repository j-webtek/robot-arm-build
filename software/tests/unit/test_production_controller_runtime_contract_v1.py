"""Offline tests for the production controller runtime contract rehearsal."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.arm.all_joint_command import all_joint_command
from rocell.arm.protocol import encode_line
from rocell.application.production_controller_runtime_contract_v1 import (
    ProductionControllerRuntimeContractError,
    ProductionControllerRuntimeContractV1,
    ProductionControllerRuntimeManifestV1,
    ProductionRuntimeState,
    RuntimeCommandFrameV1,
)


WORKSPACE = Path(__file__).resolve().parents[3]
SESSION = "controller-session-1"
EPOCH = "d" * 64


def _manifest():
    return ProductionControllerRuntimeManifestV1(
        runtime_id="production-runtime-candidate-1",
        candidate_app_sha256="a" * 64,
        protocol_source_sha256="b" * 64,
        controller_joint_mapping_sha256="c" * 64,
        configuration_epoch_sha256=EPOCH,
        expected_encoding_profile_sha256="e" * 64,
        controller_session_id=SESSION,
    )


def _payload(offset=0.0):
    return encode_line(all_joint_command(
        [offset + value for value in (.1, .2, .3, .4, .5, .6)],
        speed=20, acceleration=1))


def _frame(sequence=1, **changes):
    values = dict(
        sequence=sequence,
        correlation_id=f"correlation-{sequence}",
        writer_instance_id="writer-1",
        controller_session_id=SESSION,
        configuration_epoch_sha256=EPOCH,
        encoding_profile_sha256="e" * 64,
        issued_monotonic_ns=100,
        expires_monotonic_ns=200,
        wire_bytes=_payload(sequence / 100),
    )
    values.update(changes)
    return RuntimeCommandFrameV1(**values)


def _ack(sequence=1):
    return encode_line({"T": 1021, "status": "ACCEPTED_ONCE", "ordinal": sequence})


def _schema(name):
    return json.loads((WORKSPACE / "software/ai/schemas" / name).read_text(
        encoding="utf-8"))


def test_startup_is_safe_idle_with_zero_commands_or_authority():
    manifest = _manifest()
    runtime = ProductionControllerRuntimeContractV1(manifest)
    report = runtime.report()
    assert runtime.state is ProductionRuntimeState.SAFE_IDLE
    assert report["status"] == "SAFE_IDLE"
    assert report["startup_motion_commands"] == 0
    assert report["transport_open_count"] == report["hardware_write_count"] == 0
    assert report["automatic_retry"] is report["replay_allowed"] is False
    assert report["hardware_access"] is report["physical_authority"] is False
    jsonschema.Draft202012Validator(_schema(
        "production_controller_runtime_manifest_v1.schema.json"
    )).validate(manifest.to_dict())
    jsonschema.Draft202012Validator(_schema(
        "production_controller_runtime_rehearsal_v1.schema.json"
    )).validate(report)


def test_one_writer_accepts_exact_ordered_t102_frames_without_writing():
    runtime = ProductionControllerRuntimeContractV1(_manifest())
    runtime.claim_writer("writer-1")
    first = runtime.admit_t102(_frame(1), now_monotonic_ns=150)
    assert runtime.report()["status"] == "AWAITING_COMMAND_ACKNOWLEDGMENT"
    runtime.rehearse_command_acknowledgment(_ack(1))
    second = runtime.admit_t102(_frame(2), now_monotonic_ns=150)
    runtime.rehearse_command_acknowledgment(_ack(2))
    report = runtime.report()
    assert (first.sequence, second.sequence) == (1, 2)
    assert report["status"] == "CONTRACT_REHEARSAL_READY"
    assert report["last_sequence"] == report["admission_count"] == 2
    assert report["acknowledgment_count"] == 2
    assert report["pending_ack_sequence"] is None
    assert all(item["arrival_proven"] is False
               for item in report["acknowledgments"])
    assert all(item["hardware_write_count"] == 0 for item in report["admissions"])
    assert report["hardware_write_count"] == 0


@pytest.mark.parametrize("changes", [
    {"writer_instance_id": "writer-2"},
    {"controller_session_id": "other-session"},
    {"configuration_epoch_sha256": "f" * 64},
    {"encoding_profile_sha256": "f" * 64},
    {"sequence": 2, "correlation_id": "correlation-2"},
    {"expires_monotonic_ns": 120},
    {"wire_bytes": b'{"T":105}\n'},
    {"wire_bytes": b'{"T":102,"base":0,"shoulder":0,"elbow":0,'
                   b'"wrist":0,"roll":0,"hand":0,"spd":20,"acc":1,'
                   b'"extra":0}\n'},
])
def test_invalid_frame_locks_runtime_without_retry(changes):
    runtime = ProductionControllerRuntimeContractV1(_manifest())
    runtime.claim_writer("writer-1")
    with pytest.raises(Exception):
        runtime.admit_t102(_frame(**changes), now_monotonic_ns=150)
    report = runtime.report()
    assert report["status"] == "TERMINAL_NO_RETRY"
    assert report["automatic_retry"] is report["replay_allowed"] is False
    assert report["hardware_write_count"] == 0
    with pytest.raises(ProductionControllerRuntimeContractError):
        runtime.admit_t102(_frame(), now_monotonic_ns=150)


def test_duplicate_sequence_is_terminal_and_never_replayed():
    runtime = ProductionControllerRuntimeContractV1(_manifest())
    runtime.claim_writer("writer-1")
    runtime.admit_t102(_frame(), now_monotonic_ns=150)
    runtime.rehearse_command_acknowledgment(_ack())
    with pytest.raises(ProductionControllerRuntimeContractError, match="sequence"):
        runtime.admit_t102(_frame(), now_monotonic_ns=150)
    assert runtime.report()["admission_count"] == 1
    assert runtime.state is ProductionRuntimeState.TERMINAL_LOCKED


def test_next_command_before_acknowledgment_is_terminal():
    runtime = ProductionControllerRuntimeContractV1(_manifest())
    runtime.claim_writer("writer-1")
    runtime.admit_t102(_frame(1), now_monotonic_ns=150)
    with pytest.raises(ProductionControllerRuntimeContractError, match="pending"):
        runtime.admit_t102(_frame(2), now_monotonic_ns=150)
    assert runtime.report()["status"] == "TERMINAL_NO_RETRY"


@pytest.mark.parametrize("response", [
    b'{"T":1021,"status":"ACCEPTED_ONCE","ordinal":2}\n',
    b'{"T":1021,"ordinal":1,"status":"ACCEPTED_ONCE"}\n',
    b'{"T":1021,"status":"ACCEPTED_ONCE","ordinal":1,"extra":0}\n',
    b'{"T":1021,"status":"ACCEPTED_ONCE","ordinal":1}\r\n',
    b'{"T":1051,"b":0,"s":0,"e":0,"t":0,"r":0,"g":0}\n',
])
def test_wrong_stale_or_noncanonical_acknowledgment_is_terminal(response):
    runtime = ProductionControllerRuntimeContractV1(_manifest())
    runtime.claim_writer("writer-1")
    runtime.admit_t102(_frame(1), now_monotonic_ns=150)
    with pytest.raises(Exception):
        runtime.rehearse_command_acknowledgment(response)
    assert runtime.report()["status"] == "TERMINAL_NO_RETRY"
    assert runtime.report()["automatic_retry"] is False


def test_acknowledgment_timeout_latches_uncertain_without_retry():
    runtime = ProductionControllerRuntimeContractV1(_manifest())
    runtime.claim_writer("writer-1")
    runtime.admit_t102(_frame(1), now_monotonic_ns=150)
    runtime.mark_command_acknowledgment_timeout()
    report = runtime.report()
    assert report["status"] == "TERMINAL_NO_RETRY"
    assert report["terminal_reason"] == "COMMAND_ACKNOWLEDGMENT_TIMEOUT_UNCERTAIN"
    assert report["admission_count"] == 1
    assert report["acknowledgment_count"] == 0


def test_feedback_is_forbidden_until_command_acknowledgment_consumed():
    runtime = ProductionControllerRuntimeContractV1(_manifest())
    runtime.claim_writer("writer-1")
    runtime.admit_t102(_frame(1), now_monotonic_ns=150)
    with pytest.raises(ProductionControllerRuntimeContractError, match="pending"):
        runtime.rehearse_feedback_exchange(
            b'{"T":105}\n',
            b'{"T":1051,"b":0,"s":0,"e":0,"t":0,"r":0,"g":0}\n',
        )
    assert runtime.report()["status"] == "TERMINAL_NO_RETRY"


def test_exact_t105_t1051_rehearsal_uses_same_claim_without_io():
    runtime = ProductionControllerRuntimeContractV1(_manifest())
    runtime.claim_writer("writer-1")
    runtime.rehearse_feedback_exchange(
        b'{"T":105}\n',
        b'{"T":1051,"b":0.1,"s":0.2,"e":0.3,"t":0.4,'
        b'"r":0.5,"g":0.6}\n',
    )
    report = runtime.report()
    assert report["feedback_exchange_count"] == 1
    assert report["transport_open_count"] == report["hardware_write_count"] == 0


@pytest.mark.parametrize("request_bytes,response_bytes", [
    (b'{"T":105,"extra":0}\n',
     b'{"T":1051,"b":0,"s":0,"e":0,"t":0,"r":0,"g":0}\n'),
    (b'{"T":105}\n', b'{"T":1051,"b":0}\n'),
    (b'{"T":105}\n', b'{"T":105}\n'),
])
def test_bad_feedback_exchange_locks_without_retry(request_bytes, response_bytes):
    runtime = ProductionControllerRuntimeContractV1(_manifest())
    runtime.claim_writer("writer-1")
    with pytest.raises(Exception):
        runtime.rehearse_feedback_exchange(request_bytes, response_bytes)
    assert runtime.report()["status"] == "TERMINAL_NO_RETRY"


def test_restart_after_claim_requires_reconciliation_and_accepts_nothing():
    runtime = ProductionControllerRuntimeContractV1(_manifest())
    runtime.claim_writer("writer-1")
    runtime.mark_restart_after_claim()
    report = runtime.report()
    assert report["state"] == "TERMINAL_LOCKED"
    assert report["terminal_reason"] == "RESTART_RECONCILIATION_REQUIRED"
    assert report["admission_count"] == 0
    with pytest.raises(ProductionControllerRuntimeContractError):
        runtime.admit_t102(_frame(), now_monotonic_ns=150)


def test_concurrent_writer_claim_allows_exactly_one_owner():
    runtime = ProductionControllerRuntimeContractV1(_manifest())

    def claim(writer):
        try:
            runtime.claim_writer(writer)
            return "CLAIMED"
        except ProductionControllerRuntimeContractError:
            return "REJECTED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, ("writer-1", "writer-2")))
    assert sorted(outcomes) == ["CLAIMED", "REJECTED"]


def test_report_schema_rejects_injected_physical_authority():
    runtime = ProductionControllerRuntimeContractV1(_manifest())
    report = runtime.report()
    report["physical_authority"] = True
    report["hardware_write_count"] = 1
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema(
            "production_controller_runtime_rehearsal_v1.schema.json"
        )).validate(report)
