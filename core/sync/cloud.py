"""Optional HTTPS sync adapter with fail-closed transport validation."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request


class _HTTPSRedirectGuard(urllib.request.HTTPRedirectHandler):
    """Reject redirects that leave the original HTTPS authority."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        source = urllib.parse.urlparse(req.full_url)
        target = urllib.parse.urlparse(newurl)
        if source.scheme != "https" or target.scheme != "https":
            raise ValueError("secure sync transport rejects insecure redirects")
        if (source.hostname or "").lower() != (target.hostname or "").lower():
            raise ValueError("secure sync transport rejects cross-host redirects")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HTTPJSONSyncProvider:
    def __init__(self, base_url, token=None, timeout=15, allow_insecure_local=False):
        parsed = urllib.parse.urlparse(str(base_url).strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("sync base_url must be an absolute HTTP(S) URL")
        if parsed.scheme == "http":
            host = (parsed.hostname or "").lower()
            if not allow_insecure_local or host not in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("secure sync transport requires HTTPS")
        if timeout <= 0:
            raise ValueError("sync timeout must be positive")
        self.base_url = str(base_url).rstrip("/")
        self.token = token
        self.timeout = timeout
        self._opener = urllib.request.build_opener(_HTTPSRedirectGuard())

    def _request(self, method, path, payload=None):
        if not path.startswith("/") or "://" in path:
            raise ValueError("sync path must be relative")
        data = None if payload is None else json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers=headers,
        )
        with self._opener.open(req, timeout=self.timeout) as response:
            try:
                value = json.loads(response.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("sync provider returned invalid JSON") from exc
        return value

    def push(self, records):
        value = self._request("POST", "/sync/push", records)
        if not isinstance(value, dict):
            raise ValueError("sync push response must be an object")
        pushed = value.get("pushed", 0)
        if not isinstance(pushed, int) or pushed < 0:
            raise ValueError("sync push response has invalid pushed count")
        acknowledged = value.get("acknowledged_ids")
        if acknowledged is not None and (
            not isinstance(acknowledged, list)
            or not all(isinstance(item, (str, int)) for item in acknowledged)
        ):
            raise ValueError("sync push response has invalid acknowledgements")
        return value

    def pull(self, project_id):
        value = self._request("GET", "/sync/pull/" + urllib.parse.quote(str(project_id), safe=""))
        if not isinstance(value, list):
            raise ValueError("sync pull response must be a list")
        return value
