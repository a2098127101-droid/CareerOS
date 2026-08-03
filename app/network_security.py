from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class OutboundURLSecurityError(ValueError):
    pass


_BLOCKED_HOSTS = {
    "localhost", "localhost.localdomain", "metadata", "metadata.google.internal",
    "instance-data", "kubernetes.default", "kubernetes.default.svc",
}


def _is_private_or_special(ip_text: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_text)
    except ValueError:
        return False
    return bool(
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
        or ip.is_reserved or ip.is_unspecified
    )


def validate_outbound_url(url: str, *, allow_private_network: bool = False) -> str:
    """Validate configurable outbound provider URLs against common SSRF targets.

    Private/self-hosted networks are supported only when a super-admin explicitly enables the
    provider's allow_private_network flag. We resolve the hostname when possible and reject any
    private/special address in the answer set, reducing DNS-alias bypasses. Resolution failures are
    left to the HTTP client so mock transports and temporarily unavailable public DNS still work.
    """
    value = (url or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise OutboundURLSecurityError("provider URL must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise OutboundURLSecurityError("credentials in provider URL are not allowed")
    host = parsed.hostname.rstrip(".").lower()
    if allow_private_network:
        return value
    if host in _BLOCKED_HOSTS or host.endswith(".localhost") or host.endswith(".local"):
        raise OutboundURLSecurityError("private/local provider URL requires allow_private_network=true")
    if _is_private_or_special(host):
        raise OutboundURLSecurityError("private/special provider IP requires allow_private_network=true")
    try:
        answers = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError:
        return value
    ips = {entry[4][0] for entry in answers if entry and entry[4]}
    if any(_is_private_or_special(ip) for ip in ips):
        raise OutboundURLSecurityError("provider hostname resolves to a private/special network")
    return value


def validate_nonsecret_metadata(headers: dict[str, str] | None, query_params: dict[str, str] | None) -> None:
    """Reject likely secrets from plaintext provider metadata.

    Secrets belong in the encrypted primary credential fields. Custom header/query *names* remain
    configurable through auth_header_name/api_key_query_name without persisting the secret value.
    """
    sensitive_tokens = ("authorization", "api-key", "apikey", "token", "secret", "password", "credential", "cookie")
    for location, values in (("extra_headers", headers or {}), ("query_params", query_params or {})):
        for key in values:
            lowered = str(key).strip().lower()
            if any(token in lowered for token in sensitive_tokens):
                raise OutboundURLSecurityError(
                    f"{location}.{key} looks secret-bearing; use encrypted api_key/auth configuration instead"
                )
