from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from uuid import uuid4


@dataclass
class RAGEvalCase:
    query: str
    expected_source_id: str = ""
    expected_source_title: str = ""
    expected_authority: str = ""
    expected_year: str = ""
    required_terms: list[str] | None = None
    scope: str = "global"
    notes: str = ""


@dataclass
class RAGEvalResult:
    case: dict
    top_sources: list[str]
    top_titles: list[str]
    top_authorities: list[str]
    top_years: list[str]
    source_rank: int | None
    source_hit_at_5: bool
    source_hit_at_10: bool
    authority_correct: bool | None
    temporal_correct: bool | None
    required_term_coverage: float | None


def load_cases(path: str | Path) -> list[RAGEvalCase]:
    p = Path(path)
    cases: list[RAGEvalCase] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        cases.append(RAGEvalCase(**data))
    return cases


def evaluate_rag(knowledge_store, cases: list[RAGEvalCase], *, tenant_id: str = "global", k: int = 10) -> dict:
    results: list[RAGEvalResult] = []
    for case in cases:
        detailed = knowledge_store.search_detailed(
            case.query,
            scope=case.scope,
            top_k=max(k, 10),
            tenant_id=tenant_id,
            effective_year=case.expected_year,
        )
        breakdown = detailed.get("breakdown", [])
        top_sources = [str(x.get("source_id") or "") for x in breakdown]
        top_titles = [str(x.get("source_title") or "") for x in breakdown]
        top_authorities = [str(x.get("authority") or "") for x in breakdown]
        top_years = [str(x.get("effective_year") or "") for x in breakdown]
        rank = None
        if case.expected_source_id and case.expected_source_id in top_sources:
            rank = top_sources.index(case.expected_source_id) + 1
        elif case.expected_source_title and case.expected_source_title in top_titles:
            rank = top_titles.index(case.expected_source_title) + 1
        authority_correct = None if not case.expected_authority else bool(top_authorities and top_authorities[0] == case.expected_authority)
        temporal_correct = None
        if case.expected_year:
            temporal_correct = all((not y) or y == case.expected_year for y in top_years[: min(5, len(top_years))])
        required_coverage = None
        if case.required_terms:
            context = "\n".join(hit.content.lower() for hit in detailed.get("hits", [])[:5])
            required_coverage = sum(
                1 for term in case.required_terms if str(term).lower() in context
            ) / max(1, len(case.required_terms))
        results.append(RAGEvalResult(
            case=asdict(case),
            top_sources=top_sources,
            top_titles=top_titles,
            top_authorities=top_authorities,
            top_years=top_years,
            source_rank=rank,
            source_hit_at_5=bool(rank and rank <= 5),
            source_hit_at_10=bool(rank and rank <= 10),
            authority_correct=authority_correct,
            temporal_correct=temporal_correct,
            required_term_coverage=required_coverage,
        ))

    source_cases = [
        result for result in results
        if result.case.get("expected_source_id") or result.case.get("expected_source_title")
    ]
    authority_cases = [r for r in results if r.authority_correct is not None]
    temporal_cases = [r for r in results if r.temporal_correct is not None]
    term_cases = [r for r in results if r.required_term_coverage is not None]
    metrics = {
        "cases": len(results),
        "recall_at_5": round(sum(r.source_hit_at_5 for r in source_cases) / max(1, len(source_cases)), 4),
        "recall_at_10": round(sum(r.source_hit_at_10 for r in source_cases) / max(1, len(source_cases)), 4),
        "mrr_at_10": round(
            sum((1.0 / r.source_rank) if r.source_rank and r.source_rank <= 10 else 0.0 for r in source_cases)
            / max(1, len(source_cases)),
            4,
        ),
        # Citation accuracy here means expected source retrieval among evaluated citations; it does not
        # claim downstream generated-answer factual correctness.
        "citation_source_accuracy": round(sum(r.source_hit_at_5 for r in source_cases) / max(1, len(source_cases)), 4),
        "authority_accuracy": round(sum(bool(r.authority_correct) for r in authority_cases) / max(1, len(authority_cases)), 4),
        "temporal_accuracy": round(sum(bool(r.temporal_correct) for r in temporal_cases) / max(1, len(temporal_cases)), 4),
        "required_term_coverage": round(
            sum(float(r.required_term_coverage or 0.0) for r in term_cases) / max(1, len(term_cases)),
            4,
        ),
    }
    return {"run_id": f"RAGEVAL-{uuid4().hex[:12].upper()}", "metrics": metrics, "results": [asdict(r) for r in results]}
