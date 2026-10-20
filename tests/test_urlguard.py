"""Allowlist-only fetch guard (SSRF, redirects, size). Mock transport only, no network."""
import httpx
import pytest

from app.urlguard import FetchRefused, extract_urls, safe_fetch

ALLOW = ["northbridge-university.example"]


def public_resolver(host):
    return ["93.184.216.34"]


def test_allowlisted_https_fetch_works():
    t = httpx.MockTransport(lambda r: httpx.Response(200, content=b"ok"))
    assert safe_fetch("https://www.northbridge-university.example/how-to-pay", ALLOW, resolver=public_resolver,
                      transport=t) == b"ok"


@pytest.mark.parametrize("url", [
    "https://evil.example/",
    "https://northbridge-university.example.evil.example/",
    "http://www.northbridge-university.example/",
    "https://www.northbridge-university.example@evil.example/",
    "https://127.0.0.1/",
    "https://www.northbridge-university.example:8080/",
])
def test_refuses_untrusted_targets(url):
    t = httpx.MockTransport(lambda r: httpx.Response(200, content=b"should not be reached"))
    with pytest.raises(FetchRefused):
        safe_fetch(url, ALLOW, resolver=public_resolver, transport=t)


@pytest.mark.parametrize("addr", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.1", "::1"])
def test_refuses_private_resolution(addr):
    t = httpx.MockTransport(lambda r: httpx.Response(200))
    with pytest.raises(FetchRefused, match="non-public"):
        safe_fetch("https://www.northbridge-university.example/", ALLOW, resolver=lambda h: [addr], transport=t)


def test_refuses_redirect_to_untrusted_host():
    def handler(request):
        if request.url.host == "www.northbridge-university.example":
            return httpx.Response(302, headers={"location": "https://evil.example/steal"})
        return httpx.Response(200, content=b"evil")
    with pytest.raises(FetchRefused, match="not on the reviewed allowlist"):
        safe_fetch("https://www.northbridge-university.example/", ALLOW, resolver=public_resolver,
                   transport=httpx.MockTransport(handler))


def test_follows_redirect_inside_allowlist():
    def handler(request):
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        return httpx.Response(200, content=b"new")
    assert safe_fetch("https://www.northbridge-university.example/old", ALLOW, resolver=public_resolver,
                      transport=httpx.MockTransport(handler)) == b"new"


def test_refuses_oversized_response():
    t = httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 300_000))
    with pytest.raises(FetchRefused, match="size limit"):
        safe_fetch("https://www.northbridge-university.example/", ALLOW, resolver=public_resolver, transport=t)


def test_extract_urls_is_bounded_and_deduplicated():
    text = " ".join(["https://a.example/x"] * 5 + [f"https://h{i}.example" for i in range(40)])
    urls = extract_urls(text)
    assert urls[0] == "https://a.example/x" and len(urls) == 20
