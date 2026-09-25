"""Powered-feedback endpoint domain, distinct from passive/canonical permits."""

from dataclasses import dataclass
import hashlib
import json

from rocell.application.powered_arm_feedback_contract import PoweredFeedbackIntent
from rocell.application.passive_arm_identity import PassiveControllerSelection
from .passive_serial_binding import PassiveSerialBinding


@dataclass(frozen=True, slots=True)
class PoweredFeedbackBinding:
    selection: PassiveControllerSelection
    intent: PoweredFeedbackIntent

    def __post_init__(self):
        if (
            type(self.selection) is not PassiveControllerSelection
            or type(self.intent) is not PoweredFeedbackIntent
        ):
            raise ValueError("Exact powered selection and intent required")
        selection = PassiveControllerSelection(self.selection.payload)
        intent = PoweredFeedbackIntent(self.intent.payload)
        native, body = json.loads(selection.payload), intent.to_dict()
        if (
            hashlib.sha256(selection.payload).hexdigest()
            != body["references"]["native_identity_original_sha256"]
            or native["binding"]["mode"] != body["mode"]
            or native["binding"]["session_id"] != body["session_id"]
            or native["binding"]["source_sha256"] != body["references"]["source_sha256"]
        ):
            raise ValueError("Powered feedback selection context mismatch")
        object.__setattr__(self, "selection", selection)
        object.__setattr__(self, "intent", intent)

    @property
    def identity(self):
        return PassiveSerialBinding(self.selection).identity

    @property
    def origin(self):
        return PassiveSerialBinding(self.selection).origin

    @property
    def binding_sha256(self):
        return hashlib.sha256(
            b"rocell.powered_feedback_binding.v1\0"
            + self.intent.payload
            + b"\0"
            + self.selection.payload
        ).hexdigest()
