from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from ...auth_store import Principal
from ...domain.roles import CANONICAL_ROLES, LEGACY_ROLES, canonical_role, storage_role
from ..sqlalchemy_common import SQLAlchemyRepo

VALID_ROLES = CANONICAL_ROLES | LEGACY_ROLES


class PostgresIdentityRepository(SQLAlchemyRepo):
    """SQLAlchemy identity/tenant repository designed for PostgreSQL and parity-tested on SQLite."""

    def __init__(self, engine: Engine, session_ttl_hours: int = 168):
        super().__init__(engine)
        self.session_ttl_hours = session_ttl_hours
        self._ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _dt(value) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        text_value = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text_value)
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
        with self.engine.begin() as conn:
            existing = conn.execute(text("SELECT tenant_id FROM tenants WHERE tenant_id=:tenant_id"), {"tenant_id": tenant_id}).first()
            if existing:
                conn.execute(text("""UPDATE tenants SET name=:name,tenant_type=:tenant_type,product_preset=:product_preset,updated_at=CURRENT_TIMESTAMP WHERE tenant_id=:tenant_id"""),
                             {"name": name.strip() or tenant_id, "tenant_type": tenant_type, "product_preset": product_preset, "tenant_id": tenant_id})
            else:
                conn.execute(text("""INSERT INTO tenants(tenant_id,name,status,tenant_type,product_preset,branding_json,settings_json)
                    VALUES(:tenant_id,:name,'active',:tenant_type,:product_preset,'{}','{}')"""),
                             {"tenant_id": tenant_id, "name": name.strip() or tenant_id, "tenant_type": tenant_type, "product_preset": product_preset})
        return self.get_tenant(tenant_id)

    def get_tenant(self, tenant_id: str) -> dict:
        row = self.one("SELECT * FROM tenants WHERE tenant_id=:tenant_id", {"tenant_id": tenant_id})
        if not row:
            raise KeyError(tenant_id)
        data = dict(row)
        data["branding"] = json.loads(data.pop("branding_json") or "{}")
        data["settings"] = json.loads(data.pop("settings_json", "{}") or "{}")
        return data

    def list_tenants(self) -> list[dict]:
        out=[]
        for row in self.all("SELECT * FROM tenants WHERE status='active' ORDER BY created_at DESC"):
            data=dict(row); data["branding"]=json.loads(data.pop("branding_json") or "{}"); data["settings"]=json.loads(data.pop("settings_json", "{}") or "{}"); out.append(data)
        return out

    def update_tenant_branding(self, tenant_id: str, branding: dict) -> dict:
        count=self.execute("UPDATE tenants SET branding_json=:branding,updated_at=CURRENT_TIMESTAMP WHERE tenant_id=:tenant_id", {"branding":json.dumps(branding or {},ensure_ascii=False),"tenant_id":tenant_id})
        if not count: raise KeyError(tenant_id)
        return self.get_tenant(tenant_id)

    def update_tenant_product_config(self, tenant_id: str, *, tenant_type: str | None=None, product_preset: str | None=None, settings: dict | None=None) -> dict:
        values=self.get_tenant(tenant_id)
        return self._update_tenant_config(tenant_id, tenant_type or values.get("tenant_type","organization"), product_preset or values.get("product_preset","career_development"), settings if settings is not None else values.get("settings",{}))

    def _update_tenant_config(self, tenant_id: str, tenant_type: str, product_preset: str, settings: dict) -> dict:
        self.execute("""UPDATE tenants SET tenant_type=:tenant_type,product_preset=:product_preset,settings_json=:settings,updated_at=CURRENT_TIMESTAMP WHERE tenant_id=:tenant_id""",
                     {"tenant_type":tenant_type,"product_preset":product_preset,"settings":json.dumps(settings or {},ensure_ascii=False),"tenant_id":tenant_id})
        return self.get_tenant(tenant_id)

    def create_user(self, *, email: str, password: str, display_name: str, tenant_id: str, role: str, user_id: str | None=None) -> dict:
        if role not in VALID_ROLES: raise ValueError("invalid role")
        role=storage_role(role); email=email.strip().lower()
        if "@" not in email: raise ValueError("invalid email")
        user_id=user_id or f"USR-{uuid4().hex[:16].upper()}"; membership_id=f"MEM-{uuid4().hex[:16].upper()}"
        password_hash=self.hash_password(password)
        try:
            with self.engine.begin() as conn:
                if not conn.execute(text("SELECT 1 FROM tenants WHERE tenant_id=:tenant_id"),{"tenant_id":tenant_id}).first(): raise KeyError(f"tenant not found: {tenant_id}")
                conn.execute(text("INSERT INTO users(user_id,email,password_hash,display_name,status) VALUES(:user_id,:email,:password_hash,:display_name,'active')"),locals())
                conn.execute(text("INSERT INTO tenant_memberships(membership_id,tenant_id,user_id,role,status) VALUES(:membership_id,:tenant_id,:user_id,:role,'active')"),locals())
        except IntegrityError as exc:
            raise ValueError("user or membership already exists") from exc
        return self.get_user(user_id,include_memberships=True)

    def ensure_user(self, *, email: str, password: str, display_name: str, tenant_id: str, role: str) -> dict:
        if role not in VALID_ROLES: raise ValueError("invalid role")
        role=storage_role(role); existing=self.find_user_by_email(email)
        if existing:
            with self.engine.begin() as conn:
                row=conn.execute(text("SELECT 1 FROM tenant_memberships WHERE tenant_id=:tenant_id AND user_id=:user_id AND role=:role"),{"tenant_id":tenant_id,"user_id":existing["user_id"],"role":role}).first()
                if not row:
                    conn.execute(text("INSERT INTO tenant_memberships(membership_id,tenant_id,user_id,role,status) VALUES(:membership_id,:tenant_id,:user_id,:role,'active')"),{"membership_id":f"MEM-{uuid4().hex[:16].upper()}","tenant_id":tenant_id,"user_id":existing["user_id"],"role":role})
            return self.get_user(existing["user_id"],include_memberships=True)
        return self.create_user(email=email,password=password,display_name=display_name,tenant_id=tenant_id,role=role)

    def find_user_by_email(self,email:str)->dict|None:
        row=self.one("SELECT * FROM users WHERE lower(email)=lower(:email)",{"email":email.strip()}); return dict(row) if row else None

    def get_user(self,user_id:str,include_memberships:bool=False)->dict:
        row=self.one("SELECT user_id,email,display_name,status,created_at,updated_at FROM users WHERE user_id=:user_id",{"user_id":user_id})
        if not row: raise KeyError(user_id)
        data=dict(row)
        if include_memberships:
            items=[dict(r) for r in self.all("SELECT tenant_id,role,status,created_at FROM tenant_memberships WHERE user_id=:user_id ORDER BY created_at",{"user_id":user_id})]
            for x in items: x["canonical_role"]=canonical_role(x.get("role",""))
            data["memberships"]=items
        return data

    def list_users(self,tenant_id:str,role:str|None=None)->list[dict]:
        sql="""SELECT u.user_id,u.email,u.display_name,u.status,u.created_at,m.role,m.tenant_id FROM users u JOIN tenant_memberships m ON m.user_id=u.user_id WHERE m.tenant_id=:tenant_id AND m.status='active'"""
        params={"tenant_id":tenant_id}
        if role: sql+=" AND m.role=:role"; params["role"]=storage_role(role)
        sql+=" ORDER BY u.created_at DESC"
        out=[dict(r) for r in self.all(sql,params)]
        for x in out: x["canonical_role"]=canonical_role(x.get("role",""))
        return out

    def memberships(self,user_id:str)->list[dict]:
        out=[dict(r) for r in self.all("SELECT tenant_id,role,status FROM tenant_memberships WHERE user_id=:user_id AND status='active' ORDER BY created_at",{"user_id":user_id})]
        for x in out: x["canonical_role"]=canonical_role(x.get("role",""))
        return out

    def authenticate(self,email:str,password:str,tenant_id:str|None=None,role:str|None=None)->tuple[Principal,str]:
        user=self.find_user_by_email(email)
        if not user or user["status"]!="active" or not self.verify_password(user["password_hash"],password): raise PermissionError("invalid credentials")
        memberships=self.memberships(user["user_id"])
        if tenant_id: memberships=[m for m in memberships if m["tenant_id"]==tenant_id]
        if role: memberships=[m for m in memberships if canonical_role(m["role"])==canonical_role(role)]
        if not memberships: raise PermissionError("no active membership")
        m=next((m for m in memberships if m["role"]=="super_admin"),memberships[0])
        p=Principal(user_id=user["user_id"],email=user["email"],display_name=user["display_name"],tenant_id=m["tenant_id"],role=m["role"])
        return p,self.create_session(p)

    def create_session(self,principal:Principal)->str:
        raw=secrets.token_urlsafe(48); auth_session_id=f"AUTH-{uuid4().hex[:18].upper()}"; expires=self._now()+timedelta(hours=self.session_ttl_hours)
        self.execute("INSERT INTO auth_sessions(auth_session_id,token_hash,user_id,tenant_id,role,expires_at) VALUES(:id,:token,:user,:tenant,:role,:expires)",{"id":auth_session_id,"token":self._token_hash(raw),"user":principal.user_id,"tenant":principal.tenant_id,"role":principal.role,"expires":expires})
        return raw

    def resolve_session(self,raw_token:str|None)->Principal|None:
        if not raw_token:return None
        row=self.one("""SELECT s.*,u.email,u.display_name,u.status AS user_status,m.status AS membership_status FROM auth_sessions s JOIN users u ON u.user_id=s.user_id JOIN tenant_memberships m ON m.user_id=s.user_id AND m.tenant_id=s.tenant_id AND m.role=s.role WHERE s.token_hash=:token AND s.revoked_at IS NULL""",{"token":self._token_hash(raw_token)})
        if not row:return None
        if self._dt(row["expires_at"])<=self._now() or row["user_status"]!="active" or row["membership_status"]!="active":
            self.execute("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE auth_session_id=:id",{"id":row["auth_session_id"]}); return None
        self.execute("UPDATE auth_sessions SET last_seen_at=CURRENT_TIMESTAMP WHERE auth_session_id=:id",{"id":row["auth_session_id"]})
        return Principal(user_id=row["user_id"],email=row["email"],display_name=row["display_name"],tenant_id=row["tenant_id"],role=row["role"])

    def revoke_session(self,raw_token:str|None)->None:
        if raw_token:self.execute("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE token_hash=:token",{"token":self._token_hash(raw_token)})

    def change_password(self,user_id:str,old_password:str,new_password:str)->None:
        row=self.one("SELECT password_hash FROM users WHERE user_id=:id",{"id":user_id})
        if not row or not self.verify_password(row["password_hash"],old_password):raise PermissionError("invalid current password")
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE users SET password_hash=:h,updated_at=CURRENT_TIMESTAMP WHERE user_id=:id"),{"h":self.hash_password(new_password),"id":user_id})
            conn.execute(text("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=:id"),{"id":user_id})

    def request_password_reset(self,email:str,ttl_minutes:int=30)->str|None:
        user=self.find_user_by_email(email)
        if not user:return None
        raw=secrets.token_urlsafe(40); expires=self._now()+timedelta(minutes=ttl_minutes)
        self.execute("INSERT INTO password_reset_tokens(reset_id,token_hash,user_id,expires_at) VALUES(:id,:token,:user,:expires)",{"id":f"RESET-{uuid4().hex[:16].upper()}","token":self._token_hash(raw),"user":user["user_id"],"expires":expires})
        return raw

    def reset_password(self,raw_token:str,new_password:str)->None:
        row=self.one("SELECT * FROM password_reset_tokens WHERE token_hash=:token AND used_at IS NULL",{"token":self._token_hash(raw_token)})
        if not row or self._dt(row["expires_at"])<=self._now():raise PermissionError("invalid or expired reset token")
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE users SET password_hash=:h,updated_at=CURRENT_TIMESTAMP WHERE user_id=:id"),{"h":self.hash_password(new_password),"id":row["user_id"]})
            conn.execute(text("UPDATE password_reset_tokens SET used_at=CURRENT_TIMESTAMP WHERE reset_id=:id"),{"id":row["reset_id"]})
            conn.execute(text("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=:id"),{"id":row["user_id"]})

    def create_invitation(self,*,email:str,tenant_id:str,role:str,invited_by:str="",display_name:str="",ttl_hours:int=72)->dict:
        if role not in VALID_ROLES: raise ValueError("invalid role")
        role=storage_role(role);email=email.strip().lower()
        if "@" not in email: raise ValueError("invalid email")
        if not self.one("SELECT 1 FROM tenants WHERE tenant_id=:tenant AND status='active'",{"tenant":tenant_id}): raise KeyError("tenant not found")
        raw=secrets.token_urlsafe(40);invitation_id=f"INV-{uuid4().hex[:16].upper()}";expires=self._now()+timedelta(hours=max(1,int(ttl_hours)))
        self.execute("INSERT INTO user_invitations(invitation_id,token_hash,tenant_id,email,role,display_name,invited_by,expires_at) VALUES(:id,:token,:tenant,:email,:role,:name,:by,:expires)",{"id":invitation_id,"token":self._token_hash(raw),"tenant":tenant_id,"email":email,"role":role,"name":display_name.strip(),"by":invited_by,"expires":expires})
        return {"invitation_id":invitation_id,"token":raw,"tenant_id":tenant_id,"email":email,"role":role,"display_name":display_name.strip(),"expires_at":expires.isoformat()}
    def list_invitations(self,tenant_id:str,include_closed:bool=False)->list[dict]:
        sql="SELECT invitation_id,tenant_id,email,role,display_name,invited_by,expires_at,accepted_at,revoked_at,created_at FROM user_invitations WHERE tenant_id=:tenant"
        if not include_closed: sql+=" AND accepted_at IS NULL AND revoked_at IS NULL"
        return [dict(r) for r in self.all(sql+" ORDER BY created_at DESC",{"tenant":tenant_id})]
    def revoke_invitation(self,invitation_id:str,tenant_id:str)->None:
        if not self.execute("UPDATE user_invitations SET revoked_at=CURRENT_TIMESTAMP WHERE invitation_id=:id AND tenant_id=:tenant AND accepted_at IS NULL",{"id":invitation_id,"tenant":tenant_id}): raise KeyError(invitation_id)
    def accept_invitation(self,raw_token:str,password:str,display_name:str="")->dict:
        row=self.one("SELECT * FROM user_invitations WHERE token_hash=:token AND accepted_at IS NULL AND revoked_at IS NULL",{"token":self._token_hash(raw_token)})
        if not row or self._dt(row["expires_at"])<=self._now(): raise PermissionError("invalid or expired invitation")
        existing=self.find_user_by_email(row["email"])
        if existing:
            user_id=existing["user_id"]
            if not self.one("SELECT 1 FROM tenant_memberships WHERE tenant_id=:tenant AND user_id=:user AND role=:role",{"tenant":row["tenant_id"],"user":user_id,"role":row["role"]}):
                self.execute("INSERT INTO tenant_memberships(membership_id,tenant_id,user_id,role,status) VALUES(:id,:tenant,:user,:role,'active')",{"id":f"MEM-{uuid4().hex[:16].upper()}","tenant":row["tenant_id"],"user":user_id,"role":row["role"]})
        else:
            user=self.create_user(email=row["email"],password=password,display_name=(display_name.strip() or row["display_name"] or str(row["email"]).split('@')[0]),tenant_id=row["tenant_id"],role=row["role"]);user_id=user["user_id"]
        self.execute("UPDATE user_invitations SET accepted_at=CURRENT_TIMESTAMP WHERE invitation_id=:id",{"id":row["invitation_id"]})
        return self.get_user(user_id,include_memberships=True)
    def set_user_status(self,*,user_id:str,tenant_id:str,status:str)->dict:
        if status not in {"active","disabled","archived"}: raise ValueError("invalid user status")
        if not self.one("SELECT 1 FROM tenant_memberships WHERE tenant_id=:tenant AND user_id=:user",{"tenant":tenant_id,"user":user_id}): raise KeyError(user_id)
        self.execute("UPDATE users SET status=:status,updated_at=CURRENT_TIMESTAMP WHERE user_id=:user",{"status":status,"user":user_id})
        if status!="active": self.execute("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=:user AND revoked_at IS NULL",{"user":user_id})
        return self.get_user(user_id,include_memberships=True)
    def change_membership_role(self,*,user_id:str,tenant_id:str,role:str)->dict:
        if role not in VALID_ROLES: raise ValueError("invalid role")
        role=storage_role(role); rows=self.all("SELECT membership_id FROM tenant_memberships WHERE tenant_id=:tenant AND user_id=:user AND status='active' ORDER BY created_at",{"tenant":tenant_id,"user":user_id})
        if not rows: raise KeyError(user_id)
        self.execute("UPDATE tenant_memberships SET role=:role WHERE membership_id=:id",{"role":role,"id":rows[0]["membership_id"]})
        for x in rows[1:]: self.execute("UPDATE tenant_memberships SET status='inactive' WHERE membership_id=:id",{"id":x["membership_id"]})
        self.execute("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=:user AND tenant_id=:tenant AND revoked_at IS NULL",{"user":user_id,"tenant":tenant_id})
        return self.get_user(user_id,include_memberships=True)
    def record_consent(self,*,tenant_id:str,user_id:str,policy_version:str,purpose:str="service",granted:bool=True,source:str="ui")->dict:
        consent_id=f"CONS-{uuid4().hex[:16].upper()}";self.execute("INSERT INTO privacy_consents(consent_id,tenant_id,user_id,policy_version,purpose,granted,source) VALUES(:id,:tenant,:user,:version,:purpose,:granted,:source)",{"id":consent_id,"tenant":tenant_id,"user":user_id,"version":policy_version,"purpose":purpose,"granted":1 if granted else 0,"source":source});return {"consent_id":consent_id,"tenant_id":tenant_id,"user_id":user_id,"policy_version":policy_version,"purpose":purpose,"granted":granted,"source":source}
    def list_consents(self,*,tenant_id:str,user_id:str)->list[dict]:
        out=[dict(r) for r in self.all("SELECT * FROM privacy_consents WHERE tenant_id=:tenant AND user_id=:user ORDER BY created_at DESC",{"tenant":tenant_id,"user":user_id})]
        for x in out:x["granted"]=bool(x["granted"])
        return out
    def create_data_subject_request(self,*,tenant_id:str,user_id:str,request_type:str,notes:str="")->dict:
        if request_type not in {"export","delete"}: raise ValueError("invalid request type")
        rid=f"DSR-{uuid4().hex[:16].upper()}";self.execute("INSERT INTO data_subject_requests(request_id,tenant_id,user_id,request_type,status,notes) VALUES(:id,:tenant,:user,:type,'pending',:notes)",{"id":rid,"tenant":tenant_id,"user":user_id,"type":request_type,"notes":notes});return self.get_data_subject_request(rid,tenant_id)
    def get_data_subject_request(self,request_id:str,tenant_id:str)->dict:
        r=self.one("SELECT * FROM data_subject_requests WHERE request_id=:id AND tenant_id=:tenant",{"id":request_id,"tenant":tenant_id})
        if not r:raise KeyError(request_id)
        d=dict(r);d["result"]=json.loads(d.pop("result_json") or "{}");return d
    def list_data_subject_requests(self,*,tenant_id:str,user_id:str|None=None)->list[dict]:
        rows=self.all("SELECT * FROM data_subject_requests WHERE tenant_id=:tenant AND user_id=:user ORDER BY created_at DESC",{"tenant":tenant_id,"user":user_id}) if user_id else self.all("SELECT * FROM data_subject_requests WHERE tenant_id=:tenant ORDER BY created_at DESC",{"tenant":tenant_id})
        out=[]
        for r in rows:d=dict(r);d["result"]=json.loads(d.pop("result_json") or "{}");out.append(d)
        return out
    def update_data_subject_request(self,*,request_id:str,tenant_id:str,status:str,result:dict|None=None)->dict:
        if status not in {"pending","processing","completed","rejected"}:raise ValueError("invalid request status")
        processed=self._now() if status in {"completed","rejected"} else None
        if not self.execute("UPDATE data_subject_requests SET status=:status,result_json=:result,processed_at=:processed WHERE request_id=:id AND tenant_id=:tenant",{"status":status,"result":json.dumps(result or {},ensure_ascii=False),"processed":processed,"id":request_id,"tenant":tenant_id}):raise KeyError(request_id)
        return self.get_data_subject_request(request_id,tenant_id)

    def create_class(self,tenant_id:str,name:str,class_id:str|None=None)->dict:
        class_id=class_id or f"CLS-{uuid4().hex[:12].upper()}"
        try:self.execute("INSERT INTO classes(class_id,tenant_id,name,status) VALUES(:id,:tenant,:name,'active')",{"id":class_id,"tenant":tenant_id,"name":name.strip()})
        except IntegrityError as exc:raise ValueError("group already exists") from exc
        return self.get_class(class_id)

    def get_class(self,class_id:str)->dict:
        row=self.one("SELECT * FROM classes WHERE class_id=:id",{"id":class_id})
        if not row:raise KeyError(class_id)
        return dict(row)

    def list_classes(self,tenant_id:str)->list[dict]:return [dict(r) for r in self.all("SELECT * FROM classes WHERE tenant_id=:tenant AND status='active' ORDER BY name",{"tenant":tenant_id})]

    def add_class_member(self,*,class_id:str,tenant_id:str,user_id:str,role:str)->None:
        role=storage_role(role)
        if role not in {"teacher","student"}:raise ValueError("group role must be advisor/participant (legacy teacher/student aliases are accepted)")
        with self.engine.begin() as conn:
            klass=conn.execute(text("SELECT tenant_id FROM classes WHERE class_id=:id"),{"id":class_id}).mappings().first()
            if not klass or klass["tenant_id"]!=tenant_id:raise KeyError("class not found in tenant")
            membership=conn.execute(text("SELECT 1 FROM tenant_memberships WHERE tenant_id=:tenant AND user_id=:user AND role=:role AND status='active'"),{"tenant":tenant_id,"user":user_id,"role":role}).first()
            if not membership:raise PermissionError("user does not have matching tenant role")
            exists=conn.execute(text("SELECT 1 FROM class_memberships WHERE class_id=:class_id AND user_id=:user AND role=:role"),{"class_id":class_id,"user":user_id,"role":role}).first()
            if not exists:conn.execute(text("INSERT INTO class_memberships(class_membership_id,class_id,tenant_id,user_id,role) VALUES(:id,:class_id,:tenant,:user,:role)"),{"id":f"CM-{uuid4().hex[:16].upper()}","class_id":class_id,"tenant":tenant_id,"user":user_id,"role":role})

    def user_class_ids(self,user_id:str,tenant_id:str,role:str|None=None)->set[str]:
        sql="SELECT class_id FROM class_memberships WHERE user_id=:user AND tenant_id=:tenant"; params={"user":user_id,"tenant":tenant_id}
        if role:sql+=" AND role=:role";params["role"]=role
        return {str(r["class_id"]) for r in self.all(sql,params)}

    def create_group(self,tenant_id:str,name:str,group_id:str|None=None)->dict:return self.create_class(tenant_id,name,class_id=group_id)
    def get_group(self,group_id:str)->dict:
        d=self.get_class(group_id);d["group_id"]=d.get("class_id",group_id);return d
    def list_groups(self,tenant_id:str)->list[dict]:
        out=[]
        for x in self.list_classes(tenant_id):d=dict(x);d["group_id"]=d.get("class_id","");out.append(d)
        return out
    def add_group_member(self,*,group_id:str,tenant_id:str,user_id:str,role:str)->None:self.add_class_member(class_id=group_id,tenant_id=tenant_id,user_id=user_id,role=role)
    def user_group_ids(self,user_id:str,tenant_id:str,role:str|None=None)->set[str]:return self.user_class_ids(user_id,tenant_id,role=storage_role(role) if role else None)

    def audit(self,*,tenant_id:str,user_id:str,action:str,resource_type:str="",resource_id:str="",success:bool=True,details:dict|None=None,ip_address:str="")->None:
        self.execute("""INSERT INTO security_audit_log(tenant_id,user_id,action,resource_type,resource_id,success,details_json,ip_address) VALUES(:tenant,:user,:action,:rtype,:rid,:success,:details,:ip)""",{"tenant":tenant_id or "global","user":user_id or "","action":action,"rtype":resource_type,"rid":resource_id,"success":1 if success else 0,"details":json.dumps(details or {},ensure_ascii=False)[:8000],"ip":ip_address[:120]})

    def anonymize_user_identity(self, *, user_id: str, tenant_id: str) -> dict:
        import hashlib, secrets
        marker = hashlib.sha256(f"{tenant_id}:{user_id}".encode()).hexdigest()[:20]
        anonymized_email = f"deleted+{marker}@invalid.local"
        random_password = self.hash_password(secrets.token_urlsafe(48))
        membership = self.one("SELECT 1 AS ok FROM tenant_memberships WHERE tenant_id=:tenant AND user_id=:user", {"tenant": tenant_id, "user": user_id})
        if not membership:
            raise KeyError(user_id)
        with self.engine.begin() as conn:
            from sqlalchemy import text
            conn.execute(text("UPDATE users SET email=:email,display_name='Deleted User',password_hash=:password,status='archived',updated_at=CURRENT_TIMESTAMP WHERE user_id=:user"), {"email": anonymized_email, "password": random_password, "user": user_id})
            conn.execute(text("UPDATE tenant_memberships SET status='inactive' WHERE tenant_id=:tenant AND user_id=:user"), {"tenant": tenant_id, "user": user_id})
            conn.execute(text("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=:user AND revoked_at IS NULL"), {"user": user_id})
            conn.execute(text("DELETE FROM password_reset_tokens WHERE user_id=:user"), {"user": user_id})
            conn.execute(text("DELETE FROM privacy_consents WHERE tenant_id=:tenant AND user_id=:user"), {"tenant": tenant_id, "user": user_id})
        return {"user_id": user_id, "tenant_id": tenant_id, "status": "archived", "display_name": "Deleted User", "email": anonymized_email}
