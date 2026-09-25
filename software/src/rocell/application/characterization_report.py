"""Pure presentation of batch review results; no files, devices or simulation.

Kept separate so the CLI and a future wizard panel can render the same review
without either owning the experiment or recomputing its classification.
"""


def render_batch_review(summary: dict) -> str:
    """Render the current synthetic review schema, explicitly stating its scope."""
    if (summary.get('schema') != 'rocell.characterization_batch_review.v1'
            or summary.get('basis') != 'SYNTHETIC_ONLY'
            or summary.get('movement_authorized') is not False):
        raise ValueError('Unsupported review schema or evidence scope')
    lines = [
        '# Campaign endpoint review', '',
        '**Synthetic simulation only — not a physical accuracy test.**', '',
        f"Campaign state: {summary['campaign_state']}. No compensation applied.", '',
        'All positions and errors below are encoder counts, not millimetres.', '',
        '| Servo | Target | Direction | Speed | Acceleration | Repeats | Mean error | Max absolute error | Endpoint spread |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- |',
    ]
    for row in summary['grouped_endpoints']:
        direction = '+' if row['approach_direction'] > 0 else '-'
        lines.append(
            f"| {row['servo_id']} | {row['target_counts']} | {direction} | "
            f"{row['speed']} | {row['acceleration']} | {row['samples']} | "
            f"{row['mean_error_counts']:.3f} | {row['max_absolute_error_counts']} | "
            f"{row['endpoint_range_counts']} |")
    lines += ['', '## Interpretation', '',
              'Small endpoint spread means repeatable observations at that target; '
              'it does not mean the target was reached accurately.', '',
              'Compare opposite approach directions at the same target before '
              'attributing an error to direction. Do not infer stylus-tip accuracy.', '',
              '## Excluded legs', '']
    excluded = summary['excluded_legs']
    lines += ([f"- Leg {row['leg_id']}: {row['reason']}" for row in excluded]
              if excluded else ['None.'])
    if 'source_manifest_sha256' in summary:
        lines += ['', 'Source export manifest SHA-256:', '',
                  f"`{summary['source_manifest_sha256']}`"]
    return '\n'.join(lines) + '\n'
