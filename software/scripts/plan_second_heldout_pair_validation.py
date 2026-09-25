"""Export the frozen second held-out pair test plan; never contacts the arm."""
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.second_heldout_pair_validation import draft
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
    text = """# Second held-out shoulder-pair validation

The model remains frozen. This reverse-direction endpoint is deliberately more discriminating than the first held-out tie.

- desired measured endpoint: `2387/1729`
- candidate command: `2378/1736`; frozen prediction: `2387.667/1729`
- direct control command: `2386/1728`; frozen predicted error: `+3/-5`
- both terminal trials use the same immediate lower-to-upper approach history
- one campaign admission per variant; no retry or automatic return

The control includes one extra setup leg only to avoid a meaningless near-zero first command from the candidate predecessor. This remains an encoder-space test; it does not establish Cartesian, keyboard, stylus, or camera accuracy.
"""
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({"mode": "second-heldout-pair-validation-plan"}, [], attachments={
        "second-heldout-pair-plan.json": canonical(plan),
        "second-heldout-pair-plan.md": text.encode()})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Second held-out plan export failed")
    return saved["path"]


if __name__ == "__main__":
    print(build(Path(__file__).resolve().parents[1] / "runs/wizard-exports"))
