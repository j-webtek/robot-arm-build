# Keyboard input observer

## Purpose and limits

The local test pad supplies independent **input-event evidence**, separate from
arm endpoint telemetry. It checks whether a short expected lowercase sequence
produced matching key-down, text-input and key-release events.

It does not move the arm, authorize contact, correlate events to an arm request,
or identify whether a person or robot caused them. Browser `isTrusted` is retained
but is not authenticated proof of origin. The server describes the record as a
supplied browser transcript. A successful result means INPUT_MATCH_OBSERVED,
not ROBOT_PRESS_CONFIRMED. Android pairing/capture is not implemented here.

## Use from the wizard

1. Open **Task rehearsal → Open keyboard test pad**. It opens on the same local
   loopback service. Existing launch credentials stay in session storage; the
   page never opens the arm, camera or an operating-system input hook.
2. Set harmless expected text: start with `a`, then at most eight lowercase
   letters. Never enter passwords or other sensitive text.
3. Click **Start capture**. Only the dedicated test field is observed. For an
   initial manual check, press and release the expected key(s).
4. After releasing the key, click **Stop capture**. Inspect the transcript.
5. Click **Preview saving this capture**, review the action, then **Save reviewed
   capture**. This uses the wizard's existing prepare/execute ticket workflow.
6. Return to **Activity & results** to confirm processing, then use the usual
   diagnostic export action. The transcript and review are included in the
   assigned export folder. Submission is not proof that saving completed; check
   Activity after a network failure. Once submission is attempted, this page
   disables preparing or saving that capture again, even if the response is lost.
   Start a new capture only for a genuinely new observation, not to retry a save.
   This is a page-local duplicate guard, not server-wide deduplication of manually
   supplied transcripts.

If session storage is unavailable, the separate page cannot use the launch's
credentials. The transcript remains visible and can be supplied to the wizard's
**Review keyboard test-pad capture** action from the authenticated main page.

## What fails verification

- Missing, extra or wrong text.
- Missing key-up, unpaired release, duplicate down, held-key repeat or overlapping
  presses. The first workflow deliberately uses individual unmodified keys.
- Untrusted/script-generated events in the supplied transcript.
- Focus loss or interruption; modifiers, paste, composition and unsupported input.
- More than 64 events or a capture exceeding 60 seconds.

No global keyboard listener exists. No input is collected before Start or after
Stop. Paste/composition is prevented without retaining its text. Observing raw
events is separate from commanding movement; it cannot silently retry a press.

## Verification and remaining work

Automated tests exercise the actual JavaScript handlers with an inert DOM,
the collector's limits, server-side evaluation, loopback asset serving, wizard
service publication and diagnostic export in both modes. These tests do not
substitute for a manual real-browser/keyboard check.

The automated browser tool could not open the local QA wizard
(`ERR_BLOCKED_BY_CLIENT`); no real-browser validation is claimed. Handler tests
cover successful submission, lost execution response, repeated clicks and late
blur/stop events. A new explicit capture resets the page-local submission guard.

Next: perform that manual check, add explicit command/capture association when
motion is restored, then implement a separately paired benign Android tap target.
Do not expose the existing wizard on the LAN to make phone testing convenient;
its loopback access boundary remains unchanged.
