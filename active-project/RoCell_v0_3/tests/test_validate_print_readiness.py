from __future__ import annotations

import copy
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_print_readiness as readiness  # noqa: E402


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class EngineeringReleaseGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = load_json("config/measurement_record.json")
        self.jobs = load_json("config/print_jobs.json")

    @staticmethod
    def write_valid_fastener_map(directory: str, **overrides: str) -> Path:
        source = ROOT / "FASTENER_MAP.csv"
        target = Path(directory) / "FASTENER_MAP.csv"
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or ())
            rows = list(reader)
        for row in rows:
            row.update(
                {
                    "selected_length_mm": "25.0",
                    "anchor_type": "qualified test threaded anchor",
                    "anchor_manufacturer_part": "TEST-M4-ANCHOR",
                    "bore_mode": "THROUGH",
                    "final_board_bore_mm": "6.0",
                    "bore_depth_mm_or_through": "THROUGH",
                    "install_face": "UNDERSIDE",
                    "pilot_diameter_mm": "3.0",
                    "qualification_reference": "tests/fixtures/anchor-qualification",
                }
            )
            row.update(overrides)
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return target

    def valid_board_fabrication(self, fastener_map_path: Path) -> dict:
        record = copy.deepcopy(self.record)
        gate = record["gates"]["board_fabrication_pass"]
        gate["status"] = "PASS"
        gate["recorded_values"].update(
            {
                "width_mm": 610.0,
                "depth_mm": 457.0,
                "thickness_mm": 18.0,
                "front_width_mm": 610.0,
                "rear_width_mm": 610.0,
                "left_depth_mm": 457.0,
                "right_depth_mm": 457.0,
                "diagonal_1_mm": 762.2,
                "diagonal_2_mm": 762.2,
                "transferred_center_coordinate_record": "Step 01 coordinate audit",
                "both_faces_sealed_result": "PASS",
                "all_edges_sealed_result": "PASS",
                "finish_cure_result": "PASS",
                "finish_product_and_batch": "waterborne finish, batch TEST",
                "finish_application_and_cure_record": (
                    "two equal face coats plus all edges; fully cured"
                ),
                "finish_evidence_reference": "BUILD_BY_STEP/01/finish-evidence",
                "local_flatness_by_station_mm": {
                    "keyboard_left": 0.20,
                    "keyboard_right": 0.25,
                    "phone_tcp": 0.20,
                },
                "overall_bow_mm": 1.0,
                "template_x_scale_bar_mm": 100.0,
                "template_y_scale_bar_mm": 100.0,
                "local_thickness_by_locator_mm": {
                    "KBL-LOC-ROUND": 18.0,
                    "KBL-LOC-RADIAL": 18.0,
                    "PT-LOC-ROUND": 18.0,
                    "PT-LOC-RADIAL": 18.0,
                },
                "blind_locator_bore_depths_mm": {
                    "KBL-LOC-ROUND": 15.0,
                    "KBL-LOC-RADIAL": 15.0,
                    "PT-LOC-ROUND": 15.0,
                    "PT-LOC-RADIAL": 15.0,
                },
                "locator_projection_measurements_mm": {
                    "KBL-LOC-ROUND": 5.0,
                    "KBL-LOC-RADIAL": 5.0,
                    "PT-LOC-ROUND": 5.0,
                    "PT-LOC-RADIAL": 5.0,
                },
                "threaded_board_interface_result": "PASS",
                "scrap_stack_proof_load_result": "PASS",
                "selected_fastener_map_sha256": hashlib.sha256(
                    fastener_map_path.read_bytes()
                ).hexdigest(),
            }
        )
        return record

    def test_fixed_camera_fallback_jobs_have_a_hard_architecture_interlock(self) -> None:
        expected = {"03C3", "06", "07A", "07B"}
        gated = {
            job["job_id"]
            for job in self.jobs["jobs"]
            if "fixed_camera_fallback_architecture_released"
            in job.get("prerequisites", [])
        }
        self.assertEqual(gated, expected)
        for job in self.jobs["jobs"]:
            if job["job_id"] in expected:
                self.assertEqual(job["selection"], "camera_mast_optional")

    def test_unselected_camera_fallback_keeps_every_fallback_job_not_selected(self) -> None:
        report = readiness.build_report()
        by_id = {job["job_id"]: job for job in report["jobs"]}
        for job_id in ("03C3", "06", "07A", "07B"):
            with self.subTest(job_id=job_id):
                self.assertEqual(by_id[job_id]["status"], "NOT_SELECTED")
                self.assertIn(
                    "fixed_camera_fallback_architecture_released",
                    by_id[job_id]["missing_gates"],
                )

    def test_fixed_camera_fallback_gate_cannot_pass_while_decision_is_held(self) -> None:
        record = copy.deepcopy(self.record)
        gate = record["gates"]["fixed_camera_fallback_architecture_released"]
        gate["status"] = "PASS"
        gate["recorded_values"].update(
            {
                "architecture_decision_status": "ENGINEERING_ALIGNMENT_HOLD",
                "architecture_decision_revision": record["design_revision"],
                "architecture_decision_sha256": "0" * 64,
                "fixed_camera_fallback_authorized": False,
                "fallback_authorization_reference": "test-held-decision",
            }
        )
        with self.assertRaisesRegex(ValueError, "ALIGNED_AND_REVISED"):
            readiness.validate_engineering_release_gates(record)

    def test_fixed_camera_fallback_gate_binds_the_authorized_decision(self) -> None:
        record = copy.deepcopy(self.record)
        gate = record["gates"]["fixed_camera_fallback_architecture_released"]
        gate["status"] = "PASS"
        decision = load_json("config/camera_architecture_decision.json")
        decision["status"] = "ALIGNED_AND_REVISED"
        decision["fixed_camera_fallback_release"].update(
            {
                "authorized": True,
                "authorization_reference": "CAM-FALLBACK-TEST-1",
                "release_revision": record["design_revision"],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            decision_path = Path(directory) / "camera_architecture_decision.json"
            decision_path.write_text(json.dumps(decision), encoding="utf-8")
            gate["recorded_values"].update(
                {
                    "architecture_decision_status": "ALIGNED_AND_REVISED",
                    "architecture_decision_revision": record["design_revision"],
                    "architecture_decision_sha256": hashlib.sha256(
                        decision_path.read_bytes()
                    ).hexdigest(),
                    "fixed_camera_fallback_authorized": True,
                    "fallback_authorization_reference": "CAM-FALLBACK-TEST-1",
                }
            )
            with mock.patch.object(
                readiness, "CAMERA_ARCHITECTURE_DECISION_PATH", decision_path
            ):
                readiness.validate_engineering_release_gates(record)
                gate["recorded_values"]["architecture_decision_sha256"] = "0" * 64
                with self.assertRaisesRegex(ValueError, "does not match"):
                    readiness.validate_engineering_release_gates(record)

    def test_board_fabrication_binds_selected_fastener_map_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fastener_map = self.write_valid_fastener_map(directory)
            record = self.valid_board_fabrication(fastener_map)
            with mock.patch.object(readiness, "FASTENER_MAP_PATH", fastener_map):
                readiness.validate_engineering_release_gates(record)
                record["gates"]["board_fabrication_pass"]["recorded_values"][
                    "selected_fastener_map_sha256"
                ] = "0" * 64
                with self.assertRaisesRegex(ValueError, "FASTENER_MAP.csv hash is stale"):
                    readiness.validate_engineering_release_gates(record)

    def test_board_fabrication_requires_face_edge_and_cure_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fastener_map = self.write_valid_fastener_map(directory)
            record = self.valid_board_fabrication(fastener_map)
            with mock.patch.object(readiness, "FASTENER_MAP_PATH", fastener_map):
                readiness.validate_engineering_release_gates(record)
                for key in (
                    "both_faces_sealed_result",
                    "all_edges_sealed_result",
                    "finish_cure_result",
                    "finish_product_and_batch",
                    "finish_application_and_cure_record",
                    "finish_evidence_reference",
                    "threaded_board_interface_result",
                    "scrap_stack_proof_load_result",
                ):
                    with self.subTest(key=key):
                        invalid = copy.deepcopy(record)
                        invalid["gates"]["board_fabrication_pass"]["recorded_values"][key] = None
                        with self.assertRaisesRegex(ValueError, key):
                            readiness.validate_engineering_release_gates(invalid)

    def test_board_fabrication_enforces_measurement_and_blind_floor_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fastener_map = self.write_valid_fastener_map(directory)
            with mock.patch.object(readiness, "FASTENER_MAP_PATH", fastener_map):
                cases = (
                    ("front_width_mm", None, "front_width_mm"),
                    ("rear_width_mm", 609.49, "cut-size limit"),
                    ("thickness_mm", 17.49, "17.50-18.50 mm"),
                    ("diagonal_2_mm", 763.21, "edge-derived diagonal"),
                    ("local_flatness_by_station_mm", {"phone_tcp": 0.51}, "flatness exceeds"),
                    ("overall_bow_mm", 1.51, "overall bow exceeds"),
                    ("template_x_scale_bar_mm", 99.79, "100.0 \\+/- 0.2 mm"),
                    (
                        "blind_locator_bore_depths_mm",
                        {
                            "KBL-LOC-ROUND": 15.0,
                            "KBL-LOC-RADIAL": 15.0,
                            "PT-LOC-ROUND": 15.0,
                            "PT-LOC-RADIAL": 15.21,
                        },
                        "15.00 \\+/- 0.20 mm",
                    ),
                    (
                        "local_thickness_by_locator_mm",
                        {
                            "KBL-LOC-ROUND": 18.0,
                            "KBL-LOC-RADIAL": 18.0,
                            "PT-LOC-ROUND": 18.0,
                        },
                        "exactly KBL-LOC-ROUND",
                    ),
                    (
                        "locator_projection_measurements_mm",
                        {
                            "KBL-LOC-ROUND": 5.0,
                            "KBL-LOC-RADIAL": 5.0,
                            "PT-LOC-ROUND": 5.0,
                            "PT-LOC-RADIAL": 5.16,
                        },
                        "5.00 \\+/- 0.15 mm",
                    ),
                )
                for key, value, expected in cases:
                    with self.subTest(key=key):
                        invalid = self.valid_board_fabrication(fastener_map)
                        invalid["gates"]["board_fabrication_pass"]["recorded_values"][key] = value
                        with self.assertRaisesRegex(ValueError, expected):
                            readiness.validate_engineering_release_gates(invalid)

    def test_fastener_map_requires_selected_anchor_bore_plan_and_layout_coordinates(self) -> None:
        with self.assertRaisesRegex(ValueError, "selected_length_mm"):
            readiness.validate_selected_fastener_map(ROOT / "FASTENER_MAP.csv")

        with tempfile.TemporaryDirectory() as directory:
            valid = self.write_valid_fastener_map(directory)
            readiness.validate_selected_fastener_map(valid)
            cases = (
                ("bore_mode", "", "bore_mode"),
                ("final_board_bore_mm", "", "final_board_bore_mm"),
                ("anchor_manufacturer_part", "", "anchor_manufacturer_part"),
                ("world_x_mm", "999", "does not match the released layout"),
                ("bore_depth_mm_or_through", "12", "must be THROUGH"),
                ("install_face", "SIDE", "TOP or UNDERSIDE"),
            )
            for field, value, expected in cases:
                with self.subTest(field=field):
                    case_dir = Path(directory) / field
                    case_dir.mkdir()
                    invalid = self.write_valid_fastener_map(str(case_dir), **{field: value})
                    with self.assertRaisesRegex(ValueError, expected):
                        readiness.validate_selected_fastener_map(invalid)

    def test_board_template_pass_binds_scale_revision_and_pdf_hash(self) -> None:
        selected = "output/pdf/RC03_BOARD_DRILL_GUIDE_LETTER_1TO1.pdf"
        with tempfile.TemporaryDirectory() as directory:
            guide = Path(directory) / "guide.pdf"
            guide.write_bytes(b"unit-test board guide")
            record = copy.deepcopy(self.record)
            gate = record["gates"]["board_setup_template_scale_pass"]
            gate["status"] = "PASS"
            gate["recorded_values"].update(
                {
                    "template_revision": record["design_revision"],
                    "selected_guide_path": selected,
                    "selected_guide_sha256": hashlib.sha256(guide.read_bytes()).hexdigest(),
                    "source_layout_sha256": hashlib.sha256(
                        (ROOT / "config/workcell_layout.json").read_bytes()
                    ).hexdigest(),
                    "x_scale_bar_mm": 99.8,
                    "y_scale_bar_mm": 100.2,
                    "page_scaling_setting": "Actual Size / 100 percent",
                    "all_sheet_registration_marks_result": "PASS",
                }
            )
            with mock.patch.object(readiness, "BOARD_DRILL_GUIDE_PATHS", {selected: guide}):
                readiness.validate_engineering_release_gates(record)

                for key, value, expected in (
                    ("selected_guide_path", "drawings/old.pdf", "selected_guide_path"),
                    ("selected_guide_sha256", "0" * 64, "selected_guide_sha256 is stale"),
                    ("source_layout_sha256", "0" * 64, "source_layout_sha256 is stale"),
                    ("x_scale_bar_mm", 99.79, "100.0 \\+/- 0.2 mm"),
                    ("y_scale_bar_mm", 100.21, "100.0 \\+/- 0.2 mm"),
                    ("page_scaling_setting", "Fit", "page_scaling_setting"),
                    ("all_sheet_registration_marks_result", "FAIL", "registration_marks_result"),
                ):
                    with self.subTest(key=key):
                        invalid = copy.deepcopy(record)
                        invalid["gates"]["board_setup_template_scale_pass"]["recorded_values"][
                            key
                        ] = value
                        with self.assertRaisesRegex(ValueError, expected):
                            readiness.validate_engineering_release_gates(invalid)

    def valid_calibration_cartridges(self) -> dict:
        record = copy.deepcopy(self.record)
        gate = record["gates"]["calibration_puck_datum_pass"]
        gate["status"] = "PASS"
        values = gate["recorded_values"]
        heights_a = [12.00, 12.01, 12.00, 12.01, 12.00, 12.01, 12.00, 12.01, 12.00, 12.01]
        heights_b = [12.00, 12.02, 12.01, 12.02, 12.00, 12.02, 12.01, 12.02, 12.00, 12.02]
        values.update(
            {
                "job_id": "03D",
                "cartridge_count": 2,
                "cartridge_A_free_state_flatness_mm": 0.02,
                "cartridge_A_crosshair_result": "PASS",
                "cartridge_A_divot_result": "PASS",
                "cartridge_A_lateral_play_mm": 0.05,
                "cartridge_A_remove_reinstall_cycles": 10,
                "cartridge_A_mounted_height_measurements_mm": heights_a,
                "cartridge_A_mounted_height_range_mm": 0.01,
                "cartridge_A_mean_mounted_height_mm": sum(heights_a) / len(heights_a),
                "cartridge_B_free_state_flatness_mm": 0.03,
                "cartridge_B_crosshair_result": "PASS",
                "cartridge_B_divot_result": "PASS",
                "cartridge_B_lateral_play_mm": 0.08,
                "cartridge_B_remove_reinstall_cycles": 10,
                "cartridge_B_mounted_height_measurements_mm": heights_b,
                "cartridge_B_mounted_height_range_mm": 0.02,
                "cartridge_B_mean_mounted_height_mm": sum(heights_b) / len(heights_b),
                "installed_cartridge_id": "03D-A",
                "installed_selection_score": max(0.05 / 0.15, 0.01 / 0.10),
                "spare_cartridge_id": "03D-B",
                "accepted_spare_result": "PASS",
                "spare_swap_requires_tcp_recalibration": True,
            }
        )
        return record

    def test_calibration_cartridges_are_individually_qualified_and_selected(self) -> None:
        valid = self.valid_calibration_cartridges()
        readiness.validate_engineering_release_gates(valid)

        cases = (
            ("lateral play exceeds", "cartridge_B_lateral_play_mm", 0.16),
            ("INSTALL label", "installed_cartridge_id", "03D-B"),
            ("TCP recalibration", "spare_swap_requires_tcp_recalibration", False),
        )
        for expected, key, value in cases:
            with self.subTest(key=key):
                invalid = self.valid_calibration_cartridges()
                invalid["gates"]["calibration_puck_datum_pass"]["recorded_values"][key] = value
                with self.assertRaisesRegex(ValueError, expected):
                    readiness.validate_engineering_release_gates(invalid)

        excessive_range = self.valid_calibration_cartridges()
        values = excessive_range["gates"]["calibration_puck_datum_pass"]["recorded_values"]
        heights = [12.00, 12.11] * 5
        values["cartridge_B_mounted_height_measurements_mm"] = heights
        values["cartridge_B_mounted_height_range_mm"] = 0.11
        values["cartridge_B_mean_mounted_height_mm"] = sum(heights) / len(heights)
        with self.assertRaisesRegex(ValueError, "mounted-height range exceeds"):
            readiness.validate_engineering_release_gates(excessive_range)

    @staticmethod
    def approve_metadata(values: dict, approval_id: str) -> None:
        values.update(
            {
                "approval_id": approval_id,
                "approved_by": "responsible-reviewer",
                "approved_at": "2026-08-31T12:00:00Z",
                "engineering_rationale": "Controlled engineering review",
                "evidence_reference": "evidence/engineering-review.pdf",
            }
        )

    def valid_phone_clearance(self) -> dict:
        record = copy.deepcopy(self.record)
        approval = record["gates"]["phone_no_go_clearance_limit_approved"]
        approval["status"] = "PASS"
        self.approve_metadata(approval["recorded_values"], "PHONE-CLEAR-1")
        approval["recorded_values"].update(
            {"minimum_clearance_mm": 1.0, "maximum_measurement_uncertainty_mm": 0.1}
        )
        measured = record["gates"]["phone_side_features_measured"]
        measured["status"] = "PASS"
        measured["recorded_values"] = {
            "approved_clearance_limit_id": "PHONE-CLEAR-1",
            "right_side_keepouts_from_bottom_mm": [
                {"feature": "volume", "start_mm": 20.0, "end_mm": 30.0},
                {"feature": "power", "start_mm": 50.0, "end_mm": 60.0},
            ],
            "selected_clamp_centers_from_bottom_mm": [10.0, 40.0],
            "minimum_keepout_margin_mm": 10.0,
            "clearance_measurement_uncertainty_mm": 0.1,
        }
        fixture = record["gates"]["phone_fixture_assembly_pass"]
        fixture["status"] = "PASS"
        fixture["recorded_values"].update(
            {
                "approved_no_go_clearance_limit_id": "PHONE-CLEAR-1",
                "approved_minimum_no_go_clearance_mm": 1.0,
                "measured_minimum_no_go_clearance_mm": 1.2,
                "clearance_measurement_uncertainty_mm": 0.1,
            }
        )
        return record

    def test_phone_no_go_approval_and_measurements_are_cross_checked(self) -> None:
        valid = self.valid_phone_clearance()
        readiness.validate_engineering_release_gates(valid)

        cases = (
            (
                "approval ID",
                lambda row: row["gates"]["phone_side_features_measured"]["recorded_values"].__setitem__(
                    "approved_clearance_limit_id", "WRONG"
                ),
            ),
            (
                "greater than zero",
                lambda row: row["gates"]["phone_no_go_clearance_limit_approved"][
                    "recorded_values"
                ].__setitem__("minimum_clearance_mm", 0),
            ),
            (
                "inside a keepout",
                lambda row: row["gates"]["phone_side_features_measured"]["recorded_values"].__setitem__(
                    "selected_clamp_centers_from_bottom_mm", [25.0, 40.0]
                ),
            ),
            (
                "below the approved minimum",
                lambda row: row["gates"]["phone_fixture_assembly_pass"]["recorded_values"].update(
                    {"measured_minimum_no_go_clearance_mm": 1.05, "clearance_measurement_uncertainty_mm": 0.1}
                ),
            ),
        )
        for expected, mutation in cases:
            with self.subTest(expected=expected):
                row = self.valid_phone_clearance()
                mutation(row)
                with self.assertRaisesRegex(ValueError, expected):
                    readiness.validate_engineering_release_gates(row)

    def valid_phone_tpu(self) -> dict:
        record = copy.deepcopy(self.record)
        approval = record["gates"]["phone_tpu_retention_limits_approved"]
        approval["status"] = "PASS"
        self.approve_metadata(approval["recorded_values"], "PHONE-TPU-1")
        approval["recorded_values"].update(
            {
                "minimum_pull_force_n": 5.0,
                "minimum_proof_duration_s": 10.0,
                "force_gauge_required_range_n": 10.0,
                "force_gauge_required_resolution_n": 0.1,
            }
        )
        coupon = record["gates"]["phone_tpu_retention_coupon_pass"]
        coupon["status"] = "PASS"
        coupon["recorded_values"].update(
            {
                "approved_limits_id": "PHONE-TPU-1",
                "minimum_pull_force_n": 5.0,
                "proof_duration_s": 12.0,
                "measured_pull_force_n": 5.5,
            }
        )
        return record

    def test_phone_tpu_coupon_must_match_approval(self) -> None:
        readiness.validate_engineering_release_gates(self.valid_phone_tpu())
        for key, value, expected in (
            ("approved_limits_id", "WRONG", "approval ID"),
            ("minimum_pull_force_n", 4.0, "does not match"),
            ("proof_duration_s", 9.0, "below the approved"),
            ("measured_pull_force_n", 4.9, "below the approved"),
        ):
            with self.subTest(key=key):
                row = self.valid_phone_tpu()
                row["gates"]["phone_tpu_retention_coupon_pass"]["recorded_values"][key] = value
                with self.assertRaisesRegex(ValueError, expected):
                    readiness.validate_engineering_release_gates(row)

    @staticmethod
    def keyboard_limits() -> dict:
        return {
            "compression_force_checkpoints": [
                {"travel_mm": 0.0, "minimum_force_n": 0.0, "maximum_force_n": 1.0},
                {"travel_mm": 4.0, "minimum_force_n": 2.0, "maximum_force_n": 6.0},
            ],
            "tcp_axis_range_limit_mm": 0.2,
            "rod_bushing_minimum_pull_force_n": 5.0,
            "rod_bushing_minimum_proof_duration_s": 10.0,
            "keyboard_tpu_minimum_pull_force_n": 4.0,
            "keyboard_tpu_minimum_proof_duration_s": 8.0,
        }

    @staticmethod
    def stylus_limits() -> dict:
        return {
            "compression_force_checkpoints": [
                {"travel_mm": 0.0, "minimum_force_n": 0.0, "maximum_force_n": 1.0},
                {"travel_mm": 4.0, "minimum_force_n": 2.0, "maximum_force_n": 5.0},
            ],
            "tcp_axis_range_limit_mm": 0.15,
            "stylus_collar_minimum_pull_force_n": 3.0,
            "stylus_collar_minimum_proof_duration_s": 9.0,
        }

    def valid_tool(self, routes: tuple[str, ...] = ("keyboard_rod_route",)) -> dict:
        record = copy.deepcopy(self.record)
        # Test cases must not inherit whichever route-selection state is stored
        # in the live, deliberately incomplete measurement record.
        for route in readiness.TOOL_ROUTE_IDS:
            record["selected_routes"][route] = False
        for route in routes:
            record["selected_routes"][route] = True
        approval = record["gates"]["tool_force_tcp_limits_approved"]
        approval["status"] = "PASS"
        self.approve_metadata(approval["recorded_values"], "TOOL-1")
        approval["recorded_values"].update(
            {
                "selected_routes": list(routes),
                "limits_by_route": {
                    route: self.keyboard_limits() if route == "keyboard_rod_route" else self.stylus_limits()
                    for route in routes
                },
                "force_gauge_required_range_n": 10.0,
                "force_gauge_required_resolution_n": 0.1,
                "tcp_probe_method_and_reference_frame": "fixed probe in board frame",
            }
        )
        assembled = record["gates"]["tool_assembled_motion_pass"]
        assembled["status"] = "PASS"
        results = {}
        for route in routes:
            common = {
                "cycle_count": 20,
                "free_travel_mm": 4.0,
                "force_measurements_by_checkpoint": [
                    {"travel_mm": 0.0, "measured_force_n": 0.5},
                    {"travel_mm": 4.0, "measured_force_n": 3.0},
                ],
                "full_return_pass": True,
                "no_coil_bind_pass": True,
                "gripper_retention_pass": True,
                "functional_contact_pass": True,
                "tcp_probe_cycle_count": 10,
                "tcp_range_x_mm": 0.1,
                "tcp_range_y_mm": 0.1,
                "tcp_range_z_mm": 0.1,
            }
            if route == "keyboard_rod_route":
                common.update(
                    {
                        "rod_bushing_pull_force_n": 5.0,
                        "rod_bushing_proof_duration_s": 10.0,
                        "keyboard_tpu_pull_force_n": 4.0,
                        "keyboard_tpu_proof_duration_s": 8.0,
                    }
                )
            else:
                common.update(
                    {"stylus_collar_pull_force_n": 3.0, "stylus_collar_proof_duration_s": 9.0}
                )
            results[route] = common
        assembled["recorded_values"].update(
            {
                "approved_limits_id": "TOOL-1",
                "selected_routes": list(routes),
                "force_gauge_id": "FG-1",
                "tcp_probe_method_and_reference_frame": "fixed probe in board frame",
                "results_by_route": results,
            }
        )
        return record

    def test_tool_approval_and_results_exactly_cover_routes(self) -> None:
        for routes in (
            ("keyboard_rod_route",),
            ("phone_stylus_route",),
            ("keyboard_rod_route", "phone_stylus_route"),
        ):
            with self.subTest(routes=routes):
                readiness.validate_engineering_release_gates(self.valid_tool(routes))

        wrong_id = self.valid_tool()
        wrong_id["gates"]["tool_assembled_motion_pass"]["recorded_values"]["approved_limits_id"] = "WRONG"
        with self.assertRaisesRegex(ValueError, "approval ID"):
            readiness.validate_engineering_release_gates(wrong_id)

        missing_route = self.valid_tool(("keyboard_rod_route", "phone_stylus_route"))
        del missing_route["gates"]["tool_force_tcp_limits_approved"]["recorded_values"][
            "limits_by_route"
        ]["phone_stylus_route"]
        with self.assertRaisesRegex(ValueError, "exactly cover"):
            readiness.validate_engineering_release_gates(missing_route)

        bad_force = self.valid_tool()
        bad_force["gates"]["tool_assembled_motion_pass"]["recorded_values"]["results_by_route"][
            "keyboard_rod_route"
        ]["force_measurements_by_checkpoint"][1]["measured_force_n"] = 7.0
        with self.assertRaisesRegex(ValueError, "outside approval"):
            readiness.validate_engineering_release_gates(bad_force)

    def test_route_coupon_limits_must_match_tool_approval(self) -> None:
        cases = (
            (
                "keyboard_tpu_retention_coupon_pass",
                "keyboard_rod_route",
                "keyboard_tpu_minimum_pull_force_n",
                "keyboard_tpu_minimum_proof_duration_s",
            ),
            (
                "rod_bushing_retention_pass",
                "keyboard_rod_route",
                "rod_bushing_minimum_pull_force_n",
                "rod_bushing_minimum_proof_duration_s",
            ),
            (
                "stylus_collar_retention_pass",
                "phone_stylus_route",
                "stylus_collar_minimum_pull_force_n",
                "stylus_collar_minimum_proof_duration_s",
            ),
        )
        for gate_id, route, force_key, duration_key in cases:
            with self.subTest(gate_id=gate_id):
                record = self.valid_tool((route,))
                gate = record["gates"][gate_id]
                gate["status"] = "PASS"
                limits = record["gates"]["tool_force_tcp_limits_approved"]["recorded_values"][
                    "limits_by_route"
                ][route]
                gate["recorded_values"].update(
                    {
                        "approved_limits_id": "TOOL-1",
                        "minimum_pull_force_n": limits[force_key],
                        "proof_duration_s": limits[duration_key],
                        "measured_pull_force_n": limits[force_key],
                    }
                )
                readiness.validate_engineering_release_gates(record)
                gate["recorded_values"]["minimum_pull_force_n"] = limits[force_key] / 2
                with self.assertRaisesRegex(ValueError, "does not match"):
                    readiness.validate_engineering_release_gates(record)

    def valid_commissioning(self) -> dict:
        record = copy.deepcopy(self.record)
        artifact_paths = {
            "homing_reference_procedure": "README_FIRST.md",
            "empty_cell_program": "software_helpers/detect_apriltags.py",
            "final_process_program": "software_helpers/calibrate_camera_charuco.py",
        }
        artifact_values = {}
        for key, relative in artifact_paths.items():
            artifact_values[f"{key}_path"] = relative
            artifact_values[f"{key}_sha256"] = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        approval = record["gates"]["commissioning_motion_contact_limits_approved"]
        approval["status"] = "PASS"
        self.approve_metadata(approval["recorded_values"], "COMMISSION-1")
        approval["recorded_values"].update(
            {
                "empty_motion_tcp_speed_limit_mm_s": 50.0,
                "empty_motion_tcp_acceleration_limit_mm_s2": 100.0,
                "minimum_clearance_mm": 5.0,
                "first_contact_tcp_speed_limit_mm_s": 10.0,
                "first_contact_force_limit_n": 2.0,
                "first_contact_travel_limit_mm": 1.0,
                "station_20n_lateral_proof_duration_s": 10.0,
                "station_10n_functional_proof_duration_s": 10.0,
                "controller_model_and_firmware": "test-controller firmware 1",
                "estop_implementation": "rated dual-channel test E-stop",
                "board_anti_shift_implementation": "rated test bench clamps",
                **artifact_values,
            }
        )
        workcell = record["gates"]["workcell_commissioning_pass"]
        workcell["status"] = "PASS"
        workcell["recorded_values"].update(
            {
                "approved_motion_contact_limits_id": "COMMISSION-1",
                "empty_motion_tcp_speed_used_mm_s": 40.0,
                "empty_motion_tcp_acceleration_used_mm_s2": 90.0,
                "minimum_clearance_limit_mm": 5.0,
                "minimum_clearance_measured_mm": 6.0,
                "first_contact_tcp_speed_used_mm_s": 8.0,
                "first_contact_force_measured_n": 1.5,
                "first_contact_travel_measured_mm": 0.8,
                "station_20n_lateral_proof_duration_s": 11.0,
                "station_10n_functional_proof_duration_s": 11.0,
                "controller_model_and_firmware": "test-controller firmware 1",
                "estop_implementation": "rated dual-channel test E-stop",
                "board_anti_shift_implementation": "rated test bench clamps",
                **artifact_values,
            }
        )
        return record

    def test_commissioning_fields_have_units_and_respect_approval(self) -> None:
        readiness.validate_engineering_release_gates(self.valid_commissioning())
        for field, value, expected in (
            ("empty_motion_tcp_speed_used_mm_s", 51.0, "exceeds approved"),
            ("minimum_clearance_measured_mm", 4.9, "below the approved"),
            ("first_contact_force_measured_n", 2.1, "exceeds approved"),
            ("station_20n_lateral_proof_duration_s", 9.0, "below the approved"),
        ):
            with self.subTest(field=field):
                row = self.valid_commissioning()
                row["gates"]["workcell_commissioning_pass"]["recorded_values"][field] = value
                with self.assertRaisesRegex(ValueError, expected):
                    readiness.validate_engineering_release_gates(row)

        typed = self.valid_commissioning()
        typed["gates"]["commissioning_motion_contact_limits_approved"]["recorded_values"][
            "minimum_clearance_mm"
        ] = "5.0"
        with self.assertRaisesRegex(ValueError, "JSON number"):
            readiness.validate_engineering_release_gates(typed)

    def test_commissioning_requires_bound_programs_and_implementations(self) -> None:
        valid = self.valid_commissioning()
        readiness.validate_engineering_release_gates(valid)
        for key in (
            "controller_model_and_firmware",
            "estop_implementation",
            "board_anti_shift_implementation",
            "homing_reference_procedure_path",
            "empty_cell_program_path",
            "final_process_program_path",
        ):
            with self.subTest(key=key):
                row = self.valid_commissioning()
                row["gates"]["commissioning_motion_contact_limits_approved"]["recorded_values"][key] = None
                with self.assertRaisesRegex(ValueError, key):
                    readiness.validate_engineering_release_gates(row)
        stale = self.valid_commissioning()
        stale["gates"]["commissioning_motion_contact_limits_approved"]["recorded_values"][
            "empty_cell_program_sha256"
        ] = "0" * 64
        with self.assertRaisesRegex(ValueError, "stale"):
            readiness.validate_engineering_release_gates(stale)

    def test_public_measurement_validator_invokes_engineering_checks(self) -> None:
        record = copy.deepcopy(self.record)
        record["test_context"] = {
            "operator": "tester",
            "date": "2026-08-31",
            "printer_serial": "QIDI-TEST",
            "measurement_tool_id": "CAL-1",
            "evidence_directory": "BUILD_BY_STEP/evidence/test",
            "qidi_studio_version": "test",
        }
        approval = record["gates"]["phone_no_go_clearance_limit_approved"]
        approval["status"] = "PASS"
        self.approve_metadata(approval["recorded_values"], "PHONE-CLEAR-BAD")
        approval["recorded_values"].update(
            {"minimum_clearance_mm": -1.0, "maximum_measurement_uncertainty_mm": 0.1}
        )
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            readiness.validate_measurement_record(record, self.jobs)


if __name__ == "__main__":
    unittest.main()
