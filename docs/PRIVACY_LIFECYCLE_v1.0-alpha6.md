# Privacy Lifecycle · v1.0-alpha6

## Delete request flow

1. User creates a delete request.
2. Admin reviews `GET /api/admin/privacy/requests/{request_id}/plan`.
3. `confirm=false` returns a dry-run plan only.
4. Processing requires `PRIVACY_DELETE_EXECUTOR_ENABLED=true` and `confirm=true`.
5. User-owned operational data is removed and identity is de-identified.

## Deleted categories

- user-owned sessions;
- artifact versions/series for those sessions;
- evidence items and evidence graph records;
- workflow instances/steps;
- feedback and AI tasks tied to those sessions;
- private stored objects owned by the user.

## De-identified / retained

The user identity row is retained under an internal pseudonymous identifier, archived, and stripped of the original email/display name. Security/audit/billing categories are retained intentionally.

This is a technical foundation, not a jurisdiction-specific legal retention policy. Production deployment must define retention schedules, legal holds and deletion completion evidence.
