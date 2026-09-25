"""Run the exact four-leg r61 visible shoulder interval campaign once."""
import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_recovery_http import CharacterizationRecoveryHTTP
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.visible_interval_campaign import plan_visible_interval_campaign
from rocell.application.visible_interval_runner import VisibleIntervalRunner
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter


REVISION = 61
PLAN_EXPORT = "wizard-20260922T223155774570Z-3eabfb9d99bf4b4c8b7fe6ac7c57eafb"


def preflight(root, startup_export):
    binding = review_recovery_startup(root, startup_export, revision=REVISION)
    exports = root / "runs/wizard-exports"
    boot = binding["expected_boot"]
    claim = exports / f"r61-visible-interval-{boot}.json"
    conflicting_claims = (
        claim,
        exports / f"pose-observation-{boot}.json",
        exports / f"characterization-campaign-{boot}.json",
    )
    if any(path.exists() for path in conflicting_claims):
        raise ValueError("Boot already reserved for capture or movement")
    saved, _ = _read(
        exports, PLAN_EXPORT, "attachment-visible-interval-campaign-plan.json"
    )
    expected = plan_visible_interval_campaign()
    if saved != expected:
        raise ValueError("Frozen visible interval plan binding differs")
    binding["mapping_plan"] = expected
    return binding, exports, claim


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--startup-export", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument(
        "--authorized-visible-interval-clearance-confirmed", action="store_true"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    binding, exports, claim = preflight(root, args.startup_export)
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "status": "VISIBLE_INTERVAL_BINDING_VERIFIED",
                    "revision": REVISION,
                    "legs": 4,
                    "maximum_writes": 4,
                    "hardware_access": False,
                    "movement_authorized": False,
                }
            )
        )
        return

    key = load_reviewed_key(root)
    WizardDiagnosticExporter(exports).prepare(create=True)
    with claim.open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "boot": binding["expected_boot"],
                "startup_export": args.startup_export,
                "scope": "r61-visible-interval-campaign",
                "plan_sha256": binding["mapping_plan"]["plan_sha256"],
                "maximum_writes": 4,
                "retry_allowed": False,
                "automatic_return": False,
            },
            stream,
        )
        stream.flush()
        os.fsync(stream.fileno())
    client = CharacterizationHTTP(
        binding["address"], key=key, boot=binding["expected_boot"]
    )

    def recovery(campaign):
        return CharacterizationRecoveryHTTP(
            binding["address"],
            key=key,
            boot=binding["expected_boot"],
            campaign=campaign,
        )

    result = VisibleIntervalRunner(
        client,
        exports,
        key=key,
        boot=binding["expected_boot"],
        recovery_factory=recovery,
    ).run(motion_admitted=True)
    print(
        json.dumps(
            {
                "export_path": result["export_path"],
                "mapping_export": result.get("mapping_export"),
                "status": result["report"]["status"],
                "error": result["report"].get("error_message"),
            }
        )
    )
    if result["report"]["status"] != "COMPLETE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
