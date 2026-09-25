"""Offline exact r57-to-r58 app-only review; never accesses the controller."""

import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


COMPILE = 'wizard-20260922T194627054855Z-9bc643483a50464ea3b3e127600ae487'
STAGE = 'wizard-20260922T194423914331Z-623ded2b34774085a9b6d13895e12939'
R57_REVIEW = 'wizard-20260922T003202822812Z-8aa82ffd1c644837abfcc3d6609357a4'
APP_SHA = '944155ce47d2eeb60e6c7e7cb12d687a9250c6b3c030de49d39c9e923dc544f5'
R57_SHA = '7d8ac14ae59272368fbf3031ebc3ad5a5835e84913d85ee5758df46670767b68'


def review(root):
    root = Path(root).resolve()
    exports = root / 'runs/wizard-exports'
    compiled, compile_digest = _read(exports, COMPILE,
                                     'attachment-compile-review.json')
    staged, stage_digest = _read(exports, STAGE,
                                 'attachment-r58-visible-step-stage.json')
    predecessor, predecessor_digest = _read(exports, R57_REVIEW,
                                             'attachment-r57-park-return-review.json')
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    target = 'configured-diagnostic-candidate-r58'
    if (compiled['status'] != 'COMPILED' or compiled['target'] != target or
            compiled['build_profile'] != 'default-4mb-no-psram' or
            compiled['hardware_access'] is not False or
            compiled['firmware_uploaded'] is not False or
            staged['revision'] != 58 or staged['predecessor_revision'] != 57 or
            staged['hardware_access'] is not False or staged['uploaded'] is not False or
            staged['fixed_target_goals'] != [2413, 1701] or
            staged['expected_encoder_positions'] != [2415, 1700] or
            staged['maximum_excursion_counts'] != 28 or
            set(staged['changed_files']) != {'park_reanchor_policy.h'} or
            predecessor['app_sha256'] != R57_SHA):
        raise ValueError('Pinned stage, compile or predecessor differs')
    old = root / '.firmware-tools/configured-diagnostic-candidate-r57/RoArm-M3_example'
    new = root / '.firmware-tools/configured-diagnostic-candidate-r58/RoArm-M3_example'
    old_files = {p.name: p.read_bytes() for p in old.iterdir() if p.is_file()}
    new_files = {p.name: p.read_bytes() for p in new.iterdir() if p.is_file()}
    changed = {name for name in old_files if old_files[name] != new_files[name]}
    if set(old_files) != set(new_files) or changed != {'park_reanchor_policy.h'}:
        raise ValueError('Unreviewed source change')
    expected_policy = (root / 'firmware/diagnostics/park_reanchor_policy_r58.h').read_bytes()
    if new_files['park_reanchor_policy.h'] != expected_policy:
        raise ValueError('Reviewed r58 policy differs')
    prefix = '.firmware-tools/configured-diagnostic-candidate-r58/RoArm-M3_example/'
    source_hashes = {name.replace('\\', '/'): digest
                     for name, digest in compiled['source_hashes'].items()}
    for name, raw in new_files.items():
        if source_hashes.get(prefix + name) != sha(raw):
            raise ValueError('Compiled source changed')
    delta = staged['changed_files']['park_reanchor_policy.h']
    if delta != {'before': sha(old_files['park_reanchor_policy.h']),
                 'after': sha(expected_policy)}:
        raise ValueError('Staged policy hash changed')
    image = (root / '.firmware-tools/build-configured-diagnostic-candidate-r58--default-4mb-no-psram/'
             'RoArm-M3_example.ino.bin').read_bytes()
    if (sha(image) != APP_SHA or
            compiled['artifact_hashes']['RoArm-M3_example.ino.bin'] != APP_SHA or
            not 0 < len(image) <= 0x140000 or
            any(identity not in image for identity in (
                b'/rocell/park-return/start', b'/rocell/park-return/record',
                b'/rocell/park-return/receipt', b'RCRTN00001'))):
        raise ValueError('Compiled visible-step app identity or slot differs')
    old_image = (root / '.firmware-tools/build-configured-diagnostic-candidate-r57--default-4mb-no-psram/'
                 'RoArm-M3_example.ino.bin').read_bytes()
    if sha(old_image) != R57_SHA:
        raise ValueError('Predecessor image changed')
    for suffix, expected in (
            ('bootloader.bin', 'b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7'),
            ('partitions.bin', '148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1')):
        if compiled['artifact_hashes']['RoArm-M3_example.ino.' + suffix] != expected:
            raise ValueError('Boot or partition artifact changed')
    report = {
        'schema': 'rocell.r58_visible_shoulder_step_review.v1',
        'target': target, 'app_sha256': APP_SHA, 'app_bytes': len(image),
        'app_offset': 0x10000, 'app_slot_bytes': 0x140000,
        'app_headroom_bytes': 0x140000 - len(image),
        'predecessor_sha256': R57_SHA,
        'predecessor_review_id': R57_REVIEW,
        'predecessor_review_sha256': predecessor_digest,
        'compile_export_id': COMPILE, 'compile_report_sha256': compile_digest,
        'stage_export_id': STAGE, 'stage_report_sha256': stage_digest,
        'changed_files': ['park_reanchor_policy.h'],
        'fixed_target_goals': [2413, 1701],
        'settings_preserved_by_design': True,
        'runtime_heap_verified': False, 'device_bytes_verified': False,
        'hardware_access': False, 'firmware_uploaded': False,
        'deployment_authorized': False,
    }
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r58-offline-app-review'}, [], attachments={
        'r58-visible-step-review.json': canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Offline r58 review export invalid')
    return saved['path'], report


if __name__ == '__main__':
    print(review(Path(__file__).resolve().parents[1])[0])
