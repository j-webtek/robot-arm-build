"""Narrow passive endpoint binding; never a feedback/firmware qualification.

The immutable correlated selection supplies only observed USB/COM metadata.
Fresh resolution, original entry retention and one-use dispatch remain the
supervisor's responsibility. This object alone cannot authorize an open.
"""

from dataclasses import dataclass
import hashlib
import json

from rocell.application.passive_arm_identity import PassiveControllerSelection
from rocell.application.physical_connection_contracts import EvidenceOrigin


@dataclass(frozen=True, slots=True)
class PassiveEndpoint:
    port_name: str
    identity_sha256: str


@dataclass(frozen=True, slots=True)
class PassiveSerialBinding:
    selection: PassiveControllerSelection

    def __post_init__(self):
        if type(self.selection) is not PassiveControllerSelection:
            raise ValueError("Exact passive metadata selection required")
        # Reconstruct rather than trusting a caller-modified frozen instance.
        object.__setattr__(
            self, "selection", PassiveControllerSelection(self.selection.payload)
        )

    @property
    def identity(self) -> PassiveEndpoint:
        value = json.loads(self.selection.payload)
        return PassiveEndpoint(
            value["reviewed_generic_candidate"]["ephemeral_locator_observation"],
            value["native_observation_sha256"],
        )

    @property
    def origin(self) -> EvidenceOrigin:
        return EvidenceOrigin(
            json.loads(self.selection.payload)["provenance"]["origin"]
        )

    @property
    def binding_sha256(self) -> str:
        # Domain separation prevents confusing this with a feedback binding.
        return hashlib.sha256(
            b"rocell.passive_serial_binding.v1\0" + self.selection.payload
        ).hexdigest()
