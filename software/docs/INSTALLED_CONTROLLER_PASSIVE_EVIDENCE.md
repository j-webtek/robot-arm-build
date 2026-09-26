# Installed-controller passive evidence candidate

This procedure collects the narrowest useful S4 controller evidence without
opening the serial port, restarting the controller, sending a command, or moving
the arm. It is a precursor to independent review, not qualification.

The r96 collector performs exactly one HTTP `GET` with no retry against the
fixed capability endpoint. It accepts only the reviewed one-leg application
shape: one maximum leg, no automatic progression, no gripper writes, and motion
unauthorized. It then correlates that live boot with these retained originals:

- exact r96 app bytes;
- the one-attempt installation journal and protected-region check;
- the final diagnostic export manifest; and
- the final registration feedback attachment.

The resulting local record is excluded from Git because it includes a physical
USB instance identity. Its schema permanently fixes `UNREVIEWED`, zero writes,
zero movement, no serial open, no restart, and no transport/execution authority.
It cannot be edited into an approved qualification record while remaining schema
valid.

Run only after separately authorizing one passive controller observation:

```powershell
$env:PYTHONPATH='software/src'
python software/scripts/capture_r96_passive_evidence.py `
  --output software/runs/installed-controller-qualification/r96-passive.json `
  --usb-port COM7 `
  --usb-pnp-instance-id '<freshly observed exact PnP instance id>'
```

The collector deliberately leaves these blockers:

1. independent review is not complete;
2. the running firmware does not attest its own app hash;
3. controller-to-planner joint mapping evidence is not bound;
4. qualified T=102 protocol-source evidence is not bound;
5. startup behavior review is not bound;
6. T=1051 feedback protocol review is not bound; and
7. a configuration epoch is not established.

An independent reviewer must inspect the retained originals and close each
blocker with separately hashed evidence. Only then may another tool construct
`rocell.installed_controller_qualification_evidence.v1` and evaluate the
qualification gate. Even a passing gate grants only zero-write profile binding;
it never grants transport or execution authority.

