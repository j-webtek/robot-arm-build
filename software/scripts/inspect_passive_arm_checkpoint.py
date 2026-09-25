"""Read-only inspection of one named historical diagnostic, with no replay."""

import argparse
import json
from pathlib import Path

from rocell.application.passive_arm_diagnostic_checkpoint import recover


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    args = parser.parse_args()
    try:
        result = recover(args.checkpoint)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "UNVERIFIED",
                    "error_type": type(exc).__name__,
                    "physical_authority": False,
                    "replay_allowed": False,
                }
            )
        )
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
