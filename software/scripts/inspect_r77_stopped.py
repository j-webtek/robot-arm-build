"""Read-only reconciliation of a stopped r77 HTTP session after host process exit.

Only signed GET requests are attempted. Wrong sequence numbers are rejected by
the controller without changing its sequence or campaign state.
"""
import argparse
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boot", required=True)
    parser.add_argument("--initial-sequence", type=int, default=1)
    parser.add_argument("--max-sequence", type=int, default=160)
    args = parser.parse_args()
    if not 1 <= args.initial_sequence <= args.max_sequence <= 256:
        raise ValueError("Bounded read-only sequence scan required")
    root=Path(__file__).resolve().parents[1]
    key = load_reviewed_key(root)
    for sequence in range(args.initial_sequence, args.max_sequence + 1):
        client = CharacterizationHTTP("192.168.0.225", key=key, boot=args.boot,
                                      read_only_initial_sequence=sequence)
        try:
            status = client("GET", "/rocell/air-type-final/status")
        except ValueError:
            continue
        report=dict(schema="rocell.r77_postfault_status.v1",boot=args.boot,
                    accepted_sequence=sequence,raw_status=status.decode("ascii"),
                    request_method="GET",movement_command_sent=False,
                    retry_allowed=False)
        exporter=WizardDiagnosticExporter(root/"runs/wizard-exports")
        exporter.prepare(create=True)
        saved=exporter.export({"mode":"r77-postfault-status"},[],attachments={
            "r77-postfault-status.json":canonical(report)})
        if not verify_export(Path(saved["path"]))["valid"]:
            raise ValueError("Postfault status export invalid")
        print({"export_path":saved["path"],**report})
        return
    raise ValueError("No accepted read-only sequence in bounded range")


if __name__ == "__main__":
    main()
