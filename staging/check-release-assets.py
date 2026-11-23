"""Smoke-test the Runs assets using the reviewed package manifest and runtime verifier."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import tarfile
import tempfile

from release_identity import validate_release, verified_asset


def check_assets(package, scratch):
    metadata = json.loads((package / "metadata.json").read_text())
    if metadata.get("package_version") != 3:
        raise ValueError("Runs smoke requires a version 3 package")
    archive = package / "product.tar.gz"
    if (package / "product.tar.gz.sha256").read_text().split() != [sha256(archive.read_bytes()).hexdigest(), archive.name]:
        raise ValueError("Product archive identity mismatch")
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        root = Path(temporary)
        with tarfile.open(archive, "r:gz") as product:
            product.extractall(root / "releases/product", filter="data")
        release = validate_release(root, metadata)
        for path, expected_type in (
            ("/static/rms/run_workflow.css", "text/css; charset=utf-8"),
            ("/static/rms/run_workflow.js", "text/javascript; charset=utf-8"),
        ):
            asset = verified_asset(path, release, metadata)
            if asset is None or not asset[0] or asset[1] != expected_type:
                raise ValueError(f"Packaged asset missing or mistyped: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("scratch", type=Path)
    args = parser.parse_args()
    check_assets(args.package, args.scratch)
    print("PASS packaged Runs assets: inventory, checksum and MIME")
