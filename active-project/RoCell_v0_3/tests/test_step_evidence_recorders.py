from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_step_packages as packages  # noqa: E402
import record_step_result as recorder  # noqa: E402
import sign_off_step as signer  # noqa: E402
import step_evidence_common as common  # noqa: E402


class StepEvidenceRecorderTests(unittest.TestCase):
    @contextmanager
    def fixture(self, *, test_ids: tuple[str, ...] = ("03-A",)):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "BUILD_BY_STEP"
            package.mkdir()
            sentinel = package / packages.SENTINEL
            sentinel.write_text(f"layout_version={packages.LAYOUT_VERSION}\n", encoding="utf-8")
            active = package / packages.ACTIVE_BUILD_FILE
            active.write_text(
                json.dumps({"schema_version": 1, "active_build_id": "BUILD-1"}),
                encoding="utf-8",
            )
            folder_name = "03 - Friendly Step"
            index = package / "INDEX.json"
            index.write_text(
                json.dumps(
                    {
                        "layout_version": packages.LAYOUT_VERSION,
                        "steps": [{"id": "03", "folder": folder_name}],
                    }
                ),
                encoding="utf-8",
            )
            step_dir = package / folder_name
            manifest_path = step_dir / packages.STEP_MANIFEST_FILE
            manifest_path.parent.mkdir(parents=True)
            digest = "a" * 64
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "layout_version": packages.LAYOUT_VERSION,
                        "design_revision": "RC03-INT-R1",
                        "step_id": "03",
                        "active_build_id": "BUILD-1",
                        "package_definition_hash": digest,
                        "canonical_snapshot_hash": "b" * 64,
                    }
                ),
                encoding="utf-8",
            )
            build_dir = step_dir / packages.STEP_EVIDENCE_DIRECTORY / "BUILD-1"
            (build_dir / "photos").mkdir(parents=True)
            (build_dir / "photos" / "proof.jpg").write_bytes(b"proof")
            common_values = {
                "schema_version": 1,
                "design_revision": "RC03-INT-R1",
                "package_definition_hash": digest,
                "canonical_snapshot_hash": "b" * 64,
                "canonical_input_hash": "b" * 64,
                "step_id": "03",
                "build_id": "BUILD-1",
            }
            measurement_path = build_dir / packages.MEASUREMENT_RECORD_FILE
            measurement_path.write_text(
                json.dumps(
                    {
                        **common_values,
                        "operator": None,
                        "started_at": None,
                        "instrument_ids": [],
                        "measurements": [
                            {
                                "test_id": test_id,
                                "criterion": f"Criterion {test_id}",
                                "value_or_observation": None,
                                "unit": None,
                                "instrument_id": None,
                                "evidence_files": [],
                                "result": "NOT_TESTED",
                                "notes": None,
                            }
                            for test_id in test_ids
                        ],
                        "evidence_files": [],
                        "corrections_and_retests": [],
                    }
                ),
                encoding="utf-8",
            )
            signoff_path = build_dir / packages.SIGNOFF_RECORD_FILE
            signoff_path.write_text(
                json.dumps(
                    {
                        **common_values,
                        "status": "NOT_STARTED",
                        "required_test_ids": list(test_ids),
                        "accepted_test_ids": [],
                        "open_holds": [],
                        "operator": None,
                        "witness": None,
                        "signed_at": None,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.multiple(
                common,
                PACKAGE=package,
                SENTINEL=sentinel,
                ACTIVE_PATH=active,
                INDEX_PATH=index,
            ):
                yield build_dir, measurement_path, signoff_path

    @staticmethod
    def record_args(**overrides):
        values = {
            "step": "03",
            "test": "03-A",
            "value": "seats by hand; no rocking",
            "unit": "N/A",
            "instrument": "visual inspection",
            "evidence": ["photos/proof.jpg"],
            "result": "PASS",
            "operator": "operator-a",
            "notes": None,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    @staticmethod
    def sign_args(**overrides):
        values = {
            "step": "03",
            "status": "PASS",
            "operator": "operator-a",
            "witness": None,
            "hold": None,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_records_and_traceably_updates_one_row(self) -> None:
        with self.fixture() as (_, measurement_path, signoff_path):
            recorder.record_result(self.record_args())
            first = json.loads(measurement_path.read_text(encoding="utf-8"))
            signoff = json.loads(signoff_path.read_text(encoding="utf-8"))
            self.assertEqual(first["measurements"][0]["result"], "PASS")
            self.assertEqual(first["measurements"][0]["evidence_files"], ["photos/proof.jpg"])
            self.assertEqual(first["instrument_ids"], ["visual inspection"])
            self.assertEqual(signoff["status"], "IN_PROGRESS")
            self.assertEqual(signoff["accepted_test_ids"], ["03-A"])

            recorder.record_result(
                self.record_args(value="retested; still seats freely", notes="Repeatability retest")
            )
            second = json.loads(measurement_path.read_text(encoding="utf-8"))
            self.assertEqual(second["measurements"][0]["value_or_observation"], "retested; still seats freely")
            self.assertEqual(len(second["corrections_and_retests"]), 1)
            self.assertEqual(second["corrections_and_retests"][0]["reason"], "Repeatability retest")

    def test_invalid_or_missing_evidence_leaves_record_unchanged(self) -> None:
        with self.fixture() as (build_dir, measurement_path, _):
            before = measurement_path.read_bytes()
            for evidence in (
                ["photos/missing.jpg"],
                ["../outside.jpg"],
                [str((build_dir / "photos" / "proof.jpg").resolve())],
                ["photos"],
                [packages.MEASUREMENT_RECORD_FILE],
                [packages.SIGNOFF_RECORD_FILE],
            ):
                with self.subTest(evidence=evidence):
                    with self.assertRaises(common.EvidenceError):
                        recorder.record_result(self.record_args(evidence=evidence))
                    self.assertEqual(measurement_path.read_bytes(), before)

    def test_duplicate_evidence_paths_are_normalized_once(self) -> None:
        with self.fixture() as (_, measurement_path, _):
            recorder.record_result(
                self.record_args(evidence=["photos/proof.jpg", "photos/./proof.jpg"])
            )
            measurement = json.loads(measurement_path.read_text(encoding="utf-8"))
            self.assertEqual(measurement["measurements"][0]["evidence_files"], ["photos/proof.jpg"])

    def test_pass_requires_every_complete_row_and_existing_evidence(self) -> None:
        with self.fixture() as (build_dir, _, signoff_path):
            before = signoff_path.read_bytes()
            with self.assertRaises(common.EvidenceError):
                signer.sign_off(self.sign_args())
            self.assertEqual(signoff_path.read_bytes(), before)

            recorder.record_result(self.record_args())
            result = signer.sign_off(self.sign_args(witness="reviewer"))
            self.assertEqual(result["status"], "PASS")
            signed = json.loads(signoff_path.read_text(encoding="utf-8"))
            self.assertEqual(signed["accepted_test_ids"], ["03-A"])
            self.assertEqual(signed["witness"], "reviewer")

            (build_dir / "photos" / "proof.jpg").unlink()
            with self.assertRaises(common.EvidenceError):
                signer.sign_off(self.sign_args())

    def test_hold_requires_reason_and_preserves_recorded_results(self) -> None:
        with self.fixture() as (_, _, signoff_path):
            recorder.record_result(self.record_args())
            before = signoff_path.read_bytes()
            with self.assertRaises(common.EvidenceError):
                signer.sign_off(self.sign_args(status="HOLD", hold=None))
            self.assertEqual(signoff_path.read_bytes(), before)

            signer.sign_off(self.sign_args(status="HOLD", hold=["fixture moved during test"]))
            signed = json.loads(signoff_path.read_text(encoding="utf-8"))
            self.assertEqual(signed["status"], "HOLD")
            self.assertEqual(signed["accepted_test_ids"], ["03-A"])
            self.assertEqual(signed["open_holds"], ["fixture moved during test"])

    def test_fresh_hold_establishes_started_measurement_identity(self) -> None:
        with self.fixture() as (_, measurement_path, signoff_path):
            signer.sign_off(self.sign_args(status="HOLD", hold=["input fixture is damaged"]))
            measurement = json.loads(measurement_path.read_text(encoding="utf-8"))
            signoff = json.loads(signoff_path.read_text(encoding="utf-8"))
            self.assertEqual(measurement["operator"], "operator-a")
            self.assertTrue(measurement["started_at"])
            self.assertEqual(signoff["status"], "HOLD")

    def test_mismatched_record_identity_fails_without_writing(self) -> None:
        with self.fixture() as (_, measurement_path, signoff_path):
            signoff = json.loads(signoff_path.read_text(encoding="utf-8"))
            signoff["build_id"] = "WRONG"
            signoff_path.write_text(json.dumps(signoff), encoding="utf-8")
            before = measurement_path.read_bytes()
            with self.assertRaises(common.EvidenceError):
                recorder.record_result(self.record_args())
            self.assertEqual(measurement_path.read_bytes(), before)

    def test_helper_results_and_signoff_feed_computed_step_state(self) -> None:
        step = {
            "id": "03",
            "prerequisite_steps": [],
            "input_gates": [],
            "completion_gates": [],
            "acceptance": [{"test_id": "03-A", "criterion": "Criterion 03-A"}],
        }
        measurement = {"design_revision": "RC03-INT-R1", "selected_routes": {}, "gates": {}}
        for result in ("PASS", "FAIL"):
            with self.subTest(result=result), self.fixture() as (build_dir, _, _):
                recorder.record_result(self.record_args(result=result))
                state, blockers = packages.compute_state(
                    step,
                    measurement,
                    build_dir.parents[1],
                    {},
                    "BUILD-1",
                    "a" * 64,
                )
                self.assertEqual((state, blockers), ("IN_PROGRESS", []))
                if result == "PASS":
                    signer.sign_off(self.sign_args())
                    state, blockers = packages.compute_state(
                        step,
                        measurement,
                        build_dir.parents[1],
                        {},
                        "BUILD-1",
                        "a" * 64,
                    )
                    self.assertEqual((state, blockers), ("COMPLETE", []))

    def test_fresh_helper_hold_feeds_computed_hold_state(self) -> None:
        step = {
            "id": "03",
            "prerequisite_steps": [],
            "input_gates": [],
            "completion_gates": [],
            "acceptance": [{"test_id": "03-A", "criterion": "Criterion 03-A"}],
        }
        measurement = {"design_revision": "RC03-INT-R1", "selected_routes": {}, "gates": {}}
        with self.fixture() as (build_dir, _, _):
            signer.sign_off(self.sign_args(status="HOLD", hold=["input fixture is damaged"]))
            state, blockers = packages.compute_state(
                step,
                measurement,
                build_dir.parents[1],
                {},
                "BUILD-1",
                "a" * 64,
            )
            self.assertEqual(state, "HOLD")
            self.assertEqual(blockers, [])


if __name__ == "__main__":
    unittest.main()
