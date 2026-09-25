# Physical camera presentation and operator boundaries

The existing Camera page and terminal wizard render the same cached
`physical_camera` projection. This is not a second camera application or a new
device dispatcher. Opening the wizard, visiting a page, and displaying a report
do not query metadata, launch a helper, change a setting, or capture an image.
Explicit action preparation may check current source files; device-inert does
not mean all preparation is filesystem-I/O-free.

## What the operator can understand now

- **Reviewed endpoint metadata:** hashes identify the retained endpoint and
  metadata review, without exposing a symbolic link, raw port, or camera index.
  These are not received-model, USB 3 topology, firmware, or persistent-unit
  qualifications.
- **Separate probe and capture runtimes:** the fixed development candidates are
  shown independently, with dormant status and disabled dispatch. Candidate
  hashes do not mean their installed files were inspected or their drivers were
  qualified. Metadata-helper registration permits neither probe nor capture.
- **Explicit planning:** a completed `physical_camera_plan` action can publish
  an intent while acquisition remains `HELD` and `PREPARED_NOT_ADMITTED`.
  `CURRENT` publication identifies the current plan/report, not a connection,
  frame, passed canonical stage, or physical release.
- **Reported support, intent, and readback:** the presentation supports the
  distinct physical capability/configuration/readback schemas. Modes remain
  opaque choices; unsupported layouts stay held. Six possible electronic
  controls retain their reported ranges, steps, units, defaults, supported
  flags, and current flags. Ambiguous flags are not converted into a selection.
  Immutable settings intent is explicitly **not applied**. Requested values,
  reported readback, process cleanup, native cleanup, and unknown final power
  remain separate. Manual lens focus and aperture need physical adjustment.
- **Last captured frame, not live video:** the current implementation starts
  with no physical frame. A future frame publication must carry independently
  verified pixel, manifest, endpoint, settings, attempt, and capture-evidence
  references. The browser fetches only the already cached image endpoint after
  these references agree with a current publication. Pending, historical, or
  inconsistent publication is withheld; there is no automatic recapture.

The action forms remain server-owned. No new custom connect button, arbitrary
endpoint/path field, automatic mode selection, checked-by-default activation
consent, or physical gate override is introduced by this presentation.

## Fault investigation

The dedicated retained fault card accepts only
`rocell.camera_fault_diagnostic.v1`, either from the cached rehearsal sibling,
the optional physical-camera fault field, or the named
`retained-incapable-owned-camera-diagnostics` operation step. It does not search
arbitrary JSON for apparent errors. Fixed categories distinguish a reported
settings rejection from timeout, cancellation, unconfirmed cleanup, and missing
retained evidence. A reported rejection is not an invented observed value.

The card is explicitly historical. Even `NO_REPORTED_FAULT` grants no current
success, retry, same-attempt replay, quarantine clearing, or physical authority.
Malformed sidecars are withheld from both the card and the generic display of
that named step. This display filtering does not mutate private evidence or its
exported record. Use explicit diagnostic result loading and the assigned-folder
export workflow to investigate a failure before considering a new action.

## Verification scope

`test_wizard_physical_camera_ui.py` exercises real pure capability/intent/readback
and fault producers, plus actual planning-service state transitions, against
both renderers. Native-shaped observations in these tests are modeled codec
fixtures, not executed processes or received-camera observations. Tests check
malformed schemas, coerced booleans/integers, unsupported modes, ambiguous flags,
binding drift, readback mismatches, historical images, bounded cached-image GETs,
explicit result retrieval, and no render-triggered action dispatch.

The UI validates bounded presentation contracts, not the integrity or authority
of the underlying M1 evidence. Storage qualification and complete diagnostic
records never substitute for the separately required physical release gates.
