"""Pure binding contracts. These injected dependencies are not physical reviews."""

from dataclasses import FrozenInstanceError, replace
import json

import pytest

from rocell.application.rehearsal_reference_binding import (
    RehearsalReferenceBinding,
    ReviewedReferencePredecessor,
)


def encoded(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def make_binding(context=None):
    if context is None:
        context = {
            "schema": "rocell.rehearsal_reference_sources.v1",
            "static_phase1_graph_sha256": "1" * 64,
            "static_phase1_context_hashes": {"test-only-source": "2" * 64},
            "nominal_geometry": {"fixture": "NOT_A_QUALIFIED_GEOMETRY_INPUT"},
        }
    return RehearsalReferenceBinding(
        "a" * 64,
        "b" * 64,
        "test-cell",
        "test-session",
        "test-operator",
        tuple(
            ReviewedReferencePredecessor(stage, "c" * 64, "d" * 64, "e" * 64, "f" * 64)
            for stage in (
                "optics_intrinsics",
                "static_registration",
                "feedback_only_connection",
            )
        ),
        "1" * 64,
        "2" * 64,
        "3" * 64,
        "4" * 64,
        "5" * 64,
        "6" * 64,
        "7" * 64,
        "8" * 64,
        encoded(context),
    )


def test_binding_is_immutable_and_detaches_all_nested_views():
    value = make_binding()
    before = value.binding_sha256
    value.source_context["nominal_geometry"]["fixture"] = "CHANGED"
    value.to_dict()["predecessors"][0]["receipt_sha256"] = "9" * 64
    assert value.binding_sha256 == before
    assert value.to_dict()["stage"] == "reference_frame_calibration"
    assert value.to_dict()["physical_authority"] is False
    assert value.to_dict()["camera_input_role"] == "DEPENDENCY_ONLY_NOT_NUMERIC_INPUT"
    with pytest.raises(FrozenInstanceError):
        value.operator_id = "another"


@pytest.mark.parametrize(
    "field",
    [
        "workspace_source_sha256",
        "catalog_sha256",
        "camera_capture_receipt_sha256",
        "feedback_binding_sha256",
        "campaign_context_binding_sha256",
        "retained_campaign_sha256",
        "feedback_inner_evidence_sha256",
        "feedback_request_sha256",
        "controller_binding_sha256",
        "final_power_observation_sha256",
    ],
)
def test_each_hash_domain_is_distinct_and_bound(field):
    value = make_binding()
    assert replace(value, **{field: "9" * 64}).binding_sha256 != value.binding_sha256
    for bad in (None, True, 1, "0" * 64, "A" * 64, "a" * 63):
        with pytest.raises(ValueError):
            replace(value, **{field: bad})


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize(
    "field",
    ["receipt_sha256", "assessment_sha256", "review_sha256", "evaluation_sha256"],
)
def test_every_review_trio_and_full_evaluation_hash_is_bound(index, field):
    value = make_binding()
    prior = list(value.predecessors)
    prior[index] = replace(prior[index], **{field: "9" * 64})
    assert (
        replace(value, predecessors=tuple(prior)).binding_sha256 != value.binding_sha256
    )


@pytest.mark.parametrize("mutation", ["reorder", "missing", "duplicate", "list"])
def test_exact_ordered_review_predecessors_required(mutation):
    value = make_binding()
    prior = value.predecessors
    changed = {
        "reorder": prior[::-1],
        "missing": prior[:2],
        "duplicate": (prior[0], prior[0], prior[2]),
        "list": list(prior),
    }[mutation]
    with pytest.raises(ValueError):
        replace(value, predecessors=changed)


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "missing",
        "duplicate",
        "noncanonical",
        "empty",
        "oversized",
        "mutable",
        "invalid-hash",
        "nan",
    ],
)
def test_source_snapshot_cannot_be_mutable_ambiguous_or_unbounded(mutation):
    value = make_binding()
    context = value.source_context
    changed = value.source_context_json
    if mutation == "extra":
        context["extra"] = True
        changed = encoded(context)
    elif mutation == "missing":
        del context["nominal_geometry"]
        changed = encoded(context)
    elif mutation == "duplicate":
        changed = changed[:-1] + b',"nominal_geometry":{}}'
    elif mutation == "noncanonical":
        changed += b"\n"
    elif mutation == "empty":
        changed = b""
    elif mutation == "oversized":
        changed = b" " * (16 * 1024 + 1)
    elif mutation == "mutable":
        changed = bytearray(changed)
    elif mutation == "invalid-hash":
        context["static_phase1_context_hashes"]["test-only-source"] = "0" * 64
        changed = encoded(context)
    else:
        changed = changed.replace(b'"NOT_A_QUALIFIED_GEOMETRY_INPUT"', b"NaN")
    with pytest.raises(ValueError):
        replace(value, source_context_json=changed)


@pytest.mark.parametrize("field", ["cell_id", "session_id", "operator_id"])
@pytest.mark.parametrize("value", [None, True, "", "x y", "x" * 97])
def test_unbounded_or_untyped_actor_context_rejected(field, value):
    with pytest.raises(ValueError):
        replace(make_binding(), **{field: value})
