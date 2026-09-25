"""r91 live host is exact-release, fresh-session and one-boot bound."""
from pathlib import Path

import pytest

from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.reviewed_hover_recovery_live_host import (
    R91_APP_SHA, R91_RELEASE_SHA, ReviewedHoverRecoveryLiveHost,
)
from rocell.application.wizard_diagnostic_export import (
    WizardDiagnosticExporter, verify_export,
)


BOOT = "ab" * 16
KEY = bytes(range(32))


def client(**kwargs):
    return CharacterizationHTTP("127.0.0.1", 1, key=KEY, boot=BOOT,
        recovery_hover_live_release_sha256=R91_RELEASE_SHA, **kwargs)


def test_live_host_construction_is_pinned_and_has_no_device_io(tmp_path):
    connection = client()
    host = ReviewedHoverRecoveryLiveHost(connection, boot=BOOT,
        export_root=tmp_path, authorize_noncontact_motion=True)
    assert host.app_sha256 == R91_APP_SHA
    assert host.release_sha256 == R91_RELEASE_SHA
    assert host.reviewed["leg_count"] == 5
    assert not list(tmp_path.iterdir())


def test_live_host_rejects_wrong_release_boot_or_session(tmp_path):
    for options in (dict(boot="cd" * 16), dict(app_sha256="34" * 32),
                    dict(release_sha256="34" * 32),
                    dict(authorize_noncontact_motion=False)):
        args = dict(boot=BOOT, export_root=tmp_path,
                    authorize_noncontact_motion=True)
        args.update(options)
        with pytest.raises(ValueError, match="Fresh exact"):
            ReviewedHoverRecoveryLiveHost(client(), **args)
    stale = client()
    stale.session._sequence = 1
    with pytest.raises(ValueError, match="Fresh exact"):
        ReviewedHoverRecoveryLiveHost(stale, boot=BOOT,
            export_root=tmp_path, authorize_noncontact_motion=True)


def test_intent_export_and_boot_reservation_are_durable(tmp_path):
    host = ReviewedHoverRecoveryLiveHost(client(), boot=BOOT,
        export_root=tmp_path, authorize_noncontact_motion=True)
    exporter = WizardDiagnosticExporter(tmp_path)
    exporter.prepare(create=True)
    host._reserve_before_start(exporter)
    marker = tmp_path / f"recovery-hover-live-{BOOT}.json"
    assert marker.is_file()
    exports = list(tmp_path.glob("wizard-*"))
    assert len(exports) == 1 and verify_export(Path(exports[0]))["valid"]
    with pytest.raises(ValueError, match="already claimed"):
        host._reserve_before_start(exporter)
