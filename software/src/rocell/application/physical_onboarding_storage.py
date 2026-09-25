"""Qualified publication adapter for physical-onboarding V2 stores.

This module is a persistence adapter only.  It has no device, camera, serial,
power, motion, permit, or worker dependency.  A caller must provide a mutation
guard (normally a recheck of already-held CELL/SESSION leases) and both the
stable qualification anchor and the fresh startup qualification report for the
exact deployment root.

The cell-global ledgers use an immutable next-event file as their compare-and-
set token.  The event is made durable before the independently replaceable
head is advanced.  A failure between those publications therefore leaves a
detectable suffix; this adapter never adopts, deletes, or retries that suffix.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
from typing import Any, Callable, Iterable, Mapping

from rocell.application.physical_onboarding import MAX_EVIDENCE_BYTES
from rocell.application.physical_onboarding_attempts import (
    ATTEMPT_LEDGER_EVENT_SCHEMA,
    ATTEMPT_LEDGER_HEAD_SCHEMA,
    ATTEMPT_LEDGER_HEADER_SCHEMA,
    MAX_JSON_BYTES as MAX_LEDGER_JSON_BYTES,
    DurableLedgerPublisher,
    parse_canonical_json,
)
from rocell.application.physical_onboarding_durability import (
    DurabilityCheckpoint,
    DurabilityQualificationReport,
    FaultInjector,
    PhysicalOnboardingDurabilityError,
    PublicationMode,
    canonical_bytes,
    canonical_sha256,
    contained_path,
    publish_bytes,
    read_bounded_regular_file,
    require_effect_durability_pair,
    safe_root,
)
from rocell.application.physical_onboarding_quarantine import (
    QUARANTINE_LEDGER_EVENT_SCHEMA,
    QUARANTINE_LEDGER_HEAD_SCHEMA,
    QUARANTINE_LEDGER_HEADER_SCHEMA,
)
from rocell.application.physical_onboarding_v2 import SessionPublicationProtocol


MAX_SESSION_PUBLICATION_BYTES = MAX_EVIDENCE_BYTES
MAX_LISTING_PATH_CHARS = 2048
MAX_LISTING_DEPTH = 8

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_EVENT_PATH_RE = re.compile(r"events/event-([0-9]{8})\.json\Z")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
_HEAD_FIELDS = frozenset(
    {
        "schema",
        "ledger_id",
        "cell_id",
        "header_sha256",
        "event_count",
        "last_sequence",
        "last_event_sha256",
        "head_sha256",
    }
)
_HEADER_TO_HEAD_AND_EVENT = {
    ATTEMPT_LEDGER_HEADER_SCHEMA: (
        ATTEMPT_LEDGER_HEAD_SCHEMA,
        ATTEMPT_LEDGER_EVENT_SCHEMA,
        "attempt_head_before_sha256",
    ),
    QUARANTINE_LEDGER_HEADER_SCHEMA: (
        QUARANTINE_LEDGER_HEAD_SCHEMA,
        QUARANTINE_LEDGER_EVENT_SCHEMA,
        "quarantine_head_before_sha256",
    ),
}
_HEAD_TO_EVENT = {
    head_schema: (event_schema, prior_head_field)
    for head_schema, event_schema, prior_head_field in _HEADER_TO_HEAD_AND_EVENT.values()
}

MutationGuard = Callable[[], None]


class PhysicalOnboardingStorageError(PhysicalOnboardingDurabilityError):
    """The qualified store or one of its guarded publications is invalid."""


def _digest(value: object, label: str, *, allow_zero: bool = False) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise PhysicalOnboardingStorageError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    if not allow_zero and value == "0" * 64:
        raise PhysicalOnboardingStorageError(f"{label} cannot be the zero digest")
    return value


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PhysicalOnboardingStorageError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _parse_canonical_object(
    payload: bytes, *, maximum: int, label: str
) -> dict[str, Any]:
    if type(payload) is not bytes or not payload or len(payload) > maximum:
        raise PhysicalOnboardingStorageError(f"{label} exceeds its byte bound")
    try:
        value = json.loads(
            payload.decode("ascii"),
            object_pairs_hook=_strict_object,
            parse_float=lambda token: (_ for _ in ()).throw(
                PhysicalOnboardingStorageError(f"{label} contains a float")
            ),
            parse_constant=lambda token: (_ for _ in ()).throw(
                PhysicalOnboardingStorageError(
                    f"{label} contains nonfinite constant {token!r}"
                )
            ),
        )
    except PhysicalOnboardingStorageError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PhysicalOnboardingStorageError(f"{label} is not strict JSON") from exc
    if not isinstance(value, dict):
        raise PhysicalOnboardingStorageError(f"{label} must be a JSON object")
    if canonical_bytes(value, maximum_bytes=maximum) != payload:
        raise PhysicalOnboardingStorageError(f"{label} is not canonical JSON")
    return value


def _validate_self_hash(
    document: Mapping[str, Any], hash_field: str, label: str
) -> str:
    if hash_field not in document:
        raise PhysicalOnboardingStorageError(f"{label} has no {hash_field}")
    recorded = _digest(document[hash_field], f"{label} {hash_field}")
    core = dict(document)
    del core[hash_field]
    if canonical_sha256(core) != recorded:
        raise PhysicalOnboardingStorageError(f"{label} self hash mismatch")
    return recorded


def _parse_head(payload: bytes, label: str) -> dict[str, Any]:
    document = _parse_canonical_object(
        payload, maximum=MAX_LEDGER_JSON_BYTES, label=label
    )
    if set(document) != _HEAD_FIELDS:
        raise PhysicalOnboardingStorageError(
            f"{label} fields differ from the ledger schema"
        )
    if document["schema"] not in _HEAD_TO_EVENT:
        raise PhysicalOnboardingStorageError(f"{label} schema is unsupported")
    count = document["event_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise PhysicalOnboardingStorageError(f"{label} event_count is invalid")
    if document["last_sequence"] != count - 1:
        raise PhysicalOnboardingStorageError(f"{label} sequence/count mismatch")
    _digest(document["header_sha256"], f"{label} header_sha256")
    _digest(
        document["last_event_sha256"],
        f"{label} last_event_sha256",
        allow_zero=count == 0,
    )
    if (count == 0) != (document["last_event_sha256"] == "0" * 64):
        raise PhysicalOnboardingStorageError(f"{label} empty-head hash is inconsistent")
    _validate_self_hash(document, "head_sha256", label)
    return document


def _stable_report_identity(
    report: DurabilityQualificationReport,
) -> tuple[object, ...]:
    return (
        report.source_binding_sha256,
        report.root_sha256,
        report.platform,
        report.filesystem,
        report.volume_identity,
        report.adapter_id,
        tuple((item.check_id, item.passed) for item in report.checks),
        report.qualified_for_effects,
    )


@dataclass(frozen=True, slots=True)
class QualifiedWindowsOnboardingPublication:
    """Qualified, guarded persistence for V2 sessions and global ledgers.

    ``qualification_anchor`` is the stable receipt whose hash is embedded in
    ledger records.  ``startup_report`` is a fresh execution of the same
    on-volume qualification.  Its timestamp and report hash may differ, while
    all safety-relevant identity and check results must remain identical.
    """

    deployment_root: Path
    source_binding_sha256: str
    qualification_anchor: DurabilityQualificationReport
    startup_report: DurabilityQualificationReport
    mutation_guard: MutationGuard = field(compare=False, repr=False)
    fault_injector: FaultInjector | None = field(
        default=None, compare=False, repr=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.deployment_root, Path):
            raise TypeError("deployment_root must be pathlib.Path")
        root = safe_root(self.deployment_root, label="onboarding deployment root")
        object.__setattr__(self, "deployment_root", root)
        _digest(self.source_binding_sha256, "source_binding_sha256")
        if not isinstance(self.qualification_anchor, DurabilityQualificationReport):
            raise TypeError(
                "qualification_anchor must be DurabilityQualificationReport"
            )
        if not isinstance(self.startup_report, DurabilityQualificationReport):
            raise TypeError("startup_report must be DurabilityQualificationReport")
        if not callable(self.mutation_guard):
            raise TypeError("mutation_guard must be callable")
        if self.fault_injector is not None and not callable(self.fault_injector):
            raise TypeError("fault_injector must be callable")
        self._require_qualified_reports()

    @property
    def effectful_durability_qualified(self) -> bool:
        try:
            self._require_qualified_reports()
        except PhysicalOnboardingDurabilityError:
            return False
        return True

    @property
    def durability_qualification_sha256(self) -> str:
        self._require_qualified_reports()
        return self.qualification_anchor.report_sha256

    def _require_qualified_reports(self) -> None:
        require_effect_durability_pair(
            self.qualification_anchor,
            self.startup_report,
            root=self.deployment_root,
            source_binding_sha256=self.source_binding_sha256,
        )
        if _stable_report_identity(
            self.qualification_anchor
        ) != _stable_report_identity(self.startup_report):
            raise PhysicalOnboardingStorageError(
                "startup durability report differs from the qualification anchor"
            )
        if self.startup_report.checked_at_ns < self.qualification_anchor.checked_at_ns:
            raise PhysicalOnboardingStorageError(
                "startup durability report predates the qualification anchor"
            )

    def _guard(self) -> None:
        try:
            self.mutation_guard()
        except Exception as exc:
            raise PhysicalOnboardingStorageError(
                "mutation guard rejected publication"
            ) from exc

    def _checkpoint(self, checkpoint: str | DurabilityCheckpoint) -> None:
        if self.fault_injector is not None:
            self.fault_injector(
                checkpoint.value
                if isinstance(checkpoint, DurabilityCheckpoint)
                else checkpoint
            )

    def _lexical_candidate(self, path: Path, *, label: str) -> Path:
        """Validate names and containment, without granting filesystem approval."""

        if not isinstance(path, Path):
            raise TypeError(f"{label} must be pathlib.Path")
        if not path.is_absolute() or any(
            part in {"", ".", ".."} for part in path.parts[1:]
        ):
            raise PhysicalOnboardingStorageError(
                f"{label} must be an absolute canonical path"
            )
        for part in path.parts[1:]:
            self._validate_windows_name(part, label=label)
        candidate = Path(os.path.abspath(path))
        if candidate == self.deployment_root:
            return self.deployment_root
        try:
            candidate.relative_to(self.deployment_root)
        except ValueError as exc:
            raise PhysicalOnboardingStorageError(
                f"{label} is outside the qualified deployment root"
            ) from exc
        return candidate

    def _candidate(self, path: Path, *, label: str) -> Path:
        candidate = self._lexical_candidate(path, label=label)
        if candidate == self.deployment_root:
            return self.deployment_root
        return contained_path(
            self.deployment_root,
            candidate.relative_to(self.deployment_root),
            label=label,
        )

    def _existing_root(self, root: Path, *, label: str) -> Path:
        # Establish one existing root with one complete fresh ancestor walk.
        # Strict canonical resolution and directory/type/link checks belong to
        # safe_root, not the lexical helper. No observation survives this call;
        # later file containment, qualification and opened-handle checks remain
        # independent. New publication destinations still use _candidate above.
        candidate = self._lexical_candidate(root, label=label)
        return safe_root(candidate, label=label)

    def qualification_sha256(self, root: Path) -> str:
        self._require_qualified_reports()
        self._candidate(root, label="qualified ledger root")
        return self.qualification_anchor.report_sha256

    def write_new_file(self, path: Path, payload: bytes) -> None:
        self._require_qualified_reports()
        destination = self._candidate(path, label="immutable publication path")
        parent = self._existing_root(destination.parent, label="publication parent")
        self._guard()
        publish_bytes(
            parent,
            destination.name,
            payload,
            mode=PublicationMode.IMMUTABLE,
            maximum_bytes=MAX_SESSION_PUBLICATION_BYTES,
            fault_injector=self.fault_injector,
        )
        self._guard()

    def replace_file(self, path: Path, payload: bytes) -> None:
        self._require_qualified_reports()
        destination = self._candidate(path, label="replace publication path")
        parent = self._existing_root(destination.parent, label="publication parent")
        self._guard()
        publish_bytes(
            parent,
            destination.name,
            payload,
            mode=PublicationMode.REPLACE,
            maximum_bytes=MAX_SESSION_PUBLICATION_BYTES,
            fault_injector=self.fault_injector,
        )
        self._guard()

    def publish_new_directory(self, source: Path, destination: Path) -> None:
        self._require_qualified_reports()
        source_root = self._existing_root(source, label="directory publication source")
        selected_destination = self._candidate(
            destination, label="directory publication destination"
        )
        if source_root.parent != selected_destination.parent:
            raise PhysicalOnboardingStorageError(
                "directory publication must be a same-parent atomic move"
            )
        if os.path.lexists(selected_destination):
            raise PhysicalOnboardingStorageError(
                "immutable directory publication already exists"
            )
        self._audit_directory_tree(source_root)
        self._guard()
        if os.name == "nt":
            # TODO: move this behind a public durability-module directory
            # publication helper.  Until then, use the exact qualified Win32
            # MOVEFILE_WRITE_THROUGH implementation rather than plain rename.
            from rocell.application.physical_onboarding_durability import (
                _windows_move,
            )

            _windows_move(source_root, selected_destination, replace=False)
        else:
            os.rename(source_root, selected_destination)
            self._portable_sync_directory(selected_destination.parent)
        self._guard()
        self._existing_root(selected_destination, label="published directory")

    def sync_directory(self, path: Path) -> None:
        self._require_qualified_reports()
        directory = self._existing_root(path, label="directory synchronization target")
        if os.name != "nt":
            self._portable_sync_directory(directory)
        # On Windows every file publication and directory move used above is
        # already write-through and reopened/flushed.  The startup report's
        # directory-entry check qualifies that exact strategy.  There is no
        # portable Python directory-fsync call that should be presented as an
        # additional Windows guarantee.

    @staticmethod
    def _portable_sync_directory(path: Path) -> None:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(path, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def initialize_ledger(
        self, root: Path, *, header_payload: bytes, head_payload: bytes
    ) -> None:
        self._require_qualified_reports()
        destination = self._candidate(root, label="new ledger root")
        if destination == self.deployment_root:
            raise PhysicalOnboardingStorageError(
                "ledger root cannot be the deployment root"
            )
        parent = self._existing_root(destination.parent, label="ledger parent")
        if os.path.lexists(destination):
            raise PhysicalOnboardingStorageError("ledger root already exists")
        header = _parse_canonical_object(
            header_payload, maximum=MAX_LEDGER_JSON_BYTES, label="ledger header"
        )
        head = _parse_head(head_payload, "initial ledger head")
        header_schema = header.get("schema")
        if not isinstance(header_schema, str):
            raise PhysicalOnboardingStorageError("ledger header schema is invalid")
        expected = _HEADER_TO_HEAD_AND_EVENT.get(header_schema)
        if expected is None or head["schema"] != expected[0]:
            raise PhysicalOnboardingStorageError("ledger header/head schema mismatch")
        header_hash = _validate_self_hash(header, "header_sha256", "ledger header")
        if (
            head["ledger_id"] != header.get("ledger_id")
            or head["cell_id"] != header.get("cell_id")
            or head["header_sha256"] != header_hash
            or head["event_count"] != 0
            or header.get("durability_qualification_sha256")
            != self.durability_qualification_sha256
        ):
            raise PhysicalOnboardingStorageError(
                "initial ledger binding is inconsistent"
            )

        temporary = self._candidate(
            parent / f".partial-{destination.name}-{secrets.token_hex(16)}",
            label="partial ledger root",
        )
        self._guard()
        try:
            temporary.mkdir(exist_ok=False)
            (temporary / "events").mkdir(exist_ok=False)
            self.write_new_file(temporary / "header.json", header_payload)
            self.write_new_file(temporary / "head.json", head_payload)
            self.sync_directory(temporary / "events")
            self.sync_directory(temporary)
            self.publish_new_directory(temporary, destination)
            self.sync_directory(parent)
        finally:
            # If ownership was lost, retain even a known partial for explicit
            # reconciliation instead of mutating it outside the guard.
            try:
                self._guard()
            except PhysicalOnboardingStorageError:
                pass
            else:
                self._cleanup_partial_ledger(temporary)
        self._guard()

    @staticmethod
    def _cleanup_partial_ledger(temporary: Path) -> None:
        if not os.path.lexists(temporary):
            return
        # Remove only the exact files this initializer owns.  Unexpected or
        # substituted entries are retained for explicit reconciliation.
        try:
            for name in ("header.json", "head.json"):
                path = temporary / name
                if path.is_file() and not path.is_symlink():
                    path.unlink()
            events = temporary / "events"
            if events.is_dir() and not events.is_symlink():
                events.rmdir()
            temporary.rmdir()
        except OSError:
            pass

    def read_bounded(
        self, root: Path, relative_path: str, *, maximum_bytes: int
    ) -> bytes:
        self._require_qualified_reports()
        # Containment below performs the complete fresh root walk itself.
        # Validate lexical deployment membership here, not a second identical
        # filesystem walk immediately before that containment check. Nothing
        # is cached across reads: qualification, root/relative components and
        # the independently opened file handle are all checked on every call.
        selected_root = self._lexical_candidate(root, label="ledger read root")
        if (
            isinstance(maximum_bytes, bool)
            or not isinstance(maximum_bytes, int)
            or maximum_bytes <= 0
            or maximum_bytes > MAX_SESSION_PUBLICATION_BYTES
        ):
            raise PhysicalOnboardingStorageError("read byte bound is invalid")
        relative = self._relative_path(relative_path, label="ledger read path")
        path = contained_path(
            selected_root, Path(*relative.parts), label="ledger read path"
        )
        try:
            # The Win32 implementation opens with FILE_SHARE_DELETE so atomic
            # head replacement is not wedged by a concurrent bounded reader.
            payload = read_bounded_regular_file(
                path, maximum_bytes=maximum_bytes, label="ledger file"
            )
        except PhysicalOnboardingDurabilityError as exc:
            raise PhysicalOnboardingStorageError("could not read ledger file") from exc
        return payload

    def list_relative_files(
        self, root: Path, *, maximum_entries: int
    ) -> tuple[str, ...]:
        self._require_qualified_reports()
        selected_root = self._existing_root(root, label="ledger listing root")
        if (
            isinstance(maximum_entries, bool)
            or not isinstance(maximum_entries, int)
            or maximum_entries <= 0
        ):
            raise PhysicalOnboardingStorageError("listing entry bound is invalid")
        files: list[str] = []
        stack: list[tuple[Path, PurePosixPath | None, int]] = [(selected_root, None, 0)]
        visited_entries = 0
        while stack:
            directory, prefix, depth = stack.pop()
            if depth > MAX_LISTING_DEPTH:
                raise PhysicalOnboardingStorageError(
                    "ledger listing is too deeply nested"
                )
            try:
                entries = list(os.scandir(directory))
            except OSError as exc:
                raise PhysicalOnboardingStorageError(
                    "could not enumerate ledger root"
                ) from exc
            for entry in entries:
                visited_entries += 1
                if visited_entries > maximum_entries:
                    raise PhysicalOnboardingStorageError(
                        "ledger listing exceeds its entry bound"
                    )
                relative = (
                    PurePosixPath(entry.name) if prefix is None else prefix / entry.name
                )
                rendered = relative.as_posix()
                if len(rendered) > MAX_LISTING_PATH_CHARS:
                    raise PhysicalOnboardingStorageError(
                        "ledger listing path is too long"
                    )
                candidate = contained_path(
                    selected_root, Path(*relative.parts), label="ledger listing entry"
                )
                if entry.is_symlink():
                    raise PhysicalOnboardingStorageError(
                        "ledger listing contains a symlink"
                    )
                if entry.is_dir(follow_symlinks=False):
                    if rendered != "events":
                        raise PhysicalOnboardingStorageError(
                            "ledger listing contains an unknown directory"
                        )
                    stack.append(
                        (
                            safe_root(candidate, label="ledger directory"),
                            relative,
                            depth + 1,
                        )
                    )
                elif entry.is_file(follow_symlinks=False):
                    files.append(rendered)
                else:
                    raise PhysicalOnboardingStorageError(
                        "ledger listing contains a non-file entry"
                    )
        return tuple(sorted(files))

    @staticmethod
    def _relative_path(value: str, *, label: str) -> PurePosixPath:
        if not isinstance(value, str) or not value or "\\" in value:
            raise PhysicalOnboardingStorageError(f"{label} is malformed")
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or len(value) > MAX_LISTING_PATH_CHARS
        ):
            raise PhysicalOnboardingStorageError(f"{label} is unsafe")
        for part in path.parts:
            QualifiedWindowsOnboardingPublication._validate_windows_name(
                part, label=label
            )
        return path

    @staticmethod
    def _validate_windows_name(value: str, *, label: str) -> None:
        if (
            not value
            or ":" in value
            or value != value.rstrip(" .")
            or any(ord(character) < 32 for character in value)
            or value.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES
        ):
            raise PhysicalOnboardingStorageError(
                f"{label} contains a Windows-unsafe path component"
            )

    def _audit_directory_tree(self, root: Path) -> None:
        stack = [root]
        count = 0
        while stack:
            directory = stack.pop()
            try:
                entries = list(os.scandir(directory))
            except OSError as exc:
                raise PhysicalOnboardingStorageError(
                    "could not audit directory publication source"
                ) from exc
            for entry in entries:
                count += 1
                if count > 16_384:
                    raise PhysicalOnboardingStorageError(
                        "directory publication source exceeds its entry bound"
                    )
                self._validate_windows_name(entry.name, label="directory publication")
                candidate = self._candidate(
                    Path(entry.path), label="directory publication entry"
                )
                if entry.is_symlink():
                    raise PhysicalOnboardingStorageError(
                        "directory publication source contains a symlink"
                    )
                if entry.is_dir(follow_symlinks=False):
                    stack.append(safe_root(candidate, label="publication directory"))
                elif not entry.is_file(follow_symlinks=False):
                    raise PhysicalOnboardingStorageError(
                        "directory publication source contains a non-file entry"
                    )

    def commit_append(
        self,
        root: Path,
        *,
        event_relative_path: str,
        event_payload: bytes,
        head_payload: bytes,
        expected_head_sha256: str,
    ) -> None:
        """Publish one exact next event, then advance its committed head."""

        self._require_qualified_reports()
        selected_root = self._existing_root(root, label="ledger append root")
        expected_hash = _digest(expected_head_sha256, "expected_head_sha256")
        relative_event = self._relative_path(
            event_relative_path, label="ledger event path"
        )
        match = _EVENT_PATH_RE.fullmatch(relative_event.as_posix())
        if match is None:
            raise PhysicalOnboardingStorageError("ledger event path is not canonical")

        self._guard()
        current_payload = self.read_bounded(
            selected_root, "head.json", maximum_bytes=MAX_LEDGER_JSON_BYTES
        )
        current = _parse_head(current_payload, "current ledger head")
        if current["head_sha256"] != expected_hash:
            raise PhysicalOnboardingStorageError("stale committed ledger head")
        sequence = current["event_count"]
        if int(match.group(1)) != sequence:
            raise PhysicalOnboardingStorageError(
                "ledger event path is not the exact next sequence"
            )

        event = parse_canonical_json(event_payload, "ledger event")
        next_head = _parse_head(head_payload, "next ledger head")
        expected_event_schema, prior_head_field = _HEAD_TO_EVENT[current["schema"]]
        if next_head["schema"] != current["schema"]:
            raise PhysicalOnboardingStorageError(
                "ledger head schema changed during append"
            )
        if event.get("schema") != expected_event_schema:
            raise PhysicalOnboardingStorageError(
                "ledger event schema does not match its head"
            )
        event_hash = _validate_self_hash(event, "event_sha256", "ledger event")
        shared = ("ledger_id", "cell_id", "header_sha256")
        if any(next_head[key] != current[key] for key in shared):
            raise PhysicalOnboardingStorageError("next ledger head identity changed")
        if (
            event.get("ledger_id") != current["ledger_id"]
            or event.get("cell_id") != current["cell_id"]
            or event.get("sequence") != sequence
            or event.get("previous_event_sha256") != current["last_event_sha256"]
            or event.get(prior_head_field) != expected_hash
            or event.get("durability_qualification_sha256")
            != self.durability_qualification_sha256
            or next_head["event_count"] != sequence + 1
            or next_head["last_sequence"] != sequence
            or next_head["last_event_sha256"] != event_hash
        ):
            raise PhysicalOnboardingStorageError(
                "ledger append binding is inconsistent"
            )

        event_path = contained_path(
            selected_root, Path(*relative_event.parts), label="ledger event publication"
        )
        self._guard()
        publish_bytes(
            selected_root,
            Path(*relative_event.parts),
            event_payload,
            mode=PublicationMode.IMMUTABLE,
            maximum_bytes=MAX_LEDGER_JSON_BYTES,
            fault_injector=self.fault_injector,
        )
        if not event_path.is_file():
            raise PhysicalOnboardingStorageError(
                "published ledger event is unavailable"
            )
        self._checkpoint(DurabilityCheckpoint.LEDGER_AFTER_RECORD_PUBLISH)
        self._guard()

        # The immutable next-event path is the CAS token.  Rechecking the old
        # head before replacement also rejects any writer that bypassed that
        # token or changed the ledger while this process held its guard.
        rechecked_payload = self.read_bounded(
            selected_root, "head.json", maximum_bytes=MAX_LEDGER_JSON_BYTES
        )
        if rechecked_payload != current_payload:
            raise PhysicalOnboardingStorageError(
                "committed ledger head changed after event publication"
            )
        self._guard()
        publish_bytes(
            selected_root,
            "head.json",
            head_payload,
            mode=PublicationMode.REPLACE,
            maximum_bytes=MAX_LEDGER_JSON_BYTES,
            fault_injector=self.fault_injector,
        )
        self._checkpoint(DurabilityCheckpoint.LEDGER_AFTER_HEAD_PUBLISH)
        self._guard()
        if (
            self.read_bounded(
                selected_root, "head.json", maximum_bytes=MAX_LEDGER_JSON_BYTES
            )
            != head_payload
        ):
            raise PhysicalOnboardingStorageError(
                "committed ledger head did not reopen exactly"
            )


def _typecheck_protocols(
    value: QualifiedWindowsOnboardingPublication,
) -> tuple[SessionPublicationProtocol, DurableLedgerPublisher]:
    """Static-only witness that the adapter implements both narrow protocols."""

    return value, value


__all__ = [
    "MAX_SESSION_PUBLICATION_BYTES",
    "MutationGuard",
    "PhysicalOnboardingStorageError",
    "QualifiedWindowsOnboardingPublication",
]
