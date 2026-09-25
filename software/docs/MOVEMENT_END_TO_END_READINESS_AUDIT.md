# Movement campaign readiness audit

Date: 2026-09-13. Scope: current integration and remaining path to the original
movement-characterization playbook. This is not a completion certificate.

## Evidence collected this audit

- Re-read the playbook's phases, acceptance criteria, export requirements and
  handoff checklist. The original scope includes an actual qualified move,
  progressive finite physical trials and an evidence-backed settings report.
- Ran the planner, simulator, nominal geometry, controller/executor, timed and
  endpoint metrics, and full-window coverage test modules: **85 passed in 2.00s**.
  Result: `software/runs/movement-core-audit-20260913-01.xml`.
  These are unit regressions, not proof of physical accuracy or comprehensive
  satisfaction of every phase's acceptance criteria.
- Started the real physical-mode wizard with cell `UI-AUDIT-NO-HARDWARE` and
  inspected its browser accessibility state. The local service connected; arm
  and camera were NOT CONNECTED; activation was independently gated; all physical
  stages remained pending. No action was submitted.
- Stopped that exact server process using its terminal handle and observed exit.
  No launch credentials are retained in this document.
- Full browser form interaction remains unverified. The available browser surface
  returned page state but no documented interaction API; no guessed input methods
  or alternative device actions were used. Modeled-DOM tests are separate evidence.

## Current end-to-end status

| Requirement | Current evidence | Remaining qualification |
| --- | --- | --- |
| Bounded full-window telemetry, finite planning and deterministic simulations | Current core unit regressions pass; historical reanalysis is linked from the playbook | Preserve coverage/uncertainty limits in actual trial exports |
| Wizard draft, reviews and attachment | Implemented ticketed actions; recent service and modeled-renderer tests | Full actual browser interaction with clearly synthetic evidence in an incapable test environment |
| Source/identity-bound one-use executor | Implemented separately from read-only capture; boundary tests exist | Real key readiness, actual original records, current operator/clearance evidence and live timing qualification |
| One physically qualified slow move | Not established | Actual command plus retained telemetry and independent observation of the same attempt |
| Progressive physical pose/speed campaign | Not established | Qualification, reviewed finite subsets, inspection between expansions and retained failures |
| Evidence-backed settings recommendation | No physical basis established | Sufficient qualified repeats, uncertainty comparison and explicit applicability limits |

## Important software gap: post-run qualification

Separate timing audit: all six load-sensitive pipeline tests passed in 20.48
seconds. Report: `software/runs/first-motion-timing-audit-20260913-01.xml`.
Preparation-only samples reached the incapable dispatch boundary in 1710.35,
1943.05 and 1961.80 ms. Parent-prelaunch variants completed in 3610.37, 3674.50
and 3719.87 ms, including deliberate backend failure/result retention. The
historical property name `pre_dispatch_elapsed_ms` describes whole tested-path
elapsed time for those variants, not just the first prelaunch admission interval.
All samples reached their intended incapable boundary without a native launch.

The six pytest warnings concern `record_property` with xunit2 output; the timing
properties were present and read back from the XML. These measurements use
synthetic keys and incapable process backends and do not include qualified real
DPAPI key loading, native process creation or USB I/O. Physical dispatch remains
paused pending independent measurements/clearance and current operator presence.

Review UI/regression checkpoint: the qualification decision form now displays the
selected assessment's holds, exact evidence hashes, reported observation and
limitations as text. It explicitly labels the display cached, explains execution
revalidation, and does not submit or change review decisions when selection changes.
The shipped renderer is tested in the modeled DOM; actual browser form interaction
is still not claimed.

The broader commissioning suite passed **480 tests in 90.59 seconds**:
`software/runs/first-motion-full-regression-20260913-04.xml`. This run selected all
`test_first_motion*.py` and `test_wizard_first_motion*.py` unit modules except the
separately load-sensitive pipeline timing module. It is not a whole-repository
test run or native live-timing qualification. No device was opened by this work.
Independent wrist-angle/radius measurements with uncertainty and actual reviewed
clearance remain required before the physical stage; old photos/permissions do
not supply them. Real live qualification and the finite campaign remain incomplete.

Review export update: wizard diagnostics now reserve a dedicated
`attachment-first-motion-qualification.json` bundle before ordinary result
rotation. Successful review receipts are held separately (bounded to sixteen per
session); their exact assessment and decision originals are re-read, hash-checked
and structurally reconstructed at export. Shared assessment bytes are deduplicated.
The bounded base64 representation preserves originals through ordinary diagnostic
redaction. Complete-bundle limits fail explicitly instead of silently truncating.

66 review/export/service tests passed in 15.09 seconds:
`software/runs/first-motion-review-export-20260913-01.xml`. The synthetic wizard
observation -> assessment -> acceptance -> general-export path verifies the export
manifest and exact decoded assessment/decision bytes and hashes. Altered decision
flags are rejected even with a substituted claimed digest. Existing native-log
export and service tests pass. No real qualification, motion or observer identity
authentication is established. Actual browser interaction and live qualification
remain outstanding; the original finite campaign/settings report is unfinished.

Wizard decision update: `review_first_motion_qualification` now selects a
successful same-session assessment, re-reads its hashed original, resolves its
retained observation receipt and reconstructs native/observer evidence before
and after recording the decision. The wizard supplies its own outcome and
supervisor receipt; no browser-provided assessment JSON, process facts or hashes
are accepted. UNKNOWN is the default decision and all four review checkboxes
start unchecked. A HELD assessment cannot be accepted even when boxes are checked.

122 wizard/decision/catalog/service tests passed in 12.10 seconds:
`software/runs/first-motion-review-wizard-20260913-01.xml`. Synthetic fixtures cover
the observation -> assessment -> explicit review path using actual original-file
loaders, recomputed telemetry and receipt association. Held acceptance fails,
altered assessment files fail, and accepted synthetic review records retain
matching hashes without changing attempt identity or granting motion authority.
No actual independent review or live qualification occurred. Review-original
export coverage and full browser interaction remain to verify before real use.

Decision-layer update: `application/first_motion_qualification_decision.py` now
records UNKNOWN, REJECT or ACCEPT_FUNCTIONAL_RESPONSE against an exact canonical
assessment. Acceptance requires a review-ready, hold-free assessment plus explicit
observer-identity, method-compliance, observation-timing and discrepancy review
checks and a bounded rationale. These are reviewer declarations, not authenticated
identity or calibrated physical measurement. No decision grants another move.

The trusted caller must reconstruct the assessment before and after immutable
publication. Changed evidence prevents a successful receipt; partially published
originals remain for diagnosis and are not automatically adopted. Assessment and
decision originals have exclusive operation-relative names and hashes. The
decision's scope is one retained wrist functional response, not other poses,
speeds, payloads, physical stopping or calibrated accuracy.

24 decision/correlation/wizard-assessment tests passed in 3.88 seconds:
`software/runs/first-motion-qualification-decision-20260913-01.xml`. Synthetic
tests cover all three decisions, held-assessment acceptance rejection, incomplete
or malformed checks, repeat publication and evidence changes before/after writes.
Wizard decision selection/revalidation wiring and real review remain outstanding.

Wizard assessment update: `assess_first_motion_qualification` now selects a
successful retained observation from the current session, checks its request and
result against the service-owned outcome, and invokes the actual native/observer
correlation with that outcome's supervisor receipt. The assessment is saved as an
exclusive operation-relative original with a SHA-256 in the result. A successful
assessment action can report HELD; operation success means assessment retention,
not physical qualification. Cancellation/time limits are checked before and after
correlation. No attachment or attempt identity is changed by assessment.

71 assessment/wizard/catalog tests passed in 4.18 seconds:
`software/runs/first-motion-assessment-wizard-20260913-01.xml`. Tests exercise the
ticketed observation-to-assessment flow using synthetic native originals and
supervisor receipts, with real readback/analysis and observation loaders. Missing
ownership and no observed movement stay HELD; changed child streams fail; retained
assessment hashes are verified. No actual hardware or physical qualification is
represented by these fixtures. Explicit qualification-decision recording and the
full browser interaction check remain unfinished.

Correlation update: `application/first_motion_qualification.py` now combines
unchanged observation originals with native readback and an optional exact
host-owned supervisor receipt. Readback compares attempt/wire identity and both
streams, checks successful process/input/cleanup facts, and rechecks the saved
worker claim against the supervisor's process ID, runtime and finish time.
Missing ownership, cleanup uncertainty, unsuitable telemetry, an unexpected
observation or partial/unknown observation coverage keeps the assessment HELD.
Mismatched streams or worker identity are rejected outright.

19 correlation/readback/publication tests passed in 4.76 seconds:
`software/runs/first-motion-qualification-assessment-20260913-01.xml`. Synthetic
native publications and supervisor receipts are used; this is not actual process
or physical qualification. A ready assessment is labeled
`READY_FOR_EXPLICIT_QUALIFICATION_REVIEW`; every physical-verification and campaign
advancement flag remains false. Explicit review still must address observer
identity, method compliance and timing, and must not generalize a wrist response
to calibrated accuracy or other poses/speeds. Wizard assessment/decision wiring
and the actual live qualification remain outstanding.

Native readback update: `application/first_motion_result_readback.py` now verifies
the host-selected result digest, reads fixed attempt-relative request/stdout/stderr
originals, checks their wrapper sizes/hashes/filenames, validates the exact native
request and reconstructs accepted native summaries using the existing full trial
and raw-telemetry analysis. Modified displayed metrics cannot substitute for the
original streams. Rejected results are retained as rejected and are not rescued
by opportunistic parsing. Process-completion uncertainty cannot become review-ready.

26 readback/result-review/publication tests passed in 4.13 seconds:
`software/runs/first-motion-readback-20260913-01.xml`. Tests use synthetic native
publications and cover altered streams, summaries, digests, request mismatch,
rejected child output and unconfirmed process completion. The reader explicitly
does not reauthenticate a historical parent or verify physical movement. Its
`telemetry_ready_for_review` is a data-consistency prerequisite only. Next combine
this result with the unchanged observation original and current host-owned process
association before accepting any explicit qualification decision.

Export update: general wizard exports now reserve a dedicated
`attachment-first-motion-observations.json` bundle before ordinary result rotation.
It contains hash-addressed original request/result/observation bytes encoded in
bounded base64 chunks, plus receipt associations. Identical requests/results are
deduplicated. Export revalidates the retained observation and result; a changed
original or exceeded budget fails rather than presenting a truncated bundle as
complete. Up to sixteen observations are retained per session independently of
ordinary result-history rotation. The single bundle is capped at 900 KiB and the
existing whole-export limits still apply. Partial original publications remain
diagnostic files, not successful observation receipts or qualification evidence.

74 observation/export/service tests passed in 10.48 seconds:
`software/runs/first-motion-observation-export-20260913-02.xml`. Tests verify the
actual general export manifest, decode preserved original bytes and recompute
their hashes for small and approximately 240 KiB synthetic result documents.
The bundle helper separately preserves the full 256 KiB result limit, deduplicates
shared originals and rejects changed files. No actual physical observation or
qualification decision was created. This closes the observation export round-trip
gap noted below; full browser interaction and qualification remain incomplete.

Wizard integration update: `record_first_motion_observation` now offers this
session's retained commissioning outcome, bound to attempt ID and result digest.
Execution compares the saved result's exact bytes with the host-owned outcome,
reads the fixed final-click original, validates the request and attempt, then
records the observer fields separately. The browser supplies no result JSON,
request, arbitrary path, claimed process facts or qualification flags. UNKNOWN
is the default movement outcome and observed coverage. Partial publication or
missing retained results remain diagnostic failures, not movement permission.

76 observation/service/run/export regression tests passed in 10.39 seconds:
`software/runs/first-motion-observation-integration-20260913-01.xml`. New tests
inject an explicitly synthetic terminal outcome (no process/hardware) and verify
actual retained-file correlation, changed-result/request rejection and unchanged
attempt identity. The existing export tests pass, but this run does not establish
a full observation-original export round trip or actual browser interaction.
The separate qualification decision layer remains unfinished.

Implementation update: `application/first_motion_observation.py` now provides
bounded, immutable recording and readback of a self-reported observation linked
to exact request/result hashes and the request's observation-method reference.
It preserves outcome, coverage, rationale and limitations, and distinguishes host
recording time from unknown observation time. Expected, absent, wrong and unknown
movement remain retainable, including observations associated with rejected
native results. It checks correlation, not full native-result validity or an
observer's identity. A supplied method label is not proof that the planned method
was followed. Host receipt selection and native-result verification remain required.

The loader reconstructs the exact original and rejects changed declarations,
different attempts and altered result bytes. It does not renew an expired request
or modify any result. Every physical-verification/advancement flag remains false.
36 observation/result-review/publication tests passed in 3.05 seconds:
`software/runs/first-motion-observation-20260913-01.xml`. All observations in these
tests are synthetic. Wizard intake and the separate qualification decision layer
remain to be implemented; this update is not physical qualification.

Inspection of `application/first_motion_result_review.py` confirms that consistent
data is explicitly returned as `TRIAL_DATA_CONSISTENT_NOT_PHYSICALLY_QUALIFIED`.
Inspection of `providers/windows/first_motion_result_publication.py` confirms that
even a retained result has `physical_movement_verified`, `physical_stop_verified`
and `campaign_advance_allowed` set false. This is correct; those flags must not be
changed merely because a command or telemetry converged.

The next qualification layer must correlate a separately retained independent
observation with the exact attempt/request and immutable telemetry result. It must:

1. Retain the observer's identity, method, observation outcome, timing limitations
   and discrepancies without rewriting the command or raw telemetry originals.
2. Reject attaching an observation to a different attempt or altered result.
3. Keep NO MOVEMENT, WRONG MOVEMENT, UNKNOWN, faults and incomplete capture visible
   and prevent campaign advancement on those outcomes.
4. Separate self-reported observation, independently calibrated accuracy and
   physical stop/power state. None is automatically inferred from another.
5. Produce a distinct reviewed qualification decision, not mutate the executor's
   diagnostic-only output. A successful decision must not authorize a next trial
   without that trial's own current checks and one-use permit.
6. Exercise this path using incapable synthetic fixtures before accepting real
   observations. No actual physical observation may be generated by simulation.

## Physical evidence still required

Requirements update, 2026-09-13: the paragraph below describes the existing
measured-profile gate, not a continuing demand for the user to take precision
measurements for basic functionality. The user selected a lower-friction
[observational bench workflow](OBSERVATIONAL_BENCH_TESTING.md). Implement that
explicit profile before using it for dispatch; do not fabricate measured records.

The current record does not supply independently measured wrist starting-angle
bounds and distal-radius uncertainty, a verified complete swept/gravity-drop
clearance basis, or all actual installed-unit/controller/supporting reviews.
The earlier read-only host key check reported no configured private review key;
this audit did not provision or recheck it. Do not treat that historical check as
a new current observation. Old photographs and blanket permissions do not provide
the missing measurements or prove present operator attendance.

Keep physical dispatch paused until these requirements are satisfied. Continue
the independent-observation/qualification software and full-flow verification
without claiming that passing more simulation tests completes the live campaign.
