"""Pure closed NC-01 lineage and immutable source snapshot boundaries."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from rocell.application.rehearsal_noncontact_binding import (
    RehearsalNoncontactBinding,
    canonical,
)
from test_rehearsal_noncontact_stage import make_noncontact_binding


@pytest.fixture(scope="module")
def binding():
    return make_noncontact_binding()


def test_inert_detached_exact_parent_provenance(binding, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("pure binding must not inspect sources")

    for name in ("open", "read_bytes", "read_text", "stat", "resolve"):
        monkeypatch.setattr(Path, name, forbidden)
    result = replace(binding, operator_id="new-operator")
    assert result.reference_binding.operator_id == "test-operator"
    assert (
        result.workspace_source_sha256
        == binding.reference_binding.workspace_source_sha256
    )
    assert result.cell_id == binding.reference_binding.cell_id
    assert result.session_id == binding.reference_binding.session_id
    assert result.catalog_sha256 == binding.reference_binding.catalog_sha256
    before = result.binding_sha256
    result.to_dict()["reference_binding"].clear()
    result.source_context["scene"].clear()
    assert result.binding_sha256 == before
    with pytest.raises(FrozenInstanceError):
        result.source_context_json = b"{}"


@pytest.mark.parametrize(
    "field,value",
    [
        ("predecessor_receipt_sha256", "0" * 64),
        ("predecessor_assessment_sha256", "A" * 64),
        ("predecessor_review_sha256", "not-a-hash"),
        ("reference_evidence_sha256", True),
        ("operator_id", ""),
        ("operator_id", "a" * 65),
        ("operator_id", " operator"),
        ("operator_id", "operator\n"),
        ("reference_binding", {}),
        ("source_context_json", "{}"),
        ("source_context_json", b"{}"),
        ("source_context_json", b" " * (32 * 1024 + 1)),
    ],
    ids=[
        "zero",
        "upper",
        "invalid",
        "bool",
        "empty-actor",
        "long-actor",
        "space-actor",
        "control-actor",
        "mapping-parent",
        "text-source",
        "empty-schema",
        "oversized-source",
    ],
)
def test_strict_hash_type_actor_source_boundary(binding, field, value):
    with pytest.raises(ValueError):
        replace(binding, **{field: value})


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(extra=True),
        lambda d: d.update(schema="physical.sources.v1"),
        lambda d: d.update(reference_source_context_sha256="9" * 64),
        lambda d: d.update(accuracy_policy_sha256="9" * 64),
        lambda d: d.update(accuracy_policy_utf8=d["accuracy_policy_utf8"] + " "),
        lambda d: d.update(dependency_source_sha256s={}),
        lambda d: d["dependency_source_sha256s"].update(unknown="bad"),
    ],
)
def test_source_snapshot_schema_hash_membership_rejects(binding, mutation):
    source = binding.source_context
    mutation(source)
    with pytest.raises(ValueError):
        replace(binding, source_context_json=canonical(source))


def test_low_level_mutated_parent_is_detected_not_resnapshotted(binding):
    parent = replace(binding.reference_binding)
    selected = replace(binding, reference_binding=parent)
    object.__setattr__(parent, "operator_id", "mutated-review-operator")
    with pytest.raises(ValueError, match="original reference binding changed"):
        selected.__post_init__()


def test_whole_original_reference_context_not_replaced_by_another_stage(binding):
    parent = binding.reference_binding
    source = parent.source_context
    source["nominal_geometry"]["tool_case_id"] = "different-overlay"
    changed = replace(parent, source_context_json=canonical(source))
    with pytest.raises(ValueError, match="reviewed reference source context differ"):
        replace(binding, reference_binding=changed)
