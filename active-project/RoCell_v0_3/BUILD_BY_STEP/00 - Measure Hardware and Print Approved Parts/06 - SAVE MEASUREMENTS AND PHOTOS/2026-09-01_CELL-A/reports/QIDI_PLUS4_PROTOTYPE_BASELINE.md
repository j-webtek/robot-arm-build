# QIDI Plus4 prototype baseline

Recorded: 2026-09-01  
Operator: Jack  
Build ID: `2026-09-01_CELL-A`

This is a simplified prototype-build record. It records fixed manufacturer data from official QIDI sources and the operator's confirmation that the printer is fully updated and its basic printer qualification has been completed. Unit serial number, individual PETG spool lot, and photographic machine-travel evidence are intentionally not tracked for this prototype build.

## Manufacturer baseline

- Printer: QIDI Plus4.
- Nominal print volume: 305 x 305 x 280 mm.
- Project protected print envelope: 295 x 295 x 275 mm. This is an internal 5 mm-per-edge design margin within the manufacturer volume, not a separate QIDI claim.
- Supplied build surface: dual-sided textured PEI plate over a 6 mm aluminum heated-bed substrate.
- Standard nozzle: 0.4 mm bimetal nozzle; 0.2, 0.6, and 0.8 mm are optional.
- Filament diameter: 1.75 mm.
- PETG is listed by QIDI as a supported material.
- Slicer baseline: QIDI Studio v02.07.02.10, the latest official release found on the record date.
- Firmware baseline: Plus4 v1.7.1, the latest official release found on the record date.

Official sources:

- QIDI Plus4 technical specifications: https://us.qidi3d.com/pages/qidi-plus-4-techspecs
- QIDI Plus4 official firmware releases: https://github.com/QIDITECH/QIDI_PLUS4/releases
- QIDI Studio official releases: https://github.com/QIDITECH/QIDIStudio/releases
- QIDI Plus4 official printer configuration showing a 0.400 mm nozzle: https://github.com/QIDITECH/QIDI_PLUS4/blob/main/config/printer.cfg

## Operator confirmation and prototype simplification

The operator confirmed in the project conversation that the machine is the previously specified QIDI Plus4, that the printer has been fully updated, and that the earlier printer qualification steps are complete. For this prototype phase:

- Printer serial: not tracked.
- Exact installed firmware display value: represented by the current official v1.7.1 baseline and operator confirmation of a complete update.
- Machine clearance and full-travel checks: accepted from the operator's completed qualification confirmation.
- Installed nozzle: accepted as the standard 0.4 mm configuration confirmed by the operator and official specification.
- PETG brand, commercial product name, and spool lot: not tracked.
- Drying history: operator-confirmed print-ready PETG; detailed time/temperature record not tracked.
- The six RC03 PETG process profiles use the same qualified PETG/nozzle baseline. Their different layer, wall, and infill settings remain controlled by `config/print_profiles.json` and are tested by their matching coupon plates.

This simplified release applies only to diagnostic coupon printing. Dimensional coupon results and actual production-hardware fits must still be measured before dependent full-size parts are released.
