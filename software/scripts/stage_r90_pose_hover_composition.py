"""Stage r90 with pose observation beside the sole reviewed-hover movement owner."""

import hashlib
import json
from pathlib import Path

if __package__:
    from .preflight_r89_live_campaign import COMPILE_EXPORT, local_install_review
else:
    from preflight_r89_live_campaign import COMPILE_EXPORT, local_install_review
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.reviewed_hover_manifest import ghost_key_manifest, validate_manifest
from rocell.application.reviewed_hover_release_identity import (
    derive_release_identity, render_release_stamp,
)
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


SOURCE = "configured-diagnostic-candidate-r89"
TARGET = "configured-diagnostic-candidate-r90"


def replace_one(raw: bytes, before: bytes, after: bytes) -> bytes:
    if raw.count(before) != 1:
        raise ValueError("Pinned r89 boot marker absent or ambiguous")
    return raw.replace(before, after)


def stage(root: Path) -> dict:
    root = Path(root).resolve()
    installed = local_install_review(root)
    exports = root / "runs/wizard-exports"
    compiled, _ = _read(exports, COMPILE_EXPORT, "attachment-compile-review.json")
    source = root / ".firmware-tools" / SOURCE / "RoArm-M3_example"
    destination = root / ".firmware-tools" / TARGET / "RoArm-M3_example"
    sha = lambda data: hashlib.sha256(data).hexdigest()
    files = {path.name: path.read_bytes() for path in source.iterdir() if path.is_file()}
    prefix = f".firmware-tools/{SOURCE}/RoArm-M3_example/"
    expected = {Path(name).name: digest for name, digest in compiled["source_hashes"].items()
                if name.replace("\\", "/").startswith(prefix)}
    if (compiled.get("status") != "COMPILED" or compiled.get("target") != SOURCE
            or set(files) != set(expected)
            or any(sha(data) != expected[name] for name, data in files.items())):
        raise ValueError("Pinned r89 source differs from compiled image")
    boot = files["diagnostic_boot.h"]
    boot = replace_one(boot,
        b"  registerShoulderSessionRoutes();\n  if(!rocellHoverApp)return;\n",
        b"  registerShoulderSessionRoutes();\n  if(!rocellHoverApp)return;\n"
        b"  registerPoseObservationRoutes();\n  if(!rocellPoseOwner||!rocellPoseRoutes)return;\n")
    boot = replace_one(boot,
        b"  if(rocellDiagnosticBootReady)pollShoulderSession();\n",
        b"  if(rocellDiagnosticBootReady){\n"
        b"    pollPoseObservation();\n    pollShoulderSession();\n  }\n")
    files["diagnostic_boot.h"] = boot
    if (b"if(rocellPoseReserved)" not in files["characterization_board_services.h"]
            and b"rocellPoseReserved||" not in files["characterization_board_services.h"]):
        raise ValueError("Reviewed-hover reservation does not exclude pose owner")
    if (b"if(rocellShoulderReserved)return false;" not in files["pose_observation_board.h"]
            or b"rocellPoseReserved=true;rocellDiagnosticOwned=true;" not in
            files["pose_observation_board.h"]):
        raise ValueError("Pose reservation does not exclude reviewed-hover owner")
    if b"SyncWritePosEx" in files["pose_observation_board.h"]:
        raise ValueError("Pose board unexpectedly defines a movement write")

    # The generated stamp is excluded from its own source-derived identity.
    source_hashes = {
        str(path.relative_to(root)).replace("\\", "/"): sha(path.read_bytes())
        for path in (root / "firmware/diagnostics").iterdir()
        if path.suffix in (".h", ".cpp", ".ino")
    }
    for name, raw in files.items():
        if name != "reviewed_hover_release_stamp.h":
            source_hashes[f".firmware-tools/{TARGET}/RoArm-M3_example/{name}"] = sha(raw)
    recipe = validate_manifest(ghost_key_manifest())["manifest_sha256"]
    lock = sha((root / "firmware/toolchain.lock.json").read_bytes())
    release = derive_release_identity(source_hashes=source_hashes,
        toolchain_lock_sha256=lock, recipe_sha256=recipe,
        build_profile="default-4mb-no-psram")
    files["reviewed_hover_release_stamp.h"] = render_release_stamp(release)
    if release == installed["release_sha256"]:
        raise ValueError("Changed image reused r89 release identity")

    destination.mkdir(parents=True, exist_ok=True)
    existing = {path.name: path.read_bytes() for path in destination.iterdir() if path.is_file()}
    if existing and existing != files:
        raise ValueError("Existing r90 stage differs; no overwrite")
    for name, raw in files.items():
        path = destination / name
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(raw)
        if path.read_bytes() != raw:
            raise ValueError("r90 staged source readback differs")
    report = dict(schema="rocell.r90_pose_hover_stage.v1", status="STAGED_OFFLINE",
                  predecessor_app_sha256=installed["app_sha256"],
                  predecessor_release_sha256=installed["release_sha256"],
                  release_sha256=release, recipe_sha256=recipe,
                  changed_files={name: dict(before=sha(data), after=sha(files[name]))
                                 for name, data in {path.name: path.read_bytes()
                                    for path in source.iterdir() if path.is_file()}.items()
                                 if files[name] != data},
                  route_owner="reviewed_hover_only",
                  extra_route="pose_observation_acquisition_only",
                  hardware_access=False, firmware_uploaded=False, deployable=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r90-pose-hover-stage"}, [],
                            attachments={"r90-pose-hover-stage.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Stage export failed")
    return dict(report=report, export=saved["path"])


if __name__ == "__main__":
    print(json.dumps(stage(Path(__file__).resolve().parents[1])))
