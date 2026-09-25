"""Offline exact r58-to-r60 review; r59 remains a retained failed build."""

import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


COMPILE = 'wizard-20260922T203120491645Z-474a80e233d44303a95718d8188c0f2c'
STAGE = 'wizard-20260922T202919030806Z-b486fb383fa64b7cbcdf332df9bc6c9b'
R58_REVIEW = 'wizard-20260922T194754620618Z-50534b00d3c94ccaa7e9f83706caeae5'
FAILED_R59_COMPILE = 'wizard-20260922T202808438722Z-86271b878fd84537b1bf5eb339bf3f0c'
APP_SHA = '6f98f372b5a927b016ae81f0673df1ee8ddd0f0b78bc714d181746e575df7211'
R58_SHA = '944155ce47d2eeb60e6c7e7cb12d687a9250c6b3c030de49d39c9e923dc544f5'


def review(root):
    root = Path(root).resolve(); exports = root / 'runs/wizard-exports'
    compiled, compile_digest = _read(exports, COMPILE, 'attachment-compile-review.json')
    staged, stage_digest = _read(exports, STAGE,
                                 'attachment-r60-policy-bound-adapter-stage.json')
    predecessor, predecessor_digest = _read(exports, R58_REVIEW,
                                             'attachment-r58-visible-step-review.json')
    failed, failed_digest = _read(exports, FAILED_R59_COMPILE,
                                  'attachment-compile-review.json')
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    target = 'configured-diagnostic-candidate-r60'
    if (compiled['status'] != 'COMPILED' or compiled['target'] != target or
            compiled['build_profile'] != 'default-4mb-no-psram' or
            staged['revision'] != 60 or staged['predecessor_revision'] != 58 or
            staged['fixed_target_goals'] != [2413, 1701] or
            staged['adapter_uses_policy_constants'] is not True or
            staged['compile_order_fix'] != 'EXPLICIT_POLICY_INCLUDE' or
            set(staged['changed_files']) != {'characterization_board_services.h'} or
            predecessor['app_sha256'] != R58_SHA or
            failed['status'] != 'FAILED' or failed['artifact_hashes']):
        raise ValueError('Pinned r60 evidence differs')
    old = root / '.firmware-tools/configured-diagnostic-candidate-r58/RoArm-M3_example'
    new = root / '.firmware-tools/configured-diagnostic-candidate-r60/RoArm-M3_example'
    old_files = {p.name: p.read_bytes() for p in old.iterdir() if p.is_file()}
    new_files = {p.name: p.read_bytes() for p in new.iterdir() if p.is_file()}
    if (set(old_files) != set(new_files) or
            {name for name in old_files if old_files[name] != new_files[name]} !=
            {'characterization_board_services.h'}):
        raise ValueError('Unreviewed source change')
    service = new_files['characterization_board_services.h']
    section = service.split(b'bool park_return_write', 1)[1].split(
        b'bool park_return_evidence', 1)[0]
    if (b'#include "park_reanchor_policy.h"' not in service or
            b'ParkReanchorPolicy::target12' not in section or
            b'ParkReanchorPolicy::target13' not in section or
            b'a!=2389||b!=1725' in section):
        raise ValueError('Policy-bound service differs')
    prefix = '.firmware-tools/configured-diagnostic-candidate-r60/RoArm-M3_example/'
    sources = {name.replace('\\', '/'): digest
               for name, digest in compiled['source_hashes'].items()}
    for name, raw in new_files.items():
        if sources.get(prefix + name) != sha(raw):
            raise ValueError('Compiled source changed')
    delta = staged['changed_files']['characterization_board_services.h']
    if delta != {'before': sha(old_files['characterization_board_services.h']),
                 'after': sha(service)}:
        raise ValueError('Staged service hash changed')
    image = (root / '.firmware-tools/build-configured-diagnostic-candidate-r60--default-4mb-no-psram/'
             'RoArm-M3_example.ino.bin').read_bytes()
    if (sha(image) != APP_SHA or
            compiled['artifact_hashes']['RoArm-M3_example.ino.bin'] != APP_SHA or
            not 0 < len(image) <= 0x140000 or
            any(identity not in image for identity in (
                b'/rocell/park-return/start', b'/rocell/park-return/record',
                b'/rocell/park-return/receipt', b'RCRTN00001'))):
        raise ValueError('Compiled r60 app differs')
    old_image = (root / '.firmware-tools/build-configured-diagnostic-candidate-r58--default-4mb-no-psram/'
                 'RoArm-M3_example.ino.bin').read_bytes()
    if sha(old_image) != R58_SHA:
        raise ValueError('Predecessor app differs')
    for suffix, expected in (
            ('bootloader.bin', 'b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7'),
            ('partitions.bin', '148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1')):
        if compiled['artifact_hashes']['RoArm-M3_example.ino.' + suffix] != expected:
            raise ValueError('Boot or partition artifact changed')
    report = {
        'schema': 'rocell.r60_policy_bound_adapter_review.v1',
        'target': target, 'app_sha256': APP_SHA, 'app_bytes': len(image),
        'app_offset': 0x10000, 'app_slot_bytes': 0x140000,
        'app_headroom_bytes': 0x140000-len(image),
        'predecessor_sha256': R58_SHA,
        'predecessor_review_id': R58_REVIEW,
        'predecessor_review_sha256': predecessor_digest,
        'compile_export_id': COMPILE, 'compile_report_sha256': compile_digest,
        'stage_export_id': STAGE, 'stage_report_sha256': stage_digest,
        'failed_r59_compile_export_id': FAILED_R59_COMPILE,
        'failed_r59_compile_sha256': failed_digest,
        'changed_files': ['characterization_board_services.h'],
        'fixed_target_goals': [2413, 1701],
        'r58_fault_prebus_rejection_resolved': True,
        'settings_preserved_by_design': True,
        'runtime_heap_verified': False, 'device_bytes_verified': False,
        'hardware_access': False, 'firmware_uploaded': False,
        'deployment_authorized': False,
    }
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r60-offline-app-review'}, [], attachments={
        'r60-policy-bound-adapter-review.json': canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Offline r60 review export invalid')
    return saved['path'], report


if __name__ == '__main__':
    print(review(Path(__file__).resolve().parents[1])[0])
