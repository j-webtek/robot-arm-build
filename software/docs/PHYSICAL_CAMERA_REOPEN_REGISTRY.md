# Original camera-store discovery registry

`application/physical_camera_reopen_registry.py` supplies the bounded discovery
and selected-metadata guard for the [restart workflow](PHYSICAL_CAMERA_RESTART_IMPLEMENTATION.md).
It does not open M1, qualify a volume, enumerate devices, run a native helper,
read camera frames, pass a stage, clear quarantine or replay an operation.
The application must still use the actual `PhysicalCameraSession.refresh` and
original prerequisite readback before adopting the original store.

## API

```python
registry = PhysicalCameraReopenRegistry(
    workspace,
    current_launch_id="wizard-<32 lowercase hex>",
    source_sha256=original_current_workspace_hash,
)
snapshot = registry.discover(cancellation=stop, deadline_ns=original_deadline)
options = registry.choices()                 # opaque {value, label}; no default
preview = registry.preview(options[0]["value"])  # explicitly selected by operator
with registry.selected(
    preview["choice_id"], preview["discovery_sha256"],
    cancellation=stop, deadline_ns=original_open_deadline,
) as descriptor:
    # Application-owned original M1 refresh/readback; never initialize here.
    ...
# Only now may the application publish its independently verified original state.
```

Construction, `view`, `choices`, `preview`, descriptor decoding and `invalidate`
are pure/cached. Discovery is explicit, at most 30 seconds. Selected scope is
explicit, at most 120 seconds including the caller's M1/readback work. Both use
the original monotonic deadline; slow reads never renew it. Cancellation, clock
regression, source changes and changed choices fail closed. A successful selected
scope can be reverified explicitly; a failed scope revokes its choices. Caller
exceptions, including `KeyboardInterrupt`/`SystemExit`, retain their identity;
no partial operation is rewritten as success.

The trusted setup service can capture `registry.descriptor(choice_id)` **before**
entering the first scope, along with the independently retained descriptor hash
from the preview. This pure getter returns an exact detached immutable object.
After a cancelled/failed initial opening, a later operator-requested refresh can
use `registry.revalidate_original(descriptor, expected_descriptor_sha256,
cancellation=stop, deadline_ns=original_refresh_deadline)`. This takes the same
120-second bounded guard and before/after checks for that **one original** only.
It validates exact type, original digest, current launch/source and assigned
root; it never consults another choice, mints/revives a token, searches for a
replacement, opens M1 or repairs data. Registry view remains invalidated after
successful explicit revalidation. No automatic retry is added; service review
and original M1 verification remain necessary.

## Exact scope and binding

- Sole root: `workspace/software/runs/physical-camera-acquisition`.
- At most 32 immediate entries, 128 entries within each store, one immediate
  `cells` child, and one `onboarding-*` session. No recursive workspace or
  evidence search. Missing root remains missing; the registry creates nothing.
- Read exactly `durability-anchor.json`, the cell's `cell.json`, and the
  session's `header.json`, at most 16 KiB each. Check regular single-link files,
  no reparse/link ancestry, exact canonical bytes, file identities, byte counts,
  timestamps and hashes before/after. Identity numbers are retained as decimal
  text, not inaccurately rounded JavaScript numbers.
- Reuse the actual M1 cell, V2 header and durability report parsers. Match their
  source, cell, session, stage plan, qualification digest, directory name and
  original root hash. Historical qualification metadata is **not** a current
  volume self-test or hardware qualification.
- Selectable IDs must match the actual acquisition lineage:
  `SHA256(canonical_ASCII({launch: origin_launch, source: current_source}))`;
  cell uses the first 16 hex and session the next 32. The header/cell/anchor
  must bind `physical_camera_source_binding(current_source)`.
- A differing source binding is retained as `SOURCE_DRIFT_HELD`, without an
  opaque token. Those three metadata files do not retain the original raw
  workspace hash, so the registry does not invent one or validate a different
  source's lineage. It cannot authorize migration/relabeling of that store.

The immutable `PhysicalCameraStoreDescriptor` has `.payload` (canonical ASCII,
at most 32 KiB), `.descriptor_sha256`, `.to_dict()` (detached), `.directory`,
`.origin_launch_id`, `.cell_id`, `.session_id`, `.workspace_source_sha256`,
`.source_binding_sha256`, and `.header_sha256`. Its private document retains
the three complete metadata documents and their file/directory observations.
It is contextual data, not a permit or authenticated provenance claim. Only a
descriptor yielded by the current registry's exact selected scope should be
used by the application.

Selected scope pins the original store, session and cell ancestry, re-reads
immutable metadata before **and after** the caller's work, and rechecks source,
Stop and original deadline before release. It uses the existing explicit
directory WRITE-sharing compatibility mode for M1 child lease `ReplaceFileW`.
GENERIC_READ and omitted DELETE sharing continue to deny directory rename and
delete. This is not exclusion of writable directory handles, adversarial file
writer isolation, process containment or a power-loss guarantee. The existing
guard's cleanup/host limitations remain unchanged. Mutable journal/lease files
are deliberately not treated as immutable discovery metadata; M1 audits them.

## Cached presentation

`view()` schema `rocell.physical_camera_reopen_registry.v1` contains status,
current launch/source, nullable discovery hash, at most 32 store rows, at most
33 fixed-code issues, nullable invalidation reason, and constant false device
IO/physical authority. No path, raw JSON metadata, provider error, endpoint,
power observation or automatically selected choice is exposed in its rows.

Statuses are `NOT_DISCOVERED`, `DISCOVERED`, `HELD`, `INVALIDATED`. Initial and
invalidated states clear rows/issues/hash; held operations clear rows/hash and
retain fixed issues. Successful discovery can include valid choices and held
rows/issues simultaneously. `preview` adds the discovery/current launch/source
binding to one selectable row; a browser path is never an input.

## Verification

`tests/unit/test_physical_camera_reopen_registry.py` uses only its own temporary
metadata. Its anchor checks are explicitly modeled historical records, not
actual qualification. Tests forbid M1 initialization/open and process launch;
cover inert calls, canonical/hash/identity/domain/lineage mismatches, source
drift, ambiguity, bounds, cancellation, deadline expiry, defensive copies,
post-yield mutation and caller errors. A Windows-only test verifies own temporary
leaf/ancestor rename denial. Real original-store M1 refresh and restart UI
publication are separate application integration tests.
