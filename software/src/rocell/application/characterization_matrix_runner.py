"""Offline matrix runner. No live CLI or board selection is enabled here."""
from .characterization_matched_runner import MatchedRunner
from .characterization_reference import decode_reference
from .shoulder_movement_matrix import draft_matrix


class MatrixRunner(MatchedRunner):
    def review(self, raw, challenge):
        reference = decode_reference(raw, expected_sha256=challenge['reference'])
        joints = reference['poses'][-1]['joints']
        anchor = [joint['position'] for joint in joints]
        matrix = draft_matrix([joints[i]['goal'] for i in (1, 2)], anchor[1:3])
        if challenge['manifest']['goals'] != [leg['targets'] for leg in matrix['legs']]:
            raise ValueError('Exact twelve-leg variant matrix required')
        return dict(measured_anchor=anchor, maximum_selected_excursion_counts=32,
                    maximum_neighbour_excursion_counts=2, movement_authorized=False,
                    physical_clearance_verified=False, live_qualified=False,
                    matrix=matrix)
