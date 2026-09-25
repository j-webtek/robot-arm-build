"""Actual regular-file intake choices; no camera, serial or native process."""

import os
from pathlib import Path
from threading import Event
from time import monotonic_ns

import pytest

from rocell.application import physical_intake_inbox as module
from rocell.application.wizard_actions import WizardError

SOURCE = "a" * 64
LAUNCH = "wizard-" + "1" * 32


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    (tmp_path / "software/runs").mkdir(parents=True)
    monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    return module.PhysicalIntakeInbox(tmp_path, launch_id=LAUNCH, source_sha256=SOURCE)


def discover(inbox, **kwargs):
    return inbox.discover(
        cancellation=kwargs.get("cancellation", Event()),
        deadline_ns=kwargs.get("deadline_ns", monotonic_ns() + 20_000_000_000),
    )


def selected(inbox, choices, **kwargs):
    return inbox.selected_files(
        tuple(choices),
        cancellation=kwargs.get("cancellation", Event()),
        deadline_ns=kwargs.get("deadline_ns", monotonic_ns() + 20_000_000_000),
    )


def test_constructor_and_views_do_not_scan_or_create(inbox, monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("An inert view performed filesystem/source IO")

    assert not inbox.root.exists()
    with monkeypatch.context() as patch:
        for name in ("stat", "open", "mkdir", "iterdir"):
            patch.setattr(Path, name, denied)
        patch.setattr(module, "source_fingerprint", denied)
        before = inbox.view()
        before["files"].append({"not": "a choice"})
        assert inbox.choices() == [] and inbox.view()["status"] == "NOT_DISCOVERED"
    assert not inbox.root.exists()


@pytest.mark.parametrize(
    "name,payload,mime",
    [
        ("unknown.txt", b"Hardware is not present.\n", "text/plain"),
        ("notes.json", b'{"measurement":null}', "application/json"),
        ("photo.png", b"\x89PNG\r\n\x1a\nOpaque fixture", "image/png"),
        ("photo.jpeg", b"\xff\xd8\xffOpaque fixture", "image/jpeg"),
        ("drawing.pdf", b"%PDF-Opaque fixture", "application/pdf"),
    ],
)
def test_exact_originals_are_selected_and_not_media_decoded(inbox, name, payload, mime):
    assert discover(inbox)["files"] == []
    (inbox.root / name).write_bytes(payload)
    view = discover(inbox)
    assert view["status"] == "READY" and not view["issues"]
    choice = view["files"][0]
    assert choice["basename"] == name and choice["media_type"] == mime
    with selected(inbox, [choice["choice_id"]]) as files:
        assert files[0].payload == payload
        assert files[0].payload_sha256 == choice["payload_sha256"]
        with pytest.raises(WizardError, match="owns"):
            discover(inbox)


@pytest.mark.parametrize(
    "name,payload",
    [
        ("image.exe", b"not allowed"),
        ("notes.txt", b"\x00NUL"),
        ("notes.json", b"\xff"),
        ("image.jpg", b"not jpeg"),
        ("image.png", b"not png"),
        ("drawing.pdf", b"not pdf"),
        ("notes.txt", b""),
        ("space name.txt", b"invalid portable name"),
    ],
)
def test_bad_inputs_are_retained_as_issues_not_choices(inbox, name, payload):
    discover(inbox)
    (inbox.root / name).write_bytes(payload)
    result = discover(inbox)
    assert result["files"] == [] and result["issues"]
    assert (inbox.root / name).read_bytes() == payload


@pytest.mark.parametrize(
    "name", ["CON.txt", "aux.json", "COM1.png", "LPT9.pdf", "a/../b.txt", "a.txt."]
)
def test_windows_reserved_and_nonportable_names_rejected_without_io(name):
    with pytest.raises(WizardError):
        module._media(name, b"fixture")


def test_replacement_and_rediscovery_invalidate_tokens(inbox):
    discover(inbox)
    path = inbox.root / "original.txt"
    path.write_bytes(b"first original")
    token = discover(inbox)["files"][0]["choice_id"]
    path.write_bytes(b"later original")
    with pytest.raises(WizardError, match="changed"):
        with selected(inbox, [token]):
            pytest.fail("changed input selected")
    next_token = discover(inbox)["files"][0]["choice_id"]
    assert next_token != token
    with pytest.raises(WizardError, match="choice"):
        with selected(inbox, [token]):
            pytest.fail("stale selection reused")


def test_hardlinks_and_directories_not_read_as_files(inbox):
    discover(inbox)
    (inbox.root / "directory.txt").mkdir()
    original = inbox.root / "original.txt"
    original.write_bytes(b"multiply linked")
    os.link(original, inbox.root / "alias.txt")
    result = discover(inbox)
    assert result["files"] == [] and len(result["issues"]) == 3


def test_inventory_overflow_is_held_and_does_not_publish_partial_choices(inbox):
    discover(inbox)
    for index in range(33):
        (inbox.root / f"note-{index}.txt").write_bytes(b"fixture")
    with pytest.raises(WizardError, match="exceeds"):
        discover(inbox)
    assert inbox.view()["status"] == "HELD" and not inbox.choices()


def test_empty_selection_needs_no_input_directory(inbox):
    with selected(inbox, []) as files:
        assert files == ()
    assert not inbox.root.exists()


@pytest.mark.parametrize("fault", ["stop", "deadline", "source"])
def test_stop_deadline_source_hold_before_or_after_selection(inbox, monkeypatch, fault):
    discover(inbox)
    (inbox.root / "note.txt").write_bytes(b"fixture")
    token = discover(inbox)["files"][0]["choice_id"]
    cancel = Event()
    with pytest.raises(WizardError):
        with selected(inbox, [token], cancellation=cancel):
            if fault == "stop":
                cancel.set()
            elif fault == "source":
                monkeypatch.setattr(module, "source_fingerprint", lambda _: "f" * 64)
            else:
                monkeypatch.setattr(module.time, "monotonic_ns", lambda: 2**63 - 1)


@pytest.mark.skipif(os.name != "nt", reason="Windows original input sharing pin")
def test_windows_pin_denies_input_write_and_delete_but_releases_after_scope(inbox):
    discover(inbox)
    path = inbox.root / "note.txt"
    path.write_bytes(b"original fixture")
    token = discover(inbox)["files"][0]["choice_id"]
    with selected(inbox, [token]):
        with pytest.raises(OSError):
            path.write_bytes(b"replacement")
        with pytest.raises(OSError):
            path.unlink()
    assert path.read_bytes() == b"original fixture"
