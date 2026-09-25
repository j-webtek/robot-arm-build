"""Read one rehearsal intent/outcome pair without reconnecting or replaying."""

import argparse
import json
from pathlib import Path
from rocell.application.passive_arm_diagnostic_checkpoint import recover_attempt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("diagnostic_root", type=Path)
    parser.add_argument("session_id")
    args = parser.parse_args()
    try:
        report = recover_attempt(args.diagnostic_root, args.session_id)
    except Exception as exc:
        print(
            json.dumps(
                dict(
                    status="UNVERIFIED_NO_REPLAY",
                    error_type=type(exc).__name__,
                    physical_authority=False,
                    replay_allowed=False,
                )
            )
        )
        return 2
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "HISTORICAL_PAIR_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
