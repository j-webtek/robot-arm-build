# Vendor camera geometry

## `B0477.STEP`

- Download source: <https://www.arducam.com/downloads/3D_Model/B0477.STEP>
- Downloaded: 2026-09-06
- SHA-256: `f0202344106113492277220debdd35197a1f38667fbbbb172fecd024bc5567a0`
- Intended catalog item: Arducam B0477 / IMX283 USB 3 camera package

Important: the STEP file's own header names the assembly
`UVC3.0 (b0498).STEP`. Inspection also shows multiple optical components. It
is therefore a **vendor geometry proxy**, not proof that every solid represents
the delivered B0477 configuration. Use its nominal `38 x 38 x 25 mm` enclosure,
approximately `39.5 mm` lens envelope, and USB-side clearance only to create an
adjustable first-article holder. Do not derive a released mounting-hole thread,
usable thread depth, camera mass, centre of mass, delivered lens, or connector
bend requirement from this file.

Before installing the camera, compare the received enclosure and plug directly
against the printed fit gauge and holder. The cage must retain the enclosure on
four sides with a separate bolted keeper; it must not rely on the two small rear
holes or clamp the focus/iris rings.
