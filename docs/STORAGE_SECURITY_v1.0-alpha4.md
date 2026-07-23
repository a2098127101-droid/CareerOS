# Storage & Upload Security — v1.0-alpha4

## Private delivery

Local development uses an application-signed HMAC token with expiration. S3-compatible deployments use provider presigned GET URLs after server-side authorization.

A file is never intentionally exposed as a permanent public `/uploads/...` URL.

## Authorization

Before issuing access:

1. locate object within tenant scope;
2. authorize owner/session/advisor/admin access;
3. issue short-lived access;
4. enforce expiration.

## Upload validation

Implemented checks:

- extension allowlist;
- maximum input bytes;
- PDF signature;
- Office ZIP signature;
- Office internal structure;
- declared/detected MIME mismatch;
- archive entry count;
- uncompressed archive limit;
- compression-ratio zip-bomb detection;
- optional external malware scanner hook.

## Malware hook

Configure for example:

```env
MALWARE_SCAN_COMMAND=clamscan --no-summary {file}
```

A non-zero scanner exit code rejects the upload. No scanner is bundled and no malware engine was live-verified in this environment.
