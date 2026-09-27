# Repository artifact governance

- **Document status:** Current repository policy
- **Audience:** Contributors and maintainers
- **Authority:** Repository placement and reviewability only; this policy does
  not qualify hardware, establish redistribution rights, or authorize a release

Tactevra includes source, printable hardware, CAD exchange files, manuals, and
media. Those assets make the repository useful, but byte-for-byte copies and
large generated outputs accumulate clone cost quickly. Existing history remains
intact. New changes must identify one canonical artifact instead of adding the
same bytes to several instructional folders.

## Current baseline

The September 27, 2026 protected-`main` baseline contains substantial hardware
content, including repeated historical build-package files. GitHub reports a
repository size of roughly 304 MiB; the checked-out tree is larger before Git
compression. This is a maintenance baseline, not a target and not permission to
continue the same duplication pattern.

Do not rewrite history or delete a historical package merely to satisfy this
policy. Reduction or archival requires a separate compatibility review because
published paths, manifests, checksums, and build instructions may depend on the
existing bytes.

## Ordinary change policy

The protected offline workflow compares the proposed revision with its first
parent. It rejects:

- an added or modified file larger than 10 MiB; and
- an added or modified governed binary whose exact Git object already exists at
  another tracked path.

The governed binary set is recorded in
`.github/repository-artifact-policy.json` and includes CAD, print, archive,
document, image, video, and workbook formats. Text and source files are not
subject to duplicate-byte rejection. Existing unchanged duplicates are
grandfathered so ordinary documentation and software work remains possible.

Run the check after committing the proposed change:

```powershell
python scripts/ci/check_repository_artifacts.py
```

## Preferred placement

1. Keep the editable or authoritative source in one canonical component folder.
2. Generate build-step packages, archives, rendered manuals, and convenience
   bundles from a manifest when practical.
3. In instructions, link to the canonical path or name the packaging command;
   do not copy identical bytes into each step.
4. Keep private captures, credentials, device backups, model weights, and bulk
   experiment output outside Git under the existing evidence and release rules.
5. Record third-party origin and terms separately; a size-policy pass is not a
   license or redistribution decision.

Git LFS is not assumed available for this repository. Moving a file to LFS or
external hosting therefore requires a separate cost, access, retention, and
clean-clone review.

## Exception procedure

An exception requires a public owner-reviewed issue explaining:

1. why a smaller source, generator, manifest, or external artifact is
   insufficient;
2. the exact path, byte size, SHA-256 digest, and expected update frequency;
3. clone/history cost and later-removal expectations;
4. privacy, credential, provenance, and redistribution review; and
5. the reproduction or inspection procedure.

After that disposition, add one exact entry to the policy's `exceptions` list.
Any byte or path change invalidates the exception. Do not raise the global limit,
use wildcard exceptions, or split one artifact into pieces to evade review.

## Relationship to other controls

- [Evidence retention](EVIDENCE_RETENTION.md) governs generated research data.
- [Release integrity](RELEASING.md) governs source-preview contents and
  candidate selection.
- [Third-party notices](../THIRD_PARTY_NOTICES.md) index external ownership and
  unresolved redistribution questions.
- [Repository operations](REPOSITORY_OPERATIONS.md) defines review and handoff
  behavior.

A passing artifact check means only that the current change stayed within the
ordinary repository-growth boundary.
