#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_PATH = REPO_ROOT / "models.json"
RUN_BENCH = REPO_ROOT / "scripts" / "run_bench.py"
ALL_BENCHES = ["strict-custom-agent", "vague-developer"]


def load_models() -> list[dict]:
    return json.loads(MODELS_PATH.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benches", default=",".join(ALL_BENCHES))
    parser.add_argument("--only", default="")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=1500)
    args = parser.parse_args()

    benches = [b.strip() for b in args.benches.split(",") if b.strip()]
    only = {item.strip() for item in args.only.split(",") if item.strip()}
    models = load_models()
    if only:
        models = [m for m in models if m["slug"] in only]

    if not models:
        print("No models selected", file=sys.stderr)
        return 1

    for bench in benches:
        for model in models:
            result_meta = REPO_ROOT / "results" / bench / model["slug"] / "metadata.json"
            if args.skip_existing and result_meta.exists():
                print(f"skip {bench}/{model['slug']}: metadata exists")
                continue
            cmd = [
                sys.executable,
                str(RUN_BENCH),
                "--bench",
                bench,
                "--provider",
                model["provider"],
                "--slug",
                model["slug"],
                "--display",
                model.get("display", model["slug"]),
                "--timeout-seconds",
                str(args.timeout_seconds),
            ]
            if model.get("note"):
                cmd.extend(["--note", model["note"]])
            if model.get("requested"):
                cmd.extend(["--requested", model["requested"]])
            print(f"running {' '.join(cmd)}")
            proc = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
            if proc.returncode != 0:
                print(f"run failed for {bench}/{model['slug']} with exit {proc.returncode}", file=sys.stderr)
                return proc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
