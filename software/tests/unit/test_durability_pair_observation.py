"""One fresh storage observation per gate; no cached admission or device IO."""

from dataclasses import replace
import os

import pytest

from rocell.application import physical_onboarding_durability as durability
from rocell.application.physical_onboarding_storage import (
    PhysicalOnboardingStorageError,
    QualifiedWindowsOnboardingPublication,
)


SOURCE = "a" * 64
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows NTFS gate")


@pytest.fixture(scope="module")
def qualified_pair(tmp_path_factory):
    # These are actual on-volume storage self-tests, not camera/arm observations.
    root = tmp_path_factory.mktemp("durability-pair").resolve()
    anchor = durability.run_on_volume_startup_self_test(
        root, source_binding_sha256=SOURCE, checked_at_ns=1000
    )
    startup = durability.run_on_volume_startup_self_test(
        root, source_binding_sha256=SOURCE, checked_at_ns=2000
    )
    assert anchor.qualified_for_effects and startup.qualified_for_effects
    return root, anchor, startup


def _require(pair):
    root, anchor, startup = pair
    durability.require_effect_durability_pair(
        anchor, startup, root=root, source_binding_sha256=SOURCE
    )


def _variant(report, defect):
    if defect == "absent":
        return None
    if defect == "type":
        return object()
    document = report.to_dict()
    if defect == "source":
        document["source_binding_sha256"] = "b" * 64
    elif defect == "root":
        document["root_sha256"] = "c" * 64
    elif defect == "volume":
        document["volume_identity"] += "_different"
    elif defect == "filesystem":
        document["filesystem"] = "NTFS_REMOTE_UNQUALIFIED"
        document["qualified_for_effects"] = False
    elif defect == "platform":
        document["platform"] = "Linux"
        document["qualified_for_effects"] = False
    elif defect == "failed-check":
        document["checks"][0]["passed"] = False
        document["qualified_for_effects"] = False
    else:
        raise AssertionError(defect)
    document.pop("report_sha256")
    document["report_sha256"] = durability.canonical_sha256(document)
    return durability.DurabilityQualificationReport.from_dict(document)


@pytest.mark.parametrize("target", [1, 2], ids=["anchor", "startup"])
@pytest.mark.parametrize(
    "defect,message",
    [
        ("absent", "absent"),
        ("type", "type is invalid"),
        ("source", "source is stale"),
        ("root", "another root"),
        ("volume", "another deployment volume"),
        ("filesystem", "another deployment volume"),
        ("platform", "unqualified"),
        ("failed-check", "unqualified"),
    ],
)
def test_both_receipts_retain_standalone_rejection_rules(
    qualified_pair, target, defect, message
):
    pair = list(qualified_pair)
    pair[target] = _variant(pair[target], defect)
    with pytest.raises(durability.DurabilityQualificationError, match=message):
        durability.require_effect_durability(
            pair[target], root=pair[0], source_binding_sha256=SOURCE
        )
    with pytest.raises(durability.DurabilityQualificationError, match=message):
        _require(pair)


def test_every_gate_observes_root_and_volume_once_without_caching(
    qualified_pair, monkeypatch
):
    roots, volumes = [], []
    original_root = durability.safe_root
    original_volume = durability._windows_volume_identity

    def fresh_root(path, **kwargs):
        roots.append(path)
        return original_root(path, **kwargs)

    def fresh_volume(path):
        volumes.append(path)
        return original_volume(path)

    monkeypatch.setattr(durability, "safe_root", fresh_root)
    monkeypatch.setattr(durability, "_windows_volume_identity", fresh_volume)
    for count in range(1, 4):
        _require(qualified_pair)
        assert len(roots) == len(volumes) == count
        assert roots[-1] == volumes[-1] == qualified_pair[0]


@pytest.mark.parametrize("change", ["volume", "unverifiable", "unsafe-root"])
def test_successful_call_cannot_mask_next_gate_failure(
    qualified_pair, monkeypatch, change
):
    _require(qualified_pair)
    if change == "volume":
        monkeypatch.setattr(
            durability, "_windows_volume_identity", lambda _: ("NTFS", "changed")
        )
        message = "another deployment volume"
    elif change == "unverifiable":

        def fail_volume(_):
            raise durability.PhysicalOnboardingDurabilityError("observation failed")

        monkeypatch.setattr(durability, "_windows_volume_identity", fail_volume)
        message = "cannot be reverified"
    else:

        def fail_path(*args, **kwargs):
            raise durability.PhysicalOnboardingDurabilityError("unsafe root")

        monkeypatch.setattr(durability, "safe_root", fail_path)
        message = "unsafe root"
    with pytest.raises(durability.PhysicalOnboardingDurabilityError, match=message):
        _require(qualified_pair)


def _publication(pair, guard):
    root, anchor, startup = pair
    return QualifiedWindowsOnboardingPublication(
        root, SOURCE, anchor, startup, mutation_guard=guard
    )


def test_publication_preserves_anchor_and_timestamp_order(qualified_pair):
    publication = _publication(qualified_pair, lambda: None)
    assert (
        publication.durability_qualification_sha256 == qualified_pair[1].report_sha256
    )
    assert (
        publication.startup_report.report_sha256
        != publication.qualification_anchor.report_sha256
    )
    # Both receipts qualify independently, but reversing them still fails.
    with pytest.raises(PhysicalOnboardingStorageError, match="predates"):
        replace(
            publication,
            qualification_anchor=publication.startup_report,
            startup_report=publication.qualification_anchor,
        )


@pytest.mark.parametrize("operation", ["property", "write", "replace", "mkdir", "sync"])
def test_adapter_rechecks_after_construction_and_never_writes_on_failure(
    qualified_pair, monkeypatch, operation
):
    guards = []
    publication = _publication(qualified_pair, lambda: guards.append("guard"))
    root = qualified_pair[0]
    before = sorted(str(item.relative_to(root)) for item in root.rglob("*"))
    monkeypatch.setattr(
        durability, "_windows_volume_identity", lambda _: ("NTFS", "changed")
    )
    assert publication.effectful_durability_qualified is False
    operations = {
        "property": lambda: publication.durability_qualification_sha256,
        "write": lambda: publication.write_new_file(root / "never.bin", b"never"),
        "replace": lambda: publication.replace_file(root / "never.bin", b"never"),
        "mkdir": lambda: publication.publish_new_directory(
            root / "never-source", root / "never-destination"
        ),
        "sync": lambda: publication.sync_directory(root),
    }
    with pytest.raises(durability.DurabilityQualificationError, match="volume"):
        operations[operation]()
    assert guards == []
    assert before == sorted(str(item.relative_to(root)) for item in root.rglob("*"))
