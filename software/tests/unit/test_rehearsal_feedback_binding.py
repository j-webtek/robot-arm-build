"""Pure stage-12 dependencies; these fixtures are not physical admission."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.application import commissioning_rehearsal_reopen as reopen
from rocell.application import rehearsal_arm_identity_stage as identity
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.rehearsal_feedback_binding import (
    RehearsalFeedbackBinding,
    ReviewedFeedbackPredecessor,
    controller_from_verified_arm_identity,
    owned_metadata_feedback_binding,
)


WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def identity_report():
    # Actual source/profile + injected inventory evaluator, never OS discovery.
    binding = identity.RehearsalArmIdentityBinding(
        "a" * 64,
        "b" * 64,
        "cell-test",
        "session-test",
        "operator-test",
        "c" * 64,
        "d" * 64,
        "e" * 64,
        "f" * 64,
    )
    return identity.evaluate_rehearsal_arm_identity_stage(WORKSPACE, binding).to_dict()


@pytest.fixture
def binding(identity_report):
    prior = tuple(
        ReviewedFeedbackPredecessor(
            stage.value,
            str(index) * 64,
            "b" * 64,
            "c" * 64,
            "d" * 64,
        )
        for index, stage in enumerate(STAGE_ORDER[8:11], 1)
    )
    return RehearsalFeedbackBinding(
        "a" * 64,
        "b" * 64,
        "cell-test",
        "session-test",
        "operator-test",
        prior,
        controller_from_verified_arm_identity(
            identity_report, identity_receipt_sha256="1" * 64
        ),
    )


def test_controller_is_exact_stage_nine_fixture_with_unmeasured_driver(binding):
    unit = binding.controller.identity
    assert (unit.vid, unit.pid, unit.port_name) == ("1234", "5678", "COM42")
    assert unit.unit_serial == "INCAPABLE-ARM-001"
    assert unit.driver.provider == "SYNTHETIC_UNMEASURED"
    assert binding.to_dict()["physical_authority"] is False
    assert binding.selected_identity_document == unit.to_dict()
    document = binding.to_dict()
    document["controller"]["identity"]["port_name"] = "COM1"
    assert binding.controller.identity.port_name == "COM42"


def test_owned_native_fixture_retains_separate_original_generic_review(
    binding, monkeypatch
):
    import ctypes
    from rocell.application import physical_device_inventory as inventory

    def forbidden(*args, **kwargs):
        pytest.fail("Pure fixture adaptation must not discover or open hardware")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(inventory, "inventory_serial_ports_with_pyserial", forbidden)
    original = binding.to_dict()
    adapted = owned_metadata_feedback_binding(binding)
    assert binding.to_dict() == original
    assert original["schema"] == "rocell.rehearsal_feedback_binding.v1"
    assert "generic_reviewed_controller" not in original
    assert adapted.to_dict()["schema"] == "rocell.rehearsal_feedback_binding.v2"
    assert adapted.to_dict()["generic_reviewed_controller"] == original["controller"]
    assert adapted.controller.identity.persistent_port_path.startswith("\\\\?\\")
    assert "INCAPABLE-CM-" in adapted.controller.identity.persistent_instance_id
    assert (
        adapted.controller.identity.port_name == binding.controller.identity.port_name
    )
    assert adapted.controller.identity.driver == binding.controller.identity.driver
    assert (
        adapted.controller.identity_receipt_sha256
        == binding.controller.identity_receipt_sha256
    )
    assert adapted.predecessors == binding.predecessors
    assert adapted.binding_sha256 != binding.binding_sha256
    assert owned_metadata_feedback_binding(binding) == adapted
    with pytest.raises(ValueError, match="second time"):
        owned_metadata_feedback_binding(adapted)
    with pytest.raises(ValueError, match="lineage"):
        replace(
            adapted,
            controller=replace(
                adapted.controller,
                identity=replace(adapted.controller.identity, port_name="COM43"),
            ),
        )


@pytest.mark.parametrize(
    "field",
    ["receipt_sha256", "assessment_sha256", "review_sha256", "evaluation_sha256"],
)
@pytest.mark.parametrize("index", [0, 1, 2])
def test_each_exact_predecessor_digest_affects_binding(binding, index, field):
    previous = list(binding.predecessors)
    previous[index] = replace(previous[index], **{field: "e" * 64})
    if index == 0 and field == "receipt_sha256":
        with pytest.raises(ValueError):
            replace(binding, predecessors=tuple(previous))
    else:
        assert (
            replace(binding, predecessors=tuple(previous)).binding_sha256
            != binding.binding_sha256
        )


@pytest.mark.parametrize("value", [None, True, 1, "0" * 64, "A" * 64, "1" * 63])
def test_invalid_source_rejected(binding, value):
    with pytest.raises(ValueError):
        replace(binding, workspace_source_sha256=value)


@pytest.mark.parametrize("mutation", ["reorder", "missing", "list", "duplicate"])
def test_exact_predecessor_tuple_required(binding, mutation):
    prior = binding.predecessors
    changed = {
        "reorder": prior[::-1],
        "missing": prior[:2],
        "list": list(prior),
        "duplicate": (prior[0], prior[0], prior[2]),
    }[mutation]
    with pytest.raises(ValueError):
        replace(binding, predecessors=changed)


@pytest.mark.parametrize(
    "field,value",
    [
        ("ephemeral_locator_observation", "COM43"),
        ("qualified", True),
        ("selection_performed", True),
        ("persistent_ids", ["COM42"]),
        ("identity_blockers", ["INCOMPLETE"]),
    ],
)
def test_no_candidate_substitution(identity_report, field, value):
    report = deepcopy(identity_report)
    report["reports"]["selection_baseline"]["candidate"][field] = value
    with pytest.raises(ValueError):
        controller_from_verified_arm_identity(report, identity_receipt_sha256="a" * 64)


def test_predecessor_builder_uses_each_pure_verifier_and_full_trio(
    monkeypatch, identity_report
):
    calls = []
    trios = {}
    for stage in STAGE_ORDER[5:11]:
        trios[stage] = tuple(
            SimpleNamespace(document=lambda s=stage, i=i: {"stage": s.value, "part": i})
            for i in range(3)
        )

    def reviewed(snapshot, evidence, stage):
        return trios[stage]

    def verify(snapshot, evidence, receipt, source, catalog):
        stage = receipt.document()["stage"]
        calls.append(stage)
        return SimpleNamespace(
            outcome="REHEARSAL_CHECKS_PASSED",
            evidence_sha256="e" * 64,
            to_dict=lambda: deepcopy(identity_report),
        )

    monkeypatch.setattr(reopen, "_reviewed_stage_evidence", reviewed)
    monkeypatch.setattr(reopen, "_verify_evaluated_receipt", verify)
    snapshot = SimpleNamespace(
        header=SimpleNamespace(cell_id="cell-test", session_id="session-test")
    )
    result, camera = reopen._feedback_binding(
        snapshot, {}, "operator-test", "a" * 64, "b" * 64
    )
    assert calls == [stage.value for stage in STAGE_ORDER[8:11]]
    assert camera is trios[STAGE_ORDER[5]][0]
    for index, stage in enumerate(STAGE_ORDER[8:11]):
        row = result.predecessors[index]
        assert row.receipt_sha256 == reopen._hash(trios[stage][0].document())
        assert row.assessment_sha256 == reopen._hash(trios[stage][1].document())
        assert row.review_sha256 == reopen._hash(trios[stage][2].document())


def test_blocked_predecessor_cannot_become_feedback_input(monkeypatch):
    monkeypatch.setattr(
        reopen, "_reviewed_stage_evidence", lambda *args: (None, None, None)
    )
    monkeypatch.setattr(
        reopen,
        "_verify_evaluated_receipt",
        lambda *args: SimpleNamespace(outcome="BLOCKED"),
    )
    with pytest.raises(reopen.RehearsalReopenError, match="must pass"):
        reopen._feedback_binding(None, {}, "operator-test", "a" * 64, "b" * 64)
