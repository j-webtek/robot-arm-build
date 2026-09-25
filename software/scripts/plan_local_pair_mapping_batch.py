"""Export the frozen r48 multi-endpoint shoulder mapping plan; offline only."""
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.local_pair_mapping_batch import plan_mapping_batch
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export(
        {"mode": "local-pair-mapping-batch-plan"},
        [],
        attachments={"local-pair-mapping-batch-plan.json": canonical(plan_mapping_batch())},
    )
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Mapping plan export failed verification")
    print(saved["path"])


if __name__ == "__main__":
    main()
