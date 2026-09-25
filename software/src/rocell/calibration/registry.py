"""Content-addressed calibration storage with dependency invalidation."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import threading
from typing import Any, BinaryIO, Iterable, Iterator, Mapping, Sequence
import uuid

from .artifacts import (
    ArtifactAssessment,
    ArtifactState,
    CalibrationArtifact,
    CalibrationResolution,
)


class CalibrationRegistryError(RuntimeError):
    """Calibration storage, integrity, or dependency resolution failed."""


_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.-]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_INDEX_FIELDS = frozenset({"schema", "current"})
_PUBLICATION_FIELDS = frozenset(
    {
        "schema",
        "artifact_id",
        "artifact_hash",
        "artifact_version",
        "artifact_document_sha256",
        "previous_artifact_hash",
    }
)
_MAX_INDEX_BYTES = 1_000_000
_MAX_ARTIFACT_BYTES = 16_000_000
_MAX_PUBLICATION_BYTES = 16_384
_MAX_PUBLICATIONS_PER_ARTIFACT = 4_096
_PROCESS_LOCKS: dict[str, threading.RLock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise CalibrationRegistryError(f"{name} must match {_IDENTIFIER.pattern}")
    return value


def _sha256(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise CalibrationRegistryError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _canonical_payload(document: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def _strict_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CalibrationRegistryError(f"Duplicate JSON field {key!r}")
        result[key] = value
    return result


def _load_object(path: Path, *, maximum_bytes: int) -> dict[str, Any]:
    try:
        # Never use read_bytes() at a trust boundary: it allocates according to
        # attacker-controlled file size before we can apply the schema limit.
        with path.open("rb") as stream:
            payload = stream.read(maximum_bytes + 1)
        if len(payload) > maximum_bytes:
            raise CalibrationRegistryError(
                f"Registry JSON exceeds {maximum_bytes} bytes: {path}"
            )
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CalibrationRegistryError(f"Nonfinite JSON constant {value!r}")
            ),
        )
    except CalibrationRegistryError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise CalibrationRegistryError(f"Could not read {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise CalibrationRegistryError(f"Expected an object in {path}")
    if payload != _canonical_payload(document):
        raise CalibrationRegistryError(f"Registry JSON is not canonical: {path}")
    return document


def _atomic_json(
    path: Path,
    document: Mapping[str, Any],
    *,
    maximum_bytes: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_payload(document)
    if len(payload) > maximum_bytes:
        raise CalibrationRegistryError(
            f"Registry JSON exceeds {maximum_bytes} bytes: {path}"
        )
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _immutable_json(
    path: Path,
    document: Mapping[str, Any],
    *,
    maximum_bytes: int,
) -> None:
    """Publish a complete immutable file without replacing an existing one."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_payload(document)
    if len(payload) > maximum_bytes:
        raise CalibrationRegistryError(
            f"Registry JSON exceeds {maximum_bytes} bytes: {path}"
        )
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
    finally:
        if temporary.exists():
            temporary.unlink()


def _process_lock(key: str) -> threading.RLock:
    with _PROCESS_LOCKS_GUARD:
        return _PROCESS_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def _exclusive_file_lock(stream: BinaryIO) -> Iterator[None]:
    """Hold a one-byte advisory lock for cross-process index writers."""

    stream.seek(0, os.SEEK_END)
    if stream.tell() == 0:
        stream.write(b"\0")
        stream.flush()
        os.fsync(stream.fileno())
    stream.seek(0)
    if os.name == "nt":
        locking = importlib.import_module("msvcrt")
        locking.locking(stream.fileno(), locking.LK_LOCK, 1)
        try:
            yield
        finally:
            stream.seek(0)
            locking.locking(stream.fileno(), locking.LK_UNLCK, 1)
        return

    locking = importlib.import_module("fcntl")
    locking.flock(stream.fileno(), locking.LOCK_EX)
    try:
        yield
    finally:
        locking.flock(stream.fileno(), locking.LOCK_UN)


class CalibrationRegistry:
    INDEX_SCHEMA = "rocell.calibration_registry.v1"
    PUBLICATION_SCHEMA = "rocell.calibration_publication.v1"

    def __init__(self, root: Path) -> None:
        requested_root = Path(root).absolute()
        if requested_root.is_symlink():
            raise CalibrationRegistryError("Calibration registry root cannot be a symlink")
        self.root = requested_root.resolve()
        self.index_path = self.root / "index.json"
        self.artifact_root = self.root / "artifacts"
        self.publication_root = self.root / "publications"
        self._writer_lock_path = self.root / ".registry.lock"
        self._process_writer_lock = _process_lock(os.path.normcase(str(self.root)))

    def _assert_safe_path(self, path: Path) -> None:
        try:
            relative = path.absolute().relative_to(self.root)
        except ValueError as exc:
            raise CalibrationRegistryError(
                f"Calibration registry path escapes its root: {path}"
            ) from exc
        if self.root.is_symlink():
            raise CalibrationRegistryError("Calibration registry root cannot be a symlink")
        current = self.root
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise CalibrationRegistryError(
                    f"Calibration registry path cannot traverse a symlink: {current}"
                )
            # On Windows, directory junctions/reparse points are not reliably
            # reported by Path.is_symlink().  Resolving each existing prefix
            # and proving it still lies below the selected root also catches
            # those escape paths.
            try:
                current.resolve(strict=False).relative_to(self.root)
            except (OSError, ValueError) as exc:
                raise CalibrationRegistryError(
                    "Calibration registry path cannot traverse a symlink, "
                    f"junction, or reparse-point escape: {current}"
                ) from exc

    def _ensure_directory(self, path: Path) -> None:
        self._assert_safe_path(path)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CalibrationRegistryError(
                f"Could not create calibration registry directory {path}: {exc}"
            ) from exc
        self._assert_safe_path(path)
        if not path.is_dir():
            raise CalibrationRegistryError(
                f"Calibration registry directory is invalid: {path}"
            )

    def _validated_index(self, document: Mapping[str, Any]) -> dict[str, Any]:
        actual_fields = frozenset(document)
        if actual_fields != _INDEX_FIELDS:
            missing = tuple(sorted(_INDEX_FIELDS - actual_fields))
            unexpected = tuple(sorted(actual_fields - _INDEX_FIELDS))
            raise CalibrationRegistryError(
                "Calibration registry fields differ from the exact schema: "
                f"missing={missing}, unexpected={unexpected}"
            )
        if document["schema"] != self.INDEX_SCHEMA:
            raise CalibrationRegistryError("Unsupported calibration registry schema")
        raw_current = document["current"]
        if not isinstance(raw_current, dict):
            raise CalibrationRegistryError("Calibration registry current map is invalid")
        current = {
            _identifier(key, "Current calibration artifact id"): _sha256(
                digest, f"Current calibration hash for {key!r}"
            )
            for key, digest in raw_current.items()
        }
        return {
            "schema": self.INDEX_SCHEMA,
            "current": dict(sorted(current.items())),
        }

    def _index(self) -> dict[str, Any]:
        self._assert_safe_path(self.index_path)
        if not self.index_path.exists():
            return {"schema": self.INDEX_SCHEMA, "current": {}}
        index = _load_object(self.index_path, maximum_bytes=_MAX_INDEX_BYTES)
        return self._validated_index(index)

    def _path(self, artifact_id: str, digest: str) -> Path:
        validated_id = _identifier(artifact_id, "Calibration artifact id")
        validated_digest = _sha256(digest, "Calibration artifact hash")
        path = self.artifact_root / validated_id / f"{validated_digest}.json"
        self._assert_safe_path(path)
        return path

    def _read_artifact(self, path: Path) -> CalibrationArtifact:
        self._assert_safe_path(path)
        try:
            return CalibrationArtifact.from_dict(
                _load_object(path, maximum_bytes=_MAX_ARTIFACT_BYTES)
            )
        except CalibrationRegistryError:
            raise
        except (TypeError, ValueError) as exc:
            raise CalibrationRegistryError(
                f"Invalid calibration artifact document {path}: {exc}"
            ) from exc

    def _publication_path(self, artifact_id: str, digest: str) -> Path:
        validated_id = _identifier(artifact_id, "Calibration artifact id")
        validated_digest = _sha256(digest, "Calibration artifact hash")
        path = self.publication_root / validated_id / f"{validated_digest}.json"
        self._assert_safe_path(path)
        return path

    def _publication_document(
        self,
        artifact: CalibrationArtifact,
        digest: str,
        previous_digest: str | None,
    ) -> dict[str, Any]:
        return {
            "schema": self.PUBLICATION_SCHEMA,
            "artifact_id": artifact.artifact_id,
            "artifact_hash": digest,
            "artifact_version": artifact.version,
            "artifact_document_sha256": hashlib.sha256(
                _canonical_payload(artifact.to_dict())
            ).hexdigest(),
            "previous_artifact_hash": previous_digest,
        }

    def _validate_publication(
        self,
        document: Mapping[str, Any],
        *,
        artifact: CalibrationArtifact,
        digest: str,
    ) -> None:
        actual_fields = frozenset(document)
        if actual_fields != _PUBLICATION_FIELDS:
            missing = tuple(sorted(_PUBLICATION_FIELDS - actual_fields))
            unexpected = tuple(sorted(actual_fields - _PUBLICATION_FIELDS))
            raise CalibrationRegistryError(
                "Calibration publication fields differ from the exact schema: "
                f"missing={missing}, unexpected={unexpected}"
            )
        if document["schema"] != self.PUBLICATION_SCHEMA:
            raise CalibrationRegistryError("Unsupported calibration publication schema")
        if document["artifact_id"] != artifact.artifact_id:
            raise CalibrationRegistryError("Calibration publication artifact id mismatch")
        if document["artifact_hash"] != digest:
            raise CalibrationRegistryError("Calibration publication artifact hash mismatch")
        if document["artifact_version"] != artifact.version or isinstance(
            document["artifact_version"], bool
        ):
            raise CalibrationRegistryError("Calibration publication version mismatch")
        expected_document_hash = hashlib.sha256(
            _canonical_payload(artifact.to_dict())
        ).hexdigest()
        if document["artifact_document_sha256"] != expected_document_hash:
            raise CalibrationRegistryError(
                "Calibration publication document hash mismatch"
            )
        previous = document["previous_artifact_hash"]
        if previous is not None:
            _sha256(previous, "Previous calibration artifact hash")
            if previous == digest:
                raise CalibrationRegistryError(
                    "Calibration publication cannot refer to itself as previous"
                )

    def _published_artifacts(
        self, artifact_id: str
    ) -> tuple[tuple[str, CalibrationArtifact], ...]:
        """Load and validate one artifact's immutable publication history.

        Publication receipts are the registry's durable history.  Reading the
        current index without comparing it with that history would allow an
        older, otherwise self-consistent index to silently roll the selected
        calibration back.  Each receipt and artifact is parsed exactly once,
        then their predecessor links are checked as one linear graph.  This is
        deliberately O(n), rather than walking every predecessor chain and
        doing O(n**2) file reads.
        """

        validated_id = _identifier(artifact_id, "Calibration artifact id")
        directory = self.publication_root / validated_id
        self._assert_safe_path(directory)
        if not directory.exists():
            return ()
        if not directory.is_dir():
            raise CalibrationRegistryError(
                f"Calibration publication path is not a directory: {directory}"
            )
        # Do not materialize an untrusted directory with glob().  Stop after
        # limit + 1 matching entries so the memory and directory-walk work are
        # bounded even if an attacker fills this directory.
        publication_paths: list[Path] = []
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if not entry.name.endswith(".json"):
                        continue
                    if len(publication_paths) >= _MAX_PUBLICATIONS_PER_ARTIFACT:
                        raise CalibrationRegistryError(
                            "Calibration publication history exceeds its bounded limit"
                        )
                    publication_path = Path(entry.path)
                    self._assert_safe_path(publication_path)
                    if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                        raise CalibrationRegistryError(
                            "Calibration publication entry is not a regular file: "
                            f"{publication_path}"
                        )
                    publication_paths.append(publication_path)
        except CalibrationRegistryError:
            raise
        except OSError as exc:
            raise CalibrationRegistryError(
                f"Could not enumerate calibration publication history {directory}: {exc}"
            ) from exc

        nodes: dict[str, tuple[CalibrationArtifact, str | None]] = {}
        for publication_path in publication_paths:
            self._assert_safe_path(publication_path)
            digest = _sha256(
                publication_path.stem,
                "Calibration publication filename hash",
            )
            artifact_path = self._path(validated_id, digest)
            if not artifact_path.is_file():
                raise CalibrationRegistryError(
                    "Calibration publication names a missing artifact: "
                    f"{validated_id}:{digest}"
                )
            artifact = self._read_artifact(artifact_path)
            if artifact.artifact_id != validated_id or artifact.content_hash != digest:
                raise CalibrationRegistryError(
                    "Published calibration artifact integrity failed"
                )
            publication = _load_object(
                publication_path, maximum_bytes=_MAX_PUBLICATION_BYTES
            )
            self._validate_publication(
                publication, artifact=artifact, digest=digest
            )
            previous = publication["previous_artifact_hash"]
            nodes[digest] = (artifact, previous)

        if not nodes:
            return ()

        successors: dict[str, str] = {}
        for digest, (_, previous) in nodes.items():
            if previous is None:
                continue
            if previous not in nodes:
                raise CalibrationRegistryError(
                    "Calibration publication names a missing predecessor: "
                    f"{validated_id}:{previous}"
                )
            existing_successor = successors.get(previous)
            if existing_successor is not None:
                raise CalibrationRegistryError(
                    "Calibration publication history branches after "
                    f"{validated_id}:{previous}"
                )
            successors[previous] = digest

        # Detect closed cycles before reporting the derived genesis/head
        # counts.  A cycle cannot satisfy the append-only lineage contract even
        # when a separate valid-looking chain supplies one genesis and head.
        completed: set[str] = set()
        for start in nodes:
            trail: set[str] = set()
            current = start
            while current not in completed:
                if current in trail:
                    raise CalibrationRegistryError(
                        f"Cyclic calibration publication history for {validated_id}"
                    )
                trail.add(current)
                previous = nodes[current][1]
                if previous is None:
                    break
                current = previous
            completed.update(trail)

        genesis = tuple(
            digest for digest, (_, previous) in nodes.items() if previous is None
        )
        if len(genesis) != 1:
            raise CalibrationRegistryError(
                "Calibration publication history must contain exactly one genesis"
            )
        heads = tuple(digest for digest in nodes if digest not in successors)
        if len(heads) != 1:
            raise CalibrationRegistryError(
                "Calibration publication history must contain exactly one head"
            )

        ordered_digests: list[str] = []
        current = genesis[0]
        while True:
            ordered_digests.append(current)
            successor = successors.get(current)
            if successor is None:
                break
            current = successor
        if len(ordered_digests) != len(nodes) or ordered_digests[-1] != heads[0]:
            raise CalibrationRegistryError(
                f"Disconnected calibration publication history for {validated_id}"
            )

        for previous_digest, current_digest in zip(
            ordered_digests, ordered_digests[1:]
        ):
            previous_artifact = nodes[previous_digest][0]
            current_artifact = nodes[current_digest][0]
            if previous_artifact.version >= current_artifact.version:
                raise CalibrationRegistryError(
                    "Calibration publication versions must strictly increase"
                )

        return tuple((digest, nodes[digest][0]) for digest in ordered_digests)

    def _validate_current_is_publication_head(
        self,
        artifact_id: str,
        digest: str | None,
        artifact: CalibrationArtifact | None,
        *,
        publications: tuple[tuple[str, CalibrationArtifact], ...] | None = None,
    ) -> None:
        """Reject index deletion, rollback, branching, or a stale current head."""

        if publications is None:
            publications = self._published_artifacts(artifact_id)
        if digest is None:
            if publications:
                raise CalibrationRegistryError(
                    "Calibration index omits an artifact with publication history"
                )
            return
        if artifact is None:  # pragma: no cover - internal programming guard
            raise CalibrationRegistryError("Current calibration artifact is unavailable")
        matching = tuple(item for item in publications if item[0] == digest)
        if len(matching) != 1 or matching[0][1] != artifact:
            raise CalibrationRegistryError(
                "Current calibration is not represented exactly once by a publication "
                "receipt in publication history"
            )
        if publications[-1][0] != digest:
            raise CalibrationRegistryError(
                "Calibration index is not at the unique published version head"
            )

    def install(self, artifact: CalibrationArtifact) -> str:
        """Store immutable content and make it the current version atomically."""

        if not isinstance(artifact, CalibrationArtifact):
            raise TypeError("artifact must be a CalibrationArtifact")
        self._ensure_directory(self.root)
        self._ensure_directory(self.artifact_root)
        self._ensure_directory(self.publication_root)
        self._assert_safe_path(self._writer_lock_path)
        with self._process_writer_lock:
            try:
                lock_stream = self._writer_lock_path.open("a+b")
            except OSError as exc:
                raise CalibrationRegistryError(
                    f"Could not open calibration registry writer lock: {exc}"
                ) from exc
            with lock_stream, _exclusive_file_lock(lock_stream):
                # Version comparison and read-modify-write of the shared index
                # are one transaction with respect to all cooperating writers.
                digest = artifact.content_hash
                current_artifact = self.get_current(artifact.artifact_id)
                if (
                    current_artifact is not None
                    and current_artifact.content_hash != digest
                    and artifact.version <= current_artifact.version
                ):
                    raise CalibrationRegistryError(
                        f"Calibration {artifact.artifact_id} version must increase beyond "
                        f"{current_artifact.version}"
                    )
                index = self._index()
                current = dict(index["current"])
                current[artifact.artifact_id] = digest
                proposed_index = {
                    "schema": self.INDEX_SCHEMA,
                    "current": dict(sorted(current.items())),
                }
                artifact_document = artifact.to_dict()
                publication_document = self._publication_document(
                    artifact,
                    digest,
                    (
                        current_artifact.content_hash
                        if current_artifact is not None
                        else None
                    ),
                )
                # Prove every pending owned file fits its read-side bound
                # before publishing any immutable component.  A failed size
                # check therefore cannot strand an orphan history branch.
                for document, maximum_bytes, label in (
                    (artifact_document, _MAX_ARTIFACT_BYTES, "artifact"),
                    (publication_document, _MAX_PUBLICATION_BYTES, "publication"),
                    (proposed_index, _MAX_INDEX_BYTES, "index"),
                ):
                    if len(_canonical_payload(document)) > maximum_bytes:
                        raise CalibrationRegistryError(
                            f"Calibration {label} exceeds {maximum_bytes} bytes"
                        )
                destination = self._path(artifact.artifact_id, digest)
                self._ensure_directory(destination.parent)
                if not destination.exists():
                    _immutable_json(
                        destination,
                        artifact_document,
                        maximum_bytes=_MAX_ARTIFACT_BYTES,
                    )
                loaded = self._read_artifact(destination)
                if loaded != artifact or loaded.content_hash != digest:
                    raise CalibrationRegistryError(
                        "Stored calibration content does not match the publication"
                    )

                publication_path = self._publication_path(
                    artifact.artifact_id, digest
                )
                self._ensure_directory(publication_path.parent)
                if not publication_path.exists():
                    _immutable_json(
                        publication_path,
                        publication_document,
                        maximum_bytes=_MAX_PUBLICATION_BYTES,
                    )
                self._validate_current_is_publication_head(
                    artifact.artifact_id, digest, loaded
                )

                self._assert_safe_path(self.index_path)
                _atomic_json(
                    self.index_path,
                    proposed_index,
                    maximum_bytes=_MAX_INDEX_BYTES,
                )
                return digest

    def get_current(self, artifact_id: str) -> CalibrationArtifact | None:
        validated_id = _identifier(artifact_id, "Calibration artifact id")
        digest = self._index()["current"].get(validated_id)
        if digest is None:
            self._validate_current_is_publication_head(validated_id, None, None)
            return None
        publications = self._published_artifacts(validated_id)
        matching = tuple(item for item in publications if item[0] == digest)
        if matching:
            artifact = matching[0][1]
        else:
            # Preserve the more specific missing/current-integrity diagnostics
            # for an index that points outside publication history, while the
            # head check below still rejects a well-formed but unpublished blob.
            path = self._path(validated_id, digest)
            if not path.is_file():
                raise CalibrationRegistryError(
                    f"Missing current artifact file for {validated_id}"
                )
            artifact = self._read_artifact(path)
            if artifact.artifact_id != validated_id or artifact.content_hash != digest:
                raise CalibrationRegistryError(
                    f"Current artifact integrity failed for {validated_id}"
                )
        self._validate_current_is_publication_head(
            validated_id, digest, artifact, publications=publications
        )
        return artifact

    def _assess_recursive(
        self,
        artifact_id: str,
        context_hashes: Mapping[str, str],
        *,
        manifest_id: str,
        active_build_id: str,
        stack: tuple[str, ...],
        memo: dict[str, ArtifactAssessment],
    ) -> ArtifactAssessment:
        if artifact_id in memo:
            return memo[artifact_id]
        artifact = self.get_current(artifact_id)
        if artifact is None:
            assessment = ArtifactAssessment(
                artifact_id,
                ArtifactState.MISSING,
                None,
                (f"MISSING_CALIBRATION:{artifact_id}",),
            )
            memo[artifact_id] = assessment
            return assessment

        reasons: list[str] = []
        state = artifact.state
        if artifact.state is not ArtifactState.VALID:
            reasons.append(f"CALIBRATION_STATE:{artifact_id}:{artifact.state.value}")
        if artifact.manifest_id != manifest_id:
            reasons.append(f"CALIBRATION_MANIFEST_MISMATCH:{artifact_id}")
        if artifact.active_build_id != active_build_id:
            reasons.append(f"CALIBRATION_BUILD_MISMATCH:{artifact_id}")
        for dependency, expected_hash in artifact.dependency_hashes.items():
            if context_hashes.get(dependency) != expected_hash:
                reasons.append(
                    f"STALE_CALIBRATION_DEPENDENCY:{artifact_id}:{dependency}"
                )
        next_stack = (*stack, artifact_id)
        for parent_id, expected_hash in artifact.parent_artifact_hashes.items():
            parent = self.get_current(parent_id)
            if parent is None or parent.content_hash != expected_hash:
                reasons.append(
                    f"STALE_PARENT_CALIBRATION:{artifact_id}:{parent_id}"
                )
                continue
            if parent_id in next_stack:
                reasons.append(
                    f"CYCLIC_PARENT_CALIBRATION:{artifact_id}:{parent_id}"
                )
                continue
            # A child already marked non-valid never gains authority, so keep
            # its own direct state diagnostic stable.  A nominal-only graph is
            # useful rehearsal evidence and should not explode into redundant
            # transitive reasons.  The transitive check is mandatory for every
            # artifact that otherwise claims VALID.
            if artifact.state is ArtifactState.VALID:
                parent_assessment = self._assess_recursive(
                    parent_id,
                    context_hashes,
                    manifest_id=manifest_id,
                    active_build_id=active_build_id,
                    stack=next_stack,
                    memo=memo,
                )
                if not parent_assessment.valid:
                    reasons.append(
                        f"INVALID_PARENT_CALIBRATION:{artifact_id}:{parent_id}"
                    )
        if reasons and state is ArtifactState.VALID:
            state = ArtifactState.STALE_DEPENDENCY
        assessment = ArtifactAssessment(
            artifact_id, state, artifact.content_hash, tuple(reasons)
        )
        memo[artifact_id] = assessment
        return assessment

    def assess(
        self,
        artifact_id: str,
        context_hashes: Mapping[str, str],
        *,
        manifest_id: str,
        active_build_id: str,
    ) -> ArtifactAssessment:
        validated_id = _identifier(artifact_id, "Calibration artifact id")
        return self._assess_recursive(
            validated_id,
            context_hashes,
            manifest_id=manifest_id,
            active_build_id=active_build_id,
            stack=(),
            memo={},
        )

    def resolve(
        self,
        artifact_ids: Iterable[str],
        context_hashes: Mapping[str, str],
        *,
        manifest_id: str,
        active_build_id: str,
    ) -> CalibrationResolution:
        memo: dict[str, ArtifactAssessment] = {}
        assessments = {
            artifact_id: self._assess_recursive(
                _identifier(artifact_id, "Calibration artifact id"),
                context_hashes,
                manifest_id=manifest_id,
                active_build_id=active_build_id,
                stack=(),
                memo=memo,
            )
            for artifact_id in dict.fromkeys(artifact_ids)
        }
        return CalibrationResolution(assessments)

    def affected_by(self, changed_dependencies: Iterable[str]) -> tuple[str, ...]:
        changed = set(changed_dependencies)
        affected: list[str] = []
        for artifact_id in self._index()["current"]:
            artifact = self.get_current(artifact_id)
            if artifact is not None and changed.intersection(artifact.dependency_hashes):
                affected.append(artifact_id)
        return tuple(sorted(affected))
