#!/usr/bin/env python3
"""Validate deterministic path sequencing for the reviewed Aprende content set."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_SCRIPT = os.path.join(SCRIPT_DIR, "build_content_db.py")


def load_build_module():
    spec = importlib.util.spec_from_file_location("build_content_db", BUILD_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {BUILD_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", help="optional path for the full sequencing report JSON")
    args = parser.parse_args()

    build = load_build_module()
    lexemes, _sentences, _accepted, _sentence_lexeme, _conj, exercises, nodes = build.vetted_sample()
    report = build.validate_sequencing(lexemes, exercises, nodes)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w") as f:
            json.dump(report, f, indent=2)
            f.write("\n")

    print(json.dumps({
        "status": report["status"],
        "summary": report["summary"],
        "counts": report["counts"],
        "failureCounts": {
            key: len(value)
            for key, value in report["failures"].items()
        },
    }, indent=2))
    build.enforce_sequencing(report)


if __name__ == "__main__":
    main()
