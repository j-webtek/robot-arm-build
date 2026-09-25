"""Pure entry-evidence checks for the approved USB-only engineering test.

This is not a permit issuer. A caller must authenticate retained originals,
resolve fresh native identity, consume a durable attempt and use the registered
supervisor before device access. In particular, matching hashes prove byte
association, not the truth or authorship of an operator statement.
"""

from dataclasses import dataclass
import hashlib
import json
import re

from .arm_bench_qualification_contract import PassiveBenchRequest


POLICY_ID = "ROCELL-ARM-USB-PASSIVE-ENTRY-002"
SCHEMA = "rocell.passive_arm_entry_evidence.v1"
MAX_ORIGINAL_BYTES = 32768
MAX_SETUP_AGE_NS = 300_000_000_000

# These are evidence semantics, not selectable settings. The legacy request
# field electrical_isolation_review_sha256 binds this design review without
# upgrading it to measured isolation. Changing this policy needs a new review.
_FACTS = {
    "policy_id": POLICY_ID,
    "policy_approved": True,
    "power_basis": "OPERATOR_REPORTED_EXTERNAL_ADAPTER_DISCONNECTED",
    "electrical_basis": "VENDOR_DESIGN_REVIEW",
    "measured_isolation": "NOT_ESTABLISHED",
    "installed_firmware": "UNKNOWN",
    "reset_on_open": "POSSIBLE",
    "secured_and_clear": True,
    "canonical_commissioning_pass": False,
    "motion_or_contact_authority": False,
}
_REFS = (
    "entry_policy_sha256",
    "electrical_isolation_review_sha256",
    "received_unit_association_sha256",
    "operator_attestation_sha256",
    "native_metadata_review_sha256",
)


def _digest(value: object) -> bool:
    return (
        type(value) is str
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None
        and value != "0" * 64
    )


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate evidence field")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class PassiveEntryEvidence:
    """Detached bounded evidence envelope; constructing it performs no I/O."""

    payload: bytes

    def __post_init__(self):
        if (
            type(self.payload) is not bytes
            or not 0 < len(self.payload) <= MAX_ORIGINAL_BYTES
        ):
            raise ValueError("Expected bounded evidence bytes")
        try:
            value = json.loads(self.payload, object_pairs_hook=_strict_object)
            fields = {
                "schema",
                "attempt_id",
                "launch_id",
                "source_sha256",
                "setup_confirmed_monotonic_ns",
                "facts",
                "references",
            }
            if (
                type(value) is not dict
                or set(value) != fields
                or value["schema"] != SCHEMA
            ):
                raise ValueError("Unknown evidence fields")
            # Exact types matter: JSON 0/1 must not stand in for false/true.
            facts = value["facts"]
            if type(facts) is not dict or set(facts) != set(_FACTS):
                raise ValueError("Missing evidence limitations")
            if any(
                type(facts[k]) is not type(v) or facts[k] != v
                for k, v in _FACTS.items()
            ):
                raise ValueError("Unapproved evidence basis")
            for field in ("attempt_id", "launch_id"):
                if (
                    type(value[field]) is not str
                    or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value[field])
                    is None
                ):
                    raise ValueError("Invalid attempt identity")
            refs = value["references"]
            if (
                type(refs) is not dict
                or set(refs) != set(_REFS)
                or not all(_digest(v) for v in refs.values())
            ):
                raise ValueError("Invalid original references")
            if not _digest(value["source_sha256"]):
                raise ValueError("Invalid source reference")
            stamp = value["setup_confirmed_monotonic_ns"]
            if type(stamp) is not int or not 0 < stamp < 2**63:
                raise ValueError("Invalid setup clock")
            payload = json.dumps(
                value, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("ascii")
        except (ValueError, TypeError, RecursionError, UnicodeError) as error:
            raise ValueError("Invalid passive entry evidence") from error
        object.__setattr__(self, "payload", payload)

    def assess(
        self,
        request: PassiveBenchRequest,
        originals: dict[str, bytes],
        *,
        now_monotonic_ns: int,
    ) -> dict:
        """Check exact bytes and current-attempt association, never authenticate.

        The short freshness window is checked only within the bound live launch;
        a recovered file cannot renew it or make monotonic clocks portable.
        All originals must already have been read through bounded storage APIs.
        """
        if type(request) is not PassiveBenchRequest:
            raise ValueError("Exact request required")
        if type(now_monotonic_ns) is not int or not 0 < now_monotonic_ns < 2**63:
            raise ValueError("Invalid current clock")
        if type(originals) is not dict or set(originals) != set(_REFS):
            raise ValueError("Exact original set required")
        value, target = json.loads(self.payload), request.to_dict()
        blockers = []
        if target["mode"] != "physical":
            blockers.append("PHYSICAL_REQUEST_REQUIRED")
        for key in ("attempt_id", "launch_id"):
            if value[key] != target[key]:
                blockers.append(key.upper() + "_MISMATCH")
        if value["source_sha256"] != target["references"]["source_sha256"]:
            blockers.append("SOURCE_MISMATCH")
        age = now_monotonic_ns - value["setup_confirmed_monotonic_ns"]
        if not 0 <= age <= MAX_SETUP_AGE_NS:
            blockers.append("SETUP_CONFIRMATION_STALE_OR_FUTURE")
        for key in _REFS:
            raw = originals[key]
            if type(raw) is not bytes or not 0 < len(raw) <= MAX_ORIGINAL_BYTES:
                blockers.append(key.upper() + "_ORIGINAL_INVALID")
            elif hashlib.sha256(raw).hexdigest() != value["references"][key]:
                blockers.append(key.upper() + "_ORIGINAL_MISMATCH")
            if value["references"][key] != target["references"][key]:
                blockers.append(key.upper() + "_REQUEST_MISMATCH")
        return {
            "schema": "rocell.passive_arm_entry_assessment.v1",
            "policy_id": POLICY_ID,
            "status": "HELD" if blockers else "ASSOCIATED_NOT_AUTHENTICATED",
            "blockers": blockers,
            "evidence_sha256": hashlib.sha256(self.payload).hexdigest(),
            "references_authenticated": False,
            "physical_authority": False,
            "connected": False,
            "physical_dispatch_available": False,
        }
