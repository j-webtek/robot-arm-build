"""Run one named synthetic diagnostic with verified export/replay; no hardware."""
import argparse
import json
from pathlib import Path
from rocell.application.servo_diagnostic_rehearsal import run_rehearsal
from rocell.application.servo_diagnostic_simulation import SCENARIOS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scenario',choices=SCENARIOS)
    parser.add_argument('--export-root',type=Path,
        default=Path(__file__).resolve().parents[1]/'runs/wizard-exports')
    args=parser.parse_args()
    print(json.dumps(run_rehearsal(args.export_root,args.scenario)))


if __name__=='__main__':main()
