"""Strict cached design presentation with modeled subjects, never hardware.

The separate public composed tests run real design collectors/services through
these same production renderers. Fixtures here isolate malformed/held states.
"""

from copy import deepcopy

import pytest

from rocell.ui.terminal import _StaticCameraOnboardingDisplay as Display
from test_wizard_physical_camera_setup_ui import complete_setup, prerequisite_summary
from test_wizard_source_reassessment_ui import fixture_view
from test_wizard_workspace_source_ui import render_snapshot

ACCEPTED = "Stage 2 design accepted only — no installation or native camera release."
ERROR = "STATIC_CAMERA_ONBOARDING_NOT_VERIFIED"


def fixture(data, *, reviewed=True, verdict="PASS", entry=False):
    view = fixture_view(data, stage2=True)
    setup = view["physical_camera_setup"]
    source = view["source_reassessment"]
    source.update(status="HISTORICAL_HELD", next_action=None)
    source["publication"]["status"] = "HISTORICAL_HELD"
    context = deepcopy(source["original_context"])
    qualification = source["qualification"]
    contract_id = "staticcontract-" + "a" * 32
    binding = {
        **context,
        "contract_id": contract_id,
        "collection_launch_id": setup["launch_session_id"],
        "operator_id": "static_operator",
        "source_qualification": {
            "receipt": qualification["receipt_sha256"],
            "assessment": qualification["assessment_sha256"],
            "review": qualification["review"]["review_sha256"],
        },
        "static_request_event_sha256": "9" * 64,
        "store_directory": setup["session"]["binding"]["directory"],
    }
    flags = dict.fromkeys(Display.ROLE_FLAGS, False)
    checks = [
        {"check_id": key, "passed": verdict == "PASS" or i != 0}
        for i, key in enumerate(Display.CHECKS)
    ]
    receipt = {
        "schema": "rocell.static_camera_contract_receipt_summary.v1",
        "binding": deepcopy(binding),
        "receipt_sha256": "a" * 64,
        "status": "DESIGN_INPUTS_COLLECTED",
        "checks": deepcopy(checks),
        "design": {
            "camera_model": "MODELED_camera_not_received",
            "sensor": "MODELED_sensor",
            "lens_mount": "MODELED_mount",
            "focal_length_mm": 16,
            "board_size_mm": [610, 457, 18],
            "required_view_mm": [670, 517],
            "nominal_entrance_pupil_z_mm": 1000,
            "published_mode": {
                "host_bus": "USB",
                "width_px": 5472,
                "height_px": 3648,
                "maximum_fps": 9,
                "pixel_format": "YUY2",
                "evidence_state": "PUBLISHED_NOT_OBSERVED",
            },
            "value_provenance": "DESIGN_NOT_MEASURED",
        },
        "blockers": {
            "architecture": ["retained_architecture_hold"],
            "profile": ["retained_profile_hold"],
            "support": ["retained_support_hold"],
        },
        "source_file_count": 5,
        "source_bytes": 12000,
        **flags,
    }
    assessment = {
        "schema": "rocell.static_camera_contract_assessment_summary.v1",
        "binding": deepcopy(binding),
        "receipt_sha256": receipt["receipt_sha256"],
        "assessment_sha256": "b" * 64,
        "status": "ASSESSED",
        "verdict": verdict,
        "checks": deepcopy(checks),
        "missing_requirements": [
            row["check_id"] for row in checks if not row["passed"]
        ],
        **flags,
    }
    review = (
        {
            "schema": "rocell.static_camera_contract_review_summary.v1",
            "binding": deepcopy(binding),
            "receipt_sha256": receipt["receipt_sha256"],
            "assessment_sha256": assessment["assessment_sha256"],
            "review_sha256": "c" * 64,
            "status": "REVIEW_RECORDED",
            "verdict": verdict,
            "reviewer_id": "static_reviewer",
            "review_launch_id": setup["launch_session_id"],
            "reviewed_at_ns": 2**63 - 1,
            "procedure_complete": True,
            **flags,
        }
        if reviewed
        else None
    )
    state = verdict if reviewed else "REVIEW_PENDING"
    setup["session"]["stages"][1].update(state=state, last_event_sequence=10)
    setup["session"]["stages"][2].update(
        state="WAITING_OPERATOR" if entry else "PENDING",
        last_event_sequence=11 if entry else None,
    )
    view["static_camera_onboarding"] = {
        "schema": "rocell.wizard_static_camera_onboarding.v1",
        "source_sha256": setup["source_sha256"],
        "launch_session_id": setup["launch_session_id"],
        "original_context": context,
        "publication": {"status": "CURRENT", "operation_id": "static-operation"},
        "status": "REVIEWED_" + verdict if reviewed else "REVIEW_PENDING",
        "stage_states": {
            "workspace_sources": "PASS",
            "static_camera_contract": state,
            "camera_receipt": "WAITING_OPERATOR" if entry else "PENDING",
        },
        "contract": {
            "contract_id": contract_id,
            "state": "REVIEWED_" + verdict if reviewed else "REVIEW_PENDING",
            "receipt": receipt,
            "assessment": assessment,
            "review": review,
        },
        "camera_receipt_entry": "d" * 64 if entry else None,
        "next_action": None,
        "physical_authority": False,
        "hardware_qualified": False,
        "native_release_allowed": False,
        "device_io_performed": False,
        "meaning": "Modeled retained subject for cached presentation only.",
    }
    return view


def rendered(view):
    before = deepcopy(view)
    value = view["static_camera_onboarding"]
    assert Display.projection(value, view) == value
    texts = render_snapshot(view)
    assert view == before
    assert all(ERROR not in text for text in texts)
    return texts


@pytest.mark.parametrize("entry", [False, True])
def test_design_only_pass_and_explicit_received_stage_are_separate(
    complete_setup, entry
):
    for text in rendered(fixture(complete_setup, entry=entry)):
        assert ACCEPTED in text
        assert "MODELED_camera_not_received" in text
        assert "retained_architecture_hold" in text
        assert "retained_profile_hold" in text
        assert "retained_support_hold" in text
        assert "Published catalog mode" in text
        assert "not selected or observed device settings" in text
        assert "not authenticated independent people" in text
        assert "9223372036854775807" not in text
        assert (
            "remains WAITING_OPERATOR" in text
            if entry
            else "Stage 3 remains PENDING" in text
        )


@pytest.mark.parametrize("verdict", ["PASS", "BLOCKED"])
def test_retained_assessment_is_not_committed_acceptance(complete_setup, verdict):
    for text in rendered(fixture(complete_setup, reviewed=False, verdict=verdict)):
        assert ACCEPTED not in text
        assert "exact-subject review is still required" in text


def test_blocked_design_preserves_failed_check_and_does_not_enter_stage3(
    complete_setup,
):
    for text in rendered(fixture(complete_setup, verdict="BLOCKED")):
        assert ACCEPTED not in text
        assert "base_software_ready" in text
        assert "BLOCKED" in text


@pytest.mark.parametrize("publication", ["PENDING", "HISTORICAL_HELD"])
def test_pending_and_historical_never_look_current(complete_setup, publication):
    view = fixture(complete_setup)
    value = view["static_camera_onboarding"]
    value.update(status="HISTORICAL_HELD", next_action=None)
    value["publication"]["status"] = publication
    if publication == "PENDING":
        value["contract"] = None
    else:
        view["source_binding_sha256"] = "f" * 64
        view["session_id"] = "wizard-" + "f" * 32
    for text in rendered(view):
        assert ACCEPTED not in text
        if publication == "PENDING":
            assert "Design publication pending" in text
            assert "MODELED_camera_not_received" not in text
        else:
            assert "Historical design subject only" in text


@pytest.mark.parametrize(
    "phase", ["initial", "receipt-only", "assessment-only", "review-uncommitted"]
)
def test_no_missing_record_or_commit_is_inferred(complete_setup, phase):
    view = fixture(complete_setup)
    value = view["static_camera_onboarding"]
    value["status"] = "NOT_STARTED" if phase == "initial" else "INCOMPLETE_HELD"
    if phase == "initial":
        value["contract"] = None
    else:
        t = value["contract"]
        t["state"] = {
            "receipt-only": "INCOMPLETE",
            "assessment-only": "ASSESSMENT_RETAINED_NOT_COMMITTED",
            "review-uncommitted": "REVIEW_RETAINED_NOT_COMMITTED",
        }[phase]
        if phase != "review-uncommitted":
            t["review"] = None
        if phase == "receipt-only":
            t["assessment"] = None
    for text in rendered(view):
        assert ACCEPTED not in text


@pytest.mark.parametrize(
    "path,value",
    [
        (("physical_authority",), True),
        (("hardware_qualified",), 0),
        (("native_release_allowed",), True),
        (("device_io_performed",), "false"),
        (("source_sha256",), "f" * 64),
        (("launch_session_id",), "wizard-" + "f" * 32),
        (("original_context", "header_sha256"), "f" * 64),
        (("original_context", "prerequisites_sha256"), "f" * 64),
        (
            ("contract", "receipt", "binding", "source_qualification", "review"),
            "f" * 64,
        ),
        (("contract", "receipt", "binding", "store_directory"), "C:/elsewhere"),
        (("contract", "receipt", "checks", 0, "passed"), 1),
        (("contract", "receipt", "checks", 0, "check_id"), "invented_check"),
        (("contract", "receipt", "source_bytes"), 131073),
        (("contract", "receipt", "source_file_count"), 4),
        (("contract", "receipt", "design", "focal_length_mm"), -1),
        (("contract", "receipt", "design", "value_provenance"), "OBSERVED"),
        (("contract", "receipt", "design", "board_size_mm"), [610, 457]),
        (("contract", "receipt", "native_runtime_released"), True),
        (("contract", "assessment", "missing_requirements"), ["invented_check"]),
        (("contract", "assessment", "checks", 0, "passed"), False),
        (("contract", "review", "reviewer_id"), "STATIC_OPERATOR"),
        (("contract", "review", "procedure_complete"), "true"),
        (("contract", "review", "verdict"), "BLOCKED"),
        (("contract", "review", "reviewed_at_ns"), -1),
        (("contract", "review", "assessment_sha256"), "f" * 64),
        (("publication", "status"), "PENDING"),
        (("publication", "operation_id"), None),
        (("stage_states", "camera_receipt"), "WAITING_OPERATOR"),
        (("camera_receipt_entry",), "d" * 64),
        (("next_action",), "physical_camera_capture"),
    ],
)
def test_malformed_or_unbound_subject_withheld(complete_setup, path, value):
    view = fixture(complete_setup)
    target = view["static_camera_onboarding"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert Display.projection(view["static_camera_onboarding"], view) is None
    for text in render_snapshot(view):
        assert ERROR in text
        assert ACCEPTED not in text


def test_oversized_canonical_unicode_and_unknown_keys_are_withheld(complete_setup):
    for mutation in ("unicode", "extra"):
        view = fixture(complete_setup)
        receipt = view["static_camera_onboarding"]["contract"]["receipt"]
        if mutation == "unicode":
            receipt["blockers"]["architecture"] = ["é" * 1000] * 5
        else:
            receipt["unexpected_device_flag"] = True
        assert Display.projection(view["static_camera_onboarding"], view) is None
        assert all(ERROR in text for text in render_snapshot(view))


def test_nullable_published_mode_is_a_design_gap_not_received_mode(complete_setup):
    view = fixture(complete_setup)
    view["static_camera_onboarding"]["contract"]["receipt"]["design"][
        "published_mode"
    ] = None
    assert all(
        "No unique matching published design mode retained" in text
        for text in rendered(view)
    )


def test_legacy_snapshot_does_not_infer_static_acceptance(complete_setup):
    view = fixture(complete_setup)
    del view["static_camera_onboarding"]
    for text in render_snapshot(view):
        assert "No static-camera onboarding projection in this legacy snapshot" in text
        assert ACCEPTED not in text and ERROR not in text


def test_initialized_storage_before_prerequisites_has_no_design_subject(complete_setup):
    view = fixture(complete_setup)
    setup = view["physical_camera_setup"]
    setup["prerequisites"] = None
    setup["requirements_provenance"] = "NONE"
    for row in setup["session"]["stages"]:
        row.update(state="PENDING", last_event_sequence=None, evidence_ids=[])
    value = view["static_camera_onboarding"]
    value.update(status="NOT_STARTED", contract=None, original_context=None)
    value["stage_states"] = dict.fromkeys(value["stage_states"], "PENDING")
    for text in rendered(view):
        assert ACCEPTED not in text
        assert "No complete static contract is published" in text
