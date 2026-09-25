"""Stage a separate r91 recovery image from pinned r90 sources; no device I/O."""
import hashlib
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.reviewed_hover_recovery_admission import (
    recovery_manifest, validate_recovery_manifest,
)
from rocell.application.reviewed_hover_release_identity import (
    derive_release_identity, render_release_stamp,
)
from rocell.application.wizard_diagnostic_export import (
    WizardDiagnosticExporter, verify_export,
)


SOURCE = "configured-diagnostic-candidate-r90"
TARGET = "configured-diagnostic-candidate-r91"
R90_COMPILE = "wizard-20260925T115330774418Z-399cdfe58f7441d3af02d1584ceddfe1"
R90_APP_SHA = "f3d5705b16eedfd49b11fec668da1709eee71d50345ceb07eadf26f0384fe129"
R90_RELEASE_SHA = "65f0106f05de4e8edf68fbd7729a807ebab179c4b86b9e5e37bba5dca9d7a538"
OVERLAYS = {
    "reviewed_hover_board.h": "reviewed_hover_recovery_board.h",
    "reviewed_hover_owner.h": "reviewed_hover_owner.h",
    "reviewed_hover_routes.h": "reviewed_hover_routes.h",
    "reviewed_hover_composition.h": "reviewed_hover_composition.h",
    "reviewed_hover_recovery_board_adapter.h": "reviewed_hover_recovery_board_adapter.h",
    "reviewed_hover_recovery_admission.h": "reviewed_hover_recovery_admission.h",
    "reviewed_hover_recovery_policy.h": "reviewed_hover_recovery_policy.h",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def staged_files(root: Path) -> tuple[dict[str, bytes], dict]:
    root = Path(root).resolve()
    source = root / ".firmware-tools" / SOURCE / "RoArm-M3_example"
    compiled, _ = _read(root / "runs/wizard-exports", R90_COMPILE,
                        "attachment-compile-review.json")
    original = {path.name: path.read_bytes() for path in source.iterdir()
                if path.is_file()}
    prefix = f".firmware-tools/{SOURCE}/RoArm-M3_example/"
    expected = {Path(name).name: digest for name, digest in
                compiled["source_hashes"].items()
                if name.replace("\\", "/").startswith(prefix)}
    app = (root / f".firmware-tools/build-{SOURCE}--default-4mb-no-psram"
           / "RoArm-M3_example.ino.bin").read_bytes()
    if (compiled.get("status") != "COMPILED" or compiled.get("target") != SOURCE
            or compiled.get("build_profile") != "default-4mb-no-psram"
            or set(original) != set(expected)
            or any(sha(data) != expected[name] for name, data in original.items())
            or sha(app) != R90_APP_SHA
            or compiled.get("artifact_hashes", {}).get("RoArm-M3_example.ino.bin") != R90_APP_SHA
            or original.get("reviewed_hover_release_stamp.h") !=
            render_release_stamp(R90_RELEASE_SHA)):
        raise ValueError("Pinned r90 source, app, or release differs")
    files = dict(original)
    for destination, candidate in OVERLAYS.items():
        files[destination] = (root / "firmware/diagnostics" / candidate).read_bytes()
    if (b"ReviewedHoverComposition<rocell_diag::Esp32StartCrypto,"
            not in files["reviewed_hover_board.h"] or
            b"WebServer,false,true>" not in files["reviewed_hover_board.h"] or
            b"ReviewedHoverRecoveryBoardAdapter" not in files["reviewed_hover_board.h"] or
            b"/rocell/recovery-hover/capabilities" not in files["reviewed_hover_board.h"] or
            b"/rocell/reviewed-hover/capabilities" in files["reviewed_hover_board.h"] or
            b"registerPoseObservationRoutes();" not in files["diagnostic_boot.h"] or
            b"SyncWritePosEx" in files["pose_observation_board.h"]):
        raise ValueError("Recovery owner or acquisition-only composition differs")
    recipe = validate_recovery_manifest(recovery_manifest())
    source_hashes = {
        str(path.relative_to(root)).replace("\\", "/"): sha(path.read_bytes())
        for path in (root / "firmware/diagnostics").iterdir()
        if path.suffix in (".h", ".cpp", ".ino")
    }
    for name, data in files.items():
        if name != "reviewed_hover_release_stamp.h":
            source_hashes[f".firmware-tools/{TARGET}/RoArm-M3_example/{name}"] = sha(data)
    lock = sha((root / "firmware/toolchain.lock.json").read_bytes())
    release = derive_release_identity(source_hashes=source_hashes,
        toolchain_lock_sha256=lock, recipe_sha256=recipe,
        build_profile="default-4mb-no-psram")
    if release == R90_RELEASE_SHA:
        raise ValueError("Recovery reused predecessor release identity")
    files["reviewed_hover_release_stamp.h"] = render_release_stamp(release)
    report = dict(schema="rocell.r91_hover_recovery_stage.v1",
                  status="STAGED_OFFLINE", predecessor_app_sha256=R90_APP_SHA,
                  predecessor_release_sha256=R90_RELEASE_SHA,
                  release_sha256=release, recipe_sha256=recipe,
                  source_hashes=source_hashes, toolchain_lock_sha256=lock,
                  changed_files={name: dict(before=sha(original[name]), after=sha(data))
                                 for name, data in files.items()
                                 if name in original and data != original[name]},
                  added_files={name: sha(data) for name, data in files.items()
                               if name not in original},
                  route_owner="recovery_hover_only",
                  extra_route="pose_observation_acquisition_only",
                  hardware_access=False, firmware_uploaded=False,
                  deployable=False)
    return files, report


def stage(root: Path) -> dict:
    root = Path(root).resolve()
    files, report = staged_files(root)
    destination = root / ".firmware-tools" / TARGET / "RoArm-M3_example"
    existing = {path.name: path.read_bytes() for path in destination.iterdir()
                if path.is_file()} if destination.exists() else {}
    if existing and existing != files:
        raise ValueError("Existing r91 stage differs; no overwrite")
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        path = destination / name
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(data)
        if path.read_bytes() != data:
            raise ValueError("r91 staged source readback differs")
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r91-hover-recovery-stage"}, [],
        attachments={"r91-hover-recovery-stage.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r91 stage export failed")
    return dict(report=report, export=saved["path"])


if __name__ == "__main__":
    print(json.dumps(stage(Path(__file__).resolve().parents[1])))
