#!/usr/bin/env python3
"""Read-only StackOS C3 APT repository audit. No installation or publishing."""
import gzip
import hashlib
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = "https://stackoslinux-dev.github.io/repo/c3/"
TARGETS = ("libgl1-mesa-dri", "mesa-vulkan-drivers", "mesa-utils", "vulkan-tools")
LIMIT = 40 * 1024 * 1024

def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "StackOS-C3-Audit/1.0"})
    with urllib.request.urlopen(req, timeout=25, context=ssl.create_default_context()) as response:
        data = response.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError("Repository response exceeds safety limit")
    return data

def fields(stanza):
    result = {}
    for line in stanza.splitlines():
        if line and not line[0].isspace() and ":" in line:
            key, value = line.split(":", 1)
            result[key] = value.strip()
    return result

def main():
    result = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "repository": BASE, "tls": "failed", "inrelease": "unavailable",
              "index": "unavailable", "packages": {p: "not_checked" for p in TARGETS}}
    try:
        release = get("InRelease")
        result["tls"] = "verified"
        result["inrelease"] = "downloaded_NOT_signature_verified"
        text = release.decode("utf-8", errors="replace")
        index = None
        expected = None
        # Discover index and digest from signed metadata; signature is NOT verified here.
        section = None
        for line in text.splitlines():
            if line == "SHA256:":
                section = "sha256"
                continue
            if line and not line.startswith(" "):
                section = None
            if section == "sha256":
                parts = line.split()
                if len(parts) == 3 and parts[2] in ("Packages.gz", "Packages"):
                    expected, _, index = parts
                    break
        if not index:
            raise ValueError("No Packages or Packages.gz SHA256 entry in InRelease")
        data = get(index)
        if hashlib.sha256(data).hexdigest().lower() != expected.lower():
            raise ValueError("Packages index SHA256 mismatch")
        result["index"] = "sha256_verified_against_unverified_InRelease"
        raw = gzip.decompress(data) if index.endswith(".gz") else data
        found = {}
        for stanza in raw.decode("utf-8", errors="replace").split("\n\n"):
            entry = fields(stanza)
            name = entry.get("Package")
            if name in TARGETS:
                found[name] = entry.get("Version", "version_missing")
        result["packages"] = {p: found.get(p, "missing_from_index") for p in TARGETS}
    except Exception as exc:
        result["error"] = str(exc)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("error") or any(v == "missing_from_index" for v in result["packages"].values()):
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
