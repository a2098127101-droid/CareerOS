from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any
from uuid import uuid4

from .privacy import minimize_for_model


@dataclass
class ModelEvalSummary:
    eval_id: str
    metrics: dict[str, Any]
    cases: list[dict[str, Any]]


async def run_model_evaluation(*, gateway, store, tenant_id: str, provider_id: str, model: str, task: str, cases: list[dict[str, Any]]) -> ModelEvalSummary:
    provider = store.get_provider(provider_id)
    if not provider:
        raise ValueError("provider not found")
    cap = store.get_model_capability(provider_id, model) or {}
    results: list[dict[str, Any]] = []
    totals = {"success": 0, "contains": 0, "json_valid": 0, "latency_ms": 0, "input_tokens": 0, "output_tokens": 0}
    for case in cases:
        started = perf_counter()
        row = {"prompt": case.get("prompt", ""), "expected_contains": case.get("expected_contains", []), "expect_json": bool(case.get("expect_json")), "success": False}
        try:
            prompt, redactions = minimize_for_model(row["prompt"], enabled=bool(getattr(gateway, "pii_redaction_enabled", False)))
            text, usage = await gateway._call_provider(provider, model=model, system="You are being evaluated. Follow the user instruction precisely.", user=prompt, temperature=0, max_tokens=min(int(cap.get("max_output") or 1024), 4096))
            latency = int((perf_counter() - started) * 1000)
            row["pii_redactions"] = redactions
            store.record_usage(task=f"evaluation:{task}",provider_id=provider_id,model=model,input_tokens=int(usage.get("input_tokens") or 0),output_tokens=int(usage.get("output_tokens") or 0),total_tokens=int(usage.get("total_tokens") or 0),latency_ms=latency,success=True,tenant_id=tenant_id)
            contains_ok = all(str(x).lower() in text.lower() for x in row["expected_contains"])
            json_ok = True
            if row["expect_json"]:
                try:
                    json.loads(text.strip().strip("`"))
                except Exception:
                    json_ok = False
            row.update({"success": True, "contains_ok": contains_ok, "json_valid": json_ok, "latency_ms": latency, "output_excerpt": text[:500], "usage": usage})
            totals["success"] += 1
            totals["contains"] += int(contains_ok)
            totals["json_valid"] += int(json_ok)
            totals["latency_ms"] += latency
            totals["input_tokens"] += int(usage.get("input_tokens") or 0)
            totals["output_tokens"] += int(usage.get("output_tokens") or 0)
        except Exception as exc:
            latency = int((perf_counter() - started) * 1000)
            row.update({"error": str(exc), "latency_ms": latency})
            store.record_usage(task=f"evaluation:{task}",provider_id=provider_id,model=model,latency_ms=latency,success=False,error=str(exc),tenant_id=tenant_id)
        results.append(row)
    n=max(1,len(results))
    estimated_cost=(totals["input_tokens"]*float(cap.get("input_cost_per_million") or 0)+totals["output_tokens"]*float(cap.get("output_cost_per_million") or 0))/1_000_000
    metrics={
        "cases": len(results),
        "success_rate": round(totals["success"]/n,4),
        "expected_contains_rate": round(totals["contains"]/n,4),
        "json_validity_rate": round(totals["json_valid"]/n,4),
        "average_latency_ms": round(totals["latency_ms"]/n,1),
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "estimated_cost": round(estimated_cost,6),
    }
    eval_id=f"MEVAL-{uuid4().hex[:16].upper()}"
    store.record_model_eval(eval_id=eval_id,tenant_id=tenant_id,task=task,provider_id=provider_id,model=model,metrics=metrics,cases=results)
    return ModelEvalSummary(eval_id=eval_id,metrics=metrics,cases=results)
