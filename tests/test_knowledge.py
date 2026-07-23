from pathlib import Path

from app.knowledge import KnowledgeStore


def test_knowledge_ingest_and_search(tmp_path: Path):
    store = KnowledgeStore(str(tmp_path / "k.db"))
    official = store.ingest(
        title="2026岗位准备官方评估细则",
        filename="rules.txt",
        mime_type="text/plain",
        text="岗位准备评估标准强调目标清晰度、能力证据与发展潜力。",
        tags=["2026", "官方"],
        category="rubric",
        authority="official",
        effective_year="2026",
        priority=95,
    )
    store.ingest(
        title="旧版内部笔记",
        filename="old.txt",
        mime_type="text/plain",
        text="岗位准备评估标准强调目标清晰度。",
        category="rubric",
        authority="internal",
        effective_year="2024",
        priority=30,
    )
    hits = store.search("岗位准备评估标准 能力证据", top_k=5)
    assert hits
    assert hits[0].source_id == official["source_id"]
    context, refs = store.build_context("岗位准备评估标准")
    assert "2026岗位准备官方评估细则" in context
    assert refs


def test_source_toggle_excludes_from_search(tmp_path: Path):
    store = KnowledgeStore(str(tmp_path / "k.db"))
    source = store.ingest(title="规则", filename="r.txt", mime_type="text/plain", text="能力成长评估包含职业探索。")
    assert store.search("能力成长评估标准")
    store.update_source(source["source_id"], active=False)
    assert store.search("能力成长评估标准") == []
