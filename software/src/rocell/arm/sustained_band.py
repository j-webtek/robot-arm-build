"""Offline sampled-telemetry assessment; never grants motion or physical accuracy.

Call only after reconstructing original response bodies. Host request/response
bounds do not establish device freshness or continuous physical position.
"""
import math


def assess_sustained_band(samples, *, desired_rad, band_deg, required_duration_s,
                          maximum_gap_s=1.0):
    """Measure in-band runs conservatively from first response to last request.

An out-of-band sample or excessive response-to-response gap breaks a run.
Earlier qualifying runs cannot qualify the final suffix after a later excursion.
This is sampled evidence, not proof about positions between observations.
"""
    settings = (desired_rad, band_deg, required_duration_s, maximum_gap_s)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
           not math.isfinite(v) for v in settings):
        raise ValueError('Finite numeric settings required')
    if min(band_deg, required_duration_s, maximum_gap_s) <= 0:
        raise ValueError('Band, duration and gap must be positive')
    if not samples:
        raise ValueError('Nonempty reconstructed samples required')
    rows = []
    for sample in samples:
        begin = sample['request_started_monotonic_s']
        end = sample['response_finished_monotonic_s']
        value = sample['joints_rad']['r']
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
               not math.isfinite(v) for v in (begin, end, value)):
            raise ValueError('Finite numeric observations required')
        if begin > end or (rows and begin < rows[-1][1]):
            raise ValueError('Ordered nonoverlapping response bounds required')
        if sample.get('status', 'SUCCEEDED') != 'SUCCEEDED':
            raise ValueError('Successful reconstructed observations required')
        rows.append((begin, end, abs(value-desired_rad) <= math.radians(band_deg)))
    runs = []
    start = None
    gaps = []
    for i, (begin, end, inside) in enumerate(rows):
        gap = i > 0 and end-rows[i-1][1] > maximum_gap_s
        if gap:
            gaps.append(i)
        if start is not None and (gap or not inside):
            runs.append((start, i-1))
            start = None
        if inside and start is None:
            start = i
    if start is not None:
        runs.append((start, len(rows)-1))
    def duration(run):
        return max(0.0, rows[run[1]][0]-rows[run[0]][1])
    suffix = runs[-1] if runs and runs[-1][1] == len(rows)-1 else None
    suffix_s = duration(suffix) if suffix else 0.0
    coverage = max(0.0, rows[-1][0]-rows[0][1])
    all_inside = all(row[2] for row in rows)
    return dict(schema='rocell.sustained_band.v1', band_deg=band_deg,
        required_duration_s=required_duration_s, maximum_gap_s=maximum_gap_s,
        sample_count=len(rows), observed_response_span_s=rows[-1][1]-rows[0][1],
        conservative_observation_span_s=coverage,
        gap_break_sample_indices=gaps, all_samples_in_band=all_inside,
        longest_in_band_run_s=max((duration(r) for r in runs), default=0.0),
        final_in_band_run_s=suffix_s,
        final_sampled_run_qualifies=suffix_s >= required_duration_s,
        entire_sampled_window_qualifies=(all_inside and not gaps and
                                        coverage >= required_duration_s),
        physical_continuity_verified=False, device_sample_freshness_verified=False,
        motion_authorized=False)
