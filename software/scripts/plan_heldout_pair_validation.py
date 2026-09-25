"""Export a frozen-model held-out pair test plan; never contacts the arm."""
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.heldout_pair_validation import draft
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


EVIDENCE = "wizard-20260920T195904937964Z-0a6902dbff5340e887db1d93b27259f6"
MODEL_SOURCE = "wizard-20260920T170731881182Z-5aa06999afa04b93a1c450b826e54391"


def build(exports):
    evidence, evidence_hash = _read(exports, EVIDENCE, "attachment-bidirectional-evidence.json")
    proposal, proposal_hash = _read(exports, MODEL_SOURCE, "attachment-repeatability-plan.json")
    if (evidence.get("schema") != "rocell.bidirectional_pair_evidence.v1" or
            evidence.get("hardware_access") is not False or
            evidence.get("movement_authorized") is not False):
        raise ValueError("Verified offline bidirectional evidence required")
    plan = draft(proposal["frozen_models"], [[0, 4095]] * 7,
                 evidence_export=EVIDENCE,
                 evidence_model_sha256=evidence["frozen_model_sha256"])
    plan["source_bidirectional_evidence_sha256"] = evidence_hash
    plan["source_frozen_plan_export"] = MODEL_SOURCE
    plan["source_frozen_plan_sha256"] = proposal_hash
    text = """# Nearby held-out shoulder-pair validation

The frozen model is not refit. Both candidate and control first move to the same lower target, then approach the new desired encoder endpoint `2390/1725` from a matched lower state. A redundant upper leg was removed because simulation showed it would be a near-zero first command after the candidate predecessor and would correctly trigger the clear-response stop.

- candidate terminal target: `2388/1726`; frozen predicted endpoint: `2390/1725`
- control terminal target: `2389/1725`; frozen predicted endpoint: `2391/1724`
- matched-start tolerance: 1 count per selected joint
- one campaign admission per variant; no retry or automatic return
- a fresh pose reacquisition and renewed clearance decision are required before physical execution

This is a local encoder-space interpolation test. It does not validate Cartesian position, keyboard contact, camera registration, or general compensation.
"""
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({"mode": "heldout-pair-validation-plan"}, [], attachments={
        "heldout-pair-plan.json": canonical(plan), "heldout-pair-plan.md": text.encode()})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Held-out plan export failed")
    return saved["path"]


if __name__ == "__main__":
    print(build(Path(__file__).resolve().parents[1] / "runs/wizard-exports"))
