"""Offline exact r56-to-r57 app-only review; never accesses the controller."""

import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


COMPILE = 'wizard-20260922T003055181870Z-087edefca56649f3a79cc1b33ea83d05'
STAGE = 'wizard-20260922T002841249867Z-803adda070224eb3ab82ac9493ab4998'
R56_REVIEW = 'wizard-20260921T234210592410Z-e54a5c2690a746fd9b7459456cf6f6d0'
APP_SHA = '7d8ac14ae59272368fbf3031ebc3ad5a5835e84913d85ee5758df46670767b68'
R56_SHA = '09864d144d630b2655c78956b0ea8148b0525bcdef017caa843d74f1f4661e79'
CHANGED = {
    'characterization_board_services.h', 'characterization_composition.h',
    'characterization_smoke_board.h', 'park_reanchor_policy.h',
    'park_reanchor_owner.h', 'park_reanchor_routes.h',
}
ADDED = {'park_reanchor_policy.h', 'park_reanchor_owner.h',
         'park_reanchor_routes.h'}


def review(root):
    root = Path(root).resolve()
    exports = root / 'runs/wizard-exports'
    compiled, compile_digest = _read(exports, COMPILE, 'attachment-compile-review.json')
    staged, stage_digest = _read(exports, STAGE, 'attachment-r57-park-return-stage.json')
    predecessor, predecessor_digest = _read(exports, R56_REVIEW,
                                            'attachment-r56-park-step-review.json')
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    target = 'configured-diagnostic-candidate-r57'
    if (compiled['status'] != 'COMPILED' or compiled['target'] != target or
            compiled['build_profile'] != 'default-4mb-no-psram' or
            compiled['hardware_access'] is not False or
            compiled['firmware_uploaded'] is not False or
            staged['revision'] != 57 or staged['predecessor_revision'] != 56 or
            staged['hardware_access'] is not False or staged['uploaded'] is not False or
            staged['park_step_route_enabled'] is not False or
            staged['park_return_route_enabled'] is not True or
            staged['fixed_target_goals'] != [2389, 1725] or
            set(staged['changed_files']) != CHANGED or
            predecessor['app_sha256'] != R56_SHA):
        raise ValueError('Pinned stage, compile or predecessor differs')
    old = root / '.firmware-tools/configured-diagnostic-candidate-r56/RoArm-M3_example'
    new = root / '.firmware-tools/configured-diagnostic-candidate-r57/RoArm-M3_example'
    old_files = {path.name: path.read_bytes() for path in old.iterdir() if path.is_file()}
    new_files = {path.name: path.read_bytes() for path in new.iterdir() if path.is_file()}
    if (set(new_files) - set(old_files) != ADDED or
            set(old_files) - set(new_files) or
            {name for name in old_files if old_files[name] != new_files[name]} !=
            CHANGED - ADDED):
        raise ValueError('Unreviewed source change')
    prefix = '.firmware-tools/configured-diagnostic-candidate-r57/RoArm-M3_example/'
    source_hashes = {name.replace('\\', '/'): digest
                     for name, digest in compiled['source_hashes'].items()}
    for name, raw in new_files.items():
        if source_hashes.get(prefix + name) != sha(raw):
            raise ValueError('Compiled source changed')
    for name, delta in staged['changed_files'].items():
        previous = old_files.get(name)
        if delta != {'before': sha(previous) if previous is not None else None,
                     'after': sha(new_files[name])}:
            raise ValueError('Staged file hash changed')
    smoke = new_files['characterization_smoke_board.h']
    if (smoke.count(b'CharacterizationPattern::GhostPairTransitionCampaign,false,false,true));') != 1 or
            b'CharacterizationPattern::GhostPairTransitionCampaign,false,true));' in smoke):
        raise ValueError('Return-only route opt-in differs')
    image = (root / '.firmware-tools/build-configured-diagnostic-candidate-r57--default-4mb-no-psram/'
             'RoArm-M3_example.ino.bin').read_bytes()
    if (sha(image) != APP_SHA or
            compiled['artifact_hashes']['RoArm-M3_example.ino.bin'] != APP_SHA or
            not 0 < len(image) <= 0x140000 or
            any(identity not in image for identity in (
                b'/rocell/park-return/start', b'/rocell/park-return/record',
                b'/rocell/park-return/receipt', b'RCRTN00001'))):
        raise ValueError('Compiled return app identity or slot differs')
    old_image = (root / '.firmware-tools/build-configured-diagnostic-candidate-r56--default-4mb-no-psram/'
                 'RoArm-M3_example.ino.bin').read_bytes()
    if sha(old_image) != R56_SHA:
        raise ValueError('Predecessor image changed')
    for suffix, expected in (
            ('bootloader.bin', 'b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7'),
            ('partitions.bin', '148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1')):
        if compiled['artifact_hashes']['RoArm-M3_example.ino.' + suffix] != expected:
            raise ValueError('Boot or partition artifact changed')
    report = {
        'schema': 'rocell.r57_park_return_review.v1', 'target': target,
        'app_sha256': APP_SHA, 'app_bytes': len(image), 'app_offset': 0x10000,
        'app_slot_bytes': 0x140000, 'app_headroom_bytes': 0x140000-len(image),
        'predecessor_sha256': R56_SHA, 'predecessor_review_id': R56_REVIEW,
        'predecessor_review_sha256': predecessor_digest,
        'compile_export_id': COMPILE, 'compile_report_sha256': compile_digest,
        'stage_export_id': STAGE, 'stage_report_sha256': stage_digest,
        'changed_files': sorted(CHANGED), 'settings_preserved_by_design': True,
        'runtime_heap_verified': False, 'device_bytes_verified': False,
        'hardware_access': False, 'firmware_uploaded': False,
        'deployment_authorized': False,
    }
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r57-offline-app-review'}, [], attachments={
        'r57-park-return-review.json': canonical(report),
    })
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Offline return review export invalid')
    return saved['path'], report


if __name__ == '__main__':
    print(review(Path(__file__).resolve().parents[1])[0])
