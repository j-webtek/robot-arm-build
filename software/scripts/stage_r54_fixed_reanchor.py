"""Pin r53 and stage the r54 fixed re-anchor application offline; never upload."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R53_COMPILE = 'wizard-20260921T192555773211Z-73d0f9f74c9c4b5d8cb022e9370880d0'
OVERLAY = (
    'shoulder_preload_candidate.h',
    'characterization_board_services.h',
    'characterization_composition.h',
    'fixed_pair_reanchor_policy.h',
    'fixed_pair_reanchor_owner.h',
    'fixed_pair_reanchor_routes.h',
)


def stage(root):
    root = Path(root).resolve()
    report, receipt = _read(root / 'runs/wizard-exports', R53_COMPILE,
                            'attachment-compile-review.json')
    prefix = '.firmware-tools/configured-diagnostic-candidate-r53/RoArm-M3_example/'
    source = root / prefix
    files = {path.name: path.read_bytes() for path in source.iterdir() if path.is_file()}
    expected = {Path(path).name: digest for path, digest in report['source_hashes'].items()
                if path.replace('\\', '/').startswith(prefix)}
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    if (report['status'] != 'COMPILED' or
            report['target'] != 'configured-diagnostic-candidate-r53' or
            set(files) != set(expected) or
            any(sha(raw) != expected[name] for name, raw in files.items())):
        raise ValueError('Pinned r53 source differs')
    changed = {}
    for name in OVERLAY:
        old = files.get(name)
        new = (root / 'firmware/diagnostics' / name).read_bytes()
        files[name] = new
        changed[name] = {'before': sha(old) if old is not None else None, 'after': sha(new)}
    board = 'characterization_smoke_board.h'
    old = files[board]
    needle = b'rocell_diag::CharacterizationPattern::GhostPairTransitionCampaign));'
    if old.count(needle) != 1:
        raise ValueError('r53 board composition call changed')
    files[board] = old.replace(needle,
        b'rocell_diag::CharacterizationPattern::GhostPairTransitionCampaign,true));')
    changed[board] = {'before': sha(old), 'after': sha(files[board])}
    target = root / '.firmware-tools/configured-diagnostic-candidate-r54/RoArm-M3_example'
    target.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (target / name).open('xb') as stream:
            stream.write(raw)
        if (target / name).read_bytes() != raw:
            raise ValueError('Staged source readback differs')
    exporter = WizardDiagnosticExporter(root / 'runs/wizard-exports')
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r54-fixed-reanchor-stage'}, [], attachments={
        'r54-fixed-reanchor-stage.json': canonical(dict(
            revision=54, predecessor_revision=53, predecessor_compile_receipt=receipt,
            changed_files=changed, hardware_access=False, uploaded=False,
            settings_changed=False, deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Stage export invalid')
    return saved['path']


if __name__ == '__main__':
    print(stage(Path(__file__).resolve().parents[1]))
