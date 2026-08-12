from __future__ import annotations
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app

required={
 ('GET','/api/foundation/v1/me'),
 ('GET','/api/foundation/v1/tasks/{task_id}'),
 ('PUT','/api/foundation/v1/tasks/{task_id}/answer'),
 ('POST','/api/foundation/v1/tasks/{task_id}/hint'),
 ('POST','/api/foundation/v1/tasks/{task_id}/complete'),
 ('POST','/api/foundation/v1/expression'),
 ('GET','/api/foundation/v1/growth/{subject_user_id}'),
 ('GET','/api/foundation/v1/cohort'),
}
registered={(method,getattr(route,'path','')) for route in app.routes for method in (getattr(route,'methods',None) or set())}
missing=required-registered
if missing: raise SystemExit('MISSING FOUNDATION ROUTES: '+repr(sorted(missing)))
student=Path('app/static/student.html').read_text(encoding='utf-8')
teacher=Path('app/static/teacher.html').read_text(encoding='utf-8')
practice=Path('app/routers/practice.py').read_text(encoding='utf-8')
for marker in ['/api/foundation/v1/me','renderFoundation','foundationTrackHtml','foundationApiPath','先做一件小事','先不急着选岗位']:
    if marker not in student: raise SystemExit('STUDENT FOUNDATION MARKER MISSING '+marker)
for marker in ['/api/foundation/v1/cohort','基础成长','最近是怎么进步的']:
    if marker not in teacher: raise SystemExit('TEACHER FOUNDATION MARKER MISSING '+marker)
for marker in ['foundation_locked','exploration_locked','participant_start_gate']:
    if marker not in practice: raise SystemExit('PRACTICE SERVER GATE MISSING '+marker)
print(f'FOUNDATION_CONTRACT_OK routes={len(required)}')
