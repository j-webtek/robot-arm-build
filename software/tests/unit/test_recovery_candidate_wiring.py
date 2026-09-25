"""Check the generated include boundary that component-only tests cannot see."""
from pathlib import Path


def test_staged_recovery_http_includes_board_routes():
    root = Path(__file__).resolve().parents[2]
    sketch = root / '.firmware-tools/configured-diagnostic-candidate-r16/RoArm-M3_example'
    http = (sketch / 'diagnostic_http.h').read_text()
    assert http.count('void registerHoldDiagnosticRoutes()') == 1
    assert http.count('#include "configured_pair_board_routes.h"') == 1
    assert http.index('void registerHoldDiagnosticRoutes()') < http.index('#include "configured_pair_board_routes.h"')
    board = (sketch / 'configured_pair_board_routes.h').read_text()
    assert '#include "configured_recovery_board_routes.h"' in board
    assert 'rocellRecoveryRoutes.register_routes();' in board
    assert 'poll_hold_pair_recovery_diagnostics' in (sketch / 'diagnostic_boot.h').read_text()
    assert '#define ROCELL_RECOVERY_DIAGNOSTIC_OWNER 1' in (sketch / 'configured_native_owner.h').read_text()
    # Ordinary challenge creation is blocked before any settings access.
    assert http.index('if(rocellRecoveryReserved)return false;') < http.index('LittleFS.open')
