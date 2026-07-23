from scripts.audit_repository_contract import audit


def test_sqlalchemy_adapters_cover_legacy_public_repository_contracts():
    report = audit()
    assert report["ok"] is True
    assert report["pairs"] == 12
    assert all(not item["missing"] for item in report["items"])
