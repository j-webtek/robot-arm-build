"""Export the frozen r61 four-leg interval plan; no hardware access."""
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.visible_interval_campaign import plan_visible_interval_campaign
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root = Path(__file__).resolve().parents[1]
    exports = root / "runs/wizard-exports"
    plan = plan_visible_interval_campaign()
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "visible-interval-campaign-plan"}, [], attachments={
        "visible-interval-campaign-plan.json": canonical(plan),
    })
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Visible interval plan export invalid")
    print(json.dumps({
        "export_path": saved["path"],
        "plan_sha256": plan["plan_sha256"],
        "legs": plan["manifest"]["legs"],
        "goals": plan["manifest"]["goals"],
        "hardware_access": False,
        "movement_authorized": False,
    }))


if __name__ == "__main__":
    main()

