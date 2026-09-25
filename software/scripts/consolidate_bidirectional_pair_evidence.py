"""Consolidate verified forward/reverse shoulder evidence without hardware access."""
import argparse
import importlib.util
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


MODEL_SHA = "963df1b4975ca385e6b8d9cd9509695fdfa4838f0cab9bcde9444e28c28452e5"
DESIRED = [2388, 1729]
FORWARD_TARGETS = [[2389, 1725], [2377, 1737], [2389, 1725], [2378, 1736]]


def _sibling(name):
    path = Path(__file__).resolve().with_name(name)
    spec = importlib.util.spec_from_file_location(f"rocell_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source(exports, value, attachment):
    selected = Path(value)
    if selected.parent.resolve() != exports.resolve():
        raise ValueError("Source outside assigned export folder")
    return _read(exports, selected.name, attachment)[0]


def _load_forward_repeat(exports, audit_id):
    audit, digest = _read(exports, audit_id, "attachment-next-validation-terminal-review.json")
    if (audit.get("variant") != "forward_repeat" or
            audit.get("terminal_measurement_usable") is not True or
            audit.get("desired") != DESIRED or
            audit.get("general_compensation_validated") is not False):
        raise ValueError("Usable forward repeat audit required")
    run = _source(exports, audit["source_run"], "attachment-smoke-run.json")
    record = _source(exports, audit["source_result"], "attachment-characterization-result.json")
    if (run.get("status") != "COMPLETE" or
            run.get("challenge", {}).get("manifest", {}).get("goals") != FORWARD_TARGETS or
            len(run.get("legs", [])) != 4 or run["legs"][-1].get("export_path") != audit["source_result"] or
            record.get("leg") != 3 or record.get("goals") != FORWARD_TARGETS):
        raise ValueError("Forward repeat raw campaign differs")
    for index, leg in enumerate(run["legs"]):
        raw = _source(exports, leg["export_path"], "attachment-characterization-result.json")
        if (leg.get("leg") != index or raw.get("leg") != index or raw.get("goals") != FORWARD_TARGETS or
                leg.get("assessment", {}).get("continuation_eligible") is not True):
            raise ValueError("Forward repeat leg evidence differs")
    before = [record["baseline"]["joints"][index]["position"] for index in (1, 2)]
    actual = [record["observations"][-1]["joints"][index]["position"] for index in (1, 2)]
    if before != audit["before"] or actual != audit["actual"]:
        raise ValueError("Forward repeat audit and endpoint differ")
    predictions = _source(exports, run["baseline_review"]["prediction_export"],
                          "attachment-next-validation-predictions.json")
    if (predictions.get("variant") != "forward_repeat" or
            predictions.get("targets") != FORWARD_TARGETS or
            predictions.get("frozen_models", {}).get("sha256") != MODEL_SHA):
        raise ValueError("Forward repeat model provenance differs")
    return audit, digest


def _comparison(exports, export_id, attachment):
    value, digest = _read(exports, export_id, attachment)
    if value.get("comparison_eligible") is not True or value.get("model_refitted") is not False:
        raise ValueError("Eligible frozen comparison required")
    return value, digest


def consolidate(exports, *, control_id, candidate_id, repeat_id,
                reverse_candidate_id, reverse_control_id,
                forward_comparison_id, reverse_comparison_id):
    forward = _sibling("compare_ab_pilot.py")
    reverse = _sibling("compare_reverse_validation.py")
    control, control_hash, control_model = forward.load_trial(exports, control_id, "control")
    candidate, candidate_hash, candidate_model = forward.load_trial(exports, candidate_id, "compensated")
    repeat, repeat_hash = _load_forward_repeat(exports, repeat_id)
    reverse_candidate, reverse_candidate_hash, reverse_candidate_model = reverse.load_trial(
        exports, reverse_candidate_id, "reverse_candidate")
    reverse_control, reverse_control_hash, reverse_control_model = reverse.load_trial(
        exports, reverse_control_id, "reverse_control")
    models = [control_model, candidate_model, reverse_candidate_model, reverse_control_model]
    if any(model.get("sha256") != MODEL_SHA for model in models) or any(model != models[0] for model in models[1:]):
        raise ValueError("One unchanged frozen model is required")
    forward_comparison, forward_comparison_hash = _comparison(
        exports, forward_comparison_id, "attachment-ab-comparison.json")
    reverse_comparison, reverse_comparison_hash = _comparison(
        exports, reverse_comparison_id, "attachment-reverse-comparison.json")
    if (forward_comparison.get("control_audit_sha256") != control_hash or
            forward_comparison.get("candidate_audit_sha256") != candidate_hash or
            reverse_comparison.get("candidate_audit_sha256") != reverse_candidate_hash or
            reverse_comparison.get("control_audit_sha256") != reverse_control_hash or
            reverse_comparison.get("model_sha256") != MODEL_SHA):
        raise ValueError("Comparison-to-audit binding differs")
    if candidate["actual"] != repeat["actual"] or candidate["signed_error"] != repeat["signed_error"]:
        raise ValueError("Forward compensated endpoint did not repeat exactly")

    rows = [
        ("forward_control", control_id, control_hash, control),
        ("forward_candidate", candidate_id, candidate_hash, candidate),
        ("forward_repeat", repeat_id, repeat_hash, repeat),
        ("reverse_candidate", reverse_candidate_id, reverse_candidate_hash, reverse_candidate),
        ("reverse_control", reverse_control_id, reverse_control_hash, reverse_control),
    ]
    trials = []
    for name, export_id, digest, audit in rows:
        error = [actual - desired for actual, desired in zip(audit["actual"], DESIRED)]
        trials.append(dict(name=name, audit_export=export_id, audit_sha256=digest,
                           before=audit["before"], actual=audit["actual"], desired=DESIRED,
                           signed_error=error, maximum_absolute_error=max(map(abs, error)),
                           terminal_status=audit["assessment"]["status"],
                           terminal_reason=audit["assessment"]["reason"]))
    result = dict(
        schema="rocell.bidirectional_pair_evidence.v1", frozen_model_sha256=MODEL_SHA,
        model_refitted=False, desired=DESIRED, trials=trials,
        forward_comparison_export=forward_comparison_id,
        forward_comparison_sha256=forward_comparison_hash,
        reverse_comparison_export=reverse_comparison_id,
        reverse_comparison_sha256=reverse_comparison_hash,
        findings=dict(forward_control_max_abs_error=5, forward_candidate_max_abs_error=1,
                      forward_repeat_exact=True, reverse_control_max_abs_error=2,
                      reverse_candidate_max_abs_error=1,
                      candidate_improved_max_abs_error_in_both_directions=True),
        limitations=dict(general_compensation_validated=False,
                         workspace_accuracy_validated=False,
                         cartesian_accuracy_validated=False,
                         camera_registration_validated=False,
                         interpolation_is_not_validation=True),
        next_step="Evaluate one nearby held-out endpoint with the frozen model; do not refit.",
        hardware_access=False, movement_authorized=False)
    lines = ["# Bidirectional shoulder-pair evidence", "",
             f"Frozen model: `{MODEL_SHA}` (not refit)", "",
             "| Trial | Before | Actual | Error | Max abs |", "|---|---:|---:|---:|---:|"]
    for row in trials:
        lines.append(f"| {row['name']} | {'/'.join(map(str,row['before']))} | "
                     f"{'/'.join(map(str,row['actual']))} | {'/'.join(map(str,row['signed_error']))} | "
                     f"{row['maximum_absolute_error']} |")
    lines += ["", "Forward compensated behavior repeated exactly. Candidate targeting reduced maximum "
              "absolute error in both tested directions. This remains a local count-space result, not "
              "workspace, Cartesian, key-press, or general compensation validation."]
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({"mode": "bidirectional-pair-evidence"}, [], attachments={
        "bidirectional-evidence.json": canonical(result),
        "bidirectional-evidence.md": "\n".join(lines).encode()})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Bidirectional evidence export failed")
    return saved["path"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("control", "candidate", "repeat", "reverse-candidate", "reverse-control",
                 "forward-comparison", "reverse-comparison"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args()
    print(consolidate(Path(__file__).resolve().parents[1] / "runs/wizard-exports",
        control_id=args.control, candidate_id=args.candidate, repeat_id=args.repeat,
        reverse_candidate_id=args.reverse_candidate, reverse_control_id=args.reverse_control,
        forward_comparison_id=args.forward_comparison, reverse_comparison_id=args.reverse_comparison))
