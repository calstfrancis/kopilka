"""WebDAV sync — supports pCloud, Nextcloud, Disroot, and any WebDAV server."""

import base64
import json
import os
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


# ── Exceptions ────────────────────────────────────────────────────────────────

class WebDAVError(Exception):
    pass


class ConflictError(WebDAVError):
    """Remote file changed since last sync — ETag mismatch on PUT."""
    def __init__(self, remote_etag: str = ""):
        self.remote_etag = remote_etag
        super().__init__("Conflict: remote file was modified since last sync")


class AuthError(WebDAVError):
    pass


# ── Provider presets ──────────────────────────────────────────────────────────

PROVIDERS = {
    "pcloud":    {"label": "pCloud",           "url": "https://webdav.pcloud.com",                          "path_hint": "Kopilka/budget.json"},
    "pcloud_eu": {"label": "pCloud (EU)",       "url": "https://ewebdav.pcloud.com",                         "path_hint": "Kopilka/budget.json"},
    "nextcloud": {"label": "Nextcloud",         "url": "https://your.nextcloud.com/remote.php/webdav",       "path_hint": "Kopilka/budget.json"},
    "disroot":   {"label": "Disroot",           "url": "https://cloud.disroot.org/remote.php/webdav",        "path_hint": "Kopilka/budget.json"},
    "custom":    {"label": "Custom WebDAV",     "url": "",                                                    "path_hint": "Kopilka/budget.json"},
}


# ── Low-level client ──────────────────────────────────────────────────────────

class WebDAVClient:
    """Minimal WebDAV client — PROPFIND / GET / PUT via stdlib urllib."""

    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        creds = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._auth = f"Basic {creds}"

    def _request(
        self,
        method: str,
        url: str,
        headers: dict | None = None,
        body: bytes | None = None,
        timeout: int = 20,
    ) -> tuple[int, dict, bytes]:
        req = urllib.request.Request(url, method=method)
        req.add_header("Authorization", self._auth)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        if body is not None:
            req.data = body

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()
        except urllib.error.URLError as e:
            raise WebDAVError(f"Network error: {e.reason}") from e

    def propfind(self, path: str) -> dict:
        """Return {etag, last_modified} for path. Returns {} if not found."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        body = b"""<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:">
  <D:prop><D:getetag/><D:getlastmodified/></D:prop>
</D:propfind>"""
        status, _headers, data = self._request(
            "PROPFIND", url,
            headers={"Depth": "0", "Content-Type": "application/xml"},
            body=body,
        )
        if status == 401:
            raise AuthError("Authentication failed")
        if status not in (200, 207):
            return {}
        try:
            root = ET.fromstring(data)
            ns = {"D": "DAV:"}
            etag = root.findtext(".//D:getetag", namespaces=ns) or ""
            lastmod = root.findtext(".//D:getlastmodified", namespaces=ns) or ""
            return {"etag": etag.strip('"'), "last_modified": lastmod}
        except ET.ParseError:
            return {}

    def get(self, path: str) -> tuple[bytes, str]:
        """Download file. Returns (content, etag)."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        status, headers, data = self._request("GET", url)
        if status == 401:
            raise AuthError("Authentication failed")
        if status == 404:
            raise WebDAVError(f"File not found on server: {path}")
        if status != 200:
            raise WebDAVError(f"Download failed: HTTP {status}")
        etag = headers.get("ETag", "").strip('"')
        return data, etag

    def put(self, path: str, content: bytes, if_match_etag: str | None = None) -> str:
        """Upload file. Returns new ETag. Raises ConflictError on ETag mismatch (412)."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers: dict = {"Content-Type": "application/json; charset=utf-8"}
        if if_match_etag:
            headers["If-Match"] = f'"{if_match_etag}"'

        status, resp_headers, _ = self._request("PUT", url, headers=headers, body=content)
        if status == 401:
            raise AuthError("Authentication failed")
        if status == 412:
            props = self.propfind(path)
            raise ConflictError(props.get("etag", ""))
        if status not in (200, 201, 204):
            raise WebDAVError(f"Upload failed: HTTP {status}")
        return resp_headers.get("ETag", "").strip('"')

    def mkcol_parents(self, path: str):
        """Ensure all parent directories exist (best-effort)."""
        parts = [p for p in path.split("/") if p]
        for i in range(1, len(parts)):
            partial = "/".join(parts[:i])
            url = f"{self.base_url}/{partial}"
            try:
                self._request("MKCOL", url, timeout=10)
            except Exception:
                pass


# ── High-level sync manager ───────────────────────────────────────────────────

class WebDAVSyncManager:
    """Manages WebDAV sync state for a single budget.json file."""

    def __init__(self, config: dict):
        self._config = config
        self._client: WebDAVClient | None = None
        self._lock = threading.Lock()

    def is_configured(self) -> bool:
        return bool(
            self._config.get("webdav_url")
            and self._config.get("webdav_username")
            and self._config.get("webdav_password")
            and self._config.get("webdav_remote_path")
        )

    def _get_client(self) -> WebDAVClient:
        if self._client is None:
            self._client = WebDAVClient(
                self._config["webdav_url"],
                self._config["webdav_username"],
                self._config["webdav_password"],
            )
        return self._client

    @property
    def _remote_path(self) -> str:
        return self._config.get("webdav_remote_path", "budget.json")

    def get_remote_etag(self) -> str:
        """PROPFIND the remote file. Returns ETag or '' on error."""
        if not self.is_configured():
            return ""
        try:
            props = self._get_client().propfind(self._remote_path)
            return props.get("etag", "")
        except Exception:
            return ""

    def is_remote_newer(self) -> bool:
        """True if remote ETag differs from the last-known ETag in config."""
        if not self.is_configured():
            return False
        remote = self.get_remote_etag()
        known = self._config.get("webdav_etag", "")
        return bool(remote) and remote != known

    def peek_remote_metadata(self) -> dict:
        """Return {last_modified, last_modified_by} from the remote file header."""
        if not self.is_configured():
            return {"last_modified": "", "last_modified_by": "your partner"}
        try:
            content, _ = self._get_client().get(self._remote_path)
            data = json.loads(content)
            meta = data.get("metadata", {})
            return {
                "last_modified": meta.get("last_modified", ""),
                "last_modified_by": meta.get("last_modified_by", "your partner"),
            }
        except Exception:
            return {"last_modified": "", "last_modified_by": "your partner"}

    def download(self, local_path: str) -> str:
        """
        Download the remote budget to local_path.

        Backs up the existing local file first (keeps last 3 backups).
        Returns the new ETag.
        """
        with self._lock:
            client = self._get_client()
            content, etag = client.get(self._remote_path)

            p = Path(local_path)
            if p.exists():
                stamp = datetime.now().strftime("%Y%m%d%H%M%S")
                backup = p.with_suffix(f".backup{stamp}.json")
                p.rename(backup)
                _prune_backups(p, keep=3)

            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)
            return etag

    def upload(self, local_path: str) -> str:
        """
        Upload local_path to the remote.

        Uses If-Match ETag check for optimistic concurrency.
        Raises ConflictError if the remote changed since last sync.
        Returns the new ETag.
        """
        with self._lock:
            client = self._get_client()
            content = Path(local_path).read_bytes()
            known_etag = self._config.get("webdav_etag", "")

            try:
                client.mkcol_parents(self._remote_path)
            except Exception:
                pass

            return client.put(
                self._remote_path,
                content,
                if_match_etag=known_etag if known_etag else None,
            )

    def save_conflict_copy(self, local_path: str) -> Path:
        """
        Download the remote version and save it as a conflict copy.
        Returns the path to the conflict file.
        """
        client = self._get_client()
        content, _ = client.get(self._remote_path)
        p = Path(local_path)
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        conflict_path = p.with_name(f"{p.stem}.conflict{stamp}.json")
        conflict_path.write_bytes(content)
        return conflict_path

    def test_connection(self) -> tuple[bool, str]:
        """Verify credentials and that the remote path's parent is reachable."""
        if not self.is_configured():
            return False, "WebDAV sync is not configured"
        try:
            client = self._get_client()
            parent = str(Path(self._remote_path).parent).replace("\\", "/")
            if not parent or parent == ".":
                parent = ""
            props = client.propfind(parent or "/")
            # If PROPFIND returns something (even empty), auth and URL are good.
            # 404 on the folder is still a successful auth check.
            return True, "Connection successful"
        except AuthError:
            return False, "Authentication failed — check username and password"
        except WebDAVError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Connection failed: {e}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _prune_backups(original_path: Path, keep: int = 3):
    stem = original_path.stem
    parent = original_path.parent
    backups = sorted(parent.glob(f"{stem}.backup*.json"))
    for old in backups[:-keep]:
        try:
            old.unlink()
        except OSError:
            pass


def build_from_config(config: dict) -> WebDAVSyncManager:
    return WebDAVSyncManager(config)


def conflict_files_local(budget_path: str) -> list[Path]:
    """Return local conflict copies (*.conflict*.json) for this budget file."""
    p = Path(budget_path)
    return sorted(p.parent.glob(f"{p.stem}.conflict*.json"))
