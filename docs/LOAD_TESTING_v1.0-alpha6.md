# Load Testing · v1.0-alpha6

A small asynchronous HTTP harness is included for staging smoke/load checks.

```bash
python scripts/load_test.py \
  --base-url https://staging.example.com \
  --path /live \
  --requests 1000 \
  --concurrency 100 \
  --out data/load-test-100.json
```

The output includes:

- success/error counts;
- error rate;
- average latency;
- P50/P95/P99/max latency;
- status-code distribution.

Do not interpret laptop/local results as production capacity. The required 100/500/1000 concurrency certification must be executed against staging with database, Redis, workers, storage and model providers configured.
