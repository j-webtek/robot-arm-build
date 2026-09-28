import unittest

from check_source_archive_footprint import TreeEntry
import inventory_source_archive_duplicates as inventory


class SourceArchiveDuplicateInventoryTests(unittest.TestCase):
    def test_ranks_by_avoidable_duplicate_bytes(self):
        entries = [
            TreeEntry("a" * 40, 200, "one.bin"),
            TreeEntry("a" * 40, 200, "two.bin"),
            TreeEntry("b" * 40, 150, "one.dat"),
            TreeEntry("b" * 40, 150, "two.dat"),
            TreeEntry("b" * 40, 150, "three.dat"),
        ]
        groups = inventory.inventory(entries, minimum_bytes=100)
        self.assertEqual("b" * 40, groups[0].object_id)
        self.assertEqual(300, groups[0].duplicate_bytes)

    def test_routes_rc03_step_copies_to_central_stl_candidate(self):
        central = "active-project/RoCell_v0_3/stl/gauge.stl"
        groups = inventory.inventory([
            TreeEntry("a" * 40, 200, central),
            TreeEntry(
                "a" * 40, 200,
                "active-project/RoCell_v0_3/BUILD_BY_STEP/00 - Start/03 - STL MODELS/gauge.stl",
            ),
        ], minimum_bytes=100)
        self.assertEqual("rc03-instructional-stl-copy", groups[0].classification)
        self.assertEqual((central,), groups[0].canonical_candidates)

    def test_cross_revision_group_is_not_treated_as_simple_step_copy(self):
        groups = inventory.inventory([
            TreeEntry("a" * 40, 200, "active-project/RoCell_v0_2/stl/gauge.stl"),
            TreeEntry("a" * 40, 200, "active-project/RoCell_v0_3/stl/gauge.stl"),
            TreeEntry(
                "a" * 40, 200,
                "active-project/RoCell_v0_3/BUILD_BY_STEP/00 - Start/03 - STL MODELS/gauge.stl",
            ),
        ], minimum_bytes=100)
        self.assertEqual(
            "cross-revision-and-instructional-stl", groups[0].classification)

    def test_routes_frozen_cross_revision_pair_to_current_canonical_stl(self):
        canonical = "active-project/RoCell_v0_3/stl/gauge.stl"
        groups = inventory.inventory([
            TreeEntry("a" * 40, 200, "active-project/RoCell_v0_2/stl/gauge.stl"),
            TreeEntry("a" * 40, 200, canonical),
        ], minimum_bytes=100)
        self.assertEqual(
            "frozen-cross-revision-stl-retention", groups[0].classification)
        self.assertEqual((canonical,), groups[0].canonical_candidates)
        self.assertIn("immutable historical evidence", groups[0].provenance_note)

    def test_routes_static_camera_outputs_without_asserting_canonical_path(self):
        groups = inventory.inventory([
            TreeEntry(
                "a" * 40, 200,
                "hardware/static_overhead_camera/cad/output/revisions/PACK/part.stl",
            ),
            TreeEntry(
                "a" * 40, 200,
                "hardware/static_overhead_camera/cad/output/stl/part.stl",
            ),
        ], minimum_bytes=100)
        self.assertEqual(
            "static-camera-packaged-output-copy", groups[0].classification)
        self.assertEqual(
            ("hardware/static_overhead_camera/cad/output/stl/part.stl",),
            groups[0].canonical_candidates,
        )

    def test_report_sums_groups_and_preserves_limitations(self):
        groups = inventory.inventory([
            TreeEntry("a" * 40, 200, "one.bin"),
            TreeEntry("a" * 40, 200, "two.bin"),
        ], minimum_bytes=100)
        payload = inventory.report(groups, "c" * 40, 100)
        self.assertEqual(inventory.SCHEMA, payload["schema"])
        self.assertEqual(200, payload["duplicate_bytes"])
        self.assertTrue(payload["limitations"])


if __name__ == "__main__":
    unittest.main()
