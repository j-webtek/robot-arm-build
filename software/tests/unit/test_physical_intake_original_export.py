"""Actual temporary byte export, modeled intake subjects, no device access."""

from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from threading import Event
from time import monotonic_ns
from types import SimpleNamespace

import pytest

from rocell.application import physical_intake_original_export as module
from test_physical_intake_submission import intake_fixture


@pytest.fixture(scope="module")
def fixture():
    return intake_fixture(observed=True)


def export(tmp_path, fixture, **changes):
    kwargs = dict(
        submission=fixture.submission,
        originals=(
            (
                fixture.reference,
                fixture.attachment.basename,
                fixture.attachment.media_type,
                fixture.payload,
            ),
        ),
        include_private_originals=True,
        cancellation=Event(),
        deadline_ns=monotonic_ns() + 120_000_000_000,
    )
    kwargs.update(changes)
    return module.export_physical_intake_originals(tmp_path, **kwargs)


def test_exact_original_bytes_and_submission_manifest_last(
    tmp_path, fixture, monkeypatch
):
    names = []
    original_write = module._write_payload

    def recording(path, payload, **kwargs):
        names.append(path.name)
        return original_write(path, payload, **kwargs)

    monkeypatch.setattr(module, "_write_payload", recording)
    result = export(tmp_path, fixture)
    directory = Path(result["path"])
    assert result["status"] == "EXPORTED_PRIVATE_ORIGINALS"
    assert names == [
        "original-00-modeled-observation.txt",
        "submission.json",
        "manifest.json",
    ]
    assert (directory / names[0]).read_bytes() == fixture.payload
    assert (directory / "submission.json").read_bytes() == fixture.submission.payload
    raw = (directory / "manifest.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == result["manifest_sha256"]
    manifest = json.loads(raw)
    assert manifest["submission_sha256"] == fixture.submission.sha256
    assert manifest["attachments"][0]["reference"] == fixture.reference.to_dict()
    assert result["attachment_bytes"] == len(fixture.payload)
    assert result["submission_bytes"] == len(fixture.submission.payload)
    assert result["total_bytes"] == len(raw) + len(fixture.payload) + len(
        fixture.submission.payload
    )
    assert result["original_bytes_preserved"] is True
    assert "without redaction" in result["privacy_warning"]
    assert all(result[key] is False for key in module._FLAGS)
    assert set(p.name for p in directory.iterdir()) == set(names)


def test_credential_like_originals_are_not_sanitized(tmp_path, fixture, monkeypatch):
    from rocell.application import wizard_diagnostic_export

    def forbidden(*args, **kwargs):
        pytest.fail("private original export must not invoke the text sanitizer")

    monkeypatch.setattr(
        wizard_diagnostic_export, "sanitize_diagnostic_record", forbidden
    )
    monkeypatch.setattr(wizard_diagnostic_export, "_sanitize", forbidden)
    result = export(tmp_path, fixture)
    assert (
        Path(result["path"], "submission.json").read_bytes()
        == fixture.submission.payload
    )


@pytest.mark.parametrize("approval", [False, 1, "true", None])
def test_privacy_approval_is_literal_and_checked_before_io(
    tmp_path, fixture, monkeypatch, approval
):
    def forbidden(*args, **kwargs):
        pytest.fail("denied original export touched filesystem")

    with monkeypatch.context() as patcher:
        patcher.setattr(module, "_checked_directory", forbidden)
        with pytest.raises(module.PhysicalIntakeOriginalExportError) as raised:
            export(tmp_path, fixture, include_private_originals=approval)
        assert raised.value.code == "PRIVATE_ORIGINALS_APPROVAL_REQUIRED"
        assert raised.value.receipt is None
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "fault",
    [
        "bytes",
        "length",
        "reference",
        "name",
        "media",
        "missing",
        "duplicate",
        "mutable_bytes",
        "list",
    ],
)
def test_wrong_exact_original_tuple_refused_before_creating_directory(
    tmp_path, fixture, fault
):
    ref, name, media, raw = (
        fixture.reference,
        fixture.attachment.basename,
        fixture.attachment.media_type,
        fixture.payload,
    )
    if fault == "bytes":
        raw = b"x" * len(raw)
    if fault == "length":
        raw += b"x"
    if fault == "reference":
        ref = replace(ref, manifest_sha256="e" * 64)
    if fault == "name":
        name = "other.txt"
    if fault == "media":
        media = "image/png"
    if fault == "mutable_bytes":
        raw = bytearray(raw)
    items = ((ref, name, media, raw),)
    if fault == "missing":
        items = ()
    if fault == "duplicate":
        items *= 2
    if fault == "list":
        items = list(items)
    with pytest.raises(module.PhysicalIntakeOriginalExportError):
        export(tmp_path, fixture, originals=items)
    assert not list(tmp_path.iterdir())


def test_cancel_and_expired_deadline_do_not_create_destination(tmp_path, fixture):
    stop = Event()
    stop.set()
    for values in (
        {"cancellation": stop},
        {"deadline_ns": monotonic_ns() - 1},
        {"deadline_ns": monotonic_ns() + 121_000_000_000},
    ):
        with pytest.raises(module.PhysicalIntakeOriginalExportError):
            export(tmp_path, fixture, **values)
    assert not list(tmp_path.iterdir())


def test_fixed_export_name_collision_never_overwrites(tmp_path, fixture, monkeypatch):
    monkeypatch.setattr(module.uuid, "uuid4", lambda: SimpleNamespace(hex="a" * 32))
    first = export(tmp_path, fixture)
    raw = Path(first["path"], "manifest.json").read_bytes()
    with pytest.raises(module.PhysicalIntakeOriginalExportError) as raised:
        export(tmp_path, fixture)
    assert raised.value.code == "ORIGINAL_EXPORT_NAME_COLLISION"
    assert raised.value.receipt["directory_created"] is False
    assert Path(first["path"], "manifest.json").read_bytes() == raw


def test_partial_write_is_retained_without_manifest_or_retry(
    tmp_path, fixture, monkeypatch
):
    original_write = module._write_payload
    calls = []

    def fail_after_first(path, payload, **kwargs):
        calls.append(path.name)
        if path.name == "submission.json":
            with path.open("xb") as stream:
                stream.write(payload[:17])
            raise OSError("private arbitrary message must not enter receipt")
        return original_write(path, payload, **kwargs)

    monkeypatch.setattr(module, "_write_payload", fail_after_first)
    with pytest.raises(module.PhysicalIntakeOriginalExportError) as raised:
        export(tmp_path, fixture)
    receipt = raised.value.receipt
    assert receipt["status"] == "INCOMPLETE_OR_HELD" and not receipt["manifest_written"]
    assert receipt["verified_attachment_count"] == 1
    directory = Path(receipt["path"])
    assert (
        directory / "original-00-modeled-observation.txt"
    ).read_bytes() == fixture.payload
    assert (directory / "submission.json").read_bytes() == fixture.submission.payload[
        :17
    ]
    assert not (directory / "manifest.json").exists()
    assert len(calls) == 2 and "private arbitrary" not in json.dumps(receipt)


def test_changed_output_detected_before_manifest(tmp_path, fixture, monkeypatch):
    read = module.read_bounded_regular_file
    counts = {}

    def changed(path, **kwargs):
        counts[path.name] = counts.get(path.name, 0) + 1
        raw = read(path, **kwargs)
        if path.name.startswith("original-") and counts[path.name] == 2:
            return b"x" * len(raw)
        return raw

    monkeypatch.setattr(module, "read_bounded_regular_file", changed)
    with pytest.raises(module.PhysicalIntakeOriginalExportError) as raised:
        export(tmp_path, fixture)
    assert raised.value.code == "ORIGINAL_EXPORT_BYTE_MISMATCH"
    assert not Path(raised.value.receipt["path"], "manifest.json").exists()


def test_late_guard_failure_retains_complete_files_as_held(
    tmp_path, fixture, monkeypatch
):
    real_guard = module._directory_guard

    @contextmanager
    def fails_after_export(path, **kwargs):
        with real_guard(path, **kwargs):
            yield
        if path == tmp_path:
            raise OSError("late root guard failure")

    monkeypatch.setattr(module, "_directory_guard", fails_after_export)
    with pytest.raises(module.PhysicalIntakeOriginalExportError) as raised:
        export(tmp_path, fixture)
    receipt = raised.value.receipt
    assert receipt["manifest_written"] is True
    assert receipt["original_bytes_preserved"] is False
    assert receipt["status"] == "INCOMPLETE_OR_HELD"
    assert Path(receipt["path"], "manifest.json").is_file()


def test_missing_or_relative_parent_is_not_created(tmp_path, fixture):
    for parent in (tmp_path / "missing", Path("relative-parent")):
        with pytest.raises(module.PhysicalIntakeOriginalExportError):
            export(parent, fixture)
    assert not list(tmp_path.iterdir())


def test_stop_after_final_manifest_readback_retains_the_written_marker(
    tmp_path, fixture, monkeypatch
):
    stop = Event()
    read = module.read_bounded_regular_file

    def stop_after_manifest(path, **kwargs):
        raw = read(path, **kwargs)
        if path.name == "manifest.json":
            stop.set()
        return raw

    monkeypatch.setattr(module, "read_bounded_regular_file", stop_after_manifest)
    with pytest.raises(module.PhysicalIntakeOriginalExportError) as raised:
        export(tmp_path, fixture, cancellation=stop)
    receipt = raised.value.receipt
    assert raised.value.code == "ORIGINAL_EXPORT_CANCELLED"
    assert receipt["manifest_written"] is True
    assert receipt["original_bytes_preserved"] is False
    assert receipt["status"] == "INCOMPLETE_OR_HELD"
    assert Path(receipt["path"], "manifest.json").is_file()


def test_short_write_keeps_partial_bytes_without_final_manifest(
    tmp_path, fixture, monkeypatch
):
    original_open = Path.open

    class ShortWrite:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def write(self, data):
            return self.stream.write(data[:-1])

    def opened(path, mode="r", *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        return (
            ShortWrite(stream)
            if mode == "xb" and path.name.startswith("original-")
            else stream
        )

    monkeypatch.setattr(Path, "open", opened)
    with pytest.raises(module.PhysicalIntakeOriginalExportError) as raised:
        export(tmp_path, fixture)
    assert raised.value.code == "ORIGINAL_EXPORT_IO_FAILED"
    directory = Path(raised.value.receipt["path"])
    assert (
        directory / "original-00-modeled-observation.txt"
    ).read_bytes() == fixture.payload[:-1]
    assert not (directory / "manifest.json").exists()


def test_expired_original_deadline_has_fixed_timeout_code(tmp_path, fixture):
    with pytest.raises(module.PhysicalIntakeOriginalExportError) as raised:
        export(tmp_path, fixture, deadline_ns=monotonic_ns() - 1)
    assert raised.value.code == "ORIGINAL_EXPORT_TIMED_OUT"
