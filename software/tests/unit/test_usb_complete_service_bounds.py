"""Cheap no-device navigation and partial-publication behavior checks."""

from copy import deepcopy
from types import SimpleNamespace
import pytest

from rocell.application import physical_usb_complete_service as m
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from test_physical_usb_presence_binding import reference
from rocell.application.physical_usb_identity_service import (
    PhysicalUsbIdentityService,
    FLAGS,
)
from rocell.application.arrival_wizard_service import ArrivalWizardService


def boundary(review=False):
    return dict(
        schema=(
            m.SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA
            if review
            else m.SOURCE_WORKFLOW_USB_REBOOT_SCHEMA
        ),
        usb_qualification_reboot=dict(
            state="RETAINED_BLOCKED",
            phase="AFTER_REBOOT",
            phase_record={"MODELED": True},
        ),
        **(
            dict(
                usb_qualification_complete=dict(
                    state="REVIEW_PENDING",
                    series={},
                    assessment={},
                    review=None,
                    events=[{}, {}],
                )
            )
            if review
            else {}
        ),
    )


@pytest.mark.parametrize("review", [False, True])
def test_boundary_is_inert_and_does_not_edit_records(review):
    value = boundary(review)
    before = deepcopy(value)
    assert m.complete_action_boundary(value) == (m.REVIEW if review else m.ASSESS)
    assert value == before


def labels():
    return dict(
        usb_qualification_trial=dict(plan=dict(document=dict(operator_id="PLAN"))),
        **{
            "usb_qualification_"
            + phase: dict(
                phase_record=dict(
                    document=dict(context=dict(operator_id=phase.upper()))
                )
            )
            for phase in ("baseline", "absence", "reconnect", "reboot")
        },
    )


@pytest.mark.parametrize(
    "reviewer", ["plan", "BASELINE", "absence", "reconnect", "reboot", None, True]
)
def test_preflight_rejects_non_distinct_labels_without_mutation(reviewer):
    workflow = labels()
    previous = deepcopy(workflow)
    assert m.distinct_review_label(workflow, reviewer) is False
    assert workflow == previous


def test_distinct_label_check_neither_authenticates_nor_changes_originals():
    workflow = labels()
    assert m.distinct_review_label(workflow, "MODELED-independent-reviewer") is True
    for phase in ("baseline", "absence", "reconnect", "reboot"):
        bad = deepcopy(workflow)
        del bad["usb_qualification_" + phase]
        assert m.distinct_review_label(bad, "MODELED-independent-reviewer") is False


@pytest.mark.parametrize("action_id", sorted(m.ACTIONS))
def test_file_result_withholds_history_before_projection_and_parent_validation(
    action_id,
):
    owner = SimpleNamespace(
        _summaries=lambda: tuple({"MODELED_OLD_QUERY": True} for _ in range(4)),
        _context=lambda: {},
        _baseline={},
        _attempt=None,
        _publication=dict(status="HISTORICAL_HELD", operation_id=None),
    )

    def projection():
        assert owner._publication == dict(status="PENDING", operation_id=None)
        return dict(
            schema="rocell.wizard_usb_qualification.v6",
            publication=deepcopy(owner._publication),
            status="NOT_DECLARED",
            next_action=None,
            **{
                key: None
                for key in (
                    "plan",
                    "baseline",
                    "absence",
                    "reconnect",
                    "reboot",
                    "complete",
                )
            },
            **FLAGS,
        )

    owner.qualification_view = projection
    result = PhysicalUsbIdentityService._result(owner, action_id)
    ArrivalWizardService._validate_usb_identity_result(action_id, result)
    report = result["steps"][0]["report"]
    assert all(
        report[key] is None
        for key in ("inspection", "review", "execution", "observation")
    )
    assert owner._pending_result == canonical(result)
    assert owner._pending_action == action_id
    for key in ("plan", "baseline", "absence", "reconnect", "reboot", "complete"):
        bad = deepcopy(result)
        bad["steps"][0]["report"]["qualification"][key] = {"MODELED_PENDING_LEAK": True}
        with pytest.raises(ValueError, match="withheld"):
            ArrivalWizardService._validate_usb_identity_result(action_id, bad)


@pytest.mark.parametrize(
    "value",
    [None, [], {}, {"schema": True}, {"schema": m.SOURCE_WORKFLOW_USB_REBOOT_SCHEMA}],
)
def test_missing_original_never_exposes_action(value):
    assert m.complete_action_boundary(value) is None


@pytest.mark.parametrize(
    "status",
    [
        "ASSESSMENT_REQUESTED",
        "INCOMPLETE",
        "REVIEWED_PASS",
        "REVIEWED_BLOCKED",
        None,
        True,
    ],
)
def test_partial_or_consumed_complete_boundary_has_no_action(status):
    value = boundary(True)
    value["usb_qualification_complete"]["state"] = status
    assert m.complete_action_boundary(value) is None


@pytest.mark.parametrize(
    "fault",
    [
        "schema",
        "reboot-state",
        "reboot-phase",
        "missing-phase",
        "early-review",
        "missing-series",
        "missing-assessment",
        "event-count",
    ],
)
def test_invalid_boundary_never_exposes_action(fault):
    value = boundary(True)
    if fault == "schema":
        value["schema"] = "rocell.physical_camera_source_workflow_readback.v15"
    elif fault == "reboot-state":
        value["usb_qualification_reboot"]["state"] = "ORIGINAL_CAMPAIGN_HELD"
    elif fault == "reboot-phase":
        value["usb_qualification_reboot"]["phase"] = "AFTER_RECONNECT"
    elif fault == "missing-phase":
        value["usb_qualification_reboot"]["phase_record"] = None
    elif fault == "early-review":
        value["usb_qualification_complete"]["review"] = {}
    elif fault == "missing-series":
        value["usb_qualification_complete"]["series"] = None
    elif fault == "missing-assessment":
        value["usb_qualification_complete"]["assessment"] = None
    else:
        value["usb_qualification_complete"]["events"] = [{}]
    assert m.complete_action_boundary(value) is None


def subject():
    doc = {"meaning": "MODELED ROLE FOR STORAGE TEST, NOT QUALIFICATION"}
    raw = canonical(doc)
    return SimpleNamespace(
        role="series", payload=raw, sha256=digest(raw), to_dict=lambda: doc
    )


@pytest.mark.parametrize("boundary", [1, 2, 3])
def test_stop_around_role_write_preserves_known_retention(boundary):
    model = m._UsbCompleteReview(object())
    model.attempt = dict(records={}, events=[])
    value = subject()
    calls, effects = [0], []
    ref = reference(value.payload, "MODELED-new-complete-series")
    tx = SimpleNamespace(
        snapshot=lambda: SimpleNamespace(head=SimpleNamespace(head_sha256="a" * 64)),
        store_evidence=lambda *a, **k: (effects.append("store"), ref)[1],
        read_stage_evidence=lambda r: (effects.append("read"), value.payload)[1],
    )

    def guard():
        calls[0] += 1
        if calls[0] == boundary:
            raise RuntimeError("MODELED_STOP")

    with pytest.raises(RuntimeError, match="MODELED_STOP"):
        model._retain(tx, value, "usbseries-" + "7" * 32, guard)
    if boundary == 1:
        assert effects == [] and model.attempt["records"] == {}
    else:
        row = model.attempt["records"]["series"]
        assert row["reference"] == ref.to_dict()
        assert row["retention"] == (
            "M1_PUBLISHED_READBACK_PENDING"
            if boundary == 2
            else "M1_FULL_BYTES_READ_BACK"
        )
        assert row["document"] == value.to_dict()


def test_commit_is_cached_before_late_stop():
    model = m._UsbCompleteReview(object())
    model.attempt = dict(records={}, events=[])
    calls = [0]
    doc = dict(meaning="MODELED COMMITTED EVENT")
    tx = SimpleNamespace(
        snapshot=lambda: SimpleNamespace(head=SimpleNamespace(head_sha256="a" * 64)),
        commit_stage_state=lambda *a, **k: SimpleNamespace(
            committed_events=[SimpleNamespace(to_dict=lambda: doc)]
        ),
    )

    def guard():
        calls[0] += 1
        if calls[0] == 2:
            raise RuntimeError("MODELED_LATE_STOP")

    with pytest.raises(RuntimeError, match="MODELED_LATE_STOP"):
        model._commit(
            tx,
            "ASSESSMENT_REQUESTED",
            m.V2StageState.WAITING_OPERATOR,
            "usbseries-" + "7" * 32,
            (),
            guard,
        )
    assert model.attempt["events"] == [doc]
