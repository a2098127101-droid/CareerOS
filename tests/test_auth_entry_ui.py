from pathlib import Path


LOGIN_HTML = Path(__file__).parents[1] / "app" / "static" / "login.html"


def test_login_entry_removes_demo_credentials_and_role_guessing():
    source = LOGIN_HTML.read_text(encoding="utf-8")
    assert "Local Demo Accounts" not in source
    assert "CareerOS-Demo-123!" not in source
    assert "student@demo.local" not in source
    assert 'id="role"' not in source


def test_registration_ui_exposes_safe_role_specific_paths():
    source = LOGIN_HTML.read_text(encoding="utf-8")
    for role in ("student", "teacher", "school_admin", "super_admin"):
        assert f'data-role="{role}"' in source
    assert "/api/auth/register" in source
    assert "/api/auth/invitations/accept" in source
    assert "平台管理员注册必须由现有平台管理员授权" in source
    assert "Math.random" not in source
