"""Closed private pair; all process/camera observations below are modeled."""

from dataclasses import replace
from pathlib import Path

import pytest

from rocell.application.camera_activation_campaign_evidence import (
    CameraActivationArtifact,
    ROLE_LIMITS,
    camera_activation_evidence,
    validate_camera_activation_evidence,
    _COMMON,
)
from rocell.application.cell_commissioning_coordinator import (
    CampaignEvidence,
    validate_campaign_evidence,
)
from rocell.providers.windows.native_camera_protocol import canonical
from rocell.providers.windows.owned_worker_process import decode_owned_json
from test_native_camera_activation_supervisor import setup, run, no_physical_owner


def pair(tmp_path, monkeypatch, purpose="probe", fault=None):
    owner, prepared, _, current = setup(tmp_path, monkeypatch, purpose, fault)
    outcome = run(prepared, current)
    return prepared, outcome, camera_activation_evidence(prepared, outcome)


def changed_detail(artifacts, change):
    detail = decode_owned_json(artifacts[1].payload, maximum=ROLE_LIMITS["supervision"])
    change(detail)
    return artifacts[0], CameraActivationArtifact("supervision", canonical(detail))


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_complete_pair_reverifies_inertly_without_legacy_conversion(
    tmp_path, monkeypatch, purpose
):
    prepared, _, artifacts = pair(tmp_path, monkeypatch, purpose)

    def forbidden(*a, **kw):
        pytest.fail("Paired-artifact verification attempted filesystem I/O")

    with monkeypatch.context() as patch:
        for name in ("open", "stat", "resolve", "mkdir"):
            patch.setattr(Path, name, forbidden)
        verified = validate_camera_activation_evidence(artifacts)
        assert verified.prepared.payload == prepared.payload
        assert verified.run.assessment().status == "SUCCEEDED_NATIVE_DIAGNOSTIC"
        assert verified.run.safe_summary()["physical_authority"] is False
        data = verified.run.to_dict()
        data["owner_constructed"] = False
        assert verified.run.to_dict()["owner_constructed"]
    with pytest.raises(Exception, match="untyped retained campaign evidence"):
        validate_campaign_evidence(artifacts)


@pytest.mark.parametrize(
    "fault",
    [
        "pin",
        "start",
        "bad-result",
        "cleanup-throw",
        "cleanup-resource",
        "lose-output-after-cleanup",
    ],
)
def test_failed_run_and_before_after_detail_remain_retained(
    tmp_path, monkeypatch, fault
):
    _, outcome, artifacts = pair(tmp_path, monkeypatch, fault=fault)
    checked = validate_camera_activation_evidence(artifacts)
    assert checked.run.assessment().status == "FAILED"
    assert checked.supervision_payload == canonical(outcome.diagnostics())
    if fault in ("pin", "start", "bad-result", "lose-output-after-cleanup"):
        assert checked.run.safe_summary()["native_counts"] is None


@pytest.mark.parametrize("field", _COMMON)
def test_every_shared_field_must_match_exactly(tmp_path, monkeypatch, field):
    _, _, artifacts = pair(tmp_path, monkeypatch)

    def change(detail):
        detail[field] = "different" if detail[field] != "different" else None

    with pytest.raises(ValueError, match="RUN_BINDING"):
        validate_camera_activation_evidence(changed_detail(artifacts, change))


@pytest.mark.parametrize(
    "fault",
    [
        "extra",
        "registration",
        "after",
        "before-missing",
        "before-budget",
        "errors",
        "retained-success",
        "bool-as-int",
    ],
)
def test_closed_pair_rejects_substitution_without_discarding_original_bytes(
    tmp_path, monkeypatch, fault
):
    _, _, artifacts = pair(tmp_path, monkeypatch)
    saved = tuple(item.payload for item in artifacts)

    def change(detail):
        if fault == "extra":
            detail["operator_approved"] = True
        elif fault == "registration":
            detail["actual_registration"]["composition"] = "INCAPABLE_PROCESS_FIXTURE"
        elif fault == "after":
            detail["after_cleanup"]["fields"]["pid"]["value"] += 1
        elif fault == "before-missing":
            detail["before_cleanup"] = None
        elif fault == "before-budget":
            detail["before_cleanup"]["stdout_limit"] = 128
        elif fault == "errors":
            detail["supervisor_errors"] = ["unbounded arbitrary exception text"]
        elif fault == "retained-success":
            detail["unresolved_owner_retained"] = True
        else:
            detail["release_check_passed"] = 1

    with pytest.raises(ValueError):
        validate_camera_activation_evidence(changed_detail(artifacts, change))
    assert tuple(item.payload for item in artifacts) == saved


def test_incapable_executed_registration_cannot_be_relabelled(tmp_path, monkeypatch):
    prepared, outcome, _ = pair(tmp_path, monkeypatch)
    registration = decode_owned_json(outcome.actual_registration, maximum=48 * 1024)
    registration["composition"] = "INCAPABLE_PROCESS_FIXTURE"
    fixture = replace(outcome, actual_registration=canonical(registration))
    with pytest.raises(ValueError, match="EXECUTED_ACTIVATION_REGISTRATION_MISMATCH"):
        camera_activation_evidence(prepared, fixture)


def test_full_bounded_pipe_diagnostics_exceed_legacy_limit_without_truncation(
    tmp_path, monkeypatch
):
    owner, prepared, _, current = setup(tmp_path, monkeypatch)
    owner.result = b"x" * (256 * 1024 - len(owner.ready))
    outcome = run(prepared, current)
    artifacts = camera_activation_evidence(prepared, outcome)
    assert all(len(item.payload) > 128 * 1024 for item in artifacts)
    assert (
        validate_camera_activation_evidence(artifacts).run.assessment().native is None
    )
    assert len(outcome.before_cleanup.values()["stdout"]) == 256 * 1024
    with pytest.raises(Exception, match="byte bound"):
        CampaignEvidence(artifacts[0].schema, artifacts[0].label, artifacts[0].payload)


@pytest.mark.parametrize("role", ["run", "supervision"])
def test_each_role_has_its_own_finite_shell_limit(role):
    # Artifact shells bind finite bytes; paired semantic validation is separate.
    CameraActivationArtifact(role, b"x" * ROLE_LIMITS[role])
    for payload in (b"", b"x" * (ROLE_LIMITS[role] + 1), "not bytes"):
        with pytest.raises(ValueError):
            CameraActivationArtifact(role, payload)


@pytest.mark.parametrize("shape", ["missing", "extra", "reversed", "list", "legacy"])
def test_exact_ordered_pair_required(tmp_path, monkeypatch, shape):
    _, _, artifacts = pair(tmp_path, monkeypatch)
    wrong = {
        "missing": artifacts[:1],
        "extra": artifacts + artifacts[:1],
        "reversed": artifacts[::-1],
        "list": list(artifacts),
        "legacy": tuple(
            CampaignEvidence(item.schema, item.label, item.payload)
            for item in artifacts
        ),
    }[shape]
    with pytest.raises(ValueError):
        validate_camera_activation_evidence(wrong)
