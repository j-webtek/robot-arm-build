"""Host review for the fixed r48 mapping batch; no generic target API."""
from __future__ import annotations

import json
from pathlib import Path

from .characterization_matched_runner import MatchedRunner
from .characterization_reference import decode_reference
from .local_pair_mapping_batch import (
    INITIAL_GOALS,
    INITIAL_POSITIONS,
    INITIAL_TOLERANCE,
    plan_mapping_batch,
)
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


class LocalPairMappingRunner(MatchedRunner):
    """Run and summarize only the reviewed twelve-leg encoder mapping route."""

    plan_factory = staticmethod(plan_mapping_batch)
    initial_goals = INITIAL_GOALS
    initial_positions = INITIAL_POSITIONS
    initial_tolerance = INITIAL_TOLERANCE
    start_attachment = "local-pair-mapping-start.json"
    result_attachment = "local-pair-mapping-result.json"
    result_schema = "rocell.local_pair_mapping_result.v1"

    @property
    def targets(self):
        return self.plan_factory()["manifest"]["goals"]

    @staticmethod
    def _near(actual, expected, tolerance):
        return all(abs(a - e) <= tolerance for a, e in zip(actual, expected))

    def _export(self, name, document):
        exporter = WizardDiagnosticExporter(self.root.resolve())
        exporter.prepare(create=True)
        saved = exporter.export(
            {"mode": "local-pair-mapping-evidence"},
            [],
            attachments={name: json.dumps(document, indent=2).encode()},
        )
        if not verify_export(Path(saved["path"]))["valid"]:
            raise ValueError("Mapping evidence export verification failed")
        return saved["path"]

    def review(self, raw, challenge):
        reference = decode_reference(raw, expected_sha256=challenge["reference"])
        joints = reference["poses"][-1]["joints"]
        anchor = [joint["position"] for joint in joints]
        goals = [joints[index]["goal"] for index in (1, 2)]
        if challenge["manifest"]["goals"] != self.targets:
            raise ValueError("Exact mapping batch manifest required")
        if goals != list(self.initial_goals) or not self._near(
            anchor[1:3], self.initial_positions, self.initial_tolerance
        ):
            raise ValueError("Mapping batch starting state differs")
        if any(abs(target[j] - anchor[j + 1]) > 32 for target in self.targets for j in range(2)):
            raise ValueError("Mapping batch target exceeds anchor envelope")
        frozen = self.plan_factory()
        plan_export = self._export(
            self.start_attachment,
            {
                "plan": frozen,
                "boot": self.boot,
                "campaign": challenge["campaign"],
                "reference_sha256": challenge["reference"],
                "measured_anchor": anchor,
                "movement_authorized": False,
            },
        )
        return {
            "measured_anchor": anchor,
            "maximum_selected_excursion_counts": 32,
            "maximum_neighbour_excursion_counts": 2,
            "mapping_plan_sha256": frozen["plan_sha256"],
            "plan_export": plan_export,
            "movement_authorized": False,
            "physical_clearance_verified": False,
        }

    def check_result(self, report, result):
        super().check_result(report, result)
        record = json.loads(
            (Path(result["export_path"]) / "attachment-characterization-result.json").read_text()
        )
        if record["goals"] != self.targets:
            raise ValueError("Mapping result manifest differs")
        leg = record["leg"]
        baseline = record["baseline"]["joints"]
        endpoint = record["observations"][-1]["joints"]
        target = self.targets[leg]
        baseline_goals = [baseline[index]["goal"] for index in (1, 2)]
        baseline_positions = [baseline[index]["position"] for index in (1, 2)]
        actual = [endpoint[index]["position"] for index in (1, 2)]
        command_delta = target[0] - baseline_goals[0]
        report.setdefault("mapping_rows", []).append(
            {
                "leg": leg,
                "source_export": result["export_path"],
                "target": target,
                "approach_direction": 1 if command_delta > 0 else -1,
                "command_delta": [target[i] - baseline_goals[i] for i in range(2)],
                "baseline_goals": baseline_goals,
                "baseline_positions": baseline_positions,
                "actual": actual,
                "target_residual": [actual[i] - target[i] for i in range(2)],
                "assessment": result["assessment"],
            }
        )

    def run(self, **kwargs):
        result = super().run(**kwargs)
        rows = result["report"].get("mapping_rows", [])
        if result["report"]["status"] == "COMPLETE" and len(rows) == len(self.targets):
            grouped = {}
            for row in rows:
                grouped.setdefault(str(row["target"][0]), []).append(row["actual"])
            summary = {
                "schema": self.result_schema,
                "source_run": result["export_path"],
                "plan_sha256": self.plan_factory()["plan_sha256"],
                "rows": rows,
                "repeated_endpoints": {key: values for key, values in grouped.items() if len(values) > 1},
                "model_fitted": False,
                "compensation_promoted": False,
                "general_compensation_validated": False,
            }
            result["mapping_export"] = self._export(self.result_attachment, summary)
        return result
