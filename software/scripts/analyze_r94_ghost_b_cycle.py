"""Read and check the five immutable local B-cycle exports; no hardware I/O."""
import json
from pathlib import Path

from rocell.application.ghost_b_cycle_analysis import analyze
from rocell.application.wizard_diagnostic_export import verify_export


EXPORT_IDS = (
    "wizard-20260925T154253781204Z-6226d1d9fb574acc9f27a377de802e22",
    "wizard-20260925T162922982911Z-a1b2b3c564c646d986465857626bc704",
    "wizard-20260925T163122665031Z-b07afdbf3ef24d9bb63469185c2cabb0",
    "wizard-20260925T163316562825Z-9726886cc32842d49a7b4cf183498937",
    "wizard-20260925T165306016823Z-d79a8b491ee847888bc0d52e1a07899d",
)


def review(export_root: Path) -> dict:
    records = []
    for export_id in EXPORT_IDS:
        directory = Path(export_root).resolve() / export_id
        if verify_export(directory)["valid"] is not True:
            raise ValueError(f"Invalid B-cycle export {export_id}")
        records.append(json.loads(
            (directory / "attachment-ghost-b-leg.json").read_text(encoding="utf-8")))
    return analyze(records)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "runs" / "wizard-exports"
    print(json.dumps(review(root), indent=2))
