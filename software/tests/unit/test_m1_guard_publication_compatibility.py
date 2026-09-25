"""Actual Windows sharing with owned temporary child publications only.

No reparse point, device, inventory, production store or live lease is touched.
These tests exercise the existing M1 publication primitive, not power-loss
qualification or exclusion of hostile directory writers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from rocell.application.physical_onboarding_durability import (
    PhysicalOnboardingDurabilityError,
    PublicationMode,
    publish_canonical_json,
)
from rocell.application.wizard_diagnostic_export import _directory_guard


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Actual Win32 sharing")


@pytest.mark.parametrize("allow_writes", [False, True])
def test_opt_in_preserves_leaf_ancestor_rename_denial_and_allows_m1_replace(
    tmp_path: Path, allow_writes: bool
) -> None:
    ancestor = tmp_path / "owned-ancestor"
    store = ancestor / "owned-store"
    # M1 OnboardingLeaseManager uses the deployment/store root itself, so its
    # owner pointer is an immediate child of the directory pinned by reopen.
    leases = store
    leases.mkdir(parents=True)
    target = publish_canonical_json(
        leases,
        "fixture.owner.json",
        {"owner": "prior", "generation": 1},
        mode=PublicationMode.IMMUTABLE,
    )
    original = target.read_bytes()
    with _directory_guard(store, allow_directory_write_sharing=allow_writes):
        # Both targets are explicitly confined to this invocation's tmp_path.
        for source, renamed in (
            (store, ancestor / "renamed-store"),
            (ancestor, tmp_path / "renamed-ancestor"),
        ):
            assert source.is_relative_to(tmp_path)
            assert renamed.is_relative_to(tmp_path)
            with pytest.raises(OSError) as denied:
                source.rename(renamed)
            assert denied.value.winerror in {5, 32}
            assert source.is_dir() and not renamed.exists()
        if allow_writes:
            actual = publish_canonical_json(
                leases,
                target.name,
                {"owner": "next", "generation": 2},
                mode=PublicationMode.REPLACE,
            )
            assert actual == target
            assert json.loads(actual.read_bytes()) == {"owner": "next", "generation": 2}
            assert actual.stat().st_nlink == 1
        else:
            with pytest.raises(PhysicalOnboardingDurabilityError, match="ReplaceFileW"):
                publish_canonical_json(
                    leases,
                    target.name,
                    {"owner": "next", "generation": 2},
                    mode=PublicationMode.REPLACE,
                )
            assert target.read_bytes() == original
        assert {item.name for item in leases.iterdir()} == {target.name}


def test_opt_in_does_not_turn_immutable_publication_into_replace(
    tmp_path: Path,
) -> None:
    store = tmp_path / "owned-store"
    store.mkdir()
    target = publish_canonical_json(
        store, "receipt.json", {"generation": 1}, mode=PublicationMode.IMMUTABLE
    )
    original = target.read_bytes()
    with _directory_guard(store, allow_directory_write_sharing=True):
        with pytest.raises(PhysicalOnboardingDurabilityError, match="already exists"):
            publish_canonical_json(
                store, "receipt.json", {"generation": 2}, mode=PublicationMode.IMMUTABLE
            )
    assert target.read_bytes() == original


@pytest.mark.parametrize("allow_writes", [False, True])
def test_both_modes_deny_removal_of_guarded_empty_leaf(
    tmp_path: Path, allow_writes: bool
) -> None:
    leaf = tmp_path / "owned-empty-leaf"
    leaf.mkdir()
    with _directory_guard(leaf, allow_directory_write_sharing=allow_writes):
        with pytest.raises(OSError) as denied:
            leaf.rmdir()
        assert denied.value.winerror in {5, 32}
        assert leaf.is_dir()
