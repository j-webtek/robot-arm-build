"""Actual NC-01 source/calculations; injected review digests are not M1 reviews."""

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path

import pytest

from rocell.application import rehearsal_noncontact_stage as nc
from rocell.application.rehearsal_noncontact_binding import (
    RehearsalNoncontactBinding,
    canonical,
)
from rocell.application.rehearsal_reference_stage import read_reference_source_context
from rocell.application.context import load_simulation_context
from rocell.application.collision_readiness import assess_current_collision_readiness
from rocell.application.wizard_diagnostic_export import (
    sanitize_diagnostic_record,
    WizardDiagnosticExporter,
    verify_export,
)
from test_rehearsal_reference_binding import make_binding

WORKSPACE = Path(__file__).resolve().parents[3]


def make_noncontact_binding():
    """Real fixed source snapshot plus explicitly injected reviewed-parent hashes."""
    reference = make_binding(read_reference_source_context(WORKSPACE))
    return RehearsalNoncontactBinding(
        reference,
        "noncontact-operator",
        "1" * 64,
        "2" * 64,
        "3" * 64,
        "4" * 64,
        nc.read_noncontact_source_context(WORKSPACE),
    )


@pytest.fixture(scope="module")
def actual():
    binding = make_noncontact_binding()
    evidence = nc.evaluate_rehearsal_noncontact_stage(WORKSPACE, binding)
    return binding, evidence, hashlib.sha256(Path(nc.__file__).read_bytes()).hexdigest()


def verify(document, actual, *, binding=None):
    expected, _, source = actual
    payload = canonical(document)
    return nc.verify_rehearsal_noncontact_evidence(
        payload,
        expected_binding=binding or expected,
        expected_evidence_sha256=hashlib.sha256(payload).hexdigest(),
        expected_evaluator_source_sha256=source,
    )


def test_actual_full_historical_report_and_nominal_gaps_not_fault_success(actual):
    binding, evidence, _ = actual
    assert evidence.outcome == "BLOCKED"
    checks = evidence.checks
    assert len(checks) == 8
    assert [row["passed"] for row in checks if row["check_kind"] == "NOMINAL"] == [
        False
    ] * 3
    assert all(row["passed"] for row in checks if row["check_kind"] != "NOMINAL")
    context = load_simulation_context(
        WORKSPACE, WORKSPACE / "software/config/system_manifest.json"
    )
    assert (
        evidence.to_dict()["technical_reports"]["historical_collision"]
        == assess_current_collision_readiness(context).to_dict()
    )
    summary = evidence.safe_summary()
    assert summary["collision_historical"]["required_body_count"] == 19
    assert summary["collision_historical"]["proxy_body_count"] == 6
    assert summary["collision_historical"]["urdf_collision_element_count"] == 0
    assert summary["static_geometry"]["required_body_count"] == 26
    assert len(summary["static_geometry"]["missing_geometry_body_ids"]) == 26
    assert summary["static_geometry"]["required_source_count"] == 9
    assert len(summary["static_geometry"]["missing_source_keys"]) == 5
    assert len(summary["accuracy"]["unmeasured_term_ids"]) == 10
    assert summary["accuracy"]["conservative_error_micrometers"] is None
    assert summary["accuracy"]["remaining_margin_micrometers"] is None
    assert summary["selection"]["keyboard_targets_evaluated"] == 0
    assert summary["selection"]["phone_targets_evaluated"] == 0
    assert summary["selection"]["tool_case_id"] == "nominal_tool_100mm"
    assert summary["not_evaluated"] == [
        "POSE",
        "ROUTE",
        "SENSITIVITY",
        "VISIBILITY",
        "DYNAMICS",
        "PHYSICAL_MOTION",
    ]
    assert all(
        value == 0 for value in evidence.to_dict()["actual_physical_effects"].values()
    )
    assert (
        evidence.to_dict()["binding"]["reference_binding"]["operator_id"]
        == "test-operator"
    )
    assert (
        evidence.to_dict()["binding"]["operator_id"]
        == binding.operator_id
        != "test-operator"
    )


def test_real_typed_assessments_and_complete_lossless_common_input_reconstruction(
    actual,
):
    binding, evidence, _ = actual
    technical = evidence.to_dict()["technical_reports"]
    policy = nc.load_target_accuracy_budget_policy(WORKSPACE)
    for case in technical["accuracy_cases"]:
        clock, target, terms, observations = nc._typed_case(
            technical["accuracy_common"], case
        )
        from dataclasses import asdict

        expected = nc.assess_target_accuracy_budget(
            policy,
            observations,
            term_bindings=terms,
            assessment_context=clock,
            target_geometry=target,
        )
        assert nc._plain(asdict(expected)) == case["result"]
    controls = evidence.safe_summary()["accuracy"]["controls"]
    assert [row["case_id"] for row in controls] == list(nc._CASES)
    assert controls[4]["eroded_target_radius_micrometers"] == -500
    assert controls[4]["remaining_margin_micrometers"] == -1500
    assert controls[5]["conservative_error_micrometers"] == 1000
    assert controls[5]["remaining_margin_micrometers"] == 3000
    assert all(row["conservative_error_micrometers"] is None for row in controls[:4])
    assert (
        verify(evidence.to_dict(), actual).canonical_bytes()
        == evidence.canonical_bytes()
    )


def test_pure_verify_view_never_reads_source_or_reruns_evaluator_assessor_solver(
    actual, monkeypatch
):
    binding, evidence, source = actual

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "retained verification must not execute work or read files"
        )

    for name in (
        "evaluate_rehearsal_noncontact_stage",
        "read_noncontact_source_context",
        "read_reference_source_context",
        "load_simulation_context",
        "revalidate_simulation_context",
        "assess_current_collision_readiness",
        "assess_target_accuracy_budget",
        "load_target_accuracy_budget_policy",
    ):
        monkeypatch.setattr(nc, name, forbidden)
    for name in ("open", "read_bytes", "read_text", "stat", "lstat", "resolve"):
        monkeypatch.setattr(Path, name, forbidden)
    result = nc.verify_rehearsal_noncontact_evidence(
        evidence.canonical_bytes(),
        expected_binding=binding,
        expected_evidence_sha256=evidence.evidence_sha256,
        expected_evaluator_source_sha256=source,
    )
    assert result.safe_summary() == evidence.safe_summary()
    assert result.checks == evidence.checks


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(extra=False),
        lambda d: d.update(physical_authority=True),
        lambda d: d.update(outcome="REHEARSAL_CHECKS_PASSED"),
        lambda d: d["checks"][0].update(passed=True),
        lambda d: d["checks"].pop(),
        lambda d: d["provenance"].update(source_domain="RANK_1_OVERLAY"),
        lambda d: d["actual_physical_effects"].update(device_opens=1),
        lambda d: d["technical_reports"].pop("accuracy_common"),
        lambda d: d["technical_reports"]["historical_collision"]["contract"][
            "bodies"
        ].pop(),
        lambda d: d["technical_reports"]["historical_collision"][
            "geometry_audit"
        ].update(diagnostic_ready=True),
        lambda d: d["technical_reports"]["historical_collision"]["verified_sources"][
            "urdf"
        ].update(collision_element_count=1),
        lambda d: d["technical_reports"]["static_inventory"]["requirements"].pop(),
        lambda d: d["technical_reports"]["static_inventory"]["source_inventory"].pop(),
        lambda d: d["technical_reports"]["static_inventory"]["geometry"][0].update(
            state="MEASURED"
        ),
        lambda d: d["technical_reports"]["accuracy_common"]["observations"].pop(),
        lambda d: d["technical_reports"]["accuracy_common"]["observations"][0].update(
            bound_micrometers=0
        ),
        lambda d: d["technical_reports"]["accuracy_common"]["term_bindings"][0].update(
            evidence_sha256="9" * 64
        ),
        lambda d: d["technical_reports"]["accuracy_cases"].pop(),
        lambda d: d["technical_reports"]["accuracy_cases"][2][
            "observation_replacements"
        ][0]["provenance"].update(valid_until_unix_ns=3000),
        lambda d: d["technical_reports"]["accuracy_cases"][4]["result"].update(
            remaining_margin_micrometers=0
        ),
        lambda d: d["technical_reports"]["accuracy_cases"][5]["result"].update(
            conservative_error_micrometers=True
        ),
        lambda d: d["safe_summary"]["selection"].update(phone_targets_evaluated=29),
        lambda d: d["safe_summary"]["static_geometry"].update(required_body_count=25),
        lambda d: d["safe_summary"]["accuracy"].update(remaining_margin_micrometers=0),
    ],
)
def test_complete_result_tamper_rejects_even_with_rehashed_outer(actual, mutation):
    document = actual[1].to_dict()
    mutation(document)
    with pytest.raises(nc.RehearsalNoncontactError):
        verify(document, actual)


@pytest.mark.parametrize(
    "field",
    [
        "predecessor_receipt_sha256",
        "predecessor_assessment_sha256",
        "predecessor_review_sha256",
        "reference_evidence_sha256",
        "operator_id",
    ],
)
def test_stale_or_other_review_binding_rejects(actual, field):
    changed = replace(
        actual[0], **{field: "other-operator" if field == "operator_id" else "9" * 64}
    )
    with pytest.raises(nc.RehearsalNoncontactError):
        verify(actual[1].to_dict(), actual, binding=changed)


@pytest.mark.parametrize(
    "field",
    [
        "session_id",
        "cell_id",
        "workspace_source_sha256",
        "controller_binding_sha256",
        "final_power_observation_sha256",
        "camera_capture_receipt_sha256",
    ],
)
def test_reference_dependency_binding_change_rejects(actual, field):
    parent = replace(
        actual[0].reference_binding,
        **{field: "other-session" if field.endswith("_id") else "9" * 64}
    )
    changed = replace(actual[0], reference_binding=parent)
    with pytest.raises(nc.RehearsalNoncontactError):
        verify(actual[1].to_dict(), actual, binding=changed)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"{}",
        b"null",
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b" " * (112 * 1024 + 1),
        "not-bytes",
    ],
    ids=["empty", "object", "null", "duplicate", "nan", "oversized", "not-bytes"],
)
def test_noncanonical_or_unbounded_input_denied(actual, payload):
    with pytest.raises(nc.RehearsalNoncontactError):
        nc.verify_rehearsal_noncontact_evidence(
            payload,
            expected_binding=actual[0],
            expected_evidence_sha256="9" * 64,
            expected_evaluator_source_sha256=actual[2],
        )


def test_all_external_hashes_required_and_checked(actual):
    binding, evidence, source = actual
    for eh, sh in (("9" * 64, source), (evidence.evidence_sha256, "9" * 64)):
        with pytest.raises(nc.RehearsalNoncontactError):
            nc.verify_rehearsal_noncontact_evidence(
                evidence.canonical_bytes(),
                expected_binding=binding,
                expected_evidence_sha256=eh,
                expected_evaluator_source_sha256=sh,
            )
    with pytest.raises(TypeError):
        nc.verify_rehearsal_noncontact_evidence(
            evidence.canonical_bytes(), expected_binding=binding
        )


def test_evidence_and_binding_are_immutable_detached(actual):
    binding, evidence, _ = actual
    raw, sha = evidence.canonical_bytes(), binding.binding_sha256
    evidence.to_dict()["technical_reports"].clear()
    evidence.safe_summary()["accuracy"].clear()
    evidence.checks[0]["passed"] = True
    binding.to_dict()["reference_binding"]["source_context"].clear()
    binding.source_context["scene"].clear()
    assert binding.binding_sha256 == sha and evidence.canonical_bytes() == raw
    with pytest.raises(FrozenInstanceError):
        evidence._payload = b"{}"
    with pytest.raises(FrozenInstanceError):
        binding.operator_id = "changed"


def test_source_changes_before_or_after_collection_fail_closed(actual, monkeypatch):
    binding = actual[0]
    original = nc.read_noncontact_source_context
    calls = []

    def changed(workspace):
        calls.append(1)
        result = json.loads(original(workspace))
        if len(calls) > 1:
            result["scene"]["design_revision"] = "changed"
        return canonical(result)

    monkeypatch.setattr(nc, "read_noncontact_source_context", changed)
    with pytest.raises(nc.RehearsalNoncontactError, match="after calculation"):
        nc.evaluate_rehearsal_noncontact_stage(WORKSPACE, binding)
    changed_source = binding.source_context
    changed_source["scene"]["design_revision"] = "changed"
    swapped = replace(binding, source_context_json=canonical(changed_source))
    monkeypatch.setattr(nc, "read_noncontact_source_context", original)
    with pytest.raises(nc.RehearsalNoncontactError, match="fresh source"):
        nc.evaluate_rehearsal_noncontact_stage(WORKSPACE, swapped)


def test_complete_public_and_failure_and_export_envelopes_fit_losslessly(
    actual, tmp_path
):
    """Exact root nesting shapes; publication/M1 ownership is not simulated here."""
    binding, evidence, _ = actual
    report = evidence.to_dict()
    receipt = {
        "schema": "rocell.rehearsal_noncontact_receipt.v1",
        "session_id": binding.session_id,
        "evaluation": report,
        "evaluation_sha256": evidence.evidence_sha256,
        "physical_authority": False,
    }
    normal = {
        "steps": [{"report": {"status": "COLLECTED"}}, {"report": report}],
        "physical_authority": False,
    }
    failure = {
        "failure": {"retained_noncontact_receipt": receipt},
        "physical_authority": False,
    }
    exported = {
        "schema": "rocell.noncontact_export.v1",
        "publication": "HISTORICAL_HELD",
        "original_bytes_preserved": True,
        "receipt": receipt,
        "physical_authority": False,
        "meaning": "Diagnostic only",
    }
    assert len(canonical(receipt)) < 128 * 1024
    assert len(evidence.canonical_bytes()) < nc.MAX_EVIDENCE_BYTES
    for envelope in (normal, failure, exported):
        assert (
            sanitize_diagnostic_record(envelope, maximum_bytes=1024 * 1024) == envelope
        )
    exporter = WizardDiagnosticExporter(tmp_path / "export")
    exporter.prepare(create=True)
    saved = exporter.export(
        {"physical_authority": False},
        [],
        attachments={"noncontact.json": canonical(exported)},
    )
    folder = Path(saved["path"])
    verify_export(folder)
    retained = json.loads((folder / "attachment-noncontact.json").read_bytes())
    assert canonical(retained["receipt"]["evaluation"]) == evidence.canonical_bytes()
