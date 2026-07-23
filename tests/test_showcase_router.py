from pathlib import Path


def test_showcase_has_real_hash_routes():
    html = Path('CareerOS_H5_Showcase.html').read_text(encoding='utf-8')
    required = [
        '/student/home', '/student/works', '/student/ppt', '/student/interview',
        '/teacher/students', '/teacher/review', '/teacher/tasks', '/teacher/knowledge',
        '/system/models', '/system/knowledge', '/system/jobs', '/system/usage',
    ]
    for route in required:
        assert f'data-route="{route}"' in html or f"'{route}'" in html
    assert 'function renderRoute' in html
    assert 'function navigate' in html
    assert "window.addEventListener('hashchange'" in html
    assert 'Demo 导航已响应' not in html


def test_showcase_keeps_offline_storage_fallback():
    html = Path('CareerOS_H5_Showcase.html').read_text(encoding='utf-8')
    assert 'function safeStoreGet' in html
    assert 'function safeStoreSet' in html


def test_server_showcase_is_synced_with_standalone():
    standalone = Path('CareerOS_H5_Showcase.html').read_text(encoding='utf-8')
    served = Path('app/static/showcase.html').read_text(encoding='utf-8')
    assert served == standalone
