"""Hardware-free lifecycle double for the Isaac Sim adapter contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import IsaacSimRunReceipt, IsaacSimRunRequest, canonical_sha256


@dataclass(slots=True)
class FakeIsaacSimAdapter:
    """Exercise request/receipt and cancellation behavior without Isaac Sim."""

    _cancelled: bool = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self, request: IsaacSimRunRequest) -> IsaacSimRunReceipt:
        if not isinstance(request, IsaacSimRunRequest):
            raise TypeError("request must be an IsaacSimRunRequest")
        source = request.to_dict()
        physics = source["scene"]["physics"]
        sample_count = len(source["trajectory"]["samples"])
        status = "REJECT" if self._cancelled else "PASS"
        reasons = ["CANCELLED_BEFORE_START"] if self._cancelled else []
        result_basis: dict[str, Any] = {
            "adapter": "fake-v1",
            "request_sha256": request.request_sha256,
            "status": status,
            "reason_codes": reasons,
        }
        unsigned = {
            "schema": "rocell.isaac_sim_run_receipt.v1",
            "request_id": request.request_id,
            "request_sha256": request.request_sha256,
            "evidence_class": "CONTRACT_TEST_ONLY",
            "toolchain": {
                "isaac_sim_version": source["toolchain"]["isaac_sim_version"],
                "installation_sha256": source["toolchain"]["installation_sha256"],
                "backend": "FAKE",
            },
            "execution": {
                "step_count": 0 if self._cancelled else sample_count,
                "time_step_s": physics["time_step_s"],
                "substeps": physics["substeps"],
                "random_seed": source["scene"]["random_seed"],
                "gpu": "NOT_USED",
                "driver": "NOT_USED",
                "renderer": "NOT_USED",
                "physics_backend": "FAKE_CONTRACT_ONLY",
            },
            "import_parity": {"status": "NOT_EVALUATED"},
            "tracking": {"status": "NOT_EVALUATED"},
            "geometry": {"status": "NOT_EVALUATED", "collision_events": []},
            "contact": {"status": "NOT_EVALUATED", "events": []},
            "vision": {"status": "NOT_EVALUATED", "frames": []},
            "differential": {"status": "NOT_EVALUATED", "disagreements": []},
            "reproducibility": {
                "result_signature_sha256": canonical_sha256(result_basis),
                "repeat_index": 0,
            },
            "status": status,
            "reason_codes": reasons,
            "limitations": [
                "FAKE_ADAPTER_CONTRACT_ONLY",
                "NO_PHYSICS_GEOMETRY_RENDERING_OR_HARDWARE_EVIDENCE",
            ],
            "wire_commands": [],
            "hardware_access": False,
            "physical_authority": False,
            "gate_promotions": [],
        }
        return IsaacSimRunReceipt.seal(unsigned)

