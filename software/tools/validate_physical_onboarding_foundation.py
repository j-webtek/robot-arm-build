#!/usr/bin/env python3
"""Validate the physical-onboarding foundation without touching hardware.

This command is deliberately a thin, read-only wrapper around the aggregate
foundation loader.  The loader verifies the controlled source contracts; this
wrapper only renders a deterministic operator summary.  It does not discover,
open, configure, power, or command a camera, serial device, or robot arm.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence, Sized
import json
from pathlib import Path
import re
import sys
from typing import Protocol, cast


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE_ROOT = WORKSPACE / "software" / "src"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_VALIDATION_SCHEMA = "rocell.physical_onboarding_foundation_validation.v1"
_VALID_RESULT = "VALID_ZERO_AUTHORITY_FOUNDATION"


class _FoundationView(Protocol):
    """Stable fields exposed by the strict aggregate foundation loader."""

    foundation_id: str
    source_sha256: str
    runtime_activation: bool
    zero_physical_authority: bool
    contracts: Sized
    open_implementation_gates: Sequence[str]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the source-bound physical-onboarding foundation "
            "without acquiring hardware authority."
        )
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the canonical validation summary as JSON",
    )
    return parser


def _load_foundation(workspace: Path) -> _FoundationView:
    """Import lazily so the tool works without an editable installation."""

    if str(SOURCE_ROOT) not in sys.path:
        sys.path.insert(0, str(SOURCE_ROOT))
    from rocell.application.physical_onboarding_foundation import (  # pylint: disable=import-outside-toplevel
        load_physical_onboarding_foundation,
    )

    return cast(_FoundationView, load_physical_onboarding_foundation(workspace))


def _summary(foundation: _FoundationView) -> dict[str, object]:
    """Build a stable report and independently preserve zero authority."""

    if foundation.runtime_activation is not False:
        raise ValueError("foundation runtime_activation must remain false")
    if foundation.zero_physical_authority is not True:
        raise ValueError("foundation must retain zero physical authority")
    if not isinstance(foundation.foundation_id, str) or not foundation.foundation_id:
        raise ValueError("foundation_id must be non-empty text")
    if _SHA256.fullmatch(foundation.source_sha256) is None:
        raise ValueError("foundation source_sha256 must be lowercase SHA-256")

    gates = tuple(foundation.open_implementation_gates)
    if any(not isinstance(gate, str) or not gate for gate in gates):
        raise ValueError("open implementation gates must be non-empty text")

    return {
        "schema": _VALIDATION_SCHEMA,
        "result": _VALID_RESULT,
        "foundation_id": foundation.foundation_id,
        "foundation_sha256": foundation.source_sha256,
        "runtime_activation": False,
        "physical_authority": False,
        "physical_release_effect": "NONE",
        "hardware_access_attempted": False,
        "validated_contract_count": len(foundation.contracts),
        "open_implementation_gate_count": len(gates),
        "open_implementation_gates": list(gates),
    }


def _failure(exc: BaseException) -> dict[str, object]:
    return {
        "schema": _VALIDATION_SCHEMA,
        "result": "INVALID",
        "physical_authority": False,
        "physical_release_effect": "NONE",
        "hardware_access_attempted": False,
        "error": str(exc),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = _summary(_load_foundation(WORKSPACE))
    except (AttributeError, ImportError, OSError, TypeError, ValueError) as exc:
        if args.json:
            print(json.dumps(_failure(exc), indent=2, sort_keys=True))
        else:
            print(f"PHYSICAL_ONBOARDING_FOUNDATION_INVALID: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("PHYSICAL_ONBOARDING_FOUNDATION_VALID_ZERO_AUTHORITY")
        print(f"foundation: {report['foundation_id']}")
        print(f"source sha256: {report['foundation_sha256']}")
        print(f"validated contracts: {report['validated_contract_count']}")
        print(
            "runtime activation: false; physical authority: false; "
            f"open implementation gates: {report['open_implementation_gate_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
