"""Produce a deterministic, read-only inventory of large exact duplicate blobs.

The report uses Git object identity, not filename or content heuristics, to find
duplicates. Classifications and canonical candidates are routing aids for human
review; they do not authorize deletion, relocation, or history rewriting.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess

from check_source_archive_footprint import ROOT, TreeEntry, git_tree, load_policy


SCHEMA = "tactevra.source-archive-duplicate-inventory.v1"


@dataclass(frozen=True)
class DuplicateGroup:
    object_id: str
    blob_bytes: int
    copies: int
    duplicate_bytes: int
    classification: str
    review_owner: str
    provenance_note: str
    canonical_candidates: tuple[str, ...]
    paths: tuple[str, ...]


def _classify(paths: tuple[str, ...]) -> tuple[str, str, str, tuple[str, ...]]:
    rc03_prefix = "active-project/RoCell_v0_3/"
    rc03_step_prefix = f"{rc03_prefix}BUILD_BY_STEP/"
    rc03_stl_prefix = f"{rc03_prefix}stl/"
    rc03_canonical = tuple(path for path in paths if path.startswith(rc03_stl_prefix))
    has_step_copy = any(path.startswith(rc03_step_prefix) for path in paths)
    crosses_revision = any(path.startswith("active-project/RoCell_v0_2/") for path in paths)
    if rc03_canonical and has_step_copy and crosses_revision:
        return (
            "cross-revision-and-instructional-stl",
            "arm and hardware workstreams",
            "One exact STL blob appears in frozen RC02 material, the central RC03 STL set, "
            "and one or more RC03 build-step folders. Frozen-revision retention and current "
            "instructional convenience copies require separate review.",
            rc03_canonical,
        )
    if rc03_canonical and has_step_copy:
        return (
            "rc03-instructional-stl-copy",
            "arm and hardware workstreams",
            "One exact STL blob appears in the central RC03 STL set and one or more "
            "build-step folders. The central path is a canonical candidate, subject to "
            "builder-route and regeneration review.",
            rc03_canonical,
        )
    if rc03_canonical and crosses_revision:
        return (
            "frozen-cross-revision-stl-retention",
            "arm, hardware, and repository workstreams",
            "One exact STL blob is intentionally retained in frozen RC02 provenance and "
            "the active canonical RC03 STL set. RC02 remains immutable historical evidence; "
            "the RC03 path is the current canonical source. Removal requires a new owner "
            "decision and is outside the approved Step 00 cleanup.",
            rc03_canonical,
        )

    camera_prefix = "hardware/static_overhead_camera/cad/output/"
    if all(path.startswith(camera_prefix) for path in paths):
        non_revision = tuple(
            path for path in paths if "/revisions/" not in f"/{path}/")
        return (
            "static-camera-packaged-output-copy",
            "hardware and repository workstreams",
            "One exact generated CAD output appears in multiple live, revision, fallback, "
            "or print-pack locations. Packaging and historical evidence must be reviewed "
            "before selecting a canonical path.",
            non_revision,
        )

    return (
        "unclassified-exact-duplicate",
        "repository maintainer with affected workstream",
        "The paths share an exact Git blob but do not match a reviewed repository-specific "
        "routing pattern. Determine provenance and ownership before proposing a change.",
        (),
    )


def inventory(entries: list[TreeEntry], minimum_bytes: int) -> list[DuplicateGroup]:
    grouped: dict[str, list[TreeEntry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.object_id].append(entry)

    result: list[DuplicateGroup] = []
    for object_id, raw_group in grouped.items():
        if len(raw_group) < 2 or raw_group[0].size < minimum_bytes:
            continue
        paths = tuple(sorted(entry.path for entry in raw_group))
        classification, owner, note, candidates = _classify(paths)
        result.append(DuplicateGroup(
            object_id=object_id,
            blob_bytes=raw_group[0].size,
            copies=len(raw_group),
            duplicate_bytes=raw_group[0].size * (len(raw_group) - 1),
            classification=classification,
            review_owner=owner,
            provenance_note=note,
            canonical_candidates=tuple(sorted(candidates)),
            paths=paths,
        ))
    return sorted(
        result,
        key=lambda group: (-group.duplicate_bytes, group.object_id),
    )


def report(groups: list[DuplicateGroup], commit: str, minimum_bytes: int) -> dict:
    class_bytes: Counter[str] = Counter()
    class_groups: Counter[str] = Counter()
    for group in groups:
        class_bytes[group.classification] += group.duplicate_bytes
        class_groups[group.classification] += 1
    return {
        "schema": SCHEMA,
        "commit": commit,
        "minimum_blob_bytes": minimum_bytes,
        "group_count": len(groups),
        "duplicate_bytes": sum(group.duplicate_bytes for group in groups),
        "classification_summary": {
            name: {
                "groups": class_groups[name],
                "duplicate_bytes": class_bytes[name],
            }
            for name in sorted(class_groups)
        },
        "groups": [asdict(group) for group in groups],
        "limitations": [
            "Exact Git object identity finds byte-for-byte duplicates only.",
            "Classifications and canonical candidates are provisional review routes.",
            "The inventory does not authorize deletion, relocation, or history rewriting.",
        ],
    }


def _markdown(payload: dict, limit: int) -> str:
    groups = payload["groups"] if limit == 0 else payload["groups"][:limit]
    lines = [
        "# Tactevra large exact-duplicate inventory",
        "",
        f"Commit: `{payload['commit']}`  ",
        f"Minimum blob size: `{payload['minimum_blob_bytes']}` bytes  ",
        f"Groups: `{payload['group_count']}`  ",
        f"Avoidable duplicate bytes: `{payload['duplicate_bytes']}`",
        "",
        "Classifications are review routes, not deletion decisions.",
        "",
        "| Rank | Duplicate bytes | Copies | Classification | Blob |",
        "| ---: | ---: | ---: | --- | --- |",
    ]
    for rank, group in enumerate(groups, 1):
        lines.append(
            f"| {rank} | {group['duplicate_bytes']} | {group['copies']} | "
            f"{group['classification']} | `{group['object_id']}` |")
    for rank, group in enumerate(groups, 1):
        lines.extend([
            "",
            f"## {rank}. `{group['object_id']}`",
            "",
            f"- Review owner: {group['review_owner']}",
            f"- Blob bytes: {group['blob_bytes']}",
            f"- Duplicate bytes: {group['duplicate_bytes']}",
            f"- Provenance note: {group['provenance_note']}",
            "- Canonical candidates: "
            + (", ".join(f"`{path}`" for path in group["canonical_candidates"])
               if group["canonical_candidates"] else "none identified"),
            "- Paths:",
        ])
        lines.extend(f"  - `{path}`" for path in group["paths"])
    return "\n".join(lines)


def _head(root: Path = ROOT) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True,
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument(
        "--limit", type=int, default=0,
        help="maximum groups in Markdown output; zero includes every group",
    )
    args = parser.parse_args()
    if args.limit < 0:
        raise SystemExit("--limit must be zero or a positive integer")
    try:
        policy = load_policy()
        minimum = policy["ceilings"]["duplicate_min_blob_bytes"]
        payload = report(inventory(git_tree(), minimum), _head(), minimum)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"duplicate inventory could not run: {exc}") from exc
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_markdown(payload, args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
