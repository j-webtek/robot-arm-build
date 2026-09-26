# Tactevra versioning and compatibility

Tactevra is pre-release research software. The repository currently has no
stable release and makes no general compatibility or physical-performance
guarantee. This policy governs future **source preview** labels; it does not
qualify hardware, firmware, trained models, or live operation.

## Source preview versions

Future source previews use Semantic Versioning with an explicit pre-release
suffix, for example `tactevra-v0.1.0-alpha.1`. Until a stable `1.0.0` release:

- minor versions may introduce substantial experimental interfaces;
- patch versions contain compatible corrections within that preview line;
- pre-release suffix changes identify successive reviewed candidates; and
- every published tag is immutable and resolves to one reviewed commit.

The [release procedure](RELEASING.md) controls publication. A merge to `main`, a
passing CI run, or an `[Unreleased]` changelog entry is not a published release.

## Compatibility surfaces

The Tactevra brand and repository slug do not rename deployed compatibility
interfaces. Existing `rocell` package names, commands, schemas, configuration
keys, evidence identifiers, and historical RC02/RC03 paths remain unchanged
unless a separately reviewed compatibility change says otherwise.

The following have independent identities and qualification evidence:

- source repository previews;
- Python package and command interfaces;
- AI-to-arm schemas and contracts;
- controller applications and firmware images;
- hardware and printable-workcell releases; and
- model checkpoints and evaluation records.

A version change in one surface does not silently promote or requalify another.
Release notes must identify exactly which surfaces are included.

## Breaking changes

A proposed breaking change must document the affected producers and consumers,
migration path, deprecation behavior, and evidence required by both workstreams.
Security or physical-safety corrections may remove unsafe behavior without a
long deprecation period; the release notes must state that explicitly.

Historical records are not rewritten to match newer interfaces. They retain
their original names, outcomes, and limitations.
