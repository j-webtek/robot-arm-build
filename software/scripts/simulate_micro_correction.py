"""Run synthetic policy scenarios only; optional new JSON report, never overwrite."""
import argparse
import json
from pathlib import Path

from rocell.arm.micro_correction_simulator import scenarios

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    results = scenarios()
    if args.output:
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(results, stream, indent=2)
            stream.write('\n')
    print(json.dumps({name: result['reason'] for name, result in results.items()}, indent=2))
