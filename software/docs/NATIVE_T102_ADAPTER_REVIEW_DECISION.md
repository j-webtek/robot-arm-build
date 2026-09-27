# Native T=102 adapter external-review decision intake

ARM-056 defines the closed document that may carry a genuinely independent
review of the exact ARM-055 packet back into the repository. The intake checks
structure, content identity, checklist completeness, disposition, declared
independence, open findings, and validity time. It does not create a review,
authenticate a person, open an endpoint, or authorize controller activity.

## Exact subject

The decision must bind all four identities:

- packet SHA-256
  `65749a9f122fd4f685375652b6e52a101038a88b0fed1c1b921aea6c4b059f0d`;
- manifest SHA-256
  `0aff3af9a167e82b792fd55ff6bdd544c6ee2b961109c1dac6d7cb34c17bba4b`;
- ARM-054 candidate commit
  `9bd17ac21d7fd00d18f3dd4378b9bea529b5b681`; and
- adapter source SHA-256
  `29cf25dd80c7560fb1613710fcef273466aba970b5b9333df3ed7bf9acbfafea`.

A mismatch in any identity blocks the decision. A decision also binds its
review start, completion, and expiration timestamps. Assessment before review
completion or at/after expiration blocks intake.

## Closed checklist

The reviewer records one Boolean result for each ordered check:

1. closed packet membership;
2. member hashes;
3. adapter source inspection;
4. pre/post-open endpoint identity;
5. serial settings and finite timeouts;
6. one canonical T=102 write;
7. bounded T=1021 and T=1051 capture;
8. no fallback, reopen, or retry;
9. ARM-053 authority consumption before open;
10. durable no-replay journal behavior; and
11. retention of all unqualified and unauthorized flags.

Approval requires every check to pass and no open findings. Rejection,
incomplete checks, an implementation-author conflict, or failure to assert
independence blocks the decision.

## Authority boundary

An accepted report sets only
`ready_for_read_only_endpoint_qualification_intake=true`. Both decision and
report keep the following false:

- endpoint open authorization;
- controller start authorization;
- execution authorization;
- hardware access; and
- physical authority.

The repository cannot establish reviewer identity or custody from a JSON claim.
Those remain external evidence obligations. `SYNTHETIC_TEST_ONLY` decisions are
accepted only as integration rehearsals and can never become endpoint-intake
ready.

The next milestone after a real accepted decision is a separately designed and
authorized read-only endpoint qualification. Movement remains out of scope.

## Offline exchange commands

Build a fresh reviewer directory from the repository root:

```powershell
$env:PYTHONPATH='software/src'
python software/scripts/build_arm054_adapter_review_exchange.py <new-output-directory>
```

The directory contains the immutable ARM-055 packet, both schemas, this
procedure, and an exchange manifest. It intentionally contains no review
decision. The builder refuses to overwrite an existing directory.

After a real reviewer returns a decision through an independently controlled
channel, assess it into another new directory:

```powershell
$env:PYTHONPATH='software/src'
python software/scripts/assess_arm054_adapter_review_decision.py `
  <returned-decision.json> <new-assessment-directory> `
  --assessment-utc <YYYY-MM-DDTHH:MM:SSZ>
```

The intake rejects duplicate JSON fields, non-UTF-8 or oversized input,
symlinked files, unknown fields, hash mismatches, and overwrite attempts. It
retains the normalized decision, assessment report, raw input-document hash,
and intake summary. Exit status is zero only when the decision is structurally
ready for later read-only qualification intake; a blocked decision is retained
and exits with status 2. Neither outcome accesses hardware.
