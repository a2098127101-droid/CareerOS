# CareerOS Deployment

For the current certification candidate, start with:

- `README_BETA1_STAGING.md`
- `.env.staging.example`
- `docker-compose.staging.yml`

These files provide a production-like **staging certification harness**. They do not make CareerOS production-ready by themselves. Real secrets, HTTPS, external persistence/backup, live runtime/business certificates, monitoring, migration/recovery drills and measured load results are still required before production release.
