"""Verify an explicit product package and its allowlisted static assets."""

from hashlib import sha256
from pathlib import Path
import re


LEGACY_COMMIT = "0fd772a54bbb1bea7962feb77db21a6c7a6c6dd0"
LEGACY_TREE = "c1219ad5bd24bbb43b11f74938c7b2b4c8e08f77"
ASSETS = {
    "/static/rms/rms_forms.js": "text/javascript; charset=utf-8",
    "/static/rms/draft_shell.js": "text/javascript; charset=utf-8",
    "/static/rms/record_form.js": "text/javascript; charset=utf-8",
    "/static/rms/navigation.css": "text/css; charset=utf-8",
    "/static/rms/test_plan.js": "text/javascript; charset=utf-8",
    "/static/rms/test_plan.css": "text/css; charset=utf-8",
}


def validate_release(root, metadata):
    for key in ("commit", "tree"):
        if not isinstance(metadata.get(key), str) or not re.fullmatch(r"[0-9a-f]{40}", metadata[key]):
            raise ValueError("Invalid explicit release identity")
    if metadata.get("package_version") == 2:
        if metadata.get("integrated_navigation") is not True:
            raise ValueError("Integrated navigation flag missing")
        release = Path(root) / "releases" / "product"
        inventory = metadata.get("file_sha256")
        if not isinstance(inventory, dict) or not inventory:
            raise ValueError("Product file inventory missing")
        for required in ("rms_project/urls.py", "rms/navigation_urls.py", "rms/hypothesis_api_urls.py", *(url.lstrip("/") for url in ASSETS)):
            if required not in inventory:
                raise ValueError("Integrated product input missing")
        for name, expected in inventory.items():
            relative = Path(name)
            if not relative.parts or relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Invalid product path")
            path = (release / relative).resolve(strict=True)
            if not path.is_relative_to(release.resolve(strict=True)) or sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Product file identity mismatch")
        return release
    if metadata.get("commit") != LEGACY_COMMIT or metadata.get("tree") != LEGACY_TREE:
        raise ValueError("Legacy product pin changed")
    release = Path(root) / "releases" / LEGACY_COMMIT
    if sha256((release / "static/rms/rms_forms.js").read_bytes()).hexdigest() != metadata.get("static_sha256"):
        raise ValueError("Legacy static identity mismatch")
    return release


def version_page_requested(path, metadata):
    return path == "/__staging/version" or (path == "/" and metadata.get("package_version") != 2)


def verified_asset(path, release, metadata):
    if path not in ASSETS:
        return None
    relative = path.lstrip("/")
    expected = metadata.get("file_sha256", {}).get(relative) if metadata.get("package_version") == 2 else metadata.get("static_sha256") if path == "/static/rms/rms_forms.js" else None
    if expected is None:
        return None
    content = (Path(release) / relative).read_bytes()
    if sha256(content).hexdigest() != expected:
        raise ValueError("Static identity mismatch")
    return content, ASSETS[path]
