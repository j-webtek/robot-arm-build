"""Bind a retained wizard setup to one exact passive engineering request.

No native APIs, processes or permits are created here. The service must supply
its retained setup hash and closed runtime registration; a browser cannot choose
paths or supply these references. This helper never renews the setup timestamp.
"""

import base64
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import re

from .arm_bench_qualification_contract import (
    PassiveBenchRequest,
    SCHEMA,
    PURPOSE,
    _LIMITS,
    _canonical,
)
from .passive_arm_entry_policy import (
    PassiveEntryEvidence,
    SCHEMA as ENTRY_SCHEMA,
    _FACTS,
)
from .passive_arm_identity import PassiveControllerSelection
from .physical_onboarding_durability import contained_path, read_bounded_regular_file
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from . import wizard_native_arm_metadata as metadata
from .passive_arm_attempt_store import PassiveAttemptJournal
from rocell.providers.windows.nonpurging_serial_api import DcbSettings, CommTimeouts


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class PreparedPassiveAttempt:
    request: PassiveBenchRequest
    evidence: PassiveEntryEvidence
    selection: PassiveControllerSelection
    journal: PassiveAttemptJournal


def prepare_attempt(
    *,
    root,
    setup_operation_id,
    expected_setup_sha256,
    session_id,
    source_sha256,
    attempt_id,
    registration,
    deadline_ns,
    now_monotonic_ns
):
    """Read the named original, validate all associations, and retain intent.

    Creating this record does not consume it or dispatch a worker. A missing,
    stale, changed or foreign-launch setup fails before journal publication.
    """
    if (
        type(setup_operation_id) is not str
        or re.fullmatch(r"operation-[a-f0-9]{32}", setup_operation_id) is None
    ):
        raise ValueError("Exact service setup operation required")
    path = contained_path(
        Path(root),
        setup_operation_id + "-passive-setup-original.json",
        label="passive setup original",
    )
    raw = read_bounded_regular_file(path, maximum_bytes=1024 * 1024)
    if _hash(raw) != expected_setup_sha256:
        raise ValueError("Setup original differs from service receipt")
    original = decode_diagnostic_json(raw, maximum=1024 * 1024)
    fields = {
        "schema",
        "session_id",
        "operation_id",
        "source_sha256",
        "recorded_monotonic_ns",
        "operator_report",
        "measured_isolation",
        "reset_on_open",
        "generic_review",
        "native_report",
        "documents",
        "connected",
        "physical_authority",
        "replay_allowed",
    }
    if (
        type(original) is not dict
        or set(original) != fields
        or _canonical(original) != raw
    ):
        raise ValueError("Invalid canonical setup original")
    if (
        original["schema"] != "rocell.wizard_passive_arm_setup_original.v1"
        or original["session_id"] != session_id
        or original["operation_id"] != setup_operation_id
        or original["source_sha256"] != source_sha256
        or original["connected"] is not False
        or original["physical_authority"] is not False
        or original["replay_allowed"] is not False
        or original["measured_isolation"] != "NOT_ESTABLISHED"
        or original["reset_on_open"] != "POSSIBLE"
    ):
        raise ValueError("Setup launch/source/evidence basis mismatch")
    operator = original["operator_report"]
    if type(operator) is not dict or set(operator) != {
        "operator_id",
        "external_adapter_disconnected",
        "secured_and_clear",
        "model_association",
        "model_association_basis",
    }:
        raise ValueError("Invalid operator original")
    if (
        type(operator["operator_id"]) is not str
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", operator["operator_id"])
        is None
        or operator["external_adapter_disconnected"] is not True
        or operator["secured_and_clear"] is not True
        or operator["model_association"] != "RoArm-M3 Pro"
        or operator["model_association_basis"]
        != "PREVIOUS_OPERATOR_REPORT_NOT_NEW_INSPECTION"
    ):
        raise ValueError("Explicit USB-only operator basis required")
    native = original["native_report"]
    rebuilt = metadata.correlate_native_arm_metadata(
        native["snapshot"],
        original["generic_review"],
        mode="physical",
        session_id=session_id,
        source_sha256=source_sha256,
        operation_id=native["binding"]["operation_id"],
    )
    if (
        _canonical(native) != _canonical(rebuilt)
        or rebuilt["status"] != "METADATA_CORRELATED"
    ):
        raise ValueError("Setup metadata originals do not correlate")
    documents = original["documents"]
    names = {
        "ARM_USB_ONLY_ENTRY_POLICY_PROPOSAL.md",
        "ARM_USB_ELECTRICAL_DESIGN_REVIEW.md",
    }
    if type(documents) is not dict or set(documents) != names:
        raise ValueError("Exact policy and design originals required")
    decoded = {}
    for name, document in documents.items():
        if type(document) is not dict or set(document) != {"sha256", "base64"}:
            raise ValueError("Invalid document original")
        data = base64.b64decode(document["base64"], validate=True)
        if not 0 < len(data) <= 32768 or _hash(data) != document["sha256"]:
            raise ValueError("Design/policy original hash mismatch")
        decoded[name] = data
    policy = decoded["ARM_USB_ONLY_ENTRY_POLICY_PROPOSAL.md"]
    if (
        b"ROCELL-ARM-USB-PASSIVE-ENTRY-002" not in policy
        or b"USER APPROVED; IMPLEMENTATION IN PROGRESS; NO PHYSICAL RELEASE"
        not in policy
    ):
        raise ValueError("Approved entry policy original required")
    association = _canonical(
        {
            "setup_sha256": expected_setup_sha256,
            "operator_model_report": operator["model_association"],
            "native_report_sha256": native["report_sha256"],
        }
    )
    attestation = _canonical(
        {
            "setup_sha256": expected_setup_sha256,
            "operator_report": operator,
            "recorded_monotonic_ns": original["recorded_monotonic_ns"],
        }
    )
    originals = {
        "entry_policy_sha256": policy,
        "electrical_isolation_review_sha256": decoded[
            "ARM_USB_ELECTRICAL_DESIGN_REVIEW.md"
        ],
        "received_unit_association_sha256": association,
        "operator_attestation_sha256": attestation,
        "native_metadata_review_sha256": _canonical(native),
    }
    refs = {key: _hash(data) for key, data in originals.items()}
    refs.update(
        source_sha256=source_sha256,
        runtime_sha256=_hash(_canonical(registration)),
        serial_profile_sha256=_hash(
            _canonical(
                {"dcb": asdict(DcbSettings()), "timeouts": asdict(CommTimeouts())}
            )
        ),
    )
    request = PassiveBenchRequest(
        _canonical(
            dict(
                schema=SCHEMA,
                purpose=PURPOSE,
                attempt_id=attempt_id,
                launch_id=session_id,
                mode="physical",
                references=refs,
                parent_deadline_monotonic_ns=deadline_ns,
                limits=dict(_LIMITS),
            )
        )
    )
    evidence = PassiveEntryEvidence(
        _canonical(
            dict(
                schema=ENTRY_SCHEMA,
                attempt_id=attempt_id,
                launch_id=session_id,
                source_sha256=source_sha256,
                setup_confirmed_monotonic_ns=original["recorded_monotonic_ns"],
                facts=dict(_FACTS),
                references={key: refs[key] for key in originals},
            )
        )
    )
    journal = PassiveAttemptJournal(
        root,
        request,
        evidence,
        originals,
        registration,
        now_monotonic_ns=now_monotonic_ns,
    )
    return PreparedPassiveAttempt(
        request, evidence, PassiveControllerSelection(_canonical(native)), journal
    )
