from app.evidence_lock import audit_evidence


def test_flags_unsupported_number():
    audit = audit_evidence("带领10人团队，增长30%", "我参与过一个项目")
    assert not audit.passed
    assert audit.unsupported_numbers


def test_passes_supported_numbers():
    audit = audit_evidence("带领10人团队", "事实：带领10人团队")
    assert audit.passed
