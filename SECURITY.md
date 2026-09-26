# Tactevra security reporting

## Report privately

Please use [GitHub private vulnerability reporting](https://github.com/j-webtek/robot-arm-build/security/advisories/new)
for suspected security vulnerabilities. Private reporting was enabled and checked
on September 26, 2026. You need a GitHub account to submit a report.

Do not put vulnerabilities, exploit details, credentials, or private device data
in public issues or pull requests. If the private form is unavailable, open a
public issue titled **Private reporting channel unavailable** without sensitive
details and ask the maintainer to restore it. No alternative private email
channel is currently published here.

Useful reports include:

- Affected commit or release, operating system, and relevant configuration with
  secrets removed.
- Expected behavior, observed behavior, and security impact.
- Minimal hardware-free reproduction, if possible, and the evidence that supports
  the finding. Identify simulation or modeled evidence explicitly.
- Whether any credentials or private information may have been exposed, without
  including the actual secret values.

Test only systems you own or are authorized to assess. Do not move an arm, bypass
an execution gate, or access someone else's devices to demonstrate a finding.

## What belongs here

Examples include unauthorized command execution, bypassed admission checks,
credential disclosure, unsafe handling of untrusted model output, and export or
dependency behavior that exposes private information. A vulnerability that could
enable unintended movement belongs in the private channel too. Ordinary setup
questions and non-sensitive defects belong in [support](SUPPORT.md).

## Maintenance and response expectations

Tactevra is experimental. The current `main` branch is the development baseline;
there is no maintained stable-version matrix, guaranteed response time, commercial
support agreement, or bug-bounty program stated by this project. Historical
firmware and hardware packages are retained as evidence, not a promise of ongoing
security maintenance. Report older-version issues with their exact identity so
they can be assessed against current development.

Maintainers should acknowledge and investigate reports in the private advisory,
agree on disclosure with the reporter, and publish remediation guidance when
available. Do not disclose a report publicly just because a local test passed.
If a secret was exposed, revoke or rotate it through the owning service; deleting
a file or commit alone does not invalidate the secret.

## Limits of repository checks

CI and the snapshot audit are scoped development checks, not security
certification or physical safety qualification. The snapshot audit is heuristic
and does not scan all Git history. Its [synthetic-fixture exceptions](docs/AUDIT_FIXTURE_REVIEW.md)
are individually reviewed and do not exempt arbitrary credentials. See
[verification tiers](docs/CI.md) for what each kind of test establishes.
