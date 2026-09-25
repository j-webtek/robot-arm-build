"""Source-level integration guards, supplemental to real ESP32 compilation."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def test_staged_smoke_registration_follows_boot_identity():
    staged=ROOT/'.firmware-tools/configured-diagnostic-candidate-r33/RoArm-M3_example'
    routes=(staged/'configured_pair_board_routes.h').read_text()
    registration=routes.split('void registerDiagnosticRoutes(){',1)[1]
    assert registration.index('registerHoldDiagnosticRoutes();') < registration.index('registerShoulderSessionRoutes();')
    assert '#define ROCELL_CHARACTERIZATION_SMOKE 1' in (staged/'shoulder_board_session.h').read_text()
    board=(staged/'characterization_smoke_board.h').read_text()
    assert 'CharacterizationPattern::Smoke' in board
    assert board == (ROOT/'firmware/diagnostics/characterization_smoke_board.h').read_text()


def test_staging_preserves_nonmoving_boot_source():
    tools=ROOT/'.firmware-tools'
    relative='RoArm-M3_example/diagnostic_boot.h'
    assert (tools/'configured-diagnostic-candidate-r33'/relative).read_bytes() == (
        tools/'configured-diagnostic-candidate-r31'/relative).read_bytes()


def test_r34_changes_only_reference_export_headers():
    tools=ROOT/'.firmware-tools'
    previous=tools/'configured-diagnostic-candidate-r33/RoArm-M3_example'
    current=tools/'configured-diagnostic-candidate-r34/RoArm-M3_example'
    before={p.name:p.read_bytes() for p in previous.iterdir() if p.is_file()}
    after={p.name:p.read_bytes() for p in current.iterdir() if p.is_file()}
    assert set(before)==set(after)
    assert {name for name in before if before[name]!=after[name]}=={
        'characterization_prepare.h','characterization_controller.h','characterization_prepare_routes.h'}
    assert b'/rocell/characterization/reference' in after['characterization_prepare_routes.h']
