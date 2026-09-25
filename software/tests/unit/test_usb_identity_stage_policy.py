"""Policy/selection codecs are pure and cannot approve their own provenance."""

from pathlib import Path
import json

import pytest

from rocell.application import usb_identity_stage_policy as m


def identity_document():
    hashes = {key: "a" * 64 for key in m._IDENTITY_HASHES}
    hashes.update(
        stage_policy_sha256=m.usb_identity_stage_policy().sha256,
        policy_review_sha256="b" * 64,
        runtime_review_sha256="c" * 64,
    )
    subjects = []
    for role, char in zip(("metadata", "policy_review", "runtime_review"), "abc"):
        sha = char * 64
        subjects.append(
            dict(
                role=role,
                document_sha256=sha,
                reference=dict(
                    evidence_id="evidence-" + sha,
                    stage="camera_identity",
                    package_sha256=sha,
                    manifest_sha256=sha,
                    payload_sha256=sha,
                    payload_bytes=100,
                ),
            )
        )
    return dict(
        schema=m.IDENTITY_SCHEMA,
        cell_id="wizard-physical-camera-" + "1" * 16,
        session_id="physical-camera-" + "2" * 32,
        original_subjects=subjects,
        **hashes,
    )


def review_document():
    policy = m.usb_identity_stage_policy()
    return dict(
        schema=m.REVIEW_SCHEMA,
        cell_id="wizard-physical-camera-" + "1" * 16,
        session_id="physical-camera-" + "2" * 32,
        source_sha256="3" * 64,
        header_sha256="4" * 64,
        policy=policy.to_dict(),
        policy_sha256=policy.sha256,
        operator_id="collector",
        reviewer_id="reviewer",
        reviewed_at_utc_ns=1,
        purpose="REVIEW_EXACT_USB_QUERY_POLICY_ONLY",
        **m._FLAGS,
    )


def test_policy_inert_and_detached(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("pure codec performed a file lookup")

    monkeypatch.setattr(Path, "open", forbidden)
    policy = m.usb_identity_stage_policy()
    doc = policy.to_dict()
    doc["budget"]["maximum_writes"] = 1
    assert policy.to_dict()["budget"]["maximum_writes"] == 0
    assert policy.to_dict()["stage"] == "camera_identity"
    assert policy.to_dict()["automatic_retry_allowed"] is False


@pytest.mark.parametrize(
    "key,value",
    [
        ("revision", True),
        ("revision", 2),
        ("stage", "camera_stream"),
        ("camera_capture_authorized", True),
        ("arm_access_authorized", True),
        ("historical_catalog_modified", 0),
        ("base_catalog_sha256", "f" * 64),
        ("action_id", "physical-native-camera-probe"),
        ("composition", "PHYSICAL_DIAGNOSTIC_CAMERA_ACQUISITION"),
    ],
)
def test_policy_exact_bytes(key, value):
    doc = m.usb_identity_stage_policy().to_dict()
    doc[key] = value
    with pytest.raises(m.UsbIdentityPolicyError):
        m.UsbIdentityStagePolicy(m.canonical(doc))


@pytest.mark.parametrize(
    "codec,factory",
    [
        (m.UsbIdentityStagePolicy, lambda: m.usb_identity_stage_policy().to_dict()),
        (m.UsbIdentityAdmissionIdentity, identity_document),
        (m.UsbIdentityPolicyReview, review_document),
    ],
)
def test_all_closed_and_canonical(codec, factory):
    doc = factory()
    original = codec(m.canonical(doc))
    assert original.to_dict() == doc and original.sha256 == m.digest(original.payload)
    for wire in (
        json.dumps(doc, indent=2).encode(),
        m.canonical(dict(doc, extra=False)),
        m.canonical(doc) + b"\n",
        b"{}",
        b'{"schema":1,"schema":2}',
    ):
        with pytest.raises(m.UsbIdentityPolicyError):
            codec(wire)


@pytest.mark.parametrize("key", sorted(m._IDENTITY_HASHES))
@pytest.mark.parametrize("value", [True, None, "x", "A" * 64])
def test_identity_hashes_are_exact(key, value):
    doc = identity_document()
    doc[key] = value
    with pytest.raises(m.UsbIdentityPolicyError):
        m.UsbIdentityAdmissionIdentity(m.canonical(doc))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["original_subjects"].reverse(),
        lambda d: d["original_subjects"].pop(),
        lambda d: d["original_subjects"][0]["reference"].update(stage="camera_receipt"),
        lambda d: d["original_subjects"][0]["reference"].update(
            payload_sha256="f" * 64
        ),
        lambda d: d["original_subjects"][1].update(document_sha256="a" * 64),
        lambda d: d.update(policy_review_sha256="a" * 64),
        lambda d: d.update(stage_policy_sha256="f" * 64),
        lambda d: d.update(cell_id="rehearsal-cell"),
        lambda d: d.update(session_id="rehearsal-session"),
    ],
)
def test_identity_original_links(mutation):
    doc = identity_document()
    mutation(doc)
    with pytest.raises(m.UsbIdentityPolicyError):
        m.UsbIdentityAdmissionIdentity(m.canonical(doc))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(operator_id="reviewer"),
        lambda d: d.update(operator_id="REVIEWER"),
        lambda d: d.update(reviewer_id=" review "),
        lambda d: d.update(reviewer_id="bad\nvalue"),
        lambda d: d.update(reviewed_at_utc_ns=True),
        lambda d: d.update(reviewed_at_utc_ns=0),
        lambda d: d.update(physical_authority=True),
        lambda d: d.update(physical_authority=0),
        lambda d: d.update(policy_sha256="a" * 64),
        lambda d: d["policy"].update(arm_access_authorized=True),
        lambda d: d.update(purpose="ENABLE_CAMERA"),
    ],
)
def test_review_is_specific_and_not_a_grant(mutation):
    doc = review_document()
    mutation(doc)
    with pytest.raises(m.UsbIdentityPolicyError):
        m.UsbIdentityPolicyReview(m.canonical(doc))


def test_inspection_only_accepts_exact_catalog(monkeypatch):
    class Catalog:
        source_sha256 = m.CATALOG_SHA256
        canonical_stage_order_sha256 = m.STAGE_ORDER_SHA256

    monkeypatch.setattr(
        m, "load_physical_onboarding_stage_catalog", lambda w: Catalog()
    )
    assert (
        m.inspect_usb_identity_stage_policy(Path.cwd()) == m.usb_identity_stage_policy()
    )
    Catalog.source_sha256 = "f" * 64
    with pytest.raises(m.UsbIdentityPolicyError, match="BASE_CATALOG_CHANGED"):
        m.inspect_usb_identity_stage_policy(Path.cwd())
