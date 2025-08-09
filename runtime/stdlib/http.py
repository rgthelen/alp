import os
import urllib.request
import urllib.parse
import ipaddress


def register(reg):
    def _http_is_private_host(host: str) -> bool:
        try:
            ip = ipaddress.ip_address(host)
            return ip.is_private or ip.is_loopback or ip.is_link_local
        except ValueError:
            return host in ("localhost",)

    def _http_allowed(url: str) -> bool:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname or ""
        if not host:
            return False
        block_local = os.getenv("ALP_HTTP_BLOCK_LOCAL", "1") != "0"
        if block_local and _http_is_private_host(host):
            return False
        allowlist = os.getenv("ALP_HTTP_ALLOWLIST", "").strip()
        if not allowlist:
            return False
        allowed_hosts = {h.strip().lower() for h in allowlist.split(",") if h.strip()}
        return host.lower() in allowed_hosts

    def _http_fetch(method: str, url: str, data_bytes: bytes | None, headers: dict | None):
        if not _http_allowed(url):
            raise RuntimeError("HTTP blocked by allowlist. Set ALP_HTTP_ALLOWLIST=host1,host2")
        timeout = float(os.getenv("ALP_HTTP_TIMEOUT", "10"))
        req = urllib.request.Request(url=url, method=method)
        for k, v in (headers or {}).items():
            req.add_header(str(k), str(v))
        max_bytes = int(os.getenv("ALP_HTTP_MAX_BYTES", "1000000"))
        with urllib.request.urlopen(req, data=data_bytes, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            body = resp.read(max_bytes)
        try:
            text = body.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        return {"status": int(status), "text": text}

    def http(a, ctx):
        method = str(a.get("method") or "GET").upper()
        url = a.get("url")
        if not isinstance(url, str) or not url:
            raise RuntimeError("http requires 'url'")
        headers = a.get("headers") if isinstance(a.get("headers"), dict) else None
        data_bytes = None
        if "json" in a and a.get("json") is not None:
            import json as _json
            payload = _json.dumps(a.get("json")).encode("utf-8")
            headers = headers or {}
            headers.setdefault("Content-Type", "application/json")
            data_bytes = payload
        elif "data" in a and a.get("data") is not None:
            data_bytes = (str(a.get("data"))).encode("utf-8")
        return _http_fetch(method, url, data_bytes, headers)

    reg("http", http)
