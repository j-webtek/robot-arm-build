"""Reassess all six retained controller records and export repeatability evidence."""
import json
from pathlib import Path

from rocell.application.air_typing_r79_review import export_review


if __name__=="__main__":
    root=Path(__file__).resolve().parents[1]/"runs/wizard-exports"
    report,path=export_review(root)
    print(json.dumps(dict(status=report["status"],export_path=path,
                          maximum_pair_difference_counts=report["maximum_pair_difference_counts"],
                          retract_elbow_goal_error_counts=report["retract_elbow_goal_error_counts"],
                          compensation_supported=report["compensation_supported"])))
