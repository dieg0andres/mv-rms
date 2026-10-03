"""Build a local reviewed package from explicit Git objects; never deploys."""

import argparse
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

from release_identity import ASSETS


def git(*args):
    return subprocess.check_output(["git", *args])


def build(output, commit, tree):
    if not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (commit, tree)):
        raise ValueError("Supply full reviewed commit and tree identities")
    if git("rev-parse", commit + "^{tree}").decode().strip() != tree:
        raise ValueError("Reviewed commit/tree mismatch")
    output = Path(output)
    if output.exists():
        raise ValueError("Refusing to overwrite an existing package directory")
    archive = git("archive", "--format=tar", commit)
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as contents:
        for member in contents.getmembers():
            if member.isdir():
                continue
            path = Path(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts:
                raise ValueError("Unsupported product archive member")
            files[member.name] = contents.extractfile(member).read()
    for required in ("rms_project/urls.py", "rms/navigation_urls.py", "rms/hypothesis_api_urls.py", "docs/RMS-HN-INTEGRATED-SOURCE-MANIFEST.json", *(url.lstrip("/") for url in ASSETS)):
        if required not in files:
            raise ValueError("Integrated product input missing")
    product_manifest = json.loads(files["docs/RMS-HN-INTEGRATED-SOURCE-MANIFEST.json"])
    for item in product_manifest["files"]:
        data = files[item["path"]]
        if len(data) != item["bytes"] or sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Committed source differs from integrated manifest")
    recipe = {name: files["staging/" + name] for name in ("compose.yaml", "entrypoint.sh", "requirements-staging.lock", "runtime.py", "request_policy.py", "release_identity.py", "create-principals.py", "README.md")}
    recipe["Dockerfile"] = files["staging/Dockerfile.hn"]
    metadata = {"package_version": 2, "integrated_navigation": True, "commit": commit, "tree": tree,
                "summary": "Hypothesis drafts and navigation; invented software records only.",
                "source_manifest_sha256": sha256(files["docs/RMS-HN-INTEGRATED-SOURCE-MANIFEST.json"]).hexdigest(),
                "file_sha256": {path: sha256(data).hexdigest() for path, data in sorted(files.items())}}
    output.mkdir(parents=True)
    compressed = gzip.compress(archive, mtime=0)
    (output / "product.tar.gz").write_bytes(compressed)
    (output / "product.tar.gz.sha256").write_text(sha256(compressed).hexdigest() + "  product.tar.gz\n")
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    for name, data in recipe.items():
        (output / name).write_bytes(data)
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("commit")
    parser.add_argument("tree")
    args = parser.parse_args()
    result = build(args.output, args.commit, args.tree)
    print(json.dumps({"commit": result["commit"], "tree": result["tree"], "source_manifest_sha256": result["source_manifest_sha256"], "deployed": False}))
