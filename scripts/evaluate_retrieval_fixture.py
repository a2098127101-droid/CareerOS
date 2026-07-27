from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.knowledge import KnowledgeStore
from app.rag_evaluation import evaluate_rag, load_cases
from app.retrieval import RerankerGateway


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def run(dataset: Path) -> dict:
    # Windows indexing/antivirus can briefly hold a closed SQLite file. The
    # fixture is disposable, so cleanup errors must not change retrieval results.
    with tempfile.TemporaryDirectory(
        prefix="careeros-rag-eval-",
        ignore_cleanup_errors=True,
    ) as temp_dir:
        store = KnowledgeStore(
            str(Path(temp_dir) / "evaluation.db"),
            embedding_gateway=EmbeddingGateway(EmbeddingConfig()),
            reranker_gateway=RerankerGateway(),
        )
        for source in _jsonl(dataset / "sources.jsonl"):
            if source.get("demo_data") is not True:
                raise ValueError("fixture sources must explicitly set demo_data=true")
            store.ingest(
                title=source["title"],
                filename="demo-fixture.txt",
                mime_type="text/plain",
                text=source["content"],
                scope=source.get("scope", "global"),
                category=source.get("category", "other"),
                authority=source.get("authority", "internal"),
                effective_year=source.get("effective_year", ""),
                priority=int(source.get("priority", 50)),
                tenant_id="global",
                tags=["demo-data", "retrieval-evaluation"],
            )
        cases = load_cases(dataset / "queries.jsonl")
        report = evaluate_rag(store, cases, tenant_id="global", k=10)
        report["dataset"] = str(dataset)
        report["demo_data"] = True
        report["retrieval_contract"] = {
            "embedding": "local_hash deterministic fallback",
            "bm25": "Okapi BM25 plus SQLite FTS5 when available",
            "reranker": "disabled fixture; remote adapters require credentials",
        }
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the deterministic CareerOS RAG fixture.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "data_samples" / "rag_eval_v1",
    )
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report = run(args.dataset.resolve())
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["metrics"]["recall_at_5"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
