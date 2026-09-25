"""Verify the staged diagnostic adds no motion/startup/configuration changes."""
from pathlib import Path


def test_gain_candidate_only_changes_reviewed_boundary():
    root = Path(__file__).resolve().parents[2]
    tools = root / '.firmware-tools'
    before = tools / 'configured-diagnostic-candidate-r16/RoArm-M3_example'
    after = tools / 'configured-diagnostic-candidate-r17/RoArm-M3_example'
    old = {p.name: p.read_bytes() for p in before.iterdir()}
    new = {p.name: p.read_bytes() for p in after.iterdir()}
    assert set(new) - set(old) == {'elbow_gain_snapshot.h', 'elbow_gain_json.h', 'elbow_gain_routes.h'}
    assert set(old) - set(new) == set()
    assert {name for name in old if old[name] != new[name]} == {'configured_pair_board_routes.h'}
    board = new['configured_pair_board_routes.h'].decode()
    additions = [line for line in board.splitlines() if line not in old['configured_pair_board_routes.h'].decode().splitlines()]
    assert additions == [
        '#include "elbow_gain_routes.h"',
        '// Separate retained capture: never acquires at startup or while motion owns the bus.',
        'rocell_diag::ElbowGainRoutes<decltype(st),decltype(rocellConfiguredClock),WebServer>',
        '    rocellGainRoutes(st,rocellConfiguredClock,server,rocellDiagnosticInstance,rocellConfigurationBusInactive);',
        '  rocellGainRoutes.register_routes();',
    ]
    for name in set(new) - set(old):
        assert new[name] == (root / 'firmware/diagnostics' / name).read_bytes()


def test_read_only_gain_routes_do_not_expose_write_capability():
    root = Path(__file__).resolve().parents[2] / 'firmware/diagnostics'
    routes = (root / 'elbow_gain_routes.h').read_text()
    assert routes.count('web_.on(') == 2
    assert 'snapshot_.acquire' in routes
    assert '"/rocell/elbow-gain/capture",HTTP_POST' in routes
    assert '"/rocell/elbow-gain/result",HTTP_GET' in routes
    # Native tests compile against a bus with Read only; no Write/Torque API.
    test = (root / 'test_elbow_gain_snapshot.cpp').read_text()
    assert 'struct ReadOnlyBus' in test
