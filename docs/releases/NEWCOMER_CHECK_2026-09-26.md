# Hardware-free newcomer check — September 26, 2026

Related task: [#24](https://github.com/j-webtek/robot-arm-build/issues/24).
Source checked: `28aef3d2ab6c7c52e0040ca6fdce48d13ecef8d5`.
This is setup evidence, not a release, UI acceptance certification, or hardware test.

## Environment and isolation

- Fresh detached Git worktree of that merged commit, with a new root `.venv`.
  Tracked files were clean before and after testing. No private lab files were copied.
- Windows build 26200, PowerShell 7.6.5, Python 3.10.10.
- Editable base installation: rocell 0.1.0, Pillow 12.3.0, packaging 26.3;
  pip 22.3.1 and setuptools 65.5.0 in the environment.
- Package installation used PyPI with a process-only `PIP_EXTRA_INDEX_URL`
  override to avoid the workstation's unrelated secondary index. No persistent
  package configuration or system execution policy was changed.

A worktree tests clean tracked source, not a fresh network clone or Git download
performance. This is one Windows/Python combination; Linux/macOS browser behavior,
Windows PowerShell 5.1, and newer Python versions were not tested here.

## Commands and observations

Commands ran from the checkout root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e './software'
.\.venv\Scripts\python -m pip check
.\.venv\Scripts\python software/ai/run_offline.py ground --request 'Type "hi" on the keyboard'
.\.venv\Scripts\python software/ai/run_offline.py coordinate-preview --request 'Type "hi" on the keyboard'
$startupCheck = .\start-rocell-wizard.ps1 -Check | ConvertFrom-Json
$startupCheck | Select-Object mode, status, verification
.\start-rocell-wizard.ps1 -Ui terminal
```

| Check | Observed result |
| --- | --- |
| Base installation | Completed; `pip check` reported no broken requirements |
| Grounded request | Accepted; literal `hi` preserved; H then I |
| Coordinate preview | H then I; nominal unmeasured geometry; empty controller commands; execution unauthorized |
| Wizard preflight | Rehearsal; `READY_FOR_DIAGNOSTICS`; `DIAGNOSTIC_ONLY_NOT_RECEIVED_UNIT_VERIFIED` |
| Terminal launcher | Started and exited with code 0 after `quit`; no action selected |
| Local HTTP smoke | Rehearsal service and bundled server on an ephemeral loopback port returned HTTP 200, `text/html`, 3,591 bytes at `/`; server closed and thread joined |

Terminal input was supplied through a subprocess's stdin. An earlier PowerShell
pipeline attempt could not bind `quit` to the script's parameters and reached
EOF instead; that harness attempt is not the successful explicit-quit result.

The HTTP smoke used `ArrivalWizardService`, `create_wizard_server`,
`start_in_thread`, a read-only request to `/`, then `close` and thread join.
It did not launch a graphical browser, test authenticated UI interactions,
execute actions, or create diagnostic exports. Session URLs were not published.

## Documentation outcome

README navigation was checked through getting started, current status,
contribution guidance and support. Maintained local-link checking passed.
The guide now states expected result fields, offers a short preflight projection,
explains normal missing-execution prerequisites, and documents terminal exit and
the existing no-browser fallback. No runtime fix was needed for the tested path.

No camera, serial connection, model service, firmware operation or physical
movement was used. A first-run software pass does not close calibration,
controller qualification, contact testing, or release-readiness requirements.
