# Observability — v1.0-alpha4

Implemented foundation:

- structured logging;
- optional JSON log formatter;
- request correlation using `X-Request-ID`;
- request count/error/latency metrics;
- Sentry-compatible SDK initialization;
- OpenTelemetry capability detection/foundation;
- liveness and readiness probes.

Endpoints:

```text
GET /live
GET /ready
GET /api/admin/system/metrics
```

The in-process metrics collector is a foundation only. Multi-instance aggregation requires a real metrics exporter/backend such as OpenTelemetry Collector + Prometheus-compatible storage.
