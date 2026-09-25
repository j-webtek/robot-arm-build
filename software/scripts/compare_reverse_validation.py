"""Compare verified reverse candidate/control exports without hardware or fitting."""
import argparse
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


FIXED = {
    "reverse_candidate": [[2389, 1725], [2377, 1737], [2385, 1729]],
    "reverse_control": [[2389, 1725], [2377, 1737], [2386, 1728]],
}
DESIRED = [2388, 1729]


def _source(exports: Path, path: str, attachment: str):
    selected = Path(path)
    if selected.parent.resolve() != exports.resolve():
        raise ValueError("Source outside assigned export folder")
    return _read(exports, selected.name, attachment)[0]


def load_trial(exports: Path, audit_id: str, variant: str):
    audit, digest = _read(exports, audit_id, "attachment-next-validation-terminal-review.json")
    if (
        variant not in FIXED
        or audit.get("variant") != variant
        or audit.get("terminal_measurement_usable") is not True
        or audit.get("desired") != DESIRED
        or audit.get("general_compensation_validated") is not False
    ):
        raise ValueError("Usable selected reverse terminal audit required")
    run = _source(exports, audit["source_run"], "attachment-smoke-run.json")
    record = _source(exports, audit["source_result"], "attachment-characterization-result.json")
    terminal = run.get("failed_leg_export")
    if terminal is None and run.get("legs"):
        terminal = run["legs"][-1]
    if not terminal or terminal.get("leg") != 2 or terminal.get("export_path") != audit["source_result"]:
        raise ValueError("Terminal source is not the run result")
    expected = FIXED[variant]
    if record.get("leg") != 2 or record.get("goals") != expected:
        raise ValueError("Fixed reverse trial identity differs")
    if run.get("challenge", {}).get("manifest", {}).get("goals") != expected:
        raise ValueError("Run manifest differs")
    if len(run.get("legs", [])) < 2:
        raise ValueError("Missing conditioning evidence")
    for index in (0, 1):
        leg = run["legs"][index]
        conditioning = _source(exports, leg["export_path"], "attachment-characterization-result.json")
        if (
            leg.get("leg") != index
            or conditioning.get("leg") != index
            or conditioning.get("goals") != expected
            or leg.get("assessment", {}).get("continuation_eligible") is not True
        ):
            raise ValueError("Conditioning identity differs")
    before = [record["baseline"]["joints"][index]["position"] for index in (1, 2)]
    actual = [record["observations"][-1]["joints"][index]["position"] for index in (1, 2)]
    goals = [record["baseline"]["joints"][index]["goal"] for index in (1, 2)]
    if before != audit["before"] or actual != audit["actual"] or goals != [2377, 1737]:
        raise ValueError("Audit and raw reverse endpoint differ")
    predictions = _source(
        exports,
        run["baseline_review"]["prediction_export"],
        "attachment-next-validation-predictions.json",
    )
    if (
        predictions.get("variant") != variant
        or predictions.get("targets") != expected
        or predictions.get("desired") != DESIRED
        or predictions.get("campaign") != run["challenge"]["campaign"]
        or predictions.get("reference_sha256") != run["challenge"]["reference"]
    ):
        raise ValueError("Frozen reverse prediction provenance differs")
    return audit, digest, predictions["frozen_models"]


def compare(exports: Path, candidate_id: str, control_id: str):
    candidate, candidate_hash, candidate_model = load_trial(
        exports, candidate_id, "reverse_candidate"
    )
    control, control_hash, control_model = load_trial(exports, control_id, "reverse_control")
    if candidate_model != control_model:
        raise ValueError("Frozen model differs between reverse trials")
    starts_match = all(abs(a - b) <= 1 for a, b in zip(candidate["before"], control["before"]))
    candidate_error = [a - d for a, d in zip(candidate["actual"], DESIRED)]
    control_error = [a - d for a, d in zip(control["actual"], DESIRED)]
    result = dict(
        schema="rocell.reverse_candidate_control_comparison.v1",
        candidate_export=candidate_id,
        control_export=control_id,
        candidate_audit_sha256=candidate_hash,
        control_audit_sha256=control_hash,
        candidate_before=candidate["before"],
        control_before=control["before"],
        starts_match_within_one_count=starts_match,
        desired=DESIRED,
        candidate_actual=candidate["actual"],
        control_actual=control["actual"],
        candidate_error=candidate_error,
        control_error=control_error,
        candidate_max_abs_error=max(map(abs, candidate_error)),
        control_max_abs_error=max(map(abs, control_error)),
        candidate_l1_error=sum(map(abs, candidate_error)),
        control_l1_error=sum(map(abs, control_error)),
        candidate_squared_error=sum(value * value for value in candidate_error),
        control_squared_error=sum(value * value for value in control_error),
        candidate_terminal_status=candidate["assessment"]["status"],
        candidate_terminal_reason=candidate["assessment"]["reason"],
        control_terminal_status=control["assessment"]["status"],
        control_terminal_reason=control["assessment"]["reason"],
        candidate_improves_max_abs_error=max(map(abs, candidate_error)) < max(map(abs, control_error)),
        model_sha256=candidate_model["sha256"],
        model_refitted=False,
        comparison_eligible=starts_match,
        general_compensation_validated=False,
        hardware_access=False,
        movement_authorized=False,
    )
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export(
        {"mode": "reverse-candidate-control-comparison"},
        [],
        attachments={"reverse-comparison.json": canonical(result)},
    )
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Reverse comparison export failed")
    return saved["path"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-audit", required=True)
    parser.add_argument("--control-audit", required=True)
    args = parser.parse_args()
    print(
        compare(
            Path(__file__).resolve().parents[1] / "runs/wizard-exports",
            args.candidate_audit,
            args.control_audit,
        )
    )
