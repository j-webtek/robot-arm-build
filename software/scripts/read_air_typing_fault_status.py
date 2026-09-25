"""Bounded signed GET-only sequence reconciliation after stopped r75 campaign."""
import argparse
import json
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.first_motion_contract import canonical
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--startup-export", required=True)
    parser.add_argument("--min-sequence", type=int, default=1)
    parser.add_argument("--max-sequence", type=int, default=512)
    args = parser.parse_args()
    if not 1 <= args.min_sequence <= args.max_sequence <= 512:
        raise ValueError("Bounded GET-only range required")
    root = Path(__file__).resolve().parents[1]
    binding = review_recovery_startup(root, args.startup_export, revision=75)
    key = load_reviewed_key(root)
    accepted = None
    for sequence in range(args.min_sequence, args.max_sequence + 1):
        client = CharacterizationHTTP(binding["address"], key=key, boot=binding["expected_boot"],
                                      read_only_initial_sequence=sequence)
        try:
            raw = client("GET", "/rocell/air-type/status")
        except ValueError as error:
            if str(error) != "Response sequence mismatch" and "Authenticated HTTP failure" not in str(error):
                raise
            continue
        accepted = dict(sequence=sequence, raw_status=raw.decode("ascii"),
                        boot=binding["expected_boot"], hardware_access=True,
                        request_method="GET", movement_command_sent=False)
        break
    if accepted is None:
        raise ValueError("No accepted read-only sequence in bounded range")
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r75-air-typing-read-only-fault-status"}, [], attachments={
        "r75-air-typing-fault-status.json": canonical(accepted)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Status export invalid")
    print(json.dumps(dict(**accepted, export_path=saved["path"])))


if __name__ == "__main__":
    main()
