"""Offline builder wiring checks; never stage, provision or access a device."""
import importlib.util
from pathlib import Path


def test_pair_candidate_composition():
    root=Path(__file__).resolve().parents[2]
    spec=importlib.util.spec_from_file_location('pair_builder',root/'scripts/prepare_owner_firmware_candidate.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    folder=root/'firmware/diagnostics'
    outputs={name:(folder/source).read_bytes() for name,source in (
        ('configured_native_owner.h','configured_hold_owner.h'),
        ('diagnostic_http.h','configured_hold_routes.h'),
        ('diagnostic_boot.h','diagnostic_boot.h'))}
    original=dict(outputs)
    module.integrate_pair_mode(outputs)
    owner=outputs['configured_native_owner.h'].decode()
    routes=outputs['diagnostic_http.h'].decode()
    boot=outputs['diagnostic_boot.h'].decode()
    assert '#include "configured_pair_board.h"' in owner
    assert 'rocellPairRuntime.interference()' in owner
    assert 'void registerHoldDiagnosticRoutes()' in routes
    assert '#include "configured_pair_board_routes.h"' in routes
    assert 'poll_hold_pair_diagnostics(rocellConfiguredRuntime,rocellPairRuntime,server)' in boot
    assert 'initHttpWebServer' not in boot and 'jsonCmdReceiveHandler' not in boot
    assert 'LittleFS.begin(false)' in boot
    assert original['configured_native_owner.h']==(folder/'configured_hold_owner.h').read_bytes()
