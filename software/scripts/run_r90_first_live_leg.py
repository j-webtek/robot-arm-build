"""Run exactly the first reviewed r90 noncontact hover leg, then stop.

The start request can enable servos and move the arm. This consumes the boot;
it deliberately sends no export receipt or next-leg admission.
"""

import argparse
import json
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from preflight_r90_live_campaign import preflight
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.reviewed_hover_live_host import (
    R90_RELEASE_SHA, ReviewedHoverLiveHost,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", default="192.168.0.225")
    parser.add_argument("--authorized-first-leg", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    report = preflight(root, args.address)
    if not report["software_preflight_ready"]:
        raise ValueError("Current boot is not eligible for one-use live motion")
    if not args.authorized_first_leg:
        print(json.dumps(dict(status="R90_FIRST_LEG_PREFLIGHT_ONLY",
                              report=report, hardware_access=False)))
        return
    key = load_reviewed_key(root)
    client = CharacterizationHTTP(args.address, key=key,
        boot=report["boot_id"],
        reviewed_hover_live_release_sha256=R90_RELEASE_SHA)
    host = ReviewedHoverLiveHost(client, boot=report["boot_id"],
        export_root=root / "runs/wizard-exports",
        authorize_noncontact_motion=True, release_sha256=R90_RELEASE_SHA)
    result = host.run_first_leg_only()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
