"""Export synthetic command-strategy comparisons; never contacts the robot."""
import argparse
import json
from pathlib import Path
from rocell.arm.command_strategy_simulation import compare

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    records=compare()
    if args.output:
        with args.output.open('x',encoding='utf-8') as stream:
            json.dump(records,stream,indent=2)
            stream.write('\n')
    print(json.dumps([{k:r[k] for k in ('strategy','model','reason','final_error_deg')}
                      for r in records],indent=2))
