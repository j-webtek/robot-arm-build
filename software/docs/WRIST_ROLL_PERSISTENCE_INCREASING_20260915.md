# Increasing wrist-roll persistence: live result

One increasing one-degree v19 command completed through the wizard, followed by
35 seconds in the same owned connection. No compensation, retry, return, or
additional positioning was applied. No motion software changed for this trial.

| Measurement | Degrees |
| --- | ---: |
| Fresh start | +0.263671854 |
| Raw absolute command | +1.263671854 |
| Reported endpoint at 5, 10, 20 and 35 seconds | +1.230468748 |
| Signed command error | -0.033203106 |
| Reported change after five seconds | 0 |
| Separate reconnect endpoint | +1.230468748 |

All five other joints reported zero drift. There were 1,947 post-command pose
records (284/562/1117/1947 through the four horizons), 395,567 raw post bytes and
2,202 post reads. Largest host gap was 63 ms. Reported quiet-entry bounds were
406–437 ms after the write, not independently measured physical settling time.

One complete 64-byte command was submitted with no uncertainty. All handles
closed within budget, no I/O remained pending, and portable original integrity,
full reconstruction and endpoint completion passed. The subsequent separate
baseline sent zero command bytes; all decoded roll values and the final six-joint
pose matched the continuous-capture endpoint. No reconnect change was observed.

## Original evidence

- Starting baseline: `operation-99eedaa5551743129c7fabef04116bee`.
- Campaign: `campaign-8e69010a84ae4ad2b8775c6cf1fd9df9`.
- Report SHA256: `0c6a85363feff26896b40f96dc9f2a9302d78ebccd3837eb1e877c0254923402`.
- Raw export: `software/runs/wizard-exports/campaign-8e69010a84ae4ad2b8775c6cf1fd9df9/`.
- Reconnect baseline: `operation-597a53cd0def417285003043a3fd5398`.
- Derived results with lifecycle, original hashes, horizon evidence and reconnect
  comparison: `software/runs/WRIST_ROLL_PERSISTENCE_INCREASING_20260915.json`.

Final [b,s,e,t,r,g] radians:

```text
[0.007669904,0,1.593806039,0.047553404,0.021475731,3.149262558]
```

Roll command count is nine; base remains 44.

## Meaning

Both recent directions have persistent reported endpoints and matching reconnect
captures. This does not explain or invalidate the earlier delayed discrepancy:
these trials used different starts and targets. The increasing error here is
smaller than earlier increasing errors, without any correction being applied.
Therefore do not assume one universal directional offset or claim the software
has improved physical accuracy. Tool-tip position remains independently unmeasured.

Next: repeat fixed command/start pairs with the long observation profile before
fitting a model. See [fixed long-window repeat plan](WRIST_ROLL_LONG_FIXED_REPEAT_PLAN_20260915.md).
