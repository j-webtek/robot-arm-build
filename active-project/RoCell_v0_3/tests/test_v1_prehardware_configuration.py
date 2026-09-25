from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_print_readiness as readiness  # noqa: E402


ALLOWED_STATES = {
    "CANDIDATE",
    "CANDIDATE_SELECTED",
    "OUT_OF_V1",
    "OPEN",
    "PHYSICAL_QUALIFICATION_REQUIRED",
}


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def state_values(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"state", "decision_state", "qualification_state"}:
                found.append(str(child))
            else:
                found.extend(state_values(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(state_values(child))
    return found


class V1PrehardwareConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.configuration = load_json("config/v1_prehardware_configuration.json")
        cls.measurement = load_json("config/measurement_record.json")
        cls.print_jobs = load_json("config/print_jobs.json")

    def test_state_vocabulary_is_provisional_only(self) -> None:
        self.assertEqual(
            set(self.configuration["status_vocabulary"]), ALLOWED_STATES
        )
        states = state_values(self.configuration)
        self.assertTrue(states)
        self.assertTrue(set(states).issubset(ALLOWED_STATES))
        self.assertIn("CANDIDATE_SELECTED", states)
        self.assertIn("PHYSICAL_QUALIFICATION_REQUIRED", states)
        self.assertNotIn(
            "PASS",
            json.dumps(self.configuration, sort_keys=True),
        )
        self.assertFalse(self.configuration["release_authority"])

    def test_required_v1_candidates_are_explicit(self) -> None:
        items = self.configuration["configuration"]
        self.assertEqual(items["printer"]["model"], "Plus4")
        self.assertEqual(
            items["printer"]["nominal_build_envelope_mm"],
            [305.0, 305.0, 280.0],
        )
        self.assertEqual(
            items["printer"]["provisional_protected_envelope_mm"],
            [295.0, 295.0, 275.0],
        )
        self.assertEqual(
            items["structural_board"]["finished_size_mm"],
            [610.0, 457.0, 18.0],
        )
        self.assertEqual(items["keyboard"]["model_family"], "PERIBOARD-409")
        self.assertEqual(items["phone"]["installed_case_state"], "Bare phone; no case")
        self.assertEqual(items["phone_usb_cable"]["model"], "R2CCR-1M-USB-CABLE")
        self.assertEqual(items["camera"]["manufacturer_part_number"], "960-001401")
        self.assertEqual(items["tool_spring"]["published_stock_code"], "LP022J01S316")
        self.assertEqual(items["camera_support"]["decision_state"], "CANDIDATE")
        self.assertEqual(items["v1_contact_tool"]["route_id"], "keyboard_rod_route")
        self.assertEqual(
            items["phone_stylus_route"]["decision_state"], "CANDIDATE_SELECTED"
        )

    def test_provisional_choices_do_not_select_canonical_routes(self) -> None:
        self.assertEqual(
            self.measurement["selected_routes"],
            {
                "phone_stylus_route": True,
                "keyboard_rod_route": True,
                "camera_mast_optional": False,
            },
        )

    def test_job_00d_is_phone_route_dependent(self) -> None:
        jobs = {job["job_id"]: job for job in self.print_jobs["jobs"]}
        self.assertEqual(jobs["00D"]["selection"], "phone_stylus_route")
        self.assertFalse(
            readiness.selection_active(
                jobs["00D"]["selection"],
                {"phone_stylus_route": False},
            )
        )
        self.assertTrue(
            readiness.selection_active(
                jobs["00D"]["selection"],
                {"phone_stylus_route": True},
            )
        )

        with (ROOT / "JOB_KITS.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            row_00d = next(row for row in csv.DictReader(handle) if row["job_id"] == "00D")
        self.assertEqual(row_00d["route_requirement"], "phone_stylus_route")

    def test_productization_control_files_exist_and_issue_states_are_valid(self) -> None:
        required = (
            "07 - PHASE 1 CONFIGURATION FREEZE DECISIONS.md",
            "08 - V1 PREHARDWARE CONFIGURATION.md",
            "09 - ISSUE REGISTER.csv",
            "10 - CHANGE LOG.md",
            "11 - HARDWARE ARRIVAL AND QUALIFICATION PLAN.md",
        )
        for name in required:
            self.assertTrue((ROOT / "PRODUCTIZATION" / name).is_file(), name)

        with (ROOT / "PRODUCTIZATION" / "09 - ISSUE REGISTER.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertGreaterEqual(len(rows), 10)
        self.assertTrue(all(row["state"] in ALLOWED_STATES for row in rows))
        self.assertTrue(all(row["blocks_v1"] == "yes" for row in rows))

    def test_operator_sources_state_the_00d_route_rule(self) -> None:
        steps = load_json("config/assembly_steps.json")
        step_00 = next(step for step in steps["steps"] if step["id"] == "00")
        procedure = " ".join(step_00["procedure"])
        self.assertIn("00A, 00B, 00C, 00E, and 00F", procedure)
        self.assertIn("00D only when `phone_stylus_route`", procedure)

        manual = (ROOT / "ASSEMBLY_MANUAL.md").read_text(encoding="utf-8")
        self.assertIn("Run job 00D only when `phone_stylus_route` is selected", manual)


if __name__ == "__main__":
    unittest.main()
