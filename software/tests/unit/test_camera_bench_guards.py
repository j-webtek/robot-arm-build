"""Offline rejection checks: these tests must never enumerate/open any hardware."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


@pytest.fixture
def bench(monkeypatch, tmp_path):
    source = Path(__file__).resolve().parents[2] / "scripts/camera_bench_check.py"
    spec = importlib.util.spec_from_file_location("camera_bench_under_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    exports = tmp_path / "exports"
    exports.mkdir()
    monkeypatch.setattr(module, "EXPORTS", exports)

    def forbidden(*args, **kwargs):
        raise AssertionError("Offline rejection tests must never start a process")

    monkeypatch.setattr(module.subprocess, "Popen", forbidden)
    # Missing dependencies also stop a valid invocation before creating a run.
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    return module


def arguments(bench):
    return [
        "camera_bench_check.py",
        "--device-alias",
        r"@device_pnp_\\?\usb#vid_04b4&pid_0477&mi_00#offline-test",
        "--output-directory",
        str(bench.EXPORTS / "new-run"),
        "--confirm-camera-only-tests",
    ]


def reject(bench, monkeypatch, capsys, argv, reason):
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as error:
        bench.main()
    assert error.value.code == 2
    assert reason in capsys.readouterr().err
    assert not (bench.EXPORTS / "new-run").exists()


def test_explicit_confirmation_required(bench, monkeypatch, capsys):
    reject(bench, monkeypatch, capsys, arguments(bench)[:-1], "confirmation required")


@pytest.mark.parametrize(
    "alias", ["0", "video=other-camera", "@device_pnp_wrong", '"', "\n"]
)
def test_wrong_device_selector_rejected(bench, monkeypatch, capsys, alias):
    argv = arguments(bench)
    argv[2] = alias
    reject(bench, monkeypatch, capsys, argv, "exact observed B0477")


@pytest.mark.parametrize("duration", ["0", "4", "61"])
def test_duration_is_bounded(bench, monkeypatch, capsys, duration):
    argv = arguments(bench) + ["--full-resolution-seconds", duration]
    reject(bench, monkeypatch, capsys, argv, "between 5 and 60")


@pytest.mark.parametrize('duration',['-1','6'])
def test_sample_warmup_is_bounded(bench,monkeypatch,capsys,duration):
    argv=arguments(bench)+['--sample-warmup-seconds',duration]
    reject(bench,monkeypatch,capsys,argv,'between 0 and 5')


@pytest.mark.parametrize("target", ["outside", "nested", "existing"])
def test_output_must_be_new_workspace_child(bench, monkeypatch, capsys, target):
    argv = arguments(bench)
    folder = {
        "outside": bench.EXPORTS.parent / "outside",
        "nested": bench.EXPORTS / "parent" / "nested",
        "existing": bench.EXPORTS,
    }[target]
    argv[4] = str(folder)
    reject(bench, monkeypatch, capsys, argv, "new direct child")
    assert not list(bench.EXPORTS.iterdir())


def test_missing_tools_do_not_install_or_open_device(bench, monkeypatch, capsys):
    reject(bench, monkeypatch, capsys, arguments(bench), "nothing is installed")


def test_existing_observation_is_not_overwritten(bench, tmp_path):
    original = tmp_path / "original.json"
    original.write_text('{"retained": true}', encoding="utf-8")
    with pytest.raises(FileExistsError):
        bench.write_json(original, {"replacement": True})
    assert original.read_text(encoding="utf-8") == '{"retained": true}'


@pytest.mark.parametrize('level,status', [(0,'NEAR_BLACK'), (8,'NEAR_BLACK'),
    (9,'SCENE_REVIEW_REQUIRED'), (128,'SCENE_REVIEW_REQUIRED'),
    (246,'SCENE_REVIEW_REQUIRED'), (247,'NEAR_WHITE'), (255,'NEAR_WHITE')])
def test_visibility_is_not_transport_or_calibration(bench,tmp_path,level,status):
    from PIL import Image
    path=tmp_path/'sample.png'
    Image.new('RGB',(100,100),(level,level,level)).save(path)
    report=bench.assess_sample_visibility(path)
    assert report['status']==status
    assert report['mean_luma_8bit']==level
    assert not report['arm_visible_verified']
    assert not report['calibration_verified'] and not report['physical_authority']


def test_hot_pixel_does_not_disguise_black_frame(bench,tmp_path):
    from PIL import Image
    image=Image.new('L',(100,100),0)
    image.putpixel((50,50),255)
    path=tmp_path/'sample.png'
    image.save(path)
    report=bench.assess_sample_visibility(path)
    assert report['status']=='NEAR_BLACK'
    assert report['fraction_luma_le_8']==.9999


def test_invalid_image_is_not_qualified(bench,tmp_path):
    path=tmp_path/'bad.png'
    path.write_bytes(b'not an image')
    with pytest.raises(OSError):
        bench.assess_sample_visibility(path)
