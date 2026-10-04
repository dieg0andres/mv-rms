"""Prepare an exact Test Plan candidate package; does not apply a release."""

import argparse
import importlib.util
import json
from pathlib import Path


def build(output, commit, tree):
    recipe = Path(__file__).with_name("build-hn-package.py")
    spec = importlib.util.spec_from_file_location("rms_existing_package", recipe)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build(
        output, commit, tree,
        manifest_path="docs/RMS-TP-INTEGRATED-SOURCE-MANIFEST.json",
        summary="Strategy Specification and Test Plan; invented software records only.",
        extra_required=(
            "docs/RMS_STRATEGY_SPECIFICATION_AND_TEST_PLAN_DESIGN_CONTRACT_V1_0.md",
            "docs/RMS-TP-API-1.md",
            "rms/test_plan_schema.json",
            "rms/test_plan_api_urls.py",
            "rms/test_plan_navigation_urls.py",
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("commit")
    parser.add_argument("tree")
    args = parser.parse_args()
    result = build(args.output, args.commit, args.tree)
    print(json.dumps({
        "commit": result["commit"], "tree": result["tree"],
        "source_manifest_sha256": result["source_manifest_sha256"],
        "deployed": False,
    }))
