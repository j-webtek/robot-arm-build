"""Offline-qualified matched runner; deliberately not wired to the live CLI."""
from .characterization_smoke_runner import SmokeRunner
from .characterization_reference import decode_reference
from .shoulder_characterization import draft_manifest


class MatchedRunner(SmokeRunner):
    def review(self, raw, challenge):
        reference=decode_reference(raw,expected_sha256=challenge['reference'])
        joints=reference['poses'][-1]['joints']
        anchor=[j['position'] for j in joints]
        expected=[leg['command_goals'] for leg in
                  draft_manifest([joints[1]['goal'],joints[2]['goal']],pattern='matched')['legs']]
        if challenge['manifest']['goals']!=expected:
            raise ValueError('Exact twelve-leg matched pattern required')
        for targets in expected:
            if any(abs(targets[i]-anchor[i+1])>32 for i in range(2)):
                raise ValueError('Campaign target exceeds total excursion envelope')
        return dict(measured_anchor=anchor,maximum_selected_excursion_counts=32,
                    maximum_neighbour_excursion_counts=2,movement_authorized=False,
                    physical_clearance_verified=False,live_qualified=False)

    def check_result(self, report, result):
        anchor=report['baseline_review']['measured_anchor']
        # Inspect every retained observation, not only the final endpoint. This
        # host check withholds continuation; it is not a real-time motion stop.
        import json
        from pathlib import Path
        record=json.loads((Path(result['export_path'])/'attachment-characterization-result.json').read_text())
        for pose in [record['baseline'],*record['observations']]:
            for i,joint in enumerate(pose['joints']):
                if abs(joint['position']-anchor[i])>(32 if i in (1,2) else 2):
                    raise ValueError('Measured campaign excursion exceeded; no receipt')
