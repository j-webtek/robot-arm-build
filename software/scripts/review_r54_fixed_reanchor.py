"""Offline exact r53-to-r54 source, build, slot and recovery review."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


COMPILE = 'wizard-20260921T212407586789Z-77c03cf66296433dad23aba1c4e72ff3'
STAGE = 'wizard-20260921T212212710482Z-d53d0e9a1dd44cc3b8f5adf0ef55ade3'
APP_SHA = 'c418af3062200c91e6cdf4c5540a7e251f09cdc36fccb9659a9b9a6181f818fe'
R53_SHA = '8d5ed3f0feb491e2294bb6f56bf27f82c53f616d257c61f493df58d94f050de5'
DIFF = {'shoulder_preload_candidate.h', 'characterization_board_services.h',
        'characterization_composition.h', 'fixed_pair_reanchor_policy.h',
        'fixed_pair_reanchor_owner.h', 'fixed_pair_reanchor_routes.h',
        'characterization_smoke_board.h'}


def review(root):
    root = Path(root).resolve()
    exports = root / 'runs/wizard-exports'
    compile_report, compile_digest = _read(exports, COMPILE, 'attachment-compile-review.json')
    stage_report, stage_digest = _read(exports, STAGE, 'attachment-r54-fixed-reanchor-stage.json')
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    target = 'configured-diagnostic-candidate-r54'
    if (compile_report['status'] != 'COMPILED' or compile_report['target'] != target or
            compile_report['build_profile'] != 'default-4mb-no-psram' or
            compile_report['hardware_access'] is not False or
            compile_report['firmware_uploaded'] is not False or
            stage_report['revision'] != 54 or stage_report['predecessor_revision'] != 53 or
            stage_report['hardware_access'] is not False or
            stage_report['uploaded'] is not False or
            set(stage_report['changed_files']) != DIFF):
        raise ValueError('Pinned offline stage or compile differs')
    old = root / '.firmware-tools/configured-diagnostic-candidate-r53/RoArm-M3_example'
    new = root / '.firmware-tools/configured-diagnostic-candidate-r54/RoArm-M3_example'
    old_files = {p.name: p.read_bytes() for p in old.iterdir() if p.is_file()}
    new_files = {p.name: p.read_bytes() for p in new.iterdir() if p.is_file()}
    if {name for name in new_files if old_files.get(name) != new_files[name]} != DIFF:
        raise ValueError('Unreviewed source change in r54')
    if set(old_files)-set(new_files):
        raise ValueError('r53 source file removed')
    prefix = '.firmware-tools/configured-diagnostic-candidate-r54/RoArm-M3_example/'
    source_hashes = {name.replace('\\', '/'): digest
                     for name, digest in compile_report['source_hashes'].items()}
    for name, raw in new_files.items():
        if source_hashes.get(prefix+name) != sha(raw):
            raise ValueError('Compiled source differs from staged source')
    for name, change in stage_report['changed_files'].items():
        if change != {'before': sha(old_files[name]) if name in old_files else None,
                      'after': sha(new_files[name])}:
            raise ValueError('Staging change hash mismatch')
    board = new_files['characterization_smoke_board.h']
    if b'CharacterizationPattern::GhostPairTransitionCampaign,true));' not in board:
        raise ValueError('Explicit r54 route enable missing')
    routes = new_files['fixed_pair_reanchor_routes.h']
    for identity in (b'/rocell/reanchor/start', b'/rocell/reanchor/status',
                     b'/rocell/reanchor/record', b'/rocell/reanchor/receipt'):
        if identity not in routes:
            raise ValueError('Fixed route missing')
    app_path = root / '.firmware-tools/build-configured-diagnostic-candidate-r54--default-4mb-no-psram/RoArm-M3_example.ino.bin'
    app = app_path.read_bytes()
    if (sha(app) != APP_SHA or compile_report['artifact_hashes']['RoArm-M3_example.ino.bin'] != APP_SHA
            or not 0 < len(app) <= 0x140000 or
            any(identity not in app for identity in (
                b'/rocell/reanchor/start', b'/rocell/reanchor/record',
                b'/rocell/reanchor/receipt', b'RCRANCH001'))):
        raise ValueError('Compiled r54 identity or app slot differs')
    r53 = (root / '.firmware-tools/build-configured-diagnostic-candidate-r53--default-4mb-no-psram/RoArm-M3_example.ino.bin').read_bytes()
    if sha(r53) != R53_SHA:
        raise ValueError('Predecessor image changed')
    private = root / 'private-backups/controller-20260918-session1'
    backup = (private / 'flash-pair-a.bin').read_bytes()
    if (len(backup) != 0x400000 or sha(backup) !=
            'd9e3de5cf3738b18144697095534ec9a33e531a6cd5062f68b85b5a29f6df2b9'
            or (private / 'flash-pair-b.bin').read_bytes() != backup or
            (private / 'original-app0-slot.bin').read_bytes() != backup[0x10000:0x150000]):
        raise ValueError('Recovery artifacts changed')
    for suffix, expected in (
        ('bootloader.bin', 'b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7'),
        ('partitions.bin', '148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1')):
        actual = compile_report['artifact_hashes']['RoArm-M3_example.ino.'+suffix]
        if actual != expected:
            raise ValueError('Boot or partition profile changed')
    report = dict(schema='rocell.r54_fixed_reanchor_review.v1', target=target,
                  app_sha256=APP_SHA, app_bytes=len(app), app_offset=0x10000,
                  app_slot_bytes=0x140000, app_headroom_bytes=0x140000-len(app),
                  predecessor_sha256=R53_SHA, compile_export_id=COMPILE,
                  compile_report_sha256=compile_digest, stage_export_id=STAGE,
                  stage_report_sha256=stage_digest, changed_files=sorted(DIFF),
                  recovery_artifacts_verified=True, settings_preserved_by_design=True,
                  runtime_heap_verified=False, device_bytes_verified=False,
                  hardware_access=False, firmware_uploaded=False,
                  deployment_authorized=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r54-offline-app-review'}, [], attachments={
        'r54-fixed-reanchor-review.json': canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Offline r54 review export failed')
    return saved['path'], report


if __name__ == '__main__':
    print(review(Path(__file__).resolve().parents[1])[0])
