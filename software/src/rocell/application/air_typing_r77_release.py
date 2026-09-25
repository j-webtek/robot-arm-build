"""Pinned r77 seven-leg noncontact finale candidate evidence."""
from .product_ghost_export_review import _read

APP_SHA="7a2059d76243b37e9b443c822093ef597611f136f5497a055f01278c3bcda496"
APP_BYTES=1203152
REVIEW="wizard-20260924T230203395592Z-20d1fae308454058afb76d5ef6fd56f4"


def review_release(root):
    report,digest=_read(root/"runs/wizard-exports",REVIEW,"attachment-r77-air-typing-review.json")
    expected=dict(schema="rocell.r77_air_typing_review.v1",
        target="configured-diagnostic-candidate-r77",app_sha256=APP_SHA,
        app_bytes=APP_BYTES,app_offset=0x10000,app_slot_bytes=0x140000,
        predecessor_revision=76,
        predecessor_sha256="874c89ca5af7bbb5e492cb5b3cf95ea47116c19fc65190151c638e47aeac0987",
        selector="AIR7",maximum_writes=7,
        source_goals=[1941,2098,2016,2609,2201,2040,2047],
        source_positions=[1949,2099,2015,2610,2203,2041,2047],
        targets=[[1941,2111,2003,2621,2176,2040,2047],
                 [1941,2080,2034,2591,2236,2040,2047],
                 [1994,2076,2038,2598,2234,2040,2047],
                 [2047,2075,2039,2600,2233,2040,2047],
                 [2047,2093,2021,2618,2197,2040,2047],
                 [2047,2105,2009,2630,2173,2040,2047],
                 [2047,2075,2039,2600,2233,2040,2047]],
        synchronized_servo_ids=[11,12,13,14,15,16,17],
        requires_durable_export_receipt=True,retry_allowed=False,
        settings_preserved_by_design=True,hardware_access=False,
        firmware_uploaded=False,deployment_authorized=False)
    if any(type(report.get(key)) is not type(value) or report[key]!=value
           for key,value in expected.items()):
        raise ValueError("Pinned r77 review differs")
    return report,digest
