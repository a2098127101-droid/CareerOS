from scripts.audit_repository_contract import audit


def test_sqlalchemy_adapters_cover_legacy_public_repository_contracts():
    report = audit()
    assert report["ok"] is True
    assert report["pairs"] == 13
    project = next(item for item in report["items"] if item["legacy"] == "ProjectRepositoryProtocol")
    assert project["missing"] == []
    assert project["extra"] == []
    assert all(not item["missing"] for item in report["items"])
