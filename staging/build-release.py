"""Package a reviewed RMS commit and tree for the existing private Compose deployment."""

import argparse
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def build_release(output, commit, tree):
    recipe = spec_from_file_location("rms_package", Path(__file__).with_name("build-hn-package.py"))
    module = module_from_spec(recipe)
    recipe.loader.exec_module(module)
    return module.build(
        output, commit, tree, manifest_path=None,
        summary="Research workspace for versioned synthetic records.",
        extra_required=("rms/test_plan_schema.json", "rms/test_plan_navigation_urls.py",
                        "rms/test_plan_api_urls.py", "templates/rms/base.html",
                        "templates/rms/includes/navigation.html", "templates/rms/navigation.html"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New package directory")
    parser.add_argument("commit", help="Full reviewed Git commit")
    parser.add_argument("tree", help="Full reviewed Git tree")
    args = parser.parse_args()
    metadata = build_release(args.output, args.commit, args.tree)
    print(f"Packaged {metadata['commit']} / {metadata['tree']}")
