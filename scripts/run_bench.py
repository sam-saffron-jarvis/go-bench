#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STRICT_TEMPLATE = REPO_ROOT / "benches" / "strict-custom-agent" / "template"
STRICT_VERIFIER = STRICT_TEMPLATE / "agent" / "scripts" / "verify-board.mjs"
RESULTS_ROOT = REPO_ROOT / "results"
RUNS_ROOT = REPO_ROOT / ".runs"

STRICT_PROMPT = (
    "Build the board described in SPEC.md. Create or replace workspace/board.html. "
    "Use the verify_board tool repeatedly until it passes. When the board passes, reply DONE."
)
VAGUE_PROMPT = "build a standalone 9x9 fully functioning go board in index.html"

STATS_RE = re.compile(
    r"Stats:\s+(?P<elapsed>[0-9.]+)s"
    r"(?:\s+\(llm\s+(?P<llm_time>[0-9.]+)s\s+\+\s+tool\s+(?P<tool_time>[0-9.]+)s\))?"
    r"\s+\|\s+(?P<input>[0-9.]+[kKmM]?)\s+in"
    r"(?:\s+\(cache:\s+(?P<cache>[0-9.]+[kKmM]?)\s+read\))?"
    r"\s+→\s+(?P<output>[0-9.]+[kKmM]?)\s+out\s+"
    r"\(last:\s+(?P<last_in>[0-9.]+[kKmM]?)→(?P<last_out>[0-9.]+[kKmM]?)(?:,\s+peak:\s+(?P<peak>[0-9.]+[kKmM]?))?\)\s+\|\s+"
    r"(?P<tools>\d+)\s+tools\s+\|\s+(?P<llm_calls>\d+)\s+llm calls"
)


def parse_compact_number(value: str) -> int:
    lower = value.lower()
    mult = 1
    if lower.endswith("k"):
        mult = 1000
        lower = lower[:-1]
    elif lower.endswith("m"):
        mult = 1000000
        lower = lower[:-1]
    return int(float(lower) * mult)


def sh(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def term_llm_version() -> str:
    proc = sh(["term-llm", "--version"], cwd=REPO_ROOT)
    return proc.stdout.strip()


def unload_ollama() -> None:
    proc = sh(["bash", "-lc", "ollama ps | awk 'NR>1 {print $1}'"], cwd=REPO_ROOT)
    names = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    for name in names:
        sh(["ollama", "stop", name], cwd=REPO_ROOT, timeout=60)
    if names:
        time.sleep(1)


def parse_stats(log_text: str) -> dict | None:
    lines = [line.strip() for line in log_text.splitlines() if line.strip().startswith("Stats:")]
    if not lines:
        return None
    raw = lines[-1]
    match = STATS_RE.search(raw)
    if not match:
        return {"raw": raw}
    data = match.groupdict()
    parsed = {
        "raw": raw,
        "elapsed_seconds": float(data["elapsed"]),
        "input_tokens": parse_compact_number(data["input"]),
        "output_tokens": parse_compact_number(data["output"]),
        "last_input_tokens": parse_compact_number(data["last_in"]),
        "last_output_tokens": parse_compact_number(data["last_out"]),
        "tool_calls": int(data["tools"]),
        "llm_calls": int(data["llm_calls"]),
    }
    if data.get("cache"):
        parsed["cache_read_tokens"] = parse_compact_number(data["cache"])
    if data.get("peak"):
        parsed["peak_tokens"] = parse_compact_number(data["peak"])
    if data.get("llm_time"):
        parsed["llm_seconds"] = float(data["llm_time"])
    if data.get("tool_time"):
        parsed["tool_seconds"] = float(data["tool_time"])
    return parsed


def prepare_temp_dir(bench: str, slug: str) -> Path:
    temp_dir = RUNS_ROOT / bench / slug
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.parent.mkdir(parents=True, exist_ok=True)
    if bench == "strict-custom-agent":
        shutil.copytree(STRICT_TEMPLATE, temp_dir)
        (temp_dir / "workspace").mkdir(exist_ok=True)
    elif bench == "vague-developer":
        temp_dir.mkdir(parents=True, exist_ok=True)
    else:
        raise ValueError(f"unknown bench: {bench}")
    return temp_dir


def generated_output_path(bench: str, temp_dir: Path) -> Path:
    if bench == "strict-custom-agent":
        return temp_dir / "workspace" / "board.html"
    if bench == "vague-developer":
        return temp_dir / "index.html"
    raise ValueError(f"unknown bench: {bench}")


def command_for(bench: str, provider: str) -> list[str]:
    common = ["--no-session", "--text", "--stats", "--yolo", "--provider", provider]
    if bench == "strict-custom-agent":
        return [
            "term-llm",
            "ask",
            *common,
            "--max-turns",
            "30",
            "--agent",
            "./agent",
            "--read-dir",
            ".",
            "--write-dir",
            "./workspace",
            "-f",
            "./SPEC.md",
            STRICT_PROMPT,
        ]
    if bench == "vague-developer":
        return [
            "term-llm",
            "ask",
            "@developer",
            *common,
            "--read-dir",
            ".",
            "--write-dir",
            ".",
            VAGUE_PROMPT,
        ]
    raise ValueError(f"unknown bench: {bench}")


def copy_generated_tree(temp_dir: Path, bench: str, result_dir: Path) -> None:
    generated_dir = result_dir / "generated"
    if generated_dir.exists():
        shutil.rmtree(generated_dir)
    generated_dir.mkdir(parents=True)
    if bench == "strict-custom-agent":
        for name in ["agent", "SPEC.md", "workspace"]:
            src = temp_dir / name
            dest = generated_dir / name
            if src.is_dir():
                shutil.copytree(src, dest)
            elif src.exists():
                shutil.copy2(src, dest)
    else:
        for child in temp_dir.iterdir():
            dest = generated_dir / child.name
            if child.is_dir():
                shutil.copytree(child, dest)
            else:
                shutil.copy2(child, dest)


def verify_output(html_path: Path, result_dir: Path) -> tuple[bool, str, int]:
    proc = sh(["node", str(STRICT_VERIFIER), str(html_path)], cwd=REPO_ROOT, timeout=180)
    (result_dir / "verify.log").write_text(proc.stdout, encoding="utf-8")
    return proc.returncode == 0, proc.stdout, proc.returncode


def render_screenshot(html_path: Path, result_dir: Path) -> str | None:
    if not html_path.exists():
        return None
    out = result_dir / "screenshot.png"
    proc = sh(["bash", str(REPO_ROOT / "scripts" / "render_screenshot.sh"), str(html_path), str(out)], cwd=REPO_ROOT, timeout=180)
    if proc.returncode != 0:
        (result_dir / "screenshot.log").write_text(proc.stdout, encoding="utf-8")
        return None
    return out.name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", required=True, choices=["strict-custom-agent", "vague-developer"])
    parser.add_argument("--provider", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--display", default="")
    parser.add_argument("--timeout-seconds", type=int, default=1500)
    parser.add_argument("--note", default="")
    parser.add_argument("--requested", default="")
    args = parser.parse_args()

    bench = args.bench
    provider = args.provider
    slug = args.slug
    result_dir = RESULTS_ROOT / bench / slug
    if result_dir.exists():
        shutil.rmtree(result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = prepare_temp_dir(bench, slug)
    if provider.startswith("ollama:"):
        unload_ollama()

    command = command_for(bench, provider)
    command_text = subprocess.list2cmdline(command)
    (result_dir / "command.txt").write_text(command_text + "\n", encoding="utf-8")

    start = time.time()
    timed_out = False
    try:
        proc = sh(command, cwd=temp_dir, timeout=args.timeout_seconds)
        run_output = proc.stdout
        return_code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        run_output = (exc.stdout or "") + "\nTIMEOUT\n"
        return_code = 124
    elapsed = time.time() - start

    (result_dir / "run.log").write_text(run_output, encoding="utf-8")

    html_path = generated_output_path(bench, temp_dir)
    verified, verify_output_text, verify_returncode = verify_output(html_path, result_dir)
    screenshot_name = render_screenshot(html_path, result_dir)
    copy_generated_tree(temp_dir, bench, result_dir)

    stats = parse_stats(run_output)
    metadata = {
        "bench": bench,
        "slug": slug,
        "display": args.display or slug,
        "provider": provider,
        "requested": args.requested or None,
        "note": args.note or None,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "term_llm_version": term_llm_version(),
        "command": command,
        "command_text": command_text,
        "prompt": STRICT_PROMPT if bench == "strict-custom-agent" else VAGUE_PROMPT,
        "timeout_seconds": args.timeout_seconds,
        "run": {
            "exit_code": return_code,
            "timed_out": timed_out,
            "elapsed_seconds": round(elapsed, 3),
            "stats": stats,
        },
        "verification": {
            "passed": verified,
            "exit_code": verify_returncode,
            "output": verify_output_text.strip(),
        },
        "artifacts": {
            "run_log": "run.log",
            "verify_log": "verify.log",
            "generated_dir": "generated",
            "screenshot": screenshot_name,
        },
        "output": {
            "expected_file": str(html_path.relative_to(temp_dir)),
            "exists": html_path.exists(),
        },
    }
    (result_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    status = "PASS" if verified else "FAIL"
    stats_text = stats["raw"] if stats and "raw" in stats else "no stats"
    print(f"[{bench}] {slug}: {status} | {stats_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
