# Verified arrival with incomplete hold: reporting update

No hardware access or movement occurred. No deadlines, motion limits, candidate
values or admission rules changed.

## Behavior

The offline Wi-Fi roll reviewer now retains initial endpoint verification when
a subsequent passive hold fails. After export integrity and original-response
reconstruction, it reports:

- `endpoint_replayed: true` if the movement verdict independently replays.
- `hold_completed: false`, `failure_code: HOLD_INCOMPLETE` and
  `full_validation_success: false` for a failed/cancelled hold.
- Bounded fault category/phase metadata, successful-prefix sample count and a
  separately labeled `partial_hold_assessment`. It emits no sustained-band
  qualification for an incomplete hold, even if its prefix looks stable.
- No stitching of successful recovery samples after a fault into the same hold.
- Tampered exports, mismatched summaries or malformed evidence still raise.
- CLI exit remains 1. A partial hold is not a successful trial.

The session core now emits `LEG_REVIEW_FAILED` and a specific `HOLD_INCOMPLETE`
reason before stopping. It retains the reviewed failed leg and export reference,
without sending another command. Existing historical journals are not rewritten;
the old generic stopped reason remains part of their original record.

## Real export replay

Export: `wizard-20260917T032028360335Z-be9aaa7fb7de41809a84988617b7718b`.
Manifest file SHA-256:
`85970dc420e1e3dd40ea6526fcfd5e4eeaf8d4c463ae33758559c6251b0efb66`.

Independent replay preserves arrival at 1.142578111 degrees, command 0.85,
desired 1.25, error -0.107421889. The hold has 91 successful prefix readings over
26.303616 seconds, then TIMEOUT at REQUEST_SEND. Its partial reported pose was
unchanged, but its full hold remains incomplete. The session loader now returns
that structured failure instead of a generic exception. No failed evidence was
reclassified as a successful complete hold or added to validation counts.

## Verification and next step

54 focused tests passed across the export reviewer, finite session, block auditor
and wizard adapter. New coverage includes partial/empty prefixes, bounded failure
metadata, post-fault sample rejection, preserved endpoint verdicts, nonzero CLI
exit and no-next-command behavior. The real failed export and session loader were
also checked directly.

Next hardware action should be a fresh read-only health check. Any later probe
must be a new admitted trial, not resumption of the consumed incomplete sweep.
Choose the next experiment using the plateau and historical variability evidence;
do not silently replace the failed sample or relax the hold to claim completion.

## Fresh read-only check completed

Export `wizard-20260917T032517433736Z-9d5398b631464f9cbde8d6ed857046dc`
passed export integrity and original-response reconstruction. Manifest file
SHA-256: `7e640d13a6c7c6af4fdc275a2f3964f8c05b172351e07a90e82bc92269e080e6`.

There were 121 successful feedback responses over 35.003604 seconds, maximum
response gap 496.7844 ms. All six reported joints remained unchanged. Latest
reported roll was 1.142578111 degrees (`r=0.01994175` radians). No motion command
was sent. This confirms a clean recent observation window, not a resolved root
cause for the prior timeout or a guarantee about the next exchange.

The original interrupted hold and sweep remain incomplete. This later observation
is not appended to the old hold or counted as a second completed 0.85-degree probe.
Any further experiment needs a fresh baseline and new admission. A useful next
bounded trial is a separately recorded high-positioning/full-hold followed by a
new 0.85-degree characterization/full-hold, preserving the interrupted record.
