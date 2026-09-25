"""Reassess all seven retained controller records and export a cycle review."""
import json
from pathlib import Path

from rocell.application.air_typing_cycle_review import export_retained_cycle


if __name__=="__main__":
    root=Path(__file__).resolve().parents[1]/"runs/wizard-exports"
    report,path=export_retained_cycle(root)
    print(json.dumps(dict(status=report["status"],export_path=path,
                          maximum_repeated_A_arrival_delta_counts=
                          report["maximum_repeated_A_arrival_delta_counts"],
                          compensation_supported=report["compensation_supported"])))
