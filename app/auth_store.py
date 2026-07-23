from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

from .domain.roles import CANONICAL_ROLES, LEGACY_ROLES, canonical_role, storage_role

VALID_ROLES = CANONICAL_ROLES | LEGACY_ROLES


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str
    display_name: str
    tenant_id: str
    role: str
    authenticated: bool = True

    @property
    def canonical_role(self) -> str:
        return canonical_role(self.role)

    @property
    def is_super_admin(self) -> bool:
        return self.canonical_role == "platform_admin"

    @property
    def is_organization_admin(self) -> bool:
        return self.canonical_role == "organization_admin"

    @property
    def is_advisor(self) -> bool:
        return self.canonical_role == "advisor"

    @property
    def is_participant(self) -> bool:
        return self.canonical_role == "participant"


class AuthStore:
    def __init__(self, db_path: str, session_ttl_hours: int = 168):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_ttl_hours = session_ttl_hours
        self._lock = threading.Lock()
        self._ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)
        from .migrations import run_migrations
        run_migrations(str(self.db_path))

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _dt(value: str) -> datetime:
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def hash_password(self, password: str) -> str:
        if len(password) < 10:
            raise ValueError("password must contain at least 10 characters")
        return self._ph.hash(password)

    def verify_password(self, password_hash: str, password: str) -> bool:
        try:
            return bool(self._ph.verify(password_hash, password))
        except (VerifyMismatchError, InvalidHashError):
            return False

    def ensure_tenant(self, tenant_id: str, name: str, *, tenant_type: str = "organization", product_preset: str = "career_development") -> dict:
        tenant_id = tenant_id.strip()
        if not tenant_id:
            raise ValueError("tenant_id required")
        with self._lock, self._connect() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(tenants)").fetchall()}
            if {"tenant_type", "product_preset"}.issubset(cols):
                conn.execute(
                    """INSERT INTO tenants(tenant_id,name,status,tenant_type,product_preset,updated_at)
                    VALUES(?,?, 'active', ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(tenant_id) DO UPDATE SET name=excluded.name,tenant_type=excluded.tenant_type,
                    product_preset=excluded.product_preset,updated_at=CURRENT_TIMESTAMP""",
                    (tenant_id, name.strip() or tenant_id, tenant_type, product_preset),
                )
            else:
                conn.execute(
                    """INSERT INTO tenants(tenant_id,name,status,updated_at)
                    VALUES(?,?, 'active', CURRENT_TIMESTAMP)
                    ON CONFLICT(tenant_id) DO UPDATE SET name=excluded.name, updated_at=CURRENT_TIMESTAMP""",
                    (tenant_id, name.strip() or tenant_id),
                )
            conn.commit()
        return self.get_tenant(tenant_id)

    def get_tenant(self, tenant_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tenants WHERE tenant_id=?", (tenant_id,)).fetchone()
        if not row:
            raise KeyError(tenant_id)
        data = dict(row)
        data["branding"] = json.loads(data.pop("branding_json") or "{}")
        if "settings_json" in data:
            data["settings"] = json.loads(data.pop("settings_json") or "{}")
        return data

    def list_tenants(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM tenants WHERE status='active' ORDER BY created_at DESC").fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data["branding"] = json.loads(data.pop("branding_json") or "{}")
            if "settings_json" in data:
                data["settings"] = json.loads(data.pop("settings_json") or "{}")
            result.append(data)
        return result

    def update_tenant_branding(self, tenant_id: str, branding: dict) -> dict:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE tenants SET branding_json=?, updated_at=CURRENT_TIMESTAMP WHERE tenant_id=?",
                (json.dumps(branding or {}, ensure_ascii=False), tenant_id),
            )
            if cur.rowcount == 0:
                raise KeyError(tenant_id)
            conn.commit()
        return self.get_tenant(tenant_id)

    def update_tenant_product_config(self, tenant_id: str, *, tenant_type: str | None = None, product_preset: str | None = None, settings: dict | None = None) -> dict:
        fields: list[str] = []
        values: list[object] = []
        if tenant_type is not None:
            fields.append("tenant_type=?"); values.append(tenant_type)
        if product_preset is not None:
            fields.append("product_preset=?"); values.append(product_preset)
        if settings is not None:
            fields.append("settings_json=?"); values.append(json.dumps(settings, ensure_ascii=False))
        if not fields:
            return self.get_tenant(tenant_id)
        fields.append("updated_at=CURRENT_TIMESTAMP")
        values.append(tenant_id)
        with self._lock, self._connect() as conn:
            cur = conn.execute(f"UPDATE tenants SET {','.join(fields)} WHERE tenant_id=?", tuple(values))
            if cur.rowcount == 0:
                raise KeyError(tenant_id)
            conn.commit()
        return self.get_tenant(tenant_id)

    def create_user(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
        tenant_id: str,
        role: str,
        user_id: str | None = None,
    ) -> dict:
        if role not in VALID_ROLES:
            raise ValueError("invalid role")
        role = storage_role(role)
        email = email.strip().lower()
        if "@" not in email:
            raise ValueError("invalid email")
        user_id = user_id or f"USR-{uuid4().hex[:16].upper()}"
        membership_id = f"MEM-{uuid4().hex[:16].upper()}"
        password_hash = self.hash_password(password)
        try:
            with self._lock, self._connect() as conn:
                tenant = conn.execute("SELECT 1 FROM tenants WHERE tenant_id=?", (tenant_id,)).fetchone()
                if not tenant:
                    raise KeyError(f"tenant not found: {tenant_id}")
                conn.execute(
                    "INSERT INTO users(user_id,email,password_hash,display_name,status) VALUES(?,?,?,?, 'active')",
                    (user_id, email, password_hash, display_name.strip()),
                )
                conn.execute(
                    """INSERT INTO tenant_memberships(membership_id,tenant_id,user_id,role,status)
                    VALUES(?,?,?,?, 'active')""",
                    (membership_id, tenant_id, user_id, role),
                )
                conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("user or membership already exists") from exc
        return self.get_user(user_id, include_memberships=True)

    def ensure_user(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
        tenant_id: str,
        role: str,
    ) -> dict:
        if role not in VALID_ROLES:
            raise ValueError("invalid role")
        role = storage_role(role)
        existing = self.find_user_by_email(email)
        if existing:
            with self._lock, self._connect() as conn:
                row = conn.execute(
                    "SELECT 1 FROM tenant_memberships WHERE tenant_id=? AND user_id=? AND role=?",
                    (tenant_id, existing["user_id"], role),
                ).fetchone()
                if not row:
                    conn.execute(
                        "INSERT INTO tenant_memberships(membership_id,tenant_id,user_id,role,status) VALUES(?,?,?,?, 'active')",
                        (f"MEM-{uuid4().hex[:16].upper()}", tenant_id, existing["user_id"], role),
                    )
                    conn.commit()
            return self.get_user(existing["user_id"], include_memberships=True)
        return self.create_user(
            email=email,
            password=password,
            display_name=display_name,
            tenant_id=tenant_id,
            role=role,
        )

    def find_user_by_email(self, email: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE", (email.strip(),)).fetchone()
        return dict(row) if row else None

    def get_user(self, user_id: str, include_memberships: bool = False) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id,email,display_name,status,created_at,updated_at FROM users WHERE user_id=?",
                (user_id,),
            ).fetchone()
            if not row:
                raise KeyError(user_id)
            data = dict(row)
            if include_memberships:
                memberships = [dict(r) for r in conn.execute(
                    "SELECT tenant_id,role,status,created_at FROM tenant_memberships WHERE user_id=? ORDER BY created_at",
                    (user_id,),
                ).fetchall()]
                for item in memberships:
                    item["canonical_role"] = canonical_role(item.get("role", ""))
                data["memberships"] = memberships
        return data

    def list_users(self, tenant_id: str, role: str | None = None) -> list[dict]:
        params: list[str] = [tenant_id]
        sql = """
            SELECT u.user_id,u.email,u.display_name,u.status,u.created_at,m.role,m.tenant_id
            FROM users u JOIN tenant_memberships m ON m.user_id=u.user_id
            WHERE m.tenant_id=? AND m.status='active'
        """
        if role:
            sql += " AND m.role=?"
            params.append(storage_role(role))
        sql += " ORDER BY u.created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        result = [dict(r) for r in rows]
        for item in result:
            item["canonical_role"] = canonical_role(item.get("role", ""))
        return result

    def memberships(self, user_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT tenant_id,role,status FROM tenant_memberships WHERE user_id=? AND status='active' ORDER BY created_at",
                (user_id,),
            ).fetchall()
        result = [dict(r) for r in rows]
        for item in result:
            item["canonical_role"] = canonical_role(item.get("role", ""))
        return result

    def authenticate(self, email: str, password: str, tenant_id: str | None = None, role: str | None = None) -> tuple[Principal, str]:
        user = self.find_user_by_email(email)
        if not user or user["status"] != "active" or not self.verify_password(user["password_hash"], password):
            raise PermissionError("invalid credentials")
        memberships = self.memberships(user["user_id"])
        if tenant_id:
            memberships = [m for m in memberships if m["tenant_id"] == tenant_id]
        if role:
            requested_role = canonical_role(role)
            memberships = [m for m in memberships if canonical_role(m["role"]) == requested_role]
        if not memberships:
            raise PermissionError("no active membership")
        # Prefer super-admin when available, otherwise use the first active membership.
        membership = next((m for m in memberships if m["role"] == "super_admin"), memberships[0])
        principal = Principal(
            user_id=user["user_id"],
            email=user["email"],
            display_name=user["display_name"],
            tenant_id=membership["tenant_id"],
            role=membership["role"],
        )
        token = self.create_session(principal)
        return principal, token

    def create_session(self, principal: Principal) -> str:
        raw = secrets.token_urlsafe(48)
        auth_session_id = f"AUTH-{uuid4().hex[:18].upper()}"
        expires = self._now() + timedelta(hours=self.session_ttl_hours)
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO auth_sessions(auth_session_id,token_hash,user_id,tenant_id,role,expires_at)
                VALUES(?,?,?,?,?,?)""",
                (
                    auth_session_id,
                    self._token_hash(raw),
                    principal.user_id,
                    principal.tenant_id,
                    principal.role,
                    expires.isoformat(),
                ),
            )
            conn.commit()
        return raw

    def resolve_session(self, raw_token: str | None) -> Principal | None:
        if not raw_token:
            return None
        token_hash = self._token_hash(raw_token)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """SELECT s.*,u.email,u.display_name,u.status user_status,m.status membership_status
                FROM auth_sessions s
                JOIN users u ON u.user_id=s.user_id
                JOIN tenant_memberships m ON m.user_id=s.user_id AND m.tenant_id=s.tenant_id AND m.role=s.role
                WHERE s.token_hash=? AND s.revoked_at IS NULL""",
                (token_hash,),
            ).fetchone()
            if not row:
                return None
            if self._dt(row["expires_at"]) <= self._now() or row["user_status"] != "active" or row["membership_status"] != "active":
                conn.execute("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE auth_session_id=?", (row["auth_session_id"],))
                conn.commit()
                return None
            conn.execute("UPDATE auth_sessions SET last_seen_at=CURRENT_TIMESTAMP WHERE auth_session_id=?", (row["auth_session_id"],))
            conn.commit()
        return Principal(
            user_id=row["user_id"],
            email=row["email"],
            display_name=row["display_name"],
            tenant_id=row["tenant_id"],
            role=row["role"],
        )

    def revoke_session(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE token_hash=?",
                (self._token_hash(raw_token),),
            )
            conn.commit()

    def change_password(self, user_id: str, old_password: str, new_password: str) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT password_hash FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row or not self.verify_password(row["password_hash"], old_password):
            raise PermissionError("invalid current password")
        new_hash = self.hash_password(new_password)
        with self._lock, self._connect() as conn:
            conn.execute("UPDATE users SET password_hash=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (new_hash, user_id))
            conn.execute("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=?", (user_id,))
            conn.commit()

    def request_password_reset(self, email: str, ttl_minutes: int = 30) -> str | None:
        user = self.find_user_by_email(email)
        if not user:
            return None
        raw = secrets.token_urlsafe(40)
        expires = self._now() + timedelta(minutes=ttl_minutes)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO password_reset_tokens(reset_id,token_hash,user_id,expires_at) VALUES(?,?,?,?)",
                (f"RESET-{uuid4().hex[:16].upper()}", self._token_hash(raw), user["user_id"], expires.isoformat()),
            )
            conn.commit()
        return raw

    def reset_password(self, raw_token: str, new_password: str) -> None:
        token_hash = self._token_hash(raw_token)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM password_reset_tokens WHERE token_hash=? AND used_at IS NULL", (token_hash,)
            ).fetchone()
            if not row or self._dt(row["expires_at"]) <= self._now():
                raise PermissionError("invalid or expired reset token")
            new_hash = self.hash_password(new_password)
            conn.execute("UPDATE users SET password_hash=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (new_hash, row["user_id"]))
            conn.execute("UPDATE password_reset_tokens SET used_at=CURRENT_TIMESTAMP WHERE reset_id=?", (row["reset_id"],))
            conn.execute("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=?", (row["user_id"],))
            conn.commit()

    def create_invitation(self, *, email: str, tenant_id: str, role: str, invited_by: str = "", display_name: str = "", ttl_hours: int = 72) -> dict:
        if role not in VALID_ROLES:
            raise ValueError("invalid role")
        role = storage_role(role)
        email = email.strip().lower()
        if "@" not in email:
            raise ValueError("invalid email")
        raw = secrets.token_urlsafe(40)
        invitation_id = f"INV-{uuid4().hex[:16].upper()}"
        expires = self._now() + timedelta(hours=max(1, int(ttl_hours)))
        with self._lock, self._connect() as conn:
            if not conn.execute("SELECT 1 FROM tenants WHERE tenant_id=? AND status='active'", (tenant_id,)).fetchone():
                raise KeyError("tenant not found")
            conn.execute("""INSERT INTO user_invitations(invitation_id,token_hash,tenant_id,email,role,display_name,invited_by,expires_at) VALUES(?,?,?,?,?,?,?,?)""",
                         (invitation_id,self._token_hash(raw),tenant_id,email,role,display_name.strip(),invited_by,expires.isoformat()))
            conn.commit()
        return {"invitation_id":invitation_id,"token":raw,"tenant_id":tenant_id,"email":email,"role":role,"display_name":display_name.strip(),"expires_at":expires.isoformat()}

    def list_invitations(self, tenant_id: str, include_closed: bool = False) -> list[dict]:
        sql="SELECT invitation_id,tenant_id,email,role,display_name,invited_by,expires_at,accepted_at,revoked_at,created_at FROM user_invitations WHERE tenant_id=?"
        if not include_closed:
            sql += " AND accepted_at IS NULL AND revoked_at IS NULL"
        sql += " ORDER BY created_at DESC"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql,(tenant_id,)).fetchall()]

    def revoke_invitation(self, invitation_id: str, tenant_id: str) -> None:
        with self._lock, self._connect() as conn:
            cur=conn.execute("UPDATE user_invitations SET revoked_at=CURRENT_TIMESTAMP WHERE invitation_id=? AND tenant_id=? AND accepted_at IS NULL",(invitation_id,tenant_id))
            if cur.rowcount == 0: raise KeyError(invitation_id)
            conn.commit()

    def accept_invitation(self, raw_token: str, password: str, display_name: str = "") -> dict:
        token_hash=self._token_hash(raw_token)
        with self._connect() as conn:
            row=conn.execute("SELECT * FROM user_invitations WHERE token_hash=? AND accepted_at IS NULL AND revoked_at IS NULL",(token_hash,)).fetchone()
        if not row or self._dt(row["expires_at"]) <= self._now():
            raise PermissionError("invalid or expired invitation")
        existing=self.find_user_by_email(row["email"])
        if existing:
            user_id=existing["user_id"]
            with self._lock, self._connect() as conn:
                if not conn.execute("SELECT 1 FROM tenant_memberships WHERE tenant_id=? AND user_id=? AND role=?",(row["tenant_id"],user_id,row["role"])).fetchone():
                    conn.execute("INSERT INTO tenant_memberships(membership_id,tenant_id,user_id,role,status) VALUES(?,?,?,?, 'active')",(f"MEM-{uuid4().hex[:16].upper()}",row["tenant_id"],user_id,row["role"]))
                conn.execute("UPDATE user_invitations SET accepted_at=CURRENT_TIMESTAMP WHERE invitation_id=?",(row["invitation_id"],)); conn.commit()
        else:
            user=self.create_user(email=row["email"],password=password,display_name=(display_name.strip() or row["display_name"] or row["email"].split('@')[0]),tenant_id=row["tenant_id"],role=row["role"]); user_id=user["user_id"]
            with self._lock, self._connect() as conn:
                conn.execute("UPDATE user_invitations SET accepted_at=CURRENT_TIMESTAMP WHERE invitation_id=?",(row["invitation_id"],)); conn.commit()
        return self.get_user(user_id, include_memberships=True)

    def set_user_status(self, *, user_id: str, tenant_id: str, status: str) -> dict:
        if status not in {"active","disabled","archived"}: raise ValueError("invalid user status")
        with self._lock, self._connect() as conn:
            membership=conn.execute("SELECT 1 FROM tenant_memberships WHERE tenant_id=? AND user_id=?",(tenant_id,user_id)).fetchone()
            if not membership: raise KeyError(user_id)
            conn.execute("UPDATE users SET status=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",(status,user_id))
            if status != "active":
                conn.execute("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=? AND revoked_at IS NULL",(user_id,))
            conn.commit()
        return self.get_user(user_id, include_memberships=True)

    def change_membership_role(self, *, user_id: str, tenant_id: str, role: str) -> dict:
        if role not in VALID_ROLES: raise ValueError("invalid role")
        role=storage_role(role)
        with self._lock, self._connect() as conn:
            rows=conn.execute("SELECT membership_id FROM tenant_memberships WHERE tenant_id=? AND user_id=? AND status='active'",(tenant_id,user_id)).fetchall()
            if not rows: raise KeyError(user_id)
            conn.execute("UPDATE tenant_memberships SET role=? WHERE membership_id=?",(role,rows[0]["membership_id"]))
            for extra in rows[1:]: conn.execute("UPDATE tenant_memberships SET status='inactive' WHERE membership_id=?",(extra["membership_id"],))
            conn.execute("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=? AND tenant_id=? AND revoked_at IS NULL",(user_id,tenant_id))
            conn.commit()
        return self.get_user(user_id,include_memberships=True)

    def record_consent(self, *, tenant_id: str, user_id: str, policy_version: str, purpose: str = "service", granted: bool = True, source: str = "ui") -> dict:
        consent_id=f"CONS-{uuid4().hex[:16].upper()}"
        with self._lock, self._connect() as conn:
            conn.execute("INSERT INTO privacy_consents(consent_id,tenant_id,user_id,policy_version,purpose,granted,source) VALUES(?,?,?,?,?,?,?)",(consent_id,tenant_id,user_id,policy_version,purpose,1 if granted else 0,source))
            conn.commit()
        return {"consent_id":consent_id,"tenant_id":tenant_id,"user_id":user_id,"policy_version":policy_version,"purpose":purpose,"granted":granted,"source":source}

    def list_consents(self, *, tenant_id: str, user_id: str) -> list[dict]:
        with self._connect() as conn:
            rows=conn.execute("SELECT * FROM privacy_consents WHERE tenant_id=? AND user_id=? ORDER BY created_at DESC",(tenant_id,user_id)).fetchall()
        out=[dict(r) for r in rows]
        for x in out: x["granted"]=bool(x["granted"])
        return out

    def create_data_subject_request(self, *, tenant_id: str, user_id: str, request_type: str, notes: str = "") -> dict:
        if request_type not in {"export","delete"}: raise ValueError("invalid request type")
        request_id=f"DSR-{uuid4().hex[:16].upper()}"
        with self._lock, self._connect() as conn:
            conn.execute("INSERT INTO data_subject_requests(request_id,tenant_id,user_id,request_type,status,notes) VALUES(?,?,?,?, 'pending',?)",(request_id,tenant_id,user_id,request_type,notes))
            conn.commit()
        return self.get_data_subject_request(request_id,tenant_id)

    def get_data_subject_request(self, request_id: str, tenant_id: str) -> dict:
        with self._connect() as conn:
            row=conn.execute("SELECT * FROM data_subject_requests WHERE request_id=? AND tenant_id=?",(request_id,tenant_id)).fetchone()
        if not row: raise KeyError(request_id)
        d=dict(row); d["result"]=json.loads(d.pop("result_json") or "{}"); return d

    def list_data_subject_requests(self, *, tenant_id: str, user_id: str | None = None) -> list[dict]:
        with self._connect() as conn:
            rows=conn.execute("SELECT * FROM data_subject_requests WHERE tenant_id=? AND user_id=? ORDER BY created_at DESC",(tenant_id,user_id)).fetchall() if user_id else conn.execute("SELECT * FROM data_subject_requests WHERE tenant_id=? ORDER BY created_at DESC",(tenant_id,)).fetchall()
        out=[]
        for r in rows: d=dict(r); d["result"]=json.loads(d.pop("result_json") or "{}"); out.append(d)
        return out

    def update_data_subject_request(self, *, request_id: str, tenant_id: str, status: str, result: dict | None = None) -> dict:
        if status not in {"pending","processing","completed","rejected"}: raise ValueError("invalid request status")
        with self._lock, self._connect() as conn:
            cur=conn.execute("UPDATE data_subject_requests SET status=?,result_json=?,processed_at=CASE WHEN ? IN ('completed','rejected') THEN CURRENT_TIMESTAMP ELSE processed_at END WHERE request_id=? AND tenant_id=?",(status,json.dumps(result or {},ensure_ascii=False),status,request_id,tenant_id))
            if cur.rowcount == 0: raise KeyError(request_id)
            conn.commit()
        return self.get_data_subject_request(request_id,tenant_id)

    def create_class(self, tenant_id: str, name: str, class_id: str | None = None) -> dict:
        class_id = class_id or f"CLS-{uuid4().hex[:12].upper()}"
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT INTO classes(class_id,tenant_id,name,status) VALUES(?,?,?, 'active')",
                    (class_id, tenant_id, name.strip()),
                )
                conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("group already exists") from exc
        return self.get_class(class_id)

    def get_class(self, class_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM classes WHERE class_id=?", (class_id,)).fetchone()
        if not row:
            raise KeyError(class_id)
        return dict(row)

    def list_classes(self, tenant_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM classes WHERE tenant_id=? AND status='active' ORDER BY name", (tenant_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def add_class_member(self, *, class_id: str, tenant_id: str, user_id: str, role: str) -> None:
        role = storage_role(role)
        if role not in {"teacher", "student"}:
            raise ValueError("group role must be advisor/participant (legacy teacher/student aliases are accepted)")
        with self._lock, self._connect() as conn:
            klass = conn.execute("SELECT tenant_id FROM classes WHERE class_id=?", (class_id,)).fetchone()
            if not klass or klass["tenant_id"] != tenant_id:
                raise KeyError("class not found in tenant")
            membership = conn.execute(
                "SELECT 1 FROM tenant_memberships WHERE tenant_id=? AND user_id=? AND role=? AND status='active'",
                (tenant_id, user_id, role),
            ).fetchone()
            if not membership:
                raise PermissionError("user does not have matching tenant role")
            conn.execute(
                """INSERT OR IGNORE INTO class_memberships(class_membership_id,class_id,tenant_id,user_id,role)
                VALUES(?,?,?,?,?)""",
                (f"CM-{uuid4().hex[:16].upper()}", class_id, tenant_id, user_id, role),
            )
            conn.commit()

    def user_class_ids(self, user_id: str, tenant_id: str, role: str | None = None) -> set[str]:
        params: list[str] = [user_id, tenant_id]
        sql = "SELECT class_id FROM class_memberships WHERE user_id=? AND tenant_id=?"
        if role:
            sql += " AND role=?"
            params.append(role)
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return {str(r["class_id"]) for r in rows}

    # Canonical group aliases. Legacy class methods remain for backward compatibility.
    def create_group(self, tenant_id: str, name: str, group_id: str | None = None) -> dict:
        return self.create_class(tenant_id, name, class_id=group_id)

    def get_group(self, group_id: str) -> dict:
        data = self.get_class(group_id)
        data["group_id"] = data.get("class_id", group_id)
        return data

    def list_groups(self, tenant_id: str) -> list[dict]:
        out = []
        for item in self.list_classes(tenant_id):
            row = dict(item)
            row["group_id"] = row.get("class_id", "")
            out.append(row)
        return out

    def add_group_member(self, *, group_id: str, tenant_id: str, user_id: str, role: str) -> None:
        return self.add_class_member(class_id=group_id, tenant_id=tenant_id, user_id=user_id, role=role)

    def user_group_ids(self, user_id: str, tenant_id: str, role: str | None = None) -> set[str]:
        return self.user_class_ids(user_id, tenant_id, role=storage_role(role) if role else None)

    def audit(
        self,
        *,
        tenant_id: str,
        user_id: str,
        action: str,
        resource_type: str = "",
        resource_id: str = "",
        success: bool = True,
        details: dict | None = None,
        ip_address: str = "",
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO security_audit_log(tenant_id,user_id,action,resource_type,resource_id,success,details_json,ip_address)
                VALUES(?,?,?,?,?,?,?,?)""",
                (
                    tenant_id or "global", user_id or "", action, resource_type, resource_id,
                    1 if success else 0, json.dumps(details or {}, ensure_ascii=False)[:8000], ip_address[:120],
                ),
            )
            conn.commit()

    def anonymize_user_identity(self, *, user_id: str, tenant_id: str) -> dict:
        """De-identify a user while retaining an internal pseudonymous key for audit/legal references."""
        marker = hashlib.sha256(f"{tenant_id}:{user_id}".encode()).hexdigest()[:20]
        anonymized_email = f"deleted+{marker}@invalid.local"
        random_password = self.hash_password(secrets.token_urlsafe(48))
        with self._lock, self._connect() as conn:
            membership = conn.execute("SELECT 1 FROM tenant_memberships WHERE tenant_id=? AND user_id=?", (tenant_id, user_id)).fetchone()
            if not membership:
                raise KeyError(user_id)
            conn.execute("UPDATE users SET email=?,display_name='Deleted User',password_hash=?,status='archived',updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (anonymized_email, random_password, user_id))
            conn.execute("UPDATE tenant_memberships SET status='inactive' WHERE tenant_id=? AND user_id=?", (tenant_id, user_id))
            conn.execute("UPDATE class_memberships SET role=role WHERE tenant_id=? AND user_id=?", (tenant_id, user_id))
            conn.execute("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=? AND revoked_at IS NULL", (user_id,))
            conn.execute("DELETE FROM password_reset_tokens WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM privacy_consents WHERE tenant_id=? AND user_id=?", (tenant_id, user_id))
            conn.commit()
        return {"user_id": user_id, "tenant_id": tenant_id, "status": "archived", "display_name": "Deleted User", "email": anonymized_email}
