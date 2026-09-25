"""Pure v2 application accounting using explicitly modeled run observations."""

from pathlib import Path

import pytest

from rocell.application.native_camera_bounded_effect import (
    assess_activation_camera_bounded_effect,
)
from rocell.safety.effects import EffectCertainty
from test_native_camera_activation_evidence import modeled, retain
from test_native_camera_activation_registration import preparation


def assess(record, args, **overrides):
    context = dict(
        expected_preparation=args["prepared"],
        expected_evidence_sha256=record.evidence_sha256,
        expected_started_ns=args["started_ns"],
        expected_deadline_ns=args["parent_deadline_ns"],
        maximum_elapsed_ns=20_000_000_000,
    )
    context.update(overrides)
    return assess_activation_camera_bounded_effect(record, **context)


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_v2_accounting_preserves_exact_counts_and_does_no_io(
    tmp_path, monkeypatch, purpose
):
    owner, args = modeled(tmp_path, purpose)
    record = retain(owner, args)

    def forbidden(*a, **kw):
        pytest.fail("Pure accounting attempted filesystem access")

    with monkeypatch.context() as patch:
        for name in ("open", "stat", "resolve", "mkdir"):
            patch.setattr(Path, name, forbidden)
        effect = assess(record, args)
    assert effect.effect_certainty is EffectCertainty.CONFIRMED
    assert not effect.reasons and effect.cleanup_confirmed
    assert effect.counts is not None and effect.counts.source_activation_attempts == 1
    assert effect.counts.frames_written == (1 if purpose == "capture" else 0)
    # Confirmed accounting is not connection/qualification/contact permission.
    assert record.safe_summary()["physical_authority"] is False


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("expected_started_ns", 999_999_999, "ORIGINAL_START_MISMATCH"),
        ("expected_deadline_ns", 26_000_000_000, "ORIGINAL_DEADLINE_MISMATCH"),
        (
            "maximum_elapsed_ns",
            2_000_000_000,
            "CAMPAIGN_DURATION_UNCONFIRMED_OR_EXCEEDED",
        ),
    ],
)
def test_independent_invocation_context_cannot_be_echoed_from_evidence(
    tmp_path, field, value, reason
):
    owner, args = modeled(tmp_path)
    effect = assess(retain(owner, args), args, **{field: value})
    assert effect.effect_certainty is EffectCertainty.UNCERTAIN
    assert reason in effect.reasons
    assert effect.counts is not None  # Useful diagnostics survive failed binding.


@pytest.mark.parametrize(
    "fault", ["cleanup", "cancelled", "missing-output", "no-finish"]
)
def test_failed_or_incomplete_runs_stay_uncertain(tmp_path, fault):
    owner, args = modeled(tmp_path)
    if fault == "cleanup":
        args["cleanup"]["errors"] = ["CLOSE_FAILED:pinned-file"]
    elif fault == "cancelled":
        args["primary_error"] = "CANCELLED"
    elif fault == "missing-output":
        del owner.stdout
    else:
        args["finished_ns"] = None
    effect = assess(retain(owner, args), args)
    assert effect.effect_certainty is EffectCertainty.UNCERTAIN
    assert "RUN_NOT_SUCCESSFUL" in effect.reasons
    assert (effect.counts is None) == (fault == "missing-output")
    if fault in ("cleanup", "no-finish"):
        assert not effect.process_cleanup_confirmed
        assert effect.native_cleanup_confirmed


def test_pre_owner_hold_does_not_invent_native_zero_counts(tmp_path):
    _, args = modeled(tmp_path)
    args.update(
        owner_constructed=False,
        primary_error="PHYSICAL_PROVIDER_QUALIFICATION_HELD",
        ready_wire=b"",
        release_wire=b"",
        release_check_passed=False,
        accepted_result_sha256=None,
        cleanup=dict(
            attempted=False,
            returned=False,
            deadline_ns=None,
            finished_ns=None,
            errors=None,
        ),
    )
    effect = assess(retain(None, args), args)
    assert effect.effect_certainty is EffectCertainty.UNCERTAIN
    assert effect.counts is None and not effect.cleanup_confirmed


@pytest.mark.parametrize("changed", ["hash", "preparation"])
def test_independent_evidence_digest_and_preparation_are_mandatory(tmp_path, changed):
    owner, args = modeled(tmp_path)
    overrides = (
        {"expected_evidence_sha256": "9" * 64}
        if changed == "hash"
        else {"expected_preparation": preparation(tmp_path / "different")}
    )
    with pytest.raises(ValueError, match="TRUSTED"):
        assess(retain(owner, args), args, **overrides)


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_started_ns", True),
        ("expected_started_ns", -1),
        ("expected_started_ns", 25_000_000_000),
        ("expected_deadline_ns", True),
        ("expected_deadline_ns", 2**63),
        ("maximum_elapsed_ns", True),
        ("maximum_elapsed_ns", 0),
        ("maximum_elapsed_ns", 25_000_000_001),
    ],
)
def test_closed_finite_original_context_required(tmp_path, field, value):
    owner, args = modeled(tmp_path)
    with pytest.raises(ValueError, match="EXACT_ACTIVATION_EFFECT_CONTEXT"):
        assess(retain(owner, args), args, **{field: value})
