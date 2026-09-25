"""Export public observed-pose/+10 settings; no private staging or hardware."""
import argparse
import json
from pathlib import Path
from rocell.application.observed_pose_candidate import export_candidate


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pose-export', required=True)
    args = parser.parse_args()
    print(json.dumps(export_candidate(Path(__file__).resolve().parents[1], args.pose_export)))
