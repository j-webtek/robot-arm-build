# Camera helper inspection and review presentation

The Camera page places **Camera metadata helper inspection & review** between
generic camera candidate review and native endpoint enrollment. The terminal
shows the same Camera-specific section. The card is read-only; its presence
does not inspect, hash, install, register or launch a helper.

## Operator sequence

1. Start with the fixed catalogue shown by the workbench. Physical startup is
   unregistered. No helper path, executable picker, installation command or
   catalogue selection is accepted through the UI.
2. Choose the explicit helper inspection action, enter an operator label and
   affirm metadata-only consent. In rehearsal, select nominal, missing-helper
   or hash-drift: these are visibly incapable synthetic inspections, not
   observations of installed files. Preview and execute are separate steps.
3. Read the retained inspection status, catalogue/report/source references and
   blockers. Missing, changed, unsafe or unreadable files remain held. Their
   summary does not present an expected helper hash as observed file content.
4. A different reviewer label may explicitly review the exact retained report,
   again with metadata-only consent and separate preview/execute. Distinct labels
   are diagnostic audit labels, not authentication or proof that two independent
   people performed the work. A held acknowledgment does not repair or install
   files and cannot register the helper.
5. Eligible registration enables only separately authorized `inventory` and
   `identity` metadata operations. Continue with generic camera review and native
   endpoint enrollment as required by the current action holds. No native lookup
   runs as a consequence of simply viewing the registered state.

Both interfaces always preserve **camera NOT_CONNECTED**, **camera NOT_QUALIFIED**,
`probe_allowed: false`, `capture_allowed: false` and zero physical authority.
Matching catalogue files does not establish current full-build provenance, a
trusted software release, qualified driver/process containment, received-unit
identity or permission to capture. Source activation, robot power, movement and
contact are outside this registration.

## State and validation

`NO_INSPECTION` has no retained inspection or review. `INSPECTION_RETAINED` may
contain a matching or failed inspection. `METADATA_HELPER_REGISTERED` requires
an eligible matching inspection and a registration digest from explicit review;
`REVIEW_HELD` keeps an ineligible inspection and no registration digest.
`INVALIDATED` clears both. Resetting review can preserve the inspection but never
restores the old review automatically.

The exact `rocell.wizard_camera_helper_registration.v1` display contract binds
the inspection provenance to rehearsal or workspace-file-inspection mode, checks
all authority flags, restricts allowed operations and requires distinct labels
and both operation references. It permits only the four closed inspection
statuses, 128 UTF-8 bytes per displayed identifier/label, and 32 unique blocker
codes per list. Unknown fields, stale state, oversized data or authority-bearing
claims produce a readable unverified message; the card does not expand raw
paths or silently truncate a list. Complete operation evidence remains separate
and available through the existing diagnostics/export flow.

The presentation tests cover all states, held/missing/drift outcomes, explicit
consent, distinct labels, exact schema and size limits. Producer-to-UI tests use
the actual incapable inspector, registration state and public Arrival actions;
physical startup tests forbid inspection/provider construction during status
reads. None of this test evidence is physical camera acceptance.
