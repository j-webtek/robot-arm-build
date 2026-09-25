"""Offline comparison of four explicitly selected recent long-window trials."""
import json
import math
from pathlib import Path
import runpy

PINS=(
    ('campaign-83563fca6ffc425ab12d94061c3c7bb0','dd29aad9a417490e5c277246e3824b0bdaa1ec8443d9b0b6f0bc3a08d202585f'),
    ('campaign-e621169d1a9147158c32c043e17022f8','262df257dd73f9e0f79d3fb825d6a885fea3053ae2d6fd89a21220cdc3b28017'),
    ('campaign-562c2a5eb4c043899a583ec0c4da329e','532bbf41a2f41f11bb9dc9176fe34068668031c85243129b5c51bf0898d8dfe5'),
    ('campaign-20bc8b3f7d764bc599e8fc0ac6d03f97','3bee0038fe2b0710dc1034dd84f08d95db3f760b52e46f36e52804f67ed36e49'),
)


def review():
    helpers=runpy.run_path(str(Path(__file__).with_name('review_roll_return_pair_20260915.py')))
    require=helpers['require']
    rows=[helpers['read_trial'](*pin) for pin in PINS]
    require(len({r['campaign_id'] for r in rows})==4,'Distinct trials required')
    for previous,following in zip(rows,rows[1:]):
        require(previous['final']==following['start'],'Reported handoff changed')
    pairs=[]
    for left,right in ((rows[0],rows[2]),(rows[1],rows[3])):
        for key in ('start','command','schema'):
            require(left[key]==right[key],'Pair differs: '+key)
        matches={k:left['references'][k]==right['references'][k] for k in left['references']}
        for key in ('source_sha256','configuration_sha256','native_controller_review_sha256',
                    'protocol_review_sha256','workcell_sha256','tool_payload_sha256','bounded_motion_risk_sha256'):
            require(matches[key],'Context mismatch: '+key)
        # Keep per-run baseline/runtime identity differences visible. A matching
        # source hash is not a claim of identical process registration bytes.
        pairs.append(dict(direction=left['endpoint']['direction'],sample_count=2,
            campaigns=[left['campaign_id'],right['campaign_id']],reference_matches=matches,
            command_rad=left['command']['rad'],start_rad=left['start'][4],
            final_rad=[r['final'][4] for r in (left,right)],
            signed_errors_deg=[math.degrees(r['endpoint']['signed_error_rad']) for r in (left,right)],
            reported_travel_deg=[math.degrees(r['final'][4]-r['start'][4]) for r in (left,right)],
            reported_endpoint_spread_deg=abs(math.degrees(right['final'][4]-left['final'][4]))))
    return dict(schema='rocell.roll_recent_repeat_screen.v1',trials=rows,pairs=pairs,
        trials_selected='Four consecutive recent v19 trials; older differing results retained separately',
        compensation_fitted=False,compensation_applied=False,
        physical_accuracy_verified=False,motion_authorized=False)


if __name__=='__main__':
    print(json.dumps(review(),indent=2))
