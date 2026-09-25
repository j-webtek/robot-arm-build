# Physical camera setup presentation

The existing Camera page and terminal wizard expose the same cached
`physical_camera_setup` projection. The server owns the explicit actions:
`physical_camera_initialize`, `physical_camera_refresh`, and
`physical_camera_prerequisites`. Displaying status never invokes them, reads an
M1 store, queries devices, or runs a provider.

## Restart continuity

The v2 presentation additionally supports the server's `physical_camera_discover`
and `physical_camera_reopen` actions. The existing generic action form accepts an
opaque discovery choice and an operator label; there is no raw path field,
automatic choice, scan, open or replay. Discovery reports bounded metadata, not
storage qualification. A source-matched choice is only eligible for an explicit
recheck. Source-drift stores have no selectable token. Invalid or ambiguous
metadata is shown as a hold, without exposing arbitrary entry names.

`launch_session_id` names the current application launch. `origin_launch_id`
must match the original session's storage binding. Reopening preserves that
original cell, session, source and launch rather than creating a replacement.
Discovery's list is not the adopted session; only the separately audited session
panel describes current storage attachment.

`requirements_provenance` distinguishes no visible report (`NONE`), requirements
from the current launch's original store (`CURRENT_LAUNCH_ORIGINAL`), and an
original context reopened by another launch (`REOPENED_ORIGINAL_CONTEXT`). The
last case is labeled historical even after successful CURRENT publication.
Retained metadata hashes are not new observations; no camera configuration,
frame, connection or received-unit qualification is restored by this display.
Pending and historical publication hide the checklist and use provenance NONE.

Exact v1 exported snapshots remain readable. They are labeled legacy records;
the interface does not invent a separate current launch or a restart adoption
that the older schema did not record.

The original binding may already be selected when its reopen audit fails. The
caption therefore says selected for reopening, not successfully adopted; audit
state and publication must be read separately. Discovery choices are also
withheld until the explicit discovery result's completion has been published.

## Read the two kinds of progress separately

The camera-only session panel shows its assigned original directory, launch,
source, cell and session bindings. Its retained M1 verification describes
Windows/NTFS storage checks, ledger heads, quarantine, unresolved attempts and
active or stale leases. The display calls the M1 storage allowance
`storage_prechecks_clear_only`: it is never camera, arm, power or motion
permission. Absolute nanosecond timestamps are not presented as exact browser
values or freshness proof.

The panel also shows the original session's 15 recorded stage states. These
are distinct from the top-level physical-progress checklist. Initialization
starts every stage PENDING. Requirements collection may record
WAITING_OPERATOR at stage 1, but it does not assess, review or pass that stage.
Stage-row evidence-reference counts are not the full retained evidence inventory
and do not imply that an intake checklist has been reviewed.

`CURRENT` publication means that a storage/report result was published. It does
not mean physical-stage PASS, current connection, native runtime admission or
received-hardware qualification. Refresh audits the same original store; it
does not repair missing state, clear quarantine, initialize a replacement or
replay an operation. Holds and possible partial stores remain explicit.

## Use requirements as questions, not answers

The stage 1–4 requirements card is generated from four retained controlled source
files. It displays their relative paths, byte counts and hashes without loading
them from the browser. The card contains:

- 17 required intake records with original units, candidate values, template
  status and notes. Every observation remains UNKNOWN, not a copied nominal
  dimension. Required evidence includes the observed value, method, time,
  operator, evidence references and uncertainty or limitations.
- INT-005 flatness: measurement and evidence are required at intake; acceptance
  is deferred to `noncontact_acceptance` until `TARGET_ACCURACY_BUDGET_CLOSED`.
  A completed measurement does not by itself accept the limit.
- Five still-open blocking hazards, their required controls and evidence.
- Eight configuration dependencies, all UNMEASURED with no epoch values.
- Optional retained endpoint metadata and a separate source-only preflight
  report, neither of which establishes received-unit or canonical acceptance.

`DISCONNECTED_REQUIRED` is a requirement. Observed power remains UNKNOWN.
There are no pre-checked approvals, measurement-entry substitutes, connect
buttons or physical release controls in this requirements presentation.

Pending or historical outer publication withholds current prerequisite details.
Original records remain available through explicit diagnostic result/export
workflows. Invalid schemas, invented measured values, coerced flags, unknown
stage states and changed INT-005 acceptance rules are withheld rather than
displayed as trusted setup progress.

## Test boundary

`test_wizard_physical_camera_setup_ui.py` exercises actual fixed-file prerequisite
producers and the actual inert setup constructor against both frontends. Its
storage-ready examples use real M1 serialization with explicitly modeled ledger
facts; those tests are not NTFS qualification or received-hardware evidence.
The separate public setup integration smoke supplies actual M1 initialization,
collection, readback, refresh and export verification.

`test_wizard_physical_camera_restart_ui.py` joins the real discovery registry and
setup service to both renderers using strictly typed modeled metadata files.
These files do not establish NTFS qualification. The test forbids M1 opening and
initialization, and models only the outer completion callback. It verifies
source-drift holds, current/origin binding, publication suppression, bounded
schema rejection, and explicit preview without dispatch.

An additional optional regression reads the September 8 source-frozen public
export directly into both interfaces. Its original CURRENT snapshot has stage 1
WAITING_OPERATOR, 14 PENDING stages, and the actual unassessed requirements.
Two display-only variants verify that pending or historical publication withholds
the current checklist. These checks never recreate the store, fetch a full
operation automatically, or replay any action. The test skips on checkouts that
do not contain this untracked local diagnostic export.
