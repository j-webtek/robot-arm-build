"""Compare verified r46/r47 terminal evidence, including retained no-response control."""
import argparse
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


DESIRED = [2387, 1729]
FIXED = {
    "second_heldout_candidate": [[2377, 1737], [2389, 1725], [2378, 1736]],
    "second_heldout_control": [[2389, 1725], [2377, 1737], [2389, 1725], [2386, 1728]],
}


def _source(exports, path, attachment):
    selected = Path(path)
    if selected.parent.resolve() != exports.resolve():
        raise ValueError("Source outside assigned export folder")
    return _read(exports, selected.name, attachment)[0]


def load_trial(exports, audit_id, variant):
    audit, digest = _read(exports, audit_id, "attachment-next-validation-terminal-review.json")
    if (audit.get("variant") != variant or audit.get("terminal_measurement_usable") is not True or
            audit.get("desired") != DESIRED or audit.get("general_compensation_validated") is not False):
        raise ValueError("Usable second held-out terminal audit required")
    run = _source(exports, audit["source_run"], "attachment-smoke-run.json")
    record = _source(exports, audit["source_result"], "attachment-characterization-result.json")
    expected, trial = FIXED[variant], len(FIXED[variant]) - 1
    if (run.get("challenge", {}).get("manifest", {}).get("goals") != expected or
            record.get("leg") != trial or record.get("goals") != expected):
        raise ValueError("Fixed second held-out trial identity differs")
    if variant.endswith("candidate"):
        if run.get("status") != "COMPLETE" or len(run.get("legs", [])) != 3:
            raise ValueError("Complete r46 candidate evidence required")
        terminal = run["legs"][-1]
        if terminal.get("export_path") != audit["source_result"]:
            raise ValueError("Candidate terminal path differs")
    else:
        failed = run.get("failed_leg_export", {})
        fault = run.get("fault_export", {})
        if (run.get("status") != "INCONCLUSIVE" or len(run.get("legs", [])) != 3 or
                failed.get("leg") != 3 or failed.get("export_path") != audit["source_result"] or
                failed.get("receipt_issued") is not False or fault.get("reason") != "NO_CLEAR_RESPONSE"):
            raise ValueError("Retained r47 no-response terminal evidence required")
    before = [record["baseline"]["joints"][i]["position"] for i in (1, 2)]
    actual = [record["observations"][-1]["joints"][i]["position"] for i in (1, 2)]
    if before != audit["before"] or actual != audit["actual"]:
        raise ValueError("Audit and raw terminal endpoint differ")
    prediction = _source(exports, run["baseline_review"]["prediction_export"],
                         "attachment-next-validation-predictions.json")
    if (prediction.get("variant") != variant or prediction.get("targets") != expected or
            prediction.get("desired") != DESIRED):
        raise ValueError("Frozen prediction provenance differs")
    return audit, digest, prediction["frozen_models"], run


def compare(exports, candidate_id, control_id):
    candidate, chash, cmodel, _ = load_trial(
        exports, candidate_id, "second_heldout_candidate")
    control, uhash, umodel, control_run = load_trial(
        exports, control_id, "second_heldout_control")
    if cmodel != umodel:
        raise ValueError("Frozen models differ")
    starts_match = all(abs(a-b) <= 1 for a, b in zip(candidate["before"], control["before"]))
    metric = lambda values: dict(max_abs=max(map(abs, values)), l1=sum(map(abs, values)),
                                 squared=sum(value*value for value in values))
    ce = [a-d for a, d in zip(candidate["actual"], DESIRED)]
    ue = [a-d for a, d in zip(control["actual"], DESIRED)]
    cm, um = metric(ce), metric(ue)
    result = dict(schema="rocell.second_heldout_candidate_control_comparison.v1",
        candidate_export=candidate_id, control_export=control_id,
        candidate_audit_sha256=chash, control_audit_sha256=uhash,
        candidate_before=candidate["before"], control_before=control["before"],
        starts_match_within_one_count=starts_match, desired=DESIRED,
        candidate_actual=candidate["actual"], control_actual=control["actual"],
        candidate_error=ce, control_error=ue,
        candidate_metrics=cm, control_metrics=um,
        control_terminal_outcome="NO_CLEAR_RESPONSE",
        control_write_attempted=control_run["failed_leg_export"]["leg"] == 3,
        candidate_improves_max_abs_error=cm["max_abs"] < um["max_abs"],
        candidate_improves_all_primary_metrics=all(cm[k] < um[k] for k in cm),
        model_sha256=cmodel["sha256"], model_refitted=False,
        comparison_eligible=starts_match,
        local_reverse_compensation_supported=starts_match and cm["max_abs"] < um["max_abs"],
        general_compensation_validated=False, hardware_access=False, movement_authorized=False)
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({"mode": "second-heldout-candidate-control-comparison"}, [],
        attachments={"second-heldout-comparison.json": canonical(result)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Second held-out comparison export failed")
    return saved["path"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-audit", required=True)
    parser.add_argument("--control-audit", required=True)
    args = parser.parse_args()
    print(compare(Path(__file__).resolve().parents[1] / "runs/wizard-exports",
                  args.candidate_audit, args.control_audit))
