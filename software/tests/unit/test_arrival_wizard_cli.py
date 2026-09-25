"""Parser/launcher contracts only: never start a socket or access a device."""

from pathlib import Path

import pytest

from rocell.cli import build_parser


def test_wizard_defaults_to_rehearsal_without_automatic_browser_or_device_open():
    args = build_parser().parse_args(["physical-onboard", "wizard"])
    assert args.mode == "rehearsal"
    assert args.ui == "browser"
    assert args.port == 0
    assert args.cell_id == "CELL-A"
    assert args.export_dir is None
    assert args.open_browser is False
    assert args.check is False
    assert not hasattr(args, "camera")
    assert not hasattr(args, "execute")


def test_omitted_workspace_runs_real_headless_startup(monkeypatch,capsys):
    """Exercise the handler, not just the parser that previously hid None."""
    import json
    from rocell import cli
    from rocell.ui import server
    workspace = Path(__file__).resolve().parents[3]
    monkeypatch.chdir(workspace)
    monkeypatch.delenv('ROCELL_WORKSPACE',raising=False)
    def forbidden(*args,**kwargs):
        pytest.fail('Headless startup must not bind a server')
    monkeypatch.setattr(server,'create_wizard_server',forbidden)
    args = build_parser().parse_args(['physical-onboard','wizard','--check','--json'])
    assert args.workspace is None
    assert cli._command_arrival_wizard(args)==0
    view = json.loads(capsys.readouterr().out)
    assert view['physical_authority'] is False
    assert view['arm']['status']=='NOT_CONNECTED'
    endpoint = next(a for a in view['actions'] if a['action_id']=='run_endpoint_trial')
    assert endpoint['enabled'] is False


def test_explicit_export_assignment_and_headless_check():
    args = build_parser().parse_args(
        [
            "physical-onboard",
            "wizard",
            "--mode",
            "physical",
            "--ui",
            "terminal",
            "--export-dir",
            "C:/work/diagnostics",
            "--check",
            "--json",
        ]
    )
    assert args.export_dir == Path("C:/work/diagnostics")
    assert args.mode == "physical" and args.ui == "terminal"
    assert args.check and args.json


@pytest.mark.parametrize(
    "arguments",
    [
        ["--mode", "live"],
        ["--host", "0.0.0.0"],
        ["--port", "COM3"],
        ["--camera-index", "0"],
        ["--allow-hardware"],
        ["--auto-initialize"],
        ["--execute"],
        ["--ui", "public"],
    ],
)
def test_wizard_exposes_no_hardware_or_public_listener_override(arguments):
    with pytest.raises(SystemExit):
        build_parser().parse_args(["physical-onboard", "wizard", *arguments])


def test_new_launcher_keeps_legacy_startup_separate():
    root = Path(__file__).resolve().parents[3]
    script = (root / "start-rocell-wizard.ps1").read_text()
    legacy = (root / "start-rocell-onboarding.ps1").read_text()
    assert "[string] $Mode = 'rehearsal'" in script
    assert "'physical-onboard', 'wizard'" in script
    assert "'--check', '--json'" in script
    assert "'--open-browser'" in script
    assert "physical-onboard new" in legacy
    assert "physical-onboard wizard" not in legacy


def test_ui_static_assets_are_declared_for_packaging():
    root = Path(__file__).resolve().parents[3]
    project = (root / "software/pyproject.toml").read_text()
    assert '"rocell.ui" = ["static/*"]' in project


def test_local_launch_url_is_flushed_before_server_loop(monkeypatch):
    """A pipe-backed launcher must not hide the URL until the server exits."""
    from types import SimpleNamespace

    from rocell import cli
    from rocell.application import arrival_wizard_service
    from rocell.ui import server as server_module

    output = []
    lifecycle = []
    service = SimpleNamespace(
        view=lambda: {"exports": {"directory": "assigned-test-export"}},
        shutdown=lambda: lifecycle.append("shutdown"),
    )

    def serve_forever(**kwargs):
        assert kwargs == {"poll_interval": 0.25}
        assert output[-1][1].get("flush") is True
        assert any("Open locally: test-only-launch-url" in row[0] for row in output)
        lifecycle.append("serve")

    server = SimpleNamespace(
        launch_url="test-only-launch-url",
        serve_forever=serve_forever,
        close=lambda: lifecycle.append("close"),
    )
    monkeypatch.setattr(
        arrival_wizard_service, "ArrivalWizardService", lambda *a, **kw: service
    )
    monkeypatch.setattr(server_module, "create_wizard_server", lambda *a, **kw: server)
    monkeypatch.setattr(
        cli, "print", lambda value, **kw: output.append((value, kw)), raising=False
    )
    args = build_parser().parse_args(["physical-onboard", "wizard"])
    args.workspace = Path(__file__).resolve().parents[3]
    assert cli._command_arrival_wizard(args) == 0
    assert lifecycle == ["serve", "close"]
