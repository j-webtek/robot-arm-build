"""Strictly ingest one returned external r97 review decision without hardware I/O."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from rocell.application.r97_independent_review_decision_v1 import (
    R97IndependentReviewDecisionError,
    assess_r97_independent_review_decision_v1,
    parse_r97_independent_review_decision_v1,
)


MAX_DECISION_BYTES = 128 * 1024


def _strict_json(data: bytes) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise R97IndependentReviewDecisionError(
                    f"decision contains duplicate field {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            data.decode("utf-8"), object_pairs_hook=pairs,
            parse_constant=lambda item: (_ for _ in ()).throw(
                R97IndependentReviewDecisionError(
                    f"decision contains {item}")),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise R97IndependentReviewDecisionError(
            "decision is not strict UTF-8 JSON") from exc
    if type(value) is not dict:
        raise R97IndependentReviewDecisionError(
            "decision root must be a JSON object")
    return value


def _utc(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise R97IndependentReviewDecisionError(
            "received_utc must be whole-second UTC") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _write(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")


def assess(decision_path: Path, output_dir: Path, *, received_utc: str) -> dict:
    decision_path = Path(decision_path)
    if decision_path.is_symlink():
        raise R97IndependentReviewDecisionError(
            "decision input must be one regular non-symlink file")
    decision_path = decision_path.resolve(strict=True)
    output_dir = Path(output_dir).resolve()
    if not decision_path.is_file():
        raise R97IndependentReviewDecisionError(
            "decision input must be one regular non-symlink file")
    if output_dir.exists():
        raise FileExistsError(
            "decision assessment output already exists; refusing to overwrite")
    received_utc = _utc(received_utc)
    data = decision_path.read_bytes()
    if not data or len(data) > MAX_DECISION_BYTES:
        raise R97IndependentReviewDecisionError(
            "decision input size is invalid")
    decision = parse_r97_independent_review_decision_v1(_strict_json(data))
    report = assess_r97_independent_review_decision_v1(decision)
    summary = {
        "schema": "rocell.r97_external_review_decision_intake.v1",
        "status": report.status,
        "input_document_sha256": hashlib.sha256(data).hexdigest(),
        "decision_sha256": decision.decision_sha256,
        "report_sha256": report.report_sha256,
        "received_utc": received_utc,
        "ready_for_configuration_epoch_intake": report.to_dict()[
            "ready_for_epoch_intake"],
        "installation_authorized": False,
        "controller_start_authorized": False,
        "transport_authorized": False,
        "execution_authorized": False,
        "hardware_access": False,
        "physical_authority": False,
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    _write(output_dir / "normalized-decision.json", decision.to_dict())
    _write(output_dir / "assessment-report.json", report.to_dict())
    _write(output_dir / "intake-summary.json", summary)
    return {**summary, "output_dir": str(output_dir)}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decision", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--received-utc", required=True)
    args = parser.parse_args()
    result = assess(args.decision, args.output_dir,
                    received_utc=args.received_utc)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ready_for_configuration_epoch_intake"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
