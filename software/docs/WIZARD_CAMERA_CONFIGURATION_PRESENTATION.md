# Camera configuration presentation

The Guided rehearsal browser and terminal views present one cached
`rocell.wizard_camera_configuration.v1` summary. Reading it does not probe,
capture, start a child, select a mode or apply controls. A missing summary stays
absent. Malformed, unknown, coerced or internally inconsistent fields produce a
withheld-summary warning instead of raw JSON or a successful verdict.

## Operator sequence and meaning

1. Explicitly run the registered rehearsal probe action when its stage permits
   it. The card distinguishes actual owned-process observations from modeled
   native cleanup. A complete probe is not a capture or a qualified camera.
2. Inspect every reported mode and all six electronic control identities.
   Unsupported formats/layouts remain held; unavailable controls have no
   invented range. The card shows ranges, steps, driver units, reported defaults,
   capability bits and current readback. Current flags `3` remain ambiguous.
3. Use the separate configuration action. Its mode field starts blank and uses
   the server's opaque occurrence ID, never a friendly name. Its finite fixture
   choices can be narrower than the card's format-contract checks. Control
   intents default to `unchanged`; displayed current numeric values are not
   implicit requests. Explicitly choose manual/auto before requesting a value.
4. Review the action preview and separately confirm execution. Staging retains
   immutable intent and a settings epoch; its `applied` value remains false.
   It does not start a camera campaign.
5. After a separately authorized finite capture and evidence verification,
   inspect requested versus observed settings. Manual values must match;
   automatic mode must read back automatic, but its observed value is not a
   fixed-value promise. Missing data or disagreement is displayed as held.

Every card retains `NOT_CONNECTED / NOT_QUALIFIED`. Capabilities are explicitly
modeled fixture values, not measured support from the purchased Arducam.
Focus and aperture remain manual physical adjustments. The card cannot
establish received-unit identity, driver compatibility, installed optics,
calibration, physical cleanup or motion authority. Source/process/capture
provenance verification belongs to the backend, not this structural renderer.

## Developer join and checks

Root service publishes `commissioning_rehearsal.camera_configuration` with
separate probe, capabilities, candidate and readback sections. The presentation
checks exact component schemas and cross-binding hashes before displaying
bounded escaped text. No raw endpoint, path, executable argument, process
output or timestamp is accepted. Existing camera-process/preview cards stay
separate. Generic action forms remain the only route to preview and execution.

`test_wizard_camera_configuration_ui.py` exercises both renderers, unknown
fields, bounds, ambiguous flags, unavailable controls, unsupported formats,
readback mismatches, no render dispatch, and actual pure producer output.
It also passes actual Arrival cached projections/dynamic field definitions
through both frontends. Those tests inject already-produced metadata into a
fresh service: they are not proof of an M1 transaction, child execution,
capture, physical observation or durable stage acceptance. Real process/store
coverage is tracked separately in the integration document.
