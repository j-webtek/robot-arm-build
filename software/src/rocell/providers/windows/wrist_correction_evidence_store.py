"""Bounded correction evidence staging and loading; no native device access.

Only generated, content-addressed filenames are read. A partial staging attempt
is retained, never repaired or overwritten automatically. Loading returns
immutable original bytes, not a claim that a process or motion is admitted.
"""
from dataclasses import dataclass
from pathlib import Path

from rocell.application.physical_onboarding_durability import (
    safe_root, contained_path, read_bounded_regular_file, publish_reservation_bytes)
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from rocell.safety.wrist_correction_review_authority import WristCorrectionReviewAuthority
from .wrist_correction_native_protocol import validate_payload, verify_originals, require


@dataclass(frozen=True, slots=True)
class CorrectionEvidence:
    originals: tuple
    plan_raw: bytes


def _root(payload, assigned_root):
    validate_payload(payload)
    root = safe_root(assigned_root)
    require(root == Path(payload['root']), 'Correction evidence root differs from assigned root')
    return root


def _names(payload):
    prefix = payload['context']['attempt_id']
    rows = [(prefix+'-evidence-'+row['request_sha256']+'.request.json',
             prefix+'-evidence-'+row['trial_sha256']+'.trial.json') for row in payload['originals']]
    return rows, prefix+'-wrist-correction-plan-review.json'


def stage_evidence(payload, *, assigned_root, originals, plan_raw):
    """Retain validated fingerprints before launch, preserving any failed tail."""
    root = _root(payload, assigned_root)
    verify_originals(payload, originals=originals, plan_raw=plan_raw)
    names, plan_name = _names(payload)
    for (request_name, trial_name), (request, raw) in zip(names, originals):
        publish_reservation_bytes(root, request_name, request.canonical_bytes, maximum_bytes=8192)
        publish_reservation_bytes(root, trial_name, raw, maximum_bytes=512*1024)
    # Publishing the plan last does not turn this into launch admission.
    publish_reservation_bytes(root, plan_name, plan_raw, maximum_bytes=65536)
    return load_evidence(payload, assigned_root=root)


def load_evidence(payload, *, assigned_root):
    root = _root(payload, assigned_root)
    names, plan_name = _names(payload)
    def read(name, maximum):
        return read_bounded_regular_file(contained_path(root, name, label='correction original'),
            maximum_bytes=maximum)
    originals = [(AbsoluteWristIntent(read(a,8192)), read(b,512*1024)) for a,b in names]
    plan_raw = read(plan_name,65536)
    verify_originals(payload, originals=originals, plan_raw=plan_raw)
    return CorrectionEvidence(tuple(originals), plan_raw)


def authenticate_evidence(payload, *, assigned_root, authority, now_ns):
    """Reload originals and verify the exact signed plan; still no IO permit."""
    require(type(authority) is WristCorrectionReviewAuthority, 'Exact correction authority required')
    evidence = load_evidence(payload, assigned_root=assigned_root)
    authority.verify_plan(evidence.plan_raw, context=payload['context'],
        originals=list(evidence.originals), now_ns=now_ns, expected_basis=payload['expected_basis'])
    return evidence
