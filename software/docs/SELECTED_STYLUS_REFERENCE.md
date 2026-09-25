# Selected stylus reference

Recorded: 2026-09-17. Status: user-selected product; mounted tool uncalibrated.

For the attended open/place/close and measurement sequence, use
[the stylus loading procedure](STYLUS_LOADING_PROCEDURE.md). Its controller
prerequisite is not yet implemented on the installed r91 diagnostic image.

## Product

User-selected [Amazon ASIN B08Q7L85X2](https://www.amazon.com/dp/B08Q7L85X2).
The retrieved listing identifies an **OASO touchscreen stylus with disc tip and
magnetic cap** and advertises capacitive touchscreen compatibility. This is a
product claim, not proof of operation when held by a robot instead of a person.
No reliable engineering dimensions for barrel, disc, or working length were
established from the retrieved listing. Do not invent these dimensions.

## Effect on the existing simulation

Keep the current 100 mm negative hand-TCP-Z offset as an explicitly hypothetical
ghost-tool setting. It is NOT a verified dimension of this stylus. Selecting the
product does not change frozen geometry, existing export provenance, controller
correlation, or authorize a live contact trajectory.

Once mounted, record the full reference-to-contact-tip transform: XYZ offset and
orientation relative to the modeled hand TCP. Overall pen length alone cannot
provide this because insertion depth, adapter geometry and grip angle matter.
Record the exposed length, barrel diameter, disc diameter and contact deflection
as measured values when available. Re-run route screening after any tool change.

## Mounting and contact design

- Grip the barrel with a repeatable insertion stop and non-slip, non-crushing
  support; do not grip the movable disc or its stem. Remove the tip cap for use.
- Keep the disc attached for screen contact. Account for its footprint and
  articulation rather than treating it as a rigid mathematical point.
- Design limited axial compliance and bounded downstroke; this project has not
  established a safe contact force or tip force sensing.
- Keyboard suitability is unverified. A disc stylus is not a rated key-press
  actuator. If it catches, slips or flexes excessively, use a separate compliant
  keyboard tip and a separately calibrated tool profile.

## Small practical validation sequence (camera not required)

1. Confirm a manual tap works on the actual Android device in the tap-test page.
2. Hold the stylus in the intended fixture without a person's hand touching its
   barrel and repeat a gentle tap. Passive capacitive operation can depend on
   electrical coupling; do not assume hand-held success proves robot-held use.
   If it fails, investigate an appropriate robot-compatible tip/coupling design;
   do not improvise a connection to mains earth or the arm electronics.
3. Check repeatable retention and disc seating over the intended approach angles.
4. Measure the mounted tool transform, update a new tool-profile version, and
   rerun ghost geometry/interpolation checks with that transform.
5. Only then perform bounded single contacts, verifying actual key/tap events
   with the existing input observers. Joint feedback alone cannot confirm input.

This reference does not resolve the existing elbow-response discrepancy and
does not require the deferred camera to resume offline development.
