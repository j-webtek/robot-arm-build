"""Export the exact r46/r47-supported local compensation policy; offline only."""
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.local_pair_compensation_policy import promote
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


COMPARISON = "wizard-20260920T211756163014Z-475119d6344843309d3d757d35f9e1da"
CANDIDATE_AUDIT = "wizard-20260920T211126005982Z-3df6c381baf34322a51b2a912a2fb02e"


def build(exports):
    comparison, comparison_hash = _read(
        exports, COMPARISON, "attachment-second-heldout-comparison.json")
    audit, _ = _read(exports, CANDIDATE_AUDIT, "attachment-next-validation-terminal-review.json")
    run_path = Path(audit["source_run"])
    if run_path.parent.resolve() != exports.resolve():
        raise ValueError("Candidate run outside assigned export folder")
    run, _ = _read(exports, run_path.name, "attachment-smoke-run.json")
    policy = promote(comparison, run["challenge"]["manifest"],
                     comparison_export=COMPARISON, comparison_sha256=comparison_hash)
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({"mode": "local-pair-compensation-policy"}, [], attachments={
        "local-pair-compensation-policy.json": canonical(policy)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Local compensation policy export failed")
    return saved["path"]


if __name__ == "__main__":
    print(build(Path(__file__).resolve().parents[1] / "runs/wizard-exports"))
