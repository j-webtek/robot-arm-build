# Owned-arm controller resolution trace display

The existing contained feedback card accepts the producer's compact owned
summary v2 and its bounded, versioned `resolution` summary. It does not parse
raw trace records, acquire metadata, compare controller properties, re-run a
worker, or grant a launch/release capability.

PRE_OPEN and PRE_WRITE are shown independently. Each displays whether an
acquisition snapshot and a metadata-comparison report were retained, their
hashes, the retained boundary verdict, and a fixed refusal code when present.
A null hash means that evidence was not retained; it is not an invented
acquisition failure, successful comparison, or reason to retry. The second
boundary cannot follow a held first boundary in a worker-bound summary.

Legacy owned summary v1 remains unchanged and renders as historical
NOT_RETAINED. A current v2 summary with no parsed trace is separately marked
NOT_RETAINED; it cannot claim complete evidence. Neither case triggers replay.

Synthetic acquisitions exercise software only. Metadata checks do not establish
atomic COM-to-handle identity, verify a USB serial descriptor, or observe the
received model, firmware, boot behavior or power. Process containment, serial
validity, native cleanup and independent synthetic power observations keep their
existing separate meanings. Connection and physical qualification remain false.

The focused tests are `test_wizard_arm_resolution_ui.py`. Fake-DOM and terminal
checks use cached projections, not a real browser, native device or admission
test. Full retained diagnostics and the backend's pure verifier remain the
authoritative record; display validation does not replace them.

The producer crosscheck also exercises the actual metadata acquirer/parser,
resolver, non-purging owner and feedback worker against sealed in-memory APIs,
then displays the resulting codec summaries. OS process observations in that
fixture are explicitly modeled. Nominal, pre-open identity change, pre-write
identity change, malformed metadata and unchanged legacy records are covered.
DLL loading and real process creation are forbidden while producing those
fixtures. The browser harness subsequently runs Node with only a cached
`GET /api/view` response; it is not a real-browser or hardware qualification test.

Reproduce the bounded presentation checks from the workspace root:

```powershell
.venv/Scripts/python.exe -m pytest software/tests/unit/test_wizard_arm_resolution_ui.py software/tests/unit/test_wizard_owned_arm_feedback_ui.py -q -k 'not actual_owned_child'
```
