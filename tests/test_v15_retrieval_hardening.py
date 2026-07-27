from __future__ import annotations

import json
from pathlib import Path

import httpx

from app.retrieval import (
    RerankerConfig,
    RerankerGateway,
    bm25_scores,
)
from scripts.evaluate_retrieval_fixture import run


def test_okapi_bm25_ranks_matching_document_first():
    scores = bm25_scores(
        "用户访谈 数据分析",
        [
            "用户访谈 用户访谈 需求分析 数据分析",
            "学校提供模拟答辩和简历门诊",
            "历史赛事规则",
        ],
    )
    assert scores[0] == 1.0
    assert scores[0] > scores[1] >= 0.0


def test_remote_reranker_contract_maps_indexed_scores(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 1, "relevance_score": 0.91},
                    {"index": 0, "relevance_score": 0.42},
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr(
        "app.retrieval.httpx.Client",
        lambda *args, **kwargs: real_client(transport=transport),
    )
    monkeypatch.setattr(
        "app.retrieval.validate_outbound_url",
        lambda value: value,
    )
    gateway = RerankerGateway(
        RerankerConfig(
            provider="jina",
            base_url="https://rerank.example.test",
            api_key="test-key",
            model="demo-reranker",
            max_retries=0,
        )
    )
    result = gateway.rerank("query", ["first", "second"], top_n=2)
    assert result.active is True
    assert result.scores == [0.42, 0.91]
    assert captured["payload"]["documents"] == ["first", "second"]
    assert captured["url"].endswith("/v1/rerank")


def test_retrieval_evaluation_fixture_is_deterministic_and_labeled_demo():
    dataset = Path("data_samples/rag_eval_v1")
    first = run(dataset)
    second = run(dataset)
    assert first["demo_data"] is True
    assert first["metrics"] == second["metrics"]
    assert first["metrics"]["recall_at_5"] == 1.0
    assert first["metrics"]["required_term_coverage"] == 1.0
