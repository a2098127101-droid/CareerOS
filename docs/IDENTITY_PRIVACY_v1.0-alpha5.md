# Identity Lifecycle & Privacy · v1.0-alpha5

## Invitation lifecycle

Supported:

- create tenant-scoped invitation
- hashed invitation token at rest
- expiry
- revoke
- accept and create membership

Current delivery is manual/debug. Production SMTP/email invitation delivery is not implemented.

## User lifecycle

Supported:

- active
- disabled
- archived
- role change
- session revocation after sensitive changes

Platform-admin protection remains server-side.

## Privacy consent

`privacy_consents` records:

- tenant
- user
- policy version
- purpose
- granted/revoked state
- source
- timestamp

## Data export

Authenticated users can export a structured bundle including identity, memberships, consent records and user-scoped CareerOS data such as sessions, artifacts, evidence, feedback, tasks and file metadata where applicable.

## Delete My Data

Alpha5 creates an auditable `data_subject_requests` record. It does **not** automatically destroy shared, audited or retention-controlled records.

A future executor must support:

- retention policy
- legal hold
- shared-record ownership
- de-identification vs hard deletion
- object storage deletion
- audit completion evidence

## PII minimization

Current redaction detects common patterns for:

- email
- CN-style mobile numbers
- 18-character CN ID-like numbers
- long account-number patterns

This is a conservative regex foundation, not full DLP/NER. Production deployments with higher compliance requirements need stronger classification and policy enforcement.
