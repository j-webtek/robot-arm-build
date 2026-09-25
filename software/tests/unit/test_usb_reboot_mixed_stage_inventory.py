"""Full inventories contain earlier stages; individual boot reads remain stage 4.

The collector's original transaction/host observations here are explicitly
modeled. The real reference parsers, inventory comparison and collector run.
No provider, device, process or original M1 store is opened.
"""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from rocell.application import physical_usb_reboot_boot as m
from test_physical_usb_reboot_boot_collector import (
    case,
    collect,
    install_observer,
    no_process_or_devices,
    prepared_case,
    predecessor,
    prerequisites,
    workspace,
    reference,
)


def prior_refs():
    return tuple(
        replace(reference(b"MODELED-PRIOR-STAGE", f"MODELED-stage-{i}"), stage=stage)
        for i, stage in enumerate(m.STAGE_ORDER[:3])
    )


def test_inventory_keeps_every_prior_stage_and_current_reference():
    references = (*prior_refs(), reference(b"MODELED-CURRENT", "MODELED-current"))
    assert m._inventory(SimpleNamespace(evidence=references)) == tuple(
        sorted(m.canonical(ref.to_dict()) for ref in references)
    )
    assert m._inventory(
        SimpleNamespace(evidence=tuple(reversed(references)))
    ) == m._inventory(SimpleNamespace(evidence=references))


def test_mixed_stage_inventory_rejects_duplicate_ids():
    ref = prior_refs()[0]
    with pytest.raises(m.UsbRebootBootError, match="INVENTORY_CHANGED"):
        m._inventory(SimpleNamespace(evidence=(ref, replace(ref, stage=m._STAGE))))


def test_collector_includes_prior_stage_refs_but_never_reads_them_as_boot_roles(
    case, monkeypatch
):
    c = case
    previous = prior_refs()
    for ref in previous:
        c.payloads[ref] = b"MODELED-PRIOR-STAGE"
    install_observer(c, monkeypatch)
    collect(c)
    assert c.collector.retained_diagnostics()["state"] == "BOOT_RETAINED"
    assert all(c.payloads[ref] == b"MODELED-PRIOR-STAGE" for ref in previous)
    assert not set(previous).intersection(row[1] for row in c.calls if row[0] == "read")
    assert len([row for row in c.calls if row[0] == "observe"]) == 1


def test_prior_stage_drift_between_original_checks_still_refuses_before_request(
    case, monkeypatch
):
    c = case
    prior = prior_refs()[0]
    c.payloads[prior] = b"MODELED-PRIOR-STAGE"
    originals = m.read_usb_reboot_boot_originals

    def changed(tx, **kwargs):
        _, workflow, predecessor = originals(tx, **kwargs)
        del c.payloads[prior]
        c.payloads[replace(prior, manifest_sha256="c" * 64)] = b"MODELED-PRIOR-STAGE"
        return c.snapshot(), workflow, predecessor

    monkeypatch.setattr(m, "read_usb_reboot_boot_originals", changed)
    with pytest.raises(m.UsbRebootBootError, match="BOOT_ORIGINAL_HEAD_CHANGED"):
        collect(c)
    assert not any(row[0] in ("observe", "commit", "store") for row in c.calls)


def test_individual_boot_role_read_still_rejects_an_earlier_stage(case):
    with pytest.raises(
        m.qualification.UsbQualificationError, match="ORIGINAL_STAGE_MISMATCH"
    ):
        m._read(case.tx, prior_refs()[0], 1024)
