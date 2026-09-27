# Tactevra decision records

**Document status:** Current decision-process index

**Authority:** Documentation and traceability only; this index does not approve a
proposal, publish a release, or authorize hardware operation.

Decision records preserve the context behind durable cross-workstream,
compatibility, architectural, and governance choices. The controlling process is
the root [governance policy](../../GOVERNANCE.md).

## When to create a record

Create a record for a choice that changes a public or shared contract, adopts a
lasting architectural direction, changes governance or release boundaries,
introduces an intentional breaking change, or supersedes an earlier record.

Do not create one for routine implementation detail, transient experiments,
ordinary dependency updates, or evidence results. Those belong in their issue,
pull request, workplan, or evidence ledger.

## File and status rules

- Copy [the template](TEMPLATE.md) to `NNNN-short-kebab-title.md` using the next
  unused four-digit number. A proposal reserves no number until its PR exists.
- Use one status: `Proposed`, `Accepted`, `Rejected`, or `Superseded`.
- A proposed record becomes accepted only when its PR merges through the normal
  protected-branch path with the required dispositions and evidence.
- Accepted, rejected, and superseded records are historical evidence. Correct
  only obvious typographical or broken-link errors; use a new record to change a
  decision or its rationale.
- A superseding record links the older record, and the older record receives a
  short forward link without rewriting its original content.
- Record exact issue, PR, commit, evidence, compatibility, and owner-disposition
  references. Do not copy private security information, credentials, personal
  data, or raw device exports into a record.

## Index

No durable decisions have been recorded under this process yet. Existing dated
plans and release records remain evidence in their current locations; they are
not retroactively converted into accepted decisions.
