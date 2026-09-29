import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("stage_system_print_pack.py")
SPEC = importlib.util.spec_from_file_location("stage_system_print_pack", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SystemPrintPackStageTests(unittest.TestCase):
    def test_tracked_references_are_hash_bound_and_targets_are_not_tracked_copies(self):
        references = MODULE.load_references()
        MODULE.verify_sources(references)
        self.assertEqual(7, len(references))
        for entry in references:
            self.assertFalse((MODULE.PACK_ROOT / entry["target"]).exists())

    def test_standalone_stage_has_reference_and_sidecar_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "SYSTEM_PRINT_PACK_v1"
            receipt = MODULE.stage(output)
            self.assertEqual("PASS", receipt["status"])
            self.assertEqual(7, receipt["reference_count"])
            self.assertGreater(receipt["sidecar_stl_dependencies_verified"], 0)
            self.assertTrue((output / "verify_system_print_pack.py").is_file())
            verified = MODULE.verify_staged(output, MODULE.load_references(output))
            self.assertEqual(receipt, verified)

    def test_source_hash_mismatch_fails_closed(self):
        references = MODULE.load_references()
        altered = json.loads(json.dumps(references))
        altered[0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(MODULE.PackError, "hash mismatch"):
            MODULE.verify_sources(altered)

    def test_existing_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(MODULE.PackError, "must not already exist"):
                MODULE.stage(Path(temporary))


if __name__ == "__main__":
    unittest.main()
