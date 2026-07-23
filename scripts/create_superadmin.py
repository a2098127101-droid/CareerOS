from __future__ import annotations

import argparse
import getpass

from app.auth_store import AuthStore
from app.config import Settings
from app.migrations import run_migrations


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or attach a CareerOS super-admin account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--tenant-id", default="platform")
    parser.add_argument("--tenant-name", default="CareerOS Platform")
    parser.add_argument("--name", default="CareerOS Super Admin")
    args = parser.parse_args()
    password = getpass.getpass("Password (>=10 chars): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match")
    settings = Settings()
    run_migrations(settings.db_path)
    auth = AuthStore(settings.db_path, session_ttl_hours=settings.session_ttl_hours)
    auth.ensure_tenant(args.tenant_id, args.tenant_name)
    user = auth.ensure_user(
        email=args.email,
        password=password,
        display_name=args.name,
        tenant_id=args.tenant_id,
        role="super_admin",
    )
    print(f"Created/updated super admin: {user['email']} ({user['user_id']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
