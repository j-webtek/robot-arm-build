# Preserved arm-resolution result-publication failure

Date: 2026-09-08. This records the first full public run of the new contained
metadata-resolution composition. It is a hardware-incapable development test,
not an incident involving a powered robot or physical serial connection.

## Original evidence

- Source: `3e993f36912ade530d1988e5288262311ac2bf614655db4bd6e513ee905e3a63`.
- Rehearsal: `rehearsal-3f2f7a2f990845d4b6162ae15c60d6e8`.
- Original store: `software/runs/wizard-rehearsal/wizard-c109d9408ecb491792b51ab21d43b121`.
- Action: `operation-a7660b8d0a1240af80c2a16250a1035a`.
- Attempt: `attempt-1d9ca4eec0b740f1ba7b5140043e9a8a`.
- Full campaign SHA-256: `2bcb6133088482b65f071f704944b7afa1353d31863400243293c1c24c705947`.
- Owned evidence SHA-256: `236a14d6e04cf8f92666e8ee6f552acfdcc8ffb2cea784cce3beefc113b27d6c`.
- Complete trace SHA-256: `d1552566d2d19da5c13244cb991bf032098373aa29312768576d833761c8c78e`.
- Failure export: `software/runs/wizard-exports/wizard-20260908T181814762746Z-f7a23c5da10f4db5891666d48c51cf47`.
- Verified export manifest SHA-256: `dd9d2cf6317fa61e5ae3e66d4ee779494ba90baed9ce093c85bdc5af7b24a900`.

The original action and campaign were not replayed, the store was not rewritten,
and no source fingerprint or approval was migrated. This is not the earlier
feedback-timeout/quarantine incident. This attempt's inner coordinator result
was `SEALED_KNOWN`, with `quarantine_latched=false`; its outer UI action failed.

## Layered outcome and cause

The public setup path completed eleven reviewed prerequisite stages and
reopened the original saved records before the arm attempt. The actual owned
child then performed both modeled Windows metadata acquisitions/resolutions,
one fixed T105 exchange and clean process/serial cleanup. The coordinator saved
the full 78,416-byte campaign and returned its known synthetic result.

Arrival rejected the ordinary worker result with `RESULT_RETENTION_LIMIT`.
The newly embedded full trace was nested underneath `steps → report →
controller_resolution → trace → attempts → snapshot/...`, exceeding the generic
result sanitizer's existing depth limit. Neither the 48 KiB child result cap
nor the 128 KiB owned evidence cap failed. Do not increase those limits or the
generic nesting limit to hide an application composition error.

The failure export succeeded and included the 23,786-byte dedicated connection
attachment with the full trace. The first implementation nevertheless labeled
that export `CURRENT_REHEARSAL_DIAGNOSTIC`, because current-card eligibility
checked completion-log persistence but not a failed outer disposition. That
label is preserved in the original export as evidence of the presentation bug;
it is not a claim of successful outer publication or physical qualification.

## Repair

`retained_feedback_diagnostics(include_resolution_trace=False)` now supplies
ordinary worker results with the compact trace status/hash and an explicit
`FULL_TRACE_IN_DEDICATED_EXPORT` label. Its default cached getter retains the
complete trace for the separate bounded export. No original metadata is trimmed
or altered, and no provider is rerun by either read.

The public view also suppresses the current arm card after the latest relevant
action fails, times out or is cancelled. Dedicated diagnostics remain available
as `HISTORICAL_HELD`. A later explicitly verified original-store reopen has its
own publication result; it does not imply permission to repeat the campaign.

A regression exercises the actual sealed CM acquisition/resolution/worker trace
through the compact ordinary wrapper and the real dedicated exporter. Existing
source/Stop/log holds and retained-history rotation checks remain enforced.

The separate historical request.v1 repair accepts its original exact untagged
operation only when a strictly decoded retained v1 request establishes that
version. It rejects partial/conflicting tags and never re-admits old execution.
This is unrelated to the nesting failure and does not change original records.

Follow the [current workflow and verification record](ARM_CONNECTION_RESOLUTION_WORKFLOW.md)
for the new-source acceptance run. Do not count this failed public run as a
successful end-to-end onboarding test.
