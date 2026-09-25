"""Stage r57 fixed return from the verified r56 source, offline only."""

import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R56_COMPILE = 'wizard-20260921T234124765413Z-d90894e35c154a5e9f8a74e42941585c'
OVERLAY = (
    'characterization_board_services.h', 'characterization_composition.h',
    'park_reanchor_policy.h', 'park_reanchor_owner.h', 'park_reanchor_routes.h',
)
OLD_OPT_IN = b'CharacterizationPattern::GhostPairTransitionCampaign,false,true));'
NEW_OPT_IN = b'CharacterizationPattern::GhostPairTransitionCampaign,false,false,true));'


def stage(root):
    root = Path(root).resolve()
    report, receipt = _read(root / 'runs/wizard-exports', R56_COMPILE,
                            'attachment-compile-review.json')
    prefix = '.firmware-tools/configured-diagnostic-candidate-r56/RoArm-M3_example/'
    source = root / prefix
    files = {path.name: path.read_bytes() for path in source.iterdir() if path.is_file()}
    expected = {Path(path).name: digest for path, digest in report['source_hashes'].items()
                if path.replace('\\', '/').startswith(prefix)}
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    if (report['status'] != 'COMPILED' or
            report['target'] != 'configured-diagnostic-candidate-r56' or
            set(files) != set(expected) or
            any(sha(raw) != expected[name] for name, raw in files.items())):
        raise ValueError('Pinned r56 source differs')
    changed = {}
    for name in OVERLAY:
        new = (root / 'firmware/diagnostics' / name).read_bytes()
        old = files.get(name)
        if old == new:
            raise ValueError('No reviewed change for ' + name)
        files[name] = new
        changed[name] = {'before': sha(old) if old is not None else None,
                         'after': sha(new)}
    old = files['characterization_smoke_board.h']
    if old.count(OLD_OPT_IN) != 1 or NEW_OPT_IN in old:
        raise ValueError('Expected single r56 park-step opt-in')
    new = old.replace(OLD_OPT_IN, NEW_OPT_IN)
    files['characterization_smoke_board.h'] = new
    changed['characterization_smoke_board.h'] = {'before': sha(old), 'after': sha(new)}
    target = root / '.firmware-tools/configured-diagnostic-candidate-r57/RoArm-M3_example'
    target.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (target / name).open('xb') as stream:
            stream.write(raw)
        if (target / name).read_bytes() != raw:
            raise ValueError('Staged source readback differs')
    exporter = WizardDiagnosticExporter(root / 'runs/wizard-exports')
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r57-park-return-stage'}, [], attachments={
        'r57-park-return-stage.json': canonical({
            'revision': 57, 'predecessor_revision': 56,
            'predecessor_compile_receipt': receipt,
            'changed_files': changed, 'hardware_access': False,
            'uploaded': False, 'settings_changed': False, 'deployable': False,
            'fixed_target_goals': [2389, 1725],
            'park_step_route_enabled': False,
            'park_return_route_enabled': True,
        }),
    })
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Stage export invalid')
    return saved['path']


if __name__ == '__main__':
    print(stage(Path(__file__).resolve().parents[1]))
