from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.knowledge import KnowledgeStore
from app.rag_evaluation import evaluate_rag, load_cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic CareerOS RAG retrieval evaluation against a SQLite knowledge store.")
    parser.add_argument("--db", required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--tenant", default="global")
    parser.add_argument("--out", default="data/rag_eval_report.json")
    args = parser.parse_args()
    store = KnowledgeStore(args.db, EmbeddingGateway(EmbeddingConfig()))
    report = evaluate_rag(store, load_cases(args.cases), tenant_id=args.tenant)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
