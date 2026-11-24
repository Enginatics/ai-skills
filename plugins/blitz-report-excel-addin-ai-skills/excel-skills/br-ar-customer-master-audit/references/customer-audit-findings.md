# The Audit_Findings sheet (contract between br-ar-customer-master-audit and br-ar-customer-master-fix)

`br-ar-customer-master-audit` writes it and never changes Oracle. `br-ar-customer-master-fix` reads
it and stages only rows whose `Decision` is `Approved` and whose `Fix Route` it supports. Row 1
holds the headers, data starts in row 2, one row per finding. Find columns by their row-1 header.

| Column | Content |
|---|---|
| Check | the check's name as in the audit's scorecard, e.g. `Payment terms missing` |
| Severity | `Error` (wrong data), `Review` (possibly wrong), `Policy` (breaks a rule the user set) |
| Party Number | the party (registry) number |
| Party Name | |
| Account Number | blank for a party-level finding |
| Site | site number and location, blank for an account- or party-level finding |
| Field | the field the finding is about, e.g. `Payment Terms`, `Taxpayer Id`, `GSTIN` |
| Current Value | the value in Oracle (blank when missing) |
| Proposed Value | only when it can be derived or the user gave it (a PAN taken from a valid GSTIN, a payment term the user named); blank otherwise |
| Evidence | why it is a finding, e.g. `GSTIN 27… is in state 27, the site is in state 24` |
| Fix Route | `Payment Terms`, `Credit Check`, `Credit Hold`, `Credit Limit`, `Order Credit Limit`, `Taxpayer Id` (fixable with the customer upload), or `Master data team` (everything else: addresses, tax registrations, duplicates, statuses) |
| Decision | `Proposed` when written; the user sets `Approved` (with a `Proposed Value`) or `Rejected` |
| Result | written by br-ar-customer-master-fix only: `Updated` or the error message |

Profile fields (`Payment Terms`, `Credit Check`, `Credit Hold`) and profile amounts (`Credit Limit`,
`Order Credit Limit`) are fixed on the account profile; a site-level finding of those fields goes
to `Master data team`.
