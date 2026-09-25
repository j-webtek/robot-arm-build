"""Read-only, receipt-bound r17 gain capture; no reset, recovery or servo writes."""
import argparse
import json
from pathlib import Path
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.held_pair_capabilities import read_pair_capabilities
from rocell.application.elbow_gain_capture import capture_gain


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only', action='store_true')
    mode.add_argument('--capture', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    binding = review_recovery_startup(root, args.startup_export, revision=17)
    if args.preflight_only:
        print(json.dumps(dict(status='LOCAL_R17_GAIN_PREFLIGHT_VERIFIED',
            expected_boot=binding['expected_boot'], hardware_access=False,
            motion_authorized=False, gain_changes_authorized=False)))
        return
    # Observe the boot before consuming the single fixed read-only acquisition.
    read_pair_capabilities(address=binding['address'], expected_boot=binding['expected_boot'])
    print(json.dumps(capture_gain(root/'runs/wizard-exports',
        address=binding['address'], expected_boot=binding['expected_boot'])))


if __name__ == '__main__':
    main()
