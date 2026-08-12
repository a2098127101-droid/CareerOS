from __future__ import annotations

import re

from fastapi import FastAPI
from fastapi.routing import APIRoute


_ALREADY_VERSIONED = re.compile(r"^/api/(?:v\d+|[^/]+/v\d+)(?:/|$)")


def _api_routes(routes) -> list[APIRoute]:
    """Flatten FastAPI routes across eager and lazy included routers.

    FastAPI 0.140 introduced lazy ``_IncludedRouter`` entries. Looking only at
    ``app.routes`` silently skips those routes and produces an incomplete
    versioned API surface.
    """

    found: list[APIRoute] = []
    seen: set[int] = set()

    def visit(items) -> None:
        for item in items:
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            if isinstance(item, APIRoute):
                found.append(item)
                continue
            original = getattr(item, "original_router", None)
            nested = getattr(original, "routes", None) if original is not None else None
            if nested is None:
                nested = getattr(item, "routes", None)
            if nested is not None:
                visit(nested)

    visit(routes)
    return found


def register_v1_compatibility_aliases(app: FastAPI) -> int:
    """Register StepIn Foundation, then expose canonical `/api/v1` aliases.

    Foundation is deliberately attached here because this hook runs once after
    the production application has initialized repositories, authorization,
    security middleware, legacy routes, and the project runtime. This keeps the
    integration additive and avoids replacing the hardened production main.
    """
    from .foundation_production import register_foundation_production_routes

    register_foundation_production_routes(app)

    routes = _api_routes(app.router.routes)
    existing = {route.path for route in routes}
    created = 0
    for route in routes:
        if not route.path.startswith("/api/") or _ALREADY_VERSIONED.match(route.path):
            continue
        alias_path = "/api/v1" + route.path[len("/api"):]
        if alias_path in existing:
            continue
        route.deprecated = True
        app.add_api_route(
            alias_path,
            route.endpoint,
            methods=sorted(route.methods or {"GET"}),
            response_model=route.response_model,
            status_code=route.status_code,
            tags=list(route.tags or []),
            dependencies=list(route.dependencies or []),
            summary=route.summary,
            description=route.description,
            response_description=route.response_description,
            responses=dict(route.responses or {}),
            deprecated=False,
            name=f"v1_{route.name}",
            response_class=route.response_class,
            openapi_extra=dict(route.openapi_extra or {}),
        )
        existing.add(alias_path)
        created += 1
    return created
