"""Link assessment and an allowlist-only fetch guard.

CEKBAO does not open links from pasted messages. It only parses them and
compares the host with the reviewed official domains in the registry.

`safe_fetch` exists for registry maintenance (checking that a reviewed source
URL still resolves). It refuses every host outside the allowlist, every
non-public IP address and every redirect to a host outside the allowlist.
The analysis workflow never calls it.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.parse import urljoin, urlsplit

import httpx

from .models import CheckStatus

_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\"')\]]+")


def extract_urls(text: str) -> list[str]:
    seen: list[str] = []
    for m in _URL_RE.finditer(text):
        url = m.group(0).rstrip(".,;:!?")
        if url.lower().startswith("www."):
            url = "http://" + url
        if url not in seen:
            seen.append(url)
    return seen[:20]


def host_matches_domain(host: str, domain: str) -> bool:
    """Exact domain or a real subdomain at a label boundary."""
    host = host.lower().rstrip(".")
    domain = domain.lower().rstrip(".")
    return host == domain or host.endswith("." + domain)


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


@dataclass
class LinkAssessment:
    url: str
    host: str | None
    status: CheckStatus
    reason: str


def assess_link(url: str, official_domains: Iterable[str] | None) -> LinkAssessment:
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        return LinkAssessment(url, None, CheckStatus.CONFLICT, "Malformed URL.")
    if not host:
        return LinkAssessment(url, None, CheckStatus.CONFLICT, "URL has no host.")
    domains = [d.lower() for d in (official_domains or [])]
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        return LinkAssessment(url, host, CheckStatus.CONFLICT,
                              "URL contains user-info ('@'). The real destination is the host after '@'.")
    if _is_ip_literal(host):
        return LinkAssessment(url, host, CheckStatus.CONFLICT, "URL points to a raw IP address.")
    if not host.isascii() or any(label.startswith("xn--") for label in host.split(".")):
        return LinkAssessment(url, host, CheckStatus.CONFLICT,
                              "Host uses non-ASCII or punycode labels (possible look-alike characters).")
    if not domains:
        return LinkAssessment(url, host, CheckStatus.NOT_VERIFIABLE,
                              "No reviewed official domain is available for comparison.")
    if any(host_matches_domain(host, d) for d in domains):
        if parts.scheme.lower() != "https":
            return LinkAssessment(url, host, CheckStatus.CONFLICT, "Official host but the link is not HTTPS.")
        if port not in (None, 443):
            return LinkAssessment(url, host, CheckStatus.CONFLICT, "Official host on a non-standard port.")
        return LinkAssessment(url, host, CheckStatus.MATCHED_SOURCE, "Host is a reviewed official domain.")
    for d in domains:
        core = d.split(".")[0]
        if d in host or core in host:
            return LinkAssessment(url, host, CheckStatus.CONFLICT,
                                  f"Look-alike host. It contains '{core}' but is not '{d}' or its subdomain.")
    return LinkAssessment(url, host, CheckStatus.CONFLICT, "Host is not a reviewed official domain.")


class FetchRefused(RuntimeError):
    pass


Resolver = Callable[[str], list[str]]


def _default_resolver(host: str) -> list[str]:
    return sorted({ai[4][0] for ai in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)})


def _check_target(url: str, allowlist: Iterable[str], resolver: Resolver) -> None:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.scheme != "https":
        raise FetchRefused("only https is allowed")
    if parts.username or parts.password or "@" in parts.netloc:
        raise FetchRefused("user-info in URL is not allowed")
    if parts.port not in (None, 443):
        raise FetchRefused("non-standard port")
    if _is_ip_literal(host) or not any(host_matches_domain(host, d) for d in allowlist):
        raise FetchRefused(f"host {host!r} is not on the reviewed allowlist")
    for addr in resolver(host):
        if not ipaddress.ip_address(addr).is_global:
            raise FetchRefused(f"host {host!r} resolves to non-public address {addr}")


def safe_fetch(url: str, allowlist: Iterable[str], *, resolver: Resolver = _default_resolver,
               transport: httpx.BaseTransport | None = None, max_bytes: int = 200_000,
               max_redirects: int = 2, timeout_s: float = 5.0) -> bytes:
    allow = [d.lower() for d in allowlist]
    current = url
    with httpx.Client(follow_redirects=False, transport=transport, timeout=timeout_s) as client:
        for _ in range(max_redirects + 1):
            _check_target(current, allow, resolver)
            with client.stream("GET", current) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location", "")
                    current = urljoin(current, location)
                    continue
                if resp.status_code != 200:
                    raise FetchRefused(f"unexpected status {resp.status_code}")
                body = bytearray()
                for chunk in resp.iter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise FetchRefused("response is larger than the size limit")
                return bytes(body)
    raise FetchRefused("too many redirects")
