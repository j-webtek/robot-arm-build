# Benign phone tap observer

## Purpose and limits

`software/tools/phone-tap-test.html` is a self-contained, offline test page for
observing input on a phone. It has no external assets, network requests, robot
commands or credentials. It is not an Android control service or a calibrated
board map. Browser/device compatibility and physical robot tapping remain untested.

It records only pointer-down, pointer-up, click and cancellation events in its
outlined test area during explicit capture. The blue 120-by-120 CSS-pixel target
is deliberately large. CSS pixels are not millimeters. Events outside the test
area, other applications and the operating system are not observed.

## Initial manual acceptance

1. Transfer the HTML file to the test phone using your normal local file transfer.
   Open it in a browser that executes local HTML. If your file viewer shows only
   source or a static preview, that is not a working test. Do not change browser
   security policies or expose the wizard's loopback server to the LAN.
2. Keep the phone stationary, with the full target visible. Use expected count 1.
3. Press **Start capture**, tap and release the center of the blue target once,
   then press **Stop capture**. This first check is manual, not robot-operated.
4. **Download JSON**, or copy the visible transcript if download is unavailable.
   Transfer it back to the computer. Keep it with the corresponding test notes.
5. In wizard Tasks, select **Review phone tap-test capture (no movement)**. Paste
   the JSON, preview the action and execute its reviewed ticket.
6. Confirm the Activity result and export diagnostics to the configured workspace
   folder. The supplied transcript and review are retained in the normal export.
7. Repeat with one deliberate tap outside the blue target but inside the outline.
   This should report `OUTSIDE_TARGET_INTERIOR`, not successful targeting.

No phone pairing or automatic upload is established by this offline workflow.
The JSON may be edited by its supplier; `isTrusted` claims are not authentication.
Do not copy sensitive text into the test transcript.

## Evaluation

The reviewer requires complete down → up → click sequences inside the target's
strict interior and exactly the requested number of taps. It rejects malformed,
oversized, nonfinite or out-of-viewport records. Missing/extra taps, overlap,
cancellation, untrusted events, unfinished gestures and interrupted captures fail
the observation check. Capture stops at 60 seconds or 32 events; resize, scroll,
window blur or hiding the page interrupts it. Restart after orientation changes.

`TAP_SEQUENCE_OBSERVED` means only that the supplied transcript matches the target
test. It never means that a robot caused the tap, that physical coordinates are
accurate, or that another phone app received input. A real browser check must
precede using the page in a robot trial.

## Integration progression

- First demonstrate manual success and deliberate failure on the actual phone.
- Once the installed tool and movement route are qualified, associate an explicit
  trial ID with the command export and the input capture; currently this is a
  recorded operator association, not an authenticated timing link.
- Keep phone orientation, viewport, zoom and fixture unchanged during that trial.
  Register the physical screen target separately; do not send CSS coordinates to
  the arm directly.
- Use one bounded approach/press/withdraw trial. A missing tap is a failed trial,
  not permission to press again automatically.
- Expand to finite repeats only after the individual movement and tap both pass.

Automated checks exercise the actual page handlers in an inert JavaScript DOM,
review rejection cases, wizard rendering and diagnostic exports in physical and
rehearsal modes. They do not substitute for Android/browser or robot testing.
