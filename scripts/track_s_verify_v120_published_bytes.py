#!/usr/bin/env python3
"""Independently compare PyCRMKit v1.2.0 published GitHub and PyPI bytes.

No third-party Python packages, credentials, mutation, or publishing.
Success means BOTH downloaded wheel/sdist bytes match each other AND their
separately published SHA256 digest and size metadata. Fail closed otherwise.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

REPO = "tawounfouet/pycrmkit"
VERSION = "1.2.0"
GITHUB_API = f"https://api.github.com/repos/{REPO}/releases/tags/v{VERSION}"
PYPI_API = f"https://pypi.org/pypi/pycrmkit/{VERSION}/json"
FILES = ("pycrmkit-1.2.0-py3-none-any.whl", "pycrmkit-1.2.0.tar.gz")
MAX_METADATA = 3 * 1024 * 1024
MAX_ARTIFACT = 16 * 1024 * 1024


def _load(url: str, max_bytes: int, *, allowed_host: str) -> bytes:
    """Make a bounded public HTTPS request with an explicit origin check."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != allowed_host:
        raise ValueError("Unexpected artifact or metadata origin")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "PyCRMKit-Track-S-Release-Audit/1.0"},
    )
    with urllib.request.urlopen(request, timeout=35) as response:
        payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError("Remote artifact exceeds size limit")
    return payload


def _json(url: str, host: str) -> dict[str, Any]:
    parsed = json.loads(_load(url, MAX_METADATA, allowed_host=host))
    if not isinstance(parsed, dict):
        raise ValueError("Metadata is not a JSON object")
    return parsed


def verify() -> dict[str, Any]:
    github = _json(GITHUB_API, "api.github.com")
    pypi = _json(PYPI_API, "pypi.org")
    if (
        github.get("tag_name") != f"v{VERSION}"
        or github.get("draft") is not False
        or github.get("prerelease") is not False
    ):
        raise ValueError("GitHub Release identity is not a published stable v1.2.0")
    if pypi.get("info", {}).get("version") != VERSION:
        raise ValueError("PyPI package version differs from v1.2.0")

    gh_files = {x.get("name"): x for x in github.get("assets", [])}
    pi_files = {x.get("filename"): x for x in pypi.get("urls", [])}
    evidence: list[dict[str, Any]] = []
    for filename in FILES:
        gh = gh_files.get(filename)
        pi = pi_files.get(filename)
        if not isinstance(gh, dict) or not isinstance(pi, dict):
            raise ValueError(f"Missing published wheel/sdist: {filename}")
        gh_url = gh.get("browser_download_url")
        pi_url = pi.get("url")
        if not isinstance(gh_url, str) or not isinstance(pi_url, str):
            raise ValueError(f"No public artifact URL for {filename}")
        # Require the exact expected named GitHub Release asset.
        expected_gh_url = f"https://github.com/{REPO}/releases/download/v{VERSION}/{filename}"
        if gh_url != expected_gh_url:
            raise ValueError(f"Unexpected GitHub asset URL for {filename}")
        gh_data = _load(gh_url, MAX_ARTIFACT, allowed_host="github.com")
        pi_data = _load(pi_url, MAX_ARTIFACT, allowed_host="files.pythonhosted.org")
        gh_hash = hashlib.sha256(gh_data).hexdigest()
        pi_hash = hashlib.sha256(pi_data).hexdigest()
        same_bytes = gh_data == pi_data
        hash_matches = (
            gh_hash == pi_hash
            and gh.get("digest") == "sha256:" + gh_hash
            and pi.get("digests", {}).get("sha256") == pi_hash
            and gh.get("size") == len(gh_data)
            and pi.get("size") == len(pi_data)
        )
        evidence.append(
            {
                "filename": filename,
                "github_sha256_computed": gh_hash,
                "pypi_sha256_computed": pi_hash,
                "github_api_sha256": gh.get("digest"),
                "pypi_api_sha256": pi.get("digests", {}).get("sha256"),
                "github_size": len(gh_data),
                "pypi_size": len(pi_data),
                "byte_identical": same_bytes,
                "verified": same_bytes and hash_matches,
            }
        )

    return {
        "project": REPO,
        "version": VERSION,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "github_release": github.get("html_url"),
        "github_published_at": github.get("published_at"),
        "pypi_release": f"https://pypi.org/project/pycrmkit/{VERSION}/",
        "files": evidence,
        "all_verified": all(x["verified"] for x in evidence),
    }


def main() -> int:
    try:
        evidence = verify()
    except (ValueError, TypeError, KeyError, OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        # Never reveal remote error bodies or user environment secrets.
        print(json.dumps({"status": "INCOMPLETE", "error_type": type(exc).__name__}))
        return 2
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["all_verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
