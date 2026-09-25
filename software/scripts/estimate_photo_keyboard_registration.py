"""Offline photo-annotated keyboard placement estimate; no hardware I/O."""
import argparse
import hashlib
import json
from pathlib import Path

from rocell.application.photo_keyboard_registration import estimate, estimate_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo", type=Path,
                        help="Optional original 10-Photo-10.jpg for SHA-256 verification")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    annotation_path = root / "config/photo_keyboard_registration_20260925.json"
    profile_path = root / "config/static_nominal_target_profiles.json"
    if args.photo is not None:
        result = estimate_files(annotation_path, profile_path, args.photo)
    else:
        profile_bytes = profile_path.read_bytes()
        result = estimate(json.loads(annotation_path.read_text(encoding="utf-8")),
                          json.loads(profile_bytes)["keyboard"],
                          profile_sha256=hashlib.sha256(profile_bytes).hexdigest())
    print(json.dumps(result, indent=2))
