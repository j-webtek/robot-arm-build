"""Fixed physical-node observation policy; inert and separate from USB queries.

The application must authenticate the original declared trial and new baseline
before deriving admission facts. A policy object is not a review, a permit, or
evidence that a device is absent. Historical stage/catalog permissions stay exact.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .physical_onboarding import PhysicalOnboardingStage
from .physical_onboarding_stage_catalog import load_physical_onboarding_stage_catalog
from .usb_identity_stage_policy import CATALOG_SHA256, STAGE_ORDER_SHA256
from rocell.providers.windows.owned_worker_process import decode_owned_json
from rocell.providers.windows.usb_identity_protocol import canonical, digest

POLICY_SCHEMA = "rocell.usb_presence_stage_policy.v1"
POLICY_ACTION = "physical-native-usb-presence"
POLICY_COMPOSITION = "PHYSICAL_DIAGNOSTIC_USB_PRESENCE"
WORKER_ID = "scoped-physical-native-usb-presence"
MAX_POLICY_BYTES = 8 * 1024


class UsbPresencePolicyError(ValueError):
    pass


def _document() -> dict[str, Any]:
    # Fresh closed document: callers cannot mutate the executable policy.
    return dict(
        schema=POLICY_SCHEMA,
        policy_id="ROCELL-STAGE4-USB-PRESENCE-001",
        revision=1,
        meaning="EXACT_PHYSICAL_NODE_OBSERVATION_NOT_QUALIFICATION",
        base_catalog_schema="rocell.physical_onboarding_stage_catalog.v2",
        base_catalog_revision=3,
        base_catalog_sha256=CATALOG_SHA256,
        canonical_stage_order_sha256=STAGE_ORDER_SHA256,
        stage=PhysicalOnboardingStage.CAMERA_IDENTITY.value,
        composition=POLICY_COMPOSITION,
        action_id=POLICY_ACTION,
        worker_id=WORKER_ID,
        effect_class="BOUNDED_CAMERA_CAMPAIGN",
        leases=["CELL", "SESSION", "CAMERA"],
        budget=dict(
            timeout_ms=25000,
            maximum_output_bytes=128 * 1024,
            maximum_opens=0,
            maximum_reads=4,
            maximum_writes=0,
            maximum_frames=0,
            maximum_closes=0,
        ),
        query_scope="EXACT_BASELINE_PHYSICAL_USB_PRESENT_NODE_LIST_ONLY",
        intended_phase="RECONNECT_ABSENCE",
        sample_count=2,
        native_duration_ms=2000,
        maximum_list_characters=8192,
        maximum_list_instances=64,
        original_trial_declaration_required=True,
        new_trial_baseline_required=True,
        selected_identity_is_phase_binding=True,
        original_review_required=True,
        durable_consumed_permit_required=True,
        retained_owned_execution_required=True,
        automatic_retry_allowed=False,
        historical_catalog_modified=False,
        physical_authority=False,
        hardware_qualified=False,
        camera_capture_authorized=False,
        arm_access_authorized=False,
        motion_authorized=False,
        contact_authorized=False,
    )


@dataclass(frozen=True, slots=True)
class UsbPresenceStagePolicy:
    payload: bytes

    def __post_init__(self) -> None:
        if (
            type(self.payload) is not bytes
            or not 0 < len(self.payload) <= MAX_POLICY_BYTES
        ):
            raise UsbPresencePolicyError("EXACT_BOUNDED_POLICY_BYTES_REQUIRED")
        try:
            document = decode_owned_json(self.payload, maximum=MAX_POLICY_BYTES)
        except (ValueError, TypeError, RecursionError) as exc:
            raise UsbPresencePolicyError("INVALID_PRESENCE_POLICY") from exc
        # Byte equality rejects Boolean/integer substitutions and extra fields.
        if (
            self.payload != canonical(_document())
            or document["schema"] != POLICY_SCHEMA
        ):
            raise UsbPresencePolicyError("EXACT_PRESENCE_POLICY_REQUIRED")

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return decode_owned_json(self.payload, maximum=MAX_POLICY_BYTES)


def usb_presence_stage_policy() -> UsbPresenceStagePolicy:
    """Return a policy subject without filesystem reads or device actions."""
    return UsbPresenceStagePolicy(canonical(_document()))


def inspect_usb_presence_stage_policy(workspace: Path) -> UsbPresenceStagePolicy:
    """Explicit file inspection only; no approval or catalog mutation."""
    catalog = load_physical_onboarding_stage_catalog(workspace)
    if (
        catalog.source_sha256 != CATALOG_SHA256
        or catalog.canonical_stage_order_sha256 != STAGE_ORDER_SHA256
    ):
        raise UsbPresencePolicyError("PRESENCE_POLICY_BASE_CATALOG_CHANGED")
    return usb_presence_stage_policy()
